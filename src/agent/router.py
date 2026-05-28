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
    """任务意图分类"""
    TEXT_CHAT = auto()         # 通用文本对话
    BOM_ANALYSIS = auto()      # BOM 分析/合并
    RULE_CHECK = auto()        # 规则检查
    PCB_ANALYSIS = auto()      # PCB 布局分析
    CODE_RULE_GEN = auto()     # 代码/DRC 规则生成
    VISUAL = auto()            # 图像分析（原理图/PCB截图）
    LOCAL_ONLY = auto()        # 纯本地处理


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
        # 视觉任务优先用多模态模型
        bindings[TaskIntent.VISUAL] = ProviderBinding(
            name="moonshot", model="kimi-k2.6", api_key=key, base_url="https://api.moonshot.cn/v1",
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

    def classify_intent(self, user_input: str) -> TaskIntent:
        """简单意图分类（关键词 + 规则）

        后续可替换为 LLM 分类器。
        """
        lowered = user_input.lower()

        # 视觉/图像分析
        if any(kw in lowered for kw in ("图片", "截图", "图像", "看图", "照片", "原理图")):
            return TaskIntent.VISUAL

        # BOM 相关
        if any(kw in lowered for kw in ("bom", "合并", "物料", "元件", "型号", "封装",
                                         "位号", "查重", "校验")):
            return TaskIntent.BOM_ANALYSIS

        # 代码/规则生成（必须在规则检查之前——"生成规则"优先于"规则"）
        if any(kw in lowered for kw in ("生成", "创建", "编写", "写一个")):
            return TaskIntent.CODE_RULE_GEN

        # 规则检查
        if any(kw in lowered for kw in ("规则", "drc", "检查", "违规", "去耦",
                                         "信号线", "电源线", "线宽")):
            return TaskIntent.RULE_CHECK

        # PCB 分析
        if any(kw in lowered for kw in ("pcb", "布局", "布线", "走线", "层", "板")):
            return TaskIntent.PCB_ANALYSIS

        return TaskIntent.TEXT_CHAT

    @property
    def available_intents(self) -> list[TaskIntent]:
        """列出有可用客户端的意图"""
        return [i for i in TaskIntent if self.resolve(i) is not None]
