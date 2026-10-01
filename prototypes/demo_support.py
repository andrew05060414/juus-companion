"""Local fake OpenAI-compatible HTTP server used only by the M0 demo."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any


class _DemoRequestHandler(BaseHTTPRequestHandler):
    server: _DemoHTTPServer

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.server.requests.append(payload)
        metadata = payload.get("metadata", {})
        speaker_id = metadata.get("speaker_id", "unknown")
        messages = payload.get("messages", [])
        last_user = next(
            (message.get("content", "") for message in reversed(messages) if message.get("role") == "user"),
            "",
        )
        if metadata.get("origin") == "proactive":
            content = f"{speaker_id} 主动提醒：记得安排一点休息。"
        else:
            content = f"{speaker_id} 回复：已收到「{last_user}」。"
        body = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": content}}]},
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        del format, args


class _DemoHTTPServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int]) -> None:
        super().__init__(address, _DemoRequestHandler)
        self.requests: list[dict[str, Any]] = []


class DemoOpenAIServer:
    """Context manager for a loopback-only, deterministic model endpoint."""

    def __init__(self) -> None:
        self._server: _DemoHTTPServer | None = None
        self._thread: Thread | None = None

    def __enter__(self) -> DemoOpenAIServer:
        self._server = _DemoHTTPServer(("127.0.0.1", 0))
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        del exc_type, exc_value, traceback
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("DemoOpenAIServer must be entered before use")
        return f"http://127.0.0.1:{self._server.server_port}/v1"

    @property
    def request_count(self) -> int:
        return len(self.requests)

    @property
    def requests(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._server.requests if self._server is not None else ())
