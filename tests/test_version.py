"""Regression lock for C7: one hardcoded field map was applied to every version."""

import pytest

from app.parsing.parser import parse
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
