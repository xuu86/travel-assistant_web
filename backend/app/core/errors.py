from __future__ import annotations

from typing import Final
from uuid import UUID

from app.core.contracts import ErrorCode, PublicError

_PUBLIC_MESSAGES: Final[dict[ErrorCode, str]] = {
    ErrorCode.UNCONFIGURED: "当前能力尚未配置。",
    ErrorCode.NO_COVERAGE: "当前查询范围暂无已确认覆盖。",
    ErrorCode.RATE_LIMITED: "查询暂受额度限制，请稍后重试。",
    ErrorCode.PROVIDER_UNAVAILABLE: "外部服务暂不可用。",
    ErrorCode.POLICY_UNAVAILABLE: "当前服务权限或政策限制，暂无法查询。",
    ErrorCode.VALIDATION_ERROR: "请求参数不符合要求，请检查后重试。",
    ErrorCode.CONFIG_INVALID: "服务配置无效，请联系维护人员。",
    ErrorCode.NOT_FOUND: "未找到请求的资源。",
    ErrorCode.FORBIDDEN: "当前账号无权访问该资源。",
    ErrorCode.INTERNAL_ERROR: "服务暂时不可用，请稍后重试。",
}
_RETRYABLE_CODES: Final[frozenset[ErrorCode]] = frozenset(
    {
        ErrorCode.RATE_LIMITED,
        ErrorCode.PROVIDER_UNAVAILABLE,
        ErrorCode.INTERNAL_ERROR,
    }
)


class ServiceError(Exception):
    """An internal typed error that only exposes a stable, curated public message."""

    def __init__(self, code: ErrorCode, *, retryable: bool | None = None) -> None:
        self.code = code
        self.retryable = code in _RETRYABLE_CODES if retryable is None else retryable
        super().__init__(_PUBLIC_MESSAGES[code])


def to_public_error(error: BaseException, *, request_id: UUID | None = None) -> PublicError:
    if isinstance(error, ServiceError):
        code = error.code
        retryable = error.retryable
    else:
        code = ErrorCode.INTERNAL_ERROR
        retryable = False
    return PublicError(
        code=code,
        message=_PUBLIC_MESSAGES[code],
        retryable=retryable,
        request_id=request_id,
    )

