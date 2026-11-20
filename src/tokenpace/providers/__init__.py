from __future__ import annotations

from tokenpace.models import Provider
from tokenpace.providers.deepseek import DeepSeekProvider
from tokenpace.providers.http_json import HttpJsonProvider
from tokenpace.providers.local_jsonl import LocalJsonlProvider
from tokenpace.providers.openrouter import OpenRouterProvider

_PROVIDERS: dict[str, Provider] = {
    provider.name: provider
    for provider in (
        OpenRouterProvider(),
        DeepSeekProvider(),
        HttpJsonProvider(),
        LocalJsonlProvider(),
    )
}


def get_provider(name: str) -> Provider:
    try:
        return _PROVIDERS[name]
    except KeyError as exc:
        supported = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"未知 provider {name!r}，支持：{supported}") from exc


__all__ = ["get_provider"]
