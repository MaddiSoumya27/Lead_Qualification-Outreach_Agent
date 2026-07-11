"""
LLM client wrapper.
Used ONLY for:
  1. Scoring rationale phrasing (scoring.py)
  2. Email drafting (drafting.py)

Never used for: score computation, routing decisions, or gate logic.

Requires OPENAI_API_KEY in environment (or .env file).
Falls back to a no-op echo if the key is absent — enabling offline/test mode.
"""
from __future__ import annotations
import os

from dotenv import load_dotenv

load_dotenv()

_OPENAI_AVAILABLE = False
_client = None

try:
    import openai
    _api_key = os.getenv("OPENAI_API_KEY", "")
    if _api_key:
        _client = openai.OpenAI(api_key=_api_key)
        _OPENAI_AVAILABLE = True
except ImportError:
    pass

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def llm_call(prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = 256) -> str:
    """
    Send a prompt to the LLM and return the text response.
    If OpenAI is unavailable (missing key or import failure), returns a deterministic
    placeholder — pipeline still runs fully in offline mode.
    """
    if _OPENAI_AVAILABLE and _client is not None:
        response = _client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content or ""
    # Offline / no-key fallback — returns the prompt's last line as a stub
    last_line = [l.strip() for l in prompt.splitlines() if l.strip()][-1]
    return f"[OFFLINE MODE] Stub response for: {last_line[:80]}"


def is_llm_available() -> bool:
    return _OPENAI_AVAILABLE
