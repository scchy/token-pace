from __future__ import annotations

from datetime import date, datetime
from typing import Any

from tokenpace.models import QuotaSnapshot
from tokenpace.providers._common import ProviderError, get_json, number, snapshot, timeout


class OpenRouterProvider:
    name = "openrouter"

    def fetch(
        self, plan_cfg: dict[str, Any], reset_date: date, now: datetime
    ) -> QuotaSnapshot:
        api_key = str(plan_cfg.get("auth", {}).get("api_key", "")).strip()
        if not api_key:
            raise ProviderError("请在 plans.auth.api_key 配置 OpenRouter API Key")
        options = plan_cfg.get("options", {})
        url = str(options.get("url", "https://openrouter.ai/api/v1/key"))
        payload = get_json(
            url,
            {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout(plan_cfg),
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ProviderError("OpenRouter 响应缺少 data 对象")
        if "usage" in data:
            used = number(data["usage"], "data.usage")
        elif "limit_remaining" in data:
            remaining = number(data["limit_remaining"], "data.limit_remaining")
            used = float(plan_cfg["total_quota"]) - remaining
        else:
            raise ProviderError("OpenRouter 响应缺少 data.usage")
        return snapshot(plan_cfg, max(0.0, used), reset_date, now)
