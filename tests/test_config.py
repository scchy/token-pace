from datetime import date
from pathlib import Path

import pytest

from tokenpace.config import ConfigError, load_config, next_reset_date


def test_load_config_expands_env_and_resolves_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TOKENPACE_TEST_VALUE", "7")
    config_file = tmp_path / "plans.toml"
    config_file.write_text(
        """
[general]
ledger_path = "history/ledger.jsonl"
workdays_only = true
[[plans]]
id = "local"
name = "Local"
provider = "local_jsonl"
unit = "tokens"
total_quota = "${TOKENPACE_TEST_VALUE}"
reset_cycle = "monthly:1"
[plans.options]
log_glob = "logs/*.jsonl"
""",
        encoding="utf-8",
    )
    config = load_config(config_file)
    assert config.ledger_path == tmp_path / "history/ledger.jsonl"
    assert config.workdays_only is True
    assert config.plans[0]["total_quota"] == "7"


def test_missing_environment_variable_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TOKENPACE_MISSING", raising=False)
    path = tmp_path / "plans.toml"
    path.write_text(
        """
[[plans]]
id = "p"
name = "P"
provider = "openrouter"
total_quota = 1
reset_cycle = "monthly:1"
[plans.auth]
api_key = "${TOKENPACE_MISSING}"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="TOKENPACE_MISSING"):
        load_config(path)


def test_reset_cycle_supports_month_end_and_fixed_dates() -> None:
    assert next_reset_date("monthly:1", date(2026, 11, 20)) == date(2026, 12, 1)
    assert next_reset_date("monthly:31", date(2026, 1, 31)) == date(2026, 2, 28)
    assert next_reset_date("2027-01-15", date(2026, 11, 20)) == date(2027, 1, 15)
    with pytest.raises(ConfigError):
        next_reset_date("weekly", date(2026, 11, 20))
