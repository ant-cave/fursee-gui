import math
import os
import sqlite3
import time

UPLOAD_MAX_BYTES = 2 * 1024 * 1024 * 1024
UPLOAD_WINDOW = 86400
TASK_MAX_COUNT = 5
TASK_WINDOW = 3600

_ADMIN_TOKEN = os.environ.get("FURSEE_ADMIN_TOKEN", "")


def is_admin_token(token: str) -> bool:
    return bool(_ADMIN_TOKEN) and token == _ADMIN_TOKEN


def check_admin_login(ip: str) -> tuple[bool, float]:
    now = time.time()
    c = _conn()
    try:
        rows = c.execute("SELECT timestamp FROM rate_limits WHERE ip = ? AND type = 'admin_fail' ORDER BY timestamp DESC LIMIT 1", (ip,)).fetchall()
        elapsed = now - rows[0]["timestamp"] if rows else 999999
        fail_count_row = c.execute("SELECT COUNT(*) AS cnt FROM rate_limits WHERE ip = ? AND type = 'admin_fail'", (ip,)).fetchone()
        fail_count = fail_count_row["cnt"] if fail_count_row else 0
        if fail_count < 5:
            return True, 0.0
        delay = 2 ** (fail_count - 5)
        return (False, delay - elapsed) if elapsed < delay else (True, 0.0)
    finally:
        c.close()


def record_admin_fail(ip: str):
    c = _conn()
    try:
        c.execute("INSERT INTO rate_limits (ip, type, timestamp, bytes) VALUES (?, 'admin_fail', ?, 0)", (ip, time.time()))
        c.commit()
    finally:
        c.close()


def reset_admin_attempts(ip: str):
    c = _conn()
    try:
        c.execute("DELETE FROM rate_limits WHERE ip = ? AND type = 'admin_fail'", (ip,))
        c.commit()
    finally:
        c.close()


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
            bytes INTEGER DEFAULT 0,
            fp TEXT DEFAULT ''
        )
    """)
    for col in ("fp TEXT DEFAULT ''",):
        try:
            conn.execute(f"ALTER TABLE rate_limits ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_limits_ip_type ON rate_limits(ip, type, timestamp)
    """)
    conn.commit()
    return conn


def _clean(ip: str, fp: str = ""):
    now = time.time()
    c = _conn()
    try:
        c.execute("DELETE FROM rate_limits WHERE ip = ? AND type = 'upload' AND timestamp < ?", (ip, now - UPLOAD_WINDOW))
        c.execute("DELETE FROM rate_limits WHERE type = 'task' AND fp = ? AND timestamp < ?", (fp, now - TASK_WINDOW))
        c.commit()
    finally:
        c.close()


def record_upload(ip: str, bytes_count: int):
    c = _conn()
    try:
        c.execute("INSERT INTO rate_limits (ip, type, timestamp, bytes) VALUES (?, 'upload', ?, ?)", (ip, time.time(), bytes_count))
        c.commit()
    finally:
        c.close()


def check_upload(ip: str, needed_bytes: int = 0) -> tuple[bool, int, int]:
    _clean(ip)
    c = _conn()
    try:
        row = c.execute("SELECT COALESCE(SUM(bytes), 0) AS total FROM rate_limits WHERE ip = ? AND type = 'upload'", (ip,)).fetchone()
        total = row["total"]
        remaining = max(0, UPLOAD_MAX_BYTES - total)
        ok = total + needed_bytes <= UPLOAD_MAX_BYTES
        return ok, remaining, UPLOAD_MAX_BYTES
    finally:
        c.close()


def record_task(fp: str):
    c = _conn()
    try:
        c.execute("INSERT INTO rate_limits (ip, type, timestamp, bytes, fp) VALUES ('fp_task', 'task', ?, 0, ?)", (time.time(), fp))
        c.commit()
    finally:
        c.close()


def check_task(fp: str) -> tuple[bool, int, int]:
    _clean("", fp)
    c = _conn()
    try:
        row = c.execute("SELECT COUNT(*) AS cnt FROM rate_limits WHERE type = 'task' AND fp = ?", (fp,)).fetchone()
        count = row["cnt"]
        remaining = max(0, TASK_MAX_COUNT - count)
        return count < TASK_MAX_COUNT, remaining, TASK_MAX_COUNT
    finally:
        c.close()


def _next_reset_in(ip: str, rec_type: str, window: int, fp: str = "") -> int:
    now = time.time()
    c = _conn()
    try:
        if rec_type == "task":
            row = c.execute("SELECT MIN(timestamp) AS oldest FROM rate_limits WHERE type = ? AND fp = ?", (rec_type, fp)).fetchone()
        else:
            row = c.execute("SELECT MIN(timestamp) AS oldest FROM rate_limits WHERE ip = ? AND type = ?", (ip, rec_type)).fetchone()
        if row["oldest"] is None:
            return 0
        remaining = window - int(now - row["oldest"])
        return max(0, remaining)
    finally:
        c.close()


MAX_ACTIVE_FPS_PER_IP = 5


def _touch_fp(ip: str, fp: str):
    c = _conn()
    try:
        c.execute("DELETE FROM rate_limits WHERE ip = ? AND type = 'active_fp' AND fp = ?", (ip, fp))
        c.execute("INSERT INTO rate_limits (ip, type, timestamp, bytes, fp) VALUES (?, 'active_fp', ?, 0, ?)", (ip, time.time(), fp))
        c.execute("DELETE FROM rate_limits WHERE ip = ? AND type = 'active_fp' AND timestamp < ?", (ip, time.time() - 300))
        c.commit()
    finally:
        c.close()


def count_active_fps_for_ip(ip: str) -> int:
    c = _conn()
    try:
        c.execute("DELETE FROM rate_limits WHERE ip = ? AND type = 'active_fp' AND timestamp < ?", (ip, time.time() - 300))
        rows = c.execute("SELECT DISTINCT fp FROM rate_limits WHERE ip = ? AND type = 'active_fp'", (ip,)).fetchall()
        return len({r["fp"] for r in rows if r["fp"]})
    finally:
        c.close()


def is_over_queue_limit(ip: str, fp: str) -> bool:
    c = _conn()
    try:
        c.execute("DELETE FROM rate_limits WHERE ip = ? AND type = 'active_fp' AND timestamp < ?", (ip, time.time() - 300))
        rows = c.execute("SELECT DISTINCT fp FROM rate_limits WHERE ip = ? AND type = 'active_fp'", (ip,)).fetchall()
        active_fps = {r["fp"] for r in rows if r["fp"]}
        if fp in active_fps:
            return False
        if len(active_fps) >= MAX_ACTIVE_FPS_PER_IP:
            return True
        up_ok, _, _ = check_upload(ip)
        task_ok, _, _ = check_task(fp)
        if not up_ok or not task_ok:
            return False
        return False
    finally:
        c.close()


def get_active_fps() -> list[dict]:
    c = _conn()
    try:
        c.execute("DELETE FROM rate_limits WHERE type = 'active_fp' AND timestamp < ?", (time.time() - 300))
        rows = c.execute(
            "SELECT ip, fp, MIN(timestamp) AS since FROM rate_limits WHERE type = 'active_fp' GROUP BY ip, fp ORDER BY ip"
        ).fetchall()
        ip_groups: dict[str, list[dict]] = {}
        for r in rows:
            ip_groups.setdefault(r["ip"], []).append({
                "fp": r["fp"],
                "since": r["since"],
            })
        result = []
        for ip, fps in sorted(ip_groups.items()):
            blocked = len(fps) > MAX_ACTIVE_FPS_PER_IP
            for entry in fps:
                up_ok, up_rem, up_max = check_upload(ip)
                task_ok, task_rem, task_max = check_task(entry["fp"])
                result.append({
                    "ip": ip,
                    "fp": entry["fp"],
                    "since": entry["since"],
                    "upload_remaining": up_rem,
                    "upload_max": up_max,
                    "task_remaining": task_rem,
                    "task_max": task_max,
                    "ip_blocked": blocked,
                })
        return result
    finally:
        c.close()


def get_quota(ip: str, fp: str = "") -> dict:
    _clean(ip, fp)
    if fp:
        _touch_fp(ip, fp)
    up_ok, up_rem, up_max = check_upload(ip)
    task_ok, task_rem, task_max = check_task(fp)
    up_reset = _next_reset_in(ip, "upload", UPLOAD_WINDOW)
    task_reset = _next_reset_in("", "task", TASK_WINDOW, fp=fp)
    return {
        "ip": ip,
        "upload_remaining": up_rem,
        "upload_max": up_max,
        "upload_ok": up_ok,
        "upload_reset_in": up_reset,
        "task_remaining": task_rem,
        "task_max": task_max,
        "task_ok": task_ok,
        "task_reset_in": task_reset,
    }
