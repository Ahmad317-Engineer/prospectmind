"""Anthropic Claude provider for ProspectMind."""

from __future__ import annotations

import os
from typing import Optional

from .base import BaseLLMProvider, LLMResponse

PRICING = {
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-opus-20240229": (15.00, 75.00),
}


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    def __init__(
        self, api_key: Optional[str] = None, model: str = "claude-3-5-haiku-20241022"
    ):
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY env var or pass --api-key."
            )
        super().__init__(api_key=key, model=model)

    @property
    def name(self) -> str:
        return "Anthropic"

    async def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError("Run: pip install anthropic")

        client = AsyncAnthropic(api_key=self.api_key)
        response = await client.messages.create(
            model=self.model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text if response.content else ""
        return LLMResponse(
            content=text,
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        in_price, out_price = PRICING.get(self.model, (0.80, 4.00))
        return (input_tokens / 1_000_000 * in_price) + (
            output_tokens / 1_000_000 * out_price
        )
