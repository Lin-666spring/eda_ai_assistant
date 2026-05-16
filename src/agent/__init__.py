from .llm_client import LLMClient
from .prompt_templates import PromptTemplates

# 向后兼容别名
DeepSeekClient = LLMClient

__all__ = ["LLMClient", "DeepSeekClient", "PromptTemplates"]
