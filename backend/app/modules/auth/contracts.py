from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.core.contracts import ContractModel


class LoginRequest(ContractModel):
    username: str = Field(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(ContractModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    password: str = Field(min_length=12, max_length=1024)


class IdentityResponse(ContractModel):
    identity_type: Literal["guest", "account"]
    owner_id: str | None = None
    display_name: str | None = None
