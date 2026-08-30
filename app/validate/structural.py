"""Segment- and field-level conformance: presence, cardinality, length."""

from __future__ import annotations

from ..defs import store
from ..parsing.models import Diagnostic, Message, Presence, Severity
from .paths import field_path, occurrence_counts, segment_path

# MSH-1 and MSH-2 are the delimiters themselves; they are synthesised during
# parsing and are always present by construction.
_SYNTHESISED = {("MSH", 1), ("MSH", 2), ("FHS", 1), ("FHS", 2), ("BHS", 1), ("BHS", 2)}


def _first_sub(field):
    if field.reps and field.reps[0].components and field.reps[0].components[0].subs:
        return field.reps[0].components[0].subs[0]
    return None


def _encoded_length(repetition) -> int:
    """Length of one repetition as it appears on the wire.

    The separators count toward an HL7 length limit, so they have to be counted:
    a component separator between each component, and a subcomponent separator
    between each subcomponent. Summing the values alone under-reports, which
    silently lets over-long fields through.
    """
    total = 0
    for component in repetition.components:
        total += sum(len(sub.raw) for sub in component.subs)
        total += max(len(component.subs) - 1, 0)
    return total + max(len(repetition.components) - 1, 0)


def _has_content(field) -> bool:
    for rep in field.reps:
        for component in rep.components:
            for sub in component.subs:
                if sub.presence is Presence.PRESENT and sub.value != "":
                    return True
    return False


def check(message: Message) -> list[Diagnostic]:
    version = store.resolve_version(message.meta.version)
    if version is None:
        return []

    found: list[Diagnostic] = []
    counts = occurrence_counts(message)

    for segment in message.segments:
        definition = store.segment_def(version, segment.id)

        if definition is None:
            # Z-segments are the sanctioned way to carry local data -- reporting
            # them as a problem would be wrong.
            if segment.id.startswith("Z"):
                found.append(
                    Diagnostic(
                        Severity.INFO, "HL7I010",
                        f"{segment.id} is a Z-segment (locally defined). No standard "
                        "definition exists, so its fields are not named.",
                        path=segment_path(segment, counts[segment.id]),
                    )
                )
            else:
                found.append(
                    Diagnostic(
                        Severity.WARNING, "HL7W010",
                        f"{segment.id} is not a known segment in HL7 {version}.",
                        path=segment_path(segment, counts[segment.id]),
                    )
                )
            continue

        field_defs = store.segment_fields(version, segment.id)
        highest = len(field_defs)
        present = {f.position: f for f in segment.fields}

        for field_def in field_defs:
            key = (segment.id, field_def.position)
            path = field_path(segment, counts[segment.id], field_def.position)
            field = present.get(field_def.position)

            missing_required = (
                field_def.required
                and key not in _SYNTHESISED
                and (field is None or not _has_content(field))
            )
            if missing_required:
                found.append(
                    Diagnostic(
                        Severity.ERROR, "HL7E010",
                        f"{path} ({field_def.name}) is required but empty.",
                        path=path,
                    )
                )

            if field is None:
                continue

            if len(field.reps) > 1 and not field_def.repeatable:
                found.append(
                    Diagnostic(
                        Severity.ERROR, "HL7E011",
                        f"{path} ({field_def.name}) repeats {len(field.reps)} times "
                        "but the specification does not allow it to repeat.",
                        path=path,
                    )
                )

            if field_def.length:
                for rep in field.reps:
                    total = _encoded_length(rep)
                    if total > field_def.length:
                        found.append(
                            Diagnostic(
                                Severity.WARNING, "HL7W011",
                                f"{path} ({field_def.name}) is {total} characters; the "
                                f"specification allows {field_def.length}.",
                                path=path,
                            )
                        )
                        break

        for position in sorted(present):
            if position > highest:
                found.append(
                    Diagnostic(
                        Severity.WARNING, "HL7W012",
                        f"{field_path(segment, counts[segment.id], position)} is beyond the "
                        f"{highest} fields "
                        f"defined for {segment.id} in HL7 {version}.",
                        path=field_path(segment, counts[segment.id], position),
                    )
                )

    return found
