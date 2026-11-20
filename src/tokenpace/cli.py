from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tokenpace import __version__
from tokenpace.config import ConfigError, load_config, next_reset_date
from tokenpace.engine import compute_metrics
from tokenpace.ledger import append_snapshot, load_daily_deltas
from tokenpace.models import PlanMetrics
from tokenpace.notifiers import get_notifier
from tokenpace.notifiers._common import render_text
from tokenpace.providers import get_provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tokenpace",
        description="汇总 AI 套餐额度，计算近 7 日消耗配速并推送每日晨报。",
    )
    parser.add_argument("--config", default="plans.toml", help="TOML 配置文件路径")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印晨报，不写账本、不发送通知",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(Path(args.config))
    except ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2

    now = datetime.now(ZoneInfo(config.timezone))
    metrics: list[PlanMetrics] = []
    errors: list[str] = []
    for plan in config.plans:
        plan_name = str(plan.get("name", plan.get("id", "未命名套餐")))
        try:
            reset_date = next_reset_date(str(plan["reset_cycle"]), now.date())
            plan["_timeout"] = config.timeout
            provider = get_provider(str(plan["provider"]))
            snap = provider.fetch(plan, reset_date, now)
            deltas = load_daily_deltas(
                config.ledger_path, snap.plan_id, before=now.date()
            )
            metric = compute_metrics(
                snap, deltas, now.date(), workdays_only=config.workdays_only
            )
            if not args.dry_run:
                append_snapshot(config.ledger_path, snap)
            metrics.append(metric)
        except Exception as exc:
            errors.append(f"{plan_name}：{exc}")

    print(render_text(metrics, errors))
    if args.dry_run:
        return 1 if errors else 0

    notification_failed = False
    for notifier_cfg in config.notifiers:
        notifier_type = str(notifier_cfg["type"])
        try:
            notifier = get_notifier(notifier_type)
            notifier_cfg.setdefault("timeout", config.timeout)
            notifier.send(metrics, errors, notifier_cfg)
        except Exception as exc:
            notification_failed = True
            print(f"通知失败（{notifier_type}）：{exc}", file=sys.stderr)
    return 1 if notification_failed else 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
