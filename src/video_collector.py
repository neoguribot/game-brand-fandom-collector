"""Collect video metadata for a brand's official channel."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from tqdm import tqdm

from src.progress import tracker
from src.utils import (
    build_video_url,
    classify_content_type,
    compute_derived_metrics,
    is_short,
    now_iso,
    parse_iso8601_duration,
    safe_int,
    strip_text,
)
from src.youtube_client import YouTubeClient, YouTubeClientError

logger = logging.getLogger("fandom_collector")


def _parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _matches_keywords(title: str, description: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = f"{title or ''} {description or ''}".lower()
    return any(keyword.lower() in text for keyword in keywords)


def collect_videos_for_brand(
    client: YouTubeClient,
    brand: dict,
    start_date: str,
    end_date: str,
    max_videos: int,
    include_shorts: bool,
    keyword_filters: list[str],
) -> list[dict]:
    brand_name = brand["brand"]
    channel_id = brand.get("channel_id")

    if not channel_id:
        logger.warning(f"Skipping {brand_name}: no channel_id configured.")
        return []

    try:
        uploads_playlist_id = client.get_uploads_playlist_id(channel_id)
    except YouTubeClientError as e:
        logger.error(f"[{brand_name}] Could not fetch uploads playlist: {e}")
        return []

    start_dt = _parse_date(start_date)
    end_dt = _parse_date(end_date)

    logger.info(f"[{brand_name}] Searching uploads between {start_date} and {end_date}")

    candidate_video_ids: list[str] = []

    # The uploads playlist is sorted newest-first. There is no way to ask the
    # API to start at a given date, so we must scan from "now" backwards and
    # skip anything newer than end_date until we reach the window, then stop
    # once we pass start_date. PLAYLIST_SCAN_SAFETY_CAP bounds how far back
    # we are willing to page (e.g. very high-frequency channels combined with
    # an end_date far in the past) so a single run can't scan forever.
    PLAYLIST_SCAN_SAFETY_CAP = 5000

    try:
        for item in client.iter_playlist_items(uploads_playlist_id, PLAYLIST_SCAN_SAFETY_CAP):
            snippet = item.get("snippet", {})
            published_at_str = snippet.get("publishedAt")
            if not published_at_str:
                continue
            published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))

            if published_at > end_dt:
                continue
            if published_at < start_dt:
                break

            video_id = item.get("contentDetails", {}).get("videoId")
            if video_id:
                candidate_video_ids.append(video_id)

            # Buffer beyond max_videos since later filtering (Shorts,
            # keywords, missing stats) may drop some candidates.
            if len(candidate_video_ids) >= max_videos * 5:
                break
    except YouTubeClientError as e:
        logger.error(f"[{brand_name}] Failed while listing playlist items: {e}")

    if not candidate_video_ids:
        logger.info(f"[{brand_name}] No videos found in the given date range.")
        return []

    try:
        video_details = client.list_videos(candidate_video_ids)
    except YouTubeClientError as e:
        logger.error(f"[{brand_name}] Failed to fetch video details: {e}")
        return []

    rows: list[dict] = []
    collected_at = now_iso()

    tracker.start_brand_videos(brand_name, max_videos)

    for video_id in tqdm(candidate_video_ids, desc=f"{brand_name} Videos"):
        if len(rows) >= max_videos:
            break

        detail = video_details.get(video_id)
        if not detail:
            logger.warning(f"[{brand_name}] Video unavailable, skipping: {video_id}")
            continue

        snippet = detail.get("snippet", {})
        statistics = detail.get("statistics", {})
        content_details = detail.get("contentDetails", {})

        title = strip_text(snippet.get("title", ""))
        description = strip_text(snippet.get("description", ""))

        if not _matches_keywords(title, description, keyword_filters):
            continue

        duration_seconds = parse_iso8601_duration(content_details.get("duration"))
        if not include_shorts and is_short(duration_seconds):
            continue

        view_count = safe_int(statistics.get("viewCount"))
        like_count = safe_int(statistics.get("likeCount"))
        comment_count = safe_int(statistics.get("commentCount"))

        derived = compute_derived_metrics(view_count, like_count, comment_count)
        content_type = classify_content_type(title, description)

        rows.append(
            {
                "brand": brand_name,
                "channel_name": brand.get("channel_name", ""),
                "channel_id": channel_id,
                "video_id": video_id,
                "video_title": title,
                "video_description": description,
                "published_at": snippet.get("publishedAt"),
                "video_url": build_video_url(video_id),
                "duration": content_details.get("duration"),
                "view_count": view_count,
                "like_count": like_count,
                "comment_count": comment_count,
                "category_id": snippet.get("categoryId"),
                "tags": "|".join(snippet.get("tags", [])) if snippet.get("tags") else "",
                "thumbnail_url": (
                    snippet.get("thumbnails", {}).get("high", {}).get("url")
                    or snippet.get("thumbnails", {}).get("default", {}).get("url")
                ),
                "content_type": content_type,
                "collected_at": collected_at,
                **derived,
            }
        )
        tracker.update_videos(brand_name, len(rows))

    tracker.finish_videos(brand_name, len(rows))
    logger.info(f"[{brand_name}] Collected {len(rows)} videos.")
    return rows
