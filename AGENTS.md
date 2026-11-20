# AGENTS.md

## Project overview

TokenPace is a Python 3.11+ CLI that fetches AI plan quotas, maintains a plain JSONL ledger, computes seven-day pacing metrics, and sends daily briefings to Feishu, Telegram, or Bark.

The core data flow is:

```text
Providers → Ledger → Engine → Notifiers
```

The runtime must remain standard-library-only. Do not add a database, web framework, daemon, or runtime package without an explicit user request.

## Configure TokenPace for users

When the user asks to install, configure, connect a provider or notifier, enable scheduled briefings, or get started with TokenPace, read and follow `.agents/skills/tokenpace-setup/SKILL.md`.

Treat configuration as an implementation task, not just an explanation:

1. Inspect the repository and any existing `plans.toml`.
2. Determine the user's plans, quotas, reset cycles, notifiers, and deployment mode.
3. Create or incrementally update `plans.toml` using only the selected integrations.
4. Help validate it with `--dry-run` when credentials are available.
5. Explain any remaining credential or scheduling steps.

Never ask the user to paste API keys, bot tokens, webhook secrets, or other credentials into chat. Never write literal credentials into repository files. Use `${ENV_VAR}` placeholders and direct the user to their environment or GitHub Actions Secrets. Do not read `.env` files or print credential values.

Running without `--dry-run` writes the ledger and sends external notifications. Obtain the user's confirmation first. Do not push commits, change GitHub secrets, or modify crontab unless the user asks.

## Development commands

```bash
uv run pytest
uv run tokenpace --help
uv run tokenpace --config plans.toml --dry-run
uv build
```

Use Python 3.11 or newer. Keep `pyproject.toml` runtime `dependencies` empty. Pytest is a development-only dependency.

## Code map

- `src/tokenpace/models.py`: snapshots, metrics, and extension protocols
- `src/tokenpace/config.py`: TOML parsing, environment expansion, and reset dates
- `src/tokenpace/ledger.py`: append-only snapshots and daily usage reconstruction
- `src/tokenpace/engine.py`: pure pacing calculations and recommendations
- `src/tokenpace/i18n.py`: English and Chinese briefing text
- `src/tokenpace/providers/`: remote and local usage adapters
- `src/tokenpace/notifiers/`: briefing formatting and delivery
- `src/tokenpace/cli.py`: orchestration, failure isolation, and dry-run behavior
- `tests/`: unit and CLI integration tests

Preserve provider failure isolation and the guarantee that `--dry-run` neither writes the ledger nor sends notifications. Add or update tests for behavior changes. Keep the English `README.md` and Chinese `README.zh-CN.md` documentation in sync when user-facing behavior changes.
