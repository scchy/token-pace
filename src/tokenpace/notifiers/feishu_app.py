from __future__ import annotations

import hashlib
import json
from typing import Any

from tokenpace.models import PlanMetrics
from tokenpace.notifiers._common import NotifierError, brief_date, post_json
from tokenpace.notifiers.feishu_cli import build_feishu_cli_card


class FeishuAppNotifier:
    name = "feishu_app"

    def send(
        self,
        metrics: list[PlanMetrics],
        errors: list[str],
        cfg: dict[str, Any],
        locale: str = "zh",
    ) -> None:
        app_id = str(cfg.get("app_id", "")).strip()
        app_secret = str(cfg.get("app_secret", "")).strip()
        user_id = str(cfg.get("user_id", "")).strip()
        if not app_id or not app_secret or not user_id:
            raise NotifierError("feishu_app 需要 app_id、app_secret 和 user_id")
        base_url = str(cfg.get("base_url", "https://open.feishu.cn")).rstrip("/")
        timeout = float(cfg.get("timeout", 10))

        token_result = post_json(
            f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
            {"app_id": app_id, "app_secret": app_secret},
            timeout,
        )
        if not isinstance(token_result, dict) or token_result.get("code") != 0:
            message = token_result.get("msg", "未知错误") if isinstance(token_result, dict) else token_result
            raise NotifierError(f"飞书应用认证失败：{message}")
        access_token = token_result.get("tenant_access_token")
        if not access_token:
            raise NotifierError("飞书应用认证响应缺少 tenant_access_token")

        card = build_feishu_cli_card(metrics, errors, locale)
        card_json = json.dumps(card, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(card_json.encode("utf-8")).hexdigest()[:12]
        result = post_json(
            f"{base_url}/open-apis/im/v1/messages?receive_id_type=open_id",
            {
                "receive_id": user_id,
                "msg_type": "interactive",
                "content": card_json,
                "uuid": f"tokenpace-{brief_date(metrics):%Y%m%d}-{digest}",
            },
            timeout,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if not isinstance(result, dict) or result.get("code") != 0:
            message = result.get("msg", "未知错误") if isinstance(result, dict) else result
            raise NotifierError(f"飞书应用发送失败：{message}")
