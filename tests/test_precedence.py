"""Regression lock for C3: '^' was split before '~', inverting HL7 precedence.

The correct order is field -> repetition -> component -> subcomponent. The old
code produced a fused ``PID.3.4 = "HOSP~MRN2"`` and invented the path
``PID.3.4.1``, merging two distinct patient identifiers into one value.
"""

from app.parsing.parser import parse
from tests.conftest import hdr


def field(message, seg_id, position):
    segment = next(s for s in message.segments if s.id == seg_id)
    return next(f for f in segment.fields if f.position == position)


def test_repetition_is_above_component():
    message = parse(f"{hdr()}\rPID|1||A^B~C^D\r")
    pid3 = field(message, "PID", 3)
    assert len(pid3.reps) == 2
    assert [c.subs[0].value for c in pid3.reps[0].components] == ["A", "B"]
    assert [c.subs[0].value for c in pid3.reps[1].components] == ["C", "D"]


def test_distinct_identifiers_are_not_fused():
    message = parse(f"{hdr()}\rPID|1||MRN1^^^HOSP~MRN2^^^CLINIC\r")
    pid3 = field(message, "PID", 3)
    assert len(pid3.reps) == 2
    # The old output was PID.3.4 == "HOSP~MRN2".
    assert pid3.reps[0].components[3].subs[0].value == "HOSP"
    assert pid3.reps[1].components[0].subs[0].value == "MRN2"
    assert pid3.reps[1].components[3].subs[0].value == "CLINIC"


def test_no_fabricated_seventh_component():
    """The old parser produced PID.3.7, which does not exist in a CX datatype."""
    message = parse(f"{hdr()}\rPID|1||MRN1^^^HOSP~MRN2^^^CLINIC\r")
    pid3 = field(message, "PID", 3)
    for rep in pid3.reps:
        assert len(rep.components) == 4
