"""Detect competitor-brand mentions ("console war" talk) in collected comments.

Finds Xbox / Nintendo (incl. Switch) mentions via regex, guarding against the
common false positive where "switch" is used as a verb ("switch to PC")
rather than a reference to the Nintendo Switch.

Classifying a matched comment into 긍정/비교/비판/옹호 (positive / comparison /
criticism / advocacy) is left to a human or LLM reviewer — at current sample
sizes (a handful of matches per brand) a dedicated classifier would be
overfit to noise. See the PlayStation report's "07 — 경쟁 브랜드 언급" section
for a worked example of that manual classification.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

XBOX_PATTERN = re.compile(r"\bx\s?box\b|\bxsx\b|\bseries x\b|\bseries s\b", re.IGNORECASE)

# "switch" alone is ambiguous (verb vs. console) — only count it as a Nintendo
# Switch mention when it is NOT the "switch to <something>" verb phrase.
_SWITCH_AS_VERB = re.compile(r"\bswitch(ing)?\s+to\b", re.IGNORECASE)
_SWITCH_WORD = re.compile(r"\bswitch\s?2?\b", re.IGNORECASE)
NINTENDO_NAME_PATTERN = re.compile(r"\bnintendo\b|\bwii\s?u\b", re.IGNORECASE)


def mentions_xbox(text: str) -> bool:
    return bool(XBOX_PATTERN.search(text or ""))


def mentions_nintendo(text: str) -> bool:
    text = text or ""
    if NINTENDO_NAME_PATTERN.search(text):
        return True
    # "switch" only counts when it isn't the "switch to <other platform>" verb phrase
    for match in _SWITCH_WORD.finditer(text):
        if not _SWITCH_AS_VERB.match(text, match.start()):
            return True
    return False


@dataclass
class CompetitorMention:
    comment_id: str
    video_id: str
    comment_text: str
    like_count: int
    brand: str  # "xbox" or "nintendo"


def find_competitor_mentions(comments: list[dict]) -> list[CompetitorMention]:
    """comments: dicts with at least comment_id, video_id, comment_text, like_count."""
    found = []
    for c in comments:
        text = c.get("comment_text", "")
        if mentions_xbox(text):
            found.append(CompetitorMention(c["comment_id"], c.get("video_id", ""), text, int(c.get("like_count") or 0), "xbox"))
        if mentions_nintendo(text):
            found.append(CompetitorMention(c["comment_id"], c.get("video_id", ""), text, int(c.get("like_count") or 0), "nintendo"))
    return found


if __name__ == "__main__":
    BASE = Path(__file__).resolve().parent.parent
    comments_csv = BASE / "data" / "raw" / "comments" / "playstation_comments.csv"

    with open(comments_csv, encoding="utf-8-sig") as f:
        comments = list(csv.DictReader(f))

    mentions = find_competitor_mentions(comments)
    mentions.sort(key=lambda m: m.like_count, reverse=True)

    print(f"경쟁 브랜드 언급: {len(mentions)}건 / 전체 댓글 {len(comments)}건 ({len(mentions)/len(comments)*100:.2f}%)\n")
    for m in mentions:
        print(f"[{m.brand:8}] [♥{m.like_count:>4}] {m.comment_text[:100]}")
