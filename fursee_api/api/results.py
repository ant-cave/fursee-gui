import io
import os
import zipfile

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

router = APIRouter(prefix="/api/results", tags=["results"])

RESULT_DIRS = {
    "classify": os.path.join("output", "classify"),
    "similar": os.path.join("output", "similar"),
    "identify": os.path.join("output", "identify"),
}

AUTO_ROOT = os.path.join("output", "auto", "classify")


THUMB_MAX_SIZE = 200


def _thumb(fpath: str):
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


def _serve_image(base_dir: str, path: str, thumb: bool = False):
    full_path = os.path.normpath(os.path.join(base_dir, path))
    base_real = os.path.realpath(base_dir)
    full_real = os.path.realpath(full_path)
    if not full_real.startswith(base_real):
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    if not os.path.isfile(full_path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    if thumb:
        resp = _thumb(full_path)
        if resp:
            return resp
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


def _fp_tag(request: Request) -> str:
    fp = getattr(request.state, "fingerprint", "unknown")
    if fp and fp != "unknown":
        return f"fp_{fp}"
    return ""


def _auto_run_dir(request: Request) -> str:
    tag = _fp_tag(request)
    if tag:
        return os.path.join(AUTO_ROOT, tag)
    return AUTO_ROOT


@router.get("/auto")
async def list_auto_results(request: Request):
    from fursee_api.core.database import get_runs
    fp = getattr(request.state, "fingerprint", "unknown")
    runs = get_runs(fp)
    return {
        "fingerprint": fp,
        "runs": runs,
        "count": len(runs),
    }


@router.get("/auto/run/{run_id}")
async def get_auto_run(run_id: str, request: Request):
    from fursee_api.core.database import get_run
    fp = getattr(request.state, "fingerprint", "unknown")
    run = get_run(fp, run_id)
    if run is None:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    return run


@router.get("/auto/run/{run_id}/image/{path:path}")
async def get_auto_run_image(run_id: str, path: str, request: Request, thumb: bool = Query(False)):
    base_dir = os.path.join(_auto_run_dir(request), run_id)
    return _serve_image(base_dir, path, thumb=thumb)


@router.get("/auto/run/{run_id}/zip")
async def download_auto_run_zip(run_id: str, request: Request):
    run_dir = os.path.join(_auto_run_dir(request), run_id)
    if not os.path.isdir(run_dir):
        return JSONResponse({"error": "Run not found"}, status_code=404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(run_dir):
            for fname in sorted(files):
                if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    arcname = os.path.relpath(os.path.join(root, fname), run_dir)
                    zf.write(os.path.join(root, fname), arcname)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=auto_{run_id}.zip"},
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
async def get_result_image(result_type: str, path: str, thumb: bool = Query(False)):
    if result_type not in RESULT_DIRS:
        return JSONResponse({"error": "Invalid result type"}, status_code=400)
    return _serve_image(RESULT_DIRS[result_type], path, thumb=thumb)
