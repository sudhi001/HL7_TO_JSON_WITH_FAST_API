# HL7 to JSON

A self-hosted HL7 v2 message parser. Paste a message, get structured JSON back —
without sending patient data to someone else's server.

## Why this exists

Most online HL7 parsers require you to paste a message into a website you don't
control. HL7 v2 messages routinely contain Protected Health Information, which
is exactly what your security team tells you not to do. This tool runs in your
own environment, so the message never leaves it.

The page makes **zero third-party requests** — CSS and JavaScript are served
from the same origin, and a Content-Security-Policy forbids any external origin.
It works with the network unplugged.

## Features

- Correct HL7 v2 parsing: CR terminators, field repetitions, components,
  subcomponents, escape sequences, and encoding characters read from MSH-2.
- **Field names and decoded codes** for every segment across HL7 v2.1-v2.7.1.
  `PID-8: M` reads as *Administrative Sex = Male*; `PV1-2: I` as *Inpatient*.
- Two output shapes: `canonical` (lossless) and `simple` (flat, jq-friendly).
- **Validation against the specification**: required fields that are empty,
  impossible dates, non-repeating fields that repeat, codes outside a closed HL7
  table, and segments the trigger event requires but the message omits.
- Diagnostics that explain what was wrong with a message instead of failing
  silently or throwing a 500.
- A library of sample messages, including edge cases, so you can start without
  supplying your own data.
- Nothing is stored, logged, or transmitted — see [SECURITY.md](SECURITY.md)
  for what that means precisely and how to verify it.

## Prerequisites

- Python 3.11 or newer. Tested on 3.11, 3.12 and 3.13 in CI, and on 3.14 locally.

## Installation

```bash
git clone https://github.com/sudhi001/HL7_TO_JSON_WITH_FAST_API.git
cd HL7_TO_JSON_WITH_FAST_API
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
uvicorn main:app
```

Then open <http://localhost:8000>.

For development with auto-reload, scope the watcher so it doesn't walk `.git/`
and your virtualenv:

```bash
uvicorn main:app --reload --reload-dir app --reload-dir templates
```

## API

**`POST /api/v2/parse`** — parse a message.
`?shape=canonical` (default) or `?shape=simple`.

```bash
curl -X POST http://localhost:8000/api/v2/parse \
  -H 'Content-Type: application/json' \
  -d '{"message": "MSH|^~\\&|SEND|FAC|RECV|RFAC|20240101120000||ADT^A01|MSG1|P|2.5.1\rPID|1||MRN1||DOE^JOHN||19800101|M"}'
```

Add `?annotate=true` to attach field names, datatypes, optionality and decoded
table values, and `?validate=true` to include specification findings.

**`POST /api/v2/validate`** — findings only, with a `valid` flag and counts by
severity. Findings are ordered most-severe first, deduplicated, and collapsed
after five of the same kind, so a 40-OBX result does not produce 40 identical
lines.
**`GET /api/v2/samples`**, **`GET /api/v2/samples/{id}`** — the sample library.

Browse the specification itself:

**`GET /api/v2/spec/versions`**
**`GET /api/v2/spec/{version}/segments`** and `.../segments/{id}`
**`GET /api/v2/spec/{version}/tables/{id}`**
**`GET /api/v2/spec/{version}/datatypes/{id}`**

**`GET /healthz`** — liveness.

Interactive docs at `/docs`.

### Deprecated

**`POST /convert/hl7/json`** still works and returns exactly what it always did,
including its defects (repeated segments overwrite each other; `~` and `^`
precedence is inverted). It cannot represent a repeating segment correctly by
construction. It sends `Deprecation` and `Sunset` headers — migrate to
`/api/v2/parse`.

## Output shapes

`canonical` preserves everything, including the difference between a field that
is absent (`||`), one that is explicitly nulled (`|""|`), and one containing a
space. Those mean different things in an update message.

`simple` is easier to read and pipe into `jq`. Segments are always arrays — even
`MSH` — so the shape never depends on the data.

## Security and compliance

Please read [SECURITY.md](SECURITY.md) before using this with real data.

In short: no server-side persistence, no outbound network calls, and no message
content in logs. But software is neither "HIPAA-compliant" nor "non-compliant" —
**deployments are.** Running this does not by itself satisfy any regulatory
obligation; TLS, access control, and audit logging remain yours to arrange.

**Any public demo instance is for synthetic or de-identified test data only.**
For real patient data, run it yourself.

## Definition store

Field names and code meanings come from `data/hl7defs.sqlite3` (2.8 MB,
committed), built from the MIT-licensed
[hl7-dictionary](https://github.com/fernandojsg/hl7-dictionary) dataset — see
[data/THIRD_PARTY_LICENSES.md](data/THIRD_PARTY_LICENSES.md). Rebuild it with:

```bash
make defs      # or: python tools/build_defs_db.py
```

It is opened lazily on first lookup and never at import, so it costs nothing at
startup — `make bench-startup` asserts this. If the file is missing the
application still starts and parses; it just serves un-annotated output.

## Development

```bash
make install
make test
```

The test suite pins each historical parsing defect with a named regression test,
and uses [hl7apy](https://github.com/crs4/hl7apy) as a differential oracle to
check the tokeniser against an independent implementation.

## Validation

Severity means something specific:

| Severity | Meaning |
|---|---|
| `error` | Unambiguously wrong — a required field is empty, a date is not a real date, a non-repeating field repeats, a value is outside a closed HL7 table. |
| `warning` | Probably wrong, but real interfaces do it — a value longer than the spec allows, a field beyond the segment definition. |
| `info` | Worth knowing, not a defect — Z-segments, values outside a site-defined table. |

Two checks are deliberately **not** implemented, because a validator that fires
on valid messages is worse than none:

- **Unlisted values in user-defined tables** are reported as `info`, not `error`.
  HL7 tables are either closed (an unlisted code really is wrong) or
  site-specific (Race, Religion, Marital Status). The bundled dataset does not
  record which, so only a short list of tables known to be closed is enforced.
- **Segment ordering and group cardinality** are not checked. Resolving nested
  optional groups correctly is genuinely ambiguous, and a wrong answer there is
  worse than no answer. Only segments a required group genuinely requires are
  reported as missing.

## Roadmap

- Message diff, de-identify mode, and batch file processing.
- Optional Caristix enrichment, which adds prose field descriptions and the
  `tableType` flag that would make the closed-table check complete.

## Contributing

Bug reports are welcome. **Please only paste de-identified messages** into
issues — replace names, identifiers, and dates before sharing.

## Contact

- Email: support@sudhi.in
- GitHub: [sudhi001](https://github.com/sudhi001)

## License

MIT — see [LICENSE](LICENSE).
