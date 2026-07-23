import json
import os
import sqlite3
import time

DB_PATH = os.path.join("output", "auto", "auto.db")
AUTO_CLEANUP_HOURS = 72


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL UNIQUE,
            timestamp REAL NOT NULL,
            entries TEXT NOT NULL,
            total INTEGER NOT NULL,
            pipeline TEXT NOT NULL DEFAULT 'auto',
            buffer_path TEXT NOT NULL DEFAULT ''
        )
    """)
    for col in ("pipeline TEXT NOT NULL DEFAULT 'auto'", "buffer_path TEXT NOT NULL DEFAULT ''"):
        try:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return conn


def clean_old_runs():
    import shutil
    cutoff = time.time() - AUTO_CLEANUP_HOURS * 3600
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT run_id, buffer_path FROM runs WHERE timestamp < ?",
            (cutoff,),
        ).fetchall()
        for row in rows:
            bp = row["buffer_path"]
            if bp and os.path.isdir(bp):
                shutil.rmtree(bp, ignore_errors=True)
            classify_root = os.path.join(os.path.dirname(DB_PATH), "classify")
            for maybe_dir in os.listdir(classify_root) if os.path.isdir(classify_root) else []:
                full = os.path.join(classify_root, maybe_dir)
                if os.path.isdir(full):
                    sub = os.path.join(full, row["run_id"])
                    if os.path.isdir(sub):
                        shutil.rmtree(sub, ignore_errors=True)
        conn.execute("DELETE FROM runs WHERE timestamp < ?", (cutoff,))
        conn.commit()
    finally:
        conn.close()
    stale_uploads = os.path.join("input", "auto_uploads")
    if os.path.isdir(stale_uploads):
        for fname in os.listdir(stale_uploads):
            fpath = os.path.join(stale_uploads, fname)
            if os.path.isfile(fpath) and time.time() - os.path.getmtime(fpath) > AUTO_CLEANUP_HOURS * 3600:
                os.remove(fpath)


def add_run(run_id: str, timestamp: float,
            entries: list[dict], total: int, *,
            pipeline: str = "auto", buffer_path: str = ""):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO runs (run_id, timestamp, entries, total, pipeline, buffer_path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, timestamp,
             json.dumps(entries, ensure_ascii=False), total,
             pipeline, buffer_path),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


def update_run(run_id: str, entries: list[dict],
               total: int, timestamp: float, buffer_path: str = ""):
    conn = _get_conn()
    conn.execute(
        "UPDATE runs SET entries = ?, total = ?, timestamp = ?, buffer_path = ? "
        "WHERE run_id = ?",
        (json.dumps(entries, ensure_ascii=False), total, timestamp, buffer_path,
         run_id),
    )
    conn.commit()
    conn.close()


def get_runs() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT run_id, timestamp, entries, total, pipeline, buffer_path FROM runs ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [
        {
            "run_id": row["run_id"],
            "timestamp": row["timestamp"],
            "entries": json.loads(row["entries"]),
            "total": row["total"],
            "pipeline": row["pipeline"],
            "buffer_path": row["buffer_path"],
        }
        for row in rows
    ]


def delete_run(run_id: str) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "DELETE FROM runs WHERE run_id = ?",
        (run_id,),
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def get_run(run_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT run_id, timestamp, entries, total, pipeline, buffer_path FROM runs "
        "WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "run_id": row["run_id"],
        "timestamp": row["timestamp"],
        "entries": json.loads(row["entries"]),
        "total": row["total"],
        "pipeline": row["pipeline"],
        "buffer_path": row["buffer_path"],
    }
