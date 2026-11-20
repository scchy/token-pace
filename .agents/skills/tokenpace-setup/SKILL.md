---
name: tokenpace-setup
description: Configure TokenPace after a fork or clone, including plans.toml, provider credentials, Feishu/Telegram/Bark notifiers, dry-run validation, GitHub Actions, and local cron. Use when the user asks to set up TokenPace, connect a plan, change quota or reset settings, enable notifications, or troubleshoot configuration.
---

# TokenPace Setup

Configure the checked-out TokenPace repository for the user. Make the changes rather than only providing a tutorial.

## Safety rules

- Never ask for API keys, tokens, webhook URLs containing secrets, or chat credentials in chat.
- Never put literal credentials in `plans.toml`, documentation, logs, commits, or command output.
- Use `${ENV_VAR}` placeholders. For GitHub Actions, direct users to repository Actions Secrets.
- Do not read `.env` files or inspect environment-variable values. Checking whether a named variable is set is allowed, but never print its value.
- `--dry-run` contacts configured providers but does not write the ledger or send notifications.
- A normal run writes `data/ledger.jsonl` and sends notifications. Ask for confirmation before doing it.
- Do not push commits, change remote secrets, enable workflows, or modify crontab without an explicit request.
- Preserve an existing `plans.toml`; edit it incrementally instead of replacing it with the example.

## Setup workflow

### 1. Inspect the repository

Read `plans.example.toml`, `README.md`, and any existing `plans.toml`. Check whether the user already has a configuration, local logs, or a preferred deployment method.

Do not copy the entire example unchanged: unused example entries cause missing-environment-variable errors and unwanted API calls.

### 2. Determine the required configuration

Collect only details that cannot be inferred:

- Plans to monitor: OpenRouter, DeepSeek, custom HTTP JSON, or local JSONL.
- For each plan: display name, unit, total quota, and reset cycle.
- Notification channels: Feishu, Telegram, Bark, several of them, or local output only.
- Briefing language: `locale = "en"` or `"zh"`; existing configurations default to `zh`.
- Deployment: GitHub Actions or local/cron.

Use concise questions and sensible defaults from `plans.example.toml`. Do not invent endpoint paths, local log locations, quota amounts, or reset dates.

For `http_json`, obtain the non-secret endpoint, response field path, whether it represents used or remaining quota, and any scale factor. Header values must use environment placeholders.

For `local_jsonl`, verify the log glob and inspect only enough record structure to determine `value_path` and `timestamp_path`. Avoid echoing whole logs because they may contain prompts or other private data. Choose `aggregate = "sum"` for per-request increments or `"latest"` for an already-cumulative field.

### 3. Create or update plans.toml

Include only selected plans and notifiers. Every plan needs:

- A unique `id` and human-readable `name`
- `provider`, `unit`, `total_quota`, and `reset_cycle`
- Provider-specific `auth`, `options`, or `headers`

Use `monthly:N` for recurring resets or `YYYY-MM-DD` for a fixed date. Keep general defaults unless the user requests otherwise:

```toml
[general]
locale = "en"
timezone = "Asia/Shanghai"
ledger_path = "data/ledger.jsonl"
workdays_only = false
timeout = 10
```

Required notifier fields:

- Feishu: `type = "feishu"`, `webhook_url = "${FEISHU_WEBHOOK_URL}"`
- Telegram: `type = "telegram"`, `bot_token`, and `chat_id`
- Bark: `type = "bark"`, `device_key`; `server` and `group` are optional

Use distinct, descriptive environment-variable names for multiple custom providers.

### 4. Help with credentials without exposing them

List each required environment-variable name and where the user sets it. Ask the user to set secrets in their own shell or in GitHub Actions Secrets, then tell you when finished.

Do not generate persistent shell configuration or secret files unless the user explicitly asks. Do not echo secrets in verification commands.

### 5. Validate the configuration

First parse TOML without contacting external services:

```bash
uv run python -c 'import tomllib; tomllib.load(open("plans.toml", "rb")); print("TOML OK")'
```

When required credentials are available, run:

```bash
uv run tokenpace --config plans.toml --dry-run
```

Confirm that:

- Every expected plan appears in the briefing.
- Used and remaining values have the expected unit and direction.
- Reset dates and recommendations are plausible.
- No `data/ledger.jsonl` entry was created by the dry run.
- No notification was sent.

If a provider fails, fix its configuration rather than silently leaving a broken entry. Preserve unrelated valid plans. Common problems include missing environment variables, reversed `used`/`remaining` mode, an incorrect JSON path or scale, and an unsupported local timestamp field.

### 6. Enable the selected delivery mode

For GitHub Actions:

- Ensure `plans.toml` and `.github/workflows/morning-brief.yml` will be committed.
- Map every referenced secret in the workflow environment.
- Explain how to run **TokenPace Morning Brief** manually from the Actions tab.
- Note that GitHub Actions cannot read logs on the user's local machine.

For local cron:

- Give a command using the repository's absolute path.
- Modify crontab only if the user explicitly asks.
- Account for the fact that cron may not inherit interactive-shell environment variables; recommend a user-controlled, permission-restricted credential mechanism rather than embedding secrets in the cron line.

### 7. Finish with a concise handoff

Report:

- The file changed and integrations configured.
- Validation performed and its result.
- Credentials or scheduling steps still requiring user action.
- That a real run has not been performed, unless the user explicitly confirmed one.

Never include secret values in the summary.
