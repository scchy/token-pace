---
name: tokenpace-setup
description: Configure and deploy TokenPace after a fork or clone, with GitHub Actions as the reference deployment, optional local Feishu CLI private cards, provider credentials, rolling quota resets, dry-run validation, and cron. Use for setup, provider or notifier changes, deployment, and troubleshooting.
---

# TokenPace Setup

Configure the checked-out TokenPace repository for the user. Make the changes rather than only providing a tutorial. Recommend **GitHub Actions first** for zero-maintenance deployment; use local cron and `feishu_cli` when the user needs local logs, existing CLI authentication, or private Feishu cards.

For open-source users, recommend **Use this template → Private**, not Fork: public forks cannot be made private and the ledger reveals usage patterns. For a minimal personal deployment that follows upstream fixes without source merges, offer `examples/config-only-repo` with its `uvx` workflow. Suggest pinning `git+https://github.com/scchy/token-pace.git` to a release tag when reproducibility matters.

## Safety rules

- Never ask for API keys, tokens, webhook URLs containing secrets, or chat credentials in chat.
- Never put literal credentials in `plans.toml`, documentation, logs, commits, or command output.
- Use `${ENV_VAR}` placeholders. For GitHub Actions, direct users to repository Actions Secrets.
- Do not read `.env` files or inspect environment-variable values. Checking whether a named variable is set is allowed, but never print its value.
- If the user says credentials are in `.bashrc`, non-interactive `source ~/.bashrc` may return early; use `bash -ic` for checks and execution when appropriate.
- `--dry-run` contacts configured providers but does not write the ledger or send notifications.
- A normal run writes `data/ledger.jsonl` and sends notifications. Confirm recipient, content, and sending identity before doing it.
- Do not push commits, change remote secrets, enable workflows, or modify crontab without an explicit request.
- Preserve an existing `plans.toml`; edit it incrementally instead of replacing it with the example.

## 1. Inspect and choose a deployment

Read `plans.example.toml`, `README.md`, `.github/workflows/morning-brief.yml`, and any existing `plans.toml`. Check local logs, provider credentials, notification preferences, and existing CLI authentication without exposing secrets.

Do not copy the entire example unchanged: unused entries cause missing-variable errors and unwanted API calls.

Default to **GitHub Actions** when the providers work over HTTP and the recipient can use a group webhook, Telegram, or Bark. Choose local mode when the user needs `local_jsonl`, local `lark-cli` authentication, or direct Feishu messages without a group.

Ask only for details that cannot be inferred:

- Plans, display names, units, total caps, and reset behavior
- Recipient: current user, another user, a group, or local output only
- Briefing language: `locale = "en"` or `"zh"`; existing configurations default to `zh`
- Deployment: GitHub Actions or local/cron

No MCP server is needed for setup, Agent access, or scheduled delivery; the CLI already supports Agent-driven dry runs.

## 2. Configure plans accurately

Include only selected plans. Every plan needs a unique `id`, `name`, `provider`, `unit`, `total_quota`, `reset_cycle`, and provider-specific `auth`, `options`, or `headers`.

Use `monthly:N` for recurring monthly resets or `YYYY-MM-DD` for a fixed fallback date. For rolling quotas, configure `options.reset_path`; it overrides the static reset date on every successful fetch and preserves the timestamp to the minute. Never infer a fixed weekday from the current response.

Inspect the actual provider response before choosing fields. Do not invent endpoints, array positions, caps, or reset dates.

### Verified Kimi recipe

- Endpoint: `https://api.kimi.com/coding/v1/usages`
- Weekly ratio: `usages.limit_7d.used_ratio`
- Rolling reset: `usages.limit_7d.reset_time`
- Header: `Authorization: Bearer ${KIM_CODE_API_KEY}` unless the user already uses another variable name
- Percentage pacing: `total_quota = 100`, `unit = "%"`, `scale = 100`, `mode = "used"`

Some Kimi accounts return only newer `usages` ratio pools, while others also include legacy `usage`. Prefer the ratio pool when present.

### Verified GLM recipe

- Endpoint: `https://open.bigmodel.cn/api/monitor/usage/quota/limit`
- Header: raw `Authorization: ${GLM_TOKEN_PLAN_API_KEY}`, with no `Bearer` prefix unless the user uses another variable name
- Select the weekly entry by `unit = 6`; do not blindly use `data.limits.1` for an unverified response
- Use its `currentValue` for consumption and `nextResetTime` for rolling reset
- For percentage pacing, set `total_quota = 100`, `unit = "%"`, and `scale = 100 / usage_cap`
- New plans may return `CREDIT_LIMIT`; older plans may return `TOKENS_LIMIT`

If the user changes a plan's unit, migrate existing ledger values to the same unit. Otherwise a credits-to-percentage conversion looks like a cycle reset.

For `local_jsonl`, verify the glob and inspect only enough record structure to determine `value_path` and `timestamp_path`. Avoid echoing whole logs because they may contain prompts or private data.

## 3. Configure the recipient

For GitHub Actions:

- Feishu direct message: `type = "feishu_app"` with `app_id = "${FEISHU_APP_ID}"`, `app_secret = "${FEISHU_APP_SECRET}"`, and `user_id = "${FEISHU_USER_ID}"`; it sends Card 2.0 through the app API and requires bot send-message scope and a direct-message relationship
- Feishu group: `type = "feishu"`, `webhook_url = "${FEISHU_WEBHOOK_URL}"`
- Telegram: `type = "telegram"`, `bot_token`, and `chat_id`
- Bark: `type = "bark"`, `device_key`; optional `server` and `group`

For local personal Feishu delivery:

```toml
[[notifiers]]
type = "feishu_cli"
identity = "bot"
# user_id = "ou_xxx" # optional; defaults to the current CLI user
```

`feishu_cli` sends a full-width Card 2.0 directly to the current CLI user, with a nine-cell progress row, no redundant percentage denominator, and minute-level reset times. It requires a working `lark-cli` login, bot send-message scope, and a direct-message relationship with the recipient. No App Secret belongs in `plans.toml`.

Use distinct, descriptive environment-variable names for multiple custom providers.

## 4. Configure credentials safely

List each required variable and where the user sets it. Ask the user to set secrets in their own shell or GitHub Actions Secrets, then tell you when finished.

For GitHub Actions, ensure `.github/workflows/morning-brief.yml` maps every referenced secret. Existing mappings include `KIM_CODE_API_KEY`, `GLM_TOKEN_PLAN_API_KEY`, `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, and `FEISHU_USER_ID`; add new mappings when introducing new variables and keep the config-only workflow synchronized.

Do not generate persistent shell configuration or secret files unless the user explicitly asks. Do not echo secrets in verification commands.

## 5. Validate without sending

Parse TOML first:

```bash
uv run python -c 'import tomllib; tomllib.load(open("plans.toml", "rb")); print("TOML OK")'
```

When credentials are available:

```bash
uv run tokenpace --config plans.toml --dry-run
```

Use `bash -ic 'uv run tokenpace --config plans.toml --dry-run'` if the credentials require interactive `.bashrc` initialization.

Confirm that every expected plan appears, units and used/remaining directions are correct, rolling reset times are plausible, no ledger entry was added, and no notification was sent. Fix broken entries instead of silently leaving them in place.

TokenPace dry runs do not invoke notifiers. For `feishu_cli`, separately preview the actual CLI request with `lark-cli im +messages-send ... --dry-run`. A real TokenPace run requires explicit confirmation of recipient, content, and identity.

## 6. Deploy

### GitHub Actions (recommended)

- Direct the user to **Use this template → Private** at `https://github.com/scchy/token-pace/generate`; do not tell them to make a public fork private. The upstream maintainer must enable **Template repository** in Settings for this link to work.
- Ensure `plans.toml` and `.github/workflows/morning-brief.yml` are included when the user asks to commit or push.
- Confirm all referenced Secrets are configured in the generated private repository.
- Explain how to run **TokenPace Morning Brief** manually from the Actions tab.
- Keep the schedule at 10:30 Asia/Shanghai unless the user requests otherwise.
- Preserve automatic `data/ledger.jsonl` commits with `git add -f`, `[skip ci]`, and `git pull --rebase`, plus the upstream missing-config skip. Branch protection must allow the bot's persistence strategy.
- For a config-only private repository, copy both files from `examples/config-only-repo` and use its `uvx` workflow instead of the source-checkout workflow. Add new provider secret mappings to both workflows.
- Do not use `feishu_cli` or `local_jsonl` unless the runner can actually provide those local resources.

### Local cron

- Use the repository's absolute path.
- Modify crontab only if the user explicitly asks.
- Ensure provider variables and `lark-cli` authentication work in cron; interactive-shell variables are not inherited automatically.
- If appropriate, use `bash -ic 'uv run tokenpace --config plans.toml'` and write logs to a user-approved location.

## 7. Finish with a concise handoff

Report changed files, configured integrations, validation results, and remaining user actions. Distinguish clearly between:

- **Configured and dry-run verified**
- **Actually sent**
- **Scheduled for automatic delivery**

Never claim cron or GitHub Actions is deployed merely because a manual run succeeded. Never include secret values in the summary.
