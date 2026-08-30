"""Regression lock for C4: '&' subcomponents were never split."""

from app.parsing.parser import parse
from tests.conftest import hdr


def test_subcomponents_are_split():
    message = parse(f"{hdr()}\rPID|1||MRN^^^HOSP&1.2.3.4&ISO\r")
    pid3 = next(f for f in message.segments[1].fields if f.position == 3)
    assert [s.value for s in pid3.reps[0].components[3].subs] == ["HOSP", "1.2.3.4", "ISO"]


def test_subcomponent_in_a_field_without_components():
    message = parse(f"{hdr()}\rPID|1||A&B&C\r")
    pid3 = next(f for f in message.segments[1].fields if f.position == 3)
    assert [s.value for s in pid3.reps[0].components[0].subs] == ["A", "B", "C"]
