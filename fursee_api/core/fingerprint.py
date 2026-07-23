import hashlib
import os
import secrets
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class FingerprintMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            hdr_fp = request.headers.get("X-Fingerprint", "").strip()
            cookie_fp = request.cookies.get("fursee_fp", "").strip()
            if not hdr_fp or not cookie_fp or hdr_fp != cookie_fp:
                return JSONResponse({"error": "Forbidden"}, status_code=403)
            request.state.fingerprint = hdr_fp
            response = await call_next(request)
        else:
            response = await call_next(request)
        return response


def generate_fp() -> str:
    return secrets.token_hex(16)


def hash_fp(fp: str) -> str:
    return hashlib.sha256(fp.encode()).hexdigest()[:16]


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
