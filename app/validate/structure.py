"""Message-structure checks against the trigger event.

Scope is deliberately narrow. Matching a real message against a full HL7
abstract structure -- with nested groups, optional groups and choices -- is
genuinely ambiguous, and a naive implementation reports order violations on
messages that are perfectly legal. So this checks only what can be stated
without resolving groups:

* the trigger event in MSH-9 is one the specification knows about;
* segments the structure requires at the top level are present.

Segment *ordering* and group cardinality are not checked. That needs real group
resolution, and a wrong answer there is worse than no answer.
"""

from __future__ import annotations

from ..defs import store
from ..parsing.models import Diagnostic, Message, Severity


def _event_ids(message: Message) -> list[str]:
    """Candidate trigger-event keys from MSH-9 (e.g. ADT^A01^ADT_A01)."""
    raw = message.meta.message_type
    if not raw:
        return []
    delims = message.meta.delimiters
    parts = [p for p in raw.split(delims.component) if p]
    candidates: list[str] = []
    if len(parts) >= 3:
        candidates.append(parts[2])              # explicit structure id
    if len(parts) >= 2:
        candidates.append(f"{parts[0]}_{parts[1]}")
    if parts:
        candidates.append(parts[0])
    return candidates


def _required_segments(entries: list[dict]) -> list[tuple[str, str]]:
    """Segments the structure genuinely requires.

    Groups are marked by a ``children`` key. A *required* group (min >= 1) is
    descended into, because a segment required inside a group that must appear
    is itself required. An *optional* group is not descended into: nothing
    inside it is required if the group may be absent entirely.
    """
    required: list[tuple[str, str]] = []
    for entry in entries or []:
        if entry.get("min", 0) < 1:
            continue
        children = entry.get("children")
        if children:
            required.extend(_required_segments(children))
            continue
        name = entry.get("name")
        if name:
            required.append((name, entry.get("desc") or ""))
    return required


def check(message: Message) -> list[Diagnostic]:
    version = store.resolve_version(message.meta.version)
    if version is None or not message.meta.message_type:
        return []

    event = None
    for candidate in _event_ids(message):
        event = store.trigger_event(version, candidate)
        if event is not None:
            break

    if event is None:
        return [
            Diagnostic(
                Severity.WARNING, "HL7W040",
                f"{message.meta.message_type!r} (MSH-9) is not a trigger event defined "
                f"in HL7 {version}, so the message structure was not checked.",
                path="MSH.9",
            )
        ]

    present = {segment.id for segment in message.segments}
    found: list[Diagnostic] = []
    structure = event.get("structure") or {}
    for name, description in _required_segments(structure.get("segments") or []):
        if name not in present:
            label = f" ({description})" if description else ""
            article = "an" if name[0] in "AEFHILMNORSX" else "a"
            found.append(
                Diagnostic(
                    Severity.ERROR, "HL7E040",
                    f"{event['id']} requires {article} {name} segment{label}, but the "
                    "message does not contain one.",
                    path=name,
                )
            )
    return found
