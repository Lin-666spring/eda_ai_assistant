"""
仿真器抽象接口
面向接口编程，核心功能与外部仿真工具解耦
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SimulationResult:
    """仿真结果"""

    success: bool
    output: str           # 原始输出文本
    plots: list[dict]     # 波形/曲线数据
    measurements: dict    # 测量数据 {"Vout": 3.3, "I_load": 0.5, ...}
    error_message: str = ""


class Simulator(ABC):
    """仿真器抽象基类

    所有外部仿真引擎（LTspice、Ngspice 等）都需要实现此接口。
    这种设计使得核心业务逻辑（BOM 处理）与仿真工具完全解耦，
    未来可无缝切换或新增仿真引擎。
    """

    @abstractmethod
    def run_simulation(self, netlist: str, analysis: str = "op") -> SimulationResult:
        """
        运行电路仿真

        Args:
            netlist:  SPICE 格式的网表文件内容
            analysis: 分析类型 (op/dc/ac/tran)

        Returns:
            SimulationResult 仿真结果
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """检查仿真器是否可用（已安装且配置正确）"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """仿真器名称"""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """仿真器版本"""
        ...


class DummySimulator(Simulator):
    """占位仿真器

    当未安装真实仿真引擎时使用，保证主流程畅通。
    所有方法返回模拟数据，便于开发和测试。
    """

    @property
    def name(self) -> str:
        return "DummySimulator"

    @property
    def version(self) -> str:
        return "0.0.0"

    def is_available(self) -> bool:
        return True

    def run_simulation(self, netlist: str, analysis: str = "op") -> SimulationResult:
        """返回模拟的仿真结果"""
        return SimulationResult(
            success=True,
            output=f"[DummySimulator] 模拟 {analysis} 分析完成\n{netlist[:200]}...",
            plots=[{"name": "V(out)", "type": "waveform", "data": []}],
            measurements={"Vout": 3.3, "I_load": 0.1},
            error_message="",
        )
