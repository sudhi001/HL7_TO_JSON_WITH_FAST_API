"""Primitive datatype checks.

Malformed dates are among the most common real interface defects and among the
most damaging: ``20240230`` looks fine until something downstream tries to store
it. Only unambiguous primitives are checked; free-text types are left alone.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..defs import store
from ..parsing.models import Diagnostic, Message, Presence, Severity
from .paths import field_path, occurrence_counts

# YYYY[MM[DD]] then optional time, then optional +/-HHMM offset.
_TS = re.compile(r"^(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\.\d{1,4})?([+-]\d{4})?$")
_TM = re.compile(r"^(\d{2})(\d{2})?(\d{2})?(\.\d{1,4})?([+-]\d{4})?$")
_NUMERIC = re.compile(r"^[+-]?\d+(\.\d+)?$")


def _valid_calendar_date(year: str, month: str | None, day: str | None) -> bool:
    if month is None:
        return True
    try:
        datetime(int(year), int(month), int(day) if day else 1)
    except ValueError:
        return False
    return True


def _check_value(datatype: str, value: str, path: str, name: str | None) -> Diagnostic | None:
    label = f"{path}" + (f" ({name})" if name else "")

    if datatype in ("DT", "TS", "DTM"):
        match = _TS.match(value)
        if not match:
            return Diagnostic(
                Severity.ERROR, "HL7E020",
                f"{label} is a {datatype} but {value!r} is not a valid HL7 "
                "date/time (expected YYYY[MM[DD[HHMM[SS]]]]).",
                path=path,
            )
        year, month, day = match.group(1), match.group(2), match.group(3)
        if not _valid_calendar_date(year, month, day):
            return Diagnostic(
                Severity.ERROR, "HL7E021",
                f"{label} is {value!r}, which is not a real date.",
                path=path,
            )
        hour, minute, second = match.group(4), match.group(5), match.group(6)
        for part, limit, unit in ((hour, 23, "hour"), (minute, 59, "minute"), (second, 59, "second")):
            if part is not None and int(part) > limit:
                return Diagnostic(
                    Severity.ERROR, "HL7E022",
                    f"{label} is {value!r}: {int(part)} is not a valid {unit}.",
                    path=path,
                )

    elif datatype == "TM":
        if not _TM.match(value):
            return Diagnostic(
                Severity.ERROR, "HL7E023",
                f"{label} is a TM but {value!r} is not a valid HL7 time.",
                path=path,
            )

    elif datatype == "NM":
        if not _NUMERIC.match(value):
            return Diagnostic(
                Severity.ERROR, "HL7E024",
                f"{label} is numeric (NM) but {value!r} is not a number.",
                path=path,
            )

    elif datatype == "SI":
        if not value.isdigit():
            return Diagnostic(
                Severity.ERROR, "HL7E025",
                f"{label} is a sequence ID (SI) but {value!r} is not a "
                "non-negative integer.",
                path=path,
            )

    return None


def check(message: Message) -> list[Diagnostic]:
    version = store.resolve_version(message.meta.version)
    if version is None:
        return []

    found: list[Diagnostic] = []
    counts = occurrence_counts(message)
    for segment in message.segments:
        for field in segment.fields:
            field_def = store.field_def(version, segment.id, field.position)
            if field_def is None or not field_def.datatype:
                continue

            components = store.datatype_components(version, field_def.datatype)

            for rep in field.reps:
                for component in rep.components:
                    component_def = (
                        components[component.index - 1]
                        if component.index - 1 < len(components)
                        else None
                    )
                    # A field whose datatype is primitive has no components; the
                    # field's own datatype applies to the single value.
                    datatype = (
                        component_def.datatype if component_def is not None
                        else (field_def.datatype if not components else None)
                    )
                    if not datatype:
                        continue

                    for sub in component.subs:
                        if sub.presence is not Presence.PRESENT or sub.value == "":
                            continue
                        # Only the first subcomponent carries the component's own
                        # datatype; deeper parts belong to a sub-composite.
                        if sub.index != 1:
                            continue
                        path = field_path(
                            segment, counts[segment.id], field.position,
                            repetition=rep.index if len(field.reps) > 1 else None,
                            component=component.index if components else None,
                        )
                        diagnostic = _check_value(
                            datatype, sub.value, path,
                            component_def.name if component_def else field_def.name,
                        )
                        if diagnostic is not None:
                            found.append(diagnostic)
    return found
