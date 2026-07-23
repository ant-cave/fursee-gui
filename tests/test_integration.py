import io
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from fursee_api.api import pipeline as pipeline_mod
from fursee_api.core import database


@pytest.fixture(autouse=True)
def _patch_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", os.path.join(str(tmp_path), "test.db"))


@pytest.fixture(autouse=True)
def _init_task_manager():
    from fursee_api.core.task_manager import TaskManager
    from fursee_api.core.worker import set_task_manager, process_pipeline
    tm = TaskManager()
    tm.set_processor(process_pipeline)
    pipeline_mod.init(tm)
    set_task_manager(tm)
    yield


@pytest.fixture
def client():
    from fursee_api.main import app
    return TestClient(app)


def _make_jpeg_bytes(w=100, h=100):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (255, 0, 0)).save(buf, "JPEG")
    return buf.getvalue()


class TestPipelineFlow:
    def test_submit_and_track_task(self, client):
        resp = client.post("/api/pipeline/auto", json={})
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]
        resp = client.get(f"/api/pipeline/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == task_id
        assert data["type"] == "auto"

    def test_list_tasks(self, client):
        client.post("/api/pipeline/auto", json={})
        client.post("/api/pipeline/auto", json={"existing_run_id": "r1"})
        resp = client.get("/api/pipeline/tasks")
        assert resp.status_code == 200
        assert len(resp.json()["tasks"]) == 2


class TestDeletedEndpoints:
    def test_all_old_pipeline_endpoints_404(self, client):
        for ep in ("db", "classify", "similar", "identify"):
            resp = client.post(f"/api/pipeline/{ep}", json={})
            assert resp.status_code == 404, f"{ep} should return 404"

    def test_old_result_endpoints_404(self, client):
        for ep in ("classify", "similar", "identify"):
            resp = client.get(f"/api/results/{ep}")
            assert resp.status_code == 404, f"results/{ep} should return 404"


class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestQuota:
    def test_quota(self, client):
        resp = client.get("/api/quota")
        assert resp.status_code == 200
        data = resp.json()
        assert "ip" in data
        assert "upload_remaining" in data
        assert "task_remaining" in data
