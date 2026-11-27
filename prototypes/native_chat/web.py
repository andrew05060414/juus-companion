"""Loopback web UI for the native one-on-one chat prototype."""

from __future__ import annotations

import json
import re
import webbrowser
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .engine import EngineError, EngineReply, LocalChatEngine

_STATIC = Path(__file__).resolve().parent / "static"
_BUBBLE_TEXT = re.compile(r"<bubble>(.*?)</bubble>", re.DOTALL)


def _jsonable(value):
    if isinstance(value, EngineReply):
        return {
            "ok": True,
            "model_id": value.model_id,
            "model_label": value.model_label,
            "configured": value.configured,
            "elapsed_ms": value.elapsed_ms,
            "warnings": list(value.warnings),
            "bubbles": [
                {"kind": bubble.kind, "text": bubble.text, "media_id": bubble.media_id}
                for bubble in value.bubbles
            ],
        }
    if isinstance(value, EngineError):
        return {
            "ok": False,
            "model_id": value.model_id,
            "model_label": value.model_label,
            "configured": value.configured,
            "error": value.error,
        }
    if is_dataclass(value):
        return asdict(value)
    return value


def _history_rows(rows):
    output = []
    for row in rows:
        item = {"role": row["role"], "id": row.get("id", ""), "at": row.get("at", "")}
        if row["role"] == "assistant":
            item["bubbles"] = _BUBBLE_TEXT.findall(row["content"])
            item["model_id"] = row.get("model_id", "")
        else:
            item["text"] = row["content"]
        output.append(item)
    return output


class NativeChatHTTPServer(ThreadingHTTPServer):
    def __init__(self, address, engine: LocalChatEngine):
        super().__init__(address, NativeChatHandler)
        self.engine = engine


class RejectedWriteRequest(PermissionError):
    """Raised when a browser cross-site or non-JSON write reaches the local API."""


class NativeChatHandler(BaseHTTPRequestHandler):
    server: NativeChatHTTPServer

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_file(_STATIC / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path in {"/app.js", "/style.css"}:
            content_type = (
                "text/javascript; charset=utf-8"
                if parsed.path.endswith(".js")
                else "text/css; charset=utf-8"
            )
            self._send_file(_STATIC / parsed.path.lstrip("/"), content_type)
            return
        if parsed.path == "/api/bootstrap":
            self._send_json(
                {
                    "personas": self.server.engine.list_personas(),
                    "models": self.server.engine.list_models(),
                    "context": _jsonable(self.server.engine.context),
                }
            )
            return
        if parsed.path == "/api/history":
            query = parse_qs(parsed.query)
            character_id = query.get("character_id", [""])[0]
            model_id = query.get("model_id", [""])[0]
            self._send_json(
                {"items": _history_rows(self.server.engine.history(character_id, model_id))}
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        try:
            self._validate_write_request()
            payload = self._read_json()
            if parsed.path == "/api/chat":
                reply = self.server.engine.send(
                    character_id=str(payload.get("character_id", "")),
                    model_id=str(payload.get("model_id", "")),
                    user_text=str(payload.get("message", "")),
                    include_context=bool(payload.get("include_context")),
                )
                self._send_json({"reply": _jsonable(reply)})
                return
            if parsed.path == "/api/compare":
                results = self.server.engine.compare(
                    character_id=str(payload.get("character_id", "")),
                    user_text=str(payload.get("message", "")),
                    include_context=bool(payload.get("include_context")),
                )
                self._send_json(
                    {"results": {key: _jsonable(value) for key, value in results.items()}}
                )
                return
            self.send_error(404)
        except RejectedWriteRequest as exc:
            self._send_json({"error": str(exc)}, status=403)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)

    def log_message(self, format: str, *args) -> None:
        del format, args

    def _validate_write_request(self) -> None:
        if self.headers.get_content_type() != "application/json":
            raise RejectedWriteRequest("write requests require application/json")
        fetch_site = self.headers.get("Sec-Fetch-Site", "").lower()
        if fetch_site == "cross-site":
            raise RejectedWriteRequest("cross-site write rejected")
        request_host = self.headers.get("Host", "").lower()
        request_hostname = urlparse(f"//{request_host}").hostname or ""
        if request_hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        } and not request_hostname.endswith(".localhost"):
            raise RejectedWriteRequest("write requests are loopback-only")
        origin = self.headers.get("Origin")
        if not origin:
            return
        origin_host = urlparse(origin).netloc.lower()
        if not origin_host or origin_host != request_host:
            raise RejectedWriteRequest("cross-origin write rejected")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 64_000:
            raise ValueError("request too large")
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body or "{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists() or path.parent != _STATIC:
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, *, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def serve(engine: LocalChatEngine, *, host: str, port: int, open_browser: bool = False) -> None:
    server = NativeChatHTTPServer((host, port), engine)
    url = f"http://{host}:{server.server_port}/"
    print(f"啾信本地试聊原型：{url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()
