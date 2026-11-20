from __future__ import annotations

from datetime import date, timedelta

from tokenpace.i18n import text
from tokenpace.models import PlanMetrics, PlanStatus, QuotaSnapshot


def count_remaining_days(
    today: date, reset_date: date, workdays_only: bool = False
) -> int:
    if reset_date <= today:
        return 1
    if not workdays_only:
        return (reset_date - today).days
    days = sum(
        1
        for offset in range((reset_date - today).days)
        if (today + timedelta(days=offset)).weekday() < 5
    )
    return max(1, days)


def compute_metrics(
    snap: QuotaSnapshot,
    daily_deltas: list[float],
    today: date,
    workdays_only: bool = False,
    locale: str = "zh",
) -> PlanMetrics:
    remaining = max(0.0, snap.total - snap.used)
    remaining_pct = remaining / snap.total * 100.0 if snap.total > 0 else 0.0
    days_left = count_remaining_days(today, snap.reset_date, workdays_only)
    recent = daily_deltas[-7:]
    burn_rate_7d = sum(recent) / len(recent) if recent else 0.0
    recommended_daily = remaining / days_left

    if burn_rate_7d > 0 and remaining > 0:
        days_until_exhaust = remaining / burn_rate_7d
        exhaust_date = today + timedelta(days=int(days_until_exhaust))
        pacing_ratio = (
            burn_rate_7d / recommended_daily
            if recommended_daily > 0
            else float("inf")
        )
    else:
        days_until_exhaust = None
        exhaust_date = None
        pacing_ratio = 0.0

    status: PlanStatus
    over_pct = 0.0
    if remaining <= 0:
        status = "exhausted"
    elif pacing_ratio == 0.0:
        status = "idle"
    elif pacing_ratio > 1.2:
        status = "fast"
        over_pct = (pacing_ratio - 1.0) * 100
    elif pacing_ratio < 0.8:
        status = "surplus"
    else:
        status = "healthy"
    advice = text(
        locale,
        f"advice_{status}",
        recommended=recommended_daily,
        unit=snap.unit,
        over_pct=over_pct,
    )

    return PlanMetrics(
        snapshot=snap,
        remaining=remaining,
        remaining_pct=remaining_pct,
        days_left=days_left,
        burn_rate_7d=burn_rate_7d,
        days_until_exhaust=days_until_exhaust,
        exhaust_date=exhaust_date,
        recommended_daily=recommended_daily,
        pacing_ratio=pacing_ratio,
        status=status,
        advice=advice,
    )
