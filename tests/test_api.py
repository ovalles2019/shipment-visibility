from pathlib import Path

from app.status_codes import bucket_for

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_ingest_requires_key(client):
    res = client.post("/api/ingest/edi214", json={"content": "ST*214*1~B10*A*B*C~AT7*X6****20260101*0100~"})
    assert res.status_code == 401


def test_ingest_and_list(client):
    raw = (SAMPLES / "03_carrier_delay.edi").read_text()
    res = client.post(
        "/api/ingest/edi214",
        json={"content": raw, "filename": "delay.edi"},
        headers={"X-API-Key": "teaching-demo-key"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["events_added"] == 3
    assert body["delay_alerts"] >= 1
    assert body["shipment"]["pro_number"] == "RT70018"
    assert body["shipment"]["bucket"] == "delayed"

    listed = client.get("/api/shipments?bucket=delayed").json()
    assert any(s["pro_number"] == "RT70018" for s in listed)

    detail = client.get(f"/api/shipments/{body['shipment']['id']}").json()
    assert len(detail["events"]) == 3
    assert detail["notifications"]


def test_duplicate_ingest_is_idempotent(client):
    raw = (SAMPLES / "05_new_pickup.edi").read_text()
    headers = {"X-API-Key": "teaching-demo-key"}
    first = client.post("/api/ingest/edi214", json={"content": raw}, headers=headers).json()
    second = client.post("/api/ingest/edi214", json={"content": raw}, headers=headers).json()
    assert first["shipment"]["id"] == second["shipment"]["id"]
    assert second["events_added"] == 0


def test_bucket_helpers():
    assert bucket_for("D1") == "delivered"
    assert bucket_for("X6", overdue=True) == "delayed"
    assert bucket_for("A9") == "delayed"
