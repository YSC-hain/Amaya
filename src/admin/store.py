from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path
from typing import Any

import storage.db_config as db_config
from fastapi import HTTPException

_LOG_LEVEL_RE = re.compile(r"\|\s*([A-Z]+)\s*\|")


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


def filter_log_by_level(lines: list[str], level: str | None) -> list[str]:
    if not level:
        return lines
    target = level.upper().strip()
    if not target:
        return lines

    filtered: list[str] = []
    for line in lines:
        match = _LOG_LEVEL_RE.search(line)
        if match and match.group(1) == target:
            filtered.append(line)
    return filtered


def sanitize_source(source: str) -> str:
    cleaned = source.strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", cleaned):
        raise HTTPException(status_code=400, detail="非法 webhook source")
    return cleaned
