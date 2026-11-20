import json
from pathlib import Path

from tokenpace.cli import run


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
