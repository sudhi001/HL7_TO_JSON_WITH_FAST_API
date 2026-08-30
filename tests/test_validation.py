"""Validation checks.

The most important tests here are the negative ones: a valid message must
produce no errors. A validator that fires on correct input trains people to
ignore it, which is worse than having none.
"""

import pytest

from app.defs import store
from app.parsing.models import Severity
from app.parsing.parser import parse
from app.validate import COLLAPSE_AFTER, validate
from tests.conftest import SAMPLES, hdr, read_sample

requires_store = pytest.mark.skipif(
    not store.DB_PATH.exists(), reason="definition store not built"
)

# The edge_* fixtures exist to exercise the tokeniser -- delimiters, escapes,
# repetitions -- and are deliberately minimal. They are not conformant messages
# and are not meant to be: padding them with an EVN and a PV1 would obscure the
# one thing each is there to test. Conformance is asserted on the realistic
# samples below.
TOKENISER_FIXTURES = {p.name for p in SAMPLES.glob("edge_*.hl7")}

VALID_ADT = (
    f"{hdr()}\rEVN|A01|20240115143000\r"
    "PID|1||MRN1^^^MCM^MR||SMITH^JOHN||19800315|M\r"
    "PV1|1|I|2000^2012^01\r"
)


def codes(message_text: str) -> list[str]:
    return [d.code for d in validate(parse(message_text))]


def errors(message_text: str) -> list[str]:
    return [d.code for d in validate(parse(message_text)) if d.severity is Severity.ERROR]


# --- no false positives -----------------------------------------------------

@requires_store
def test_a_conformant_message_produces_no_errors():
    assert errors(VALID_ADT) == []


@requires_store
@pytest.mark.parametrize(
    "name",
    sorted(p.name for p in SAMPLES.glob("*.hl7") if p.name not in TOKENISER_FIXTURES),
)
def test_realistic_samples_validate_cleanly(name):
    """Every message that claims to be realistic must produce zero errors.

    This is the anti-false-positive test: it caught four genuine defects in the
    sample corpus itself (a shifted SCH segment, an empty required RXA-4, and a
    message type using the wrong component separator).
    """
    found = validate(parse(read_sample(name)))
    reported = [f"{d.code} {d.path}: {d.message}" for d in found if d.severity is Severity.ERROR]
    assert reported == []


@requires_store
def test_z_segments_are_informational_not_errors():
    found = validate(parse(VALID_ADT + "ZPD|1|local data\r"))
    zpd = [d for d in found if d.code == "HL7I010"]
    assert zpd and zpd[0].severity is Severity.INFO


@requires_store
def test_site_defined_table_values_are_not_errors():
    """Race and similar user-defined tables legitimately carry local codes."""
    found = validate(parse(f"{hdr()}\rEVN|A01|20240115143000\r"
                           "PID|1||MRN1||SMITH^JOHN||19800315|M||W\r"
                           "PV1|1|I|2000\r"))
    race = [d for d in found if d.path and d.path.startswith("PID.10")]
    assert all(d.severity is Severity.INFO for d in race)


# --- required fields --------------------------------------------------------

@requires_store
def test_missing_required_field_is_an_error():
    broken = VALID_ADT.replace("PID|1||MRN1^^^MCM^MR||SMITH^JOHN||19800315|M",
                               "PID|1||||SMITH^JOHN||19800315|M")
    assert "HL7E010" in errors(broken)


@requires_store
def test_synthesised_msh_delimiter_fields_are_not_reported_missing():
    """MSH-1 and MSH-2 are the delimiters; they always exist by construction."""
    found = validate(parse(VALID_ADT))
    assert not [d for d in found if d.path in ("MSH.1", "MSH.2")]


# --- datatypes --------------------------------------------------------------

@requires_store
@pytest.mark.parametrize("value", ["20240230", "20241301", "20240115256000"])
def test_impossible_dates_are_errors(value):
    broken = VALID_ADT.replace("19800315", value)
    assert any(code in errors(broken) for code in ("HL7E020", "HL7E021", "HL7E022"))


@requires_store
@pytest.mark.parametrize("value", ["19800315", "198003", "1980", "19800315143000", "19800315143000+0500"])
def test_well_formed_dates_are_accepted(value):
    broken = VALID_ADT.replace("19800315", value)
    assert not [c for c in errors(broken) if c.startswith("HL7E02")]


@requires_store
def test_non_numeric_sequence_id_is_an_error():
    broken = (f"{hdr(msg_type='ORU^R01')}\rOBR|1|||CBC\r"
              "OBX|abc|NM|GLU||100|||||F\r")
    assert "HL7E025" in errors(broken)


# --- cardinality ------------------------------------------------------------

@requires_store
def test_repeating_a_non_repeating_field_is_an_error():
    broken = VALID_ADT.replace("PID|1|", "PID|1~2|")
    assert "HL7E011" in errors(broken)


@requires_store
def test_repeating_a_repeatable_field_is_fine():
    ok = VALID_ADT.replace("MRN1^^^MCM^MR", "MRN1^^^MCM^MR~MRN2^^^SSA^SS")
    assert "HL7E011" not in errors(ok)


# --- closed vs open tables --------------------------------------------------

@requires_store
def test_invalid_value_in_a_closed_hl7_table_is_an_error():
    broken = VALID_ADT.replace("|19800315|M", "|19800315|Z")
    assert "HL7E030" in errors(broken)


# --- message structure ------------------------------------------------------

@requires_store
def test_missing_required_segment_is_an_error():
    without_pv1 = VALID_ADT.replace("PV1|1|I|2000^2012^01\r", "")
    found = validate(parse(without_pv1))
    assert any(d.code == "HL7E040" and d.path == "PV1" for d in found)


@requires_store
def test_optional_groups_do_not_make_their_contents_required():
    """ORU_R01 requires OBR, but nothing inside its optional groups."""
    minimal = (f"{hdr(msg_type='ORU^R01')}\rPID|1||MRN1||SMITH^JOHN\r"
               "OBR|1|||CBC\r")
    assert not [d for d in validate(parse(minimal))
                if d.code == "HL7E040" and d.path not in ("OBR",)]


@requires_store
def test_unknown_trigger_event_warns_rather_than_failing():
    found = validate(parse(f"{hdr(msg_type='ZZZ^Z99')}\rPID|1||MRN1\r"))
    assert any(d.code == "HL7W040" for d in found)


# --- noise control ----------------------------------------------------------

@requires_store
def test_repeated_findings_are_collapsed():
    many = f"{hdr(msg_type='ORU^R01')}\rOBR|1|||CBC\r" + "".join(
        f"OBX|{i}|NM|T{i}||{i}\r" for i in range(1, 12)
    )
    found = validate(parse(many))
    required = [d for d in found if d.code == "HL7E010"]
    # Five concrete findings plus one summary line, not eleven.
    assert len(required) == COLLAPSE_AFTER + 1
    assert required[-1].message.startswith("... and")


@requires_store
def test_findings_name_which_occurrence():
    many = f"{hdr(msg_type='ORU^R01')}\rOBR|1|||CBC\r" + "".join(
        f"OBX|{i}|NM|T{i}||{i}\r" for i in range(1, 4)
    )
    paths = [d.path for d in validate(parse(many)) if d.code == "HL7E010"]
    assert "OBX[1].11" in paths and "OBX[2].11" in paths


@requires_store
def test_errors_are_listed_before_warnings_and_info():
    found = validate(parse(f"{hdr()}\rPID|1||||SMITH^JOHN||20240230|Z\rZPD|1|x\r"))
    severities = [d.severity for d in found]
    assert severities == sorted(severities, key=lambda s: {"error": 0, "warning": 1, "info": 2}[s.value])


@requires_store
def test_validation_never_raises_on_hostile_input():
    for text in (VALID_ADT, f"{hdr()}\rPID|" + "|" * 200 + "\r", f"{hdr()}\rQQQ|1\r"):
        validate(parse(text))
