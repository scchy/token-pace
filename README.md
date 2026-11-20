# token-pace

**简体中文** | [English](README.en.md)

**你的 AI Token 配速员 —— 零运维、零运行时依赖的每日额度晨报工具。**

`token-pace` 汇总多个 API 或 Coding Plan 的剩余额度，结合近 7 日真实消耗速率与周期重置日，计算今天的建议用量，并将晨报推送到飞书、Telegram 或 iOS Bark。

```text
📊 TokenPace 每日额度晨报 (11-20)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OpenRouter API   ⚠️ 偏快
██████░░░░░░ 48.5% 剩余 (48.50 / 100.00 USD · 距重置 11 天)
• 近 7 日均耗：5.60 USD/天 → 预计 8.7 天后 (11-28) 耗尽
• 均匀消耗线：4.41 USD/天
• 今日建议：消耗偏快 (+27%)，将提前耗尽。建议今日控制在 4.41 USD 以内。
```

## 特性

- **决策导向**：展示剩余额度、近 7 日均耗、预计耗尽日、均匀消耗线和今日建议。
- **可靠账本**：纯文本 `data/ledger.jsonl`，同日重复运行取最后一条，自动处理断更均摊和跨周期重置。
- **故障隔离**：一个数据源超时不会阻止其他套餐生成晨报；错误会附在晨报末尾。
- **私有自托管**：凭证只从环境变量读取，核心运行时仅用 Python 3.11+ 标准库，无数据库、Web UI 或常驻进程。
- **两种运行方式**：GitHub Actions 每日自动推送并保存账本，或在本机 cron 中运行。

## 快速开始

### GitHub Actions（推荐）

1. Fork 本仓库，建议设为 **Private**，避免公开使用习惯和历史账本。
2. 复制 `plans.example.toml` 为 `plans.toml`，删除不需要的套餐和通知渠道，提交该文件。
3. 在 `Settings → Secrets and variables → Actions` 添加配置中引用的 Secrets，例如 `OPENROUTER_API_KEY`、`FEISHU_WEBHOOK_URL`。
4. 在 Actions 页面手动运行 **TokenPace Morning Brief**。此后每天北京时间 08:30 自动执行，并自动提交新增账本。

GitHub 的定时任务可能延迟数分钟；Actions 不适合本机 `local_jsonl` 日志数据源。

### 本地运行

需要 Python 3.11+，推荐使用 [uv](https://docs.astral.sh/uv/)：

```bash
cp plans.example.toml plans.toml
export OPENROUTER_API_KEY="sk-or-..."
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/..."

# 只预览，不推送、不写账本
uv run tokenpace --config plans.toml --dry-run

# 正式运行
uv run tokenpace --config plans.toml
```

也支持 `uv run token-pace` 和 `uv run python -m tokenpace`。每日 cron 示例：

```cron
30 8 * * * cd ~/token-pace && uv run tokenpace --config plans.toml >> /tmp/token-pace.log 2>&1
```

## 配置

所有凭证必须使用 `${ENV_VAR}` 占位符。缺少环境变量时程序会明确报错，不会把占位符当作密钥发送。

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
mode = "used"                 # used 或 remaining
[plans.headers]
Authorization = "Bearer ${CUSTOM_PLAN_TOKEN}"

[[notifiers]]
type = "feishu"
webhook_url = "${FEISHU_WEBHOOK_URL}"
```

`ledger_path` 的相对路径以配置文件所在目录为基准。`reset_cycle` 支持：

- `monthly:N`：每月 N 日重置；小月份自动落到该月最后一天。
- `YYYY-MM-DD`：固定重置日期。

### 数据源

| Provider | 接口 / 输入 | 认证或配置 |
| --- | --- | --- |
| `openrouter` | `GET https://openrouter.ai/api/v1/key`，读取 `data.usage` | `plans.auth.api_key` |
| `deepseek` | `GET https://api.deepseek.com/user/balance`，按余额换算已用量 | `plans.auth.api_key` |
| `http_json` | 任意 GET JSON 接口 | `options.url`、`value_path`、`scale`、`mode` 与 `plans.headers` |
| `local_jsonl` | 本机 JSONL 用量日志 | `options.log_glob` 及可选字段映射 |

`http_json.value_path` 支持点分对象路径和数组下标，例如 `data.items.0.remaining`。`mode = "used"` 表示字段是已用量，`"remaining"` 表示字段是剩余量。

`local_jsonl` 完整示例：

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
value_path = "usage.total_tokens"  # 省略时自动识别常见 tokens / used / cost 字段
timestamp_path = "timestamp"      # 支持 ISO 时间、日期、Unix 秒或毫秒
scale = 1e-6
aggregate = "sum"                 # sum：逐条累加；latest：取累计字段的最后一条
```

月度套餐只统计当前周期内的带时间戳记录；没有时间戳的记录会纳入统计。省略 `value_path` 时依次识别 `usage.total_tokens`、`total_tokens`、`tokens`、`used`、`cost`。因此，非 Token 计费日志也可以统一换算为成本单位。

### 通知渠道

飞书使用 Interactive Card；Telegram 使用 MarkdownV2；Bark 使用 JSON 推送。

```toml
[[notifiers]]
type = "telegram"
bot_token = "${TELEGRAM_BOT_TOKEN}"
chat_id = "${TELEGRAM_CHAT_ID}"

[[notifiers]]
type = "bark"
device_key = "${BARK_DEVICE_KEY}"
server = "https://api.day.app"  # 可选，也可换成自建 Bark Server
group = "TokenPace"             # 可选
```

## 配速规则

设总额度为 `Q`、当前周期已用量为 `U`、距重置剩余 `D` 天、近 7 日平均日耗为 `B`：

- 剩余额度 `R = max(0, Q - U)`。
- 均匀消耗线 `safe = R / max(1, D)`；开启 `workdays_only` 后仅按剩余工作日计算。
- 消耗水位比 `ρ = B / safe`。
- 预计耗尽天数 `R / B`；无消耗时不预测耗尽日。

| 状态 | 条件 | 今日建议 |
| --- | --- | --- |
| 🚨 耗尽 | `R = 0` | 切换备用通道或等待重置 |
| ⚠️ 偏快 | `ρ > 1.2` | 控制在均匀消耗线内，常规任务可切轻量模型 |
| ✅ 健康 | `0.8 ≤ ρ ≤ 1.2` | 维持当前频率 |
| 🟢 充裕 | `0 < ρ < 0.8` | 可将长上下文或重度推理任务往前排 |
| 💤 闲置 | `B = 0` | 给出今日起跑线 |

历史相邻快照若相隔多天，消耗会均摊到区间每一天；若累计用量回落，则识别为周期重置，以重置后的累计值计算。新接入不足 7 天时按实际样本数计算，不会用零填充。

## 开发与测试

```bash
uv run pytest
uv run tokenpace --help
```

核心数据流为 `Providers → Ledger → Engine → Notifiers`。新增数据源只需实现 `Provider.fetch()` 并在 `src/tokenpace/providers/__init__.py` 注册；新增通知渠道对应实现 `Notifier.send()`。

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=scchy/token-pace&type=Date)](https://star-history.com/#scchy/token-pace&Date)

## License

[MIT](LICENSE)
