"""Regression lock for C1: segments were split on LF, but HL7 uses CR.

Before the rewrite, a conformant CR-delimited message collapsed into a single
MSH segment and returned HTTP 200 with wrong data.
"""

import pytest

from app.parsing.parser import parse
from tests.conftest import hdr

BODY = "PID|1||MRN1||DOE^JOHN\rOBX|1|NM|GLU||100"


def test_cr_is_the_canonical_terminator():
    message = parse(f"{hdr()}\r{BODY}")
    assert [s.id for s in message.segments] == ["MSH", "PID", "OBX"]


def test_lf_parses_identically_to_cr_but_warns():
    cr = parse(f"{hdr()}\r{BODY}")
    lf = parse(f"{hdr()}\n{BODY}".replace("\r", "\n"))
    assert [s.id for s in lf.segments] == [s.id for s in cr.segments]
    assert any(d.code == "HL7W002" for d in lf.diagnostics)


def test_crlf_does_not_leave_a_stray_cr_on_the_last_field():
    message = parse(f"{hdr()}\r\nPID|1||MRN1\r\n")
    pid = message.segments[1]
    last = pid.fields[-1].reps[0].components[0].subs[0]
    assert "\r" not in last.value and "\n" not in last.value
    assert any(d.code == "HL7W001" for d in message.diagnostics)


def test_trailing_terminator_does_not_create_an_empty_segment():
    message = parse(f"{hdr()}\rPID|1||MRN1\r")
    assert [s.id for s in message.segments] == ["MSH", "PID"]


def test_interior_blank_lines_are_skipped():
    message = parse(f"{hdr()}\r\rPID|1||MRN1\r")
    assert [s.id for s in message.segments] == ["MSH", "PID"]


def test_bom_is_stripped():
    message = parse("﻿" + f"{hdr()}\rPID|1||MRN1")
    assert message.segments[0].id == "MSH"


def test_mllp_framing_is_stripped_and_reported():
    message = parse(f"\x0b{hdr()}\rPID|1||MRN1\r\x1c\r")
    assert [s.id for s in message.segments] == ["MSH", "PID"]
    assert message.meta.framing == "mllp"
    assert any(d.code == "HL7I001" for d in message.diagnostics)
