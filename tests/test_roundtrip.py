"""serialize(parse(m)) == m.

Round-tripping is the cheapest proof of parser fidelity: it would have caught
the inverted precedence and the missing escape handling immediately.
"""

import pytest

from app.parsing.parser import parse, serialize
from tests.conftest import SAMPLES, hdr, read_sample

# Every sample round-trips. Nothing is excluded: the parser no longer rewrites
# MSH-12 when the declared version is unsupported, so even edge_malformed.hl7
# comes back byte-identical.


@pytest.mark.parametrize(
    "message",
    [
        f"{hdr()}\rPID|1||MRN1^^^HOSP&1.2.3~MRN2||DOE^JOHN^Q||19800101|M",
        f"{hdr()}\rNTE|1||a\\T\\b\\F\\c\\E\\d",
        f'{hdr()}\rPID|A||""| |x',
        "MSH|#@\\%|S|F|R|RF|20240101||ADT^A01|M1|P|2.5.1\rPID|1||X#Y@P#Q",
        f"{hdr()}\rZPD|1|custom^data|local",
        f"{hdr()}\rPID|1||||||19800101",
    ],
    ids=["repetitions", "escapes", "nulls", "custom-delims", "z-segment", "gaps"],
)
def test_round_trips_byte_for_byte(message):
    assert serialize(parse(message)) == message


@pytest.mark.parametrize(
    "name",
    sorted(p.name for p in SAMPLES.glob("*.hl7")),
)
def test_every_sample_round_trips(name):
    raw = read_sample(name).strip("\r")
    assert serialize(parse(raw)) == raw


def test_parse_is_idempotent():
    raw = read_sample("oru_r01_lab_results.hl7").strip("\r")
    once = serialize(parse(raw))
    twice = serialize(parse(once))
    assert once == twice
