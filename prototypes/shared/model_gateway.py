"""OpenAI-compatible model gateway used by both prototype shapes."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Protocol


class ModelGatewayError(RuntimeError):
    """Raised when an OpenAI-compatible response cannot be consumed."""


class ModelGateway(Protocol):
    def complete(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        metadata: Mapping[str, str],
    ) -> str:
        """Return one assistant message for the supplied conversation."""


class OpenAICompatibleGateway:
    """Minimal dependency-free client for ``/v1/chat/completions``."""

    def __init__(
        self,
        base_url: str,
        *,
        model: str,
        api_key_env: str = "JUUS_MODEL_API_KEY",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds

    def complete(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        metadata: Mapping[str, str],
    ) -> str:
        payload = {
            "model": self.model,
            "messages": list(messages),
            "metadata": dict(metadata),
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **self._auth_header()},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ModelGatewayError(f"model gateway returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ModelGatewayError(f"model gateway request failed: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelGatewayError("model gateway response lacks choices[0].message.content") from exc
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            combined = "".join(text_parts).strip()
            if combined:
                return combined
        raise ModelGatewayError("model gateway returned an empty assistant message")

    def _auth_header(self) -> dict[str, str]:
        api_key = os.getenv(self.api_key_env)
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}
