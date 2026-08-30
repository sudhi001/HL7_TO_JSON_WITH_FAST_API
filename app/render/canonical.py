"""Lossless JSON projection of a parsed message. This is the API contract."""

from __future__ import annotations

from typing import Any

from ..parsing.models import Message, Presence

SCHEMA_VERSION = 2


def _subcomponent(sub) -> dict[str, Any]:
    out: dict[str, Any] = {"v": sub.value, "p": sub.presence.value}
    if sub.raw != sub.value:
        # Only carried when escaping actually changed something, to keep the
        # payload readable.
        out["raw"] = sub.raw
    return out


def render(message: Message) -> dict[str, Any]:
    delims = message.meta.delimiters
    return {
        "schemaVersion": SCHEMA_VERSION,
        "meta": {
            "version": message.meta.version,
            "messageType": message.meta.message_type,
            "controlId": message.meta.control_id,
            "delimiters": {
                "field": delims.field,
                "component": delims.component,
                "repetition": delims.repetition,
                "escape": delims.escape,
                "subcomponent": delims.subcomponent,
            },
            "segmentTerminator": message.meta.segment_terminator,
            "framing": message.meta.framing,
            "segmentCount": message.meta.segment_count,
        },
        "segments": [
            {
                "id": segment.id,
                "occurrence": segment.occurrence,
                "fields": [
                    {
                        "pos": fld.position,
                        "path": f"{segment.id}.{fld.position}",
                        "reps": [
                            {
                                "components": [
                                    {"subs": [_subcomponent(sc) for sc in comp.subs]}
                                    for comp in rep.components
                                ]
                            }
                            for rep in fld.reps
                        ],
                    }
                    for fld in segment.fields
                ],
            }
            for segment in message.segments
        ],
        "diagnostics": [
            {
                "severity": d.severity.value,
                "code": d.code,
                "message": d.message,
                **({"path": d.path} if d.path else {}),
            }
            for d in message.diagnostics
        ],
    }
