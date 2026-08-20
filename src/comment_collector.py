"""Collect public top-level comments for previously collected videos."""

from __future__ import annotations

import logging

from tqdm import tqdm

from src.progress import tracker
from src.utils import anonymize_author, build_comment_url, now_iso, safe_int, strip_text
from src.youtube_client import CommentsDisabledError, VideoUnavailableError, YouTubeClient, YouTubeClientError

logger = logging.getLogger("fandom_collector")


def collect_comments_for_videos(
    client: YouTubeClient,
    brand_name: str,
    video_rows: list[dict],
    max_comments_per_video: int,
    anonymize_authors: bool,
) -> list[dict]:
    all_comments: list[dict] = []
    collected_at = now_iso()

    tracker.start_brand_comments(brand_name, len(video_rows), max_comments_per_video)

    progress = tqdm(video_rows, desc=f"{brand_name} Comments")
    for video in progress:
        video_id = video["video_id"]
        video_title = video["video_title"]
        channel_name = video.get("channel_name", "")

        try:
            for item in client.iter_comment_threads(video_id, max_comments_per_video):
                top_comment = item["snippet"]["topLevelComment"]["snippet"]
                comment_id = item["snippet"]["topLevelComment"]["id"]

                all_comments.append(
                    {
                        "brand": brand_name,
                        "channel_name": channel_name,
                        "video_id": video_id,
                        "video_title": video_title,
                        "comment_id": comment_id,
                        "author_name": anonymize_author(
                            top_comment.get("authorDisplayName"), anonymize_authors
                        ),
                        "comment_text": strip_text(top_comment.get("textDisplay", "")),
                        "like_count": safe_int(top_comment.get("likeCount")),
                        "published_at": top_comment.get("publishedAt"),
                        "updated_at": top_comment.get("updatedAt"),
                        "reply_count": safe_int(item["snippet"].get("totalReplyCount")),
                        "comment_url": build_comment_url(video_id, comment_id),
                        "language": "",
                        "sentiment": "",
                        "attachment": "",
                        "loyalty": "",
                        "advocacy": "",
                        "purchase_intention": "",
                        "competitor_mention": "",
                        "fandom_category": "",
                        "collected_at": collected_at,
                    }
                )
        except CommentsDisabledError:
            logger.warning(f"Comments disabled for video {video_id} ({video_title})")
            continue
        except VideoUnavailableError:
            logger.warning(f"Video unavailable while fetching comments: {video_id}")
            continue
        except YouTubeClientError as e:
            logger.error(f"Failed to fetch comments for {video_id}: {e}")
            continue

        progress.set_postfix(comments=len(all_comments))
        tracker.update_comments(brand_name, len(all_comments))

    tracker.finish_brand(brand_name, len(all_comments))
    logger.info(f"[{brand_name}] Collected {len(all_comments)} comments.")
    return all_comments
