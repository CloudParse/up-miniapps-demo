"""Verification of the user tokens issued by the Up Hub.

The Hub signs a short-lived "scoped" token (ES256) per user and per mini-app.
The shell attaches it to every request the mini-app makes. This backend only
needs the Hub's PUBLIC key: it can verify tokens offline and can never forge one.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import jwt

from app.core.config import Config
from app.core.errors import UnauthorizedError

logger = logging.getLogger(__name__)

SIGNING_ALGORITHM = "ES256"
# Scope the Hub puts in a token only for a Hub admin who asked for it
# (`POST /applications/{uuid}/token` with `{"scopes": ["profile:miniapp:admin"]}`).
ADMIN_SCOPE = "profile:miniapp:admin"
# Placeholder audience the shell's "Vite Dev" hot-reload entry mints tokens for.
# Accepted in development only.
DEV_SHELL_APP_UUID = "99999999-9999-9999-9999-999999999999"


@dataclass(frozen=True)
class AuthenticatedUser:
    user_uuid: UUID
    scopes: tuple[str, ...]

    @property
    def is_admin(self) -> bool:
        return ADMIN_SCOPE in self.scopes


class TokenVerifier:
    def __init__(self, public_key: str, audiences: list[str]) -> None:
        self._public_key = public_key
        self._audiences = audiences

    def verify(self, token: str) -> AuthenticatedUser:
        try:
            claims = jwt.decode(
                token,
                self._public_key,
                algorithms=[SIGNING_ALGORITHM],  # never trust the token's own `alg`
                audience=self._audiences,  # blocks replaying another app's token
                options={"require": ["exp", "sub", "aud"]},
            )
            scopes = claims.get("scp", [])
            if not isinstance(scopes, list) or not all(
                isinstance(scope, str) for scope in scopes
            ):
                raise ValueError("scp must be a list of strings")
            return AuthenticatedUser(
                user_uuid=UUID(claims["sub"]), scopes=tuple(scopes)
            )
        except (jwt.PyJWTError, ValueError) as error:
            # Log the reason, never the token itself.
            logger.warning("token rejected", extra={"reason": type(error).__name__})
            raise UnauthorizedError("Invalid or expired token.") from error


def build_token_verifier(config: Config) -> TokenVerifier | None:
    """Return a verifier, or None while the mini-app is not registered yet."""
    if not config.hub.app_uuid:
        logger.warning("hub.app_uuid is empty: authenticated routes are disabled")
        return None
    audiences = [config.hub.app_uuid]
    if config.is_development:
        audiences.append(DEV_SHELL_APP_UUID)
    return TokenVerifier(_read_public_key(config.hub.public_key_path), audiences)


def _read_public_key(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(
            f"Hub public key not found at {path}. Put the Hub's public key there "
            "or set HUB_PUBLIC_KEY_PATH."
        )
    return path.read_text(encoding="utf-8")
