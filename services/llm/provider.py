"""
Unified LLM Provider abstraction.

Priority chain: Ollama → OpenAI-compatible (FreeLLMAPI/OpenRouter/Groq/…) → Google Gemini
All callers should use `call_llm()` or `call_chat_llm()` instead of
making direct HTTP/SDK calls so provider switching happens in one place.
"""

import requests
from typing import Optional
from config.settings import settings
from config.logging_config import logger


def call_llm(prompt: str, expect_json: bool = False) -> Optional[str]:
    """
    Single-turn completion. Returns raw text or None if all providers fail.
    Set expect_json=True to request JSON-formatted output from the model.
    """
    provider = (settings.LLM_PROVIDER or "ollama").lower()

    if provider == "ollama":
        result = _ollama_generate(prompt, expect_json)
        if result is not None:
            return result
        logger.warning("Ollama generate failed, trying next provider")

    if provider in ("openai_compatible", "ollama"):
        result = _openai_compatible_generate(prompt, expect_json)
        if result is not None:
            return result

    result = _gemini_generate(prompt, expect_json)
    if result is not None:
        return result

    logger.error("All LLM providers failed for single-turn call")
    return None


def call_chat_llm(messages: list[dict]) -> str:
    """
    Multi-turn chat completion.
    messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]
    Returns the assistant reply, or a user-facing error string.
    """
    provider = (settings.LLM_PROVIDER or "ollama").lower()

    if provider == "ollama":
        result = _ollama_chat(messages)
        if result is not None:
            return result
        logger.warning("Ollama chat failed, trying next provider")

    if provider in ("openai_compatible", "ollama"):
        result = _openai_compatible_chat(messages)
        if result is not None:
            return result

    result = _gemini_chat(messages)
    if result is not None:
        return result

    return (
        "I am having trouble connecting to the AI model. "
        "Please check your LLM_PROVIDER setting and ensure the service is reachable."
    )


# ─── Private helpers ──────────────────────────────────────────────────────────

def _ollama_generate(prompt: str, expect_json: bool) -> Optional[str]:
    try:
        payload: dict = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        }
        if expect_json:
            payload["format"] = "json"
        resp = requests.post(settings.OLLAMA_URL, json=payload, timeout=300.0)
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        logger.warning(f"Ollama generate HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Ollama generate exception: {e}")
    return None


def _ollama_chat(messages: list[dict]) -> Optional[str]:
    try:
        chat_url = settings.OLLAMA_URL.replace("/api/generate", "/api/chat")
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
        }
        resp = requests.post(chat_url, json=payload, timeout=300.0)
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "").strip()
        logger.warning(f"Ollama chat HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Ollama chat exception: {e}")
    return None


def _openai_compatible_generate(prompt: str, expect_json: bool) -> Optional[str]:
    """Works with FreeLLMAPI, OpenRouter, Groq, Together, and any OpenAI-compatible API."""
    base_url = (settings.OPENAI_COMPATIBLE_BASE_URL or "").rstrip("/")
    api_key = settings.OPENAI_COMPATIBLE_API_KEY or ""
    if not base_url or not api_key:
        return None
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": settings.OPENAI_COMPATIBLE_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        if expect_json:
            payload["response_format"] = {"type": "json_object"}
        resp = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120.0,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        logger.warning(f"OpenAI-compatible generate HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"OpenAI-compatible generate exception: {e}")
    return None


def _openai_compatible_chat(messages: list[dict]) -> Optional[str]:
    base_url = (settings.OPENAI_COMPATIBLE_BASE_URL or "").rstrip("/")
    api_key = settings.OPENAI_COMPATIBLE_API_KEY or ""
    if not base_url or not api_key:
        return None
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.OPENAI_COMPATIBLE_MODEL,
            "messages": messages,
            "temperature": 0.3,
        }
        resp = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120.0,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        logger.warning(f"OpenAI-compatible chat HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"OpenAI-compatible chat exception: {e}")
    return None


def _gemini_generate(prompt: str, expect_json: bool) -> Optional[str]:
    api_key = settings.GEMINI_API_KEY or ""
    if not api_key or "YOUR_GEMINI_API" in api_key:
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json" if expect_json else "text/plain",
            temperature=0.1,
        )
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=cfg,
        )
        return response.text.strip()
    except Exception as e:
        logger.warning(f"Gemini generate exception: {e}")
    return None


def _gemini_chat(messages: list[dict]) -> Optional[str]:
    api_key = settings.GEMINI_API_KEY or ""
    if not api_key or "YOUR_GEMINI_API" in api_key:
        return None
    try:
        from google import genai
        from google.genai import types
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"System: {content}\n\n")
            elif role == "user":
                parts.append(f"User: {content}\n")
            elif role == "assistant":
                parts.append(f"Assistant: {content}\n")
        parts.append("Assistant:")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents="".join(parts),
            config=types.GenerateContentConfig(temperature=0.3),
        )
        return response.text.strip()
    except Exception as e:
        logger.warning(f"Gemini chat exception: {e}")
    return None
