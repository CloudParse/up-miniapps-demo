"""Small HTTP helpers for the CI scripts (standard library only). Secrets travel in headers and bodies, never in argv."""

import json
import urllib.error
import urllib.request
import uuid
from typing import Any

TIMEOUT_SECONDS = 120


class ApiError(RuntimeError):
    """An HTTP call failed: status 0 means the server could not be reached."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}" if status else message)
        self.status = status


def multipart(fields: dict[str, str], file_field: str, filename: str, content: bytes) -> tuple[bytes, str]:
    """Encode a multipart/form-data body; returns the body and its Content-Type."""
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + content
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _error_message(raw: bytes, reason: str) -> str:
    try:
        body = json.loads(raw)
    except ValueError:
        return reason
    if isinstance(body, dict):
        return str(body.get("message") or body.get("error") or reason)
    return reason


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = TIMEOUT_SECONDS,
) -> Any:
    """Send a request and return the decoded JSON answer (None for an empty body)."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
    except urllib.error.HTTPError as error:
        with error:
            raise ApiError(error.code, _error_message(error.read(), error.reason)) from error
    except urllib.error.URLError as error:
        raise ApiError(0, f"cannot reach {url}: {error.reason}") from error
    return json.loads(raw) if raw else None


def request_json(method: str, url: str, payload: Any = None, *, token: str | None = None, basic: str | None = None) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if basic:
        headers["Authorization"] = f"Basic {basic}"
    return request(method, url, headers=headers, body=data)
