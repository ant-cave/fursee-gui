import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional


class TaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    type: str
    params: dict[str, Any]
    state: TaskState = TaskState.QUEUED
    progress_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


ProcessorFunc = Callable[[Task], Coroutine[Any, Any, dict[str, Any]]]


class TaskManager:
    def __init__(self):
        self._queue: asyncio.Queue[Task] = asyncio.Queue()
        self._tasks: dict[str, Task] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._processor: Optional[ProcessorFunc] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

    def set_processor(self, func: ProcessorFunc) -> None:
        self._processor = func

    async def start(self) -> None:
        self._event_loop = asyncio.get_running_loop()
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()

    async def submit(self, task_type: str, params: dict[str, Any]) -> str:
        task_id = uuid.uuid4().hex[:12]
        task = Task(id=task_id, type=task_type, params=params)
        self._tasks[task_id] = task
        await self._queue.put(task)
        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    async def _worker_loop(self) -> None:
        while True:
            task = await self._queue.get()
            task.state = TaskState.RUNNING
            try:
                if self._processor:
                    result = await self._processor(task)
                    task.state = TaskState.COMPLETED
                    task.result = result
                    await task.progress_queue.put({"event": "complete", "output": result})
            except Exception as e:
                task.state = TaskState.FAILED
                task.error = str(e)
                await task.progress_queue.put({"event": "error", "message": str(e)})
            finally:
                await task.progress_queue.put({"event": "__done__"})

    def iter_tasks(self) -> list[dict[str, Any]]:
        return [
            {
                "id": t.id,
                "type": t.type,
                "state": t.state.value,
                "params": t.params,
                "error": t.error,
            }
            for t in sorted(self._tasks.values(), key=lambda x: x.id, reverse=True)
        ]
