"""Core orchestration layer — UI-agnostic business logic."""
from .controller import AppController, CommandContext

__all__ = ["AppController", "CommandContext"]
