"""API tests for the page, the sample, and POST /check (AC-015, AC-019)."""

from fastapi.testclient import TestClient

from vouch.app import app

client = TestClient(app)


def test_page_is_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>Vouch</title>" in r.text


def test_sample_endpoint_returns_both_files():
    s = client.get("/sample").json()
    assert s["draft"].startswith("Falcon Pay") and "Founded: 2019" in s["facts"]


def test_check_returns_the_spec_shape_with_offsets_into_the_draft():
    s = client.get("/sample").json()
    r = client.post("/check", json=s).json()
    assert set(r) == {"claims", "summary", "approvable", "model_used", "warnings"}
    for c in r["claims"]:
        assert s["draft"][c["start"] : c["end"]] == c["text"]
    assert r["summary"]["checked"] == 3
    assert r["approvable"] is False


def test_missing_field_is_rejected():
    assert client.post("/check", json={"draft": "x"}).status_code == 422
