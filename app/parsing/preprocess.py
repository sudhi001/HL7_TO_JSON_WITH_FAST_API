"""Normalisation applied before a message is tokenised.

Real messages arrive wrapped in MLLP framing, with CRLF or bare LF terminators,
sometimes with a BOM, and sometimes declaring a version no definition library
covers. Everything here bridges that gap, and every fix-up is reported as a
diagnostic so the user learns what was actually wrong with their input rather
than silently getting different data than they pasted.

The supported-version list and the MSH-12 rewrite exist so the message stays
loadable by hl7apy, which supplies the field definitions and strict validation
the annotation phase is built on.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Delimiters, Diagnostic, Severity

MLLP_START = "\x0b"
MLLP_END = "\x1c"

# Versions hl7apy ships definition libraries for.
SUPPORTED_VERSIONS = {
    "2.1", "2.2", "2.3", "2.3.1", "2.4",
    "2.5", "2.5.1", "2.6", "2.7", "2.7.1", "2.8", "2.8.1", "2.8.2",
}
DEFAULT_VERSION = "2.5"

BATCH_HEADERS = ("FHS", "BHS")
BATCH_TRAILERS = ("BTS", "FTS")


@dataclass
class Preprocessed:
    text: str
    delimiters: Delimiters
    version: str
    declared_version: str | None
    segment_terminator: str
    framing: str
    diagnostics: list[Diagnostic]


def _strip_mllp(text: str, diags: list[Diagnostic]) -> tuple[str, str]:
    """Remove MLLP block framing if present."""
    framing = "bare"
    if MLLP_START in text or MLLP_END in text:
        framing = "mllp"
        text = text.replace(MLLP_START, "")
        # Trailing block terminator is <FS><CR>; drop the FS and let the CR stand.
        text = text.replace(MLLP_END, "")
        diags.append(
            Diagnostic(
                Severity.INFO,
                "HL7I001",
                "MLLP framing characters were found and removed. This message was "
                "captured straight off the wire.",
            )
        )
    return text, framing


def _normalise_terminators(text: str, diags: list[Diagnostic]) -> tuple[str, str]:
    """Normalise segment terminators to ``\\r``.

    The HL7 segment terminator is a carriage return. A message using LF parses to
    a single segment if taken literally, which is the failure this fixes.
    """
    if "\r\n" in text:
        observed = "\r\n"
        text = text.replace("\r\n", "\r")
        diags.append(
            Diagnostic(
                Severity.WARNING,
                "HL7W001",
                "Segments were separated by CRLF. The HL7 terminator is CR alone; "
                "treated as CR.",
            )
        )
    elif "\r" not in text and "\n" in text:
        observed = "\n"
        text = text.replace("\n", "\r")
        diags.append(
            Diagnostic(
                Severity.WARNING,
                "HL7W002",
                "Segments were separated by LF. The HL7 terminator is CR; treated "
                "as CR. Messages from a real interface will use CR.",
            )
        )
    else:
        observed = "\r"
        text = text.replace("\n", "")
    return text, observed


def extract_delimiters(text: str, diags: list[Diagnostic]) -> Delimiters:
    """Read encoding characters from MSH-1/MSH-2 instead of assuming them."""
    if len(text) < 4:
        return Delimiters()

    field_sep = text[3]
    end = text.find(field_sep, 4)
    enc = text[4:end] if end != -1 else ""

    defaults = Delimiters()
    component = enc[0] if len(enc) > 0 else defaults.component
    repetition = enc[1] if len(enc) > 1 else defaults.repetition
    escape = enc[2] if len(enc) > 2 else defaults.escape
    subcomponent = enc[3] if len(enc) > 3 else defaults.subcomponent

    if len(enc) < 4:
        diags.append(
            Diagnostic(
                Severity.WARNING,
                "HL7W003",
                f"MSH-2 declared {len(enc)} encoding characters; expected 4. "
                "Defaults were used for the missing ones.",
                path="MSH.2",
            )
        )
    return Delimiters(field_sep, component, repetition, escape, subcomponent)


def _detect_version(
    text: str, delims: Delimiters, diags: list[Diagnostic]
) -> tuple[str, str | None]:
    """Read MSH-12, falling back to a supported version when we cannot use it."""
    header = text.split("\r", 1)[0]
    parts = header.split(delims.field)
    # MSH-12 is index 11 in the split, because MSH-1 is the separator itself.
    declared = parts[11].strip() if len(parts) > 11 else ""
    # MSH-12 is a VID; the version is its first component.
    declared = declared.split(delims.component)[0].strip()

    if declared in SUPPORTED_VERSIONS:
        return declared, declared

    if not declared:
        diags.append(
            Diagnostic(
                Severity.WARNING,
                "HL7W004",
                f"MSH-12 (version) is missing. Parsed as {DEFAULT_VERSION}.",
                path="MSH.12",
            )
        )
    else:
        diags.append(
            Diagnostic(
                Severity.WARNING,
                "HL7W005",
                f"MSH-12 declares version {declared!r}, which is not supported. "
                f"Parsed as {DEFAULT_VERSION}.",
                path="MSH.12",
            )
        )
    return DEFAULT_VERSION, (declared or None)


def _force_version(text: str, delims: Delimiters, version: str) -> str:
    """Rewrite MSH-12 so hl7apy will accept the message.

    hl7apy raises ``UnsupportedVersion`` rather than falling back, and offers no
    version override on ``parse_message``, so the substitution has to happen in
    the text. Only the header line is touched.
    """
    head, sep, rest = text.partition("\r")
    parts = head.split(delims.field)
    while len(parts) <= 11:
        parts.append("")
    parts[11] = version
    return delims.field.join(parts) + sep + rest


def detect_framing(text: str) -> str:
    first = text.split("\r", 1)[0][:3]
    if first in BATCH_HEADERS:
        return "batch"
    return "bare"


def preprocess(raw: str) -> Preprocessed:
    diags: list[Diagnostic] = []

    text = raw.lstrip("﻿")
    text, framing = _strip_mllp(text, diags)
    text, terminator = _normalise_terminators(text, diags)
    text = text.strip("\r")

    if detect_framing(text) == "batch":
        framing = "batch"
        diags.append(
            Diagnostic(
                Severity.INFO,
                "HL7I002",
                "This is a batch file (FHS/BHS envelope). The envelope segments are "
                "shown alongside the messages.",
            )
        )

    delims = extract_delimiters(text, diags)
    version, declared = _detect_version(text, delims, diags)
    if declared != version:
        text = _force_version(text, delims, version)

    return Preprocessed(
        text=text,
        delimiters=delims,
        version=version,
        declared_version=declared,
        segment_terminator=terminator,
        framing=framing,
        diagnostics=diags,
    )
