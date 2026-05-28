"""PCB 数据模型 — 轻量、可扩展"""

from dataclasses import dataclass, field


@dataclass
class PCBTrace:
    """走线线段"""
    net_name: str          # 所属网络名
    layer: str             # 所在层 (TopLayer/BottomLayer/...)
    width_mm: float        # 线宽 (mm)
    segments: list = field(default_factory=list)  # [(x1,y1,x2,y2), ...]


@dataclass
class PCBNet:
    """网络（一组电气连接的引脚）"""
    name: str
    pins: list[str] = field(default_factory=list)   # ["U1.8", "R1.1", ...]
    trace_count: int = 0
    total_length_mm: float = 0.0


@dataclass
class PCBVia:
    """过孔"""
    position: tuple[float, float]  # (x, y)
    drill_mm: float
    pad_mm: float
    from_layer: str
    to_layer: str
    net_name: str = ""


@dataclass
class PCBData:
    """PCB 数据容器

    轻量解析只填充 nets/traces/layers；其余字段预留 M2/M3 扩展。
    """
    format: str = "unknown"            # "lceda_json" | "lceda_epro" | "unknown"
    layers: list[str] = field(default_factory=list)
    nets: dict[str, PCBNet] = field(default_factory=dict)  # net_name → PCBNet
    traces: list[PCBTrace] = field(default_factory=list)
    vias: list[PCBVia] = field(default_factory=list)
    copper_pours: list = field(default_factory=list)        # 预留 M2
    differential_pairs: list = field(default_factory=list)  # 预留 M3
    board_outline: dict = field(default_factory=dict)       # {width_mm, height_mm, shape}
    component_positions: dict = field(default_factory=dict)  # ref → {x, y, rotation, layer}

    @property
    def net_count(self) -> int:
        return len(self.nets)

    @property
    def trace_count(self) -> int:
        return len(self.traces)

    @property
    def via_count(self) -> int:
        return len(self.vias)

    def get_nets_by_type(self, power_kw: tuple = (), signal_kw: tuple = ()) -> tuple[list, list]:
        """按关键词分类网络为电源网络和信号网络"""
        power_nets = []
        signal_nets = []
        for name, net in self.nets.items():
            upper = name.upper()
            if any(kw.upper() in upper for kw in power_kw):
                power_nets.append(net)
            elif signal_kw and any(kw.upper() in upper for kw in signal_kw):
                signal_nets.append(net)
            elif signal_kw:
                signal_nets.append(net)
        return power_nets, signal_nets
