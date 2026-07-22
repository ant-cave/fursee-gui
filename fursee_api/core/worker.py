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

    task_type = task.type
    params = task.params

    if task_type == "db":
        return await _run_in_thread(_build_db, task.id, params)
    elif task_type == "classify":
        return await _run_in_thread(_classify, task.id, params)
    elif task_type == "similar":
        return await _run_in_thread(_similar, task.id, params)
    elif task_type == "identify":
        return await _run_in_thread(_identify, task.id, params)
    elif task_type == "auto":
        return await _run_in_thread(_auto_run, task.id, params)
    else:
        raise ValueError(f"Unknown task type: {task_type}")


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


def _build_db(params: dict) -> dict:
    from db import cold_build, append_build, build_parser
    from utils.vector_db import require_feature_db

    buffer_folder = params.get("buffer", "buffer")
    db_name = params.get("db_name", "features.fvdb")
    mode = params.get("mode", "cold")

    class Args:
        pass

    args = Args()
    args.input_folder = params.get("input_folder", os.path.join("input", "images"))
    args.buffer_folder = buffer_folder
    args.db_name = db_name
    args.model_path = params.get("model_path")
    args.conf = params.get("conf", 0.5)
    args.iou = params.get("iou", 0.45)
    args.imgsz = params.get("imgsz", 1280)
    args.batch_size = params.get("batch_size")
    args.num_workers = params.get("num_workers")
    args.augmentation_count = params.get("augmentation_count", 4)
    args.use_multi_gpu = params.get("use_multi_gpu", True)

    if mode == "cold":
        args.func = cold_build
        db_path = cold_build(args)
    elif mode == "append":
        args.append_folder = params.get("append_folder")
        args.func = append_build
        db_path = append_build(args)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    return {"db_path": str(db_path), "mode": mode}


def _classify(params: dict) -> dict:
    from utils.clustering import cluster_feature_db
    from utils.vector_db import require_feature_db
    from utils.common import float_range, int_range

    buffer_folder = params.get("buffer", "buffer")
    db_name = params.get("db_name", "features.fvdb")
    output_root = params.get("output_folder", os.path.join("output", "classify"))
    input_img_root = params.get("input_folder", os.path.join("input", "images"))

    eps_start = params.get("eps_start", 1.0)
    eps_stop = params.get("eps_stop", 2.0)
    eps_step = params.get("eps_step", 0.01)
    min_samples_start = params.get("min_samples_start", 2)
    min_samples_stop = params.get("min_samples_stop", 2)
    min_samples_step = params.get("min_samples_step", 1)
    use_augmentation = params.get("use_augmentation", True)

    db_path = require_feature_db(buffer_folder, db_name)

    eps_candidates = float_range(eps_start, eps_stop, eps_step)
    min_samples_candidates = int_range(min_samples_start, min_samples_stop, min_samples_step)

    cluster_feature_db(
        input_folder=buffer_folder,
        db_name=db_name,
        output_root=output_root,
        input_img_root=input_img_root,
        eps_tolerance_candidates=eps_candidates,
        min_samples_candidates=min_samples_candidates,
        clear_output=True,
        use_augmentation=use_augmentation,
    )

    return {
        "output_folder": str(output_root),
        "eps_candidates": len(eps_candidates),
        "min_samples_candidates": len(min_samples_candidates),
    }


def _similar(params: dict) -> dict:
    from similar import stage1_topk, extract_reference_items, stage3_topk

    buffer_folder = params.get("buffer", "buffer")
    db_name = params.get("db_name", "features.fvdb")
    input_folder = params.get("input_folder", os.path.join("input", "images"))
    target_folder = params.get("target_folder", os.path.join("input", "sim_targets"))
    output_folder = params.get("output_folder", os.path.join("output", "similar"))
    target_buffer = params.get("target_buffer", os.path.join("buffer", "similar"))
    k = params.get("k", 10)
    conf = params.get("conf", 0.5)
    iou = params.get("iou", 0.45)
    imgsz = params.get("imgsz", 1280)

    from utils.vector_db import require_feature_db
    require_feature_db(buffer_folder, db_name)

    crop_paths = stage1_topk(
        ref_folder=target_folder,
        output_folder=target_buffer,
        model_path=params.get("model_path"),
        conf=conf,
        iou=iou,
        imgsz=imgsz,
    )
    reference_items = extract_reference_items(crop_paths)
    stage3_topk(
        reference_items=reference_items,
        buffer_folder=buffer_folder,
        db_name=db_name,
        input_root=input_folder,
        output_folder=output_folder,
        k=k,
    )

    return {
        "output_folder": str(output_folder),
        "queries": len(reference_items),
        "k": k,
    }


def _identify(params: dict) -> dict:
    from utils.clustering import build_augmented_bundles, choose_dbscan_labels
    from utils.common import find_original_image, list_image_files, reset_directory
    from utils.detection import crop_largest_furry_targets
    from utils.embedding import extract_features_from_folder
    from utils.vector_db import VectorDatabase, require_feature_db
    import numpy as np
    import shutil

    buffer_folder = params.get("buffer", "buffer")
    db_name = params.get("db_name", "features.fvdb")
    input_folder = params.get("input_folder", os.path.join("input", "images"))
    target_folder = params.get("target_folder", os.path.join("input", "id_targets"))
    output_folder = params.get("output_folder", os.path.join("output", "identify"))
    target_buffer = params.get("target_buffer", os.path.join("buffer", "identify"))
    conf = params.get("conf", 0.5)
    iou = params.get("iou", 0.45)
    imgsz = params.get("imgsz", 1280)
    batch_size = params.get("batch_size")
    num_workers = params.get("num_workers")
    use_multi_gpu = params.get("use_multi_gpu", True)
    use_augmentation = params.get("use_augmentation", True)
    eps_start = params.get("eps_start", 1.0)
    eps_stop = params.get("eps_stop", 2.0)
    eps_step = params.get("eps_step", 0.01)
    min_samples_start = params.get("min_samples_start", 3)
    min_samples_stop = params.get("min_samples_stop", 3)
    min_samples_step = params.get("min_samples_step", 1)

    require_feature_db(buffer_folder, db_name)

    crop_largest_furry_targets(
        input_folder=target_folder,
        output_folder=target_buffer,
        model_path=params.get("model_path"),
        conf=conf,
        iou=iou,
        imgsz=imgsz,
        clear_output=True,
    )

    target_sources = {}
    for img_name in list_image_files(target_folder):
        stem = os.path.splitext(img_name)[0]
        target_sources[stem] = os.path.join(target_folder, img_name)

    feature_items = extract_features_from_folder(
        input_folder=target_buffer,
        batch_size=batch_size,
        num_workers=num_workers,
        use_multi_gpu=use_multi_gpu,
    )

    db = VectorDatabase.load_auto(buffer_folder, preferred_name=db_name)
    all_db_vectors = db.normalized_vectors()

    if use_augmentation:
        db_keys_for_clustering, db_vectors, _, _ = build_augmented_bundles(
            db.keys, all_db_vectors, db.metadata,
        )
        db_is_augmented = np.zeros(len(db_keys_for_clustering), dtype=bool)
    else:
        original_indices = np.where(~db.is_augmented_mask())[0]
        db_keys_for_clustering = [db.keys[int(i)] for i in original_indices]
        db_vectors = all_db_vectors[original_indices]
        db_is_augmented = np.zeros(len(db_keys_for_clustering), dtype=bool)

    target_vectors = np.asarray([item["vector"] for item in feature_items], dtype=np.float32)
    if target_vectors.ndim == 1:
        target_vectors = target_vectors.reshape(1, -1)
    target_vectors = target_vectors / (np.linalg.norm(target_vectors, axis=1, keepdims=True) + 1e-8)
    combined_vectors = np.vstack([db_vectors, target_vectors, target_vectors])

    eps_candidates = np.arange(eps_start, eps_stop + eps_step * 0.5, eps_step).tolist()
    eps_candidates = [round(v, 10) for v in eps_candidates]
    min_samples_candidates = list(range(min_samples_start, min_samples_stop + 1, min_samples_step))

    labels, best_params, best_score, best_eps = choose_dbscan_labels(
        combined_vectors,
        eps_tolerance_candidates=eps_candidates,
        min_samples_candidates=min_samples_candidates,
    )

    db_count = len(db_keys_for_clustering)
    db_labels = labels[:db_count]
    target_labels_all = labels[db_count:]
    output_indices = np.where(~db_is_augmented)[0]
    output_db_keys = [db_keys_for_clustering[int(i)] for i in output_indices]
    output_db_labels = db_labels[output_indices]

    label_folders = {}
    used_names = set()
    for item, label in zip(feature_items, target_labels_all):
        label = int(label)
        if label == -1 or label in label_folders:
            continue
        target_stem = os.path.splitext(os.path.basename(item["key"]))[0]
        base_stem = target_stem.rsplit("_target", 1)[0]
        src_path = target_sources.get(base_stem)
        if not src_path:
            continue
        folder_name = os.path.splitext(os.path.basename(src_path))[0]
        unique_name = folder_name
        s = 2
        while unique_name in used_names:
            unique_name = f"{folder_name}_{s}"
            s += 1
        used_names.add(unique_name)
        label_folders[label] = {"folder_name": unique_name, "source_path": src_path}

    if not label_folders:
        reset_directory(output_folder)
        return {
            "target_count": len(feature_items),
            "identified_classes": 0,
            "copy_count": 0,
        }

    reset_directory(output_folder)
    copied_sources = set()
    copied_count = 0
    for key, label in zip(output_db_keys, output_db_labels):
        label = int(label)
        if label not in label_folders:
            continue
        src_path = find_original_image(key, input_folder)
        if not src_path:
            continue
        copy_key = (label, os.path.abspath(src_path))
        if copy_key in copied_sources:
            continue
        class_folder = os.path.join(output_folder, label_folders[label]["folder_name"])
        os.makedirs(class_folder, exist_ok=True)
        shutil.copy2(src_path, os.path.join(class_folder, os.path.basename(src_path)))
        copied_sources.add(copy_key)
        copied_count += 1

    return {
        "target_count": len(feature_items),
        "identified_classes": len(label_folders),
        "copy_count": copied_count,
        "output_folder": str(output_folder),
    }


def _auto_run(params: dict) -> dict:
    from utils.detection import crop_furry_detections
    from utils.embedding import extract_features_to_db
    from utils.clustering import cluster_feature_db
    from utils.vector_db import require_feature_db
    from utils.common import float_range, int_range
    import os

    input_folder = params.get("input_folder", "input/auto_uploads")
    buffer_folder = params.get("buffer", "buffer/auto")
    output_folder = params.get("output_folder", "output/auto/classify")
    db_name = params.get("db_name", "features.fvdb")
    conf = params.get("conf", 0.5)
    iou = params.get("iou", 0.45)
    imgsz = params.get("imgsz", 1280)
    eps_start = params.get("eps_start", 1.0)
    eps_stop = params.get("eps_stop", 2.0)
    eps_step = params.get("eps_step", 0.01)
    use_augmentation = params.get("use_augmentation", True)
    augmentation_count = params.get("augmentation_count", 4)

    tq = _ProgressTqdm.write

    tq("Step 1/3: 检测并裁切目标...")
    crop_furry_detections(
        input_folder=input_folder,
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
        input_img_root=input_folder,
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

    tq("完成！")
    return {
        "output_folder": str(output_folder),
        "entries": result_entries,
        "total": sum(e["image_count"] for e in result_entries),
    }
