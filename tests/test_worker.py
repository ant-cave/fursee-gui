import datetime
import os
import tempfile

import pytest


@pytest.fixture
def scratch_dir():
    d = tempfile.mkdtemp()
    yield d


def _make_fake_buffers(folder):
    os.makedirs(os.path.join(folder, "output", "auto", "classify", "run_001", "组_1"), exist_ok=True)
    for fname in ("old_a.jpg", "old_b.jpg"):
        with open(os.path.join(folder, "output", "auto", "classify", "run_001", "组_1", fname), "w") as f:
            f.write("fake")
    os.makedirs(os.path.join(folder, "buffer", "auto", "run_001"), exist_ok=True)
    with open(os.path.join(folder, "buffer", "auto", "run_001", "features.fvdb"), "w") as f:
        f.write("fake_db")
    os.makedirs(os.path.join(folder, "input", "auto_uploads"), exist_ok=True)
    for fname in ("new_x.jpg", "new_y.jpg"):
        with open(os.path.join(folder, "input", "auto_uploads", fname), "w") as f:
            f.write("fake")
    return folder


def _mock_all_deps(m, FakeVDB):
    import utils.detection, utils.embedding, utils.clustering, utils.vector_db, utils.common
    from fursee_api.core import database
    m.setattr(utils.detection, "crop_furry_detections", lambda **kw: None)
    m.setattr(utils.embedding, "extract_features_to_db", lambda **kw: None)
    m.setattr(utils.embedding, "extract_features_from_folder", lambda **kw: [])
    m.setattr(utils.clustering, "cluster_feature_db", lambda **kw: None)
    m.setattr(utils.vector_db, "require_feature_db", lambda *a, **kw: None)
    m.setattr(utils.vector_db, "VectorDatabase", FakeVDB)
    m.setattr(utils.common, "float_range", lambda *a: [1.5])
    m.setattr(utils.common, "reset_directory", lambda *a: None)
    m.setattr(database, "add_run", lambda **kw: None)
    m.setattr(database, "update_run", lambda *a, **kw: None)
    return database


class FakeNewDB:
    def __init__(self):
        self.keys = []
        self.vectors = []
    def add_many(self, items): pass
    def save(self, path): pass
    @staticmethod
    def load_auto(folder, preferred_name="features.fvdb", legacy_name="features.json"):
        return FakeNewDB()


class TestAutoRunNewRun:
    def test_new_run_uses_add_run(self, monkeypatch, scratch_dir):
        import utils.clustering
        db_mod = _mock_all_deps(monkeypatch, FakeNewDB)
        def fake_cluster(**kw):
            os.makedirs(os.path.join(kw["output_root"], "组_1"), exist_ok=True)
            with open(os.path.join(kw["output_root"], "组_1", "a.jpg"), "w") as f:
                f.write("fake")
        monkeypatch.setattr(utils.clustering, "cluster_feature_db", fake_cluster)
        calls = []
        monkeypatch.setattr(db_mod, "add_run", lambda **kw: calls.append(kw))
        from fursee_api.core.worker import _auto_run
        result = _auto_run({
            "input_folder": os.path.join(scratch_dir, "input_uploads"),
            "output_folder": os.path.join(scratch_dir, "out"),
            "buffer": os.path.join(scratch_dir, "buf"),
        })
        assert result["run_id"] is not None
        assert len(calls) == 1

    def test_new_run_paths(self, monkeypatch, scratch_dir):
        import utils.clustering
        db_mod = _mock_all_deps(monkeypatch, FakeNewDB)
        def fake_cluster(**kw):
            os.makedirs(os.path.join(kw["output_root"], "组_1"), exist_ok=True)
            with open(os.path.join(kw["output_root"], "组_1", "a.jpg"), "w") as f:
                f.write("fake")
        monkeypatch.setattr(utils.clustering, "cluster_feature_db", fake_cluster)
        monkeypatch.setattr(db_mod, "add_run", lambda **kw: None)
        from fursee_api.core.worker import _auto_run
        result = _auto_run({
            "input_folder": os.path.join(scratch_dir, "input_uploads"),
            "output_folder": os.path.join(scratch_dir, "out"),
            "buffer": os.path.join(scratch_dir, "buf"),
        })
        assert result["total"] > 0
        assert len(result["entries"]) == 1


class TestAutoRunAppend:
    def test_append_calls_update_run(self, monkeypatch, scratch_dir):
        _make_fake_buffers(scratch_dir)
        import utils.detection, utils.embedding, utils.clustering, utils.vector_db, utils.common
        monkeypatch.setattr(utils.detection, "crop_furry_detections", lambda **kw: None)
        monkeypatch.setattr(utils.embedding, "extract_features_from_folder",
                             lambda **kw: [{"key": "new_x.jpg", "vector": [0.5, 0.6]}])
        monkeypatch.setattr(utils.clustering, "cluster_feature_db", lambda **kw: None)
        monkeypatch.setattr(utils.vector_db, "require_feature_db", lambda *a, **kw: None)
        monkeypatch.setattr(utils.common, "float_range", lambda *a: [1.5])
        monkeypatch.setattr(utils.common, "reset_directory", lambda *a: None)
        class FakeAppendVDB:
            def __init__(self):
                self._called_add_many = False
                self._called_save = False
            def add_many(self, items):
                self._called_add_many = True
            def save(self, path):
                self._called_save = True
            @staticmethod
            def load_auto(folder, preferred_name="features.fvdb", legacy_name="features.json"):
                return FakeAppendVDB()
        monkeypatch.setattr(utils.vector_db, "VectorDatabase", FakeAppendVDB)
        from fursee_api.core import database
        update_calls = []
        add_calls = []
        monkeypatch.setattr(database, "update_run", lambda r, e, t, ts, buffer_path="": update_calls.append((r, e, t, ts, buffer_path)))
        monkeypatch.setattr(database, "add_run", lambda **kw: add_calls.append(kw))
        from fursee_api.core.worker import _auto_run
        result = _auto_run({
            "existing_run_id": "run_001",
            "input_folder": os.path.join(scratch_dir, "input", "auto_uploads"),
            "output_folder": os.path.join(scratch_dir, "output", "auto", "classify"),
            "buffer": os.path.join(scratch_dir, "buffer", "auto"),
        })
        assert result["run_id"] == "run_001"
        assert len(add_calls) == 0
        assert len(update_calls) == 1
        assert update_calls[0][0] == "run_001"

    def test_append_reuses_db(self, monkeypatch, scratch_dir):
        _make_fake_buffers(scratch_dir)
        import utils.detection, utils.embedding, utils.clustering, utils.vector_db, utils.common
        monkeypatch.setattr(utils.detection, "crop_furry_detections", lambda **kw: None)
        monkeypatch.setattr(utils.embedding, "extract_features_from_folder",
                             lambda **kw: [{"key": "n.jpg", "vector": [0.1]}])
        monkeypatch.setattr(utils.clustering, "cluster_feature_db", lambda **kw: None)
        monkeypatch.setattr(utils.vector_db, "require_feature_db", lambda *a, **kw: None)
        monkeypatch.setattr(utils.common, "float_range", lambda *a: [1.5])
        monkeypatch.setattr(utils.common, "reset_directory", lambda *a: None)
        called = {"add_many": False, "save": False}
        class FakeAppendVDB:
            def __init__(self):
                pass
            def add_many(self, items):
                called["add_many"] = True
            def save(self, path):
                called["save"] = True
            @staticmethod
            def load_auto(folder, preferred_name="features.fvdb", legacy_name="features.json"):
                return FakeAppendVDB()
        monkeypatch.setattr(utils.vector_db, "VectorDatabase", FakeAppendVDB)
        from fursee_api.core import database
        monkeypatch.setattr(database, "update_run", lambda *a, **kw: None)
        monkeypatch.setattr(database, "add_run", lambda **kw: None)
        from fursee_api.core.worker import _auto_run
        _auto_run({
            "existing_run_id": "run_001",
            "input_folder": os.path.join(scratch_dir, "input", "auto_uploads"),
            "output_folder": os.path.join(scratch_dir, "output", "auto", "classify"),
            "buffer": os.path.join(scratch_dir, "buffer", "auto"),
        })
        assert called["add_many"]
        assert called["save"]

    def test_append_no_existing_output_falls_back_to_new(self, monkeypatch, scratch_dir):
        import utils.clustering
        db_mod = _mock_all_deps(monkeypatch, FakeNewDB)
        def fake_cluster(**kw):
            os.makedirs(os.path.join(kw["output_root"], "组_1"), exist_ok=True)
            with open(os.path.join(kw["output_root"], "组_1", "a.jpg"), "w") as f:
                f.write("fake")
        monkeypatch.setattr(utils.clustering, "cluster_feature_db", fake_cluster)
        add_calls = []
        monkeypatch.setattr(db_mod, "add_run", lambda **kw: add_calls.append(kw))
        from fursee_api.core.worker import _auto_run
        _auto_run({
            "existing_run_id": "nonexistent",
            "input_folder": os.path.join(scratch_dir, "input", "auto_uploads"),
            "output_folder": os.path.join(scratch_dir, "output", "auto", "classify"),
            "buffer": os.path.join(scratch_dir, "buffer", "auto"),
        })
        assert len(add_calls) == 1

    def test_append_no_existing_db_falls_back_to_full(self, monkeypatch, scratch_dir):
        os.makedirs(os.path.join(scratch_dir, "output", "auto", "classify", "run_001", "组_1"), exist_ok=True)
        os.makedirs(os.path.join(scratch_dir, "input", "auto_uploads"), exist_ok=True)
        os.makedirs(os.path.join(scratch_dir, "buffer", "auto", "run_001"), exist_ok=True)
        import utils.detection, utils.embedding, utils.clustering, utils.vector_db, utils.common
        monkeypatch.setattr(utils.detection, "crop_furry_detections", lambda **kw: None)
        monkeypatch.setattr(utils.embedding, "extract_features_to_db", lambda **kw: None)
        monkeypatch.setattr(utils.embedding, "extract_features_from_folder", lambda **kw: [])
        monkeypatch.setattr(utils.clustering, "cluster_feature_db", lambda **kw: None)
        monkeypatch.setattr(utils.vector_db, "require_feature_db", lambda *a, **kw: None)
        monkeypatch.setattr(utils.common, "float_range", lambda *a: [1.5])
        monkeypatch.setattr(utils.common, "reset_directory", lambda *a: None)
        from fursee_api.core import database
        monkeypatch.setattr(database, "add_run", lambda **kw: None)
        monkeypatch.setattr(database, "update_run", lambda *a, **kw: None)
        class FakeFreshVDB:
            def __init__(self):
                self.keys = []
            def add_many(self, items): pass
            def save(self, path): pass
            @staticmethod
            def load_auto(folder, preferred_name="features.fvdb", legacy_name="features.json"):
                raise FileNotFoundError("no db")
        monkeypatch.setattr(utils.vector_db, "VectorDatabase", FakeFreshVDB)
        from fursee_api.core.worker import _auto_run
        _auto_run({
            "existing_run_id": "run_001",
            "input_folder": os.path.join(scratch_dir, "input", "auto_uploads"),
            "output_folder": os.path.join(scratch_dir, "output", "auto", "classify"),
            "buffer": os.path.join(scratch_dir, "buffer", "auto"),
        })
