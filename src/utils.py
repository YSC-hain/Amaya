from datetime import datetime, timezone
from zoneinfo import ZoneInfo

__all__ = ["now_utc", "now_utc_min_str", "user_local_min_to_utc", "user_local_min_to_utc_min_str",
           "utc_to_user_local_min", "utc_min_str_to_user_local_min", "utc_str_to_user_local_min", "now_user_local_min"]

def now_utc() -> datetime:
    """获取当前 UTC 时间"""
    return datetime.now(timezone.utc)

def now_utc_min_str() -> str:
    """获取当前 UTC 时间字符串，格式: 'YYYY-MM-DD HH:MM'"""
    return now_utc().strftime("%Y-%m-%d %H:%M")

def user_local_min_to_utc(local_str: str, user_tz: str) -> datetime:
    # local_str: "YYYY-MM-DD HH:MM"
    naive = datetime.strptime(local_str, "%Y-%m-%d %H:%M")
    local_dt = naive.replace(tzinfo=ZoneInfo(user_tz))
    return local_dt.astimezone(timezone.utc)

def user_local_min_to_utc_min_str(local_str: str, user_tz: str) -> str:
    utc_dt = user_local_min_to_utc(local_str, user_tz)
    return utc_dt.strftime("%Y-%m-%d %H:%M")

def utc_to_user_local_min(utc_dt: datetime, user_tz: str) -> str:
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone(ZoneInfo(user_tz))
    return local_dt.strftime("%Y-%m-%d %H:%M")

def utc_min_str_to_user_local_min(utc_str: str, user_tz: str) -> str:
    utc_dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M")
    return utc_to_user_local_min(utc_dt, user_tz)

def utc_str_to_user_local_min(utc_str: str, user_tz: str) -> str:
    utc_dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone(ZoneInfo(user_tz))
    return local_dt.strftime("%Y-%m-%d %H:%M")

def now_user_local_min(user_tz: str) -> str:
    return utc_to_user_local_min(now_utc(), user_tz)
