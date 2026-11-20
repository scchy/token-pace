from __future__ import annotations

import json
from datetime import date, timedelta
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


def load_dated_deltas(
    path: Path,
    plan_id: str,
    window_days: int = 28,
    before: date | None = None,
    current: QuotaSnapshot | None = None,
) -> list[tuple[date, float]]:
    """Return dated usage, de-duplicating dates and smoothing gaps or resets."""
    if window_days <= 0:
        return []

    by_date: dict[date, float] = {}
    if path.exists():
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

    if current is not None and current.plan_id == plan_id:
        by_date[current.captured_at.date()] = current.used

    sorted_days = sorted(by_date)
    dated: list[tuple[date, float]] = []
    for previous_day, current_day in zip(sorted_days, sorted_days[1:]):
        gap = (current_day - previous_day).days
        if gap <= 0:
            continue
        previous_used = by_date[previous_day]
        current_used = by_date[current_day]
        difference = current_used - previous_used
        daily = max(0.0, (current_used if difference < 0 else difference) / gap)
        for offset in range(gap):
            dated.append((previous_day + timedelta(days=offset), daily))

    return dated[-window_days:]


def load_daily_deltas(
    path: Path,
    plan_id: str,
    window_days: int = 7,
    before: date | None = None,
    current: QuotaSnapshot | None = None,
) -> list[float]:
    return [
        value
        for _, value in load_dated_deltas(
            path,
            plan_id,
            window_days=window_days,
            before=before,
            current=current,
        )
    ]
