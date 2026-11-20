import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tokenpace.providers.deepseek import DeepSeekProvider
from tokenpace.providers.http_json import HttpJsonProvider
from tokenpace.providers.local_jsonl import LocalJsonlProvider
from tokenpace.providers.openrouter import OpenRouterProvider

NOW = datetime(2026, 11, 20, 8, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
RESET = date(2026, 12, 1)


def plan(provider: str, **options) -> dict:
    return {
        "id": "p",
        "name": "Plan",
        "provider": provider,
        "unit": "M tokens",
        "total_quota": 50.0,
        "reset_cycle": "monthly:1",
        "auth": {"api_key": "secret"},
        "options": options,
    }


def test_local_jsonl_sums_only_current_cycle(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    rows = [
        {"timestamp": "2026-10-31T23:00:00+08:00", "usage": {"total_tokens": 100}},
        {"timestamp": "2026-11-02T10:00:00+08:00", "usage": {"total_tokens": 2_000_000}},
        {"timestamp": "2026-11-03T10:00:00+08:00", "usage": {"total_tokens": 3_000_000}},
    ]
    log.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    cfg = plan(
        "local_jsonl",
        log_glob=str(tmp_path / "*.jsonl"),
        value_path="usage.total_tokens",
        timestamp_path="timestamp",
        scale=1e-6,
    )
    snap = LocalJsonlProvider().fetch(cfg, RESET, NOW)
    assert snap.used == 5
    assert snap.captured_at == NOW


def test_http_json_supports_remaining_and_array_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tokenpace.providers.http_json.get_json",
        lambda *args: {"data": [{"remaining": 40_000_000}]},
    )
    cfg = plan(
        "http_json",
        url="https://example.test/usage",
        value_path="data.0.remaining",
        mode="remaining",
        scale=1e-6,
    )
    assert HttpJsonProvider().fetch(cfg, RESET, NOW).used == 10


def test_openrouter_and_deepseek_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tokenpace.providers.openrouter.get_json", lambda *args: {"data": {"usage": 12.5}}
    )
    openrouter = plan("openrouter")
    openrouter["unit"] = "USD"
    assert OpenRouterProvider().fetch(openrouter, RESET, NOW).used == 12.5

    monkeypatch.setattr(
        "tokenpace.providers.deepseek.get_json",
        lambda *args: {"balance_infos": [{"currency": "CNY", "total_balance": "150"}]},
    )
    deepseek = plan("deepseek")
    deepseek["unit"] = "CNY"
    deepseek["total_quota"] = 200
    assert DeepSeekProvider().fetch(deepseek, RESET, NOW).used == 50
