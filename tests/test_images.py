import io
import os
import tempfile

import pytest
from PIL import Image

from fursee_api.api.images import CATEGORIES


def _jpeg_bytes(w=50, h=50):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (255, 0, 0)).save(buf, "JPEG")
    return buf.getvalue()


def _patch_categories(monkeypatch):
    tmp_root = tempfile.mkdtemp()
    patched = {}
    for key in CATEGORIES:
        path = os.path.join(tmp_root, key)
        os.makedirs(path, exist_ok=True)
        patched[key] = path
    monkeypatch.setattr("fursee_api.api.images.CATEGORIES", patched)


class TestPathTraversal:
    def test_get_image_invalid_category(self, client):
        resp = client.get("/api/images/invalid_category/image/test.jpg")
        assert resp.status_code == 400

    def test_delete_image_invalid_category(self, client):
        resp = client.delete("/api/images/invalid_category/test.jpg")
        assert resp.status_code == 400

    def test_get_image_nonexistent(self, client):
        resp = client.get("/api/images/images/image/nonexistent.jpg")
        assert resp.status_code == 404


class TestImageList:
    def test_list_empty_category(self, client, monkeypatch):
        _patch_categories(monkeypatch)
        resp = client.get("/api/images/images")
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "images"
        assert data["count"] == 0

    def test_list_invalid_category(self, client):
        resp = client.get("/api/images/bad_cat")
        assert resp.status_code == 400


class TestImageUploadAndServe:
    def test_upload_and_list(self, client, monkeypatch):
        _patch_categories(monkeypatch)
        resp = client.post("/api/images/images/upload", files={"files": ("test.jpg", _jpeg_bytes(), "image/jpeg")})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["uploaded"] == ["test.jpg"]
        assert data["skipped"] == []

        resp = client.get("/api/images/images")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        assert resp.json()["images"][0]["name"] == "test.jpg"

    def test_upload_and_delete(self, client, monkeypatch):
        _patch_categories(monkeypatch)
        client.post("/api/images/images/upload", files={"files": ("test.jpg", _jpeg_bytes(), "image/jpeg")})
        resp = client.delete("/api/images/images/test.jpg")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "test.jpg"

    def test_delete_nonexistent(self, client, monkeypatch):
        _patch_categories(monkeypatch)
        resp = client.delete("/api/images/images/nonexistent.jpg")
        assert resp.status_code == 404

    def test_upload_skips_invalid_extension(self, client, monkeypatch):
        _patch_categories(monkeypatch)
        resp = client.post("/api/images/images/upload", files={"files": ("test.txt", b"not an image", "text/plain")})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert "test.txt" in data["skipped"]

    def test_upload_all_categories(self, client, monkeypatch):
        _patch_categories(monkeypatch)
        for cat in ("images", "sim_targets", "id_targets", "auto_uploads"):
            resp = client.post(f"/api/images/{cat}/upload", files={"files": ("a.jpg", _jpeg_bytes(), "image/jpeg")})
            assert resp.status_code == 200, f"Category {cat} failed"
            assert resp.json()["count"] == 1, f"Category {cat} upload count wrong"

    def test_upload_invalid_category(self, client):
        resp = client.post("/api/images/bad_cat/upload", files={"files": ("a.jpg", _jpeg_bytes(), "image/jpeg")})
        assert resp.status_code == 400

    def test_upload_get_then_delete(self, client, monkeypatch):
        _patch_categories(monkeypatch)
        client.post("/api/images/images/upload", files={"files": ("photo.jpg", _jpeg_bytes(), "image/jpeg")})
        get_resp = client.get("/api/images/images/image/photo.jpg")
        assert get_resp.status_code == 200
        del_resp = client.delete("/api/images/images/photo.jpg")
        assert del_resp.status_code == 200
        get_resp2 = client.get("/api/images/images/image/photo.jpg")
        assert get_resp2.status_code == 404

    def test_get_image_thumb(self, client, monkeypatch):
        _patch_categories(monkeypatch)
        client.post("/api/images/images/upload", files={"files": ("photo.jpg", _jpeg_bytes(400, 300), "image/jpeg")})
        resp = client.get("/api/images/images/image/photo.jpg?thumb=1")
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "image/jpeg"
