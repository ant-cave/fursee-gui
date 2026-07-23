import io
import os

from fastapi.responses import FileResponse, Response


THUMB_MAX_SIZE = 200


def serve_thumbnail(fpath: str):
    try:
        from PIL import Image
        img = Image.open(fpath)
        img = img.convert("RGB")
        w, h = img.size
        if w > THUMB_MAX_SIZE:
            ratio = THUMB_MAX_SIZE / w
            img = img.resize((THUMB_MAX_SIZE, int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        buf.seek(0)
        return Response(content=buf.read(), media_type="image/jpeg")
    except Exception:
        return None
