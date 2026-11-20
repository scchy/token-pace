<div align="center">

# TokenPace

**Know your burn. Pace your tokens. Never run dry.**

Your AI token pacer — a zero-maintenance daily quota briefing with **zero runtime dependencies**.

[Quick Start](#quick-start) · [Why TokenPace?](#why-tokenpace) · [Configuration](#configuration) · [Pacing Rules](#pacing-rules) · [中文文档](README.zh-CN.md)

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Zero Runtime Dependencies](https://img.shields.io/badge/Runtime-Zero%20Dependencies-2EA44F)](#why-tokenpace)
[![CI](https://github.com/scchy/token-pace/actions/workflows/ci.yml/badge.svg)](https://github.com/scchy/token-pace/actions/workflows/ci.yml)
[![Morning Brief](https://github.com/scchy/token-pace/actions/workflows/morning-brief.yml/badge.svg)](https://github.com/scchy/token-pace/actions/workflows/morning-brief.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-F0AD4E)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/scchy/token-pace?style=social)](https://github.com/scchy/token-pace/stargazers)

</div>

---

TokenPace turns scattered AI balances into one actionable morning brief. It combines your remaining quota, actual seven-day burn rate, and cycle reset date to answer three questions at a glance:

1. **How much is left?**
2. **Will it last until the next reset?**
3. **How much can I safely use today?**

Get the answer where you already are: **Feishu, Telegram, or iOS Bark** — no dashboard, database, server, or always-on process.

<div align="center">

**[1. Fork](https://github.com/scchy/token-pace/fork) · [2. Configure](plans.example.toml) · [3. Add Secrets & Run](https://github.com/scchy/token-pace/actions/workflows/morning-brief.yml)**

</div>

## AI-Assisted Setup

Open your fork or clone with a coding agent and say:

> Configure TokenPace for me using the project skill. Ask which plans and notifiers I need, create plans.toml, and validate it with a dry run.

[AGENTS.md](AGENTS.md) and the [`tokenpace-setup`](.agents/skills/tokenpace-setup/SKILL.md) skill guide minimal configuration, credential safety, dry-run validation, and optional scheduling — without asking for secrets in chat.

## Morning Brief

```text
📊 TokenPace Daily Quota Brief (11-20)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OpenRouter API   ⚠️ FAST
██████░░░░░░ 48.5% remaining (48.50 / 100.00 USD · 11 days to reset)
• 7-day average: 5.60 USD/day → exhausted in 8.7 days (11-28)
• Sustainable pace: 4.41 USD/day
• Today: 27% too fast — keep usage within 4.41 USD.
───────────────────────────────────────────────────────────
DeepSeek API     🟢 SURPLUS
█████████░░░ 76.0% remaining (152.00 / 200.00 CNY · 11 days to reset)
• 7-day average: 8.20 CNY/day → exhausted in 18.5 days (12-08)
• Sustainable pace: 13.82 CNY/day
• Today: room for heavier tasks — use up to 13.82 CNY.
```

## Why TokenPace?

| Capability | What it means for you |
| --- | --- |
| **Actionable, not just informational** | See your burn rate, predicted exhaustion date, sustainable pace, and a concrete daily budget. |
| **One brief for every plan** | Aggregate official APIs, custom JSON endpoints, and local Coding Agent logs. |
| **Reliable seven-day history** | Same-day runs are idempotent, missed days are smoothed, and cycle resets are detected automatically. |
| **Failure isolation** | One unavailable provider does not block the rest of your briefing; errors are clearly appended. |
| **Private by default** | Credentials come from environment variables. Your ledger stays in your own repository or machine. |
| **Simple to audit and run** | Python 3.11+ standard library only, plain JSONL storage, and no runtime packages to install. |

## Quick Start

### Option A — GitHub Actions

Run daily at **08:30 Asia/Shanghai**, with automatic ledger commits.

1. **Fork** this repository. Making it private is recommended because the ledger reveals usage patterns.
2. Copy `plans.example.toml` to `plans.toml`, remove unused plans and notifiers, then commit it.
3. Add the referenced credentials under **Settings → Secrets and variables → Actions**.
4. Open **Actions → TokenPace Morning Brief → Run workflow** to send your first brief.

> GitHub schedules may be delayed by several minutes. Use local mode for `local_jsonl` sources on your machine.

### Option B — Local or Cron

Python 3.11+ is required. [uv](https://docs.astral.sh/uv/) is recommended.

```bash
cp plans.example.toml plans.toml
export OPENROUTER_API_KEY="sk-or-..."
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/..."

# Preview safely: no push, no ledger write
uv run tokenpace --config plans.toml --dry-run

# Fetch, persist, and notify
uv run tokenpace --config plans.toml
```

Run every morning with cron:

```cron
30 8 * * * cd ~/token-pace && uv run tokenpace --config plans.toml >> /tmp/token-pace.log 2>&1
```

You can also invoke `uv run token-pace` or `uv run python -m tokenpace`.

## How It Works

```text
Providers → Append-only JSONL Ledger → Pacing Engine → Feishu / Telegram / Bark
```

For every plan, TokenPace calculates:

- **Remaining quota**: `R = max(0, Q - U)`
- **Sustainable daily pace**: `safe = R / max(1, D)`
- **Seven-day burn rate**: the arithmetic mean of up to seven real daily increments
- **Pacing ratio**: `ρ = B / safe`
- **Estimated exhaustion**: `R / B`, when usage is greater than zero

Enable `workdays_only` to distribute the remaining quota across weekdays only.

## Configuration

Credentials must use `${ENV_VAR}` placeholders. TokenPace stops with a clear error if a referenced variable is missing.

A minimal configuration looks like this:

```toml
[general]
timezone = "Asia/Shanghai"
ledger_path = "data/ledger.jsonl"
workdays_only = false
timeout = 10

[[plans]]
id = "openrouter"
name = "OpenRouter API"
provider = "openrouter"
unit = "USD"
total_quota = 100.0
reset_cycle = "monthly:1"
[plans.auth]
api_key = "${OPENROUTER_API_KEY}"

[[notifiers]]
type = "feishu"
webhook_url = "${FEISHU_WEBHOOK_URL}"
```

Relative ledger paths are resolved from the configuration file. Reset cycles support:

| Format | Behavior |
| --- | --- |
| `monthly:N` | Reset on day N each month; shorter months use their last day |
| `YYYY-MM-DD` | Use a fixed reset date |

See [`plans.example.toml`](plans.example.toml) for a complete multi-provider setup.

### Providers

| Provider | Source | Key configuration |
| --- | --- | --- |
| `openrouter` | OpenRouter key API, reading `data.usage` | `plans.auth.api_key` |
| `deepseek` | DeepSeek balance API, converted to usage | `plans.auth.api_key` |
| `http_json` | Any GET JSON endpoint | `url`, `value_path`, `scale`, `mode`, custom headers |
| `local_jsonl` | Local Coding Agent / CLI JSONL logs | `log_glob`, field mapping, scale, aggregation |

`http_json.value_path` supports nested objects and array indexes, such as `data.items.0.remaining`. Set `mode = "used"` for consumed quota or `"remaining"` for remaining quota.

<details>
<summary><strong>DeepSeek and custom HTTP JSON examples</strong></summary>

```toml
[[plans]]
id = "deepseek"
name = "DeepSeek API"
provider = "deepseek"
unit = "CNY"
total_quota = 200.0
reset_cycle = "monthly:1"
[plans.auth]
api_key = "${DEEPSEEK_API_KEY}"

[[plans]]
id = "custom-plan"
name = "My Coding Plan"
provider = "http_json"
unit = "M tokens"
total_quota = 50.0
reset_cycle = "monthly:15"
[plans.options]
url = "https://api.example.com/v1/usage"
value_path = "data.used_tokens"
scale = 1e-6
mode = "used"
[plans.headers]
Authorization = "Bearer ${CUSTOM_PLAN_TOKEN}"
```

</details>

<details>
<summary><strong>Local JSONL provider example</strong></summary>

```toml
[[plans]]
id = "local-agent"
name = "Local Coding Agent"
provider = "local_jsonl"
unit = "M tokens"
total_quota = 50.0
reset_cycle = "monthly:1"
[plans.options]
log_glob = "~/.coding-agent/usage/**/*.jsonl"
value_path = "usage.total_tokens"
timestamp_path = "timestamp"
scale = 1e-6
aggregate = "sum" # sum records, or use latest for a cumulative field
```

For monthly plans, timestamped records are limited to the current cycle; records without timestamps are included. ISO timestamps, dates, Unix seconds, and milliseconds are supported.

When `value_path` is omitted, TokenPace checks `usage.total_tokens`, `total_tokens`, `tokens`, `used`, and `cost` in order. Cost-based logs can therefore be normalized into a monetary unit too.

</details>

### Notifiers

| Notifier | Delivery style | Required settings |
| --- | --- | --- |
| `feishu` | Interactive Card with progress bars and status colors | `webhook_url` |
| `telegram` | MarkdownV2 message | `bot_token`, `chat_id` |
| `bark` | iOS push notification | `device_key`; optional `server`, `group`, `icon` |

```toml
[[notifiers]]
type = "telegram"
bot_token = "${TELEGRAM_BOT_TOKEN}"
chat_id = "${TELEGRAM_CHAT_ID}"

[[notifiers]]
type = "bark"
device_key = "${BARK_DEVICE_KEY}"
server = "https://api.day.app"
group = "TokenPace"
```

## Pacing Rules

| Status | Condition | Recommended action |
| --- | --- | --- |
| 🚨 Exhausted | `R = 0` | Switch to a backup provider or wait for reset |
| ⚠️ Fast | `ρ > 1.2` | Stay within the sustainable pace; use lighter models for routine tasks |
| ✅ Healthy | `0.8 ≤ ρ ≤ 1.2` | Maintain the current pace |
| 🟢 Surplus | `0 < ρ < 0.8` | Move long-context or reasoning-heavy tasks forward |
| 💤 Idle | `B = 0` | Start from the suggested daily budget |

Missing days are averaged across the snapshot interval. A decrease in cumulative usage is treated as a cycle reset. New plans use the available samples rather than padding missing history with zeros.

## Development

```bash
uv run pytest
uv run tokenpace --help
```

The extension surface is intentionally small:

- **Provider**: implement `Provider.fetch()` and register it in `src/tokenpace/providers/__init__.py`.
- **Notifier**: implement `Notifier.send()` and register it in `src/tokenpace/notifiers/__init__.py`.

Every push and pull request runs the full test suite through [CI](.github/workflows/ci.yml). Notifier tests use local mocks and require no credentials.

## Roadmap

| Planned addition | Contribution welcome |
| --- | --- |
| Discord notifier | PR welcome |
| Slack notifier | PR welcome |
| Generic JSON webhook notifier | PR welcome |
| More provider presets, including Kimi, Anthropic, and Zhipu | PR welcome |

## Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=scchy/token-pace&type=Date)](https://star-history.com/#scchy/token-pace&Date)

</div>

---

<div align="center">

**[MIT License](LICENSE)** · Built for developers who want to spend tokens wisely.

</div>
