import os

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from utils.common import IMAGE_EXTENSIONS
from utils.image_utils import serve_thumbnail
from fursee_api.core.ratelimit import check_upload, is_admin_token, record_upload

router = APIRouter(prefix="/api/images", tags=["images"])

CATEGORIES = {
    "images": os.path.join("input", "images"),
    "sim_targets": os.path.join("input", "sim_targets"),
    "id_targets": os.path.join("input", "id_targets"),
    "auto_uploads": os.path.join("input", "auto_uploads"),
}


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
async def upload_images(category: str, request: Request, files: list[UploadFile] = File(default=[])):
    if category not in CATEGORIES:
        return JSONResponse({"error": f"Invalid category: {category}"}, status_code=400)

    ip = request.client.host if request.client else "unknown"
    contents: list[tuple[str, bytes]] = []
    total_bytes = 0
    skipped_invalid: list[str] = []
    for file in files:
        if not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            skipped_invalid.append(file.filename)
            continue
        data = await file.read()
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(data))
            img.verify()
        except Exception:
            skipped_invalid.append(file.filename)
            continue
        contents.append((file.filename, data))
        total_bytes += len(data)

    if total_bytes == 0:
        return {"uploaded": [], "count": 0, "skipped": skipped_invalid}

    if not is_admin_token(request.headers.get("x-admin-token", "")):
        ok, remaining, _ = check_upload(ip)
        if not ok:
            return JSONResponse({"error": "上传配额已用尽，请等待额度刷新", "remaining": 0}, status_code=429)
        record_upload(ip, total_bytes)

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
async def delete_image(category: str, filename: str):
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
