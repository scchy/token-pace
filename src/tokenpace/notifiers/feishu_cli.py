from __future__ import annotations

import hashlib
import json
import os
import subprocess
from typing import Any

from tokenpace.i18n import text
from tokenpace.models import PlanMetrics
from tokenpace.notifiers._common import (
    NotifierError,
    brief_date,
    exhaustion_text,
    metric_status_badge,
    profile_text,
    progress_bar,
    reset_text,
)


def _run_cli(command: list[str], timeout: float) -> str:
    env = os.environ.copy()
    env["LARKSUITE_CLI_NO_UPDATE_NOTIFIER"] = "1"
    env["LARKSUITE_CLI_NO_SKILLS_NOTIFIER"] = "1"
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise NotifierError("未找到 lark-cli，请先安装并登录") from exc
    except subprocess.TimeoutExpired as exc:
        raise NotifierError("lark-cli 执行超时") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        try:
            payload = json.loads(detail)
            detail = payload.get("error", {}).get("message", detail)
        except (json.JSONDecodeError, AttributeError):
            pass
        raise NotifierError(f"lark-cli 执行失败：{detail or '未知错误'}")
    return result.stdout


def _current_user_id(cli_path: str, timeout: float) -> str:
    output = _run_cli([cli_path, "auth", "status", "--json"], timeout)
    try:
        payload = json.loads(output)
        user_id = payload["identities"]["user"]["openId"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise NotifierError("无法从 lark-cli 获取当前用户 open_id") from exc
    if not user_id:
        raise NotifierError("lark-cli 当前没有可用的用户登录态")
    return str(user_id)


def _header_color(metrics: list[PlanMetrics]) -> str:
    statuses = {metric.status for metric in metrics}
    if "exhausted" in statuses:
        return "red"
    if "fast" in statuses:
        return "orange"
    if "surplus" in statuses:
        return "blue"
    if not metrics or statuses <= {"idle", "calibrating"}:
        return "grey"
    return "green"


def build_feishu_cli_card(
    metrics: list[PlanMetrics], errors: list[str], locale: str = "zh"
) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []
    for metric in metrics:
        snap = metric.snapshot
        per_day = text(locale, "per_day")
        reset = reset_text(metric, locale)
        title = f"**{snap.plan_name}**　{metric_status_badge(metric, locale)}"
        progress = (
            f"`{progress_bar(metric.remaining_pct, width=9)}` **{metric.remaining_pct:.1f}%** "
            f"{text(locale, 'remaining')}"
        )
        quota = (
            ""
            if snap.unit == "%"
            else f"`{metric.remaining:.2f} / {snap.total:.2f} {snap.unit}` · "
        )
        detail_lines = [
            f"{quota}{reset}",
            f"**{text(locale, 'burn')}** `{metric.burn_rate_7d:.2f} {snap.unit}{per_day}`",
            exhaustion_text(metric, locale),
        ]
        profile = profile_text(metric, locale)
        if profile:
            detail_lines.append(profile)
        detail_lines.extend(
            (
                f"**{text(locale, 'safe')}** `{metric.recommended_daily:.2f} {snap.unit}{per_day}`",
                f"**{text(locale, 'advice')}**：{metric.advice}",
            )
        )
        details = "\n".join(detail_lines)
        elements.append(
            {
                "tag": "column_set",
                "flex_mode": "none",
                "horizontal_spacing": "12px",
                "margin": "0px 0px 12px 0px",
                "columns": [
                    {
                        "tag": "column",
                        "width": "weighted",
                        "weight": 1,
                        "background_style": "grey-50",
                        "padding": "12px",
                        "vertical_spacing": "4px",
                        "elements": [
                            {"tag": "markdown", "content": title},
                            {"tag": "markdown", "content": progress},
                            {"tag": "markdown", "content": details},
                        ],
                    }
                ],
            }
        )
    if errors:
        elements.append(
            {
                "tag": "column_set",
                "flex_mode": "none",
                "columns": [
                    {
                        "tag": "column",
                        "width": "weighted",
                        "weight": 1,
                        "background_style": "grey-50",
                        "padding": "12px",
                        "elements": [
                            {
                                "tag": "markdown",
                                "content": f"**⚠️ {text(locale, 'errors')}**\n"
                                + "\n".join(f"- {error}" for error in errors),
                            }
                        ],
                    }
                ],
            }
        )
    if elements:
        elements[-1]["margin"] = "0px"
    return {
        "schema": "2.0",
        "config": {
            "update_multi": True,
            "width_mode": "default",
            "summary": {"content": text(locale, "title")},
        },
        "header": {
            "title": {"tag": "plain_text", "content": text(locale, "title")},
            "subtitle": {
                "tag": "plain_text",
                "content": f"{brief_date(metrics):%Y-%m-%d}",
            },
            "template": _header_color(metrics),
            "icon": {"tag": "standard_icon", "token": "myai_colorful"},
        },
        "body": {
            "direction": "vertical",
            "padding": "12px 12px 20px 12px",
            "elements": elements,
        },
    }


class FeishuCliNotifier:
    name = "feishu_cli"

    def send(
        self,
        metrics: list[PlanMetrics],
        errors: list[str],
        cfg: dict[str, Any],
        locale: str = "zh",
    ) -> None:
        cli_path = str(cfg.get("cli_path", "lark-cli"))
        identity = str(cfg.get("identity", "bot"))
        if identity not in {"bot", "user"}:
            raise NotifierError("feishu_cli 的 identity 仅支持 bot 或 user")
        timeout = float(cfg.get("timeout", 10))
        user_id = str(cfg.get("user_id", "")).strip() or _current_user_id(cli_path, timeout)
        card = build_feishu_cli_card(metrics, errors, locale)
        card_json = json.dumps(card, ensure_ascii=False, sort_keys=True)
        card_digest = hashlib.sha256(card_json.encode("utf-8")).hexdigest()[:12]
        command = [
            cli_path,
            "im",
            "+messages-send",
            "--user-id",
            user_id,
            "--msg-type",
            "interactive",
            "--content",
            card_json,
            "--as",
            identity,
            "--idempotency-key",
            f"tokenpace-{brief_date(metrics):%Y%m%d}-{card_digest}",
        ]
        _run_cli(command, timeout)
