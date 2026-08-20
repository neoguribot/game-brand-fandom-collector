"""Shared helper functions: logging, parsing, metrics, and classification."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from src.config import CONTENT_TYPES, LOG_FILE_PATH
from src.progress import DashboardLogHandler

_ISO8601_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+)D)?"
    r"T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)

_SHORTS_MAX_SECONDS = 60

_CONTENT_TYPE_KEYWORDS = {
    "hardware": ["console", "controller", "headset", "hardware", "unboxing"],
    "game_trailer": ["trailer", "gameplay", "teaser"],
    "game_announcement": ["announce", "announcement", "reveal", "coming soon"],
    "brand_event": ["showcase", "direct", "state of play", "event", "livestream", "live"],
    "brand_campaign": ["campaign", "commercial", "ad", "partnership"],
}


def setup_logging() -> logging.Logger:
    """Configure logging to both console and logs/collector.log."""
    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("fandom_collector")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter("[%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.addHandler(DashboardLogHandler())

    return logger


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_iso8601_duration(duration: Optional[str]) -> Optional[int]:
    """Convert an ISO-8601 duration (e.g. 'PT4M13S') into total seconds."""
    if not duration:
        return None
    match = _ISO8601_DURATION_RE.fullmatch(duration)
    if not match:
        return None
    parts = match.groupdict(default="0")
    days = int(parts["days"])
    hours = int(parts["hours"])
    minutes = int(parts["minutes"])
    seconds = int(parts["seconds"])
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def is_short(duration_seconds: Optional[int]) -> bool:
    if duration_seconds is None:
        return False
    return duration_seconds <= _SHORTS_MAX_SECONDS


def safe_int(value) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def compute_rate(numerator: Optional[int], denominator: Optional[int]) -> Optional[float]:
    if not denominator:
        return None
    if numerator is None:
        return None
    try:
        return round(numerator / denominator, 6)
    except ZeroDivisionError:
        return None


def compute_derived_metrics(
    view_count: Optional[int],
    like_count: Optional[int],
    comment_count: Optional[int],
) -> dict:
    like_rate = compute_rate(like_count, view_count)
    comment_rate = compute_rate(comment_count, view_count)

    engagement_rate = None
    if view_count:
        likes = like_count or 0
        comments = comment_count or 0
        if like_count is not None or comment_count is not None:
            engagement_rate = round((likes + comments) / view_count, 6)

    return {
        "like_rate": like_rate,
        "comment_rate": comment_rate,
        "engagement_rate": engagement_rate,
    }


def classify_content_type(title: str, description: str) -> str:
    """Rule-based classifier using keyword matching on title/description.

    Kept intentionally simple so it can be swapped for an LLM classifier later.
    """
    text = f"{title or ''} {description or ''}".lower()

    for content_type in CONTENT_TYPES:
        if content_type == "other":
            continue
        keywords = _CONTENT_TYPE_KEYWORDS.get(content_type, [])
        if any(keyword in text for keyword in keywords):
            return content_type

    return "other"


def anonymize_author(author_name: Optional[str], anonymize: bool) -> Optional[str]:
    if anonymize:
        return None
    return author_name


def build_video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def build_comment_url(video_id: str, comment_id: str) -> Optional[str]:
    if not video_id or not comment_id:
        return None
    return f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"


def strip_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return " ".join(value.split())
