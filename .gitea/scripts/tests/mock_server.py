"""A tiny recording HTTP server for the CI script tests."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable

Responder = Callable[..., tuple]  # (method, path, headers, body) -> (status, payload) or (status, payload, extra headers)


class MockServer:
    def __init__(self, responder: Responder) -> None:
        self.calls: list[dict[str, Any]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                headers = {key.lower(): value for key, value in self.headers.items()}
                outer.calls.append({"method": self.command, "path": self.path, "headers": headers, "body": body})
                answer = responder(self.command, self.path, headers, body)
                status, payload = answer[0], answer[1]
                extra = answer[2] if len(answer) > 2 else {}
                data = json.dumps(payload).encode() if payload is not None else b""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for key, value in extra.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = _handle

            def log_message(self, *args: Any) -> None:  # silence
                return

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "MockServer":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
