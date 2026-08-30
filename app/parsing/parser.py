"""HL7 v2 parsing.

Division of responsibility, and the honest current state:

* **This module owns tokenisation.** It reads the encoding characters from
  MSH-1/MSH-2 and walks segment -> field -> repetition -> component ->
  subcomponent in the correct order, decoding escapes at the leaves.
* **hl7apy is the oracle, not the engine — today.** hl7apy parses correctly, but
  its tree omits empty and space-only fields entirely, so it cannot express the
  difference between an absent field, an explicitly-nulled one, and one holding
  a space. Those mean different things in an update message, so the tree is
  built here and ``tests/test_differential.py`` asserts hl7apy agrees with it on
  every value hl7apy does report.
* **hl7apy becomes load-bearing next.** Its bundled definitions (v2.1-v2.8.2:
  field names, datatypes, table bindings) and its STRICT validation level are
  what the annotation and validation phases are built on. It is a test-time
  dependency right now and a runtime one from that point.
"""

from __future__ import annotations

from .escape import decode
from .models import (
    Component,
    Delimiters,
    Diagnostic,
    Field,
    Message,
    MessageMeta,
    Presence,
    Repetition,
    Segment,
    Severity,
    Subcomponent,
)
from .preprocess import preprocess

HEADER_SEGMENTS = ("MSH", "FHS", "BHS")

# Segments whose first two fields are the separator and the encoding characters,
# which shifts every later field by one and must never be split on delimiters.
_SPECIAL_HEADER = set(HEADER_SEGMENTS)


class NotAnHL7Message(ValueError):
    """Raised when the input is not an HL7 message at all."""


def _classify(raw: str) -> Presence:
    if raw == '""':
        return Presence.NULL
    if raw == "":
        return Presence.EMPTY
    return Presence.PRESENT


def _build_subcomponents(raw: str, delims: Delimiters) -> list[Subcomponent]:
    parts = raw.split(delims.subcomponent)
    return [
        Subcomponent(
            index=i + 1,
            raw=part,
            value=decode(part, delims) if part != '""' else "",
            presence=_classify(part),
        )
        for i, part in enumerate(parts)
    ]


def _build_components(raw: str, delims: Delimiters) -> list[Component]:
    parts = raw.split(delims.component)
    return [
        Component(index=i + 1, subs=_build_subcomponents(part, delims))
        for i, part in enumerate(parts)
    ]


def _build_field(position: int, raw: str, delims: Delimiters, *, opaque: bool) -> Field:
    """Build one field.

    ``opaque`` is for MSH-2, which *contains* the delimiter characters and so
    must be stored verbatim rather than split or escape-decoded.
    """
    if opaque:
        return Field(
            position=position,
            reps=[
                Repetition(
                    index=1,
                    components=[
                        Component(
                            index=1,
                            subs=[
                                Subcomponent(1, raw, raw, _classify(raw)),
                            ],
                        )
                    ],
                )
            ],
        )

    # Repetition is a HIGHER level than component. Splitting on '^' before '~'
    # -- as the previous implementation did -- fuses distinct repetitions and
    # invents field paths that do not exist.
    reps = raw.split(delims.repetition)
    return Field(
        position=position,
        reps=[
            Repetition(index=i + 1, components=_build_components(rep, delims))
            for i, rep in enumerate(reps)
        ],
    )


def _build_segment(raw: str, occurrence: int, delims: Delimiters) -> Segment:
    raw_fields = raw.split(delims.field)
    seg_id = raw_fields[0]
    fields: list[Field] = []

    if seg_id in _SPECIAL_HEADER:
        # MSH-1 is the field separator itself; it is not produced by splitting.
        fields.append(
            Field(
                position=1,
                reps=[
                    Repetition(
                        index=1,
                        components=[
                            Component(
                                index=1,
                                subs=[
                                    Subcomponent(
                                        1, delims.field, delims.field, Presence.PRESENT
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        )
        if len(raw_fields) > 1:
            fields.append(_build_field(2, raw_fields[1], delims, opaque=True))
        # MSH-3 onward: raw_fields[2] is MSH-3.
        for offset, raw_field in enumerate(raw_fields[2:], start=3):
            fields.append(_build_field(offset, raw_field, delims, opaque=False))
    else:
        for offset, raw_field in enumerate(raw_fields[1:], start=1):
            fields.append(_build_field(offset, raw_field, delims, opaque=False))

    return Segment(id=seg_id, occurrence=occurrence, fields=fields)


def _first_value(segment: Segment, position: int) -> str | None:
    for fld in segment.fields:
        if fld.position != position:
            continue
        if fld.reps and fld.reps[0].components and fld.reps[0].components[0].subs:
            return fld.reps[0].components[0].subs[0].value
    return None


def _raw_field(segment: Segment, position: int, delims: Delimiters) -> str | None:
    """Reassemble a field's raw text, for values like MSH-9 that have components."""
    for fld in segment.fields:
        if fld.position != position:
            continue
        return delims.repetition.join(
            delims.component.join(
                delims.subcomponent.join(sc.raw for sc in comp.subs)
                for comp in rep.components
            )
            for rep in fld.reps
        )
    return None


def parse(raw_message: str) -> Message:
    """Parse an HL7 v2 message into the canonical model.

    Never raises on a merely malformed message: analysts paste broken messages
    precisely because they are broken, so problems are reported as diagnostics
    on a best-effort tree. Only input that is not HL7 at all raises.
    """
    if raw_message is None or not raw_message.strip():
        raise NotAnHL7Message("The message is empty.")

    pre = preprocess(raw_message)
    diagnostics: list[Diagnostic] = list(pre.diagnostics)

    raw_segments = [s for s in pre.text.split("\r") if s.strip()]
    if not raw_segments:
        raise NotAnHL7Message("The message is empty.")

    first_id = raw_segments[0][:3]
    if first_id not in HEADER_SEGMENTS:
        raise NotAnHL7Message(
            f"A message must begin with MSH, FHS or BHS; this one begins with "
            f"{first_id!r}. This does not look like an HL7 v2 message."
        )

    delims = pre.delimiters
    counts: dict[str, int] = {}
    segments: list[Segment] = []
    for raw_segment in raw_segments:
        seg_id = raw_segment.split(delims.field)[0]
        if len(seg_id) != 3:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "HL7W006",
                    f"Segment identifier {seg_id!r} is not three characters.",
                    path=seg_id,
                )
            )
        occurrence = counts.get(seg_id, 0)
        counts[seg_id] = occurrence + 1
        segments.append(_build_segment(raw_segment, occurrence, delims))

    header = segments[0]
    meta = MessageMeta(
        version=pre.version,
        message_type=_raw_field(header, 9, delims),
        control_id=_first_value(header, 10),
        delimiters=delims,
        segment_terminator=pre.segment_terminator,
        framing=pre.framing,
        segment_count=len(segments),
    )

    return Message(meta=meta, segments=segments, diagnostics=diagnostics)


def serialize(message: Message) -> str:
    """Rebuild the ER7 text from the model. Round-trips a parsed message."""
    delims = message.meta.delimiters
    lines: list[str] = []
    for segment in message.segments:
        parts = [segment.id]
        positions = [f.position for f in segment.fields]
        start = 3 if segment.id in _SPECIAL_HEADER else 1
        highest = max(positions) if positions else 0
        by_position = {f.position: f for f in segment.fields}

        if segment.id in _SPECIAL_HEADER:
            enc = by_position.get(2)
            parts.append(enc.reps[0].components[0].subs[0].raw if enc else delims.encoding_characters)

        for pos in range(start, highest + 1):
            fld = by_position.get(pos)
            if fld is None:
                parts.append("")
                continue
            parts.append(
                delims.repetition.join(
                    delims.component.join(
                        delims.subcomponent.join(sc.raw for sc in comp.subs)
                        for comp in rep.components
                    )
                    for rep in fld.reps
                )
            )
        lines.append(delims.field.join(parts))
    return "\r".join(lines)
