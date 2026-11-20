import json
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from tokenpace.engine import compute_metrics
from tokenpace.models import PlanMetrics, QuotaSnapshot
from tokenpace.notifiers._common import NotifierError
from tokenpace.notifiers.bark import BarkNotifier
from tokenpace.notifiers.feishu import FeishuNotifier, build_feishu_card
from tokenpace.notifiers.feishu_app import FeishuAppNotifier
from tokenpace.notifiers.feishu_cli import FeishuCliNotifier, _run_cli, build_feishu_cli_card
from tokenpace.notifiers.telegram import TelegramNotifier, build_telegram_text


def metrics(
    name: str = "Plan [A]",
    locale: str = "zh",
    unit: str = "USD",
    reset_at: datetime | None = None,
) -> list[PlanMetrics]:
    snap = QuotaSnapshot(
        plan_id="p",
        plan_name=name,
        used=50,
        total=100,
        unit=unit,
        reset_date=date(2026, 12, 1),
        captured_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
        reset_at=reset_at,
    )
    return [compute_metrics(snap, [10] * 7, date(2026, 11, 20), locale=locale)]


def test_telegram_escapes_every_markdown_v2_special_character() -> None:
    special = r"Special _*[]()~`>#+-=|{}.! \ path"
    text = build_telegram_text(metrics(special), ["failure (API). + -"])

    name_line = next(line for line in text.splitlines() if "Special" in line)
    assert name_line.startswith(
        r"*Special \_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\! \\ path*"
    )
    assert r"failure \(API\)\. \+ \-" in text


def test_telegram_inline_code_does_not_escape_decimal_points() -> None:
    text = build_telegram_text(metrics(), [])
    code_spans = [line.split("`")[1] for line in text.splitlines() if "`" in line and "USD" in line]
    assert code_spans
    assert all("\\." not in span for span in code_spans)
    assert "`50.00 / 100.00 USD`" in text


def test_english_briefing_is_english_end_to_end() -> None:
    localized = metrics(locale="en")
    telegram = build_telegram_text(localized, ["Provider failed"], locale="en")
    card = build_feishu_card(localized, ["Provider failed"], locale="en")

    assert "TokenPace Daily Quota Brief" in telegram
    assert "7\\-day average" in telegram
    assert "Sustainable pace" in telegram
    assert "Some providers failed" in telegram
    assert "Consumption is" in telegram
    assert "TokenPace Daily Quota Brief" in card["card"]["header"]["title"]["content"]
    assert "Sustainable pace" in card["card"]["elements"][0]["content"]


def test_telegram_and_feishu_handle_empty_metrics() -> None:
    telegram = build_telegram_text([], [])
    card = build_feishu_card([], [])

    assert "TokenPace" in telegram
    assert "部分数据源拉取失败" not in telegram
    assert card["card"]["header"]["template"] == "grey"
    assert card["card"]["elements"] == []
    json.dumps(card)


def test_partial_provider_failure_is_rendered_without_trailing_divider() -> None:
    error = "OpenRouter: timeout (10s). retry + fallback"
    card = build_feishu_card(metrics(), [error])
    telegram = build_telegram_text(metrics(), [error])

    elements = card["card"]["elements"]
    assert [element["tag"] for element in elements[-3:]] == ["markdown", "hr", "markdown"]
    assert error in elements[-1]["content"]
    assert card["card"]["header"]["template"] == "orange"
    assert "部分数据源拉取失败" in telegram
    assert r"timeout \(10s\)\. retry \+ fallback" in telegram
    json.dumps(card)


def test_feishu_send_uses_card_payload_and_handles_api_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def succeed(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {"code": 0}

    monkeypatch.setattr("tokenpace.notifiers.feishu.post_json", succeed)
    FeishuNotifier().send(metrics(), [], {"webhook_url": "https://example.test/hook", "timeout": 3})
    assert calls[0][0] == "https://example.test/hook"
    assert calls[0][1]["msg_type"] == "interactive"
    assert calls[0][2] == 3

    monkeypatch.setattr(
        "tokenpace.notifiers.feishu.post_json",
        lambda *args: {"code": 19021, "msg": "invalid card"},
    )
    with pytest.raises(NotifierError, match="19021"):
        FeishuNotifier().send([], [], {"webhook_url": "https://example.test/hook"})


def test_telegram_send_uses_markdown_v2_and_handles_api_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def succeed(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {"ok": True}

    monkeypatch.setattr("tokenpace.notifiers.telegram.post_json", succeed)
    TelegramNotifier().send(metrics("A.B"), [], {"bot_token": "token", "chat_id": "42"})
    assert calls[0][0].endswith("/sendMessage")
    assert calls[0][1]["parse_mode"] == "MarkdownV2"
    assert calls[0][1]["chat_id"] == "42"
    assert "A\\.B" in calls[0][1]["text"]

    monkeypatch.setattr(
        "tokenpace.notifiers.telegram.post_json",
        lambda *args: {"ok": False, "description": "can't parse entities"},
    )
    with pytest.raises(NotifierError, match="can't parse entities"):
        TelegramNotifier().send([], [], {"bot_token": "token", "chat_id": "42"})


def test_bark_send_supports_errors_and_encodes_device_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def succeed(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {"code": 200}

    monkeypatch.setattr("tokenpace.notifiers.bark.post_json", succeed)
    BarkNotifier().send(
        [],
        ["Provider failed"],
        {"device_key": "key/a", "server": "https://bark.example.test/"},
    )
    assert calls[0][0] == "https://bark.example.test/key%2Fa"
    assert calls[0][1]["group"] == "TokenPace"
    assert "Provider failed" in calls[0][1]["body"]

    monkeypatch.setattr(
        "tokenpace.notifiers.bark.post_json",
        lambda *args: {"code": 400, "message": "bad request"},
    )
    with pytest.raises(NotifierError, match="bad request"):
        BarkNotifier().send([], [], {"device_key": "key"})


def test_feishu_app_authenticates_and_sends_card2_to_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_post(url, payload, timeout, headers=None):
        calls.append((url, payload, headers))
        if "tenant_access_token" in url:
            return {"code": 0, "tenant_access_token": "tenant-token"}
        return {"code": 0, "data": {"message_id": "om_1"}}

    monkeypatch.setattr("tokenpace.notifiers.feishu_app.post_json", fake_post)
    FeishuAppNotifier().send(
        metrics(),
        [],
        {"app_id": "app-id", "app_secret": "app-secret", "user_id": "ou_target"},
    )
    assert len(calls) == 2
    assert calls[0][1] == {"app_id": "app-id", "app_secret": "app-secret"}
    message_url, message, headers = calls[1]
    assert message_url.endswith("receive_id_type=open_id")
    assert message["receive_id"] == "ou_target"
    assert message["msg_type"] == "interactive"
    assert json.loads(message["content"])["schema"] == "2.0"
    assert headers == {"Authorization": "Bearer tenant-token"}


def test_feishu_app_rejects_authentication_and_send_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "tokenpace.notifiers.feishu_app.post_json",
        lambda *args, **kwargs: {"code": 10003, "msg": "invalid app secret"},
    )
    with pytest.raises(NotifierError, match="invalid app secret"):
        FeishuAppNotifier().send(
            [], [], {"app_id": "id", "app_secret": "secret", "user_id": "ou_target"}
        )

    responses = iter(
        [
            {"code": 0, "tenant_access_token": "tenant-token"},
            {"code": 230001, "msg": "bot is not available"},
        ]
    )
    monkeypatch.setattr(
        "tokenpace.notifiers.feishu_app.post_json",
        lambda *args, **kwargs: next(responses),
    )
    with pytest.raises(NotifierError, match="bot is not available"):
        FeishuAppNotifier().send(
            [], [], {"app_id": "id", "app_secret": "secret", "user_id": "ou_target"}
        )


def test_feishu_cli_sends_direct_message_to_current_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = []

    def fake_run(command, timeout):
        commands.append(command)
        if command[:2] == ["lark-cli", "auth"]:
            return json.dumps({"identities": {"user": {"openId": "ou_current"}}})
        return json.dumps({"ok": True, "data": {"message_id": "om_1"}})

    monkeypatch.setattr("tokenpace.notifiers.feishu_cli._run_cli", fake_run)
    FeishuCliNotifier().send(metrics(), [], {})
    assert len(commands) == 2
    send = commands[1]
    assert send[:2] == ["lark-cli", "im"]
    assert send[send.index("--user-id") + 1] == "ou_current"
    assert send[send.index("--as") + 1] == "bot"
    assert send[send.index("--msg-type") + 1] == "interactive"
    card = json.loads(send[send.index("--content") + 1])
    assert card["schema"] == "2.0"
    assert card["body"]["elements"][0]["tag"] == "column_set"
    assert "Plan [A]" in card["body"]["elements"][0]["columns"][0]["elements"][0]["content"]


def test_feishu_cli_card_groups_plans_and_errors() -> None:
    card = build_feishu_cli_card(metrics(locale="en"), ["Provider failed"], locale="en")
    elements = card["body"]["elements"]
    assert card["header"]["template"] == "orange"
    assert card["config"]["width_mode"] == "default"
    assert len(elements) == 2
    assert all(element["tag"] == "column_set" for element in elements)
    assert elements[-1]["margin"] == "0px"
    assert len(elements[0]["columns"]) == 1
    progress_content = elements[0]["columns"][0]["elements"][1]["content"]
    assert "remaining" in progress_content
    assert len(progress_content.split("`")[1]) == 9
    assert "Sustainable pace" in elements[0]["columns"][0]["elements"][2]["content"]
    assert "Some providers failed" in elements[-1]["columns"][0]["elements"][0]["content"]
    assert "hr" not in json.dumps(card)
    empty = build_feishu_cli_card([], [], locale="en")
    assert empty["header"]["template"] == "grey"
    assert empty["body"]["elements"] == []


def test_feishu_cli_hides_percentage_denominator() -> None:
    card = build_feishu_cli_card(metrics(locale="en", unit="%"), [], locale="en")
    details = card["body"]["elements"][0]["columns"][0]["elements"][2]["content"]
    assert "/ 100.00 %" not in details
    assert details.startswith("11 days to reset")
    monetary = build_feishu_cli_card(metrics(locale="en"), [], locale="en")
    monetary_details = monetary["body"]["elements"][0]["columns"][0]["elements"][2]["content"]
    assert "50.00 / 100.00 USD" in monetary_details


def test_feishu_cli_shows_reset_time_to_minute() -> None:
    reset_at = datetime(2026, 11, 25, 6, 7, 8, tzinfo=timezone.utc)
    card = build_feishu_cli_card(
        metrics(locale="en", unit="%", reset_at=reset_at), [], locale="en"
    )
    details = card["body"]["elements"][0]["columns"][0]["elements"][2]["content"]
    assert details.startswith("Resets 11-25 06:07 · 5d 6h 7m left")
    assert "days to reset" not in details
    chinese = build_feishu_cli_card(metrics(unit="%", reset_at=reset_at), [])
    chinese_details = chinese["body"]["elements"][0]["columns"][0]["elements"][2]["content"]
    assert "重置时间 11-25 06:07 · 剩余 5天6小时7分钟" in chinese_details
    past = build_feishu_cli_card(
        metrics(locale="en", unit="%", reset_at=datetime(2026, 11, 19, tzinfo=timezone.utc)),
        [],
        locale="en",
    )
    past_details = past["body"]["elements"][0]["columns"][0]["elements"][2]["content"]
    assert "0d 0h 0m left" in past_details


def test_feishu_cli_supports_explicit_recipient_and_validates_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = []
    monkeypatch.setattr(
        "tokenpace.notifiers.feishu_cli._run_cli",
        lambda command, timeout: commands.append(command) or '{"ok":true}',
    )
    FeishuCliNotifier().send([], [], {"user_id": "ou_target", "identity": "user"})
    assert len(commands) == 1
    assert commands[0][commands[0].index("--user-id") + 1] == "ou_target"
    assert commands[0][commands[0].index("--as") + 1] == "user"
    with pytest.raises(NotifierError, match="identity"):
        FeishuCliNotifier().send([], [], {"identity": "admin"})


def test_feishu_cli_wraps_cli_error(monkeypatch: pytest.MonkeyPatch) -> None:
    result = SimpleNamespace(
        returncode=1,
        stdout="",
        stderr='{"ok":false,"error":{"message":"missing scope"}}',
    )
    monkeypatch.setattr("tokenpace.notifiers.feishu_cli.subprocess.run", lambda *args, **kwargs: result)
    with pytest.raises(NotifierError, match="missing scope"):
        _run_cli(["lark-cli", "test"], 1)


@pytest.mark.parametrize(
    ("notifier", "config", "message"),
    [
        (FeishuNotifier(), {}, "webhook_url"),
        (FeishuAppNotifier(), {}, "app_id"),
        (TelegramNotifier(), {}, "bot_token"),
        (BarkNotifier(), {}, "device_key"),
    ],
)
def test_notifiers_reject_missing_required_config(notifier, config, message) -> None:
    with pytest.raises(NotifierError, match=message):
        notifier.send([], [], config)
