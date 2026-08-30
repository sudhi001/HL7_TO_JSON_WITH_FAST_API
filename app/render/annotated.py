"""Canonical output with definitions bound onto it."""

from __future__ import annotations

from typing import Any

from ..annotate import annotate
from ..parsing.models import Message
from . import canonical


def render(message: Message) -> dict[str, Any]:
    out = canonical.render(message)
    annotations = annotate(message)
    out["annotations"] = annotations
    if not annotations.get("available"):
        out.setdefault("diagnostics", []).append(
            {
                "severity": "info",
                "code": "HL7I003",
                "message": annotations.get("reason", "Definitions unavailable."),
            }
        )
    return out
