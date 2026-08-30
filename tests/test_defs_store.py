"""The definition store: correctness, and the two invariants that keep it cheap.

1. Nothing is opened or queried at import time.
2. A missing or corrupt store degrades to un-annotated output, never an error --
   parsing must never depend on definitions being present.
"""

from pathlib import Path

import pytest

from app.annotate import annotate
from app.defs import store
from app.parsing.parser import parse
from tests.conftest import hdr

MESSAGE = f"{hdr()}\rPID|1||MRN1||SMITH^JOHN||19800315|M\rPV1|1|I|2000\r"


@pytest.fixture(autouse=True)
def _reset():
    store.reset_for_tests()
    yield
    store.reset_for_tests()


requires_store = pytest.mark.skipif(
    not store.DB_PATH.exists(),
    reason="definition store not built; run tools/build_defs_db.py",
)


@requires_store
def test_store_is_available_and_covers_the_documented_versions():
    assert store.available()
    assert store.versions() == ("2.1", "2.2", "2.3", "2.3.1", "2.4", "2.5", "2.5.1", "2.6", "2.7", "2.7.1")


@requires_store
def test_field_definition_lookup():
    field = store.field_def("2.5.1", "PID", 5)
    assert field.name == "Patient Name"
    assert field.datatype == "XPN"
    assert field.required is True
    assert field.repeatable is True


@requires_store
@pytest.mark.parametrize(
    "segment,position,expected_optionality",
    # Ground truth from the published v2.5.1 spec. The upstream package README
    # documents opt as 0/1 while the data uses 1/2, so this pins the mapping the
    # builder chose -- getting it backwards would invert every flag in the store.
    [("MSH", 7, "R"), ("MSH", 10, "R"), ("MSH", 3, "O"),
     ("PID", 3, "R"), ("PID", 8, "O"), ("PV1", 2, "R"), ("OBR", 4, "R")],
)
def test_optionality_matches_the_published_spec(segment, position, expected_optionality):
    assert store.field_def("2.5.1", segment, position).optionality == expected_optionality


@requires_store
@pytest.mark.parametrize(
    "table,value,meaning",
    [("1", "M", "Male"), ("1", "F", "Female"), ("4", "I", "Inpatient"),
     ("103", "P", "Production"), ("136", "Y", "Yes")],
)
def test_code_meanings(table, value, meaning):
    """The half hl7apy does not have: it knows 'M' is legal, not that it is Male."""
    assert store.code_meaning("2.5.1", table, value) == meaning


@requires_store
def test_unknown_code_returns_none_rather_than_guessing():
    assert store.code_meaning("2.5.1", "1", "ZZ") is None


@requires_store
def test_datatype_components_name_the_parts_of_a_field():
    components = store.datatype_components("2.5.1", "XPN")
    assert components[0].name == "Family Name"
    assert components[1].name == "Given Name"


@requires_store
def test_version_fallback_prefers_the_closest_available():
    # The store covers up to 2.7.1; a 2.8 message should still get field names.
    assert store.resolve_version("2.8") == "2.7.1"
    assert store.resolve_version("2.5.1") == "2.5.1"
    assert store.resolve_version(None) == "2.7.1"


@requires_store
def test_annotation_decodes_coded_values_end_to_end():
    result = annotate(parse(MESSAGE))
    assert result["available"] is True
    pid = next(s for s in result["segments"] if s["id"] == "PID")
    field8 = next(f for f in pid["fields"] if f["pos"] == 8)
    assert field8["name"] == "Administrative Sex"
    assert field8["reps"][0]["components"][0]["subs"][0]["meaning"] == "Male"


@requires_store
def test_msh_2_is_not_annotated_as_a_coded_value():
    """MSH-2 holds the delimiters themselves; decoding it would be nonsense."""
    result = annotate(parse(MESSAGE))
    msh = result["segments"][0]
    field2 = next(f for f in msh["fields"] if f["pos"] == 2)
    assert "meaning" not in field2["reps"][0]["components"][0]["subs"][0]


def segment_with(segment_id: str, position: int, value: str) -> str:
    """Build a segment carrying `value` at exactly `position`."""
    fields = [""] * position
    fields[position - 1] = value
    return segment_id + "|" + "|".join(fields)


def meanings_for(message: str, segment_id: str, position: int) -> list[str]:
    result = annotate(parse(message))
    seg = next(s for s in result["segments"] if s["id"] == segment_id)
    field = next(f for f in seg["fields"] if f["pos"] == position)
    return [
        sub.get("meaning")
        for rep in field["reps"] for comp in rep["components"] for sub in comp["subs"]
    ]


@requires_store
@pytest.mark.parametrize(
    "segment,position,value,meaning",
    [
        ("PID", 8, "M", "Male"),          # IS -- table sits on the field
        ("PID", 16, "M", "Married"),      # CE composite -- code lives in CE.1
        ("PID", 17, "CHR", "Christian"),  # CE composite
        ("PV1", 2, "I", "Inpatient"),
    ],
)
def test_coded_composites_decode_via_the_field_table(segment, position, value, meaning):
    """Regression: CE/CWE fields carry their table on the field, not on CE.1.

    Looking only at the component's own binding meant every coded composite --
    marital status, religion, patient class -- silently failed to decode.
    """
    message = f"{hdr()}\r{segment_with(segment, position, value)}\r"
    assert meaning in meanings_for(message, segment, position)


@requires_store
def test_trigger_event_code_decodes():
    """MSH-9.2 'A01' should name the trigger event, not just the message type."""
    found = meanings_for(f"{hdr()}\rPID|1||MRN1\r", "MSH", 9)
    assert any(m and "Admit/visit notification" in m for m in found)


def test_missing_store_degrades_instead_of_failing(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "absent.sqlite3")
    store.reset_for_tests()

    assert store.available() is False
    assert store.field_def("2.5.1", "PID", 5) is None
    assert store.code_meaning("2.5.1", "1", "M") is None

    # The message must still parse.
    message = parse(MESSAGE)
    assert [s.id for s in message.segments] == ["MSH", "PID", "PV1"]
    result = annotate(message)
    assert result["available"] is False
    assert "tools/build_defs_db.py" in result["reason"]


def test_corrupt_store_degrades_instead_of_failing(monkeypatch, tmp_path):
    broken = tmp_path / "broken.sqlite3"
    broken.write_bytes(b"this is not a database")
    monkeypatch.setattr(store, "DB_PATH", broken)
    store.reset_for_tests()

    assert store.available() is False
    assert store.field_def("2.5.1", "PID", 5) is None
    assert annotate(parse(MESSAGE))["available"] is False
