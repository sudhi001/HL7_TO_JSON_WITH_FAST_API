-- HL7 v2 definition store.
--
-- SQLite because it is the only option that answers a single question without
-- reading the whole file: sqlite3.connect() performs no I/O until the first
-- query, so shipping megabytes of definitions costs nothing at startup. A JSON
-- blob would have to be parsed in full before it could answer "what is PID.8",
-- moving hundreds of milliseconds onto the first request. sqlite3 is also in
-- the standard library, so this adds no dependency.
--
-- WITHOUT ROWID on the composite-key tables makes the primary key the covering
-- index, which shrinks the file and makes point lookups a single B-tree seek.

PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
) WITHOUT ROWID;

CREATE TABLE version (
    code  TEXT PRIMARY KEY,
    ord   INTEGER NOT NULL
) WITHOUT ROWID;

CREATE TABLE segment (
    version     TEXT NOT NULL,
    id          TEXT NOT NULL,
    long_name   TEXT,
    description TEXT,
    source      TEXT NOT NULL DEFAULT 'dict',
    PRIMARY KEY (version, id)
) WITHOUT ROWID;

CREATE TABLE segment_field (
    version     TEXT NOT NULL,
    segment_id  TEXT NOT NULL,
    position    INTEGER NOT NULL,
    name        TEXT,
    datatype    TEXT,
    optionality TEXT,          -- 'R' required, 'O' optional, 'C' conditional, 'B' backward
    repeatable  INTEGER,       -- 1 if the field may repeat
    max_repeat  TEXT,          -- '*' when unbounded, else a count
    length      INTEGER,
    table_id    TEXT,
    description TEXT,
    source      TEXT NOT NULL DEFAULT 'dict',
    PRIMARY KEY (version, segment_id, position)
) WITHOUT ROWID;

CREATE TABLE datatype (
    version     TEXT NOT NULL,
    id          TEXT NOT NULL,
    name        TEXT,
    description TEXT,
    source      TEXT NOT NULL DEFAULT 'dict',
    PRIMARY KEY (version, id)
) WITHOUT ROWID;

CREATE TABLE datatype_component (
    version      TEXT NOT NULL,
    datatype_id  TEXT NOT NULL,
    position     INTEGER NOT NULL,
    name         TEXT,
    datatype     TEXT,
    optionality  TEXT,
    length       INTEGER,
    table_id     TEXT,
    source       TEXT NOT NULL DEFAULT 'dict',
    PRIMARY KEY (version, datatype_id, position)
) WITHOUT ROWID;

CREATE TABLE code_table (
    version TEXT NOT NULL,
    id      TEXT NOT NULL,
    name    TEXT,
    source  TEXT NOT NULL DEFAULT 'dict',
    PRIMARY KEY (version, id)
) WITHOUT ROWID;

-- The reason this store exists. hl7apy knows which codes are legal in a field;
-- it does not know that 'M' means 'Male'. This table is that missing half.
CREATE TABLE code_entry (
    version     TEXT NOT NULL,
    table_id    TEXT NOT NULL,
    value       TEXT NOT NULL,
    description TEXT,
    source      TEXT NOT NULL DEFAULT 'dict',
    PRIMARY KEY (version, table_id, value)
) WITHOUT ROWID;

CREATE TABLE trigger_event (
    version        TEXT NOT NULL,
    id             TEXT NOT NULL,
    description    TEXT,
    structure_json BLOB,   -- deflated JSON; see tools/build_defs_db.py
    source         TEXT NOT NULL DEFAULT 'dict',
    PRIMARY KEY (version, id)
) WITHOUT ROWID;
