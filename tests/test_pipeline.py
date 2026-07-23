import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fursee_api.api import pipeline as pipeline_mod


@pytest.fixture(autouse=True)
def _patch_db_path(monkeypatch):
    from fursee_api.core import database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    monkeypatch.setattr(database, "DB_PATH", tmp)
    yield
    os.unlink(tmp)


@pytest.fixture(autouse=True)
def _init_task_manager():
    from fursee_api.core.task_manager import TaskManager
    from fursee_api.core.worker import set_task_manager, process_pipeline
    tm = TaskManager()
    tm.set_processor(process_pipeline)
    pipeline_mod.init(tm)
    set_task_manager(tm)
    yield


class TestAutoEndpoint:
    def test_auto_endpoint_returns_task_id(self, client):
        resp = client.post("/api/pipeline/auto", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data

    def test_auto_with_existing_run_id(self, client):
        resp = client.post("/api/pipeline/auto", json={"existing_run_id": "run_001"})
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data

    def test_auto_with_fingerprint_header(self, client):
        resp = client.post(
            "/api/pipeline/auto",
            json={"existing_run_id": "run_001"},
            headers={"X-Fingerprint": "abc123"},
        )
        assert resp.status_code == 200

    def test_auto_invalid_body_still_ok_with_defaults(self, client):
        resp = client.post("/api/pipeline/auto", json={"conf": 0.8, "eps_start": 0.5})
        assert resp.status_code == 200

    def test_auto_endpoint_rejects_bad_type(self, client):
        resp = client.post("/api/pipeline/auto", json={"conf": "not_a_number"})
        assert resp.status_code == 422


class TestTaskEndpoints:
    def test_list_tasks(self, client):
        resp = client.get("/api/pipeline/tasks")
        assert resp.status_code == 200
        assert "tasks" in resp.json()

    def test_get_nonexistent_task(self, client):
        resp = client.get("/api/pipeline/tasks/nonexistent")
        assert resp.status_code == 404


class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
