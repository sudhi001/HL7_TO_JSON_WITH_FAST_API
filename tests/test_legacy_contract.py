"""The deprecated endpoint must keep returning exactly what it used to.

Its output is wrong -- repeated segments overwrite, '~' and '^' precedence is
inverted -- but that wrongness is the contract someone already has in a script.
The golden file was captured from the original implementation before it was
replaced.
"""

import json
from pathlib import Path

import pytest

from app.render import legacy

GOLDEN = json.loads((Path(__file__).parent / "golden" / "legacy_output.json").read_text())


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_output_is_byte_identical_to_the_original(name):
    case = GOLDEN[name]
    got = legacy.render(case["input"])
    assert got["original"] == case["original"]
    assert got["detailed"] == case["detailed"]


def test_known_defects_are_deliberately_preserved():
    """If these ever start passing, the shim has drifted from the contract."""
    out = legacy.parse("MSH|^~\\&|S|F|||20240101||ADT^A01|M1|P|2.5.1\nPID|1||A^^^H~B")
    # C3: repetition fused into the component.
    assert out["PID"]["PID.3.4"] == "H~B"
    # C2: a second OBX would overwrite the first.
    out2 = legacy.parse("MSH|^~\\&|S|F|||20240101||ADT^A01|M1|P|2.5.1\nOBX|1|NM|A\nOBX|2|NM|B")
    assert out2["OBX"]["OBX.1"] == "2"


def test_pid_12_label_is_frozen_even_though_it_is_wrong():
    """PID-12 is Country Code. The old map says County Code; the shim keeps it."""
    assert legacy.PID_MAP["PID.12"] == "County Code"
