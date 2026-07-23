from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from fursee_api.core.task_manager import TaskManager
from fursee_api.core.ratelimit import check_task, is_admin_token, record_task

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

task_manager: Optional[TaskManager] = None


def init(tm: TaskManager) -> None:
    global task_manager
    task_manager = tm


class AutoParams(BaseModel):
    input_folder: str = "input/auto_uploads"
    buffer: str = "buffer/auto"
    db_name: str = "features.fvdb"
    output_folder: str = "output/auto/classify"
    conf: float = 0.5
    iou: float = 0.45
    imgsz: int = 1280
    eps_start: float = 1.0
    eps_stop: float = 2.0
    eps_step: float = 0.01
    use_augmentation: bool = True
    augmentation_count: int = 4
    existing_run_id: str = ""


@router.post("/auto")
async def run_auto(params: AutoParams, request: Request):
    if task_manager is None:
        raise HTTPException(503, "Task manager not initialized")
    if not is_admin_token(request.headers.get("x-admin-token", "")):
        ip = request.client.host if request.client else "unknown"
        ok, remaining, _ = check_task(ip)
        if not ok:
            raise HTTPException(429, "任务配额已用尽，请等待额度刷新")
        record_task(ip)
    pd = params.model_dump()
    pd["fingerprint"] = getattr(request.state, "fingerprint", "unknown")
    task_id = await task_manager.submit("auto", pd)
    return {"task_id": task_id}


@router.get("/tasks")
async def list_tasks():
    if task_manager is None:
        raise HTTPException(503, "Task manager not initialized")
    return {"tasks": task_manager.iter_tasks()}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    if task_manager is None:
        raise HTTPException(503, "Task manager not initialized")
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return {
        "id": task.id,
        "type": task.type,
        "state": task.state.value,
        "params": task.params,
        "result": task.result,
        "error": task.error,
    }
