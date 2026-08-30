"""Regression lock for C9: anything was accepted as a valid message.

``parse("hello world")`` used to return ``{"hello world": {}}`` with HTTP 200.
"""

import pytest

from app.parsing.parser import NotAnHL7Message, parse
from tests.conftest import hdr


@pytest.mark.parametrize("bad", ["hello world", "", "   ", "\r\r", "PID|1||X", "{}"])
def test_non_hl7_input_is_rejected(bad):
    with pytest.raises(NotAnHL7Message):
        parse(bad)


def test_error_message_says_what_was_wrong():
    with pytest.raises(NotAnHL7Message, match="must begin with MSH"):
        parse("PID|1||X")


@pytest.mark.parametrize("header", ["MSH", "FHS", "BHS"])
def test_valid_header_segments_are_accepted(header):
    parse(f"{header}|^~\\&|S|F|R|RF|20240101||ADT^A01|M1|P|2.5.1\r")


def test_short_segment_id_is_reported_but_not_fatal():
    message = parse(f"{hdr()}\rXX|not a real segment\r")
    assert any(d.code == "HL7W006" for d in message.diagnostics)
    assert [s.id for s in message.segments] == ["MSH", "XX"]


def test_z_segments_are_kept_with_their_fields():
    message = parse(f"{hdr()}\rZPD|1|custom^data|local\r")
    zpd = next(s for s in message.segments if s.id == "ZPD")
    assert zpd.fields[1].reps[0].components[0].subs[0].value == "custom"
