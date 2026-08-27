from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

import httpx

from jobflow.config import get_settings

logger = logging.getLogger(__name__)

Provider = Literal["ollama", "groq", "openai", "none"]

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def _strip_thinking(content: str) -> str:
    """Remove Qwen-style reasoning blocks from model output."""
    tag = "redacted_reasoning"
    content = re.sub(rf"<{tag}>.*?</{tag}>", "", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL | re.IGNORECASE)
    return content.strip()


def _parse_json_content(content: str) -> dict[str, Any]:
    text = _strip_thinking(content.strip())
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


class LLMClient:
    """LLM wrapper — supports Ollama (local), Groq (free hosted), and OpenAI."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider: Provider = "none"
        self._openai_client = None
        self._active_model = ""

        if self.settings.llm_provider == "ollama":
            if self._ollama_reachable():
                self.provider = "ollama"
                self._active_model = self.settings.ollama_model
                logger.info("LLM: using Ollama model %s", self._active_model)
            else:
                logger.warning("LLM: Ollama not reachable at %s", self.settings.ollama_base_url)
        elif self.settings.llm_provider == "groq":
            self._init_openai_compatible(
                api_key=self.settings.groq_api_key,
                base_url=GROQ_BASE_URL,
                provider="groq",
                model=self.settings.groq_model,
            )
        elif self.settings.llm_provider == "openai":
            self._init_openai_compatible(
                api_key=self.settings.openai_api_key,
                base_url=None,
                provider="openai",
                model=self.settings.openai_model,
            )

    def _init_openai_compatible(
        self,
        *,
        api_key: str,
        base_url: str | None,
        provider: Provider,
        model: str,
    ) -> None:
        if not api_key or api_key in ("", "sk-...", "gsk_..."):
            logger.warning("LLM: %s API key not configured", provider)
            return
        try:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self._openai_client = OpenAI(**kwargs)
            self.provider = provider
            self._active_model = model
            logger.info("LLM: using %s model %s", provider, model)
        except Exception as exc:
            logger.warning("LLM: %s init failed: %s", provider, exc)

    @property
    def enabled(self) -> bool:
        return self.provider != "none"

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self._active_model,
        }

    def _ollama_reachable(self) -> bool:
        try:
            resp = httpx.get(f"{self.settings.ollama_base_url.rstrip('/')}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def _ollama_chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        num_predict = (
            self.settings.ollama_num_predict_json if json_mode else self.settings.ollama_num_predict_text
        )
        payload: dict[str, Any] = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.2 if json_mode else 0.4,
                "num_predict": num_predict,
            },
        }
        if not self.settings.ollama_think:
            payload["think"] = False
        if json_mode:
            payload["format"] = "json"

        timeout = httpx.Timeout(self.settings.ollama_timeout, connect=10.0)
        resp = httpx.post(
            f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def _chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str | None:
        if self.provider == "ollama":
            return self._ollama_chat(messages, json_mode=json_mode)

        if self.provider in ("openai", "groq") and self._openai_client:
            kwargs: dict[str, Any] = {
                "model": self._active_model,
                "temperature": 0.2 if json_mode else 0.4,
                "messages": messages,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = self._openai_client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

        return None

    def complete_json(self, system: str, user: str, fallback: dict[str, Any]) -> dict[str, Any]:
        user = _truncate(user, self.settings.llm_max_input_chars)
        messages = [
            {"role": "system", "content": system + "\nRespond with valid JSON only."},
            {"role": "user", "content": user},
        ]
        try:
            content = self._chat(messages, json_mode=True)
            if content:
                return _parse_json_content(content)
        except Exception as exc:
            logger.warning("LLM JSON call failed (%s): %s", self.provider, exc)
        logger.info("LLM JSON using heuristic fallback")
        return fallback

    def complete_text(self, system: str, user: str, fallback: str) -> str:
        user = _truncate(user, self.settings.llm_max_input_chars)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            content = self._chat(messages, json_mode=False)
            if content:
                return _strip_thinking(content) or content
        except Exception as exc:
            logger.warning("LLM text call failed (%s): %s", self.provider, exc)
        logger.info("LLM text using heuristic fallback")
        return fallback


def extract_skills(text: str) -> list[str]:
    known = [
        "python",
        "fastapi",
        "django",
        "flask",
        "postgresql",
        "sql",
        "mongodb",
        "redis",
        "docker",
        "kubernetes",
        "aws",
        "gcp",
        "azure",
        "react",
        "typescript",
        "javascript",
        "node.js",
        "langchain",
        "openai",
        "llm",
        "rag",
        "machine learning",
        "pytorch",
        "tensorflow",
        "ci/cd",
        "git",
        "graphql",
        "rest",
        "microservices",
        "kafka",
        "spark",
        "airflow",
        "terraform",
        "linux",
        "java",
        "go",
        "rust",
        "c++",
        "nlp",
        "embeddings",
        "ecs",
        "system design",
        "css",
    ]
    lowered = text.lower()
    found: list[str] = []
    for skill in known:
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, lowered):
            found.append(skill)
    return sorted(set(found))
