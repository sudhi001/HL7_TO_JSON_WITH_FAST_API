#!/usr/bin/env python3
"""Build the HL7 definition store from the MIT-licensed hl7-dictionary dataset.

Run at build time, never at request time:

    python tools/build_defs_db.py

The vendored JavaScript is not committed (it is ~15 MB); the built SQLite file
is. That keeps the repository small while the *runtime* stays fully offline,
which is what the privacy claim actually requires.

Source: https://github.com/fernandojsg/hl7-dictionary (MIT), covering HL7 v2.1
through v2.7.1. See data/THIRD_PARTY_LICENSES.md.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import zlib
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "data" / "vendor" / "hl7-dictionary" / "lib"
OUTPUT = ROOT / "data" / "hl7defs.sqlite3"
SCHEMA = ROOT / "app" / "defs" / "schema.sql"

PACKAGE = "hl7-dictionary@1.0.1"
BASE_URL = f"https://unpkg.com/{PACKAGE}"
VERSIONS = ["2.1", "2.2", "2.3", "2.3.1", "2.4", "2.5", "2.5.1", "2.6", "2.7", "2.7.1"]

# The package README documents opt as 0=Optional / 1=Required. The shipped data
# uses 1 and 2, and checking 16 fields whose optionality is unambiguous in the
# published v2.5.1 spec (MSH-7/10/11/12, PID-3/5, EVN-2, PV1-2, OBR-4, ORC-1 ...)
# shows the data means 1=Optional, 2=Required. Trusting the README would invert
# every flag in the store, so the data wins.
OPTIONALITY = {1: "O", 2: "R"}

# Sentinel "version" for data that is shared across all versions.
SHARED = "*"


def fetch(path: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return
    url = f"{BASE_URL}/{path}"
    print(f"  fetching {path}")
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            destination.write_bytes(response.read())
    except urllib.error.URLError as exc:
        raise SystemExit(f"Could not fetch {url}: {exc}") from exc


def download_all() -> None:
    fetch("lib/tables.js", VENDOR / "tables.js")
    for version in VERSIONS:
        for name in ("segments", "fields", "messages"):
            fetch(f"lib/{version}/{name}.js", VENDOR / version / f"{name}.js")


def load_js(path: Path) -> dict:
    """Read a ``var X = {...};`` module.

    The payload is plain JSON, so this needs no JavaScript engine -- which keeps
    Node out of the build entirely.
    """
    text = path.read_text()
    start = text.index("{", text.index("="))
    end = text.rindex("};") + 1
    return json.loads(text[start:end])


def build(connection: sqlite3.Connection) -> dict[str, int]:
    counts = dict.fromkeys(
        ("segment", "field", "datatype", "component", "table", "code", "event"), 0
    )

    tables = load_js(VENDOR / "tables.js")

    # The dataset ships one shared table set, byte-identical for every version
    # (verified). Storing it ten times cost 2 MB for no information. SHARED is a
    # sentinel version the store falls back to, so a later per-version Caristix
    # override still takes precedence.
    for table_id, table in tables.items():
        connection.execute(
            "INSERT INTO code_table (version, id, name) VALUES (?,?,?)",
            (SHARED, table_id, table.get("desc")),
        )
        counts["table"] += 1
        for value, description in (table.get("values") or {}).items():
            connection.execute(
                "INSERT OR IGNORE INTO code_entry (version, table_id, value, description)"
                " VALUES (?,?,?,?)",
                (SHARED, table_id, value, description),
            )
            counts["code"] += 1

    for ordinal, version in enumerate(VERSIONS):
        segments = load_js(VENDOR / version / "segments.js")
        datatypes = load_js(VENDOR / version / "fields.js")
        messages = load_js(VENDOR / version / "messages.js")

        connection.execute("INSERT INTO version (code, ord) VALUES (?, ?)", (version, ordinal))

        for seg_id, seg in segments.items():
            connection.execute(
                "INSERT INTO segment (version, id, long_name, description) VALUES (?,?,?,?)",
                (version, seg_id, seg.get("desc"), seg.get("desc")),
            )
            counts["segment"] += 1
            for position, field in enumerate(seg.get("fields", []), start=1):
                repeat = field.get("rep")
                connection.execute(
                    "INSERT INTO segment_field (version, segment_id, position, name, datatype,"
                    " optionality, repeatable, max_repeat, length, table_id, description)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        version, seg_id, position,
                        field.get("desc"),
                        field.get("datatype"),
                        OPTIONALITY.get(field.get("opt")),
                        1 if repeat != 1 else 0,
                        "*" if repeat == 0 else str(repeat),
                        field.get("len"),
                        str(field["table"]) if field.get("table") else None,
                        field.get("desc"),
                    ),
                )
                counts["field"] += 1

        for dt_id, datatype in datatypes.items():
            connection.execute(
                "INSERT INTO datatype (version, id, name, description) VALUES (?,?,?,?)",
                (version, dt_id, datatype.get("desc"), datatype.get("desc")),
            )
            counts["datatype"] += 1
            for position, component in enumerate(datatype.get("subfields", []), start=1):
                connection.execute(
                    "INSERT INTO datatype_component (version, datatype_id, position, name,"
                    " datatype, optionality, length, table_id) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        version, dt_id, position,
                        component.get("desc"),
                        component.get("datatype"),
                        OPTIONALITY.get(component.get("opt")),
                        component.get("len"),
                        str(component["table"]) if component.get("table") else None,
                    ),
                )
                counts["component"] += 1

        for event_id, message in messages.items():
            # Deflated: these structures are ~5 MB of highly repetitive JSON
            # uncompressed, and they are only read when validating a message
            # against its trigger event.
            structure = json.dumps(message.get("segments", {}), separators=(",", ":"))
            connection.execute(
                "INSERT INTO trigger_event (version, id, description, structure_json)"
                " VALUES (?,?,?,?)",
                (version, event_id, message.get("desc"),
                 zlib.compress(structure.encode("utf-8"), 9)),
            )
            counts["event"] += 1

        print(f"  {version:<6} {len(segments):>4} segments  {len(datatypes):>3} datatypes  {len(messages):>4} messages")

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    if not args.skip_download:
        print("Downloading hl7-dictionary...")
        download_all()

    missing = [v for v in VERSIONS if not (VENDOR / v / "segments.js").exists()]
    if missing:
        raise SystemExit(f"Missing vendored data for: {', '.join(missing)}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()

    print(f"Building {args.output.relative_to(ROOT)}...")
    connection = sqlite3.connect(args.output)
    try:
        connection.executescript(SCHEMA.read_text())
        counts = build(connection)
        for key, value in {
            "schema_version": "1",
            "source": PACKAGE,
            "source_url": "https://github.com/fernandojsg/hl7-dictionary",
            "source_license": "MIT",
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "versions": ",".join(VERSIONS),
            "enriched": "0",
        }.items():
            connection.execute("INSERT INTO meta (key, value) VALUES (?,?)", (key, value))
        connection.commit()
        connection.execute("VACUUM")
        connection.commit()
    finally:
        connection.close()

    size = args.output.stat().st_size
    print(f"\nDone. {size / 1_048_576:.1f} MB")
    for key, value in counts.items():
        print(f"  {key + 's':<12} {value:>7,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
