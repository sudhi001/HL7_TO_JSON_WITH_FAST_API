"""API surface: the v2 endpoints, and the deprecated one that must not change."""

import pytest
from fastapi.testclient import TestClient

import main
from tests.conftest import hdr, read_sample

MESSAGE = f"{hdr()}\rPID|1||MRN1^^^HOSP&1.2.3~MRN2||DOE^JOHN^Q||19800101|M\rOBX|1|NM|GLU||100\rOBX|2|NM|NA||140\r"


@pytest.fixture
def client():
    return TestClient(main.app, raise_server_exceptions=False)


def test_parse_returns_canonical_shape(client):
    r = client.post("/api/v2/parse", json={"message": MESSAGE})
    assert r.status_code == 200
    body = r.json()
    assert body["schemaVersion"] == 2
    assert body["meta"]["version"] == "2.5.1"
    assert body["meta"]["messageType"] == "ADT^A01"
    assert [s["id"] for s in body["segments"]] == ["MSH", "PID", "OBX", "OBX"]


def test_parse_simple_shape_keeps_segments_as_arrays(client):
    r = client.post("/api/v2/parse?shape=simple", json={"message": MESSAGE})
    body = r.json()
    # Always arrays, even MSH -- shape ambiguity was the old output's original sin.
    assert isinstance(body["MSH"], list)
    assert len(body["OBX"]) == 2


def test_non_hl7_input_is_422_not_500(client):
    r = client.post("/api/v2/parse", json={"message": "hello world"})
    assert r.status_code == 422
    assert "MSH" in r.json()["detail"]


def test_validate_reports_parse_diagnostics(client):
    r = client.post("/api/v2/validate", json={"message": MESSAGE.replace("\r", "\n")})
    body = r.json()
    assert any(d["code"] == "HL7W002" for d in body["diagnostics"])


def test_validate_flags_a_message_that_omits_required_segments(client):
    """MESSAGE is an ADT^A01 with no EVN or PV1, which the spec requires."""
    body = client.post("/api/v2/validate", json={"message": MESSAGE}).json()
    assert body["valid"] is False
    assert body["counts"]["error"] > 0
    assert any(d["code"] == "HL7E040" for d in body["diagnostics"])


def test_validate_passes_a_conformant_message(client):
    conformant = read_sample("adt_a01_admit.hl7")
    body = client.post("/api/v2/validate", json={"message": conformant}).json()
    assert body["valid"] is True
    assert body["counts"].get("error", 0) == 0


def test_validation_is_opt_in_on_parse(client):
    """The plain parse path must not pay for validation it was not asked for."""
    plain = client.post("/api/v2/parse", json={"message": MESSAGE}).json()
    checked = client.post("/api/v2/parse?validate=true", json={"message": MESSAGE}).json()
    assert len(checked["diagnostics"]) > len(plain["diagnostics"])


@pytest.mark.parametrize("payload", [{}, {"message": None}, {"message": 123}, {"message": ""}])
def test_bad_request_bodies_are_422_not_500(client, payload):
    for path in ("/api/v2/parse", "/convert/hl7/json"):
        r = client.post(path, json=payload)
        assert r.status_code == 422, f"{path} with {payload} -> {r.status_code}"


def test_oversized_body_is_rejected(client):
    r = client.post("/api/v2/parse", json={"message": "M" * 2_000_000})
    assert r.status_code == 422


def test_no_traceback_is_ever_leaked(client):
    for payload in ({}, {"message": "hello world"}, {"message": "M" * 2_000_000}):
        r = client.post("/api/v2/parse", json=payload)
        assert "Traceback" not in r.text
        assert 'File "' not in r.text


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_index_page_has_no_phi_persistence(client):
    """The page used to write pasted messages to the Cache Storage API."""
    body = client.get("/").text
    assert "caches.open" not in body
    assert "innerHTML" not in body


def test_security_headers_present(client):
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-frame-options"] == "DENY"


def test_csp_allows_no_external_origins(client):
    """The privacy claim is only a moat if the page cannot reach off-box."""
    csp = client.get("/").headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "http://" not in csp and "https://" not in csp


def test_page_references_no_third_party_hosts(client):
    body = client.get("/").text
    assert "unpkg.com" not in body
    assert "cdn." not in body


def test_samples_are_listed_and_fetchable(client):
    listing = client.get("/api/v2/samples").json()["samples"]
    assert len(listing) >= 6
    first = client.get(f"/api/v2/samples/{listing[0]['id']}").json()
    # Samples must keep CR terminators; LF would make them non-conformant.
    assert "\r" in first["message"]
    assert client.get("/api/v2/samples/does-not-exist").status_code == 404


def test_legacy_endpoint_still_works_and_advertises_deprecation(client):
    r = client.post("/convert/hl7/json", json={"message": MESSAGE.replace("\r", "\n")})
    assert r.status_code == 200
    assert r.headers["deprecation"] == "true"
    assert "sunset" in r.headers
    assert 'rel="successor-version"' in r.headers["link"]
    assert set(r.json()) == {"original", "detailed"}


def test_empty_sample_library_explains_itself(client, monkeypatch, tmp_path):
    """An empty dropdown must be diagnosable.

    An empty list with HTTP 200 looks identical to a working-but-empty library,
    which leaves a user with nothing to act on.
    """
    from app import samples

    monkeypatch.setattr(samples, "SAMPLES_DIR", tmp_path / "missing")
    samples.all_samples.cache_clear()
    try:
        body = client.get("/api/v2/samples").json()
        assert body["samples"] == []
        assert "problem" in body
        assert str(tmp_path / "missing") in body["problem"]
    finally:
        samples.all_samples.cache_clear()
