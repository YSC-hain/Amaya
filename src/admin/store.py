from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path
from typing import Any

import storage.db_config as db_config
from fastapi import HTTPException

_LOG_LEVEL_RE = re.compile(r"\|\s*([A-Z]+)\s*\|")
_ALLOWED_LOG_LEVELS = {"TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def ensure_conn() -> None:
    if db_config.conn is None:
        raise HTTPException(status_code=503, detail="数据库尚未就绪")


async def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    ensure_conn()
    assert db_config.conn is not None
    rows: list[dict[str, Any]] = []
    async with db_config.conn.execute(sql, params) as cursor:
        col_names = [c[0] for c in cursor.description]
        async for row in cursor:
            rows.append({col_names[i]: row[i] for i in range(len(col_names))})
    return rows


async def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = await fetch_all(sql, params)
    return rows[0] if rows else None


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def tail_lines(path: Path, lines: int) -> list[str]:
    if not path.exists():
        return []
    buf = deque(maxlen=lines)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            buf.append(line.rstrip("\n"))
    return list(buf)


def normalize_log_levels(levels: list[str] | None) -> set[str]:
    if not levels:
        return set()
    normalized: set[str] = set()
    for level in levels:
        lv = str(level).upper().strip()
        if lv in _ALLOWED_LOG_LEVELS:
            normalized.add(lv)
    return normalized


def filter_logs(
    lines: list[str],
    levels: list[str] | None = None,
    keyword: str | None = None,
) -> list[str]:
    target_levels = normalize_log_levels(levels)
    target_keyword = (keyword or "").strip().lower()

    if not target_levels and not target_keyword:
        return lines

    filtered: list[str] = []
    for line in lines:
        if target_levels:
            match = _LOG_LEVEL_RE.search(line)
            if not match or match.group(1) not in target_levels:
                continue
        if target_keyword and target_keyword not in line.lower():
            continue
        filtered.append(line)

    return filtered


def sanitize_source(source: str) -> str:
    cleaned = source.strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", cleaned):
        raise HTTPException(status_code=400, detail="非法 webhook source")
    return cleaned
