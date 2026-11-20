from __future__ import annotations

from typing import Any

SUPPORTED_LOCALES = {"en", "zh"}

_MESSAGES: dict[str, dict[str, str]] = {
    "zh": {
        "title": "TokenPace 每日额度晨报",
        "exhausted": "🚨 耗尽",
        "fast": "⚠️ 偏快",
        "healthy": "✅ 健康",
        "surplus": "🟢 充裕",
        "idle": "💤 闲置",
        "remaining": "剩余",
        "reset": "距重置 {days} 天",
        "burn": "近 7 日均耗",
        "safe": "均匀消耗线",
        "advice": "今日建议",
        "errors": "部分数据源拉取失败",
        "per_day": "/天",
        "exhaust_in": "预计 {days:.1f} 天后 ({date}) 耗尽",
        "no_forecast": "暂无耗尽预测",
        "already_exhausted": "已耗尽",
        "advice_exhausted": "额度已耗尽，请切换备用通道或等待重置。",
        "advice_idle": "近 7 天无消耗，今日起可按 {recommended:.2f} {unit}/天 均匀使用。",
        "advice_fast": "消耗偏快 (+{over_pct:.0f}%)，将提前耗尽。建议今日控制在 {recommended:.2f} {unit} 以内，常规任务可切换轻量模型。",
        "advice_surplus": "额度充裕，周期末将有盈余。今日可放心使用至 {recommended:.2f} {unit}，重度任务可往前排。",
        "advice_healthy": "节奏健康，维持当前频率（建议上限 {recommended:.2f} {unit}/天）。",
    },
    "en": {
        "title": "TokenPace Daily Quota Brief",
        "exhausted": "🚨 EXHAUSTED",
        "fast": "⚠️ FAST",
        "healthy": "✅ HEALTHY",
        "surplus": "🟢 SURPLUS",
        "idle": "💤 IDLE",
        "remaining": "remaining",
        "reset": "{days} days to reset",
        "burn": "7-day average",
        "safe": "Sustainable pace",
        "advice": "Today",
        "errors": "Some providers failed",
        "per_day": "/day",
        "exhaust_in": "estimated exhaustion in {days:.1f} days ({date})",
        "no_forecast": "no exhaustion forecast",
        "already_exhausted": "already exhausted",
        "advice_exhausted": "Quota exhausted. Switch to a backup provider or wait for the reset.",
        "advice_idle": "No usage in the last 7 days. Start with up to {recommended:.2f} {unit}/day.",
        "advice_fast": "Consumption is {over_pct:.0f}% above pace and may run out early. Keep today within {recommended:.2f} {unit}; use lighter models for routine tasks.",
        "advice_surplus": "Quota is ahead of pace and may remain at reset. You can use up to {recommended:.2f} {unit} today and move heavier tasks forward.",
        "advice_healthy": "Healthy pace. Keep the current frequency (daily budget: {recommended:.2f} {unit}).",
    },
}


def text(locale: str, key: str, **values: Any) -> str:
    messages = _MESSAGES.get(locale, _MESSAGES["zh"])
    return messages[key].format(**values)


def status_badge(locale: str, status: str) -> str:
    return text(locale, status)
