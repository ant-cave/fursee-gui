import io
import os
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

router = APIRouter(prefix="/api/results", tags=["results"])

RESULT_DIRS = {
    "classify": os.path.join("output", "classify"),
    "similar": os.path.join("output", "similar"),
    "identify": os.path.join("output", "identify"),
}

AUTO_DIR = os.path.join("output", "auto", "classify")


def _serve_image(base_dir: str, path: str):
    full_path = os.path.normpath(os.path.join(base_dir, path))
    base_real = os.path.realpath(base_dir)
    full_real = os.path.realpath(full_path)
    if not full_real.startswith(base_real):
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    if not os.path.isfile(full_path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    ext = os.path.splitext(full_path)[1].lower()
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
    return FileResponse(full_path, media_type=media_type)


def _list_entries(base_dir: str):
    if not os.path.isdir(base_dir):
        return []
    entries = []
    for name in sorted(os.listdir(base_dir)):
        fpath = os.path.join(base_dir, name)
        if os.path.isdir(fpath):
            images = sorted([
                f for f in os.listdir(fpath)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
            ])
            entries.append({"name": name, "type": "folder", "images": images, "image_count": len(images)})
        else:
            entries.append({"name": name, "type": "file", "size": os.path.getsize(fpath)})
    return entries


@router.get("/auto")
async def list_auto_results():
    return {"type": "auto", "entries": _list_entries(AUTO_DIR), "count": len(_list_entries(AUTO_DIR))}


@router.get("/auto/image/{path:path}")
async def get_auto_image(path: str):
    return _serve_image(AUTO_DIR, path)


@router.get("/auto/zip")
async def download_auto_zip():
    if not os.path.isdir(AUTO_DIR):
        return JSONResponse({"error": "No results"}, status_code=404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(AUTO_DIR):
            for fname in sorted(files):
                if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    arcname = os.path.relpath(os.path.join(root, fname), AUTO_DIR)
                    zf.write(os.path.join(root, fname), arcname)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=auto_classify.zip"},
    )


@router.get("/{result_type}")
async def list_results(result_type: str):
    if result_type not in RESULT_DIRS:
        return JSONResponse({"error": f"Invalid result type: {result_type}"}, status_code=400)
    folder = RESULT_DIRS[result_type]
    if not os.path.isdir(folder):
        return {"type": result_type, "entries": [], "count": 0}
    return {"type": result_type, "entries": _list_entries(folder), "count": len(_list_entries(folder))}


@router.get("/{result_type}/zip")
async def download_results_zip(result_type: str):
    if result_type not in RESULT_DIRS:
        return JSONResponse({"error": "Invalid result type"}, status_code=400)
    folder = RESULT_DIRS[result_type]
    if not os.path.isdir(folder):
        return JSONResponse({"error": "No results to download"}, status_code=404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder):
            for fname in sorted(files):
                if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    arcname = os.path.relpath(os.path.join(root, fname), folder)
                    zf.write(os.path.join(root, fname), arcname)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={result_type}.zip"},
    )


@router.get("/{result_type}/image/{path:path}")
async def get_result_image(result_type: str, path: str):
    if result_type not in RESULT_DIRS:
        return JSONResponse({"error": "Invalid result type"}, status_code=400)
    return _serve_image(RESULT_DIRS[result_type], path)
