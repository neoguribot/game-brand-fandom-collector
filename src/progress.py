"""Live progress tracking for the collector, consumed by the web dashboard.

Writes a small JSON snapshot to web/progress.json as collection proceeds so
a static HTML page (web/index.html) can poll it and show real-time progress
without adding a web framework dependency.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
PROGRESS_FILE = WEB_DIR / "progress.json"

_MIN_WRITE_INTERVAL_SECONDS = 0.2


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ProgressTracker:
    def __init__(self) -> None:
        self.state = {
            "overall_status": "idle",
            "started_at": None,
            "updated_at": None,
            "current_brand": None,
            "brands": {},
            "recent_logs": [],
        }
        self._last_write = 0.0

    def _brand(self, brand: str) -> dict:
        return self.state["brands"].setdefault(
            brand,
            {
                "status": "pending",
                "videos": {"current": 0, "total": 0},
                "comments": {"current": 0, "total": 0},
            },
        )

    def start_run(self, brand_names: list[str]) -> None:
        self.state["overall_status"] = "running"
        self.state["started_at"] = _now_iso()
        for name in brand_names:
            self._brand(name)
        self._write(force=True)

    def start_brand_videos(self, brand: str, target_count: int) -> None:
        b = self._brand(brand)
        b["status"] = "collecting_videos"
        b["videos"] = {"current": 0, "total": target_count}
        self.state["current_brand"] = brand
        self._write(force=True)

    def update_videos(self, brand: str, current: int) -> None:
        self._brand(brand)["videos"]["current"] = current
        self._write()

    def finish_videos(self, brand: str, collected: int) -> None:
        b = self._brand(brand)
        b["videos"]["current"] = collected
        b["videos"]["total"] = max(collected, b["videos"].get("total", 0))
        self._write(force=True)

    def start_brand_comments(self, brand: str, video_count: int, max_comments_per_video: int) -> None:
        b = self._brand(brand)
        b["status"] = "collecting_comments"
        b["comments"] = {"current": 0, "total": video_count * max_comments_per_video}
        self._write(force=True)

    def update_comments(self, brand: str, current: int) -> None:
        self._brand(brand)["comments"]["current"] = current
        self._write()

    def finish_brand(self, brand: str, comment_count: int) -> None:
        b = self._brand(brand)
        b["status"] = "done"
        b["comments"]["current"] = comment_count
        self._write(force=True)

    def finish_run(self) -> None:
        self.state["overall_status"] = "done"
        self.state["current_brand"] = None
        self._write(force=True)

    def fail_run(self, message: str) -> None:
        self.state["overall_status"] = "error"
        self.log("ERROR", message)
        self._write(force=True)

    def log(self, level: str, message: str) -> None:
        self.state["recent_logs"].append({"level": level, "message": message, "time": _now_iso()})
        self.state["recent_logs"] = self.state["recent_logs"][-100:]
        self._write()

    def _write(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_write) < _MIN_WRITE_INTERVAL_SECONDS:
            return
        self._last_write = now
        self.state["updated_at"] = _now_iso()

        WEB_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path = PROGRESS_FILE.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False)
        tmp_path.replace(PROGRESS_FILE)


tracker = ProgressTracker()


class DashboardLogHandler(logging.Handler):
    """Mirrors logger output into the progress tracker's recent_logs buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            tracker.log(record.levelname, record.getMessage())
        except Exception:
            self.handleError(record)
