from __future__ import annotations

from tokenpace.models import Notifier
from tokenpace.notifiers.bark import BarkNotifier
from tokenpace.notifiers.feishu import FeishuNotifier
from tokenpace.notifiers.feishu_cli import FeishuCliNotifier
from tokenpace.notifiers.telegram import TelegramNotifier

_NOTIFIERS: dict[str, Notifier] = {
    notifier.name: notifier
    for notifier in (FeishuCliNotifier(), FeishuNotifier(), TelegramNotifier(), BarkNotifier())
}


def get_notifier(name: str) -> Notifier:
    try:
        return _NOTIFIERS[name]
    except KeyError as exc:
        supported = ", ".join(sorted(_NOTIFIERS))
        raise ValueError(f"未知 notifier {name!r}，支持：{supported}") from exc


__all__ = ["get_notifier"]
