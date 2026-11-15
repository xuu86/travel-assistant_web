from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass

from app.core.config import Settings
from app.core.contracts import ErrorCode
from app.core.errors import ServiceError
from app.modules.auth.credentials import load_test_accounts, verify_password

SESSION_TTL_SECONDS = 12 * 60 * 60
_FAILED_WINDOW_SECONDS = 15 * 60
_MAX_FAILED_ATTEMPTS = 5


@dataclass(frozen=True)
class SessionIdentity:
    owner_id: str
    display_name: str


class AuthService:
    def __init__(self, settings: Settings) -> None:
        accounts = load_test_accounts(settings.auth_test_accounts)
        self._accounts = {account.username.casefold(): account for account in accounts}
        self._sessions: dict[str, tuple[SessionIdentity, float]] = {}
        self._failures: dict[str, list[float]] = {}
        self._limiter_key = secrets.token_bytes(32)
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self._accounts)

    def authenticate(
        self, username: str, password: str, client_host: str
    ) -> tuple[str, SessionIdentity]:
        normalized = username.strip().casefold()
        limit_key = hmac.new(
            self._limiter_key,
            f"{client_host}\0{normalized}".encode(),
            hashlib.sha256,
        ).hexdigest()
        now = time.monotonic()
        with self._lock:
            attempts = [
                stamp
                for stamp in self._failures.get(limit_key, [])
                if now - stamp < _FAILED_WINDOW_SECONDS
            ]
            if len(self._failures) > 4096:
                self._failures = {
                    key: [stamp for stamp in stamps if now - stamp < _FAILED_WINDOW_SECONDS]
                    for key, stamps in self._failures.items()
                }
                self._failures = {key: stamps for key, stamps in self._failures.items() if stamps}
                attempts = self._failures.get(limit_key, attempts)
            self._failures[limit_key] = attempts
            if len(attempts) >= _MAX_FAILED_ATTEMPTS:
                raise ServiceError(ErrorCode.RATE_LIMITED)

        account = self._accounts.get(normalized)
        valid = verify_password(password, account.password_hash) if account else False
        if not valid or account is None:
            with self._lock:
                self._failures.setdefault(limit_key, []).append(now)
            raise ServiceError(ErrorCode.UNAUTHORIZED)

        with self._lock:
            self._failures.pop(limit_key, None)
            self._purge_expired_sessions(now)
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
            identity = SessionIdentity(account.owner_id, account.display_name)
            self._sessions[token_hash] = (identity, now + SESSION_TTL_SECONDS)
        return token, identity

    def identify(self, token: str | None) -> SessionIdentity | None:
        if not token or len(token) > 256:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = time.monotonic()
        with self._lock:
            record = self._sessions.get(token_hash)
            if record is None:
                return None
            identity, expires_at = record
            if expires_at <= now:
                self._sessions.pop(token_hash, None)
                return None
            return identity

    def logout(self, token: str | None) -> None:
        if not token or len(token) > 256:
            return
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._lock:
            self._sessions.pop(token_hash, None)

    def _purge_expired_sessions(self, now: float) -> None:
        expired = [key for key, (_, deadline) in self._sessions.items() if deadline <= now]
        for key in expired:
            self._sessions.pop(key, None)
