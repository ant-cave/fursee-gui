from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

from fursee_api.core.task_manager import TaskManager

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
    conf: float = Field(default=0.5, ge=0.01, le=0.99)
    iou: float = Field(default=0.45, ge=0.01, le=0.99)
    imgsz: int = Field(default=1280, ge=64, le=4096)
    eps_start: float = Field(default=1.0, ge=0.1, le=10.0)
    eps_stop: float = Field(default=2.0, ge=0.1, le=10.0)
    eps_step: float = Field(default=0.01, ge=0.001, le=1.0)
    use_augmentation: bool = True
    augmentation_count: int = Field(default=4, ge=1, le=50)
    existing_run_id: str = ""


@router.post("/auto")
async def run_auto(params: AutoParams, request: Request):
    if task_manager is None:
        raise HTTPException(503, "Task manager not initialized")
    pd = params.model_dump()
    try:
        task_id = await task_manager.submit("auto", pd)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return {"task_id": task_id}


@router.get("/tasks")
async def list_tasks(request: Request):
    if task_manager is None:
        raise HTTPException(503, "Task manager not initialized")
    return {"tasks": task_manager.iter_tasks()}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, request: Request):
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
