import io
import os
import zipfile

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from utils.image_utils import serve_thumbnail

router = APIRouter(prefix="/api/results", tags=["results"])

AUTO_ROOT = os.path.join("output", "auto", "classify")


def _serve_image(base_dir: str, path: str, thumb: bool = False):
    full_path = os.path.normpath(os.path.join(base_dir, path))
    base_real = os.path.realpath(base_dir)
    full_real = os.path.realpath(full_path)
    if not full_real.startswith(base_real):
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    if not os.path.isfile(full_path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    if thumb:
        resp = serve_thumbnail(full_path)
        if resp:
            return resp
    ext = os.path.splitext(full_path)[1].lower()
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
    return FileResponse(full_path, media_type=media_type)


@router.get("/auto")
async def list_auto_results(request: Request):
    from fursee_api.core.database import get_runs
    runs = get_runs()
    return {
        "runs": runs,
        "count": len(runs),
    }


@router.get("/auto/run/{run_id}")
async def get_auto_run(run_id: str, request: Request):
    from fursee_api.core.database import get_run
    run = get_run(run_id)
    if run is None:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    return run


@router.delete("/auto/run/{run_id}")
async def delete_auto_run(run_id: str, request: Request):
    import shutil
    from fursee_api.core.database import get_run, delete_run
    run = get_run(run_id)
    if run is None:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    run_dir = os.path.join(AUTO_ROOT, run_id)
    if os.path.isdir(run_dir):
        shutil.rmtree(run_dir, ignore_errors=True)
    buffer_path = run.get("buffer_path", "")
    buffer_root = os.path.realpath(os.path.join("buffer", "auto"))
    if buffer_path:
        bp_real = os.path.realpath(buffer_path)
        if not bp_real.startswith(buffer_root):
            return JSONResponse({"error": "Invalid buffer path"}, status_code=400)
        if os.path.isdir(buffer_path):
            shutil.rmtree(buffer_path, ignore_errors=True)
    delete_run(run_id)
    return {"deleted": run_id}


@router.get("/auto/run/{run_id}/image/{path:path}")
async def get_auto_run_image(run_id: str, path: str, request: Request, thumb: bool = Query(False)):
    base_dir = os.path.join(AUTO_ROOT, run_id)
    return _serve_image(base_dir, path, thumb=thumb)


@router.get("/auto/run/{run_id}/zip")
async def download_auto_run_zip(run_id: str, request: Request):
    run_dir = os.path.join(AUTO_ROOT, run_id)
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
