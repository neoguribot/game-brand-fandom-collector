"""CLI entry point for the Game Brand Fandom Collector.

Usage:
    python -m src.main
    python -m src.main --brand PlayStation
    python -m src.main --brand all
    python -m src.main --videos 30 --comments 100
    python -m src.main --start-date 2025-01-01 --end-date 2025-12-31
"""

from __future__ import annotations

import argparse
import sys

from src import channel_service, csv_manager
from src.comment_collector import collect_comments_for_videos
from src.config import (
    COMMENT_CSV_COLUMNS,
    COMMENT_UNIQUE_KEY,
    CollectorConfig,
    RAW_COMMENTS_DIR,
    RAW_VIDEOS_DIR,
    VIDEO_CSV_COLUMNS,
    VIDEO_UNIQUE_KEY,
    YOUTUBE_API_KEY,
)
from src.progress import tracker
from src.utils import setup_logging
from src.video_collector import collect_videos_for_brand
from src.youtube_client import YouTubeClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect YouTube video and comment data for game brand fandom research."
    )
    parser.add_argument("--brand", default="all", help="Brand name (e.g. PlayStation) or 'all'.")
    parser.add_argument("--videos", type=int, default=None, help="Max videos per brand.")
    parser.add_argument("--comments", type=int, default=None, help="Max comments per video.")
    parser.add_argument("--start-date", dest="start_date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--end-date", dest="end_date", default=None, help="YYYY-MM-DD")
    parser.add_argument(
        "--include-shorts", action="store_true", default=None, help="Include YouTube Shorts."
    )
    parser.add_argument(
        "--no-anonymize",
        dest="anonymize",
        action="store_false",
        default=None,
        help="Keep public author display names in the comment CSV.",
    )
    parser.add_argument(
        "--keywords", default=None, help="Comma-separated keyword filters for video titles/descriptions."
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> CollectorConfig:
    config = CollectorConfig()
    if args.videos is not None:
        config.max_videos_per_brand = args.videos
    if args.comments is not None:
        config.max_comments_per_video = args.comments
    if args.start_date is not None:
        config.start_date = args.start_date
    if args.end_date is not None:
        config.end_date = args.end_date
    if args.include_shorts is not None:
        config.include_shorts = args.include_shorts
    if args.anonymize is not None:
        config.anonymize_authors = args.anonymize
    if args.keywords:
        config.keyword_filters = [k.strip() for k in args.keywords.split(",") if k.strip()]
    return config


def slugify(brand_name: str) -> str:
    return brand_name.strip().lower().replace(" ", "_")


def main() -> int:
    args = parse_args()
    config = build_config(args)
    config.ensure_directories()

    logger = setup_logging()

    if not YOUTUBE_API_KEY:
        logger.error(
            "YOUTUBE_API_KEY is missing. Copy .env.example to .env and set your API key."
        )
        return 1

    try:
        client = YouTubeClient(YOUTUBE_API_KEY)
    except ValueError as e:
        logger.error(str(e))
        return 1

    brands = channel_service.load_brands()

    if args.brand.lower() != "all":
        brands = [b for b in brands if b["brand"].lower() == args.brand.lower()]
        if not brands:
            logger.error(f"Unknown brand: {args.brand}")
            return 1

    brands = channel_service.resolve_all_channels(client, brands)

    tracker.start_run([b["brand"] for b in brands])

    video_output_paths = []
    comment_output_paths = []

    for brand in brands:
        brand_name = brand["brand"]
        slug = slugify(brand_name)

        logger.info(f"Starting {brand_name} collection")

        video_rows = collect_videos_for_brand(
            client=client,
            brand=brand,
            start_date=config.start_date,
            end_date=config.end_date,
            max_videos=config.max_videos_per_brand,
            include_shorts=config.include_shorts,
            keyword_filters=config.keyword_filters,
        )

        video_path = RAW_VIDEOS_DIR / f"{slug}_videos.csv"
        csv_manager.upsert_rows(video_rows, video_path, VIDEO_CSV_COLUMNS, VIDEO_UNIQUE_KEY)
        video_output_paths.append(video_path)

        comment_rows = collect_comments_for_videos(
            client=client,
            brand_name=brand_name,
            video_rows=video_rows,
            max_comments_per_video=config.max_comments_per_video,
            anonymize_authors=config.anonymize_authors,
        )

        comment_path = RAW_COMMENTS_DIR / f"{slug}_comments.csv"
        csv_manager.upsert_rows(comment_rows, comment_path, COMMENT_CSV_COLUMNS, COMMENT_UNIQUE_KEY)
        comment_output_paths.append(comment_path)

        logger.info(f"{brand_name} collection complete")

    csv_manager.build_combined_csv(
        video_output_paths,
        RAW_VIDEOS_DIR / "all_brand_videos.csv",
        VIDEO_CSV_COLUMNS,
        VIDEO_UNIQUE_KEY,
    )
    csv_manager.build_combined_csv(
        comment_output_paths,
        RAW_COMMENTS_DIR / "all_brand_comments.csv",
        COMMENT_CSV_COLUMNS,
        COMMENT_UNIQUE_KEY,
    )

    tracker.finish_run()
    logger.info("All brand collections complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
