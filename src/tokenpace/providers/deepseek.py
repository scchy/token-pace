from __future__ import annotations

from datetime import date, datetime
from typing import Any

from tokenpace.models import QuotaSnapshot
from tokenpace.providers._common import ProviderError, get_json, number, snapshot, timeout


class DeepSeekProvider:
    name = "deepseek"

    def fetch(
        self, plan_cfg: dict[str, Any], reset_date: date, now: datetime
    ) -> QuotaSnapshot:
        api_key = str(plan_cfg.get("auth", {}).get("api_key", "")).strip()
        if not api_key:
            raise ProviderError("请在 plans.auth.api_key 配置 DeepSeek API Key")
        options = plan_cfg.get("options", {})
        url = str(options.get("url", "https://api.deepseek.com/user/balance"))
        payload = get_json(
            url,
            {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout(plan_cfg),
        )
        balances = payload.get("balance_infos") if isinstance(payload, dict) else None
        if not isinstance(balances, list) or not balances:
            raise ProviderError("DeepSeek 响应缺少 balance_infos")
        unit = str(plan_cfg.get("unit", "CNY")).upper()
        balance = next(
            (
                item
                for item in balances
                if isinstance(item, dict) and str(item.get("currency", "")).upper() == unit
            ),
            balances[0],
        )
        if not isinstance(balance, dict) or "total_balance" not in balance:
            raise ProviderError("DeepSeek 响应缺少 total_balance")
        remaining = number(balance["total_balance"], "total_balance")
        used = max(0.0, float(plan_cfg["total_quota"]) - remaining)
        return snapshot(plan_cfg, used, reset_date, now)
