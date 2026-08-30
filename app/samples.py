"""The bundled sample message library.

A first-time visitor with no HL7 message to hand otherwise faces an empty box.
These doubles as the test corpus, so they earn their keep twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"

TITLES: dict[str, tuple[str, str]] = {
    "adt_a01_admit": ("ADT^A01 — Admit / Visit Notification", "A patient is admitted and assigned a bed."),
    "adt_a08_update": ("ADT^A08 — Update Patient Information", "Demographics change for an existing patient."),
    "oru_r01_lab_results": ("ORU^R01 — Lab Results", "A CBC panel with five OBX results and a note."),
    "orm_o01_order": ("ORM^O01 — Order Message", "A new lab order placed by the ordering system."),
    "siu_s12_appointment": ("SIU^S12 — New Appointment", "A scheduled appointment with a resource."),
    "vxu_v04_immunization": ("VXU^V04 — Immunization Update", "An immunization reported to a registry."),
    "edge_repetitions": ("Edge: field repetitions", "Repeating identifiers and addresses using '~'."),
    "edge_escapes": ("Edge: escape sequences", "Escaped delimiters, hex and formatting commands."),
    "edge_empty_and_null": ("Edge: empty vs null", 'Distinguishes "||" from \'|""|\'.'),
    "edge_custom_delimiters": ("Edge: custom delimiters", "Non-default encoding characters in MSH-2."),
    "edge_z_segment": ("Edge: Z-segment", "A locally defined segment."),
    "edge_malformed": ("Edge: malformed message", "Unsupported version and a bad segment id."),
}


@dataclass(frozen=True)
class Sample:
    id: str
    title: str
    description: str
    message: str


def _read(path: Path) -> str:
    """Read a sample without any line-ending translation.

    Decoding the bytes directly is the point: text mode would apply universal
    newlines and silently rewrite every CR terminator as LF, turning a
    conformant sample into a non-conformant one. ``read_text(newline="")``
    would also work, but only on Python 3.13+ -- the parameter does not exist
    before then, and calling it raised a TypeError that surfaced as an HTTP 500
    on 3.11 and 3.12.
    """
    return path.read_bytes().decode("utf-8")


def directory_status() -> str | None:
    """Why the sample library is empty, if it is. ``None`` means it is fine."""
    if not SAMPLES_DIR.is_dir():
        return f"The sample directory {SAMPLES_DIR} does not exist."
    if not any(SAMPLES_DIR.glob("*.hl7")):
        return f"No .hl7 files were found in {SAMPLES_DIR}."
    return None


@lru_cache(maxsize=1)
def all_samples() -> tuple[Sample, ...]:
    if not SAMPLES_DIR.is_dir():
        return ()
    out = []
    for path in sorted(SAMPLES_DIR.glob("*.hl7")):
        title, description = TITLES.get(path.stem, (path.stem, ""))
        out.append(Sample(path.stem, title, description, _read(path)))
    # Real messages first, edge cases after.
    return tuple(sorted(out, key=lambda s: (s.id.startswith("edge_"), s.id)))


def get(sample_id: str) -> Sample | None:
    return next((s for s in all_samples() if s.id == sample_id), None)
