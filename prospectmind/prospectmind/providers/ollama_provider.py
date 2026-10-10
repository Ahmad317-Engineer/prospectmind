"""Ollama local LLM provider for ProspectMind."""

from __future__ import annotations

from typing import Optional

from .base import BaseLLMProvider, LLMResponse


class OllamaProvider(BaseLLMProvider):
    """Ollama local inference provider. Cost = $0."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434",
    ):
        super().__init__(api_key=None, model=model)
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "Ollama (local)"

    async def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        try:
            import httpx
        except ImportError:
            raise ImportError("Run: pip install httpx")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            return LLMResponse(content=text, model=self.model)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0  # Local inference is free
