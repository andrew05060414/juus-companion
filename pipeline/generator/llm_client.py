"""OpenAI-compatible client for LLM generation."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from pipeline.config import MODEL_NAME, OPENAI_API_KEY, OPENAI_BASE_URL

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for calling OpenAI-compatible model gateways."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ):
        self.base_url = (base_url or OPENAI_BASE_URL).rstrip("/")
        self.api_key = api_key or OPENAI_API_KEY
        self.model = model or MODEL_NAME
        self.timeout = timeout

    def is_available(self) -> bool:
        """Check if model endpoint is accessible."""
        url = f"{self.base_url}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "JuusCompanion-Pipeline/0.1",
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Optional[str]:
        """Call chat completions API."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "JuusCompanion-Pipeline/0.1",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    choices = resp_data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.warning("LLM request failed (%s): %s", url, e)
        return None

