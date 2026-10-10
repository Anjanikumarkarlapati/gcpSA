import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ETL_DATA_DIR", str(tmp_path))
    import importlib
    from app import db, etl, main, sources
    for m in (db, sources, etl, main):
        importlib.reload(m)
    with TestClient(main.app) as c:
        yield c


def wait(client, run_id):
    for _ in range(100):
        r = client.get(f"/api/runs/{run_id}").json()
        if r["status"] != "running":
            return r
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_success_and_idempotent(client):
    r1 = wait(client, client.post("/api/runs", json={"batch_id": "2026-10-10"}).json()["run_id"])
    assert r1["status"] == "success"
    assert all(t["status"] == "success" for t in r1["tasks"])
    n1 = client.get("/api/stats").json()["curated_rows"]
    assert n1 == 180  # 60 valid per source; dup, null key and bad date quarantined
    r2 = wait(client, client.post("/api/runs", json={"batch_id": "2026-10-10"}).json()["run_id"])
    assert r2["status"] == "success"
    assert client.get("/api/stats").json()["curated_rows"] == n1  # rerun creates no duplicates
    assert client.get("/api/quarantine").json()


def test_source_failure_isolated(client):
    r = wait(client, client.post("/api/runs", json={"batch_id": "2026-10-11", "fail_source": "source2"}).json()["run_id"])
    st = {t["task_id"]: t["status"] for t in r["tasks"]}
    assert r["status"] == "failed"
    assert st["load_source_1_raw"] == st["load_source_3_raw"] == "success"
    assert st["validate_source_2"] == "failed"
    assert st["merge_into_curated_table"] == "upstream_failed"
    assert client.get("/api/stats").json()["curated_rows"] == 0


def test_bad_input(client):
    assert client.post("/api/runs", json={"batch_id": "nope"}).status_code == 422
    assert client.get("/api/runs/missing").status_code == 404
