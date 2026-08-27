"""Pluggable LLM provider — OpenAI-compatible chat API.

Lets the demo/validation layer talk to ANY OpenAI-compatible endpoint for
testing: OpenAI, DeepSeek, local vLLM/Ollama, or GRAPHIA's own services
(LLM4SSH / Quagga) if they expose such an API. Configured purely via env:

    FEN_LLM_BASE_URL   e.g. https://api.deepseek.com/v1   (or https://api.openai.com/v1)
    FEN_LLM_API_KEY    secret token
    FEN_LLM_MODEL      e.g. deepseek-chat, gpt-4o-mini, llama-3.1-8b-instruct
    FEN_LLM_TIMEOUT_S  default 30

The provider never raises: callers get ``None`` on any failure so the
pipeline can fall back to a deterministic rule (no blocking points).
"""
from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


class LLMConfig:
    """Env-driven LLM settings; ``enabled`` is True only when a base URL is set."""

    def __init__(self) -> None:
        self.base_url: Optional[str] = os.getenv("FEN_LLM_BASE_URL") or None
        self.api_key: Optional[str] = os.getenv("FEN_LLM_API_KEY") or None
        self.model: str = os.getenv("FEN_LLM_MODEL", "deepseek-chat")
        self.timeout_s: float = float(os.getenv("FEN_LLM_TIMEOUT_S", "30"))

    @property
    def enabled(self) -> bool:
        return self.base_url is not None


def chat_completion(config: LLMConfig, system: str, user: str) -> Optional[str]:
    """Call POST {base_url}/chat/completions with a single-turn prompt.

    Returns the assistant message text, or None on any failure/irregular
    response — callers must handle None (fallback path).
    """
    if not config.enabled:
        return None
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=config.timeout_s)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001 - the provider must never raise (fail-open contract)
        logger.exception("LLM call to %s failed", url)
        return None


def parse_outcome(text: Optional[str], allowed: tuple) -> Optional[str]:
    """Extract one of ``allowed`` outcomes from a free-form LLM answer.

    Accepts the bare word or a line containing it (case-insensitive).
    """
    if not text:
        return None
    lowered = text.lower()
    for candidate in allowed:
        if candidate in lowered:
            return candidate
    return None
