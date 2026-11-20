from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from typing import Any

from tokenpace.i18n import status_badge, text
from tokenpace.models import PlanMetrics


class NotifierError(RuntimeError):
    pass


def progress_bar(pct: float, width: int = 12) -> str:
    filled = round(max(0.0, min(100.0, pct)) / 100.0 * width)
    return "█" * filled + "░" * (width - filled)


def brief_date(metrics: list[PlanMetrics]) -> date:
    return metrics[0].snapshot.captured_at.date() if metrics else date.today()


def exhaustion_text(metric: PlanMetrics, locale: str) -> str:
    if metric.days_until_exhaust is not None and metric.exhaust_date is not None:
        return text(
            locale,
            "exhaust_in",
            days=metric.days_until_exhaust,
            date=f"{metric.exhaust_date:%m-%d}",
        )
    if metric.status == "exhausted":
        return text(locale, "already_exhausted")
    return text(locale, "no_forecast")


def reset_text(metric: PlanMetrics, locale: str) -> str:
    reset_at = metric.snapshot.reset_at
    if reset_at is not None:
        local_reset = reset_at.astimezone(metric.snapshot.captured_at.tzinfo)
        return text(locale, "reset_at", time=f"{local_reset:%m-%d %H:%M}")
    return text(locale, "reset", days=metric.days_left)


def render_text(
    metrics: list[PlanMetrics], errors: list[str], locale: str = "zh"
) -> str:
    title = f"📊 {text(locale, 'title')} ({brief_date(metrics):%m-%d})"
    sections = [title, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for metric in metrics:
        snap = metric.snapshot
        per_day = text(locale, "per_day")
        reset = reset_text(metric, locale)
        sections.extend(
            (
                f"{snap.plan_name}   {status_badge(locale, metric.status)}",
                f"{progress_bar(metric.remaining_pct)} {metric.remaining_pct:.1f}% "
                f"{text(locale, 'remaining')} "
                f"({metric.remaining:.2f} / {snap.total:.2f} {snap.unit} · {reset})",
                f"• {text(locale, 'burn')}: {metric.burn_rate_7d:.2f} {snap.unit}{per_day} "
                f"→ {exhaustion_text(metric, locale)}",
                f"• {text(locale, 'safe')}: {metric.recommended_daily:.2f} {snap.unit}{per_day}",
                f"• {text(locale, 'advice')}: {metric.advice}",
                "──────────────────────────────────",
            )
        )
    if errors:
        sections.append(f"⚠️ {text(locale, 'errors')}")
        sections.extend(f"• {error}" for error in errors)
    while sections and sections[-1] == "──────────────────────────────────":
        sections.pop()
    return "\n".join(sections)


def post_json(
    url: str,
    payload: dict[str, Any],
    timeout: float = 10,
    headers: dict[str, str] | None = None,
) -> Any:
    request_headers = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise NotifierError(f"HTTP {exc.code} {exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise NotifierError(f"网络请求失败：{reason}") from exc
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body
