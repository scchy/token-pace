from __future__ import annotations

from datetime import date, timedelta
from statistics import median

from tokenpace.i18n import text
from tokenpace.models import PlanMetrics, PlanStatus, ProfileMode, QuotaSnapshot


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


def split_remaining_days(today: date, reset_date: date) -> tuple[int, int]:
    total = max(1, (reset_date - today).days)
    workdays = sum(
        1
        for offset in range(total)
        if (today + timedelta(days=offset)).weekday() < 5
    )
    return workdays, total - workdays


def estimate_profile(
    dated_deltas: list[tuple[date, float]],
    pacing_mode: str = "auto",
    weekend_weight: float | None = None,
) -> tuple[float, float, ProfileMode]:
    if not dated_deltas:
        return 0.0, 0.0, "calibrating"

    recent_7 = [value for _, value in dated_deltas[-7:]]
    average_7 = sum(recent_7) / len(recent_7)
    if pacing_mode == "uniform":
        return average_7, average_7, "uniform"
    if pacing_mode == "custom" and weekend_weight is not None:
        denominator = 5.0 + 2.0 * weekend_weight
        workday_rate = 7.0 * average_7 / denominator if denominator > 0 else average_7
        return workday_rate, workday_rate * weekend_weight, "fixed_weight"

    window = dated_deltas[-28:]
    workday_values = [value for day, value in window if day.weekday() < 5]
    weekend_values = [value for day, value in window if day.weekday() >= 5]
    if len(workday_values) >= 3 and len(weekend_values) >= 2:
        return (
            sum(workday_values) / len(workday_values),
            sum(weekend_values) / len(weekend_values),
            "adaptive",
        )
    return average_7, average_7, "uniform"


def simulate_exhaust_date(
    today: date,
    remaining: float,
    workday_rate: float,
    weekend_rate: float,
    max_days: int = 365,
) -> tuple[float | None, date | None]:
    if remaining <= 0 or (workday_rate <= 0 and weekend_rate <= 0):
        return None, None
    current = remaining
    for offset in range(max_days):
        day = today + timedelta(days=offset)
        rate = workday_rate if day.weekday() < 5 else weekend_rate
        if rate <= 0:
            continue
        if current <= rate:
            return offset + current / rate, day
        current -= rate
    return None, None


def detect_spike(
    recent_values: list[float], baseline_daily: float, pacing_ratio: float
) -> bool:
    if pacing_ratio <= 1.2 or len(recent_values) < 3:
        return False
    median_7d = median(recent_values)
    peak = max(recent_values)
    return median_7d <= baseline_daily * 1.1 and (
        median_7d == 0 or peak >= median_7d * 2.0
    )


def _with_dates(
    deltas: list[tuple[date, float]] | list[float], today: date
) -> list[tuple[date, float]]:
    if not deltas:
        return []
    if isinstance(deltas[0], tuple):
        return deltas  # type: ignore[return-value]
    values = deltas  # type: ignore[assignment]
    start = today - timedelta(days=len(values))
    return [(start + timedelta(days=index), value) for index, value in enumerate(values)]


def compute_metrics(
    snap: QuotaSnapshot,
    daily_deltas: list[tuple[date, float]] | list[float],
    today: date,
    workdays_only: bool = False,
    locale: str = "zh",
    pacing_mode: str = "auto",
    weekend_weight: float | None = None,
) -> PlanMetrics:
    remaining = max(0.0, snap.total - snap.used)
    remaining_pct = remaining / snap.total * 100.0 if snap.total > 0 else 0.0
    workdays_left, weekend_days_left = split_remaining_days(today, snap.reset_date)
    days_left = workdays_left + weekend_days_left
    dated = _with_dates(daily_deltas, today)
    if workdays_only:
        pacing_mode, weekend_weight = "custom", 0.0
    workday_rate, weekend_rate, profile = estimate_profile(
        dated, pacing_mode, weekend_weight
    )
    recent = [value for _, value in dated[-7:]]
    burn_rate_7d = sum(recent) / len(recent) if recent else 0.0
    median_7d = median(recent) if recent else 0.0
    expected_remaining = workdays_left * workday_rate + weekend_days_left * weekend_rate
    baseline_daily = remaining / max(1, days_left)
    today_rate = workday_rate if today.weekday() < 5 else weekend_rate
    recommended_daily = (
        remaining * today_rate / expected_remaining
        if expected_remaining > 0
        else baseline_daily
    )
    days_until_exhaust, exhaust_date = simulate_exhaust_date(
        today, remaining, workday_rate, weekend_rate
    )
    pacing_ratio = (
        expected_remaining / remaining
        if remaining > 0
        else float("inf")
        if expected_remaining > 0
        else 0.0
    )
    is_spike = detect_spike(recent, baseline_daily, pacing_ratio)

    status: PlanStatus
    if remaining <= 0:
        status = "exhausted"
    elif profile == "calibrating":
        status = "calibrating"
    elif expected_remaining <= 0:
        status = "idle"
    elif pacing_ratio > 1.2:
        status = "fast"
    elif pacing_ratio < 0.8:
        status = "surplus"
    else:
        status = "healthy"
    advice_key = "advice_fast_spike" if is_spike else f"advice_{status}"
    advice = text(
        locale,
        advice_key,
        recommended=recommended_daily,
        unit=snap.unit,
        over_pct=(pacing_ratio - 1.0) * 100 if pacing_ratio > 0 else 0.0,
        median=median_7d,
    )

    return PlanMetrics(
        snapshot=snap,
        remaining=remaining,
        remaining_pct=remaining_pct,
        days_left=days_left,
        workdays_left=workdays_left,
        weekend_days_left=weekend_days_left,
        burn_rate_7d=burn_rate_7d,
        burn_rate_workday=workday_rate,
        burn_rate_weekend=weekend_rate,
        median_7d=median_7d,
        profile_mode=profile,
        is_spike=is_spike,
        days_until_exhaust=days_until_exhaust,
        exhaust_date=exhaust_date,
        recommended_daily=recommended_daily,
        pacing_ratio=pacing_ratio,
        status=status,
        advice=advice,
    )
