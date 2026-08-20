"""Thin wrapper around the YouTube Data API v3 client.

Centralizes API access, retry logic, and error classification so the rest
of the pipeline can deal with a small set of well-known exceptions instead
of raw googleapiclient errors.
"""

from __future__ import annotations

import logging
from typing import Iterator, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("fandom_collector")


class YouTubeClientError(Exception):
    """Base class for known, recoverable YouTube API errors."""


class QuotaExceededError(YouTubeClientError):
    pass


class CommentsDisabledError(YouTubeClientError):
    pass


class VideoUnavailableError(YouTubeClientError):
    pass


class InvalidChannelError(YouTubeClientError):
    pass


class TransientAPIError(YouTubeClientError):
    """Retryable network/server-side error."""


def _classify_http_error(error: HttpError) -> Exception:
    status = getattr(error.resp, "status", None)
    reason = ""
    try:
        reason = error.error_details[0].get("reason", "") if error.error_details else ""
    except (AttributeError, IndexError, KeyError):
        reason = ""

    message = str(error)

    if status == 403 and ("quotaExceeded" in message or "dailyLimitExceeded" in message):
        return QuotaExceededError("YouTube API daily quota exceeded.")
    if status == 403 and "commentsDisabled" in message:
        return CommentsDisabledError("Comments are disabled for this video.")
    if status == 404:
        return VideoUnavailableError("Video or channel not found (deleted or private).")
    if status in (500, 503):
        return TransientAPIError(f"YouTube API server error ({status}).")
    if status == 400:
        return InvalidChannelError(f"Invalid request: {message}")

    return YouTubeClientError(message)


class YouTubeClient:
    def __init__(self, api_key: Optional[str]):
        if not api_key:
            raise ValueError(
                "YOUTUBE_API_KEY is missing. Copy .env.example to .env and set your API key."
            )
        self.service = build("youtube", "v3", developerKey=api_key, cache_discovery=False)

    @retry(
        retry=retry_if_exception_type(TransientAPIError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _execute(self, request):
        try:
            return request.execute()
        except HttpError as error:
            classified = _classify_http_error(error)
            raise classified from error

    def search_channel_by_name(self, query: str, max_results: int = 5) -> list[dict]:
        request = self.service.search().list(
            part="snippet",
            type="channel",
            q=query,
            maxResults=max_results,
        )
        response = self._execute(request)
        return response.get("items", [])

    def get_uploads_playlist_id(self, channel_id: str) -> Optional[str]:
        request = self.service.channels().list(
            part="contentDetails",
            id=channel_id,
        )
        response = self._execute(request)
        items = response.get("items", [])
        if not items:
            raise InvalidChannelError(f"Channel not found: {channel_id}")
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def iter_playlist_items(self, playlist_id: str, max_results: int) -> Iterator[dict]:
        fetched = 0
        page_token = None
        while fetched < max_results:
            request = self.service.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=min(50, max_results - fetched),
                pageToken=page_token,
            )
            response = self._execute(request)
            items = response.get("items", [])
            for item in items:
                yield item
                fetched += 1
                if fetched >= max_results:
                    return
            page_token = response.get("nextPageToken")
            if not page_token:
                return

    def list_videos(self, video_ids: list[str]) -> dict[str, dict]:
        """Fetch statistics/contentDetails/snippet for up to 50 video IDs at a time."""
        results: dict[str, dict] = {}
        for start in range(0, len(video_ids), 50):
            batch = video_ids[start : start + 50]
            request = self.service.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch),
            )
            response = self._execute(request)
            for item in response.get("items", []):
                results[item["id"]] = item
        return results

    def iter_comment_threads(self, video_id: str, max_results: int) -> Iterator[dict]:
        fetched = 0
        page_token = None
        while fetched < max_results:
            request = self.service.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, max_results - fetched),
                pageToken=page_token,
                order="relevance",
                textFormat="plainText",
            )
            response = self._execute(request)
            items = response.get("items", [])
            for item in items:
                yield item
                fetched += 1
                if fetched >= max_results:
                    return
            page_token = response.get("nextPageToken")
            if not page_token:
                return
