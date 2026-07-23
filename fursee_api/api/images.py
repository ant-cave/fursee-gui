import io
import os

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from utils.common import IMAGE_EXTENSIONS

router = APIRouter(prefix="/api/images", tags=["images"])

CATEGORIES = {
    "images": os.path.join("input", "images"),
    "sim_targets": os.path.join("input", "sim_targets"),
    "id_targets": os.path.join("input", "id_targets"),
    "auto_uploads": os.path.join("input", "auto_uploads"),
}


THUMB_MAX_SIZE = 200


def _serve_thumb(fpath: str):
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
        ext = os.path.splitext(fpath)[1].lower()
        media_type = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp",
        }.get(ext, "application/octet-stream")
        return FileResponse(fpath, media_type=media_type)


@router.get("/{category}/image/{filename:path}")
async def get_image(category: str, filename: str, thumb: bool = Query(False)):
    if category not in CATEGORIES:
        return JSONResponse({"error": "Invalid category"}, status_code=400)

    fpath = os.path.normpath(os.path.join(CATEGORIES[category], filename))
    base_real = os.path.realpath(CATEGORIES[category])
    fpath_real = os.path.realpath(fpath)

    if not fpath_real.startswith(base_real):
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    if not os.path.isfile(fpath):
        return JSONResponse({"error": "File not found"}, status_code=404)

    if thumb:
        return _serve_thumb(fpath)

    ext = os.path.splitext(fpath)[1].lower()
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(ext, "application/octet-stream")

    return FileResponse(fpath, media_type=media_type)


@router.get("/{category}")
async def list_images(category: str):
    if category not in CATEGORIES:
        return JSONResponse({"error": f"Invalid category: {category}"}, status_code=400)

    folder = CATEGORIES[category]
    os.makedirs(folder, exist_ok=True)

    images = []
    for fname in sorted(os.listdir(folder)):
        if fname.lower().endswith(IMAGE_EXTENSIONS):
            fpath = os.path.join(folder, fname)
            stat = os.stat(fpath)
            images.append({
                "name": fname,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })

    return {"category": category, "images": images, "count": len(images)}


@router.post("/{category}/upload")
async def upload_images(category: str, files: list[UploadFile] = File(default=[])):
    if category not in CATEGORIES:
        return JSONResponse({"error": f"Invalid category: {category}"}, status_code=400)

    folder = CATEGORIES[category]
    os.makedirs(folder, exist_ok=True)

    uploaded = []
    for file in files:
        if not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            continue
        dest = os.path.join(folder, file.filename)
        with open(dest, "wb") as f:
            f.write(await file.read())
        uploaded.append(file.filename)

    return {"uploaded": uploaded, "count": len(uploaded)}


@router.delete("/{category}/{filename:path}")
async def delete_image(category: str, filename: str):
    if category not in CATEGORIES:
        return JSONResponse({"error": f"Invalid category: {category}"}, status_code=400)

    fpath = os.path.join(CATEGORIES[category], filename)
    if not os.path.exists(fpath):
        return JSONResponse({"error": "File not found"}, status_code=404)

    if not fpath.startswith(os.path.realpath(CATEGORIES[category])):
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    os.remove(fpath)
    return {"deleted": filename}
