from __future__ import annotations

from datetime import date, datetime
from typing import Any

from tokenpace.models import QuotaSnapshot
from tokenpace.providers._common import (
    ProviderError,
    extract_path,
    get_json,
    number,
    snapshot,
    timeout,
)


class HttpJsonProvider:
    name = "http_json"

    def fetch(
        self, plan_cfg: dict[str, Any], reset_date: date, now: datetime
    ) -> QuotaSnapshot:
        options = plan_cfg.get("options", {})
        url = str(options.get("url", "")).strip()
        value_path = str(options.get("value_path", "")).strip()
        if not url or not value_path:
            raise ProviderError("http_json 需要 options.url 和 options.value_path")
        try:
            scale = float(options.get("scale", 1.0))
        except (TypeError, ValueError) as exc:
            raise ProviderError("http_json 的 scale 必须是数值") from exc
        mode = str(options.get("mode", "used"))
        if mode not in {"used", "remaining"}:
            raise ProviderError("http_json 的 mode 仅支持 used 或 remaining")

        headers = {str(key): str(value) for key, value in plan_cfg.get("headers", {}).items()}
        headers.setdefault("Accept", "application/json")
        payload = get_json(url, headers, timeout(plan_cfg))
        value = number(extract_path(payload, value_path), value_path) * scale
        used = value if mode == "used" else float(plan_cfg["total_quota"]) - value
        return snapshot(plan_cfg, max(0.0, used), reset_date, now)
