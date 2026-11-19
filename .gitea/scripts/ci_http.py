"""Small HTTP helpers for the CI scripts (standard library only).

Secrets travel in headers and bodies, never in argv. Only https is used, and a redirect is never followed: a redirect
would carry the Authorization header to another address. A development cluster without TLS sets UP_CI_ALLOW_HTTP=true.
"""

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from typing import Any
from urllib.parse import urlsplit

TIMEOUT_SECONDS = 120
MAX_ERROR_TEXT = 200
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")


class ApiError(RuntimeError):
    """An HTTP call failed: status 0 means the server could not be reached or the call was refused locally."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}" if status else message)
        self.status = status


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def check_url(url: str) -> None:
    """Refuse anything but https (http only with UP_CI_ALLOW_HTTP=true, for a local cluster)."""
    scheme = urlsplit(url).scheme
    if scheme == "https" or (scheme == "http" and os.environ.get("UP_CI_ALLOW_HTTP") == "true"):
        return
    raise ApiError(0, "refusing a non-https URL (set UP_CI_ALLOW_HTTP=true only on a local development cluster)")


def multipart(fields: dict[str, str], file_field: str, filename: str, content: bytes) -> tuple[bytes, str]:
    """Encode a multipart/form-data body; names, filename and field values are checked, never escaped."""
    for name in (*fields, file_field, filename):
        if not _SAFE_NAME.match(name):
            raise ApiError(0, f"refusing the multipart name {name!r}: letters, digits, '.', '_' and '-' only")
    for value in fields.values():
        if _CONTROL.search(value):
            raise ApiError(0, "refusing a multipart value with a control character")
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
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
    """The server's message, without control characters and cut short: it ends up in a public CI log."""
    message = reason
    try:
        body = json.loads(raw)
    except ValueError:
        body = None
    if isinstance(body, dict):
        message = str(body.get("message") or body.get("error") or reason)
    return _CONTROL.sub(" ", message)[:MAX_ERROR_TEXT]


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = TIMEOUT_SECONDS,
) -> Any:
    """Send a request and return the decoded JSON answer (None for an empty body)."""
    check_url(url)
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})  # noqa: S310
    try:
        with _OPENER.open(req, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        with error:
            if 300 <= error.code < 400:
                raise ApiError(error.code, "the server redirected the request; redirects are never followed") from error
            raise ApiError(error.code, _error_message(error.read(), error.reason)) from error
    except urllib.error.URLError as error:
        raise ApiError(0, f"cannot reach {urlsplit(url).netloc}: {error.reason}") from error
    try:
        return json.loads(raw) if raw else None
    except ValueError as error:
        raise ApiError(0, "the server answered with something that is not JSON") from error


def request_json(method: str, url: str, payload: Any = None, *, token: str | None = None) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return request(method, url, headers=headers, body=data)
