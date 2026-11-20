from __future__ import annotations

import calendar
import os
import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tokenpace.i18n import SUPPORTED_LOCALES

_ENV_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    timezone: str
    ledger_path: Path
    workdays_only: bool
    locale: str
    timeout: float
    plans: list[dict[str, Any]]
    notifiers: list[dict[str, Any]]


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if not os.environ.get(name):
                raise ConfigError(f"缺少环境变量 {name}（配置中的 ${{{name}}}）")
            return os.environ[name]

        return _ENV_VAR.sub(replace, value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    try:
        with config_path.open("rb") as file:
            raw = tomllib.load(file)
    except FileNotFoundError as exc:
        raise ConfigError(f"配置文件不存在：{config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"TOML 配置格式错误：{exc}") from exc

    raw = _expand_env(raw)
    general = raw.get("general", {})
    if not isinstance(general, dict):
        raise ConfigError("[general] 必须是配置表")

    timezone = str(general.get("timezone", "Asia/Shanghai"))
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"未知时区：{timezone}") from exc

    ledger_path = Path(str(general.get("ledger_path", "data/ledger.jsonl"))).expanduser()
    if not ledger_path.is_absolute():
        ledger_path = config_path.parent / ledger_path

    workdays_only = general.get("workdays_only", False)
    if not isinstance(workdays_only, bool):
        raise ConfigError("general.workdays_only 必须是布尔值")
    locale = str(general.get("locale", "zh")).lower()
    if locale not in SUPPORTED_LOCALES:
        raise ConfigError("general.locale 仅支持 en 或 zh")
    try:
        timeout = float(general.get("timeout", 10))
    except (TypeError, ValueError) as exc:
        raise ConfigError("general.timeout 必须是正数") from exc
    if timeout <= 0:
        raise ConfigError("general.timeout 必须是正数")

    plans = raw.get("plans", [])
    notifiers = raw.get("notifiers", [])
    if not isinstance(plans, list) or not plans:
        raise ConfigError("至少配置一个 [[plans]]")
    if not isinstance(notifiers, list) or any(not isinstance(n, dict) for n in notifiers):
        raise ConfigError("[[notifiers]] 必须是配置表数组")

    plan_ids: set[str] = set()
    for plan in plans:
        if not isinstance(plan, dict):
            raise ConfigError("[[plans]] 必须是配置表数组")
        plan_id = str(plan.get("id", "")).strip()
        if not plan_id:
            raise ConfigError("每个套餐都需要非空 id")
        if plan_id in plan_ids:
            raise ConfigError(f"套餐 id 重复：{plan_id}")
        plan_ids.add(plan_id)
        if not str(plan.get("name", "")).strip():
            raise ConfigError(f"套餐 {plan_id} 缺少 name")
        if not str(plan.get("provider", "")).strip():
            raise ConfigError(f"套餐 {plan_id} 缺少 provider")
        try:
            total = float(plan.get("total_quota", 0))
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"套餐 {plan_id} 的 total_quota 必须是正数") from exc
        if total <= 0:
            raise ConfigError(f"套餐 {plan_id} 的 total_quota 必须是正数")
        next_reset_date(str(plan.get("reset_cycle", "")), date.today())
        plan["unit"] = str(plan.get("unit", "tokens"))

    for notifier in notifiers:
        if not str(notifier.get("type", "")).strip():
            raise ConfigError("每个通知渠道都需要 type")

    return AppConfig(
        timezone=timezone,
        ledger_path=ledger_path,
        workdays_only=workdays_only,
        locale=locale,
        timeout=timeout,
        plans=plans,
        notifiers=notifiers,
    )


def next_reset_date(reset_cycle: str, today: date) -> date:
    if reset_cycle.startswith("monthly:"):
        try:
            reset_day = int(reset_cycle.split(":", 1)[1])
        except ValueError as exc:
            raise ConfigError(f"无效重置周期：{reset_cycle}") from exc
        if not 1 <= reset_day <= 31:
            raise ConfigError("monthly 重置日必须在 1 到 31 之间")

        year, month = today.year, today.month
        candidate = date(year, month, min(reset_day, calendar.monthrange(year, month)[1]))
        if candidate <= today:
            month += 1
            if month == 13:
                year, month = year + 1, 1
            candidate = date(year, month, min(reset_day, calendar.monthrange(year, month)[1]))
        return candidate

    try:
        return date.fromisoformat(reset_cycle)
    except ValueError as exc:
        raise ConfigError(
            f"无效重置周期 {reset_cycle!r}，应为 monthly:1 或 YYYY-MM-DD"
        ) from exc
