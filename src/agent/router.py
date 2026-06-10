"""多 LLM 协同路由网关

按任务类型自动分派到最优模型：
- 文本对话 → DeepSeek（快速、便宜）
- 视觉分析 → Kimi/Qwen-VL（多模态）
- 规则生成 → DeepSeek/Claude（推理强）
- 简单指令 → 本地关键词（零 API 调用）
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from .llm_client import LLMClient
from ..config import config as app_config

logger = logging.getLogger(__name__)


class TaskIntent(Enum):
    """任务意图分类 — 10 大类覆盖电子设计全流程"""
    TEXT_CHAT = auto()          # 通用文本对话/电子知识问答
    BOM_ANALYSIS = auto()       # BOM 物料分析/合并/校验
    BOM_HEALTH = auto()         # BOM 供应链健康（库存/替代料/成本/采购）
    RULE_CHECK = auto()         # PCB 设计规则检查 (DRC)
    PCB_ANALYSIS = auto()       # PCB 布局布线分析
    CODE_RULE_GEN = auto()      # 代码/DRC 规则/脚本生成
    REPORT_GEN = auto()         # 报告生成（HTML BOM/设计报告/统计）
    COMPONENT_LOOKUP = auto()   # 元件信息查询（datasheet/规格/参数/封装）
    VISUAL = auto()             # 图像分析（原理图/PCB截图/波形）
    LOCAL_ONLY = auto()         # 纯本地处理（统计/状态/文件操作）


@dataclass
class ProviderBinding:
    """单个厂商绑定"""
    name: str                  # 厂商名 (deepseek/openai/qwen/glm/moonshot/siliconflow)
    model: str                 # 具体模型
    api_key: str = ""
    base_url: str = ""

    def create_client(self) -> Optional[LLMClient]:
        if not self.api_key:
            return None
        return LLMClient(
            api_key=self.api_key,
            base_url=self.base_url or None,
            model=self.model or None,
            provider=self.name,
        )


@dataclass
class RouterConfig:
    """路由配置 — 每种意图绑定哪个厂商"""
    text_chat: ProviderBinding = field(default_factory=lambda: ProviderBinding(
        name="deepseek", model="deepseek-v4-pro",
    ))
    bom_analysis: ProviderBinding = field(default_factory=lambda: ProviderBinding(
        name="deepseek", model="deepseek-v4-pro",
    ))
    rule_check: ProviderBinding = field(default_factory=lambda: ProviderBinding(
        name="deepseek", model="deepseek-v4-pro",
    ))
    pcb_analysis: ProviderBinding = field(default_factory=lambda: ProviderBinding(
        name="deepseek", model="deepseek-v4-pro",
    ))
    code_rule_gen: ProviderBinding = field(default_factory=lambda: ProviderBinding(
        name="deepseek", model="deepseek-v4-pro",
    ))
    bom_health: ProviderBinding = field(default_factory=lambda: ProviderBinding(
        name="deepseek", model="deepseek-v4-pro",
    ))
    report_gen: ProviderBinding = field(default_factory=lambda: ProviderBinding(
        name="deepseek", model="deepseek-v4-pro",
    ))
    component_lookup: ProviderBinding = field(default_factory=lambda: ProviderBinding(
        name="deepseek", model="deepseek-v4-pro",
    ))
    visual: ProviderBinding = field(default_factory=lambda: ProviderBinding(
        name="moonshot", model="kimi-k2.6",
    ))

    def set_all(self, name: str, model: str):
        """快捷：所有意图用同一厂商（起步阶段）"""
        for field_name in self.__dataclass_fields__:
            setattr(self, field_name, ProviderBinding(name=name, model=model))


class LLMRouter:
    """多 LLM 路由网关

    根据任务意图自动选择最优模型。初期所有文本任务用同一 LLMClient，
    架构已预留按意图独立路由的能力。

    使用方式:
        router = LLMRouter.from_config()
        reply = router.route(TaskIntent.BOM_ANALYSIS).chat(prompt)
    """

    def __init__(self, bindings: dict[TaskIntent, ProviderBinding]):
        self._bindings = bindings
        self._clients: dict[str, LLMClient] = {}  # cache by provider+model

    @classmethod
    def from_config(cls, api_key: Optional[str] = None) -> "LLMRouter":
        """从 AppConfig 创建路由器"""
        key = api_key or app_config.llm.api_key
        url = app_config.llm.base_url
        model = app_config.llm.model
        provider = app_config.llm.provider

        binding = ProviderBinding(
            name=provider, model=model, api_key=key, base_url=url,
        )

        bindings = {intent: binding for intent in TaskIntent}
        # 视觉任务优先用原生多模态模型
        bindings[TaskIntent.VISUAL] = ProviderBinding(
            name="gemini", model="gemini-2.5-pro", api_key=key, base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        )
        # 纯本地处理不需要模型
        bindings[TaskIntent.LOCAL_ONLY] = ProviderBinding(name="local", model="")

        return cls(bindings)

    def resolve(self, intent: TaskIntent) -> Optional[LLMClient]:
        """获取意图对应的 LLM 客户端（带缓存）"""
        binding = self._bindings.get(intent)
        if binding is None or binding.name == "local":
            return None

        cache_key = f"{binding.name}:{binding.model}"
        if cache_key not in self._clients:
            client = binding.create_client()
            if client:
                self._clients[cache_key] = client
                logger.info(
                    "Router: %s → %s/%s", intent.name, binding.name, binding.model,
                )

        return self._clients.get(cache_key)

    def execute(
        self,
        intent: TaskIntent,
        prompt: str,
        system_prompt: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """端到端执行：路由 + 调用

        Returns:
            LLM 回复文本
        """
        client = self.resolve(intent)
        if client is None:
            return f"[本地处理] {intent.name}"

        try:
            if on_token:
                return client.chat_stream(
                    prompt, system_prompt=system_prompt, on_token=on_token,
                )
            return client.chat(prompt, system_prompt=system_prompt)
        except Exception as e:
            logger.error("LLM call failed for intent %s: %s", intent.name, e)
            return f"AI 调用失败 ({intent.name}): {e}"

    def classify_intent_with_confidence(self, user_input: str) -> tuple[TaskIntent, float]:
        """意图分类（带置信度）

        委托给 _classify_by_keyword（从 ToolRegistry 派生关键词）。
        NLU 引擎由 Controller 持有，Router 仅做关键词降级。

        Returns:
            (intent, confidence) — confidence 为 0.0-1.0
        """
        intent = self._classify_by_keyword(user_input)
        # 关键词命中 → 较高置信度；TEXT_CHAT fallback → 低置信度
        confidence = 0.80 if intent != TaskIntent.TEXT_CHAT else 0.30
        return (intent, confidence)

    def classify_intent(self, user_input: str) -> TaskIntent:
        """简单意图分类（向后兼容）

        委托给 classify_intent_with_confidence，仅返回意图。
        """
        intent, _ = self.classify_intent_with_confidence(user_input)
        return intent

    # 意图级关键词（Router 专用，ToolRegistry 不包含非工具意图如 VISUAL/CODE_RULE_GEN）
    _INTENT_KEYWORDS: dict[TaskIntent, tuple[str, ...]] = {
        TaskIntent.VISUAL: (
            "图片", "截图", "图像", "看图", "照片", "原理图",
            "电路图", "版图", "波形", "screenshot", "image", "photo",
        ),
        TaskIntent.CODE_RULE_GEN: (
            "生成", "创建", "编写", "写一个", "写一段", "新建",
            "脚本", "自动化", "批处理", "generate", "create rule",
        ),
        TaskIntent.RULE_CHECK: (
            "规则", "drc", "违规", "去耦",
            "信号线", "电源线", "线宽", "间距", "安规",
            "爬电", "差分", "设计规则", "过孔",
            "creepage", "clearance", "design rule",
            # 注意: "检查" 不在此列表 — 太通用，由 ToolRegistry 工具级关键词处理
        ),
        TaskIntent.BOM_ANALYSIS: (
            "bom", "合并", "物料", "元件", "型号", "封装",
            "位号", "查重", "校验", "清单", "材料", "零件",
            "器件", "元器件", "物料清单", "bom表", "归类",
            "整理", "同类", "merge", "duplicate", "validate",
        ),
        TaskIntent.PCB_ANALYSIS: (
            "pcb", "布局", "布线", "走线", "层", "板",
            "叠层", "阻抗", "载流", "信号完整性",
            "电路板", "pcb分析", "pcb布局",
            "layout", "routing", "stackup", "impedance",
        ),
    }

    def _classify_by_keyword(self, user_input: str) -> TaskIntent:
        """纯关键词意图分类

        优先用 ToolRegistry 聚合的关键词，辅以 _INTENT_KEYWORDS 兜底。
        检查优先级: VISUAL > CODE_RULE_GEN > RULE_CHECK > BOM_ANALYSIS > PCB_ANALYSIS
        """
        lowered = user_input.lower()

        # 优先级顺序（VISUAL 和 CODE_RULE_GEN 无工具但有意图关键词）
        intent_order = [
            TaskIntent.VISUAL, TaskIntent.CODE_RULE_GEN,
            TaskIntent.RULE_CHECK, TaskIntent.BOM_ANALYSIS, TaskIntent.PCB_ANALYSIS,
        ]

        for intent in intent_order:
            # 先查硬编码意图关键词
            if any(kw in lowered for kw in self._INTENT_KEYWORDS.get(intent, ())):
                return intent
            # 再查 ToolRegistry 工具关键词
            try:
                from .tools import ToolRegistry
                if any(kw in lowered for kw in ToolRegistry.get_keywords_by_intent(intent.name)):
                    return intent
            except ImportError:
                pass

        return TaskIntent.TEXT_CHAT

    @property
    def available_intents(self) -> list[TaskIntent]:
        """列出有可用客户端的意图"""
        return [i for i in TaskIntent if self.resolve(i) is not None]
