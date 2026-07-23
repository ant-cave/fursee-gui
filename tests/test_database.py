import os
import json
import tempfile

import pytest

from fursee_api.core import database


@pytest.fixture(autouse=True)
def _patch_db_path(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    monkeypatch.setattr(database, "DB_PATH", tmp)
    yield
    os.unlink(tmp)


def test_add_and_get_run():
    database.add_run("fp_test", "run_001", 1000.0, [{"name": "组_1", "image_count": 3, "images": ["a.jpg", "b.jpg", "c.jpg"]}], 3)
    runs = database.get_runs("fp_test")
    assert len(runs) == 1
    r = runs[0]
    assert r["run_id"] == "run_001"
    assert r["total"] == 3
    assert r["entries"][0]["name"] == "组_1"
    assert r["pipeline"] == "auto"
    assert r["buffer_path"] == ""


def test_multiple_runs():
    for i in range(3):
        database.add_run("fp_test", f"run_{i:03d}", float(i), [], i)
    runs = database.get_runs("fp_test")
    assert len(runs) == 3
    assert [r["run_id"] for r in runs] == ["run_000", "run_001", "run_002"]


def test_fingerprint_isolation():
    database.add_run("fp_a", "r1", 0.0, [], 0)
    database.add_run("fp_b", "r1", 0.0, [], 0)
    assert len(database.get_runs("fp_a")) == 1
    assert len(database.get_runs("fp_b")) == 1


def test_get_run():
    database.add_run("fp_test", "run_001", 1000.0, [], 5, pipeline="auto", buffer_path="buf/run_001")
    r = database.get_run("fp_test", "run_001")
    assert r is not None
    assert r["run_id"] == "run_001"
    assert r["total"] == 5
    assert r["pipeline"] == "auto"
    assert r["buffer_path"] == "buf/run_001"


def test_get_run_nonexistent():
    assert database.get_run("fp_test", "no_such_run") is None


def test_update_run():
    database.add_run("fp_test", "run_001", 1000.0, [{"name": "组_1", "image_count": 3, "images": ["a.jpg"]}], 3)
    new_entries = [{"name": "组_1", "image_count": 5, "images": ["a.jpg", "b.jpg"]}]
    database.update_run("fp_test", "run_001", new_entries, 5, 2000.0, buffer_path="buf/new_path")
    r = database.get_run("fp_test", "run_001")
    assert r["total"] == 5
    assert r["timestamp"] == 2000.0
    assert r["buffer_path"] == "buf/new_path"
    assert len(r["entries"][0]["images"]) == 2


def test_update_run_nonexistent():
    database.update_run("fp_test", "no_such_run", [], 0, 0.0)
    assert database.get_run("fp_test", "no_such_run") is None


def test_duplicate_run_id_ignored():
    database.add_run("fp_test", "run_001", 1000.0, [{"name": "组_1", "image_count": 1, "images": ["a.jpg"]}], 1)
    database.add_run("fp_test", "run_001", 2000.0, [{"name": "组_2", "image_count": 2, "images": ["b.jpg", "c.jpg"]}], 2)
    runs = database.get_runs("fp_test")
    assert len(runs) == 1
    assert runs[0]["total"] == 1


def test_run_order_ascending():
    database.add_run("fp_test", "r3", 300.0, [], 0)
    database.add_run("fp_test", "r1", 100.0, [], 0)
    database.add_run("fp_test", "r2", 200.0, [], 0)
    run_ids = [r["run_id"] for r in database.get_runs("fp_test")]
    assert run_ids == ["r3", "r1", "r2"]


def test_get_run_returns_parsed_json():
    database.add_run("fp_test", "run_001", 0.0, [{"name": "组_A", "image_count": 2, "images": ["x.png", "y.png"]}], 2)
    r = database.get_run("fp_test", "run_001")
    assert isinstance(r["entries"], list)
    assert r["entries"][0]["name"] == "组_A"
    assert r["entries"][0]["images"] == ["x.png", "y.png"]
