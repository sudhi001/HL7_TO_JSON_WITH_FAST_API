# Third-party data

## hl7-dictionary

The HL7 v2 definition store (`data/hl7defs.sqlite3`) is built from
[hl7-dictionary](https://github.com/fernandojsg/hl7-dictionary) by Fernando
Serrano, used under the MIT License. It covers HL7 v2.1 through v2.7.1:
segment and field definitions, datatypes, code tables, and message structures.

Rebuild it with:

```bash
python tools/build_defs_db.py
```

The intermediate JavaScript sources are downloaded to `data/vendor/` at build
time and are **not** committed — they are roughly 15 MB, and the built database
is 2.8 MB. Only the built database ships, which is what keeps the application
fully offline at runtime.

### A note on the `opt` field

The upstream README documents `opt` as `0 = Optional, 1 = Required`. The shipped
data uses `1` and `2`, and checking fields whose optionality is unambiguous in
the published v2.5.1 specification (MSH-7, MSH-10, MSH-11, MSH-12, PID-3, PID-5,
EVN-2, PV1-2, OBR-4, ORC-1, and others) shows the data means
`1 = Optional, 2 = Required`. The builder follows the data, not the README;
`tests/test_defs_store.py` pins this against the specification.

## HL7 v2 standard

HL7 v2 content is copyright Health Level Seven International. HL7 has licensed
its standards at no cost since 2013, but retains copyright. HL7 and FHIR are
registered trademarks of Health Level Seven International.

This project is not affiliated with or endorsed by HL7 International.
