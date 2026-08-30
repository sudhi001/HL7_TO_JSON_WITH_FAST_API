"""Request and response models for the v2 API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

MAX_MESSAGE_BYTES = 1_000_000


class Shape(str, Enum):
    CANONICAL = "canonical"
    SIMPLE = "simple"


class ParseRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MESSAGE_BYTES,
        description="The raw HL7 v2 message.",
        json_schema_extra={
            "example": "MSH|^~\\&|SEND|FAC|RECV|RFAC|20240101120000||ADT^A01|MSG1|P|2.5.1\rPID|1||MRN1||DOE^JOHN||19800101|M"
        },
    )


class ErrorResponse(BaseModel):
    error: str
    detail: str


class DiagnosticModel(BaseModel):
    severity: str
    code: str
    message: str
    path: str | None = None


class ParseResponse(BaseModel):
    """Documented for OpenAPI. Handlers return plain dicts so responses are not
    revalidated on the hot path."""

    schemaVersion: int
    meta: dict[str, Any]
    segments: list[dict[str, Any]]
    diagnostics: list[DiagnosticModel]
