import asyncio
import os
import sys

from contextlib import asynccontextmanager
import mimetypes
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fursee_api.api import images, pipeline, results
from fursee_api.core.task_manager import TaskManager
from fursee_api.core.worker import process_pipeline, set_task_manager


task_manager = TaskManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task_manager.set_processor(process_pipeline)
    set_task_manager(task_manager)
    await task_manager.start()
    pipeline.init(task_manager)
    yield
    await task_manager.stop()


app = FastAPI(title="Fursee API", version="1.0.0", lifespan=lifespan)

SERVE_FRONTEND = os.environ.get("FURSEE_SERVE_FRONTEND", "").lower() in ("1", "true", "yes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(images.router)
app.include_router(pipeline.router)
app.include_router(results.router)


DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fursee_ui", "dist")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stats")
async def stats():
    from utils.common import list_image_files
    from utils.vector_db import VectorDatabase
    import os

    input_dir = os.path.join("input", "images")
    sim_dir = os.path.join("input", "sim_targets")
    id_dir = os.path.join("input", "id_targets")
    buffer_dir = "buffer"
    db_path = os.path.join(buffer_dir, "features.fvdb")

    image_count = len(list_image_files(input_dir)) if os.path.isdir(input_dir) else 0
    sim_count = len(list_image_files(sim_dir)) if os.path.isdir(sim_dir) else 0
    id_count = len(list_image_files(id_dir)) if os.path.isdir(id_dir) else 0

    db_exists = os.path.isfile(db_path)
    db_vectors = 0
    if db_exists:
        try:
            db = VectorDatabase.load_auto(buffer_dir, preferred_name="features.fvdb")
            db_vectors = len(db.keys)
        except Exception:
            pass

    return {
        "images": {"count": image_count, "path": input_dir},
        "sim_targets": {"count": sim_count, "path": sim_dir},
        "id_targets": {"count": id_count, "path": id_dir},
        "database": {"exists": db_exists, "vectors": db_vectors, "path": db_path},
        "tasks": task_manager.iter_tasks(),
    }


@app.websocket("/api/ws/{task_id}")
async def websocket_handler(websocket: WebSocket, task_id: str):
    await websocket.accept()

    task = task_manager.get_task(task_id)
    if task is None:
        await websocket.send_json({"event": "error", "message": "Task not found"})
        await websocket.close()
        return

    try:
        while True:
            msg = await task.progress_queue.get()

            if msg.get("event") == "__done__":
                break

            await websocket.send_json(msg)

            if msg.get("event") == "error":
                break

    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


if SERVE_FRONTEND and os.path.isdir(DIST_DIR):
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi"):
            return JSONResponse({"error": "Not found"}, status_code=404)
        fpath = Path(DIST_DIR) / full_path
        if fpath.is_file():
            return FileResponse(str(fpath))
        index = Path(DIST_DIR) / "index.html"
        if index.is_file():
            return FileResponse(str(index))
        return JSONResponse({"error": "Not found"}, status_code=404)
