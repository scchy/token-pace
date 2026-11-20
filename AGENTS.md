# AGENTS.md

## Project overview

TokenPace is a Python 3.11+ CLI that fetches AI plan quotas, maintains a plain JSONL ledger, computes seven-day pacing metrics, and delivers daily briefings to Feishu, Telegram, or Bark.

The core data flow is:

```text
Providers → Ledger → Engine → Notifiers
```

The runtime must remain standard-library-only. Do not add a database, web framework, daemon, MCP server, or Python runtime package without an explicit user request. Optional external tools such as `lark-cli` are local integrations, not core runtime dependencies. Agents can already call `tokenpace --dry-run`; MCP is not required for setup or scheduled push delivery.

## Deployment priorities

Present **GitHub Actions as the recommended reference deployment**: zero server maintenance, scheduled execution, and automatic ledger persistence. Direct users to **Use this template → Private**, not Fork, because public forks cannot be made private. For a minimal self-updating personal deployment, also offer the config-only private repository in `examples/config-only-repo`, which runs upstream code through `uvx`. Local cron and `feishu_cli` direct messages are enhancements for users who need local logs, existing CLI authentication, or private Feishu cards.

For GitHub Actions:

- Keep `plans.toml` free of literal secrets and commit it only when the user asks.
- Map every referenced secret in `.github/workflows/morning-brief.yml`; existing mappings include OpenRouter, DeepSeek, Kimi, GLM, Feishu, Telegram, and Bark.
- Preserve the missing-`plans.toml` skip so the upstream repository badge does not fail.
- Preserve automatic `data/ledger.jsonl` commits with `git add -f`, `[skip ci]`, and `git pull --rebase` before pushing.
- Keep the upstream `/generate` flow and the config-only workflow secret mappings synchronized when adding providers.

## Configure TokenPace for users

When the user asks to install, configure, connect a provider or notifier, enable scheduled briefings, or get started, read and follow `.agents/skills/tokenpace-setup/SKILL.md`.

Treat configuration as an implementation task, not just an explanation:

1. Inspect the repository and any existing `plans.toml`; preserve valid entries incrementally.
2. Determine plans, quotas, reset behavior, recipient, and deployment mode. Default to GitHub Actions unless local requirements say otherwise.
3. Inspect actual provider responses before selecting JSON fields; do not guess endpoints, array positions, caps, or reset dates.
4. Validate TOML and provider dry runs, then explain remaining secrets or scheduling steps.

Never ask users to paste API keys, bot tokens, webhook secrets, or other credentials into chat. Never write literal credentials into repository files. Do not read `.env` files or print credential values. Checking whether a named variable is set is allowed. If the user says credentials live in `.bashrc`, an interactive `bash -ic` check may be necessary in a non-interactive agent shell.

Running without `--dry-run` writes the ledger and sends external notifications. Before a real send, confirm the recipient, message content, and sending identity. Do not push commits, change GitHub secrets, enable workflows, or modify crontab unless the user asks.

## Provider and pacing rules

- For rolling quotas such as Kimi and GLM, use `http_json.options.reset_path`; never infer a fixed weekday. Preserve `reset_at` and display timestamps to the minute in the configured timezone.
- Prefer percentage pacing for ratio-based plans. For count-based plans such as GLM credits, derive `scale = 100 / total_cap` and set `total_quota = 100` and `unit = "%"`.
- Verify GLM's weekly entry (`unit = 6`) and its cap instead of assuming an array index for every account.
- When changing a plan's unit, migrate its historical ledger values to the same unit to avoid false cycle resets.
- Keep `load_daily_deltas(current=snap)` so the latest interval is included without writing during dry runs.

## Notification UX

- For local personal Feishu delivery, prefer `feishu_cli`: current-user direct message, Card 2.0, and no webhook or stored App Secret.
- For groups or GitHub Actions, use `feishu` with a webhook, Telegram, or Bark. Do not require a group for a personal local setup.
- Feishu CLI cards use a full-width single-column plan group and a nine-cell dedicated progress row. Do not split the progress bar across columns.
- Percentage plans omit redundant `85 / 100 %` denominators. Monetary and token plans retain absolute remaining/total values.
- Feishu CLI idempotency keys include a content digest so changed layouts and updated quotas can be resent.
- TokenPace `--dry-run` never invokes a notifier. Use `lark-cli ... --dry-run` separately to inspect a Feishu request without sending.

## Development commands

```bash
uv run pytest
uv run tokenpace --help
uv run tokenpace --config plans.toml --dry-run
uv build
```

Use Python 3.11 or newer. Keep `pyproject.toml` runtime `dependencies` empty. Pytest is a development-only dependency.

## Code map

- `src/tokenpace/models.py`: snapshots, metrics, optional minute-level `reset_at`, and extension protocols
- `src/tokenpace/config.py`: TOML parsing, environment expansion, locale, and static reset dates
- `src/tokenpace/ledger.py`: append-only snapshots and daily usage reconstruction
- `src/tokenpace/engine.py`: pure pacing calculations and recommendations
- `src/tokenpace/i18n.py`: English and Chinese briefing text
- `src/tokenpace/providers/http_json.py`: generic JSON mapping, scaling, and response-driven reset timestamps
- `src/tokenpace/notifiers/feishu_cli.py`: local private Card 2.0 delivery through `lark-cli`
- `src/tokenpace/notifiers/`: webhook, Telegram, Bark, formatting, and delivery
- `src/tokenpace/cli.py`: orchestration, failure isolation, and dry-run behavior
- `tests/`: unit and CLI integration tests with local notifier mocks

Preserve provider failure isolation and the guarantee that `--dry-run` neither writes the ledger nor sends notifications. Add or update tests for behavior changes. Keep `README.md` and `README.zh-CN.md` synchronized when user-facing behavior changes.
