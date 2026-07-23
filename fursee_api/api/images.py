import os
import re

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from utils.common import IMAGE_EXTENSIONS
from utils.image_utils import serve_thumbnail

router = APIRouter(prefix="/api/images", tags=["images"])

CATEGORIES = {
    "images": os.path.join("input", "images"),
    "sim_targets": os.path.join("input", "sim_targets"),
    "id_targets": os.path.join("input", "id_targets"),
    "auto_uploads": os.path.join("input", "auto_uploads"),
}

MAX_FILES_PER_UPLOAD = 100
MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_TOTAL_UPLOAD_BYTES = 500 * 1024 * 1024

_SAFE_FILENAME_RE = re.compile(r'^[a-zA-Z0-9_\-.()\[\] ]+$')


def _safe_filename(name: str) -> str:
    name = os.path.basename(name)
    name = name.replace(" ", "_")
    name = re.sub(r'[^\w.\-()\[\]]', '_', name)
    return name[:255]


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
        resp = serve_thumbnail(fpath)
        if resp:
            return resp

    ext = os.path.splitext(fpath)[1].lower()
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(ext, "application/octet-stream")

    return FileResponse(fpath, media_type=media_type)


@router.get("/{category}")
async def list_images(category: str, request: Request):
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
async def upload_images(category: str, request: Request, files: list[UploadFile] = File(default=[])):
    if category not in CATEGORIES:
        return JSONResponse({"error": f"Invalid category: {category}"}, status_code=400)

    total_files = len(files)
    if total_files > MAX_FILES_PER_UPLOAD:
        return JSONResponse({"error": f"单次上传文件数量不能超过 {MAX_FILES_PER_UPLOAD}"}, status_code=413)

    contents: list[tuple[str, bytes]] = []
    total_bytes = 0
    skipped_invalid: list[str] = []
    for file in files:
        if not file.filename:
            continue
        fname = _safe_filename(file.filename)
        ext = os.path.splitext(fname)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            skipped_invalid.append(file.filename)
            continue
        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            skipped_invalid.append(file.filename)
            continue
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(data))
            img.verify()
        except Exception:
            skipped_invalid.append(file.filename)
            continue
        contents.append((fname, data))
        total_bytes += len(data)
        if total_bytes > MAX_TOTAL_UPLOAD_BYTES:
            break

    if total_bytes == 0:
        return {"uploaded": [], "count": 0, "skipped": skipped_invalid}

    folder = CATEGORIES[category]
    os.makedirs(folder, exist_ok=True)

    uploaded = []
    for fname, data in contents:
        dest = os.path.join(folder, fname)
        with open(dest, "wb") as f:
            f.write(data)
        uploaded.append(fname)

    return {"uploaded": uploaded, "count": len(uploaded), "skipped": skipped_invalid}


@router.delete("/{category}/{filename:path}")
async def delete_image(category: str, filename: str, request: Request):
    if category not in CATEGORIES:
        return JSONResponse({"error": f"Invalid category: {category}"}, status_code=400)

    folder_real = os.path.realpath(CATEGORIES[category])
    fpath = os.path.normpath(os.path.join(CATEGORIES[category], filename))
    fpath_real = os.path.realpath(fpath)

    if not fpath_real.startswith(folder_real):
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    if not os.path.exists(fpath):
        return JSONResponse({"error": "File not found"}, status_code=404)

    os.remove(fpath)
    return {"deleted": filename}
