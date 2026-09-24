"""LLM client (OpenRouter, OpenAI-compatible).

Reads OPENROUTER_API_KEY / OPENROUTER_MODEL / OPENROUTER_BASE_URL from env or .env. If no key is
present the agent layer degrades gracefully (callers use deterministic fallbacks), so the graph and
tests run with or without an LLM. The LLM is used ONLY for understand/clarify/explain — never for
calculation, scoring, eligibility, or decisions (docs/01 §0, docs/02).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional, TypeVar

from pydantic import BaseModel, ValidationError

_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
T = TypeVar("T", bound=BaseModel)


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    if key in os.environ:
        return os.environ[key]
    if _ENV.exists():
        for line in _ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1]
    return default


def llm_available() -> bool:
    if os.environ.get("AGENT_DISABLE_LLM"):   # tests / offline: force deterministic fallbacks
        return False
    return bool(_env("OPENROUTER_API_KEY"))


@lru_cache(maxsize=1)
def _client():
    from openai import OpenAI
    return OpenAI(
        api_key=_env("OPENROUTER_API_KEY"),
        base_url=_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )


def _model() -> str:
    return _env("OPENROUTER_MODEL", "openai/gpt-6-luna")


def chat(system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 700) -> str:
    """Plain-text completion. Raises if no key (callers guard with llm_available())."""
    resp = _client().chat.completions.create(
        model=_model(),
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return (resp.choices[0].message.content or "").strip()


def extract_json(system: str, user: str, schema: type[T], *, retries: int = 1) -> Optional[T]:
    """Structured extraction via JSON mode + Pydantic validation (model-agnostic).

    Returns a validated schema instance, or None if the model output can't be parsed after retries.
    Never raises on bad model output — the caller then treats fields as MISSING and clarifies.
    """
    sys = (system + "\n\nRespond with ONLY a single JSON object matching this schema, no prose:\n"
           + json.dumps(schema.model_json_schema()))
    last_err = None
    for _ in range(retries + 1):
        try:
            resp = _client().chat.completions.create(
                model=_model(),
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            )
            raw = resp.choices[0].message.content or "{}"
            return schema.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError, Exception) as e:  # noqa: BLE001
            last_err = e
    print(f"[agent] extract_json failed: {last_err}")
    return None
