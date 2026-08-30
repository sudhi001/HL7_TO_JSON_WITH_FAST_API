"""Consistent diagnostic paths.

A finding has to say *which* OBX. With five OBX segments, a bare ``OBX.11`` is
not actionable, so the occurrence is included whenever there is more than one of
a segment.
"""

from __future__ import annotations

from ..parsing.models import Segment


def segment_path(segment: Segment, occurrences: int) -> str:
    if occurrences > 1:
        return f"{segment.id}[{segment.occurrence + 1}]"
    return segment.id


def field_path(
    segment: Segment,
    occurrences: int,
    position: int,
    *,
    repetition: int | None = None,
    component: int | None = None,
) -> str:
    path = f"{segment_path(segment, occurrences)}.{position}"
    if repetition is not None:
        path += f"[{repetition}]"
    if component is not None:
        path += f".{component}"
    return path


def occurrence_counts(message) -> dict[str, int]:
    counts: dict[str, int] = {}
    for segment in message.segments:
        counts[segment.id] = counts.get(segment.id, 0) + 1
    return counts
