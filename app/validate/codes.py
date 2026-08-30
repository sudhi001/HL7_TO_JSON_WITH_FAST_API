"""Coded-value checks.

Deliberately minimal, and here is why.

HL7 code tables come in two kinds. **HL7-defined** tables are closed: a value
not in the table really is wrong. **User-defined** tables are suggestions, and
sites legitimately use their own codes -- Race, Religion and Marital Status are
the usual examples. The hl7-dictionary dataset does not record which kind a
table is, so flagging every unlisted value would fire on perfectly valid
messages and teach users to ignore the validator.

So unlisted values are reported at ``info`` and worded as an observation, not a
defect. The Caristix dataset carries ``tableType``; once that enrichment lands,
HL7-defined tables can be promoted to ``error`` and this becomes a real check.
"""

from __future__ import annotations

from ..defs import store
from ..parsing.models import Diagnostic, Message, Presence, Severity
from .paths import field_path, occurrence_counts

# Tables that are HL7-defined and closed in every version that has them. Kept
# deliberately short: each entry is one we can defend, not a guess.
CLOSED_TABLES = {
    "1": "Administrative Sex",
    "103": "Processing ID",
    "104": "Version ID",
    "136": "Yes/no indicator",
    "76": "Message type",
}


def check(message: Message) -> list[Diagnostic]:
    version = store.resolve_version(message.meta.version)
    if version is None:
        return []

    found: list[Diagnostic] = []
    counts = occurrence_counts(message)
    for segment in message.segments:
        for field in segment.fields:
            field_def = store.field_def(version, segment.id, field.position)
            if field_def is None:
                continue

            components = store.datatype_components(version, field_def.datatype or "")

            for rep in field.reps:
                for component in rep.components:
                    component_def = (
                        components[component.index - 1]
                        if component.index - 1 < len(components)
                        else None
                    )
                    table_id = (
                        component_def.table_id
                        if component_def is not None and component_def.table_id
                        else (field_def.table_id if component.index == 1 else None)
                    )
                    if not table_id:
                        continue

                    for sub in component.subs:
                        if sub.presence is not Presence.PRESENT or sub.value == "" or sub.index != 1:
                            continue
                        if store.code_meaning(version, table_id, sub.value) is not None:
                            continue

                        definition, entries = store.code_table(version, table_id)
                        if not entries:
                            continue

                        path = field_path(
                            segment, counts[segment.id], field.position,
                            repetition=rep.index if len(field.reps) > 1 else None,
                            component=component.index if components else None,
                        )
                        table_name = definition.name if definition else table_id
                        label = field_def.name or path

                        if table_id in CLOSED_TABLES:
                            allowed = ", ".join(v for v, _ in entries[:12])
                            found.append(
                                Diagnostic(
                                    Severity.ERROR, "HL7E030",
                                    f"{path} ({label}) is {sub.value!r}, which is not in "
                                    f"HL7 table {table_id} ({table_name}). Allowed: {allowed}.",
                                    path=path,
                                )
                            )
                        else:
                            found.append(
                                Diagnostic(
                                    Severity.INFO, "HL7I030",
                                    f"{path} ({label}) is {sub.value!r}, which is not listed "
                                    f"in table {table_id} ({table_name}). This is normal for "
                                    "a site-defined table.",
                                    path=path,
                                )
                            )
    return found
