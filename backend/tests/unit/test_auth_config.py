from __future__ import annotations

import json
from itertools import chain

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.auth.credentials import hash_password, load_test_accounts, verify_password
from scripts import configure_test_accounts


def valid_account_records(password: str = "test-password-123") -> list[dict[str, str]]:
    return [
        {
            "username": f"traveler{i}",
            "owner_id": f"test-user-{i}",
            "display_name": f"旅行用户{i}",
            "password_hash": hash_password(password),
        }
        for i in range(1, 6)
    ]


def test_auth_is_unconfigured_by_default_and_settings_do_not_expose_hashes() -> None:
    settings = Settings(_env_file=None)

    assert settings.auth_test_accounts is None
    assert load_test_accounts(settings.auth_test_accounts) == ()

    records = json.dumps(valid_account_records())
    configured = Settings(_env_file=None, auth_test_accounts=records)
    assert configured.auth_test_accounts is not None
    assert "test-password-123" not in repr(configured)
    assert hash_password("test-password-123") not in repr(configured)
    assert hash_password("test-password-123") not in configured.model_dump_json()


def test_environment_configuration_is_parsed_as_a_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    records = json.dumps(valid_account_records())
    monkeypatch.setenv("APP_AUTH_TEST_ACCOUNTS", records)
    settings = Settings(_env_file=None)

    assert settings.auth_test_accounts is not None
    assert len(load_test_accounts(settings.auth_test_accounts)) == 5
    assert "pbkdf2-sha256" not in repr(settings)


def test_account_configuration_requires_five_unique_stable_accounts() -> None:
    records = valid_account_records()
    duplicate_username = [*records]
    duplicate_username[-1] = {
        **duplicate_username[-1],
        "username": duplicate_username[0]["username"],
    }
    with pytest.raises(ValueError, match="five unique"):
        load_test_accounts(json.dumps(duplicate_username))

    with pytest.raises(ValueError, match="five unique"):
        load_test_accounts(json.dumps(records[:4]))


def test_account_configuration_rejects_plaintext_passwords_and_invalid_hashes() -> None:
    records = valid_account_records()
    records[0]["password"] = "test-password-123"
    with pytest.raises(ValueError, match="password_hash"):
        load_test_accounts(json.dumps(records))

    records = valid_account_records()
    records[0]["password_hash"] = "not-a-hash"
    with pytest.raises(ValueError, match="valid accounts"):
        load_test_accounts(json.dumps(records))


def test_password_hash_verification_uses_unique_salts() -> None:
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first != second
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("wrong password", first)


@pytest.mark.parametrize("malformed", ["", "pbkdf2-sha256$1$a$b", "pbkdf2-sha256$x$a$b"])
def test_password_verification_rejects_malformed_hashes(malformed: str) -> None:
    assert verify_password("anything", malformed) is False


def test_account_configuration_validation_does_not_echo_secret() -> None:
    sentinel = "private-test-password-never-echo"
    records = valid_account_records(sentinel)
    records[0]["password"] = sentinel
    with pytest.raises(ValueError) as exc_info:
        load_test_accounts(json.dumps(records))

    assert sentinel not in str(exc_info.value)


def test_invalid_settings_field_is_rejected_without_echoing_secret() -> None:
    sentinel = "private-hash-config-never-echo"
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, auth_test_accounts=sentinel)

    assert sentinel not in str(exc_info.value)


def test_account_setup_script_hides_passwords_and_outputs_only_hashes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = chain.from_iterable(
        (f"traveler{i}", f"user-{i}", f"用户{i}") for i in range(1, 6)
    )
    monkeypatch.setattr("builtins.input", lambda: next(answers))
    monkeypatch.setattr(configure_test_accounts, "getpass", lambda _: "private-setup-password")

    assert configure_test_accounts.main() == 0
    captured = capsys.readouterr()
    assert "private-setup-password" not in captured.out
    assert "private-setup-password" not in captured.err
    records = json.loads(captured.out)
    assert len(load_test_accounts(json.dumps(records))) == 5
    assert all(record["password_hash"].startswith("pbkdf2-sha256$") for record in records)
