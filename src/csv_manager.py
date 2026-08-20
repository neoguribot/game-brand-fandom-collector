"""CSV persistence with duplicate-safe append semantics."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger("fandom_collector")

ENCODING = "utf-8-sig"


def _load_existing(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(path, encoding=ENCODING, dtype=str)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


def upsert_rows(
    rows: list[dict],
    path: Path,
    columns: list[str],
    unique_key: str,
) -> int:
    """Append new rows to an existing CSV, skipping duplicates by unique_key.

    Returns the number of newly written rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    new_df = pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame(columns=columns)
    if not new_df.empty:
        new_df[unique_key] = new_df[unique_key].astype(str)

    existing_df = _load_existing(path, columns)

    if not existing_df.empty:
        existing_ids = set(existing_df[unique_key].astype(str))
        new_df = new_df[~new_df[unique_key].astype(str).isin(existing_ids)]

    if new_df.empty and existing_df.empty:
        pd.DataFrame(columns=columns).to_csv(path, index=False, encoding=ENCODING)
        return 0

    combined = pd.concat([existing_df, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=[unique_key], keep="first")
    combined.to_csv(path, index=False, encoding=ENCODING)

    added = len(new_df)
    logger.info(f"Wrote {path.name}: +{added} new rows ({len(combined)} total).")
    return added


def build_combined_csv(
    source_paths: list[Path],
    output_path: Path,
    columns: list[str],
    unique_key: str,
) -> None:
    frames = []
    for path in source_paths:
        if path.exists():
            frames.append(_load_existing(path, columns))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not frames:
        pd.DataFrame(columns=columns).to_csv(output_path, index=False, encoding=ENCODING)
        return

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=[unique_key], keep="first")
    combined.to_csv(output_path, index=False, encoding=ENCODING)
    logger.info(f"Wrote combined file {output_path.name}: {len(combined)} total rows.")
