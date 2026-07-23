import json
import os
import sqlite3

DB_PATH = os.path.join("output", "auto", "auto.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL,
            run_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            entries TEXT NOT NULL,
            total INTEGER NOT NULL,
            pipeline TEXT NOT NULL DEFAULT 'auto',
            buffer_path TEXT NOT NULL DEFAULT '',
            UNIQUE(fingerprint, run_id)
        )
    """)
    for col in ("pipeline TEXT NOT NULL DEFAULT 'auto'", "buffer_path TEXT NOT NULL DEFAULT ''"):
        try:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_runs_fingerprint ON runs(fingerprint)
    """)
    conn.commit()
    return conn


def add_run(fingerprint: str, run_id: str, timestamp: float,
            entries: list[dict], total: int, *,
            pipeline: str = "auto", buffer_path: str = ""):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO runs (fingerprint, run_id, timestamp, entries, total, pipeline, buffer_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fingerprint, run_id, timestamp,
             json.dumps(entries, ensure_ascii=False), total,
             pipeline, buffer_path),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


def update_run(fingerprint: str, run_id: str, entries: list[dict],
               total: int, timestamp: float, buffer_path: str = ""):
    conn = _get_conn()
    conn.execute(
        "UPDATE runs SET entries = ?, total = ?, timestamp = ?, buffer_path = ? "
        "WHERE fingerprint = ? AND run_id = ?",
        (json.dumps(entries, ensure_ascii=False), total, timestamp, buffer_path,
         fingerprint, run_id),
    )
    conn.commit()
    conn.close()


def get_runs(fingerprint: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT run_id, timestamp, entries, total, pipeline, buffer_path FROM runs "
        "WHERE fingerprint = ? ORDER BY id ASC",
        (fingerprint,),
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


def delete_run(fingerprint: str, run_id: str) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "DELETE FROM runs WHERE fingerprint = ? AND run_id = ?",
        (fingerprint, run_id),
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def get_run(fingerprint: str, run_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT run_id, timestamp, entries, total, pipeline, buffer_path FROM runs "
        "WHERE fingerprint = ? AND run_id = ?",
        (fingerprint, run_id),
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
