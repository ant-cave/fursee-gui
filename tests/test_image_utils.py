import io
import os
import tempfile

import pytest
from PIL import Image

from utils.image_utils import serve_thumbnail, THUMB_MAX_SIZE


def _make_test_image(w: int, h: int) -> str:
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    img = Image.new("RGB", (w, h), color=(255, 0, 0))
    img.save(path, "JPEG")
    return path


class TestServeThumbnail:
    def test_returns_response_for_large_image(self):
        path = _make_test_image(800, 600)
        try:
            resp = serve_thumbnail(path)
            assert resp is not None
            assert resp.status_code == 200
            assert resp.media_type == "image/jpeg"
            data = resp.body
            assert len(data) > 0
            thumb = Image.open(io.BytesIO(data))
            assert thumb.width <= THUMB_MAX_SIZE
        finally:
            os.unlink(path)

    def test_keeps_small_image_unchanged(self):
        path = _make_test_image(100, 100)
        try:
            resp = serve_thumbnail(path)
            assert resp is not None
            thumb = Image.open(io.BytesIO(resp.body))
            assert thumb.width == 100
            assert thumb.height == 100
        finally:
            os.unlink(path)

    def test_maintains_aspect_ratio(self):
        path = _make_test_image(800, 400)
        try:
            resp = serve_thumbnail(path)
            assert resp is not None
            thumb = Image.open(io.BytesIO(resp.body))
            assert thumb.width == THUMB_MAX_SIZE
            assert thumb.height == int(400 * THUMB_MAX_SIZE / 800)
        finally:
            os.unlink(path)

    def test_returns_none_for_invalid_file(self):
        path = "/nonexistent/image.jpg"
        resp = serve_thumbnail(path)
        assert resp is None

    def test_returns_none_for_non_image_file(self):
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        with open(path, "w") as f:
            f.write("not an image")
        try:
            resp = serve_thumbnail(path)
            assert resp is None
        finally:
            os.unlink(path)

    def test_handles_transparent_png(self):
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img = Image.new("RGBA", (500, 300), color=(255, 0, 0, 0))
        img.save(path, "PNG")
        try:
            resp = serve_thumbnail(path)
            assert resp is not None
            assert resp.media_type == "image/jpeg"
        finally:
            os.unlink(path)

    def test_exact_boundary_image(self):
        path = _make_test_image(THUMB_MAX_SIZE, 200)
        try:
            resp = serve_thumbnail(path)
            assert resp is not None
            thumb = Image.open(io.BytesIO(resp.body))
            assert thumb.width == THUMB_MAX_SIZE
            assert thumb.height == 200
        finally:
            os.unlink(path)
