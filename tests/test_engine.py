from datetime import date, datetime, timedelta, timezone

import pytest

from tokenpace.engine import compute_metrics, count_remaining_days, simulate_exhaust_date
from tokenpace.models import QuotaSnapshot


def snapshot(used: float = 0, total: float = 200) -> QuotaSnapshot:
    return QuotaSnapshot(
        plan_id="demo",
        plan_name="Demo",
        used=used,
        total=total,
        unit="CNY",
        reset_date=date(2026, 12, 1),
        captured_at=datetime(2026, 11, 20, 8, 30, tzinfo=timezone.utc),
    )


def test_fast_status_and_exhaust_date() -> None:
    metrics = compute_metrics(snapshot(used=51.5, total=100), [5.6] * 7, date(2026, 11, 20))
    assert metrics.status == "fast"
    assert metrics.remaining == 48.5
    assert metrics.recommended_daily == pytest.approx(48.5 / 11)
    assert metrics.days_until_exhaust == pytest.approx(48.5 / 5.6)
    assert metrics.exhaust_date == date(2026, 11, 28)


def test_healthy_surplus_idle_and_exhausted() -> None:
    today = date(2026, 11, 20)
    assert compute_metrics(snapshot(100), [100 / 11], today).status == "healthy"
    assert compute_metrics(snapshot(100), [1], today).status == "surplus"
    idle = compute_metrics(snapshot(100), [], today)
    assert idle.status == "calibrating"
    assert idle.pacing_ratio == 0
    assert idle.exhaust_date is None
    assert compute_metrics(snapshot(100), [0, 0], today).status == "idle"
    exhausted = compute_metrics(snapshot(200), [10], today)
    assert exhausted.status == "exhausted"
    assert exhausted.remaining_pct == 0
    assert exhausted.recommended_daily == 0
    assert exhausted.days_until_exhaust is None
    assert exhausted.exhaust_date is None


def test_english_advice_and_exhausted_forecast() -> None:
    today = date(2026, 11, 20)
    healthy = compute_metrics(snapshot(100), [100 / 11], today, locale="en")
    assert "Healthy pace" in healthy.advice
    exhausted = compute_metrics(snapshot(200), [10], today, locale="en")
    assert exhausted.days_until_exhaust is None
    assert exhausted.advice == "Quota exhausted. Switch to a backup provider or wait for the reset."


def test_burn_rate_uses_available_days_only() -> None:
    metrics = compute_metrics(snapshot(), [2, 4], date(2026, 11, 20))
    assert metrics.burn_rate_7d == 3


def test_workdays_only_has_a_minimum_of_one() -> None:
    friday = date(2026, 11, 20)
    assert count_remaining_days(friday, date(2026, 11, 24), True) == 2
    saturday = date(2026, 11, 21)
    assert count_remaining_days(saturday, date(2026, 11, 23), True) == 1
    assert count_remaining_days(friday, friday, False) == 1


def dated_values(today: date, values: list[float]) -> list[tuple[date, float]]:
    start = today - timedelta(days=len(values))
    return [(start + timedelta(days=index), value) for index, value in enumerate(values)]


def test_workday_only_profile_keeps_ratio_consistent() -> None:
    today = date(2026, 11, 23)
    history = dated_values(today, [10, 10, 10, 10, 10, 0, 0])
    metrics = compute_metrics(snapshot(used=40, total=100), history, today)
    assert metrics.profile_mode == "adaptive"
    assert metrics.burn_rate_workday == 10
    assert metrics.burn_rate_weekend == 0
    assert metrics.pacing_ratio == pytest.approx(1.0)
    assert metrics.status == "healthy"


def test_weekend_peak_profile_changes_daily_budget() -> None:
    saturday = date(2026, 11, 21)
    history = dated_values(saturday, [15, 1, 1, 1, 1, 1, 15])
    weekend = compute_metrics(snapshot(used=50, total=100), history, saturday)
    monday = compute_metrics(snapshot(used=50, total=100), history, date(2026, 11, 23))
    assert weekend.profile_mode == "adaptive"
    assert weekend.burn_rate_weekend > weekend.burn_rate_workday
    assert weekend.recommended_daily > monday.recommended_daily


def test_exhaust_simulation_skips_zero_usage_weekend() -> None:
    days, exhaust_date = simulate_exhaust_date(date(2026, 11, 20), 15, 10, 0)
    assert days == 3.5
    assert exhaust_date == date(2026, 11, 23)


def test_spike_and_sustained_overuse_have_different_advice() -> None:
    today = date(2026, 11, 20)
    spike = compute_metrics(
        snapshot(used=80, total=100),
        dated_values(today, [2, 2, 2, 2, 2, 2, 25]),
        today,
        pacing_mode="uniform",
    )
    sustained = compute_metrics(
        snapshot(used=80, total=100),
        dated_values(today, [6, 6, 6, 6, 6, 6, 6]),
        today,
        pacing_mode="uniform",
    )
    assert spike.is_spike is True
    assert "基线仍健康" in spike.advice
    assert sustained.is_spike is False
    assert "持续偏快" in sustained.advice


def test_first_day_is_calibrating_but_zero_history_is_idle() -> None:
    today = date(2026, 11, 20)
    calibrating = compute_metrics(snapshot(), [], today)
    idle = compute_metrics(snapshot(), dated_values(today, [0, 0, 0]), today)
    assert calibrating.status == "calibrating"
    assert calibrating.profile_mode == "calibrating"
    assert "首日建档" in calibrating.advice
    assert idle.status == "idle"
