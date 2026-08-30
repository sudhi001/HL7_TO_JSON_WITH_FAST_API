"""Value objects returned by the definition store."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldDef:
    segment_id: str
    position: int
    name: str | None
    datatype: str | None
    optionality: str | None      # 'R' | 'O' | 'C' | 'B'
    repeatable: bool
    max_repeat: str | None       # '*' when unbounded
    length: int | None
    table_id: str | None
    description: str | None

    @property
    def required(self) -> bool:
        return self.optionality == "R"


@dataclass(frozen=True)
class SegmentDef:
    id: str
    long_name: str | None
    description: str | None


@dataclass(frozen=True)
class ComponentDef:
    datatype_id: str
    position: int
    name: str | None
    datatype: str | None
    optionality: str | None
    length: int | None
    table_id: str | None


@dataclass(frozen=True)
class DataTypeDef:
    id: str
    name: str | None
    description: str | None


@dataclass(frozen=True)
class CodeTableDef:
    id: str
    name: str | None
