# token-pace

[简体中文](README.md) | **English**

**Your AI token pacer — a zero-maintenance daily quota briefing with no runtime dependencies.**

`token-pace` aggregates the remaining quotas of your API and Coding Plan accounts, combines their actual burn rate over the last seven days with their cycle reset dates, calculates a recommended budget for today, and delivers the briefing through Feishu, Telegram, or iOS Bark.

```text
📊 TokenPace Daily Quota Brief (11-20)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OpenRouter API   ⚠️ Fast
██████░░░░░░ 48.5% remaining (48.50 / 100.00 USD · 11 days to reset)
• 7-day average burn: 5.60 USD/day → estimated exhaustion in 8.7 days (11-28)
• Even consumption rate: 4.41 USD/day
• Today: consumption is 27% too fast. Keep usage within 4.41 USD.
```

## Features

- **Decision-oriented metrics**: remaining quota, seven-day average burn, estimated exhaustion date, even consumption rate, and actionable daily advice.
- **Reliable ledger**: a plain-text `data/ledger.jsonl` file, last-run-wins de-duplication for repeated runs on the same day, gap smoothing, and automatic cycle-reset detection.
- **Fault isolation**: a timeout from one provider does not prevent briefings for other plans; errors are appended to the briefing.
- **Private self-hosting**: credentials are read only from environment variables. The runtime uses only the Python 3.11+ standard library, with no database, web UI, or daemon.
- **Two deployment options**: GitHub Actions with automatic ledger commits, or a local cron job.

## Quick Start

### GitHub Actions (recommended)

1. Fork this repository. Making it **Private** is recommended to avoid publishing usage patterns and ledger history.
2. Copy `plans.example.toml` to `plans.toml`, remove plans and notifiers you do not need, and commit the file.
3. Under `Settings → Secrets and variables → Actions`, add every secret referenced by your configuration, such as `OPENROUTER_API_KEY` and `FEISHU_WEBHOOK_URL`.
4. Manually run **TokenPace Morning Brief** from the Actions page. It will then run every day at 08:30 Beijing time and automatically commit new ledger entries.

GitHub scheduled workflows may be delayed by several minutes. GitHub Actions cannot access local `local_jsonl` log files.

### Local Usage

Python 3.11+ is required. [uv](https://docs.astral.sh/uv/) is recommended:

```bash
cp plans.example.toml plans.toml
export OPENROUTER_API_KEY="sk-or-..."
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/..."

# Preview only: no notifications and no ledger writes
uv run tokenpace --config plans.toml --dry-run

# Run for real
uv run tokenpace --config plans.toml
```

You can also use `uv run token-pace` or `uv run python -m tokenpace`. Example cron entry:

```cron
30 8 * * * cd ~/token-pace && uv run tokenpace --config plans.toml >> /tmp/token-pace.log 2>&1
```

## Configuration

Always use `${ENV_VAR}` placeholders for credentials. If an environment variable is missing, the program reports a clear error instead of sending the placeholder as a credential.

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
mode = "used"                 # used or remaining
[plans.headers]
Authorization = "Bearer ${CUSTOM_PLAN_TOKEN}"

[[notifiers]]
type = "feishu"
webhook_url = "${FEISHU_WEBHOOK_URL}"
```

A relative `ledger_path` is resolved from the configuration file's directory. `reset_cycle` supports:

- `monthly:N`: reset on day N of each month; shorter months automatically use their last day.
- `YYYY-MM-DD`: a fixed reset date.

### Providers

| Provider | API / input | Authentication or configuration |
| --- | --- | --- |
| `openrouter` | `GET https://openrouter.ai/api/v1/key`, reading `data.usage` | `plans.auth.api_key` |
| `deepseek` | `GET https://api.deepseek.com/user/balance`, converting the balance to usage | `plans.auth.api_key` |
| `http_json` | Any GET JSON endpoint | `options.url`, `value_path`, `scale`, `mode`, and `plans.headers` |
| `local_jsonl` | Local JSONL usage logs | `options.log_glob` and optional field mappings |

`http_json.value_path` supports dot-separated object paths and array indexes, such as `data.items.0.remaining`. Use `mode = "used"` when the field contains consumed quota and `"remaining"` when it contains remaining quota.

Full `local_jsonl` example:

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
value_path = "usage.total_tokens"  # Optional: common tokens / used / cost fields are auto-detected
timestamp_path = "timestamp"      # ISO timestamps, dates, Unix seconds, or milliseconds
scale = 1e-6
aggregate = "sum"                 # sum: add records; latest: use the last cumulative value
```

For monthly plans, timestamped records are limited to the current cycle. Records without timestamps are included. When `value_path` is omitted, the provider checks `usage.total_tokens`, `total_tokens`, `tokens`, `used`, and `cost` in that order. Cost-based logs can therefore be normalized into a monetary unit as well.

### Notifiers

Feishu uses an Interactive Card, Telegram uses MarkdownV2, and Bark uses a JSON push request.

```toml
[[notifiers]]
type = "telegram"
bot_token = "${TELEGRAM_BOT_TOKEN}"
chat_id = "${TELEGRAM_CHAT_ID}"

[[notifiers]]
type = "bark"
device_key = "${BARK_DEVICE_KEY}"
server = "https://api.day.app"  # Optional; replace with your own Bark Server if needed
group = "TokenPace"             # Optional
```

## Pacing Rules

Let `Q` be the total quota, `U` the usage in the current cycle, `D` the number of days before reset, and `B` the average daily burn over the last seven days:

- Remaining quota: `R = max(0, Q - U)`.
- Even consumption rate: `safe = R / max(1, D)`; with `workdays_only`, only remaining weekdays are counted.
- Pacing ratio: `ρ = B / safe`.
- Estimated days until exhaustion: `R / B`; no exhaustion date is predicted when there is no usage.

| Status | Condition | Recommended action |
| --- | --- | --- |
| 🚨 Exhausted | `R = 0` | Switch to a backup provider or wait for reset |
| ⚠️ Fast | `ρ > 1.2` | Stay within the even consumption rate and use lighter models for routine tasks |
| ✅ Healthy | `0.8 ≤ ρ ≤ 1.2` | Maintain the current pace |
| 🟢 Surplus | `0 < ρ < 0.8` | Move long-context or reasoning-heavy tasks forward |
| 💤 Idle | `B = 0` | Show a starting budget for today |

When consecutive ledger snapshots are several days apart, consumption is distributed evenly across the interval. When cumulative usage decreases, a cycle reset is detected and the post-reset cumulative value is used. New plans with fewer than seven days of history use the actual sample count rather than zero-filled days.

## Development and Testing

```bash
uv run pytest
uv run tokenpace --help
```

The core data flow is `Providers → Ledger → Engine → Notifiers`. To add a provider, implement `Provider.fetch()` and register it in `src/tokenpace/providers/__init__.py`. To add a notifier, implement `Notifier.send()` and register it in the corresponding notifier registry.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=scchy/token-pace&type=Date)](https://star-history.com/#scchy/token-pace&Date)

## License

[MIT](LICENSE)
