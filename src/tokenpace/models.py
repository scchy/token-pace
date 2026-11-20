from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal, Protocol

PlanStatus = Literal["healthy", "fast", "surplus", "exhausted", "idle"]


@dataclass(frozen=True)
class QuotaSnapshot:
    plan_id: str
    plan_name: str
    used: float
    total: float
    unit: str
    reset_date: date
    captured_at: datetime


@dataclass(frozen=True)
class PlanMetrics:
    snapshot: QuotaSnapshot
    remaining: float
    remaining_pct: float
    days_left: int
    burn_rate_7d: float
    days_until_exhaust: float | None
    exhaust_date: date | None
    recommended_daily: float
    pacing_ratio: float | None
    status: PlanStatus
    advice: str


class Provider(Protocol):
    name: str

    def fetch(
        self, plan_cfg: dict[str, Any], reset_date: date, now: datetime
    ) -> QuotaSnapshot: ...


class Notifier(Protocol):
    name: str

    def send(
        self,
        metrics: list[PlanMetrics],
        errors: list[str],
        cfg: dict[str, Any],
        locale: str = "zh",
    ) -> None: ...
