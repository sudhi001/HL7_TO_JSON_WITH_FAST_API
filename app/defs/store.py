"""Read-only access to the HL7 definition store.

Two rules hold this together, and ``tests/test_defs_store.py`` enforces both:

1. **Nothing happens at import time.** The connection is opened on the first
   query and never before, so shipping 2.8 MB of definitions costs no startup
   time. This is the entire reason the store is SQLite rather than JSON.
2. **A missing store is not an error.** Parsing must never depend on
   definitions. If the file is absent or unreadable, every lookup returns
   ``None`` and the application serves un-annotated output.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
import zlib
from functools import lru_cache
from pathlib import Path

from .models import CodeTableDef, ComponentDef, DataTypeDef, FieldDef, SegmentDef

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "hl7defs.sqlite3"

# Sentinel version for data shared across all HL7 versions (the code tables).
SHARED = "*"

# sqlite3 connections cannot be shared between threads, and FastAPI runs sync
# endpoints in a threadpool, so each thread gets its own.
_local = threading.local()
_unavailable = False


def _connect() -> sqlite3.Connection | None:
    global _unavailable
    if _unavailable:
        return None

    connection = getattr(_local, "connection", None)
    if connection is not None:
        return connection

    if not DB_PATH.exists():
        _unavailable = True
        return None

    try:
        # immutable=1 promises the file will not change, which lets SQLite skip
        # all locking. Safe for a build artifact, and faster.
        connection = sqlite3.connect(
            f"file:{DB_PATH}?mode=ro&immutable=1", uri=True, check_same_thread=False
        )
        connection.row_factory = sqlite3.Row
        connection.execute("SELECT 1 FROM meta LIMIT 1")
    except sqlite3.Error:
        _unavailable = True
        return None

    _local.connection = connection
    return connection


def available() -> bool:
    """Whether definitions can be served. Never raises."""
    return _connect() is not None


def _query(sql: str, params: tuple) -> list[sqlite3.Row]:
    connection = _connect()
    if connection is None:
        return []
    try:
        return connection.execute(sql, params).fetchall()
    except sqlite3.Error:
        return []


@lru_cache(maxsize=1)
def metadata() -> dict[str, str]:
    return {row["key"]: row["value"] for row in _query("SELECT key, value FROM meta", ())}


@lru_cache(maxsize=1)
def versions() -> tuple[str, ...]:
    return tuple(r["code"] for r in _query("SELECT code FROM version ORDER BY ord", ()))


def resolve_version(version: str | None) -> str | None:
    """Pick the closest stored version.

    The store covers 2.1-2.7.1. A message declaring 2.8 should still get useful
    field names rather than nothing, so it falls back to the newest version we
    have rather than failing.
    """
    known = versions()
    if not known:
        return None
    if version in known:
        return version
    if version is None:
        return known[-1]
    # Longest matching prefix, e.g. '2.5.1' -> '2.5'; otherwise newest.
    candidates = [v for v in known if version.startswith(v) or v.startswith(version)]
    return max(candidates, key=len) if candidates else known[-1]


@lru_cache(maxsize=512)
def segment_def(version: str, segment_id: str) -> SegmentDef | None:
    rows = _query(
        "SELECT id, long_name, description FROM segment WHERE version=? AND id=?",
        (version, segment_id),
    )
    if not rows:
        return None
    row = rows[0]
    return SegmentDef(row["id"], row["long_name"], row["description"])


@lru_cache(maxsize=2048)
def field_def(version: str, segment_id: str, position: int) -> FieldDef | None:
    rows = _query(
        "SELECT segment_id, position, name, datatype, optionality, repeatable,"
        " max_repeat, length, table_id, description FROM segment_field"
        " WHERE version=? AND segment_id=? AND position=?",
        (version, segment_id, position),
    )
    if not rows:
        return None
    r = rows[0]
    return FieldDef(
        r["segment_id"], r["position"], r["name"], r["datatype"], r["optionality"],
        bool(r["repeatable"]), r["max_repeat"], r["length"], r["table_id"], r["description"],
    )


@lru_cache(maxsize=512)
def segment_fields(version: str, segment_id: str) -> tuple[FieldDef, ...]:
    rows = _query(
        "SELECT segment_id, position, name, datatype, optionality, repeatable,"
        " max_repeat, length, table_id, description FROM segment_field"
        " WHERE version=? AND segment_id=? ORDER BY position",
        (version, segment_id),
    )
    return tuple(
        FieldDef(
            r["segment_id"], r["position"], r["name"], r["datatype"], r["optionality"],
            bool(r["repeatable"]), r["max_repeat"], r["length"], r["table_id"], r["description"],
        )
        for r in rows
    )


@lru_cache(maxsize=512)
def datatype_def(version: str, datatype_id: str) -> DataTypeDef | None:
    rows = _query(
        "SELECT id, name, description FROM datatype WHERE version=? AND id=?",
        (version, datatype_id),
    )
    if not rows:
        return None
    r = rows[0]
    return DataTypeDef(r["id"], r["name"], r["description"])


@lru_cache(maxsize=512)
def datatype_components(version: str, datatype_id: str) -> tuple[ComponentDef, ...]:
    rows = _query(
        "SELECT datatype_id, position, name, datatype, optionality, length, table_id"
        " FROM datatype_component WHERE version=? AND datatype_id=? ORDER BY position",
        (version, datatype_id),
    )
    return tuple(
        ComponentDef(
            r["datatype_id"], r["position"], r["name"], r["datatype"],
            r["optionality"], r["length"], r["table_id"],
        )
        for r in rows
    )


@lru_cache(maxsize=1024)
def code_meaning(version: str, table_id: str, value: str) -> str | None:
    """Decode a coded value: PID-8 'M' -> 'Male'.

    This is the half hl7apy does not have -- it knows which codes are legal in a
    field, not what they mean.
    """
    rows = _query(
        "SELECT description FROM code_entry WHERE version IN (?, ?) AND table_id=? AND value=?"
        " ORDER BY version DESC LIMIT 1",
        (version, SHARED, table_id, value),
    )
    return rows[0]["description"] if rows else None


@lru_cache(maxsize=512)
def code_table(version: str, table_id: str) -> tuple[CodeTableDef | None, tuple[tuple[str, str], ...]]:
    header = _query(
        "SELECT id, name FROM code_table WHERE version IN (?, ?) AND id=?"
        " ORDER BY version DESC LIMIT 1",
        (version, SHARED, table_id),
    )
    entries = _query(
        "SELECT value, description FROM code_entry WHERE version IN (?, ?) AND table_id=?"
        " ORDER BY value",
        (version, SHARED, table_id),
    )
    definition = CodeTableDef(header[0]["id"], header[0]["name"]) if header else None
    return definition, tuple((r["value"], r["description"]) for r in entries)


@lru_cache(maxsize=256)
def trigger_event(version: str, event_id: str) -> dict | None:
    rows = _query(
        "SELECT description, structure_json FROM trigger_event WHERE version=? AND id=?",
        (version, event_id),
    )
    if not rows:
        return None
    raw = rows[0]["structure_json"]
    try:
        structure = json.loads(zlib.decompress(raw).decode("utf-8"))
    except (zlib.error, ValueError, TypeError):
        return None
    return {"id": event_id, "description": rows[0]["description"], "structure": structure}


@lru_cache(maxsize=64)
def list_segments(version: str) -> tuple[SegmentDef, ...]:
    rows = _query(
        "SELECT id, long_name, description FROM segment WHERE version=? ORDER BY id", (version,)
    )
    return tuple(SegmentDef(r["id"], r["long_name"], r["description"]) for r in rows)


def reset_for_tests() -> None:
    """Drop cached state so a test can simulate a missing or replaced store."""
    global _unavailable
    _unavailable = False
    if hasattr(_local, "connection"):
        with contextlib.suppress(sqlite3.Error):
            _local.connection.close()
        del _local.connection
    for fn in (
        metadata, versions, segment_def, field_def, segment_fields, datatype_def,
        datatype_components, code_meaning, code_table, trigger_event, list_segments,
    ):
        fn.cache_clear()
