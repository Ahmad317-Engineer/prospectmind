"""OpenAI provider for ProspectMind."""

from __future__ import annotations

import os
from typing import Optional

from .base import BaseLLMProvider, LLMResponse

# Cost per 1M tokens as of late 2024 (USD)
PRICING = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
}


class OpenAIProvider(BaseLLMProvider):
    """OpenAI ChatCompletion provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var or pass --api-key."
            )
        super().__init__(api_key=key, model=model)

    @property
    def name(self) -> str:
        return "OpenAI"

    async def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("Run: pip install openai")

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=512,
        )
        msg = response.choices[0].message.content or ""
        return LLMResponse(
            content=msg,
            model=self.model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        in_price, out_price = PRICING.get(self.model, (0.15, 0.60))
        return (input_tokens / 1_000_000 * in_price) + (
            output_tokens / 1_000_000 * out_price
        )
