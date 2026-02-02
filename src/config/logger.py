"""日志模块

级别支持: TRACE/DEBUG/INFO/WARNING/ERROR/CRITICAL (兼容别名 FATAL -> CRITICAL)

使用：先调用 setup_logging 配置日志，然后 logger.info(...) 等写日志

ToDo: 审查代码
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, Union

from loguru import logger

LogLevel = Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "FATAL"]

CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level:<8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
    "{name}:{function}:{line} - {message}"
)

_LEVEL_ALIAS = {"FATAL": "CRITICAL"}


def _normalize_level(level: Union[str, LogLevel]) -> str:
    return _LEVEL_ALIAS.get(str(level).upper(), str(level).upper())


def _file_handler(
    path: Path,
    *,
    level: str,
    retention: str,
) -> dict:
    return {
        "sink": path,
        "level": level,
        "format": FILE_FORMAT,
        "rotation": "10 MB",
        "retention": retention,
        "compression": "zip",
        "encoding": "utf-8",
    }


def setup_logging(
    log_level: LogLevel,
    log_file: Union[str, Path],
    console_level: LogLevel = "INFO",
) -> None:
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_level = _normalize_level(log_level)
    console_lv = _normalize_level(console_level)

    error_log_file = log_file.with_name(f"{log_file.stem}_error{log_file.suffix}")

    logger.configure(
        handlers=[
            {
                "sink": sys.stderr,
                "level": console_lv,
                "format": CONSOLE_FORMAT,
                "colorize": True,
            },
            _file_handler(log_file, level=file_level, retention="30 days"),
            _file_handler(error_log_file, level="ERROR", retention="90 days"),
        ]
    )


def get_logger():
    """
    返回全局 logger。
    """
    return logger


__all__ = ["setup_logging", "get_logger", "logger"]
