"""PCB 走线几何 — 无序线段串联成折线 + 折线转角（内角）计算。

背景（见 memories/epro2-format.md）：.epru / .epro2 里同一 (网络, 层) 的 LINE
线段**不保证按路径顺序记录**，实测相邻线段端点相接的比例只有 7%~48%，另外同一
线段还可能重复出现（实测 1331 段里有 77 段重复）。所以任何“取相邻两段的夹角”的
规则，都必须先做**端点串联**：

1. tol 内的端点归一到同一个节点（空间哈希 + 并查集）；
2. 长度 <= tol 的退化线段、重复线段丢弃；
3. 按图论度数把边集切成若干条折线 —— 只在度数为 2 的节点上转弯才可能是走线
   拐角，T/X 形节点（焊盘、过孔、分支）角度无意义，不参与判定。

坐标单位与输入一致（解析器统一输出 mm）。
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, replace

#: 端点视为同一点的容差 (mm)。立创坐标精度 1e-4 mm 量级，0.01mm 足以吸收
#: 浮点/取整误差，又远小于任何真实走线拐点间距。
DEFAULT_TOL_MM = 0.01


@dataclass(frozen=True)
class Corner:
    """折线上的一个拐角。

    angle_deg 是**内角**：180° = 直线（不是拐角），90° = 直角，
    <90° = 锐角（45° 布线产生的拐角是 135°）。
    is_closed=True 表示拐角来自**闭合折线**（铺铜外框、焊盘 void 轮廓、
    网格铺铜的单元环）——这些是覆铜几何，不是走线路径，规则应豁免。
    """

    angle_deg: float
    vertex: tuple[float, float]
    leg_in_mm: float
    leg_out_mm: float
    is_closed: bool = False


def _cluster_endpoints(points: list[tuple[float, float]], tol: float) -> list[int]:
    """把 tol 内的端点归簇，返回每个点的簇代表下标（并查集根）。"""
    parent = list(range(len(points)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)   # 始终以最小下标为根，代表点稳定

    cell: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, p in enumerate(points):
        cx, cy = math.floor(p[0] / tol), math.floor(p[1] / tol)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cell.get((cx + dx, cy + dy), ()):
                    q = points[j]
                    if math.hypot(p[0] - q[0], p[1] - q[1]) <= tol:
                        union(i, j)
        cell[(cx, cy)].append(i)
    return [find(i) for i in range(len(points))]


def chain_segments(
    segments, tol: float = DEFAULT_TOL_MM
) -> list[list[tuple[float, float]]]:
    """把一组无序线段串成有序折线。

    Args:
        segments: 可迭代的 (x1, y1, x2, y2)；允许带多余元素（忽略尾部）。
        tol: 端点合并容差 (mm)。

    Returns:
        折线点列列表。每条折线的相邻点不重合，内部节点度数恒为 2；
        分叉点/端点会把折线切断。没有任何有效线段时返回 []。
    """
    raw: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for s in segments or ():
        try:
            a = (float(s[0]), float(s[1]))
            b = (float(s[2]), float(s[3]))
        except (TypeError, ValueError, IndexError):
            continue
        if math.hypot(b[0] - a[0], b[1] - a[1]) > tol:
            raw.append((a, b))
    if not raw:
        return []

    pts = [p for seg in raw for p in seg]
    root = _cluster_endpoints(pts, tol)
    # 簇代表坐标 = 簇内最小下标那个点
    pos: dict[int, tuple[float, float]] = {}
    for i, p in enumerate(pts):
        pos.setdefault(root[i], p)

    # 归一后的边：去自环（退化）、去重（同一对节点只留一条）
    edges: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for k in range(0, len(pts), 2):
        u, v = root[k], root[k + 1]
        if u == v:
            continue
        key = (u, v) if u < v else (v, u)
        if key in seen:
            continue
        seen.add(key)
        edges.append((u, v))
    if not edges:
        return []

    adj: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for eid, (u, v) in enumerate(edges):
        adj[u].append((eid, v))
        adj[v].append((eid, u))

    used = [False] * len(edges)
    polylines: list[list[tuple[float, float]]] = []

    def walk(start: int, eid: int, nxt: int) -> list[tuple[float, float]]:
        line = [pos[start]]
        cur_edge, node = eid, nxt
        while True:
            used[cur_edge] = True
            line.append(pos[node])
            if len(adj[node]) != 2:          # 分叉/端点 —— 折线到此为止
                break
            for e2, w in adj[node]:
                if not used[e2]:
                    cur_edge, node = e2, w
                    break
            else:
                break                        # 环闭上
        return line

    for node in list(adj):
        if len(adj[node]) == 2:
            continue
        for eid, nxt in adj[node]:
            if not used[eid]:
                polylines.append(walk(node, eid, nxt))
    for eid, (u, v) in enumerate(edges):     # 纯环（整条网络闭合）
        if not used[eid]:
            polylines.append(walk(u, eid, v))
    return polylines


def _corner_at(
    prev_pt: tuple[float, float],
    vertex: tuple[float, float],
    next_pt: tuple[float, float],
    min_leg_mm: float,
) -> Corner | None:
    """在 vertex 处取内角；退化（零长腿 / 腿太短）返回 None。"""
    v1x, v1y = prev_pt[0] - vertex[0], prev_pt[1] - vertex[1]
    v2x, v2y = next_pt[0] - vertex[0], next_pt[1] - vertex[1]
    n1 = math.hypot(v1x, v1y)
    n2 = math.hypot(v2x, v2y)
    if n1 <= 0 or n2 <= 0:
        return None
    if min_leg_mm > 0 and min(n1, n2) < min_leg_mm:
        return None
    cos_a = (v1x * v2x + v1y * v2y) / (n1 * n2)
    angle = math.degrees(math.acos(max(-1.0, min(1.0, cos_a))))
    return Corner(angle, vertex, n1, n2)


def polyline_corners(
    points: list[tuple[float, float]], min_leg_mm: float = 0.0
) -> list[Corner]:
    """折线上所有内角拐角。直线中间点（180°）也会返回，由调用方按阈值筛。

    Args:
        points: 有序点列；首尾重合视为闭合环，环的起点也计入拐角。
        min_leg_mm: 两侧腿任一短于该值的拐角视为退化（焊盘入口短桩等）跳过。
    """
    if len(points) < 3:
        return []
    corners: list[Corner] = []
    for i in range(1, len(points) - 1):
        c = _corner_at(points[i - 1], points[i], points[i + 1], min_leg_mm)
        if c is not None:
            corners.append(c)
    if len(points) >= 4 and points[0] == points[-1]:
        c = _corner_at(points[-2], points[0], points[1], min_leg_mm)
        if c is not None:
            corners.append(c)
    return corners


def trace_corners(
    segments, tol: float = DEFAULT_TOL_MM, min_leg_mm: float = 0.0
) -> list[Corner]:
    """一组无序线段 -> 折线 -> 全部拐角（含 180° 直行点）。

    首尾重合的闭合折线（覆铜外框/void 轮廓/网格单元）上的拐角带
    is_closed=True —— 覆铜几何不是走线路径，其上的"锐角"是 45° 网格画法，
    由调用方豁免。
    """
    corners: list[Corner] = []
    for line in chain_segments(segments, tol=tol):
        closed = len(line) >= 4 and line[0] == line[-1]
        for c in polyline_corners(line, min_leg_mm=min_leg_mm):
            corners.append(replace(c, is_closed=closed) if closed else c)
    return corners
