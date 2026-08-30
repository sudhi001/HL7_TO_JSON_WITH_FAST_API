"""Regression lock for C7: one hardcoded field map was applied to every version."""

import pytest

from app.parsing.parser import parse, serialize
from app.render import canonical
from app.parsing.preprocess import DEFAULT_VERSION, SUPPORTED_VERSIONS
from tests.conftest import hdr


@pytest.mark.parametrize("version", sorted(SUPPORTED_VERSIONS))
def test_declared_version_is_carried_through(version):
    message = parse(f"{hdr(version=version)}\rPID|1||X\r")
    assert message.meta.version == version


def test_missing_version_falls_back_and_warns():
    message = parse("MSH|^~\\&|S|F|R|RF|20240101||ADT^A01|M1|P|\rPID|1||X\r")
    assert message.meta.version == DEFAULT_VERSION
    assert any(d.code == "HL7W004" for d in message.diagnostics)


def test_unsupported_version_falls_back_and_warns():
    message = parse(f"{hdr(version='9.9')}\rPID|1||X\r")
    assert message.meta.version == DEFAULT_VERSION
    assert any(d.code == "HL7W005" for d in message.diagnostics)


def test_version_with_components_uses_the_first():
    message = parse(f"{hdr(version='2.5.1^ISO^1')}\rPID|1||X\r")
    assert message.meta.version == "2.5.1"


def test_unsupported_version_does_not_rewrite_the_message():
    """Regression: substituting MSH-12 destroyed the rest of the VID.

    "9.9^ISO^1" became "2.5", discarding the coding-system components and
    reporting a version the sender never transmitted.
    """
    source = f"{hdr(version='9.9^ISO^1')}\rPID|1||X"
    message = parse(source)
    msh12 = next(f for f in message.segments[0].fields if f.position == 12)
    assert [c.subs[0].value for c in msh12.reps[0].components] == ["9.9", "ISO", "1"]
    assert serialize(message) == source


def test_resolved_and_declared_versions_are_both_reported():
    message = parse(f"{hdr(version='9.9')}\rPID|1||X\r")
    assert message.meta.version == DEFAULT_VERSION   # used for lookups
    assert message.meta.declared_version == "9.9"    # what MSH-12 said
    body = canonical.render(message)
    assert body["meta"]["version"] == DEFAULT_VERSION
    assert body["meta"]["declaredVersion"] == "9.9"


def test_declared_version_is_omitted_when_it_matches():
    body = canonical.render(parse(f"{hdr(version='2.5.1')}\rPID|1||X\r"))
    assert "declaredVersion" not in body["meta"]


def test_a_message_with_no_version_field_is_not_given_one():
    source = "MSH|\rPID|1||X"
    message = parse(source)
    assert serialize(message) == source
