from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).with_name("templates")


@lru_cache(maxsize=2)
def _load_template(name: str) -> str:
    path = _TEMPLATE_DIR / name
    return path.read_text(encoding="utf-8")


def login_page_html() -> str:
    return _load_template("login.html")


def dashboard_html() -> str:
    return _load_template("dashboard.html")
