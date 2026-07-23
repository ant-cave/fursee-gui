import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from fursee_api.core import database


@pytest.fixture
def client():
    from fursee_api.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _patch_db_path(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    monkeypatch.setattr(database, "DB_PATH", tmp)
    yield
    os.unlink(tmp)


def _make_fake_output(root: str, run_id: str, groups: list[str]):
    for g in groups:
        d = os.path.join(root, run_id, g)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "pic.jpg"), "w") as f:
            f.write("fake")


class TestListAutoResults:
    def test_list_empty(self, client):
        resp = client.get("/api/results/auto")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["runs"] == []

    def test_list_after_adding_run(self, client):
        database.add_run("run_001", 1000.0, [], 0)
        resp = client.get("/api/results/auto")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["runs"][0]["run_id"] == "run_001"


class TestGetAutoRun:
    def test_get_run(self, client):
        database.add_run("run_001", 1000.0, [{"name": "组_1", "image_count": 2, "images": ["a.jpg"]}], 2)
        resp = client.get("/api/results/auto/run/run_001")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run_001"

    def test_get_nonexistent_run(self, client):
        resp = client.get("/api/results/auto/run/no_such_run")
        assert resp.status_code == 404


class TestDeleteAutoRun:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, tmp_path):
        self.auto_root = tmp_path / "auto_results"
        self.auto_root.mkdir()
        monkeypatch.setattr("fursee_api.api.results.AUTO_ROOT", str(self.auto_root))

    def _buf_path(self, name: str) -> str:
        return os.path.join(os.getcwd(), "buffer", "auto", name)

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/results/auto/run/no_such_run")
        assert resp.status_code == 404

    def test_delete_run_removes_output_dir(self, client):
        database.add_run("r1", 1000.0, [], 0, buffer_path="")
        _make_fake_output(str(self.auto_root), "r1", ["组_1"])
        resp = client.delete("/api/results/auto/run/r1")
        assert resp.status_code == 200
        assert not (self.auto_root / "r1").exists()

    def test_delete_run_rejects_invalid_buffer_path(self, client):
        database.add_run("run_001", 1000.0, [], 0, buffer_path="/etc/passwd")
        resp = client.delete("/api/results/auto/run/run_001")
        assert resp.status_code == 400

    def test_delete_run_removes_buffer_within_buffer_root(self, client):
        buf = self._buf_path("run_buf")
        os.makedirs(buf, exist_ok=True)
        database.add_run("r2", 1000.0, [], 0, buffer_path=buf)
        _make_fake_output(str(self.auto_root), "r2", ["组_1"])
        resp = client.delete("/api/results/auto/run/r2")
        assert resp.status_code == 200
        assert not os.path.isdir(buf)

    def test_delete_run_removes_from_db(self, client):
        database.add_run("r1", 1000.0, [], 0)
        client.delete("/api/results/auto/run/r1")
        assert database.get_run("r1") is None

    def test_delete_empty_buffer_path(self, client):
        database.add_run("r1", 1000.0, [], 0, buffer_path="")
        resp = client.delete("/api/results/auto/run/r1")
        assert resp.status_code == 200

    def test_delete_nonexistent_buffer_path_skipped(self, client):
        buf = self._buf_path("noexist_buf")
        database.add_run("r3", 1000.0, [], 0, buffer_path=buf)
        _make_fake_output(str(self.auto_root), "r3", ["组_1"])
        resp = client.delete("/api/results/auto/run/r3")
        assert resp.status_code == 200


class TestAutoRunImage:
    def test_get_image_in_run(self, client, monkeypatch, tmp_path):
        auto_root = tmp_path / "auto_results"
        auto_root.mkdir()
        monkeypatch.setattr("fursee_api.api.results.AUTO_ROOT", str(auto_root))
        database.add_run("r1", 0.0, [{"name": "组_1", "image_count": 1, "images": ["pic.jpg"]}], 1)
        _make_fake_output(str(auto_root), "r1", ["组_1"])
        resp = client.get("/api/results/auto/run/r1/image/组_1/pic.jpg")
        assert resp.status_code == 200

    def test_get_image_nonexistent(self, client):
        resp = client.get("/api/results/auto/run/no_run/image/a.jpg")
        assert resp.status_code == 404


class TestDownloadZip:
    def test_download_nonexistent(self, client):
        resp = client.get("/api/results/auto/run/no_run/zip")
        assert resp.status_code == 404

    def test_download_zip(self, client, monkeypatch, tmp_path):
        auto_root = tmp_path / "auto_results"
        auto_root.mkdir()
        monkeypatch.setattr("fursee_api.api.results.AUTO_ROOT", str(auto_root))
        database.add_run("r1", 0.0, [], 1)
        _make_fake_output(str(auto_root), "r1", ["组_1"])
        resp = client.get("/api/results/auto/run/r1/zip")
        assert resp.status_code == 200
        assert "application/zip" in resp.headers.get("content-type", "")
