from __future__ import annotations

from typing import Any
from urllib.parse import quote

from tokenpace.models import PlanMetrics
from tokenpace.notifiers._common import (
    NotifierError,
    brief_date,
    post_json,
    render_text,
)


class BarkNotifier:
    name = "bark"

    def send(
        self, metrics: list[PlanMetrics], errors: list[str], cfg: dict[str, Any]
    ) -> None:
        device_key = str(cfg.get("device_key", "")).strip()
        if not device_key:
            raise NotifierError("Bark 通知缺少 device_key")
        server = str(cfg.get("server", "https://api.day.app")).rstrip("/")
        title = f"TokenPace 每日额度晨报 ({brief_date(metrics):%m-%d})"
        body = render_text(metrics, errors).split("\n", 2)[-1]
        payload: dict[str, Any] = {
            "title": title,
            "body": body,
            "group": str(cfg.get("group", "TokenPace")),
        }
        if "icon" in cfg:
            payload["icon"] = str(cfg["icon"])
        result = post_json(
            f"{server}/{quote(device_key, safe='')}",
            payload,
            float(cfg.get("timeout", 10)),
        )
        if isinstance(result, dict) and result.get("code") not in (None, 200):
            raise NotifierError(f"Bark 返回错误：{result.get('message', result)}")
