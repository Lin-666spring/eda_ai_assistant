"""
统一异常层次结构
所有项目自定义异常的基类，便于上层统一捕获和处理
"""


class EDAAIAssistantError(Exception):
    """项目基础异常 — 所有自定义异常的基类"""
    pass


# ══════════════════ BOM 模块异常 ══════════════════

class BOMError(EDAAIAssistantError):
    """BOM 处理相关异常基类"""
    pass


class BOMParseError(BOMError):
    """BOM 文件解析失败"""
    pass


class BOMValidationError(BOMError):
    """BOM 数据校验失败（封装不匹配等）"""
    pass


class BOMEmptyError(BOMError):
    """BOM 数据为空"""
    pass


class BOMFormatError(BOMError):
    """BOM 文件格式不支持"""
    pass


# ══════════════════ Agent 模块异常 ══════════════════

class AgentError(EDAAIAssistantError):
    """AI Agent 相关异常基类"""
    pass


class AgentAPIError(AgentError):
    """API 调用失败（网络、认证等）"""
    pass


class AgentParseError(AgentError):
    """AI 返回结果解析失败"""
    pass


class AgentConfigError(AgentError):
    """Agent 配置错误（API Key 缺失等）"""
    pass


# ══════════════════ 配置异常 ══════════════════

class ConfigError(EDAAIAssistantError):
    """配置相关异常"""
    pass


# ══════════════════ 仿真器异常 ══════════════════

class SimulationError(EDAAIAssistantError):
    """仿真器相关异常"""
    pass


class SimulationNotAvailableError(SimulationError):
    """仿真引擎不可用"""
    pass


# ══════════════════ PCB 模块异常 ══════════════════

class PCBError(EDAAIAssistantError):
    """PCB 解析相关异常基类"""
    pass


class PCBParseError(PCBError):
    """PCB 文件解析失败（格式不兼容/文件损坏）"""
    pass


# ══════════════════ 供应链模块异常 ══════════════════

class SupplyError(EDAAIAssistantError):
    """供应链（立创商城）相关异常基类"""
    pass


class SupplyAPIError(SupplyError):
    """商城 API 调用失败"""
    pass


class SupplyAuthError(SupplyError):
    """商城 API 认证失败"""
    pass


class SupplyNotFoundError(SupplyError):
    """元器件在商城中未找到"""
    pass
