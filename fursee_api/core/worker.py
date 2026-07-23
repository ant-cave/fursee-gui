import asyncio
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from fursee_api.core.task_manager import Task, TaskManager

_thread_pool = ThreadPoolExecutor(max_workers=1)
_current_task = threading.local()
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def _validate_input_images(folder: str, log):
    if not os.path.isdir(folder):
        return
    removed = 0
    for fname in os.listdir(folder):
        fpath = os.path.join(folder, fname)
        if not os.path.isfile(fpath):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"):
            continue
        try:
            from PIL import Image
            img = Image.open(fpath)
            img.verify()
        except Exception:
            os.remove(fpath)
            removed += 1
    if removed:
        log(f"已删除 {removed} 个无效图片文件")
    import warnings
    warnings.filterwarnings("ignore", message=".*Corrupt JPEG.*")
    import logging
    logging.getLogger("PIL").setLevel(logging.ERROR)


class _ProgressTqdm:
    _task_id: str = ""

    @classmethod
    def set_task_id(cls, task_id: str) -> None:
        cls._task_id = task_id

    @classmethod
    def write(cls, msg: str, **kwargs: Any) -> None:
        loop = _get_loop()
        if loop and cls._task_id:
            asyncio.run_coroutine_threadsafe(
                _send_log(cls._task_id, msg), loop
            )

    def __init__(self, iterable=None, desc=None, total=None, unit=None, **kwargs):
        self._iterable = iterable
        self._desc = desc or ""
        self._unit = unit or "it"
        self._n = 0
        self._closed = False
        if total is None and iterable is not None:
            try:
                self._total = len(iterable)
            except (TypeError, AttributeError):
                self._total = None
        else:
            self._total = total

    def __iter__(self):
        self._iterator = iter(self._iterable) if self._iterable is not None else iter([])
        return self

    def __next__(self):
        try:
            val = next(self._iterator)
            self._n += 1
            self._report()
            return val
        except StopIteration:
            self._close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._close()

    def update(self, n=1):
        self._n += n
        self._report()

    @property
    def n(self):
        return self._n

    @n.setter
    def n(self, value):
        self._n = value

    def close(self):
        self._close()

    def _report(self):
        loop = _get_loop()
        if loop and self._task_id:
            asyncio.run_coroutine_threadsafe(
                _send_progress(self._task_id, self._desc, self._n, self._total), loop
            )

    def _close(self):
        if not self._closed:
            self._closed = True
            self._report()

    def __len__(self):
        if self._total is not None:
            return self._total
        return 0

    def __bool__(self):
        return True


def _get_loop() -> Optional[asyncio.AbstractEventLoop]:
    if _main_loop is not None:
        return _main_loop
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


async def _send_progress(task_id: str, stage: str, current: int, total: Optional[int]):
    from fursee_api.core.task_manager import TaskManager
    tm = _get_task_manager()
    if tm is None:
        return
    task = tm.get_task(task_id)
    if task is None:
        return
    await task.progress_queue.put({
        "event": "progress",
        "stage": stage,
        "current": current,
        "total": total,
    })


async def _send_log(task_id: str, message: str):
    from fursee_api.core.task_manager import TaskManager
    tm = _get_task_manager()
    if tm is None:
        return
    task = tm.get_task(task_id)
    if task is None:
        return
    await task.progress_queue.put({
        "event": "log",
        "message": message,
    })


_task_manager_obj: Optional[TaskManager] = None


def set_task_manager(tm: TaskManager) -> None:
    global _task_manager_obj
    _task_manager_obj = tm


def _get_task_manager() -> Optional[TaskManager]:
    return _task_manager_obj


async def process_pipeline(task: Task) -> dict[str, Any]:
    global _main_loop
    _main_loop = asyncio.get_running_loop()

    if task.type == "auto":
        return await _run_in_thread(_auto_run, task.id, task.params)
    raise ValueError(f"Unknown task type: {task.type}")


async def _run_in_thread(func, task_id: str, params: dict) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _thread_pool,
        _wrap_with_hooks,
        func,
        task_id,
        params,
    )


def _wrap_with_hooks(func, task_id: str, params: dict) -> dict:
    _current_task.id = task_id
    _ProgressTqdm.set_task_id(task_id)

    import utils.detection as det_mod
    import utils.embedding as emb_mod
    import utils.clustering as clus_mod

    _patches = {}

    for mod in (det_mod, emb_mod, clus_mod):
        _patches[id(mod)] = mod.tqdm
        mod.tqdm = _ProgressTqdm

    try:
        _ProgressTqdm.write(f"Starting task {task_id}")
        result = func(params)
        return result
    finally:
        for mod in (det_mod, emb_mod, clus_mod):
            if id(mod) in _patches:
                mod.tqdm = _patches[id(mod)]
        _current_task.id = None


def _auto_run(params: dict) -> dict:
    from utils.detection import crop_furry_detections
    from utils.embedding import extract_features_to_db, extract_features_from_folder
    from utils.clustering import cluster_feature_db
    from utils.vector_db import require_feature_db, VectorDatabase
    from utils.common import float_range, reset_directory
    from datetime import datetime
    import shutil
    import os

    input_uploads = params.get("input_folder", "input/auto_uploads")
    buffer_root = params.get("buffer", "buffer/auto")
    output_root = params.get("output_folder", "output/auto/classify")
    db_name = params.get("db_name", "features.fvdb")

    existing_run_id = params.get("existing_run_id", "")

    run_id = existing_run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = os.path.join(output_root, run_id)
    buffer_folder = os.path.join(buffer_root, run_id)

    conf = params.get("conf", 0.5)
    iou = params.get("iou", 0.45)
    imgsz = params.get("imgsz", 1280)
    eps_start = params.get("eps_start", 1.0)
    eps_stop = params.get("eps_stop", 2.0)
    eps_step = params.get("eps_step", 0.01)
    use_augmentation = params.get("use_augmentation", True)
    augmentation_count = params.get("augmentation_count", 4)

    tq = _ProgressTqdm.write

    is_append = bool(existing_run_id and os.path.isdir(output_folder))

    merge_folder = os.path.join(buffer_root, f"merge_{run_id}")

    if is_append:
        tq("附加模式：合并旧图片与新图片...")
        os.makedirs(merge_folder, exist_ok=True)
        for root, dirs, files in os.walk(output_folder):
            for fname in files:
                if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    src = os.path.join(root, fname)
                    dst = os.path.join(merge_folder, fname)
                    if not os.path.isfile(dst):
                        shutil.copy2(src, dst)
        for fname in os.listdir(input_uploads):
            if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                src = os.path.join(input_uploads, fname)
                dst = os.path.join(merge_folder, fname)
                if not os.path.isfile(dst):
                    shutil.copy2(src, dst)
        input_source = merge_folder
    else:
        input_source = input_uploads

    _validate_input_images(input_source, tq)

    db_path = os.path.join(buffer_folder, db_name)

    if is_append and os.path.isfile(db_path):
        tq("附加模式：复用旧特征库，仅处理新图...")
        old_db = VectorDatabase.load_auto(buffer_folder, preferred_name=db_name)
        temp_buffer = os.path.join(buffer_root, f"temp_{run_id}")
        crop_furry_detections(
            input_folder=input_source,
            output_folder=temp_buffer,
            conf=conf, iou=iou, imgsz=imgsz,
            clear_output=True,
        )
        new_items = extract_features_from_folder(input_folder=temp_buffer)
        if new_items:
            old_db.add_many(new_items)
            old_db.save(db_path)
        if os.path.isdir(temp_buffer):
            for fname in os.listdir(temp_buffer):
                if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    src = os.path.join(temp_buffer, fname)
                    dst = os.path.join(buffer_folder, fname)
                    if os.path.isfile(src) and not os.path.isfile(dst):
                        shutil.copy2(src, dst)
            shutil.rmtree(temp_buffer, ignore_errors=True)
    else:
        tq("Step 1/3: 检测并裁切目标...")
        crop_furry_detections(
            input_folder=input_source,
            output_folder=buffer_folder,
            conf=conf, iou=iou, imgsz=imgsz,
            clear_output=True,
        )
        tq("Step 2/3: 提取特征向量...")
        extract_features_to_db(
            input_folder=buffer_folder,
            db_name=db_name,
            augmentation_count=augmentation_count if use_augmentation else 1,
        )

    tq("Step 3/3: 聚类分组...")
    require_feature_db(buffer_folder, db_name)
    eps_candidates = float_range(eps_start, eps_stop, eps_step)
    cluster_feature_db(
        input_folder=buffer_folder,
        db_name=db_name,
        output_root=output_folder,
        input_img_root=input_source,
        eps_tolerance_candidates=eps_candidates,
        min_samples_candidates=[2, 3],
        clear_output=True,
        use_augmentation=use_augmentation,
    )

    result_entries = []
    for class_name in sorted(os.listdir(output_folder)):
        class_path = os.path.join(output_folder, class_name)
        if os.path.isdir(class_path):
            images = sorted([
                f for f in os.listdir(class_path)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
            ])
            result_entries.append({
                "name": class_name,
                "image_count": len(images),
                "images": images,
            })

    reset_directory(input_uploads)
    if os.path.isdir(merge_folder):
        shutil.rmtree(merge_folder, ignore_errors=True)

    from fursee_api.core.database import add_run, update_run

    now_ts = datetime.now().timestamp()
    total = sum(e["image_count"] for e in result_entries)

    if is_append:
        update_run(run_id, result_entries, total, now_ts, buffer_path=buffer_folder)
    else:
        add_run(
            run_id=run_id,
            timestamp=now_ts,
            entries=result_entries,
            total=total,
            pipeline="auto",
            buffer_path=buffer_folder,
        )

    tq("完成！")
    return {
        "run_id": run_id,
        "output_folder": str(output_folder),
        "entries": result_entries,
        "total": total,
    }
