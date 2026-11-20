from __future__ import annotations

import calendar
import glob
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from tokenpace.models import QuotaSnapshot
from tokenpace.providers._common import ProviderError, extract_path, number, snapshot

_DEFAULT_VALUE_PATHS = (
    "usage.total_tokens",
    "total_tokens",
    "tokens",
    "used",
    "cost",
)
_TIMESTAMP_PATHS = ("timestamp", "time", "created_at", "date")


def _cycle_start(reset_cycle: str, reset_date: date) -> date | None:
    if not reset_cycle.startswith("monthly:"):
        return None
    year, month = reset_date.year, reset_date.month - 1
    if month == 0:
        year, month = year - 1, 12
    day = int(reset_cycle.split(":", 1)[1])
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _parse_time(value: Any, default_tz: Any) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=default_tz)
    if isinstance(value, str):
        text = value.strip()
        try:
            if len(text) == 10:
                return datetime.combine(date.fromisoformat(text), datetime.min.time(), default_tz)
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=default_tz)
            return parsed.astimezone(default_tz)
        except ValueError:
            return None
    return None


class LocalJsonlProvider:
    name = "local_jsonl"

    def fetch(
        self, plan_cfg: dict[str, Any], reset_date: date, now: datetime
    ) -> QuotaSnapshot:
        options = plan_cfg.get("options", {})
        pattern = str(options.get("log_glob", "")).strip()
        if not pattern:
            raise ProviderError("local_jsonl 需要 options.log_glob")
        filenames = sorted(glob.glob(str(Path(pattern).expanduser()), recursive=True))
        files = [Path(name) for name in filenames if Path(name).is_file()]
        if not files:
            raise ProviderError(f"没有找到日志文件：{pattern}")

        value_path = str(options.get("value_path", "")).strip()
        timestamp_path = str(options.get("timestamp_path", "")).strip()
        aggregate = str(options.get("aggregate", "sum"))
        if aggregate not in {"sum", "latest"}:
            raise ProviderError("local_jsonl 的 aggregate 仅支持 sum 或 latest")
        try:
            scale = float(options.get("scale", 1.0))
        except (TypeError, ValueError) as exc:
            raise ProviderError("local_jsonl 的 scale 必须是数值") from exc
        start = _cycle_start(str(plan_cfg.get("reset_cycle", "")), reset_date)

        values: list[tuple[datetime | None, float]] = []
        for file in files:
            try:
                lines = file.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError) as exc:
                raise ProviderError(f"无法读取日志 {file}：{exc}") from exc
            for line_number, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ProviderError(f"{file}:{line_number} 不是有效 JSON") from exc
                if not isinstance(row, dict):
                    continue

                selected_path = value_path
                if not selected_path:
                    selected_path = next(
                        (path for path in _DEFAULT_VALUE_PATHS if _has_path(row, path)), ""
                    )
                if not selected_path:
                    continue
                try:
                    value = number(extract_path(row, selected_path), selected_path)
                except ProviderError as exc:
                    raise ProviderError(f"{file}:{line_number}：{exc}") from exc

                time_value = None
                if timestamp_path:
                    if not _has_path(row, timestamp_path):
                        raise ProviderError(f"{file}:{line_number} 缺少 {timestamp_path}")
                    time_value = extract_path(row, timestamp_path)
                else:
                    time_value = next(
                        (row[path] for path in _TIMESTAMP_PATHS if path in row), None
                    )
                captured = _parse_time(time_value, now.tzinfo) if time_value is not None else None
                if start and captured and captured.date() < start:
                    continue
                if captured and captured.date() > now.date():
                    continue
                values.append((captured, value))

        if aggregate == "latest" and values:
            values.sort(key=lambda item: item[0] or datetime.min.replace(tzinfo=now.tzinfo))
            total = values[-1][1]
        else:
            total = sum(value for _, value in values)
        return snapshot(plan_cfg, max(0.0, total * scale), reset_date, now)


def _has_path(payload: Any, path: str) -> bool:
    try:
        extract_path(payload, path)
        return True
    except ProviderError:
        return False
