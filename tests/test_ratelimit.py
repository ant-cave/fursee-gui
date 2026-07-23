import os
import tempfile

import pytest

from fursee_api.core import database
from fursee_api.core.ratelimit import (
    check_upload, record_upload, check_task, record_task, get_quota,
    UPLOAD_MAX_BYTES, TASK_MAX_COUNT,
)


@pytest.fixture(autouse=True)
def _patch_db_path(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    monkeypatch.setattr(database, "DB_PATH", tmp)
    yield
    os.unlink(tmp)


class TestUploadRateLimit:
    def test_upload_allowed_when_empty(self):
        ok, remaining, _ = check_upload("1.2.3.4")
        assert ok
        assert remaining == UPLOAD_MAX_BYTES

    def test_upload_deducts_bytes(self):
        record_upload("1.2.3.4", 100)
        ok, remaining, _ = check_upload("1.2.3.4")
        assert ok
        assert remaining == UPLOAD_MAX_BYTES - 100

    def test_upload_exhausted(self):
        record_upload("1.2.3.4", UPLOAD_MAX_BYTES)
        ok, remaining, _ = check_upload("1.2.3.4")
        assert not ok
        assert remaining == 0

    def test_upload_isolation_by_ip(self):
        record_upload("1.2.3.4", UPLOAD_MAX_BYTES)
        ok, _, _ = check_upload("5.6.7.8")
        assert ok


class TestTaskRateLimit:
    def test_task_allowed_when_empty(self):
        ok, remaining, _ = check_task("1.2.3.4")
        assert ok
        assert remaining == TASK_MAX_COUNT

    def test_task_deducts_one(self):
        record_task("1.2.3.4")
        ok, remaining, _ = check_task("1.2.3.4")
        assert ok
        assert remaining == TASK_MAX_COUNT - 1

    def test_task_exhausted(self):
        for _ in range(TASK_MAX_COUNT):
            record_task("1.2.3.4")
        ok, _, _ = check_task("1.2.3.4")
        assert not ok

    def test_task_isolation_by_ip(self):
        for _ in range(TASK_MAX_COUNT):
            record_task("1.2.3.4")
        ok, _, _ = check_task("5.6.7.8")
        assert ok


class TestQuota:
    def test_quota_returns_all_fields(self):
        q = get_quota("1.2.3.4")
        assert "ip" in q
        assert "upload_remaining" in q
        assert "upload_max" in q
        assert "task_remaining" in q
        assert "task_max" in q
        assert q["ip"] == "1.2.3.4"

    def test_quota_after_usage(self):
        record_upload("1.2.3.4", 500)
        record_task("1.2.3.4")
        q = get_quota("1.2.3.4")
        assert q["upload_remaining"] < q["upload_max"]
        assert q["task_remaining"] < q["task_max"]


class TestAdminToken:
    def test_no_token_configured(self):
        from fursee_api.core.ratelimit import is_admin_token
        assert not is_admin_token("anything")

    def test_matches_configured_token_directly(self):
        from fursee_api.core.ratelimit import is_admin_token
        import fursee_api.core.ratelimit as rl
        rl._ADMIN_TOKEN = "test_token"
        assert is_admin_token("test_token")
        assert not is_admin_token("wrong")
        rl._ADMIN_TOKEN = ""
