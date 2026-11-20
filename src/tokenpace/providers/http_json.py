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


def _reset_from_value(value: Any, now: datetime, path: str) -> datetime:
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            parsed = datetime.fromtimestamp(timestamp, tz=now.tzinfo)
        elif isinstance(value, str):
            text = value.strip()
            if len(text) == 10:
                parsed = datetime.combine(
                    date.fromisoformat(text), datetime.min.time(), now.tzinfo
                )
            else:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=now.tzinfo)
        else:
            raise ValueError
    except (ValueError, TypeError, OSError) as exc:
        raise ProviderError(f"{path} 不是有效的 ISO 时间或 Unix 时间戳") from exc
    return parsed.astimezone(now.tzinfo)


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
        reset_at = None
        reset_path = str(options.get("reset_path", "")).strip()
        if reset_path:
            reset_at = _reset_from_value(
                extract_path(payload, reset_path), now, reset_path
            )
            reset_date = reset_at.date()
        return snapshot(plan_cfg, max(0.0, used), reset_date, now, reset_at)
