"""Message validation against the HL7 specification.

Design rule: **a validator that cries wolf is worse than none.** An analyst who
learns to ignore the output has gained nothing. So every check here has to be
defensible against a real-world message, and anything ambiguous is reported at a
lower severity or not at all:

* ``error``   - unambiguously wrong: a required field is empty, a date is not a
                real date, a non-repeating field repeats.
* ``warning`` - probably wrong, but real interfaces do it: a value longer than
                the spec allows, a field beyond the segment definition.
* ``info``    - worth knowing, not a defect: Z-segments, unknown segments.

Checks that cannot be made reliable with the current data are deliberately
omitted rather than shipped noisy. See ``codes.py``.
"""

from __future__ import annotations

from ..parsing.models import Diagnostic, Message, Severity
from . import codes, datatypes, structure, structural

# Above this many findings sharing one code, the rest are replaced by a single
# summary line. A lab result with 40 OBX segments should not produce 40 copies
# of the same observation -- that is how a validator gets ignored.
COLLAPSE_AFTER = 5

_SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def _deduplicate(found: list[Diagnostic]) -> list[Diagnostic]:
    seen: set[tuple[str, str | None, str]] = set()
    unique = []
    for diagnostic in found:
        key = (diagnostic.code, diagnostic.path, diagnostic.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(diagnostic)
    return unique


def _collapse(found: list[Diagnostic]) -> list[Diagnostic]:
    by_code: dict[str, list[Diagnostic]] = {}
    for diagnostic in found:
        by_code.setdefault(diagnostic.code, []).append(diagnostic)

    out: list[Diagnostic] = []
    summaries: list[Diagnostic] = []
    for code, group in by_code.items():
        out.extend(group[:COLLAPSE_AFTER])
        remaining = len(group) - COLLAPSE_AFTER
        if remaining > 0:
            summaries.append(
                Diagnostic(
                    group[0].severity, code,
                    f"... and {remaining} more of the same ({code}), at "
                    + ", ".join(d.path or "?" for d in group[COLLAPSE_AFTER:][:6])
                    + ("..." if remaining > 6 else "") + ".",
                )
            )
    out.extend(summaries)
    return out


def validate(message: Message) -> list[Diagnostic]:
    """Run every check. Never raises; an unknown segment simply yields no checks."""
    found: list[Diagnostic] = []
    for check in (
        structural.check,
        datatypes.check,
        codes.check,
        structure.check,
    ):
        try:
            found.extend(check(message))
        except Exception:  # a broken check must never break parsing
            continue

    found = _collapse(_deduplicate(found))
    # Most severe first: an analyst should see the errors without scrolling.
    found.sort(key=lambda d: _SEVERITY_ORDER.get(d.severity, 3))
    return found


__all__ = ["validate"]
