"""Bind HL7 definitions onto a parsed message.

This is what turns a converter into a learning tool: the raw output says
``PID.8: "M"``; the annotated output says *Administrative Sex* = **Male**, from
HL7 table 0001, an optional IS field of length 1.

Annotation is always additive and always optional. If the definition store is
missing, every lookup returns ``None`` and the message still parses -- the
structure is never dependent on the definitions.
"""

from __future__ import annotations

from typing import Any

from .defs import store
from .parsing.models import Message, Presence, Segment

# Fields whose value is a delimiter or the delimiter set itself; decoding or
# looking them up in a table is meaningless.
_LITERAL_HEADER_FIELDS = {("MSH", 1), ("MSH", 2), ("FHS", 1), ("FHS", 2), ("BHS", 1), ("BHS", 2)}


def _table_id(field_def, component_def, component_index: int) -> str | None:
    """Which code table applies to this value.

    A component's own binding wins when it has one. Otherwise the *field's*
    binding applies to component 1: coded composites such as CE and CWE put the
    code in component 1 ("Identifier") and carry the table on the field, so
    PID-16 binds table 2 even though CE.1 declares no table of its own. Without
    this fallback every CE/CWE field silently fails to decode.
    """
    if component_def is not None and component_def.table_id:
        return component_def.table_id
    if component_index == 1 and field_def is not None:
        return field_def.table_id
    return None


def _annotate_component(
    version: str,
    component,
    component_def,
    field_def,
) -> dict[str, Any]:
    out: dict[str, Any] = {"index": component.index}

    if component_def is not None:
        out["name"] = component_def.name
        out["dataType"] = component_def.datatype

    subs = []
    for sub in component.subs:
        entry: dict[str, Any] = {
            "index": sub.index,
            "value": sub.value,
            "presence": sub.presence.value,
        }
        # Only decode a real value, and only for the first subcomponent -- a
        # table binding applies to the component's value, not to each part of a
        # composite identifier.
        if sub.presence is Presence.PRESENT and sub.index == 1:
            table_id = _table_id(field_def, component_def, component.index)
            if table_id:
                meaning = store.code_meaning(version, table_id, sub.value)
                if meaning:
                    entry["meaning"] = meaning
                    entry["table"] = table_id
                # A value absent from its table is NOT flagged as an error here.
                # HL7 tables come in two kinds: HL7-defined, where an unlisted
                # code really is wrong, and user-defined, where sites legitimately
                # use their own codes (Race and Marital Status are common cases).
                # This dataset does not record which kind a table is, so flagging
                # would produce false positives on perfectly valid messages. The
                # Caristix data carries `tableType`, and the check becomes safe
                # once that enrichment lands.
        subs.append(entry)

    out["subs"] = subs
    return out


def annotate_segment(version: str, segment: Segment) -> dict[str, Any]:
    segment_def = store.segment_def(version, segment.id)
    out: dict[str, Any] = {
        "id": segment.id,
        "occurrence": segment.occurrence,
        "name": segment_def.long_name if segment_def else None,
        "known": segment_def is not None,
        "fields": [],
    }

    for field in segment.fields:
        field_def = store.field_def(version, segment.id, field.position)
        literal = (segment.id, field.position) in _LITERAL_HEADER_FIELDS

        entry: dict[str, Any] = {
            "path": f"{segment.id}.{field.position}",
            "pos": field.position,
        }
        if field_def is not None:
            entry.update(
                {
                    "name": field_def.name,
                    "dataType": field_def.datatype,
                    "optionality": field_def.optionality,
                    "required": field_def.required,
                    "repeatable": field_def.repeatable,
                    "maxRepeat": field_def.max_repeat,
                    "length": field_def.length,
                    "table": field_def.table_id,
                }
            )

        # Component names come from the field's datatype, e.g. PID-5 is an XPN
        # so component 1 is 'Family Name'.
        components = ()
        if field_def is not None and field_def.datatype and not literal:
            components = store.datatype_components(version, field_def.datatype)

        reps = []
        for rep in field.reps:
            reps.append(
                {
                    "index": rep.index,
                    "components": [
                        _annotate_component(
                            version,
                            component,
                            components[component.index - 1]
                            if component.index - 1 < len(components) and not literal
                            else None,
                            None if literal else field_def,
                        )
                        for component in rep.components
                    ],
                }
            )
        entry["reps"] = reps
        out["fields"].append(entry)

    return out


def annotate(message: Message) -> dict[str, Any]:
    """Annotate a parsed message, degrading to structure-only when unavailable."""
    version = store.resolve_version(message.meta.version)
    if version is None:
        return {
            "available": False,
            "reason": "The HL7 definition store is not present. Run "
            "`python tools/build_defs_db.py` to enable field names and code decoding.",
            "segments": [],
        }
    return {
        "available": True,
        "definitionVersion": version,
        "requestedVersion": message.meta.version,
        "segments": [annotate_segment(version, segment) for segment in message.segments],
    }
