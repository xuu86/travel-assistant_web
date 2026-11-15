from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass, field

from pydantic import SecretStr

_HASH_PREFIX = "pbkdf2-sha256"
_DEFAULT_ITERATIONS = 310_000
_MIN_ITERATIONS = 100_000
_MAX_ITERATIONS = 2_000_000
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,31}$")
_OWNER_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


@dataclass(frozen=True)
class TestAccount:
    username: str
    owner_id: str
    display_name: str
    password_hash: str = field(repr=False)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, *, iterations: int = _DEFAULT_ITERATIONS) -> str:
    if not isinstance(password, str) or not password or len(password) > 1024:
        raise ValueError("Password must contain 1 to 1024 characters.")
    if not _MIN_ITERATIONS <= iterations <= _MAX_ITERATIONS:
        raise ValueError("Password hash parameters are invalid.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_HASH_PREFIX}${iterations}${_encode(salt)}${_encode(digest)}"


def _parse_hash(encoded: str) -> tuple[int, bytes, bytes] | None:
    parts = encoded.split("$")
    if len(parts) != 4 or parts[0] != _HASH_PREFIX:
        return None
    try:
        iterations = int(parts[1])
        salt = _decode(parts[2])
        expected = _decode(parts[3])
    except (ValueError, TypeError):
        return None
    if (
        not _MIN_ITERATIONS <= iterations <= _MAX_ITERATIONS
        or len(salt) < 16
        or len(expected) != 32
    ):
        return None
    return iterations, salt, expected


def verify_password(password: str, encoded: str) -> bool:
    parsed = _parse_hash(encoded)
    if not isinstance(password, str) or not password or len(password) > 1024 or parsed is None:
        return False
    iterations, salt, expected = parsed
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def load_test_accounts(value: SecretStr | str | None) -> tuple[TestAccount, ...]:
    if value is None:
        return ()
    raw = value.get_secret_value() if isinstance(value, SecretStr) else value
    try:
        decoded = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Authentication test-account configuration is invalid.") from exc
    if not isinstance(decoded, list) or len(decoded) != 5:
        raise ValueError("Authentication configuration must contain five unique test accounts.")

    accounts: list[TestAccount] = []
    usernames: set[str] = set()
    owner_ids: set[str] = set()
    for item in decoded:
        if not isinstance(item, dict) or set(item) != {
            "username", "owner_id", "display_name", "password_hash"
        }:
            raise ValueError("Each test account must contain a password_hash and public identity.")
        username = item["username"]
        owner_id = item["owner_id"]
        display_name = item["display_name"]
        encoded = item["password_hash"]
        if (
            not isinstance(username, str)
            or not _USERNAME_RE.fullmatch(username)
            or username != username.strip()
            or username.casefold() in usernames
            or not isinstance(owner_id, str)
            or not _OWNER_ID_RE.fullmatch(owner_id)
            or owner_id in owner_ids
            or not isinstance(display_name, str)
            or not display_name.strip()
            or len(display_name) > 80
            or not isinstance(encoded, str)
            or _parse_hash(encoded) is None
        ):
            raise ValueError(
                "Authentication configuration must contain five unique valid accounts."
            )
        usernames.add(username.casefold())
        owner_ids.add(owner_id)
        accounts.append(TestAccount(username, owner_id, display_name, encoded))
    return tuple(accounts)
