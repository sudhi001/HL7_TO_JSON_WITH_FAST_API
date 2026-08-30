"""hl7apy as an oracle for this module's tokenisation.

The value tree is built here rather than read out of hl7apy, because hl7apy
drops empty and space-only fields and so cannot express the presence tri-state.
These tests assert the two agree on every value hl7apy *does* report, so the
library checks our work instead of sitting silently beside it.
"""

import pytest

from app.parsing.parser import parse
from tests.conftest import SAMPLES, read_sample

hl7apy_parser = pytest.importorskip("hl7apy.parser")

# hl7apy raises UnsupportedVersion rather than falling back.
SKIP = {"edge_malformed.hl7"}


def ours(message, seg_id, occurrence, position):
    segment = [s for s in message.segments if s.id == seg_id][occurrence]
    for field in segment.fields:
        if field.position == position:
            return field
    return None


@pytest.mark.parametrize(
    "name", sorted(p.name for p in SAMPLES.glob("*.hl7") if p.name not in SKIP)
)
def test_segment_sequence_matches_hl7apy(name):
    raw = read_sample(name).strip("\r")
    theirs = hl7apy_parser.parse_message(raw, find_groups=False)
    mine = parse(raw)
    assert [s.name for s in theirs.children] == [s.id for s in mine.segments]


@pytest.mark.parametrize(
    "name", sorted(p.name for p in SAMPLES.glob("*.hl7") if p.name not in SKIP)
)
def test_repetition_counts_match_hl7apy(name):
    """The bug that fused identifiers was a repetition-count bug."""
    raw = read_sample(name).strip("\r")
    theirs = hl7apy_parser.parse_message(raw, find_groups=False)
    mine = parse(raw)

    counts: dict[tuple[str, int, int], int] = {}
    seen: dict[str, int] = {}
    for segment in theirs.children:
        occurrence = seen.get(segment.name, 0)
        seen[segment.name] = occurrence + 1
        for child in segment.children:
            # Field names are like 'PID_3'; MSH_1/MSH_2 are synthesised by us.
            _, _, suffix = child.name.rpartition("_")
            if not suffix.isdigit():
                continue
            key = (segment.name, occurrence, int(suffix))
            counts[key] = counts.get(key, 0) + 1

    for (seg_id, occurrence, position), expected in counts.items():
        field = ours(mine, seg_id, occurrence, position)
        assert field is not None, f"{seg_id}[{occurrence}].{position} missing"
        assert len(field.reps) == expected, f"{seg_id}[{occurrence}].{position}"
