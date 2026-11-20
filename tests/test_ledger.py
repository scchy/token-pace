import json
from datetime import date, datetime, timezone
from pathlib import Path

from tokenpace.ledger import append_snapshot, load_daily_deltas
from tokenpace.models import QuotaSnapshot


def write_rows(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_deduplicates_dates_smooths_gaps_and_detects_reset(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    write_rows(
        ledger,
        [
            {"date": "2026-11-01", "plan_id": "p", "used": 10},
            {"date": "2026-11-01", "plan_id": "p", "used": 12},
            {"date": "2026-11-04", "plan_id": "p", "used": 24},
            {"date": "2026-11-05", "plan_id": "p", "used": 2},
            {"date": "2026-11-05", "plan_id": "other", "used": 999},
        ],
    )
    assert load_daily_deltas(ledger, "p") == [4, 4, 4, 2]
    assert load_daily_deltas(ledger, "p", window_days=2) == [4, 2]
    assert load_daily_deltas(ledger, "p", before=date(2026, 11, 4)) == []


def test_append_snapshot_creates_parent_and_uses_local_snapshot_date(tmp_path: Path) -> None:
    ledger = tmp_path / "nested" / "ledger.jsonl"
    snap = QuotaSnapshot(
        "p",
        "Plan",
        1.23456789,
        10,
        "USD",
        date(2026, 12, 1),
        datetime(2026, 11, 20, 8, 30, tzinfo=timezone.utc),
    )
    append_snapshot(ledger, snap)
    row = json.loads(ledger.read_text(encoding="utf-8"))
    assert row["date"] == "2026-11-20"
    assert row["used"] == 1.234568


def test_invalid_or_empty_lines_do_not_break_other_plans(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        '\nnot-json\n{"date":"2026-11-01","plan_id":"p","used":1}\n'
        '{"date":"2026-11-02","plan_id":"p","used":3}\n',
        encoding="utf-8",
    )
    assert load_daily_deltas(ledger, "p") == [2]
    assert load_daily_deltas(ledger, "missing") == []
