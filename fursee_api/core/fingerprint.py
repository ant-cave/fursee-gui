import os
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class FingerprintMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        fp = request.headers.get("X-Fingerprint", "").strip()
        request.state.fingerprint = fp if fp else "unknown"
        return await call_next(request)


def fp_prefix(fp: Optional[str]) -> str:
    if not fp or fp == "unknown":
        return ""
    return f"fp_{fp}"


def fp_path(base: str, fp: Optional[str], *parts: str) -> str:
    prefix = fp_prefix(fp)
    if prefix:
        return os.path.join(base, prefix, *parts)
    return os.path.join(base, *parts)


def fp_header(fp: Optional[str]) -> dict[str, str]:
    if not fp or fp == "unknown":
        return {}
    return {"X-Fingerprint": fp}
