from __future__ import annotations

from typing import Any

from tokenpace.models import PlanMetrics
from tokenpace.notifiers._common import (
    NotifierError,
    STATUS_BADGE,
    brief_date,
    post_json,
    progress_bar,
)


def build_feishu_card(metrics: list[PlanMetrics], errors: list[str]) -> dict[str, Any]:
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
        exhaust = (
            f"**{metric.days_until_exhaust:.1f} 天后** ({metric.exhaust_date:%m-%d})"
            if metric.days_until_exhaust is not None and metric.exhaust_date is not None
            else "暂无预测"
        )
        content = (
            f"**{snap.plan_name}**　{STATUS_BADGE[metric.status]}\n"
            f"`{progress_bar(metric.remaining_pct)}` **{metric.remaining_pct:.1f}%** 剩余 "
            f"(`{metric.remaining:.2f} / {snap.total:.2f} {snap.unit}` · 距重置 **{metric.days_left}** 天)\n"
            f"• 近 7 日均耗：`{metric.burn_rate_7d:.2f} {snap.unit}/天` → 预计 {exhaust} 耗尽\n"
            f"• 均匀消耗线：`{metric.recommended_daily:.2f} {snap.unit}/天`\n"
            f"• 今日建议：{metric.advice}"
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
                "content": "**⚠️ 部分数据源拉取失败**\n" + "\n".join(f"- {e}" for e in errors),
            }
        )
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 TokenPace 每日额度晨报 ({brief_date(metrics):%m-%d})",
                },
                "template": header_color,
            },
            "elements": elements,
        },
    }


class FeishuNotifier:
    name = "feishu"

    def send(
        self, metrics: list[PlanMetrics], errors: list[str], cfg: dict[str, Any]
    ) -> None:
        url = str(cfg.get("webhook_url", "")).strip()
        if not url:
            raise NotifierError("飞书通知缺少 webhook_url")
        result = post_json(
            url,
            build_feishu_card(metrics, errors),
            float(cfg.get("timeout", 10)),
        )
        if isinstance(result, dict):
            code = result.get("code", result.get("StatusCode", 0))
            if code not in (0, None):
                message = result.get("msg", result.get("StatusMessage", "未知错误"))
                raise NotifierError(f"飞书返回错误 {code}：{message}")
