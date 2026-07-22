from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from fursee_api.core.task_manager import TaskManager, TaskState

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

task_manager: Optional[TaskManager] = None


def init(tm: TaskManager) -> None:
    global task_manager
    task_manager = tm


class DbParams(BaseModel):
    mode: str = "cold"
    input_folder: str = "input/images"
    buffer: str = "buffer"
    db_name: str = "features.fvdb"
    model_path: Optional[str] = None
    conf: float = 0.5
    iou: float = 0.45
    imgsz: int = 1280
    batch_size: Optional[int] = None
    num_workers: Optional[int] = None
    augmentation_count: int = 4
    use_multi_gpu: bool = True
    append_folder: Optional[str] = None


class ClassifyParams(BaseModel):
    buffer: str = "buffer"
    db_name: str = "features.fvdb"
    input_folder: str = "input/images"
    output_folder: str = "output/classify"
    eps_start: float = 1.0
    eps_stop: float = 2.0
    eps_step: float = 0.01
    min_samples_start: int = 2
    min_samples_stop: int = 2
    min_samples_step: int = 1
    use_augmentation: bool = True


class SimilarParams(BaseModel):
    buffer: str = "buffer"
    db_name: str = "features.fvdb"
    input_folder: str = "input/images"
    target_folder: str = "input/sim_targets"
    output_folder: str = "output/similar"
    target_buffer: str = "buffer/similar"
    k: int = 10
    conf: float = 0.5
    iou: float = 0.45
    imgsz: int = 1280
    model_path: Optional[str] = None


class IdentifyParams(BaseModel):
    buffer: str = "buffer"
    db_name: str = "features.fvdb"
    input_folder: str = "input/images"
    target_folder: str = "input/id_targets"
    output_folder: str = "output/identify"
    target_buffer: str = "buffer/identify"
    conf: float = 0.5
    iou: float = 0.45
    imgsz: int = 1280
    model_path: Optional[str] = None
    batch_size: Optional[int] = None
    num_workers: Optional[int] = None
    use_multi_gpu: bool = True
    use_augmentation: bool = True
    eps_start: float = 1.0
    eps_stop: float = 2.0
    eps_step: float = 0.01
    min_samples_start: int = 3
    min_samples_stop: int = 3
    min_samples_step: int = 1


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


@router.post("/auto")
async def run_auto(params: AutoParams):
    if task_manager is None:
        raise HTTPException(503, "Task manager not initialized")
    task_id = await task_manager.submit("auto", params.model_dump())
    return {"task_id": task_id}


@router.post("/db")
async def run_db(params: DbParams):
    if task_manager is None:
        raise HTTPException(503, "Task manager not initialized")
    task_id = await task_manager.submit("db", params.model_dump())
    return {"task_id": task_id}


@router.post("/classify")
async def run_classify(params: ClassifyParams):
    if task_manager is None:
        raise HTTPException(503, "Task manager not initialized")
    task_id = await task_manager.submit("classify", params.model_dump())
    return {"task_id": task_id}


@router.post("/similar")
async def run_similar(params: SimilarParams):
    if task_manager is None:
        raise HTTPException(503, "Task manager not initialized")
    task_id = await task_manager.submit("similar", params.model_dump())
    return {"task_id": task_id}


@router.post("/identify")
async def run_identify(params: IdentifyParams):
    if task_manager is None:
        raise HTTPException(503, "Task manager not initialized")
    task_id = await task_manager.submit("identify", params.model_dump())
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
