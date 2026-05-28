from .llm_client import LLMClient
from .prompt_templates import PromptTemplates
from .router import LLMRouter, TaskIntent, RouterConfig, ProviderBinding

# 向后兼容别名
DeepSeekClient = LLMClient

__all__ = [
    "LLMClient", "DeepSeekClient", "PromptTemplates",
    "LLMRouter", "TaskIntent", "RouterConfig", "ProviderBinding",
]
