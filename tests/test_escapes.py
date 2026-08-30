"""Regression lock for C5: escape sequences were passed through verbatim."""

import pytest

from app.parsing.escape import decode, encode
from app.parsing.models import Delimiters
from app.parsing.parser import parse
from tests.conftest import hdr

D = Delimiters()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a\\F\\b", "a|b"),
        ("a\\S\\b", "a^b"),
        ("a\\T\\b", "a&b"),
        ("a\\R\\b", "a~b"),
        ("a\\E\\b", "a\\b"),
        ("\\X0D0A\\", "\r\n"),
        ("line\\.br\\next", "line\nnext"),
        ("plain text", "plain text"),
    ],
)
def test_decodes_standard_sequences(raw, expected):
    assert decode(raw, D) == expected


def test_locally_defined_sequences_are_preserved():
    assert decode("\\Zlocal\\", D) == "\\Zlocal\\"


def test_unterminated_escape_is_kept_literally_not_dropped():
    assert decode("value\\T", D) == "value\\T"


def test_malformed_hex_is_kept_literally():
    assert decode("\\XZZ\\", D) == "\\XZZ\\"


def test_escape_char_is_taken_from_msh2_not_assumed():
    custom = Delimiters(escape="!")
    assert decode("a!F!b", custom) == "a|b"


def test_decoded_in_a_parsed_message():
    message = parse(f"{hdr()}\rNTE|1||He said \\T\\ she said\r")
    nte3 = next(f for f in message.segments[1].fields if f.position == 3)
    assert nte3.reps[0].components[0].subs[0].value == "He said & she said"


def test_encode_decode_round_trip():
    original = "a|b^c&d~e\\f"
    assert decode(encode(original, D), D) == original
