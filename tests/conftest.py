from pathlib import Path

import pytest

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


def read_sample(name: str) -> str:
    """Read a sample preserving CR terminators.

    Text mode applies universal-newline translation and would turn every CR
    into LF, quietly defeating the thing these fixtures exist to test. Decoding
    bytes avoids that on every supported Python; ``read_text(newline="")`` is
    3.13+ only.
    """
    return (SAMPLES / name).read_bytes().decode("utf-8")


@pytest.fixture
def sample():
    return read_sample


def hdr(version: str = "2.5.1", msg_type: str = "ADT^A01") -> str:
    return f"MSH|^~\\&|S|F|R|RF|20240101120000||{msg_type}|M1|P|{version}"
