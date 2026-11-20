from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime
from typing import Any

from tokenpace.models import QuotaSnapshot


class ProviderError(RuntimeError):
    pass


def get_json(url: str, headers: dict[str, str], timeout: float) -> Any:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"HTTP {exc.code} {exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise ProviderError(f"网络请求失败：{reason}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("接口未返回有效 JSON") from exc


def extract_path(payload: Any, path: str) -> Any:
    value = payload
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise ProviderError(f"JSON 中找不到字段：{path}")
    return value


def number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ProviderError(f"{field} 不是数值")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ProviderError(f"{field} 不是数值") from exc


def snapshot(
    plan: dict[str, Any], used: float, reset_date: date, now: datetime
) -> QuotaSnapshot:
    return QuotaSnapshot(
        plan_id=str(plan["id"]),
        plan_name=str(plan["name"]),
        used=used,
        total=float(plan["total_quota"]),
        unit=str(plan.get("unit", "tokens")),
        reset_date=reset_date,
        captured_at=now,
    )


def timeout(plan: dict[str, Any]) -> float:
    return float(plan.get("options", {}).get("timeout", plan.get("_timeout", 10)))
