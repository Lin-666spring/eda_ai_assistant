"""立创 EDA V3 专业版 ``.epro2`` 工程解析器

``.epro2`` 本质是 ZIP：

- ``project2.json``   工程元信息（title / editorVersion / tags ...）
- ``<工程名>.epru``   工程日志，**JSON Lines**
- ``IMAGE/*.webp``    图片资源（忽略）

``.epru`` 每行格式为 ``{meta}||{原子对象}|``；meta 形如
``{"type":"LINE","ticket":706,"id":"e61"}``，原子对象是元素本体。
文档边界由 ``DOCHEAD`` 元素标记（``{"docType":"PCB"|"FOOTPRINT"|"DEVICE"|...}``），
元素按出现顺序归属于最近的 ``DOCHEAD``。

关键结论（对 78 个真实工程实测，见 memories/epro2-format.md）：

1. **几何数值单位是 mil**（0.001 inch），``CANVAS.unit`` 只是界面显示偏好，
   不可信。判据：立创默认过孔 ``holeDiameter=11.811 / viaDiameter=19.685``
   → 0.3mm / 0.5mm；若按 mm 解释则是 11.8mm 钻孔，物理上不可能。
2. **PCB 文档里没有 PAD**：焊盘定义在嵌入的 ``FOOTPRINT`` 文档；
   PCB 的 ``COMPONENT`` 通过其子 ``ATTR``（``key="Footprint"``）拿到
   封装文档 uuid。
3. **网络归属走 ``PAD_NET``**：meta id 为
   ``["PAD_NET", <componentId>, <padNumber>, <padElementId>]``，
   atom 的 ``padNet`` 才是网络名。``NET`` 元素本身只存
   差分对 / 等长组信息。
4. **BOM 字段在 ``DEVICE`` 文档的 ``META.attributes``**：
   ``Supplier Part``(如 C1523) / ``Manufacturer Part`` / ``Value`` /
   ``Supplier Footprint`` / ``Add into BOM`` 等。

因此单个 ``.epro2`` 可同时重建 PCB（网络/走线/过孔/覆铜/元件坐标）
与 BOM，无需任何下游导出。
"""

from __future__ import annotations

import io
import json
import logging
import math
import re
import statistics
import zipfile
from pathlib import Path
from typing import Iterator, Optional

from .models import PCBData, PCBNet, PCBTrace, PCBVia
from .parser import PCBParseStrategy
from ..exceptions import PCBParseError

logger = logging.getLogger(__name__)

#: mil → mm
MIL_TO_MM = 0.0254

_META_TYPE_RE = re.compile(r'^\{"type":"([A-Za-z0-9_]+)"')

#: LAYER 元素缺失时的兜底层名（立创默认层 ID）
_FALLBACK_LAYERS: dict[int, str] = {
    1: "Top Layer",
    2: "Bottom Layer",
    3: "Top Silkscreen Layer",
    4: "Bottom Silkscreen Layer",
    5: "Top Paste Mask Layer",
    6: "Bottom Paste Mask Layer",
    7: "Top Solder Mask Layer",
    8: "Bottom Solder Mask Layer",
    9: "Board Outline",
    10: "Multi Layer",
    11: "Board Outline",
    12: "Document Layer",
    13: "Mechanical Layer",
}

#: 需要保留原子的元素类型（其余只计数，避免解析开销）
_KEEP_PCB = frozenset({
    "CANVAS", "LAYER", "NET", "LINE", "VIA", "PAD", "PAD_NET", "POUR",
    "COMPONENT", "ATTR", "POLY", "FILL",
})


class Epro2Parser(PCBParseStrategy):
    """立创 EDA V3 ``.epro2`` 工程解析器

    产物是一个 :class:`PCBData`，其中:

    - ``nets``      网络 → 引脚（``位号.焊盘号``，来自 PAD_NET）
    - ``traces``    走线，按 (网络, 层) 聚合为折线，坐标为 **mm**
    - ``vias``      过孔（drill/pad 为 mm）
    - ``copper_pours`` 覆铜（网络名 + 层 + 名称）
    - ``component_positions`` 位号 → x/y(mm)/rotation/层
    - ``board_outline`` 板框包围盒（mm）
    - ``bom_items`` 由 DEVICE 库属性聚合出的 BOM 行（dict 列表）
    - ``metadata``  工程元信息与元素计数
    """

    # ──────────────── 对外入口 ────────────────

    def parse(self, file_path: str) -> PCBData:
        path = Path(file_path)
        if not path.exists():
            raise PCBParseError(f"文件不存在: {file_path}")
        if path.suffix.lower() != ".epro2":
            raise PCBParseError(
                f"不支持的文件格式: {path.suffix}，V3 专业版工程需要 .epro2"
            )

        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                epru = next((n for n in names if n.endswith(".epru")), None)
                if not epru:
                    raise PCBParseError(
                        f"epro2 包中未找到 .epru 工程日志，包内容: {names}"
                    )
                # 工程日志是追加式历史：38% 金样含 2~12 个 PCB 文档快照，
                # 全部合并会把不同版本的元件/走线/覆铜混在一起（实测 QU1
                # 同时落在新旧两个坐标上）。只解析最后一个 PCB 文档=最新快照
                target = _last_pcb_doc_uuid(zf, epru)
                raw = self._scan(zf, epru, target)
        except zipfile.BadZipFile as e:
            raise PCBParseError(f"epro2 文件无法作为 ZIP 打开: {e}")

        return self._assemble(raw, path)

    # ──────────────── 扫描 .epru ────────────────

    def _scan(self, zf: zipfile.ZipFile, epru: str,
              target_uuid: Optional[str] = None) -> dict:
        names = zf.namelist()

        raw: dict = {
            "epru": epru,
            "project2": {},
            "doc_counts": {},
            "doc_titles": {},
            "canvas": None,
            "layers": {},
            "nets_defined": [],
            "net_rules": {},          # 网络 → {differential, equal_length}
            "segments": [],           # (net, layer_id, width_raw, x1,y1,x2,y2)
            "line_elements": 0,
            "vias": [],
            "pad_nets": [],           # (component_id, pad_number, net, pad_elem_id)
            "orphan_nets": set(),     # 有 orphan 焊盘记录的网络（几何不完整）
            "pcb_pads": [],
            "pours": [],
            "net_fills": [],          # 带网络的 FILL 实体铜形（补丁铜/手绘铜皮）
            "net_polys": [],          # 带网络的 POLY 多段线铜形
            "polygons": [],           # BOARD_OUTLINE
            "components": {},         # component_id → 位置/层
            "comp_attrs": {},         # component_id → {key: value}
            "devices": {},            # device uuid → DEVICE META.attributes
            "device_titles": {},      # device uuid → META.title
            "footprint_names": {},    # footprint uuid → FOOTPRINT META.title（封装名）
            "footprint_pads": {},     # (footprint uuid, pad 元素 id) → 焊盘信息
            "pcb_target": target_uuid,  # 只解析的最新 PCB 文档 uuid
            "type_counts": {},
        }

        if "project2.json" in names:
            try:
                raw["project2"] = json.loads(
                    zf.read("project2.json").decode("utf-8")
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("project2.json 解析失败: %s", e)

        with zf.open(epru) as fh:
            for meta, atom in _iter_atoms(fh):
                self._consume(meta, atom, raw)

        return raw

    def _consume(self, meta: dict, atom: dict, raw: dict) -> None:
        """把单个元素累积到 raw 中（仅在扫描阶段调用）"""
        t = meta.get("type") or ""
        raw["type_counts"][t] = raw["type_counts"].get(t, 0) + 1

        if t == "DOCHEAD":
            doc_type = atom.get("docType")
            raw["cur_doc"] = doc_type
            raw["doc_counts"][doc_type] = raw["doc_counts"].get(doc_type, 0) + 1
            raw["cur_doc_uuid"] = atom.get("uuid")
            return

        doc = raw.get("cur_doc")
        mid = meta.get("id")

        if doc == "PCB" and raw.get("pcb_target") and \
                raw.get("cur_doc_uuid") != raw["pcb_target"]:
            return  # 历史 PCB 快照，跳过（只解析最新一个）

        if doc == "DEVICE":
            if t == "META":
                uuid = raw.get("cur_doc_uuid")
                if uuid:
                    raw["devices"][uuid] = atom.get("attributes") or {}
                    raw["device_titles"][uuid] = atom.get("title") or ""
            return

        if doc == "SYMBOL":
            return

        if doc == "FOOTPRINT":
            uuid = raw.get("cur_doc_uuid")
            if t == "META":
                if uuid:
                    raw["footprint_names"].setdefault(uuid, atom.get("title") or "")
            elif t == "PAD" and mid and uuid:
                # 焊盘号：BGA 等是 A1/B2 这种字母数字，PAD_NET 的第 3 段可能
                # 退化成元素 id，需要用这里建立 (封装, 元素id) → 焊盘 映射；
                # 相对坐标一并保留（孤岛判定等几何规则要用绝对焊盘位置）
                raw["footprint_pads"][(uuid, str(mid))] = {
                    "num": str(atom.get("num") or ""),
                    "x": _num(atom.get("centerX")),
                    "y": _num(atom.get("centerY")),
                    "layer_id": atom.get("layerId"),
                    "thru": atom.get("hole") is not None,
                }
            return

        if doc != "PCB" or t not in _KEEP_PCB:
            return

        if t == "CANVAS":
            if raw["canvas"] is None:
                raw["canvas"] = atom
        elif t == "LAYER":
            lid = _layer_id(meta)
            if lid is not None:
                raw["layers"][lid] = (
                    atom.get("layerName") or _FALLBACK_LAYERS.get(lid, f"Layer{lid}")
                )
        elif t == "NET":
            name = _net_name(mid)
            if name is not None and name not in raw["nets_defined"]:
                raw["nets_defined"].append(name)
            if name:
                raw["net_rules"][name] = {
                    "differential": atom.get("differentialName"),
                    "equal_length": atom.get("equalLengthGroupName"),
                }
        elif t == "LINE":
            raw["line_elements"] += 1
            net = atom.get("netName") or ""
            if not net:
                return
            raw["segments"].append((
                net,
                atom.get("layerId"),
                _num(atom.get("width")),
                _num(atom.get("startX")), _num(atom.get("startY")),
                _num(atom.get("endX")), _num(atom.get("endY")),
            ))
        elif t == "VIA":
            raw["vias"].append({
                "net": atom.get("netName") or "",
                "x": _num(atom.get("centerX")),
                "y": _num(atom.get("centerY")),
                "hole": _num(atom.get("holeDiameter")),
                "pad": _num(atom.get("viaDiameter")),
                "type": atom.get("viaType"),
            })
        elif t == "PAD_NET":
            parsed = _parse_pad_net_id(mid)
            if parsed:
                cid, pad_num, pad_elem = parsed
                raw["pad_nets"].append((cid, pad_num, atom.get("padNet") or "", pad_elem))
        elif t == "PAD":
            raw["pcb_pads"].append({
                "net": atom.get("netName") or "",
                "num": str(atom.get("num") or ""),
                "x": _num(atom.get("centerX")),
                "y": _num(atom.get("centerY")),
                "layer_id": atom.get("layerId"),
            })
        elif t == "POUR":
            raw["pours"].append({
                "net": atom.get("netName") or "",
                "layer_id": atom.get("layerId"),
                "name": atom.get("name") or "",
                "rings": _ring_count(atom.get("path")),
                "path": atom.get("path") or [],
            })
        elif t == "POLY":
            if atom.get("polyType") == "BOARD_OUTLINE":
                raw["polygons"].append(atom.get("path") or [])
            elif atom.get("netName"):
                # 手绘多段线铜皮（带网络名才会导电；10/78 板共 155 条）
                raw["net_polys"].append({
                    "net": atom["netName"],
                    "layer_id": atom.get("layerId"),
                    "path": atom.get("path") or [],
                })
        elif t == "FILL":
            if atom.get("netName"):
                # 实体填充铜形（补丁铜）。不带网络的 FILL 是图形不是导体；
                # 层归属在组装时按「本文件铜层集合」过滤
                raw["net_fills"].append({
                    "net": atom["netName"],
                    "layer_id": atom.get("layerId"),
                    "path": atom.get("path") or [],
                })
        elif t == "COMPONENT":
            raw["components"][mid] = {
                "x": _num(atom.get("x")),
                "y": _num(atom.get("y")),
                "rotation": _num(atom.get("angle")),
                "layer_id": atom.get("layerId"),
                "attrs": atom.get("attrs") or {},
            }
        elif t == "ATTR":
            parent = atom.get("parentId")
            if parent:
                raw["comp_attrs"].setdefault(parent, {})[atom.get("key")] = atom.get("value")

    # ──────────────── 组装 PCBData ────────────────

    def _assemble(self, raw: dict, path: Path) -> PCBData:
        scale = _resolve_scale(raw["vias"])
        layers = raw["layers"] or dict(_FALLBACK_LAYERS)
        pcb = PCBData(format="lceda_epro2")

        # ---- 走线：按 (网络, 层) 聚合为折线 ----
        grouped: dict[tuple[str, object], list] = {}
        widths: dict[tuple[str, object], float] = {}
        for net, layer_id, width_raw, x1, y1, x2, y2 in raw["segments"]:
            key = (net, layer_id)
            grouped.setdefault(key, []).append(
                (x1 * scale, y1 * scale, x2 * scale, y2 * scale)
            )
            if width_raw:
                widths[key] = width_raw * scale

        for (net, layer_id), segs in grouped.items():
            pcb.traces.append(PCBTrace(
                net_name=net,
                layer=layers.get(layer_id, f"Layer{layer_id}"),
                width_mm=round(widths.get((net, layer_id), 0.0), 4),
                segments=segs,
            ))

        # ---- 过孔 ----
        for v in raw["vias"]:
            pcb.vias.append(PCBVia(
                position=(v["x"] * scale, v["y"] * scale),
                drill_mm=round(v["hole"] * scale, 4),
                pad_mm=round(v["pad"] * scale, 4),
                from_layer=layers.get(1, "Top Layer"),
                to_layer=layers.get(2, "Bottom Layer"),
                net_name=v["net"],
            ))

        # ---- 覆铜（POUR 环几何 + 带网络的 FILL/POLY 铜形）----
        # 铜层集合 = 走线所在层 ∪ 覆铜所在层 ∪ {1,2}（顶/底层）；
        # FILL/POLY 落在文档层/丝印层的不算铜
        copper_layer_ids = {lid for (_n, lid) in grouped}
        copper_layer_ids.update(p["layer_id"] for p in raw["pours"])
        copper_layer_ids.update((1, 2))

        copper_pours = []
        for p in raw["pours"]:
            outer, voids = _split_rings(p.get("path"))
            copper_pours.append({
                "net_name": p["net"],
                "layer": layers.get(p["layer_id"], f"Layer{p['layer_id']}"),
                "layer_id": p["layer_id"],
                "name": p["name"],
                "rings": 1 + len(voids) if outer else p["rings"],
                "source": "POUR",
                "outer": _mm_points(outer, scale),
                "voids": [_mm_points(v, scale) for v in voids],
            })
        for kind, rows in (("FILL", raw["net_fills"]), ("POLY", raw["net_polys"])):
            for r in rows:
                if r["layer_id"] not in copper_layer_ids:
                    continue
                outer, voids = _split_rings(r["path"])
                if not outer:
                    continue
                copper_pours.append({
                    "net_name": r["net"],
                    "layer": layers.get(r["layer_id"], f"Layer{r['layer_id']}"),
                    "layer_id": r["layer_id"],
                    "name": "",
                    "rings": 1 + len(voids),
                    "source": kind,
                    "outer": _mm_points(outer, scale),
                    "voids": [_mm_points(v, scale) for v in voids],
                })
        pcb.copper_pours = copper_pours

        # ---- 实际用到哪些层（.epru 会声明全部 90+ 层，绝大多数未使用）----
        used_layer_ids = {lid for (_n, lid) in grouped}
        used_layer_ids.update(v.get("layer_id") for v in raw["pours"])
        used_layer_ids.update(p.get("layer_id") for p in raw["pcb_pads"])
        used_layer_ids.update(c.get("layer_id") for c in raw["components"].values())
        pcb.layers = [
            layers[k] for k in sorted(layers)
            if k in used_layer_ids and layers.get(k)
        ]

        # ---- 元件坐标 ----
        for cid, pos in raw["components"].items():
            attrs = raw["comp_attrs"].get(cid, {})
            ref = attrs.get("Designator") or ""
            if not ref:
                continue
            layer_id = pos.get("layer_id")
            entry = {
                "x": round(pos["x"] * scale, 4),
                "y": round(pos["y"] * scale, 4),
                "rotation": pos.get("rotation"),
                "layer": layers.get(layer_id, f"Layer{layer_id}"),
                "side": {1: "T", 2: "B"}.get(layer_id, ""),
                "device": attrs.get("Device") or "",
                "footprint": attrs.get("Footprint") or "",
            }
            dev_attrs = raw["devices"].get(entry["device"]) or {}
            entry["value"] = dev_attrs.get("Value", "")
            entry["part_number"] = dev_attrs.get("Manufacturer Part", "")
            entry["footprint_name"] = raw["footprint_names"].get(entry["footprint"], "")
            entry["in_bom"] = _in_bom(pos.get("attrs"), dev_attrs)
            pcb.component_positions[ref] = entry

        # ---- 元件焊盘绝对坐标：封装相对坐标 + 元件位置/旋转 ----
        # 证据源：PAD_NET 给网络归属，FOOTPRINT PAD 给相对坐标。双层板铜皮
        # 主要靠元件焊盘接入（金样扩展板 0 个 GND 过孔却有 288 片 GND 补丁
        # 铜），孤岛判定等几何规则必须有焊盘几何才不误报。
        for cid, pad_num, net_name, pad_elem in raw["pad_nets"]:
            if not net_name:
                continue
            attrs = raw["comp_attrs"].get(cid) or {}
            comp = raw["components"].get(cid)
            fp_uuid = attrs.get("Footprint")
            fp_pad = (
                raw["footprint_pads"].get((fp_uuid, pad_elem))
                if pad_elem else None
            )
            if comp is None or not fp_pad:
                continue
            rad = math.radians(_num(comp.get("rotation")) or 0.0)
            cs, sn = math.cos(rad), math.sin(rad)
            rx, ry = fp_pad["x"], fp_pad["y"]
            pcb.pads.append({
                "ref": attrs.get("Designator") or cid,
                "num": fp_pad["num"] or pad_num,
                "net": net_name,
                "x": round((comp["x"] + rx * cs - ry * sn) * scale, 4),
                "y": round((comp["y"] + rx * sn + ry * cs) * scale, 4),
                "layer_id": fp_pad["layer_id"],
                "thru": fp_pad["thru"],
            })

        # ---- 网络：NET 定义 ∪ 走线/过孔/焊盘引用到的网络（空网络名丢弃）----
        ordered_nets: list[str] = []
        seen: set[str] = set()
        candidates = list(raw["nets_defined"])
        candidates += [key[0] for key in grouped]
        candidates += [v["net"] for v in raw["vias"]]
        candidates += [pn[2] for pn in raw["pad_nets"]]
        candidates += [p["net"] for p in raw["pcb_pads"]]
        for nm in candidates:
            if nm and nm not in seen:
                seen.add(nm)
                ordered_nets.append(nm)

        for nm in ordered_nets:
            pcb.nets[nm] = PCBNet(name=nm)

        # 走线统计 + 长度
        for trace in pcb.traces:
            net = pcb.nets.get(trace.net_name)
            if net is None:
                continue
            net.trace_count += 1
            net.total_length_mm += sum(
                ((s[2] - s[0]) ** 2 + (s[3] - s[1]) ** 2) ** 0.5
                for s in trace.segments
            )
        for net in pcb.nets.values():
            net.total_length_mm = round(net.total_length_mm, 3)

        # 引脚：PAD_NET → "位号.焊盘号"
        #
        # PAD_NET 的 id 是 ["PAD_NET", 元件id, 焊盘号, 焊盘元素id]。BGA/字母焊盘
        # 的「焊盘号」段会退化成元素 id（如 "e220"），必须用封装文档里的
        # (封装 uuid, 元素 id) → 真实焊盘号（A1/N9…）还原。
        orphan = 0
        for cid, pad_num, net_name, pad_elem in raw["pad_nets"]:
            if not net_name:
                continue
            attrs = raw["comp_attrs"].get(cid) or {}
            ref = attrs.get("Designator") or cid
            fp_uuid = attrs.get("Footprint")
            fp_known = bool(fp_uuid) and fp_uuid in raw["footprint_names"]
            fp_pad = (
                raw["footprint_pads"].get((fp_uuid, pad_elem))
                if pad_elem else None
            )
            if fp_pad is not None:
                resolved = fp_pad["num"]
                if resolved == "":
                    # 焊盘本身没有编号（散热盘等）→ 官方网表同样不列出
                    continue
                pad_num = resolved
            elif fp_known and pad_elem:
                # 封装文档里找不到这个焊盘元素 → 日志里的陈旧记录（立创官方
                # 导出同样丢弃它）。但焊盘在板上真实存在：金样实测 JP1/JP2
                # 的两脚网络因此只剩 1 针、被当单端浮空网，天线规则误报
                # （memories/audit-findings.md orphan 丢针条）。保留记录里的
                # 焊盘号；字母焊盘号退化成元素 id 时用元素 id 兜底——引脚
                # 计数的真实性优先于编号美观。
                orphan += 1
                raw["orphan_nets"].add(net_name)
                if not pad_num:
                    pad_num = pad_elem
            # 封装文档不存在时保守保留原焊盘号
            net = pcb.nets.get(net_name)
            if net is None:
                net = pcb.nets[net_name] = PCBNet(name=net_name)
            net.pins.append(f"{ref}.{pad_num}")

        # 直接落在 PCB 上的焊盘（测试点/金手指等）
        for pad in raw["pcb_pads"]:
            if not pad["net"]:
                continue
            net = pcb.nets.get(pad["net"])
            if net is None:
                net = pcb.nets[pad["net"]] = PCBNet(name=pad["net"])
            label = f"PAD{pad['num']}" if pad["num"] else "PAD"
            net.pins.append(label)

        for net in pcb.nets.values():
            if net.pins:
                net.pins = sorted(set(net.pins))

        # ---- 差分对 ----
        for nm, rule in raw["net_rules"].items():
            if rule.get("differential") or rule.get("equal_length"):
                pcb.differential_pairs.append({
                    "net": nm,
                    "differential": rule.get("differential"),
                    "equal_length_group": rule.get("equal_length"),
                })

        # ---- 板框包围盒 ----
        # ---- 板框包围盒 ----
        # 优先用 BOARD_OUTLINE 的几何；但立创的 R 矩形模式在不同工程里落点
        # 不一致（实测泰山派 3M 的 Y 方向偏了一个板高），所以做一次包含性
        # 校验：板框必须能装下全部铜（走线/过孔/覆铜），否则退回铜的包围盒。
        outline_pts = []
        rect_like = False
        for path_pts in raw["polygons"]:
            if path_pts and isinstance(path_pts[0], str):
                rect_like = True
            outline_pts.extend(_polygon_points(path_pts))
        copper_pts = [(s[3], s[4]) for s in raw["segments"]]
        copper_pts += [(s[5], s[6]) for s in raw["segments"]]
        copper_pts += [(v["x"], v["y"]) for v in raw["vias"]]

        def _bbox(points):
            xs = [p[0] * scale for p in points]
            ys = [p[1] * scale for p in points]
            return (min(xs), min(ys), max(xs), max(ys))

        source = "none"
        bbox = None
        if outline_pts:
            ob = _bbox(outline_pts)
            if ob[2] - ob[0] > 1e-6 and ob[3] - ob[1] > 1e-6:
                bbox, source = ob, "outline"
        if copper_pts and bbox is not None:
            cb = _bbox(copper_pts)
            tol = 0.5
            contains = (
                bbox[0] - tol <= cb[0] and bbox[1] - tol <= cb[1]
                and bbox[2] + tol >= cb[2] and bbox[3] + tol >= cb[3]
            )
            if not contains:
                bbox, source = cb, "copper"
        if bbox is None and copper_pts:
            bbox, source = _bbox(copper_pts), "copper"
        if bbox is not None:
            min_x, min_y, max_x, max_y = bbox
            pcb.board_outline = {
                "width_mm": round(max_x - min_x, 3),
                "height_mm": round(max_y - min_y, 3),
                "min_x_mm": round(min_x, 3),
                "min_y_mm": round(min_y, 3),
                "max_x_mm": round(max_x, 3),
                "max_y_mm": round(max_y, 3),
                "shape": (
                    ("rectangle" if rect_like else "polygon")
                    if source == "outline" else "bbox"
                ),
                "source": source,
            }

        # ---- BOM（DEVICE 库属性 + 位号聚合）----
        pcb.bom_items = _build_bom_items(raw)

        pcb.metadata = {
            "title": (raw["project2"] or {}).get("title") or path.stem,
            "editor_version": (raw["project2"] or {}).get("editorVersion"),
            "epru": raw["epru"],
            "unit": "mil",
            # CANVAS.unit 只是界面显示偏好，与存储单位无关（见模块 docstring）
            "canvas_unit": (raw["canvas"] or {}).get("unit"),
            "scale_to_mm": scale,
            "documents": raw["doc_counts"],
            "line_elements": raw["line_elements"],
            "trace_polylines": len(pcb.traces),
            "net_elements": len(raw["nets_defined"]),
            "pads_in_footprints": len(raw["footprint_pads"]),
            "footprint_docs": len(raw["footprint_names"]),
            "pad_nets": len(raw["pad_nets"]),
            "orphan_pad_nets": orphan,
            "orphan_nets": sorted(raw["orphan_nets"]),
            "net_fills": len(raw["net_fills"]),
            "net_polys": len(raw["net_polys"]),
            "elements": raw["type_counts"],
        }

        logger.info(
            "PCB 解析完成 (lceda_epro2): %s — %d 网络, %d 走线, %d 过孔, %d 层, BOM %d 行",
            path.name, pcb.net_count, pcb.trace_count, pcb.via_count,
            len(pcb.layers), len(pcb.bom_items),
        )
        return pcb


# ──────────────── 模块级工具 ────────────────

def _iter_atoms(fh) -> Iterator[tuple[dict, dict]]:
    """流式迭代 ``.epru`` 的 (meta, atom) 对。

    为了性能，meta.type 先用正则取；只有正则失配时才回退到 json.loads。
    """
    for raw_line in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"):
        s = raw_line.strip()
        if not s:
            continue
        sep = s.find("||")
        if sep < 0:
            continue
        meta_s = s[:sep]
        atom_s = s[sep + 2:].rstrip("|")

        m = _META_TYPE_RE.match(meta_s)
        if m:
            try:
                atom = json.loads(atom_s)
            except json.JSONDecodeError:
                logger.debug("跳过无效原子: %s", atom_s[:80])
                continue
            yield {"type": m.group(1), "id": _meta_id(meta_s)}, atom
            continue

        try:
            meta = json.loads(meta_s)
            atom = json.loads(atom_s)
        except json.JSONDecodeError:
            logger.debug("跳过无效行: %s", s[:80])
            continue
        yield meta, atom


_META_ID_RE = re.compile(r'"id":"((?:[^"\\]|\\.)*)"')


def _meta_id(meta_s: str):
    """从 meta 字符串里取 id（可能是普通字符串，也可能是 JSON 数组字符串）"""
    m = _META_ID_RE.search(meta_s)
    if not m:
        return None
    raw = m.group(1)
    try:
        return json.loads('"' + raw + '"')
    except json.JSONDecodeError:
        return raw


def _layer_id(meta: dict) -> Optional[int]:
    """LAYER 的 id 形如 '["LAYER",1]' 的字符串"""
    raw = meta.get("id")
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list) and len(parsed) >= 2:
        try:
            return int(parsed[1])
        except (TypeError, ValueError):
            return None
    return None


def _net_name(meta_id) -> Optional[str]:
    """NET 的 id 形如 '["NET","VCC_3V3"]' 的字符串"""
    if not isinstance(meta_id, str):
        return None
    try:
        parsed = json.loads(meta_id)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list) and len(parsed) >= 2:
        return str(parsed[1])
    return None


def _parse_pad_net_id(meta_id):
    """PAD_NET 的 id 形如 '["PAD_NET","e1","1","e14"]'"""
    if not isinstance(meta_id, str):
        return None
    try:
        parsed = json.loads(meta_id)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list) and len(parsed) >= 3:
        pad_elem = parsed[3] if len(parsed) > 3 else ""
        return str(parsed[1]), str(parsed[2]), str(pad_elem)
    return None


def _ring_count(path) -> int:
    """覆铜/区域路径的环数（简单多边形 1 环；复杂多边形外框+若干内洞）"""
    if not path:
        return 0
    if isinstance(path[0], list):
        return len(path)
    return 1


def _copper_ring_points(sub: list) -> list[tuple[float, float]]:
    """覆铜子路径 → 环顶点（存储单位，mm 缩放由调用方处理）。

    FILL/POLY 的子路径是 R/CIRCLE 独立模式或点列模式。CIRCLE 取 24 边形
    近似——孤岛判定只需「点在多边形内」，板级尺度下弦差远小于 0.1mm；
    不能直接用 _polygon_points，它对 CIRCLE 只回包围盒对角点。
    """
    if not sub:
        return []
    head = sub[0]
    if isinstance(head, str):
        cmd = head.upper()
        nums = [v for v in sub[1:] if isinstance(v, (int, float))]
        if cmd == "CIRCLE" and len(nums) >= 3:
            cx, cy, r = float(nums[0]), float(nums[1]), float(nums[2])
            return [
                (cx + r * math.cos(2 * math.pi * k / 24),
                 cy + r * math.sin(2 * math.pi * k / 24))
                for k in range(24)
            ]
    return _polygon_points(sub)


def _split_rings(path) -> tuple[list, list]:
    """覆铜 path → (外环顶点, 内洞顶点列表)。

    环列表形式（首环外框、其余内洞）与扁平点列（整体当外环）都支持。
    """
    if not path:
        return [], []
    rings = path if isinstance(path[0], list) else [path]
    outer = _copper_ring_points(rings[0])
    voids = [v for v in (_copper_ring_points(r) for r in rings[1:]) if v]
    return outer, voids


def _mm_points(pts, scale) -> list[tuple[float, float]]:
    """环顶点按工程缩放系数转 mm"""
    return [(round(x * scale, 4), round(y * scale, 4)) for x, y in pts]


def _last_pcb_doc_uuid(zf: zipfile.ZipFile, epru: str) -> Optional[str]:
    """预扫工程日志，返回最后一个 PCB 文档的 uuid（=最新板快照）。

    只解析 DOCHEAD 行（子串快筛 + JSON），整条日志过一遍的开销远小于
    把历史快照全并进结果的代价。单 PCB 文档的工程返回其 uuid，语义不变。
    """
    last = None
    with zf.open(epru) as fh:
        for raw_line in fh:
            line = raw_line.decode("utf-8", "replace").strip()
            if '"DOCHEAD"' not in line[:80] or "||" not in line:
                continue
            meta_s, atom_s = line.split("||", 1)
            try:
                atom = json.loads(atom_s.rstrip("|"))
            except json.JSONDecodeError:
                continue
            if atom.get("docType") == "PCB":
                last = atom.get("uuid") or last
    return last


def _rect_corners(x: float, y: float, w: float, h: float, rot: float) -> list[tuple[float, float]]:
    """``R`` 矩形模式：``R X Y width height rot round``，绕 (X,Y) 旋转。

    规范明确 X/Y 是**左上角**、高度向 Y 减小方向延伸（矩形跨
    y ∈ [Y−h, Y]）。按左下角向上延伸会把整块矩形抬一个高度——万兆板
    整版 GND 覆铜落到板外 170~340mm、台账里「泰山派 R 板框 Y 偏一个
    板高」都是这一处病根。
    """
    rad = math.radians(rot or 0.0)
    c, s = math.cos(rad), math.sin(rad)
    return [
        (x + dx * c - dy * s, y + dx * s + dy * c)
        for dx, dy in ((0, 0), (w, 0), (w, -h), (0, -h))
    ]


def _polygon_points(path_pts: list) -> list[tuple[float, float]]:
    """从立创路径数组里抽出坐标点（按 V3 规范）。

    规范（``.specs/v3/lceda-pro-file-format-v3_2025.10.21.md``）：

    - 点列模式：``X0 Y0 L X Y X Y ...``，可混 ``ARC angle endX endY`` 与
      ``C x2 y2 x3 y3 x4 y4``（三阶贝塞尔，取末点为终点）
    - ``R X Y width height rot round``   矩形（独立模式）
    - ``CIRCLE cx cy r isCCW``           圆（独立模式）
    """
    pts: list[tuple[float, float]] = []
    if not path_pts:
        return pts

    head = path_pts[0]
    if isinstance(head, str):
        cmd = head.upper()
        nums = [v for v in path_pts[1:] if isinstance(v, (int, float))]
        if cmd == "R" and len(nums) >= 4:
            pts.extend(_rect_corners(
                float(nums[0]), float(nums[1]), float(nums[2]), float(nums[3]),
                float(nums[4]) if len(nums) > 4 else 0.0,
            ))
        elif cmd == "CIRCLE" and len(nums) >= 3:
            cx, cy, r = float(nums[0]), float(nums[1]), float(nums[2])
            pts.extend([(cx - r, cy - r), (cx + r, cy + r)])
        return pts

    n = len(path_pts)
    i = 0
    # 起始点
    if n >= 2 and isinstance(path_pts[0], (int, float)) and isinstance(path_pts[1], (int, float)):
        pts.append((float(path_pts[0]), float(path_pts[1])))
        i = 2

    while i < n:
        v = path_pts[i]
        if isinstance(v, str):
            cmd = v.upper()
            if cmd in ("ARC", "CARC"):
                seg = [q for q in path_pts[i + 1:i + 4] if isinstance(q, (int, float))]
                if len(seg) == 3:  # angle, endX, endY
                    pts.append((float(seg[1]), float(seg[2])))
                i += 4
            elif cmd == "C":
                seg = [q for q in path_pts[i + 1:i + 7] if isinstance(q, (int, float))]
                if len(seg) == 6:  # 控制点，末点为终点
                    pts.append((float(seg[4]), float(seg[5])))
                i += 7
            else:  # L 及其它：后续坐标对由下面分支消费
                i += 1
            continue
        if i + 1 < n and isinstance(path_pts[i + 1], (int, float)):
            pts.append((float(v), float(path_pts[i + 1])))
            i += 2
        else:
            i += 1
    return pts


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _resolve_scale(vias: list[dict]) -> float:
    """判定坐标单位并返回 → mm 的换算系数。

    数值单位是 mil（见模块 docstring）。这里保留一个 sanity check：若过孔
    钻孔中位数 < 2，说明工程本身就以 mm 存储，不再换算。
    """
    holes = [v["hole"] for v in vias if v.get("hole")]
    if holes:
        med = statistics.median(holes)
        if med < 2.0:
            logger.debug("过孔钻孔中位数 %.3f → 判定为 mm 存储", med)
            return 1.0
    return MIL_TO_MM


def _in_bom(instance_attrs: dict, device_attrs: dict) -> bool:
    """该元件是否进 BOM。

    **实例属性优先于库属性**：立创把用户逐件取消的「加入 BOM」写在 PCB 元件实例的
    ``attrs`` 里（``Add into BOM = "no"``），而 DEVICE 库属性始终是 ``yes``。
    实测泰山派 3M：只看库属性会多算 62 个位号；按实例优先过滤后与官方 BOM
    的 885 个位号完全一致。
    """
    for attrs in (instance_attrs or {}, device_attrs or {}):
        flag = attrs.get("Add into BOM")
        if flag is not None and str(flag).strip():
            return str(flag).strip().lower() not in ("no", "false", "0")
    return True


def _build_bom_items(raw: dict) -> list[dict]:
    """按器件（DEVICE uuid + 封装）聚合位号，生成 BOM 行。

    立创的 BOM 以「同一器件」为一行，位号合并；这里保持同样口径，方便与
    官方导出的 BOM xlsx 逐行比对。
    """
    groups: dict[tuple, dict] = {}
    for cid, pos in raw["components"].items():
        attrs = raw["comp_attrs"].get(cid) or {}
        ref = attrs.get("Designator") or ""
        if not ref:
            continue
        dev_uuid = attrs.get("Device") or ""
        dev = raw["devices"].get(dev_uuid) or {}
        if not _in_bom(pos.get("attrs"), dev):
            continue

        key = dev_uuid or f"__{attrs.get('Footprint','')}__{ref}"
        fp_uuid = attrs.get("Footprint") or ""
        row = groups.setdefault((key, fp_uuid), {
            "reference": [],
            "value": dev.get("Value", ""),
            "package": raw["footprint_names"].get(fp_uuid, "")
                       or dev.get("Supplier Footprint", ""),
            "part_number": dev.get("Manufacturer Part", ""),
            "supplier_part": dev.get("Supplier Part", ""),
            "manufacturer": dev.get("Manufacturer", ""),
            "description": dev.get("LCSC Part Name", "") or dev.get("Description", ""),
            "device": raw.get("device_titles", {}).get(dev_uuid, ""),
            "quantity": 0,
        })
        row["reference"].append(ref)
        row["quantity"] += 1

    items = list(groups.values())
    for row in items:
        row["reference"] = ",".join(row["reference"])
    items.sort(key=lambda r: r["reference"])
    return items


def bom_rows_to_items(rows: list[dict]) -> list:
    """把 :attr:`PCBData.bom_items` 的 dict 行转成 :class:`BOMItem` 列表。

    延迟导入 BOMItem，避免 ``src.pcb`` 的导入链拖上 pandas。
    """
    from ..bom.parser import BOMItem

    return [
        BOMItem(
            reference=row["reference"],
            value=row["value"],
            package=row["package"],
            part_number=row["part_number"],
            description=row["description"],
            quantity=row["quantity"],
            manufacturer=row["manufacturer"],
        )
        for row in rows
    ]


def load_epro2_bom_items(file_path: str) -> list:
    """解析 ``.epro2`` 并只取 BOM（:class:`BOMItem` 列表）"""
    return bom_rows_to_items(Epro2Parser().parse(file_path).bom_items)


def load_epro2_project(file_path: str) -> PCBData:
    """便捷函数：解析 ``.epro2`` 并返回含 BOM 的 :class:`PCBData`"""
    return Epro2Parser().parse(file_path)
