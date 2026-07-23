import os
import sqlite3
import time

UPLOAD_MAX_BYTES = 1 * 1024 * 1024 * 1024
UPLOAD_WINDOW = 3600
TASK_MAX_COUNT = 4
TASK_WINDOW = 600

_ADMIN_TOKEN = os.environ.get("FURSEE_ADMIN_TOKEN", "")


def is_admin_token(token: str) -> bool:
    return bool(_ADMIN_TOKEN) and token == _ADMIN_TOKEN


def _conn() -> sqlite3.Connection:
    from fursee_api.core.database import DB_PATH
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            type TEXT NOT NULL,
            timestamp REAL NOT NULL,
            bytes INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_limits_ip_type ON rate_limits(ip, type, timestamp)
    """)
    conn.commit()
    return conn


def _clean(ip: str):
    now = time.time()
    c = _conn()
    try:
        c.execute("DELETE FROM rate_limits WHERE ip = ? AND type = 'upload' AND timestamp < ?",
                  (ip, now - UPLOAD_WINDOW))
        c.execute("DELETE FROM rate_limits WHERE ip = ? AND type = 'task' AND timestamp < ?",
                  (ip, now - TASK_WINDOW))
        c.commit()
    finally:
        c.close()


def record_upload(ip: str, bytes_count: int):
    c = _conn()
    try:
        c.execute("INSERT INTO rate_limits (ip, type, timestamp, bytes) VALUES (?, 'upload', ?, ?)",
                  (ip, time.time(), bytes_count))
        c.commit()
    finally:
        c.close()


def check_upload(ip: str) -> tuple[bool, int, int]:
    _clean(ip)
    c = _conn()
    try:
        row = c.execute("SELECT COALESCE(SUM(bytes), 0) AS total FROM rate_limits "
                        "WHERE ip = ? AND type = 'upload'", (ip,)).fetchone()
        total = row["total"]
        remaining = max(0, UPLOAD_MAX_BYTES - total)
        return total < UPLOAD_MAX_BYTES, remaining, UPLOAD_MAX_BYTES
    finally:
        c.close()


def record_task(ip: str):
    c = _conn()
    try:
        c.execute("INSERT INTO rate_limits (ip, type, timestamp, bytes) VALUES (?, 'task', ?, 0)",
                  (ip, time.time()))
        c.commit()
    finally:
        c.close()


def check_task(ip: str) -> tuple[bool, int, int]:
    _clean(ip)
    c = _conn()
    try:
        row = c.execute("SELECT COUNT(*) AS cnt FROM rate_limits "
                        "WHERE ip = ? AND type = 'task'", (ip,)).fetchone()
        count = row["cnt"]
        remaining = max(0, TASK_MAX_COUNT - count)
        return count < TASK_MAX_COUNT, remaining, TASK_MAX_COUNT
    finally:
        c.close()


def _next_reset_in(ip: str, rec_type: str, window: int) -> int:
    now = time.time()
    c = _conn()
    try:
        row = c.execute("SELECT MIN(timestamp) AS oldest FROM rate_limits "
                        "WHERE ip = ? AND type = ?", (ip, rec_type)).fetchone()
        if row["oldest"] is None:
            return 0
        remaining = window - int(now - row["oldest"])
        return max(0, remaining)
    finally:
        c.close()


def get_quota(ip: str) -> dict:
    _clean(ip)
    up_ok, up_rem, up_max = check_upload(ip)
    task_ok, task_rem, task_max = check_task(ip)
    up_reset = _next_reset_in(ip, "upload", UPLOAD_WINDOW)
    task_reset = _next_reset_in(ip, "task", TASK_WINDOW)
    next_in = min(r for r in (up_reset, task_reset) if r) if (up_reset or task_reset) else 0
    return {
        "ip": ip,
        "upload_remaining": up_rem,
        "upload_max": up_max,
        "upload_ok": up_ok,
        "task_remaining": task_rem,
        "task_max": task_max,
        "task_ok": task_ok,
        "next_reset_in": next_in,
    }
