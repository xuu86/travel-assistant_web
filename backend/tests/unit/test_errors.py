from uuid import UUID

from app.core.contracts import ErrorCode
from app.core.errors import ServiceError, to_public_error


def test_service_error_exposes_only_the_declared_public_message() -> None:
    error = ServiceError(ErrorCode.PROVIDER_UNAVAILABLE)

    public = to_public_error(
        error,
        request_id=UUID("9d9b4bcb-07f2-484b-8e42-13692d3c5cab"),
    )

    assert public.code == ErrorCode.PROVIDER_UNAVAILABLE
    assert public.message == "外部服务暂不可用。"
    assert public.retryable is True
    assert public.request_id == UUID("9d9b4bcb-07f2-484b-8e42-13692d3c5cab")


def test_unexpected_error_is_mapped_without_leaking_internal_text() -> None:
    error = RuntimeError("secret=do-not-return; path=C:\\private\\file.pdf")

    public = to_public_error(error)

    assert public.code == ErrorCode.INTERNAL_ERROR
    assert "secret" not in public.message
    assert "private" not in public.message
    assert public.retryable is False


def test_public_error_codes_are_stable_and_messages_are_bounded() -> None:
    error = ServiceError(ErrorCode.RATE_LIMITED, retryable=True)

    public = to_public_error(error)

    assert public.code.value == "RATE_LIMITED"
    assert public.message == "查询暂受额度限制，请稍后重试。"
    assert public.retryable is True
    assert len(public.message) <= 240
