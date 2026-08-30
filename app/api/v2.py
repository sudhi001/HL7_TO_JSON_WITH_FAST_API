"""Version 2 of the HL7 parsing API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..parsing.parser import NotAnHL7Message, parse
from ..samples import all_samples, get as get_sample
from ..defs import store
from ..render import annotated, canonical, simple
from ..validate import validate as run_validation
from .models import ParseRequest, ParseResponse, Shape

router = APIRouter(prefix="/api/v2", tags=["v2"])


@router.post(
    "/parse",
    # response_model is deliberately not set: the two shapes return different
    # structures, and revalidating every response would cost time on the hot
    # path for no benefit. The canonical shape is documented via `responses`.
    response_model=None,
    responses={
        200: {"model": ParseResponse, "description": "Parsed message (canonical shape)."},
        422: {"description": "The input is not an HL7 v2 message."},
    },
    summary="Parse an HL7 v2 message",
)
def parse_message(
    payload: ParseRequest,
    shape: Shape = Query(
        Shape.CANONICAL,
        description="`canonical` is lossless; `simple` is a flatter projection "
        "that is easier to pipe into jq.",
    ),
    annotate: bool = Query(
        False,
        description="Attach field names, datatypes, optionality and decoded "
        "table values (PID-8 `M` becomes `Male`). Off by default so the plain "
        "parse path never touches the definition store.",
    ),
    validate: bool = Query(
        False,
        description="Also check the message against the specification and add "
        "the findings to `diagnostics`.",
    ),
) -> Any:
    try:
        message = parse(payload.message)
    except NotAnHL7Message as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if validate:
        message.diagnostics.extend(run_validation(message))

    if shape is Shape.SIMPLE:
        return simple.render(message)
    if annotate:
        return annotated.render(message)
    return canonical.render(message)


@router.post(
    "/validate",
    summary="Check a message against the HL7 specification",
    description=(
        "Reports required fields that are empty, values that are not valid for "
        "their datatype, non-repeating fields that repeat, unknown segments, and "
        "segments the trigger event requires but the message omits."
    ),
)
def validate_message(payload: ParseRequest) -> dict[str, Any]:
    try:
        message = parse(payload.message)
    except NotAnHL7Message as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    findings = message.diagnostics + run_validation(message)
    diagnostics = [
        {
            "severity": d.severity.value,
            "code": d.code,
            "message": d.message,
            **({"path": d.path} if d.path else {}),
        }
        for d in findings
    ]
    counts: dict[str, int] = {}
    for d in diagnostics:
        counts[d["severity"]] = counts.get(d["severity"], 0) + 1

    return {
        "valid": counts.get("error", 0) == 0,
        "counts": counts,
        "diagnostics": diagnostics,
    }


@router.get("/samples", summary="List the bundled sample messages")
def list_samples() -> dict[str, Any]:
    return {
        "samples": [
            {"id": s.id, "title": s.title, "description": s.description}
            for s in all_samples()
        ]
    }


@router.get("/samples/{sample_id}", summary="Fetch one sample message")
def read_sample(sample_id: str) -> dict[str, Any]:
    sample = get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=f"No sample named {sample_id!r}.")
    return {
        "id": sample.id,
        "title": sample.title,
        "description": sample.description,
        "message": sample.message,
    }


# --- Specification browsing -------------------------------------------------
# Reads the local definition store only. Nothing here reaches the network: a
# lookup keyed by the segments in someone's message would leak what they are
# inspecting, which is precisely what this tool exists to avoid.


def _require_version(version: str) -> str:
    resolved = store.resolve_version(version)
    if resolved is None:
        raise HTTPException(
            status_code=503,
            detail="The HL7 definition store is not present. Run "
            "`python tools/build_defs_db.py` to build it.",
        )
    return resolved


@router.get("/spec/versions", summary="HL7 versions covered by the definition store")
def spec_versions() -> dict[str, Any]:
    return {"versions": list(store.versions()), "source": store.metadata()}


@router.get("/spec/{version}/segments", summary="List segments for a version")
def spec_segments(version: str) -> dict[str, Any]:
    resolved = _require_version(version)
    return {
        "version": resolved,
        "segments": [
            {"id": s.id, "name": s.long_name} for s in store.list_segments(resolved)
        ],
    }


@router.get("/spec/{version}/segments/{segment_id}", summary="One segment and its fields")
def spec_segment(version: str, segment_id: str) -> dict[str, Any]:
    resolved = _require_version(version)
    segment_id = segment_id.upper()
    definition = store.segment_def(resolved, segment_id)
    if definition is None:
        raise HTTPException(
            status_code=404, detail=f"No segment {segment_id!r} in HL7 {resolved}."
        )
    return {
        "version": resolved,
        "id": definition.id,
        "name": definition.long_name,
        "fields": [
            {
                "position": f.position,
                "name": f.name,
                "dataType": f.datatype,
                "optionality": f.optionality,
                "required": f.required,
                "repeatable": f.repeatable,
                "maxRepeat": f.max_repeat,
                "length": f.length,
                "table": f.table_id,
            }
            for f in store.segment_fields(resolved, segment_id)
        ],
    }


@router.get("/spec/{version}/tables/{table_id}", summary="A code table and its values")
def spec_table(version: str, table_id: str) -> dict[str, Any]:
    resolved = _require_version(version)
    # Tables are commonly written zero-padded ('0001'); the store keys them bare.
    normalised = table_id.lstrip("0") or "0"
    definition, entries = store.code_table(resolved, normalised)
    if definition is None:
        raise HTTPException(
            status_code=404, detail=f"No table {table_id!r} in HL7 {resolved}."
        )
    return {
        "version": resolved,
        "id": definition.id,
        "name": definition.name,
        "entries": [{"value": v, "description": d} for v, d in entries],
    }


@router.get("/spec/{version}/datatypes/{datatype_id}", summary="A datatype and its components")
def spec_datatype(version: str, datatype_id: str) -> dict[str, Any]:
    resolved = _require_version(version)
    datatype_id = datatype_id.upper()
    definition = store.datatype_def(resolved, datatype_id)
    if definition is None:
        raise HTTPException(
            status_code=404, detail=f"No datatype {datatype_id!r} in HL7 {resolved}."
        )
    return {
        "version": resolved,
        "id": definition.id,
        "name": definition.name,
        "components": [
            {
                "position": c.position,
                "name": c.name,
                "dataType": c.datatype,
                "optionality": c.optionality,
                "length": c.length,
                "table": c.table_id,
            }
            for c in store.datatype_components(resolved, datatype_id)
        ],
    }
