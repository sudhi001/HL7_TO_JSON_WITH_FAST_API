"""HL7 v2 escape-sequence handling.

hl7apy does not decode escape sequences — it returns them verbatim — so this is
ours to do. Without it, a field containing an escaped delimiter is displayed
misleadingly: ``He said \\T\\ she said`` should read ``He said & she said``.
"""

from __future__ import annotations

import re

from .models import Delimiters

# Formatting commands (\.br\, \.sp\, ...). They carry layout, not data.
_FORMATTING = {
    ".br": "\n",
    ".sp": "\n",
    ".fi": "",
    ".nf": "",
    ".in": "",
    ".ti": "",
    ".sk": " ",
    ".ce": "\n",
}


def _decode_hex(body: str) -> str | None:
    """``\\Xdd..\\`` — hex-encoded bytes."""
    digits = body[1:]
    if not digits or len(digits) % 2 or not re.fullmatch(r"[0-9A-Fa-f]+", digits):
        return None
    try:
        return bytes.fromhex(digits).decode("utf-8", errors="replace")
    except ValueError:
        return None


def decode(text: str, delims: Delimiters) -> str:
    """Decode HL7 escape sequences in a leaf value.

    Unknown or malformed sequences are left exactly as they appear rather than
    dropped — for a tool people use to debug interfaces, showing the raw truth
    beats silently swallowing it.
    """
    esc = delims.escape
    if not text or esc not in text:
        return text

    simple = {
        "F": delims.field,
        "S": delims.component,
        "T": delims.subcomponent,
        "R": delims.repetition,
        "E": esc,
    }

    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch != esc:
            out.append(ch)
            i += 1
            continue

        end = text.find(esc, i + 1)
        if end == -1:
            # Unterminated escape: keep the rest literally.
            out.append(text[i:])
            break

        body = text[i + 1 : end]
        if body in simple:
            out.append(simple[body])
        elif body in _FORMATTING:
            out.append(_FORMATTING[body])
        elif body[:1] in ("X", "x"):
            decoded = _decode_hex(body)
            out.append(decoded if decoded is not None else text[i : end + 1])
        elif body[:1] in ("Z", "z", "C", "c", "M", "m"):
            # Locally defined and charset-switch sequences: preserve verbatim.
            out.append(text[i : end + 1])
        else:
            out.append(text[i : end + 1])
        i = end + 1

    return "".join(out)


def encode(text: str, delims: Delimiters) -> str:
    """Escape delimiter characters so ``text`` can be written back into a message."""
    if not text:
        return text
    # Escape char first, or it would double-escape the sequences added below.
    out = text.replace(delims.escape, f"{delims.escape}E{delims.escape}")
    for char, code in (
        (delims.field, "F"),
        (delims.component, "S"),
        (delims.subcomponent, "T"),
        (delims.repetition, "R"),
    ):
        out = out.replace(char, f"{delims.escape}{code}{delims.escape}")
    return out
