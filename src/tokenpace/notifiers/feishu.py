from __future__ import annotations

from typing import Any

from tokenpace.i18n import status_badge, text
from tokenpace.models import PlanMetrics
from tokenpace.notifiers._common import (
    NotifierError,
    brief_date,
    exhaustion_text,
    post_json,
    progress_bar,
)


def build_feishu_card(
    metrics: list[PlanMetrics], errors: list[str], locale: str = "zh"
) -> dict[str, Any]:
    statuses = {metric.status for metric in metrics}
    header_color = (
        "red"
        if "exhausted" in statuses
        else "orange"
        if "fast" in statuses
        else "blue"
        if "surplus" in statuses
        else "grey"
        if not metrics or statuses == {"idle"}
        else "green"
    )
    elements: list[dict[str, Any]] = []
    for metric in metrics:
        snap = metric.snapshot
        per_day = text(locale, "per_day")
        reset = text(locale, "reset", days=metric.days_left)
        content = (
            f"**{snap.plan_name}**　{status_badge(locale, metric.status)}\n"
            f"`{progress_bar(metric.remaining_pct)}` **{metric.remaining_pct:.1f}%** "
            f"{text(locale, 'remaining')} "
            f"(`{metric.remaining:.2f} / {snap.total:.2f} {snap.unit}` · **{reset}**)\n"
            f"• {text(locale, 'burn')}: `{metric.burn_rate_7d:.2f} {snap.unit}{per_day}` "
            f"→ {exhaustion_text(metric, locale)}\n"
            f"• {text(locale, 'safe')}: `{metric.recommended_daily:.2f} {snap.unit}{per_day}`\n"
            f"• {text(locale, 'advice')}: {metric.advice}"
        )
        elements.append({"tag": "markdown", "content": content})
        elements.append({"tag": "hr"})
    if elements:
        elements.pop()
    if errors:
        if elements:
            elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "markdown",
                "content": f"**⚠️ {text(locale, 'errors')}**\n"
                + "\n".join(f"- {error}" for error in errors),
            }
        )
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 {text(locale, 'title')} ({brief_date(metrics):%m-%d})",
                },
                "template": header_color,
            },
            "elements": elements,
        },
    }


class FeishuNotifier:
    name = "feishu"

    def send(
        self,
        metrics: list[PlanMetrics],
        errors: list[str],
        cfg: dict[str, Any],
        locale: str = "zh",
    ) -> None:
        url = str(cfg.get("webhook_url", "")).strip()
        if not url:
            raise NotifierError("飞书通知缺少 webhook_url")
        result = post_json(
            url,
            build_feishu_card(metrics, errors, locale),
            float(cfg.get("timeout", 10)),
        )
        if isinstance(result, dict):
            code = result.get("code", result.get("StatusCode", 0))
            if code not in (0, None):
                message = result.get("msg", result.get("StatusMessage", "未知错误"))
                raise NotifierError(f"飞书返回错误 {code}：{message}")
