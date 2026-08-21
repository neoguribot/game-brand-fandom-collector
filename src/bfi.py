"""Brand Fandom Index (BFI) — a weighted composite score from collected video
and comment data.

Six dimensions, each scored 0-100 and combined by weight:

    Attention          15%   reach proxy (currently YouTube views; Google
                              Trends search-interest data is a planned add-on)
    Engagement         20%   (likes + comments) / views, averaged per video
    Attachment         20%   share of comments classified as emotional/
                              nostalgic bond
    Loyalty            20%   share of comments classified as repeat-purchase /
                              long-term commitment signal
    Advocacy           15%   share of comments classified as recommending or
                              defending the brand
    Purchase Intention 10%   share of comments classified as purchase intent

Each dimension is normalized with a simple capped-linear transform:

    score = min(100, value / TARGET * 100)

TARGET is a provisional "what excellent looks like" benchmark, not a
statistically derived one — there is no peer-brand data yet to calibrate
against. Recalibrate TARGETS once Xbox/Nintendo data (and Google Trends for
Attention) are collected, so scores become relative to competitors instead of
an assumed anchor. Until then, read the composite score as a within-brand,
within-period indicator (useful for tracking PlayStation's own trend over
time), not as an absolute or cross-brand ranking.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

WEIGHTS = {
    "attention": 0.15,
    "engagement": 0.20,
    "attachment": 0.20,
    "loyalty": 0.20,
    "advocacy": 0.15,
    "purchase_intention": 0.10,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "BFI weights must sum to 100%"

# Provisional normalization targets — see module docstring.
TARGETS = {
    "attention": 200_000,   # avg views/video considered "excellent" reach
    "engagement": 0.05,     # 5% (likes+comments)/views — common "excellent" YouTube benchmark
    "attachment": 0.10,     # 10% of comments carrying an attachment signal
    "loyalty": 0.10,
    "advocacy": 0.10,
    "purchase_intention": 0.15,
}


@dataclass
class BFIResult:
    brand: str
    raw: dict = field(default_factory=dict)       # dimension -> raw measured value
    scores: dict = field(default_factory=dict)    # dimension -> 0-100 sub-score
    total: float = 0.0                            # weighted composite, 0-100

    def breakdown_rows(self) -> list[tuple[str, float, float, float, float]]:
        """(dimension, weight_pct, raw_value, sub_score, weighted_points)."""
        rows = []
        for dim, weight in WEIGHTS.items():
            raw = self.raw[dim]
            score = self.scores[dim]
            rows.append((dim, weight * 100, raw, score, score * weight))
        return rows


def _capped_linear(value: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return min(100.0, max(0.0, value / target * 100.0))


def compute_bfi(videos_csv: Path, comments_csv: Path, brand: str) -> BFIResult:
    with open(videos_csv, encoding="utf-8-sig") as f:
        videos = [row for row in csv.DictReader(f) if row["brand"] == brand]

    with open(comments_csv, encoding="utf-8-sig") as f:
        comments = [row for row in csv.DictReader(f) if row["brand"] == brand]

    if not videos:
        raise ValueError(f"No videos found for brand={brand!r} in {videos_csv}")
    if not comments:
        raise ValueError(f"No comments found for brand={brand!r} in {comments_csv}")

    views = [int(v["view_count"]) for v in videos if v["view_count"]]
    avg_views = sum(views) / len(views)

    per_video_engagement = [
        float(v["engagement_rate"]) for v in videos if v["engagement_rate"]
    ]
    avg_engagement = sum(per_video_engagement) / len(per_video_engagement)

    n_comments = len(comments)
    share = {
        dim: sum(1 for c in comments if c["fandom_category"] == dim) / n_comments
        for dim in ("attachment", "loyalty", "advocacy", "purchase_intention")
    }

    raw = {
        "attention": avg_views,
        "engagement": avg_engagement,
        "attachment": share["attachment"],
        "loyalty": share["loyalty"],
        "advocacy": share["advocacy"],
        "purchase_intention": share["purchase_intention"],
    }

    scores = {dim: _capped_linear(raw[dim], TARGETS[dim]) for dim in WEIGHTS}
    total = sum(scores[dim] * WEIGHTS[dim] for dim in WEIGHTS)

    return BFIResult(brand=brand, raw=raw, scores=scores, total=total)


def _format_raw(dim: str, value: float) -> str:
    if dim == "attention":
        return f"{value:,.0f} views/video"
    return f"{value * 100:.2f}%"


def print_report(result: BFIResult) -> None:
    print(f"\nBrand Fandom Index — {result.brand}")
    print("=" * 66)
    print(f"{'Dimension':<20}{'Weight':>8}{'Raw':>20}{'Score':>9}{'Pts':>9}")
    for dim, weight_pct, raw, score, points in result.breakdown_rows():
        print(f"{dim:<20}{weight_pct:>7.0f}%{_format_raw(dim, raw):>20}{score:>8.1f}{points:>9.1f}")
    print("-" * 66)
    print(f"{'TOTAL':<20}{'100%':>8}{'':>20}{'':>9}{result.total:>9.1f}")


if __name__ == "__main__":
    BASE = Path(__file__).resolve().parent.parent
    result = compute_bfi(
        videos_csv=BASE / "data" / "raw" / "videos" / "playstation_videos.csv",
        comments_csv=BASE / "data" / "raw" / "comments" / "playstation_comments.csv",
        brand="PlayStation",
    )
    print_report(result)
