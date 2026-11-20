from __future__ import annotations

import re
from typing import Any

from tokenpace.models import PlanMetrics
from tokenpace.notifiers._common import (
    NotifierError,
    STATUS_BADGE,
    brief_date,
    post_json,
    progress_bar,
)

_MARKDOWN_SPECIAL = re.compile(r"([\\_*\[\]()~`>#+\-=|{}.!])")


def _escape(value: Any) -> str:
    return _MARKDOWN_SPECIAL.sub(r"\\\1", str(value))


def build_telegram_text(metrics: list[PlanMetrics], errors: list[str]) -> str:
    lines = [f"📊 *TokenPace 每日额度晨报 \\({_escape(f'{brief_date(metrics):%m-%d}')}\\)*", ""]
    for metric in metrics:
        snap = metric.snapshot
        exhaust = (
            f"{metric.days_until_exhaust:.1f} 天后 ({metric.exhaust_date:%m-%d})"
            if metric.days_until_exhaust is not None and metric.exhaust_date is not None
            else "暂无预测"
        )
        lines.extend(
            (
                f"*{_escape(snap.plan_name)}* {_escape(STATUS_BADGE[metric.status])}",
                f"`{progress_bar(metric.remaining_pct)}` *{_escape(f'{metric.remaining_pct:.1f}')}*% 剩余",
                f"`{_escape(f'{metric.remaining:.2f} / {snap.total:.2f} {snap.unit}')}` · 距重置 *{metric.days_left}* 天",
                f"• 近 7 日均耗：`{_escape(f'{metric.burn_rate_7d:.2f} {snap.unit}/天')}` → 预计 {_escape(exhaust)} 耗尽",
                f"• 均匀消耗线：`{_escape(f'{metric.recommended_daily:.2f} {snap.unit}/天')}`",
                f"• 今日建议：{_escape(metric.advice)}",
                "",
            )
        )
    if errors:
        lines.append("⚠️ *部分数据源拉取失败*")
        lines.extend(f"• {_escape(error)}" for error in errors)
    return "\n".join(lines).strip()


class TelegramNotifier:
    name = "telegram"

    def send(
        self, metrics: list[PlanMetrics], errors: list[str], cfg: dict[str, Any]
    ) -> None:
        token = str(cfg.get("bot_token", "")).strip()
        chat_id = cfg.get("chat_id")
        if not token or chat_id is None:
            raise NotifierError("Telegram 通知需要 bot_token 和 chat_id")
        result = post_json(
            f"https://api.telegram.org/bot{token}/sendMessage",
            {
                "chat_id": chat_id,
                "text": build_telegram_text(metrics, errors),
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            },
            float(cfg.get("timeout", 10)),
        )
        if isinstance(result, dict) and result.get("ok") is False:
            raise NotifierError(f"Telegram 返回错误：{result.get('description', '未知错误')}")
