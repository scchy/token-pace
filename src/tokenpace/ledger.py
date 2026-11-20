from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from tokenpace.models import QuotaSnapshot


def append_snapshot(path: Path, snap: QuotaSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "date": snap.captured_at.date().isoformat(),
        "ts": snap.captured_at.isoformat(),
        "plan_id": snap.plan_id,
        "used": round(snap.used, 6),
        "total": round(snap.total, 6),
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_daily_deltas(
    path: Path,
    plan_id: str,
    window_days: int = 7,
    before: date | None = None,
) -> list[float]:
    """Load per-day usage, de-duplicating dates and smoothing gaps or resets."""
    if not path.exists() or window_days <= 0:
        return []

    by_date: dict[date, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            day = date.fromisoformat(row["date"])
            used = float(row["used"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        if row.get("plan_id") == plan_id and (before is None or day < before):
            by_date[day] = used

    sorted_days = sorted(by_date)
    deltas: list[float] = []
    for previous_day, current_day in zip(sorted_days, sorted_days[1:]):
        gap = (current_day - previous_day).days
        if gap <= 0:
            continue
        previous_used = by_date[previous_day]
        current_used = by_date[current_day]
        difference = current_used - previous_used
        daily = (current_used if difference < 0 else difference) / gap
        deltas.extend([max(0.0, daily)] * gap)

    return deltas[-window_days:]
