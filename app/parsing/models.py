"""Data model for a parsed HL7 v2 message.

The shape here is deliberately list-based. The previous model was a flat
``dict[str, str]`` keyed by dotted path, which cannot represent an HL7 message:
repeated segments collide on the segment key, and ``PID.3.2`` is ambiguous
between "second component of PID-3" and "second repetition of PID-3".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Presence(str, Enum):
    """Why a value is not there, which in HL7 is as meaningful as the value.

    ``EMPTY`` (``||``) means "no information supplied — leave any existing value
    alone". ``NULL`` (``|""|``) means "delete the existing value". In an update
    message these are opposites, so collapsing them loses clinical meaning.
    """

    PRESENT = "present"
    EMPTY = "empty"
    NULL = "null"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Delimiters:
    """Encoding characters, read from MSH-1 and MSH-2 rather than assumed."""

    field: str = "|"
    component: str = "^"
    repetition: str = "~"
    escape: str = "\\"
    subcomponent: str = "&"

    @property
    def encoding_characters(self) -> str:
        """The MSH-2 value: component, repetition, escape, subcomponent."""
        return f"{self.component}{self.repetition}{self.escape}{self.subcomponent}"


@dataclass
class Diagnostic:
    severity: Severity
    code: str
    message: str
    path: str | None = None


@dataclass
class Subcomponent:
    index: int
    raw: str
    value: str
    presence: Presence


@dataclass
class Component:
    index: int
    subs: list[Subcomponent] = field(default_factory=list)


@dataclass
class Repetition:
    index: int
    components: list[Component] = field(default_factory=list)


@dataclass
class Field:
    position: int
    reps: list[Repetition] = field(default_factory=list)


@dataclass
class Segment:
    id: str
    occurrence: int
    fields: list[Field] = field(default_factory=list)


@dataclass
class MessageMeta:
    #: The version used for lookups -- resolved to one the definition store has.
    version: str | None = None
    #: What MSH-12 actually said, when that differs from `version`.
    declared_version: str | None = None
    message_type: str | None = None
    control_id: str | None = None
    delimiters: Delimiters = field(default_factory=Delimiters)
    segment_terminator: str = "\r"
    framing: str = "bare"
    segment_count: int = 0


@dataclass
class Message:
    meta: MessageMeta = field(default_factory=MessageMeta)
    segments: list[Segment] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
