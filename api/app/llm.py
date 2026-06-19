"""Przełączalny adapter LLM — protokół zgodny z OpenAI Chat Completions.

Anthropic, Ollama i OpenAI (oraz większość lokalnych serwerów: vLLM, LM Studio,
llama.cpp) wystawiają ten sam endpoint `POST {base_url}/chat/completions` ze
streamingiem przez SSE. Dlatego przełączanie dostawcy = zmiana base_url + api_key
+ model w konfiguracji, bez żadnego SDK konkretnego vendora.
"""
import json
from collections.abc import AsyncIterator

import httpx

from app.config import get_settings

settings = get_settings()


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    return headers


async def stream_chat(
    messages: list[dict[str, str]],
    *,
    system: str | None = None,
) -> AsyncIterator[str]:
    """Strumieniuje odpowiedź modelu jako kolejne fragmenty tekstu (deltas).

    `messages`: lista {"role": "user"|"assistant", "content": str}.
    `system`: opcjonalny prompt systemowy (dołączany jako wiadomość role=system).
    """
    payload_messages: list[dict[str, str]] = []
    if system:
        payload_messages.append({"role": "system", "content": system})
    payload_messages.extend(messages)

    body = {
        "model": settings.llm_model,
        "messages": payload_messages,
        "stream": True,
        "max_tokens": 1024,
    }

    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        async with client.stream("POST", url, headers=_headers(), json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = (
                    chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                )
                if delta:
                    yield delta
