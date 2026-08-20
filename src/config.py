"""Central configuration for the Game Brand Fandom Collector."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
RAW_VIDEOS_DIR = DATA_DIR / "raw" / "videos"
RAW_COMMENTS_DIR = DATA_DIR / "raw" / "comments"
PROCESSED_DIR = DATA_DIR / "processed"
LOGS_DIR = PROJECT_ROOT / "logs"

BRANDS_CONFIG_PATH = CONFIG_DIR / "brands.json"
LOG_FILE_PATH = LOGS_DIR / "collector.log"

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

CONTENT_TYPES = (
    "hardware",
    "game_trailer",
    "game_announcement",
    "brand_event",
    "brand_campaign",
    "other",
)

VIDEO_CSV_COLUMNS = [
    "brand",
    "channel_name",
    "channel_id",
    "video_id",
    "video_title",
    "video_description",
    "published_at",
    "video_url",
    "duration",
    "view_count",
    "like_count",
    "comment_count",
    "category_id",
    "tags",
    "thumbnail_url",
    "content_type",
    "like_rate",
    "comment_rate",
    "engagement_rate",
    "collected_at",
]

COMMENT_CSV_COLUMNS = [
    "brand",
    "channel_name",
    "video_id",
    "video_title",
    "comment_id",
    "author_name",
    "comment_text",
    "like_count",
    "published_at",
    "updated_at",
    "reply_count",
    "comment_url",
    "language",
    "sentiment",
    "attachment",
    "loyalty",
    "advocacy",
    "purchase_intention",
    "competitor_mention",
    "fandom_category",
    "collected_at",
]

VIDEO_UNIQUE_KEY = "video_id"
COMMENT_UNIQUE_KEY = "comment_id"


@dataclass
class CollectorConfig:
    """Runtime configuration. CLI arguments override these defaults."""

    start_date: str = "2025-01-01"
    end_date: str = "2025-12-31"

    max_videos_per_brand: int = 30
    max_comments_per_video: int = 100

    anonymize_authors: bool = True
    include_shorts: bool = False

    keyword_filters: list[str] = field(default_factory=list)

    def ensure_directories(self) -> None:
        for directory in (
            CONFIG_DIR,
            RAW_VIDEOS_DIR,
            RAW_COMMENTS_DIR,
            PROCESSED_DIR,
            LOGS_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)
