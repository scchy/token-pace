from datetime import date, datetime, timezone

import pytest

from tokenpace.engine import compute_metrics, count_remaining_days
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
    assert idle.status == "idle"
    assert idle.pacing_ratio == 0
    assert idle.exhaust_date is None
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
