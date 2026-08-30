"""Regression lock for C10: empty, space-only and explicitly-null were conflated.

``||`` means "no information supplied -- leave any existing value alone".
``|""|`` means "delete the existing value". In an update message these are
opposites. The old parser dropped both, along with a field containing a space.
"""

from app.parsing.models import Presence
from app.parsing.parser import parse
from tests.conftest import hdr


def presences(message, seg_id="PID"):
    segment = next(s for s in message.segments if s.id == seg_id)
    return {
        f.position: f.reps[0].components[0].subs[0].presence for f in segment.fields
    }


def test_empty_null_and_space_are_distinguished():
    message = parse(f'{hdr()}\rPID|A||""| |x\r')
    got = presences(message)
    assert got[1] is Presence.PRESENT   # "A"
    assert got[2] is Presence.EMPTY     # ||
    assert got[3] is Presence.NULL      # |""|
    assert got[4] is Presence.PRESENT   # a single space is legal data
    assert got[5] is Presence.PRESENT   # "x"


def test_a_space_is_data_and_is_not_discarded():
    message = parse(f"{hdr()}\rPID|1|| |\r")
    segment = message.segments[1]
    field3 = next(f for f in segment.fields if f.position == 3)
    assert field3.reps[0].components[0].subs[0].raw == " "


def test_explicit_null_value_is_empty_string_but_flagged_null():
    message = parse(f'{hdr()}\rPID|1||""\r')
    sub = next(f for f in message.segments[1].fields if f.position == 3).reps[0].components[0].subs[0]
    assert sub.presence is Presence.NULL
    assert sub.value == ""
    assert sub.raw == '""'


def test_positions_are_not_shifted_by_empty_fields():
    """Dropping empties would renumber every later field."""
    message = parse(f"{hdr()}\rPID|1||||||19800101\r")
    got = presences(message)
    assert got[7] is Presence.PRESENT
