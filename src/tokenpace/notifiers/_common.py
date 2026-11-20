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
        seconds = max(0, int((reset_at - metric.snapshot.captured_at).total_seconds()))
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60
        remaining = text(
            locale,
            "reset_remaining",
            days=days,
            hours=hours,
            minutes=minutes,
        )
        return f"{text(locale, 'reset_at', time=f'{local_reset:%m-%d %H:%M}')} · {remaining}"
    return text(locale, "reset", days=metric.days_left)


def metric_status_badge(metric: PlanMetrics, locale: str) -> str:
    badge = status_badge(locale, metric.status)
    return badge + text(locale, "spike") if metric.is_spike else badge


def profile_text(metric: PlanMetrics, locale: str) -> str | None:
    if metric.profile_mode not in {"adaptive", "fixed_weight"}:
        return None
    per_day = text(locale, "per_day")
    result = (
        f"{text(locale, 'burn_profile')}: {text(locale, 'workday')} "
        f"{metric.burn_rate_workday:.2f} / {text(locale, 'weekend')} "
        f"{metric.burn_rate_weekend:.2f} {metric.snapshot.unit}{per_day}"
    )
    if metric.is_spike:
        result += f" · {text(locale, 'median', value=metric.median_7d)}"
    return result


def render_text(
    metrics: list[PlanMetrics], errors: list[str], locale: str = "zh"
) -> str:
    title = f"📊 {text(locale, 'title')} ({brief_date(metrics):%m-%d})"
    sections = [title, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for metric in metrics:
        snap = metric.snapshot
        per_day = text(locale, "per_day")
        reset = reset_text(metric, locale)
        sections.append(f"{snap.plan_name}   {metric_status_badge(metric, locale)}")
        sections.append(
            f"{progress_bar(metric.remaining_pct)} {metric.remaining_pct:.1f}% "
            f"{text(locale, 'remaining')} "
            f"({metric.remaining:.2f} / {snap.total:.2f} {snap.unit} · {reset})"
        )
        sections.append(
            f"• {text(locale, 'burn')}: {metric.burn_rate_7d:.2f} {snap.unit}{per_day} "
            f"→ {exhaustion_text(metric, locale)}"
        )
        profile = profile_text(metric, locale)
        if profile:
            sections.append(f"• {profile}")
        sections.extend(
            (
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
