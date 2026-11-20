from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from typing import Any

from tokenpace.models import PlanMetrics

STATUS_BADGE = {
    "exhausted": "🚨 耗尽",
    "fast": "⚠️ 偏快",
    "healthy": "✅ 健康",
    "surplus": "🟢 充裕",
    "idle": "💤 闲置",
}


class NotifierError(RuntimeError):
    pass


def progress_bar(pct: float, width: int = 12) -> str:
    filled = round(max(0.0, min(100.0, pct)) / 100.0 * width)
    return "█" * filled + "░" * (width - filled)


def brief_date(metrics: list[PlanMetrics]) -> date:
    return metrics[0].snapshot.captured_at.date() if metrics else date.today()


def render_text(metrics: list[PlanMetrics], errors: list[str]) -> str:
    title = f"📊 TokenPace 每日额度晨报 ({brief_date(metrics):%m-%d})"
    sections = [title, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for metric in metrics:
        snap = metric.snapshot
        exhaust = (
            f"预计 {metric.days_until_exhaust:.1f} 天后 ({metric.exhaust_date:%m-%d}) 耗尽"
            if metric.days_until_exhaust is not None and metric.exhaust_date is not None
            else "暂无耗尽预测"
        )
        sections.extend(
            (
                f"{snap.plan_name}   {STATUS_BADGE[metric.status]}",
                f"{progress_bar(metric.remaining_pct)} {metric.remaining_pct:.1f}% 剩余 "
                f"({metric.remaining:.2f} / {snap.total:.2f} {snap.unit} · 距重置 {metric.days_left} 天)",
                f"• 近 7 日均耗：{metric.burn_rate_7d:.2f} {snap.unit}/天 → {exhaust}",
                f"• 均匀消耗线：{metric.recommended_daily:.2f} {snap.unit}/天",
                f"• 今日建议：{metric.advice}",
                "──────────────────────────────────",
            )
        )
    if errors:
        sections.append("⚠️ 部分数据源拉取失败")
        sections.extend(f"• {error}" for error in errors)
    while sections and sections[-1] == "──────────────────────────────────":
        sections.pop()
    return "\n".join(sections)


def post_json(url: str, payload: dict[str, Any], timeout: float = 10) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
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
