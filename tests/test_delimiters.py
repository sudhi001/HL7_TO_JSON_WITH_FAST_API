"""Regression lock for C6: delimiters were hardcoded, MSH-2 captured then ignored."""

from app.parsing.parser import parse
from app.parsing.preprocess import extract_delimiters
from tests.conftest import hdr


def sub(message, seg_id, position, comp=0, rep=0, s=0):
    segment = next(x for x in message.segments if x.id == seg_id)
    field = next(f for f in segment.fields if f.position == position)
    return field.reps[rep].components[comp].subs[s]


def test_custom_encoding_characters_are_honoured():
    message = parse("MSH|#@\\%|S|F|R|RF|20240101||ADT^A01|M1|P|2.5.1\rPID|1||X#Y@P#Q\r")
    delims = message.meta.delimiters
    assert (delims.component, delims.repetition, delims.subcomponent) == ("#", "@", "%")
    pid3 = next(f for f in message.segments[1].fields if f.position == 3)
    assert len(pid3.reps) == 2
    assert pid3.reps[0].components[1].subs[0].value == "Y"


def test_msh_1_is_synthesised_from_the_actual_separator():
    """The old code asserted MSH.1 == '|' regardless of the real separator."""
    message = parse("MSH|#@\\%|S|F|R|RF|20240101||ADT^A01|M1|P|2.5.1\rPID|1||X\r")
    assert sub(message, "MSH", 1).value == "|"


def test_msh_2_is_stored_verbatim_never_split_or_decoded():
    message = parse(f"{hdr()}\rPID|1||X\r")
    # MSH-2 contains ^, ~ and \ -- splitting or decoding it would destroy it.
    assert sub(message, "MSH", 2).value == "^~\\&"


def test_msh_field_positions_are_offset_correctly():
    message = parse(f"{hdr()}\rPID|1||X\r")
    assert sub(message, "MSH", 3).value == "S"
    assert sub(message, "MSH", 9).value == "ADT"
    assert sub(message, "MSH", 12).value == "2.5.1"


def test_short_encoding_characters_fall_back_and_warn():
    diags = []
    delims = extract_delimiters("MSH|^~|S|F", diags)
    assert delims.component == "^" and delims.repetition == "~"
    assert delims.escape == "\\" and delims.subcomponent == "&"
    assert any(d.code == "HL7W003" for d in diags)


def test_regex_special_delimiters_are_treated_literally():
    message = parse("MSH|.~\\&|S|F|R|RF|20240101||ADT^A01|M1|P|2.5.1\rPID|1||A.B\r")
    pid3 = next(f for f in message.segments[1].fields if f.position == 3)
    assert [c.subs[0].value for c in pid3.reps[0].components] == ["A", "B"]
