"""Regression lock for C2: repeated segments overwrote each other.

The old model keyed segments by name in a flat dict, so an ORU with 30 OBX
reported one. This is the defect with the widest blast radius for lab results.
"""

from app.parsing.parser import parse
from tests.conftest import hdr, read_sample


def test_five_obx_segments_all_survive():
    body = "".join(f"OBX|{i}|NM|T{i}||{i * 10}\r" for i in range(1, 6))
    message = parse(f"{hdr(msg_type='ORU^R01')}\r{body}")
    obx = [s for s in message.segments if s.id == "OBX"]
    assert len(obx) == 5
    assert [s.occurrence for s in obx] == [0, 1, 2, 3, 4]


def test_occurrence_is_per_segment_type():
    message = parse(f"{hdr()}\rNK1|1\rOBX|1\rNK1|2\rOBX|2\r")
    occ = [(s.id, s.occurrence) for s in message.segments if s.id in ("NK1", "OBX")]
    assert occ == [("NK1", 0), ("OBX", 0), ("NK1", 1), ("OBX", 1)]


def test_real_lab_sample_keeps_every_result():
    message = parse(read_sample("oru_r01_lab_results.hl7"))
    assert len([s for s in message.segments if s.id == "OBX"]) == 5
