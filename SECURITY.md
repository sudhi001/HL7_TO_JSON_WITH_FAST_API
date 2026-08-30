# Security Policy

## Reporting a vulnerability

Email **support@sudhi.in**. Please do not open a public issue for a security
report, and please do not include real patient data in your report — send a
de-identified message that reproduces the problem.

We aim to acknowledge reports within 5 working days.

## What this tool does and does not do

This project parses HL7 v2 messages. HL7 v2 messages routinely contain
Protected Health Information (PHI), so the security properties that matter most
here are about **where message content goes**.

Architecturally true of this application:

- **No server-side persistence.** Message content is never written to a
  database, file, or cache on the server.
- **No outbound network calls at request time.** Parsing and field lookups are
  answered entirely from local data. The application does not contact any
  third-party service while handling a request.
- **No message content in logs.** Log records never include message bodies or
  field values.

How to verify each of these yourself:

- Persistence: `grep -rn "open(\|sqlite3.connect\|\.write(" app/` — no write
  path takes message content.
- Network: run the container with networking disabled; parsing must still work.
  Or watch outbound traffic while submitting a message.
- Logs: run with `--log-level debug`, submit a message, and grep the output for
  a field value from it.

## Scope and deployment

Software is neither "HIPAA-compliant" nor "non-compliant" — **deployments
are.** This project can be one component of a compliant workflow, but running
it does not by itself satisfy any regulatory obligation. You remain responsible
for transport security (TLS), access control, audit logging, and any Business
Associate Agreements your situation requires.

**Any public demo instance is for synthetic or de-identified test data only.**
For real patient data, run it yourself — that is what this project is for.

## Supported versions

Security fixes are applied to the latest release on the default branch.
