import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from tokenpace.cli import run


def write_config(tmp_path: Path, log: Path, locale: str = "zh") -> Path:
    config = tmp_path / "plans.toml"
    config.write_text(
        f"""
[general]
locale = "{locale}"
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
    return config


def test_cli_dry_run_then_persists_ledger(tmp_path: Path, capsys) -> None:
    log = tmp_path / "usage.jsonl"
    log.write_text(json.dumps({"total_tokens": 2_000_000}) + "\n", encoding="utf-8")
    config = write_config(tmp_path, log, locale="en")

    assert run(["--config", str(config), "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "Local Agent" in output
    assert "TokenPace Daily Quota Brief" in output
    assert not (tmp_path / "data/ledger.jsonl").exists()

    assert run(["--config", str(config)]) == 0
    ledger = tmp_path / "data/ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["used"] == 2


def test_cli_second_day_includes_current_snapshot_in_burn_rate(
    tmp_path: Path, capsys
) -> None:
    log = tmp_path / "usage.jsonl"
    log.write_text(json.dumps({"total_tokens": 4_000_000}) + "\n", encoding="utf-8")
    config = write_config(tmp_path, log, locale="en")
    ledger = tmp_path / "data/ledger.jsonl"
    ledger.parent.mkdir()
    yesterday = datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)
    ledger.write_text(
        json.dumps({"date": yesterday.isoformat(), "plan_id": "local", "used": 1}) + "\n",
        encoding="utf-8",
    )

    assert run(["--config", str(config), "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "7-day average: 3.00 M tokens/day" in output
    assert "IDLE" not in output
