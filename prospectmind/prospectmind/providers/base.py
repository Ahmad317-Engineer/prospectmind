"""Base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class BaseLLMProvider(ABC):
    """Abstract base class for LLM provider implementations."""

    def __init__(self, api_key: Optional[str], model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Send a prompt and return the completion."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for display."""
        ...

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD. Override in subclasses."""
        return 0.0
