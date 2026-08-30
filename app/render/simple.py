"""Ergonomic projection, for piping into jq.

Collapse rules, fixed and tested:

* Segments are **always** arrays, even MSH. Shape ambiguity was the original
  sin of the old output; saving two characters is not worth reintroducing it.
* One repetition, one component, one subcomponent collapses to a plain string.
* An absent field is omitted; an explicitly-nulled field is JSON ``null``.
"""

from __future__ import annotations

from typing import Any

from ..parsing.models import Message, Presence


def _subs(comp) -> Any:
    if len(comp.subs) == 1:
        sub = comp.subs[0]
        if sub.presence is Presence.NULL:
            return None
        return sub.value
    return {str(sc.index): (None if sc.presence is Presence.NULL else sc.value) for sc in comp.subs}


def _components(rep) -> Any:
    if len(rep.components) == 1:
        return _subs(rep.components[0])
    return {str(c.index): _subs(c) for c in rep.components}


def _field(fld) -> Any:
    if len(fld.reps) == 1:
        return _components(fld.reps[0])
    return [_components(rep) for rep in fld.reps]


def render(message: Message) -> dict[str, Any]:
    out: dict[str, list[dict[str, Any]]] = {}
    for segment in message.segments:
        entry: dict[str, Any] = {}
        for fld in segment.fields:
            first = fld.reps[0].components[0].subs[0] if fld.reps and fld.reps[0].components else None
            if first is not None and first.presence is Presence.EMPTY and len(fld.reps) == 1 \
                    and len(fld.reps[0].components) == 1 and len(fld.reps[0].components[0].subs) == 1:
                continue  # absent: omit the key entirely
            entry[str(fld.position)] = _field(fld)
        out.setdefault(segment.id, []).append(entry)
    return out
