"""PCB 文件解析器 — 轻量策略模式

支持:
- 立创 EDA 标准版 .json 导出文件
- 立创 EDA 专业版 .epro 项目文件 (ZIP包)
"""

import json
import logging
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .models import PCBData, PCBNet, PCBTrace, PCBVia
from ..constants import PCB
from ..exceptions import PCBParseError

logger = logging.getLogger(__name__)


# ──────────────── 共享常量 ────────────────

_LAYER_MAP: dict[str, str] = {
    "1": "TopLayer",
    "2": "BottomLayer",
    "3": "TopSilkLayer",
    "4": "BottomSilkLayer",
    "5": "TopPasteMaskLayer",
    "6": "BottomPasteMaskLayer",
    "7": "TopSolderMaskLayer",
    "8": "BottomSolderMaskLayer",
    "10": "Inner1",
    "11": "Inner2",
    "12": "Inner3",
    "13": "Inner4",
}


# ──────────────── 解析策略 ────────────────

class PCBParseStrategy(ABC):
    """PCB 解析策略抽象基类"""

    @abstractmethod
    def parse(self, file_path: str) -> PCBData:
        """解析 PCB 文件，返回 PCBData"""
        ...


class LCEDAJsonParser(PCBParseStrategy):
    """立创 EDA 标准版 .json PCB 文件解析器

    JSON 结构:
    {
      "head": {...},
      "canvas": [
        "TRACK~layerId~netId~netName~width~x1 y1~x2 y2 ...",
        "PAD~layerId~netId~netName~number~centerX centerY w h~...",
        "VIA~layerId~netId~netName~x y~drill~pad~...",
        ...
      ]
    }

    图元属性用 ~ 分隔；坐标对用空格分隔。
    轻量提取：只解析 TRACK/PAD/VIA 的关键字段，忽略全量几何。
    """

    def parse(self, file_path: str) -> PCBData:
        path = Path(file_path)
        if not path.exists():
            raise PCBParseError(f"文件不存在: {file_path}")
        if path.suffix.lower() != ".json":
            raise PCBParseError(f"不支持的文件格式: {path.suffix}，标准版需要 .json")

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            raise PCBParseError(f"JSON 解析失败: {e}")

        canvas = raw.get("canvas", [])
        if not isinstance(canvas, list):
            raise PCBParseError("PCB 文件缺少 canvas 数组")

        pcb_data = PCBData(format="lceda_json")
        nets: dict[str, set[str]] = {}  # net_name → {pin_refs}
        layers: set[str] = set()

        for shape_str in canvas:
            if not isinstance(shape_str, str):
                continue
            parts = shape_str.split("~")
            if not parts:
                continue

            shape_type = parts[0]

            if shape_type == "TRACK":
                result = self._parse_track(parts, layers)
                if result:
                    pcb_data.traces.append(result)
            elif shape_type == "PAD":
                self._parse_pad(parts, nets, layers)
            elif shape_type == "VIA":
                result = self._parse_via(parts, layers)
                if result:
                    pcb_data.vias.append(result)

        # 合并 nets 字典
        for net_name, pin_set in nets.items():
            pcb_data.nets[net_name] = PCBNet(
                name=net_name,
                pins=sorted(pin_set),
            )

        # 统计每个 net 的 trace 信息
        for trace in pcb_data.traces:
            net = pcb_data.nets.get(trace.net_name)
            if net:
                net.trace_count += 1

        pcb_data.layers = sorted(layers)
        logger.info(
            f"PCB 解析完成 (lceda_json): "
            f"{pcb_data.net_count} 网络, {pcb_data.trace_count} 走线, "
            f"{pcb_data.via_count} 过孔, {len(pcb_data.layers)} 层"
        )
        return pcb_data

    # ──── 图元解析助手 ────

    def _resolve_layer(self, layer_id: str) -> str:
        """层 ID → 层名"""
        return _LAYER_MAP.get(layer_id, f"Layer{layer_id}")

    def _parse_track(
        self, parts: list[str], layers: set[str]
    ) -> Optional[PCBTrace]:
        """TRACK~layerId~netId~netName~width~x1 y1~x2 y2 ..."""
        if len(parts) < 5:
            return None

        layer = self._resolve_layer(parts[1])
        layers.add(layer)
        net_name = parts[3] if len(parts) > 3 else ""

        try:
            width_mm = float(parts[4]) if len(parts) > 4 else 0.0
        except ValueError:
            width_mm = 0.0

        segments = []
        for seg_str in parts[5:]:
            coords = seg_str.strip().split()
            if len(coords) >= 4:
                try:
                    segments.append(tuple(float(c) for c in coords[:4]))
                except ValueError:
                    pass

        return PCBTrace(
            net_name=net_name,
            layer=layer,
            width_mm=width_mm,
            segments=segments,
        )

    def _parse_pad(
        self,
        parts: list[str],
        nets: dict[str, set[str]],
        layers: set[str],
    ) -> None:
        """PAD~layerId~netId~netName~number~cx cy w h~..."""
        if len(parts) < 5:
            return

        layer = self._resolve_layer(parts[1])
        layers.add(layer)
        net_name = parts[3] if len(parts) > 3 else ""
        pad_num = parts[4] if len(parts) > 4 else "?"

        if net_name:
            if net_name not in nets:
                nets[net_name] = set()
            nets[net_name].add(pad_num)

    def _parse_via(
        self, parts: list[str], layers: set[str]
    ) -> Optional[PCBVia]:
        """VIA~layerId~netId~netName~x y~drill~pad~..."""
        if len(parts) < 7:
            return None

        layer = self._resolve_layer(parts[1])
        layers.add(layer)
        net_name = parts[3] if len(parts) > 3 else ""

        pos_xy = parts[4].strip().split() if len(parts) > 4 else []
        if len(pos_xy) < 2:
            return None

        try:
            x, y = float(pos_xy[0]), float(pos_xy[1])
            drill = float(parts[5]) if len(parts) > 5 else 0.0
            pad = float(parts[6]) if len(parts) > 6 else 0.0
        except ValueError:
            return None

        return PCBVia(
            position=(x, y),
            drill_mm=drill,
            pad_mm=pad,
            from_layer=layer,
            to_layer=layer,  # VIA 跨层信息在简版中为单层
            net_name=net_name,
        )


class LCEDAProParser(PCBParseStrategy):
    """立创 EDA 专业版 .epro 项目文件解析器

    .epro 本质是 ZIP 包，内含:
    - project.json: 项目元信息
    - schematic.esch: 原理图 (JSON Lines)
    - pcb.epcb (或类似): PCB 图元 (JSON Lines)

    每行一个 JSON 对象，包含完整的图元属性（非 ~ 分隔）。
    """

    def parse(self, file_path: str) -> PCBData:
        path = Path(file_path)
        if not path.exists():
            raise PCBParseError(f"文件不存在: {file_path}")
        if path.suffix.lower() != ".epro":
            raise PCBParseError(f"不支持的文件格式: {path.suffix}，专业版需要 .epro")

        # 尝试作为 ZIP 打开
        try:
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                # 定位 .epcb 文件
                pcb_entry = None
                for name in names:
                    if name.endswith(".epcb"):
                        pcb_entry = name
                        break

                if not pcb_entry:
                    raise PCBParseError(
                        "epro 包中未找到 .epcb PCB 文件，"
                        f"包内容: {names}"
                    )

                raw_bytes = zf.read(pcb_entry)
                try:
                    lines = raw_bytes.decode("utf-8").splitlines()
                except UnicodeDecodeError:
                    lines = raw_bytes.decode("gbk").splitlines()
                    logger.debug("epro 文件使用 GBK 编码解码")
        except zipfile.BadZipFile as e:
            raise PCBParseError(f"epro 文件无法作为 ZIP 打开: {e}")

        pcb_data = PCBData(format="lceda_epro")
        nets: dict[str, set[str]] = {}  # net_name → {pin_refs}
        layers: set[str] = set()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                logger.debug(f"跳过无效 JSON 行: {line[:80]}...")
                continue

            self._process_element(obj, pcb_data, nets, layers)

        # 合并 nets
        for net_name, pin_set in nets.items():
            pcb_data.nets[net_name] = PCBNet(
                name=net_name,
                pins=sorted(pin_set),
            )

        for trace in pcb_data.traces:
            net = pcb_data.nets.get(trace.net_name)
            if net:
                net.trace_count += 1

        pcb_data.layers = sorted(layers)
        logger.info(
            f"PCB 解析完成 (lceda_epro): "
            f"{pcb_data.net_count} 网络, {pcb_data.trace_count} 走线, "
            f"{pcb_data.via_count} 过孔, {len(pcb_data.layers)} 层"
        )
        return pcb_data

    def _process_element(
        self,
        obj: dict,
        pcb_data: PCBData,
        nets: dict[str, set[str]],
        layers: set[str],
    ) -> None:
        """处理单个 PCB 图元 JSON 对象"""
        el_type = obj.get("type", obj.get("shape", ""))

        # 专业版图元类型映射
        if el_type in ("TRACK", "track"):
            self._handle_track(obj, pcb_data, layers)
        elif el_type in ("PAD", "pad"):
            self._handle_pad(obj, nets, layers)
        elif el_type in ("VIA", "via"):
            self._handle_via(obj, pcb_data, layers)

    def _resolve_layer(self, layer_id) -> str:
        lid = str(layer_id) if layer_id is not None else "0"
        return _LAYER_MAP.get(lid, f"Layer{lid}")

    def _handle_track(self, obj: dict, pcb_data: PCBData, layers: set[str]) -> None:
        net_name = obj.get("net", obj.get("netName", ""))
        layer = self._resolve_layer(obj.get("layer", obj.get("layerId", 0)))
        layers.add(layer)

        width = 0.0
        if "width" in obj:
            try:
                width = float(obj["width"])
            except (ValueError, TypeError):
                pass

        segments = []
        pts = obj.get("points", obj.get("path", []))
        if isinstance(pts, list) and len(pts) >= 2:
            for i in range(len(pts) - 1):
                p1, p2 = pts[i], pts[i + 1]
                if isinstance(p1, (list, tuple)) and len(p1) >= 2:
                    if isinstance(p2, (list, tuple)) and len(p2) >= 2:
                        segments.append((p1[0], p1[1], p2[0], p2[1]))

        pcb_data.traces.append(PCBTrace(
            net_name=net_name,
            layer=layer,
            width_mm=width,
            segments=segments,
        ))

    def _handle_pad(
        self, obj: dict, nets: dict[str, set[str]], layers: set[str]
    ) -> None:
        net_name = obj.get("net", obj.get("netName", ""))
        layer = self._resolve_layer(obj.get("layer", obj.get("layerId", 0)))
        layers.add(layer)
        pad_num = obj.get("number", obj.get("padNumber", "?"))

        if net_name:
            if net_name not in nets:
                nets[net_name] = set()
            nets[net_name].add(str(pad_num))

    def _handle_via(self, obj: dict, pcb_data: PCBData, layers: set[str]) -> None:
        layer = self._resolve_layer(obj.get("layer", obj.get("layerId", 0)))
        layers.add(layer)
        net_name = obj.get("net", obj.get("netName", ""))

        try:
            x = float(obj.get("x", obj.get("cx", 0)))
            y = float(obj.get("y", obj.get("cy", 0)))
            drill = float(obj.get("drill", obj.get("drillSize", 0)))
            pad = float(obj.get("pad", obj.get("padSize", 0)))
        except (ValueError, TypeError):
            return

        pcb_data.vias.append(PCBVia(
            position=(x, y),
            drill_mm=drill,
            pad_mm=pad,
            from_layer=layer,
            to_layer=layer,
            net_name=net_name,
        ))


# ──────────────── 工厂函数 ────────────────

def create_parser(file_path: str) -> PCBParseStrategy:
    """根据文件扩展名创建对应的解析器"""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".json":
        return LCEDAJsonParser()
    if suffix == ".epro":
        return LCEDAProParser()
    supported = PCB.SUPPORTED_PCB_FORMATS
    raise PCBParseError(
        f"不支持的 PCB 文件格式 '{suffix}'，支持的格式: {supported}"
    )
