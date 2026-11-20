from __future__ import annotations

import re
from typing import Any

from tokenpace.i18n import status_badge, text
from tokenpace.models import PlanMetrics
from tokenpace.notifiers._common import (
    NotifierError,
    brief_date,
    exhaustion_text,
    post_json,
    progress_bar,
    reset_text,
)

_MARKDOWN_SPECIAL = re.compile(r"([\\_*\[\]()~`>#+\-=|{}.!])")


def _escape(value: Any) -> str:
    return _MARKDOWN_SPECIAL.sub(r"\\\1", str(value))


def _escape_code(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("`", "\\`")


def build_telegram_text(
    metrics: list[PlanMetrics], errors: list[str], locale: str = "zh"
) -> str:
    title = _escape(text(locale, "title"))
    lines = [f"📊 *{title} \\({_escape(f'{brief_date(metrics):%m-%d}')}\\)*", ""]
    for metric in metrics:
        snap = metric.snapshot
        per_day = text(locale, "per_day")
        reset = _escape(reset_text(metric, locale))
        lines.extend(
            (
                f"*{_escape(snap.plan_name)}* {_escape(status_badge(locale, metric.status))}",
                f"`{progress_bar(metric.remaining_pct)}` "
                f"*{_escape(f'{metric.remaining_pct:.1f}')}*% {_escape(text(locale, 'remaining'))}",
                f"`{_escape_code(f'{metric.remaining:.2f} / {snap.total:.2f} {snap.unit}')}` · *{reset}*",
                f"• {_escape(text(locale, 'burn'))}: "
                f"`{_escape_code(f'{metric.burn_rate_7d:.2f} {snap.unit}{per_day}')}` "
                f"→ {_escape(exhaustion_text(metric, locale))}",
                f"• {_escape(text(locale, 'safe'))}: "
                f"`{_escape_code(f'{metric.recommended_daily:.2f} {snap.unit}{per_day}')}`",
                f"• {_escape(text(locale, 'advice'))}: {_escape(metric.advice)}",
                "",
            )
        )
    if errors:
        lines.append(f"⚠️ *{_escape(text(locale, 'errors'))}*")
        lines.extend(f"• {_escape(error)}" for error in errors)
    return "\n".join(lines).strip()


class TelegramNotifier:
    name = "telegram"

    def send(
        self,
        metrics: list[PlanMetrics],
        errors: list[str],
        cfg: dict[str, Any],
        locale: str = "zh",
    ) -> None:
        token = str(cfg.get("bot_token", "")).strip()
        chat_id = cfg.get("chat_id")
        if not token or chat_id is None:
            raise NotifierError("Telegram 通知需要 bot_token 和 chat_id")
        result = post_json(
            f"https://api.telegram.org/bot{token}/sendMessage",
            {
                "chat_id": chat_id,
                "text": build_telegram_text(metrics, errors, locale),
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            },
            float(cfg.get("timeout", 10)),
        )
        if isinstance(result, dict) and result.get("ok") is False:
            raise NotifierError(f"Telegram 返回错误：{result.get('description', '未知错误')}")
