import json
from pathlib import Path

from tokenpace.cli import run
from tokenpace.engine import compute_metrics
from tokenpace.models import QuotaSnapshot
from tokenpace.notifiers.feishu import build_feishu_card
from tokenpace.notifiers.telegram import build_telegram_text
from datetime import date, datetime, timezone


def test_cli_dry_run_then_persists_ledger(tmp_path: Path, capsys) -> None:
    log = tmp_path / "usage.jsonl"
    log.write_text(json.dumps({"total_tokens": 2_000_000}) + "\n", encoding="utf-8")
    config = tmp_path / "plans.toml"
    config.write_text(
        f"""
[general]
ledger_path = "data/ledger.jsonl"
[[plans]]
id = "local"
name = "Local Agent"
provider = "local_jsonl"
unit = "M tokens"
total_quota = 50
reset_cycle = "2099-01-01"
[plans.options]
log_glob = {json.dumps(str(log))}
value_path = "total_tokens"
scale = 1e-6
""",
        encoding="utf-8",
    )
    assert run(["--config", str(config), "--dry-run"]) == 0
    assert "Local Agent" in capsys.readouterr().out
    assert not (tmp_path / "data/ledger.jsonl").exists()

    assert run(["--config", str(config)]) == 0
    ledger = tmp_path / "data/ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["used"] == 2


def test_notifier_payloads_include_metrics_and_errors() -> None:
    snap = QuotaSnapshot(
        "p",
        "Plan [A]",
        50,
        100,
        "USD",
        date(2026, 12, 1),
        datetime(2026, 11, 20, tzinfo=timezone.utc),
    )
    metrics = [compute_metrics(snap, [10] * 7, date(2026, 11, 20))]
    card = build_feishu_card(metrics, ["Broken source"])
    assert card["msg_type"] == "interactive"
    assert card["card"]["header"]["template"] == "orange"
    assert "Broken source" in str(card)
    telegram = build_telegram_text(metrics, [])
    assert "Plan \\[A\\]" in telegram
    assert "偏快" in telegram
