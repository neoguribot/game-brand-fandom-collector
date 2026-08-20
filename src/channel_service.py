"""Resolve and cache official YouTube channel IDs for configured brands."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config import BRANDS_CONFIG_PATH
from src.youtube_client import YouTubeClient, YouTubeClientError

logger = logging.getLogger("fandom_collector")


def load_brands(path: Path = BRANDS_CONFIG_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["brands"]


def save_brands(brands: list[dict], path: Path = BRANDS_CONFIG_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"brands": brands}, f, ensure_ascii=False, indent=2)


def resolve_channel_id(client: YouTubeClient, brand: dict) -> dict:
    """Resolve brand['channel_id'] via search if it is not already set.

    Mutates and returns the brand dict. Does not raise on failure; instead
    logs a warning and leaves channel_id empty so the caller can skip it.
    """
    if brand.get("channel_id"):
        return brand

    query = brand.get("channel_name") or brand.get("brand")
    logger.info(f"Resolving channel ID for {brand['brand']} (query: {query})")

    try:
        results = client.search_channel_by_name(query, max_results=5)
    except YouTubeClientError as e:
        logger.warning(f"Failed to resolve channel for {brand['brand']}: {e}")
        return brand

    if not results:
        logger.warning(f"No channel found for {brand['brand']} (query: {query})")
        return brand

    top_match = results[0]
    channel_id = top_match["id"]["channelId"]
    resolved_title = top_match["snippet"]["title"]

    brand["channel_id"] = channel_id
    logger.info(f"Resolved {brand['brand']} -> channel_id={channel_id} ({resolved_title})")
    return brand


def resolve_all_channels(
    client: YouTubeClient,
    brands: list[dict],
    persist: bool = True,
) -> list[dict]:
    updated = [resolve_channel_id(client, brand) for brand in brands]
    if persist:
        _merge_and_save(updated)
    return updated


def _merge_and_save(updated_brands: list[dict], path: Path = BRANDS_CONFIG_PATH) -> None:
    """Merge resolved brands back into the full config instead of overwriting it.

    A user may run the collector for a single brand (--brand PlayStation);
    persisting only that subset would otherwise wipe out the other brands
    already configured in brands.json.
    """
    full_brands = load_brands(path)
    by_name = {b["brand"]: b for b in full_brands}
    for brand in updated_brands:
        by_name[brand["brand"]] = brand
    save_brands(list(by_name.values()), path)
