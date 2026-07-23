import os
from typing import Optional


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
