# YouTube Daily Update 用户故事

## 项目目标

维护一个 YouTube 频道列表。系统每天在 Australia/Brisbane 时间 12:05 自动检查每个频道当天发布的新视频，尽量基于字幕生成简体中文内容总结，并通过 Telegram 发送给用户。

第一版技术组合：

- GitHub Actions 定时运行
- Gemini API Free Tier 生成简体中文摘要
- Telegram Bot 发送通知
- YouTube Data API 检查频道更新
- yt-dlp 获取公开字幕或自动字幕作为 transcript fallback
- repo 内 SQLite 状态文件记录已处理视频，避免重复推送

## 已确定决策

- 定时运行：GitHub Actions cron `5 2 * * *` UTC，对应 Brisbane 时间 12:05。
- 通知渠道：Telegram。
- 摘要语言：简体中文。
- 摘要模型：Gemini API Free Tier。
- 频道数量：第一版按 20 个以内设计。
- 没有新视频时：定时任务默认不发送普通通知。
- 状态持久化：第一版使用 repo 内 SQLite 文件 `state/seen_videos.sqlite`，由 GitHub Actions 在成功运行后提交回私有仓库。
- transcript 策略：优先使用公开视频字幕或自动字幕；不可用时使用标题、简介和元数据生成低置信度摘要。

## 故事边界与合并策略

- 本文按实现顺序排列，可以从 US-001 依次实现到 US-020。
- 每条故事都保留验收标准和自动化测试要求；实现该故事时必须同步补齐对应测试。
- 不再按产品、架构、开发、测试分组，避免同一能力在不同视角重复展开。
- 每条故事用“视角”标注主要关注点；同一故事可以覆盖多个专业视角。
- Telegram 内容可读性归 US-011；Telegram 发送和重试归 US-012。
- 摘要来源策略归 US-008；摘要质量门禁归 US-010。
- 去重规则归 US-006；SQLite 持久化归 US-005；失败时是否写入成功状态归 US-015。

## 实现顺序

### US-001 建立可离线测试的 provider 边界

视角：架构、开发、测试。

作为开发者，我希望 YouTube、Transcript、LLM、Notifier 都通过可替换 provider 调用，以便核心流程可以完全离线测试。

验收标准：

- 定义 YouTube、Transcript、LLM、Notifier 的接口或抽象边界。
- 提供 fake provider，用于本地和 CI 测试。
- 核心业务流程不直接依赖真实网络调用。
- Gemini provider 后续可替换为 OpenAI、Groq 或 Ollama。
- Telegram provider 后续可替换为 Discord。

自动化测试：

- 使用 fake provider 完成最小端到端流程。
- 验证核心流程在不设置真实 API key 时也能跑通测试。

### US-002 使用配置文件维护频道列表

视角：产品、开发、测试。

作为用户，我希望通过一个简单配置文件管理频道列表，以便添加、禁用频道不需要改代码。

验收标准：

- `channels.yml` 支持 `name`、`url` 或 `channel_id`、`enabled`。
- 禁用频道不会被检查。
- 缺少必要字段时，程序给出明确错误。
- 支持 20 个以内频道的日常运行。

自动化测试：

- 配置解析测试覆盖有效配置、缺字段配置、无效 URL、禁用频道。
- 验证禁用频道不会触发 YouTube provider 查询。

### US-003 管理运行时配置和 secrets

视角：安全、隐私、开发。

作为开发者，我希望 API key 和 token 只通过环境变量或 GitHub Secrets 注入，以便避免泄露。

验收标准：

- 需要的 secrets 包括 `GEMINI_API_KEY`、`YOUTUBE_API_KEY`、`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`。
- 程序启动时校验当前运行模式需要的环境变量。
- dry-run 和 fake provider 测试不要求真实 secrets。
- 配置文件中不得包含 secrets。
- 日志输出会脱敏 token、API key 和 chat id。

自动化测试：

- 环境变量缺失测试。
- 日志捕获测试，验证 secret 原文不会出现在 stdout/stderr。
- 静态检查样例配置不包含真实 secrets。

### US-004 按 Brisbane 日期计算当天窗口

视角：架构、测试。

作为系统，我需要只处理 Australia/Brisbane 当天发布的新视频，以便每日汇总准确。

验收标准：

- 当天窗口按 Brisbane `00:00:00` 到 `23:59:59` 判断。
- YouTube UTC 发布时间会正确转换到 Brisbane 时区。
- 边界时间不会重复或遗漏。
- Brisbane 当前无夏令时，cron 和日期窗口都按 UTC+10 处理。

自动化测试：

- 覆盖 UTC 前一天 14:00 对应 Brisbane 当天 00:00。
- 覆盖 UTC 当天 13:59:59 对应 Brisbane 当天 23:59:59。
- 覆盖窗口外视频被排除。

### US-005 持久化已处理状态

视角：架构、开发、运维。

作为系统，我需要在 GitHub Actions 临时环境中保留已处理状态，以便每天运行可以去重。

验收标准：

- 第一版状态存储使用 repo 内 SQLite 文件 `state/seen_videos.sqlite`。
- 状态只保存必要元数据，例如 `video_id`、频道 ID、发布时间、处理时间和处理状态。
- 不保存完整 transcript，避免仓库膨胀和隐私风险。
- 支持 schema migration。
- SQLite 文件由 GitHub Actions 在成功运行后提交回私有仓库。

自动化测试：

- SQLite 文件读写测试。
- schema migration 测试。
- 损坏状态文件 fallback 测试。
- 验证不会写入完整 transcript。

### US-006 避免重复推送

视角：架构、产品、测试。

作为系统，我需要记录已处理视频，以便重复运行不会重复发送同一视频。

验收标准：

- 每个已处理视频以 `video_id` 为唯一键记录。
- 重复运行同一输入不会再次发送。
- 已成功通知的视频标记为 `notified`。
- 失败视频不应被错误标记为 `notified`。

自动化测试：

- 同一 fixtures 连续运行两次，第二次 Telegram notifier 不被调用。
- 模拟 Gemini 或 Telegram 失败，验证 state 不会错误记录成功。

### US-007 发现当天新视频

视角：产品、架构。

作为用户，我希望系统每天检查频道列表中当天发布的新视频，以便汇总只包含新内容。

验收标准：

- 使用 YouTube Data API 查询频道最新上传。
- 只保留 Brisbane 当天窗口内的视频。
- 支持通过 `channel_id` 直接查询。
- 对 `url` 配置，系统能解析或查询得到对应频道 ID。
- 单个频道查询失败不影响其他频道。

自动化测试：

- 使用 fake YouTube provider 覆盖多频道、多视频、无新视频、频道失败场景。
- 验证窗口外视频被过滤。
- 验证频道失败被记录但不会中断全局流程。

### US-008 获取 transcript 并 fallback

视角：产品、架构、平台合规。

作为用户，我希望系统优先基于公开字幕或自动字幕生成摘要，以便摘要比只看标题更准确。

验收标准：

- 优先使用公开视频字幕或自动字幕。
- 只抓取字幕文本，不下载视频本体。
- 字幕不可用时，fallback 到标题、简介和元数据。
- transcript 获取失败不影响其他视频处理。
- 每个视频记录摘要依据：字幕、自动字幕、标题和简介。

自动化测试：

- 覆盖字幕存在、自动字幕存在、字幕缺失、yt-dlp 失败四种路径。
- 验证 fallback 时摘要依据为标题和简介。
- 验证一个视频 transcript 失败时其他视频仍可处理。

### US-009 使用 Gemini 生成简体中文摘要

视角：产品、开发、成本。

作为用户，我希望每个新视频都生成简体中文摘要，以便快速判断是否需要观看原视频。

验收标准：

- Gemini prompt 明确要求简体中文。
- 每条视频摘要包含频道名、视频标题、发布时间、视频链接、3-5 条要点和摘要依据。
- 无字幕时必须生成低置信度摘要。
- prompt 明确要求模型不要编造未提供的信息。
- transcript 过长时按策略截断或分段，避免超出模型限制。

自动化测试：

- 使用固定 transcript mock Gemini 输出，验证最终摘要包含必要字段。
- 验证 prompt 包含简体中文、来源依据、禁止编造要求。
- 验证长 transcript 会触发截断或分段策略。

### US-010 建立摘要质量门禁

视角：测试、产品。

作为测试者，我希望摘要质量有可自动检查的最低标准，以便避免空摘要、语言错误或来源标记缺失。

验收标准：

- 摘要不能为空。
- 摘要必须是简体中文。
- 摘要必须包含来源依据：字幕、自动字幕或标题和简介。
- 无字幕时必须标记低置信度。
- 摘要不得声称看过视频画面，除非输入中包含视觉信息。

自动化测试：

- 规则测试检查输出非空、中文比例、来源标记、低置信度标记。
- mock 输入验证 prompt 不要求模型编造未提供的信息。

### US-011 生成 Telegram 可读消息

视角：产品、开发。

作为用户，我希望 Telegram 消息按视频条目清晰展示，以便在手机上快速浏览。

验收标准：

- 多个视频按条目分隔。
- 每个条目包含标题、频道名、视频链接、发布时间和摘要要点。
- 长消息优先按视频条目拆分，其次按段落拆分。
- 每条消息不超过 Telegram `sendMessage` 限制。
- Markdown 特殊字符会正确处理。

自动化测试：

- 超长中文内容拆分测试。
- Markdown 特殊字符转义测试。
- 多视频消息格式快照测试。

### US-012 发送 Telegram 通知

视角：产品、开发、运维。

作为用户，我希望每天有新视频时收到 Telegram 通知，以便及时阅读汇总。

验收标准：

- 使用 Telegram Bot API 发送消息到 `TELEGRAM_CHAT_ID`。
- 没有新视频时，定时任务默认不发送普通通知。
- Telegram 发送失败时有重试。
- 重试后仍失败时，相关视频不标记为 `notified`。

自动化测试：

- Telegram success mock 测试。
- Telegram 429、500、timeout mock 测试。
- 验证无新视频时 notifier 不被调用。
- 验证发送失败不会污染成功 state。

### US-013 支持本地 dry-run

视角：开发、测试。

作为开发者，我希望本地可以用一条命令跑完整 dry-run，以便调试摘要和消息格式。

验收标准：

- `--dry-run` 不发送 Telegram。
- `--dry-run` 默认不写入已处理 state。
- dry-run 输出即将发送的消息内容和处理统计。
- dry-run 可以使用 fake provider，也可以在显式配置 secrets 后使用真实 provider。

自动化测试：

- CLI 参数测试覆盖 dry-run。
- 验证 dry-run 不调用真实 Telegram provider。
- 验证 dry-run 无 state 写入副作用。

### US-014 编排每日主流程

视角：架构、开发。

作为系统，我需要把配置读取、视频发现、transcript 获取、摘要生成、消息发送和 state 更新串成一个可重复运行的每日流程。

验收标准：

- 主流程按频道逐个检查。
- 主流程按视频逐个处理。
- 单个频道或视频失败不影响其他频道或视频。
- 运行结束输出统计：检查频道数、新视频数、成功摘要数、成功通知数、失败数。
- 只有通知成功的视频才写入 `notified` 状态。

自动化测试：

- fake integration test 覆盖完整业务流程。
- 覆盖部分失败、全部成功、无新视频三种场景。
- 验证统计数字准确。

### US-015 外部 API 失败时可恢复

视角：开发、运维、测试。

作为系统，我希望外部服务失败时系统能部分成功，而不是整体中断。

验收标准：

- YouTube 查询失败会记录频道级错误。
- yt-dlp 失败会 fallback 到标题和简介。
- Gemini 失败会记录视频级错误，不影响其他视频。
- Telegram 失败会重试，重试后仍失败则不标记相关视频为 `notified`。
- 所有失败都有可定位的日志，不输出 secrets。

自动化测试：

- mock 429、500、timeout、无字幕、无效响应。
- 验证错误统计准确。
- 验证失败不会污染成功 state。

### US-016 控制成本和配额

视角：成本、架构、运维。

作为用户，我希望系统尽量保持在免费额度或低成本范围内，以便长期运行不会产生意外费用。

验收标准：

- 只在发现当天新视频后调用 Gemini。
- 已处理视频不会重复调用 Gemini。
- 支持限制单次运行最大处理视频数。
- 支持限制 transcript 最大字符数或 token 预算。
- YouTube API 查询数量与频道数量线性相关，第一版按 20 个以内优化。
- Gemini 或 YouTube API 限流时记录明确错误，并按失败策略继续处理其他项目。

自动化测试：

- 验证无新视频时不会调用 LLM provider。
- 验证重复视频不会调用 LLM provider。
- 验证最大视频数和 transcript 长度限制生效。
- mock quota exceeded 和 rate limit 响应。

### US-017 最小化敏感数据和持久化数据

视角：安全、隐私、平台合规。

作为用户，我希望系统只保存必要数据，以便降低泄露和仓库膨胀风险。

验收标准：

- state 只保存必要元数据，不保存完整 transcript 或完整摘要。
- 真实 secrets 只存在 GitHub Secrets 或本地环境变量中。
- 日志不输出 API key、Bot token、chat id、完整 transcript。
- 建议 GitHub 仓库为私有仓库；若仓库为公开仓库，不允许提交真实 state。
- 样例配置只能使用占位值。

自动化测试：

- 检查 state 写入字段。
- 日志脱敏测试。
- 样例配置 secrets 扫描测试。

### US-018 提供可观测性和失败提示

视角：运维、产品。

作为用户，我希望知道每日任务是否失败，以便不是静默漏掉更新。

验收标准：

- 每次运行输出结构化统计日志。
- GitHub Actions 失败时可在 Actions 页面看到明确错误。
- 如果任务部分失败但仍有成功摘要，Telegram 汇总末尾包含简短失败计数。
- 如果整次运行失败且无法发送正常摘要，允许发送一条简短错误通知到 Telegram。
- 错误通知不得包含 secrets 或完整 transcript。

自动化测试：

- 验证统计日志字段存在。
- 验证部分失败时 Telegram 消息包含失败计数。
- 验证错误通知脱敏。

### US-019 配置 GitHub Actions 自动运行

视角：运维、开发、测试。

作为用户，我希望系统每天自动运行，并支持手动触发，以便无需本机在线。

验收标准：

- workflow 包含 `schedule`，cron 为 `5 2 * * *` UTC。
- workflow 包含 `workflow_dispatch`。
- workflow 安装运行所需依赖。
- workflow 使用 GitHub Secrets 注入必要环境变量。
- workflow 运行成功后提交 `state/seen_videos.sqlite` 的变化。
- workflow 不在 pull request from fork 场景暴露 secrets。

自动化测试：

- 静态测试校验 workflow 包含 `schedule` 和 `workflow_dispatch`。
- 静态测试校验 cron 表达式。
- 静态测试校验 secrets 只通过 env 注入。
- 使用 fake provider 在 CI 中跑一次完整流程。

### US-020 支持真实服务 smoke test

视角：测试、运维。

作为测试者，我希望能手动运行真实服务 smoke test，以便验证真实链路可用，但不会默认消耗额度。

验收标准：

- 只有设置 `RUN_LIVE_TESTS=true` 且 secrets 存在时才访问真实服务。
- live test 可以限制频道数和视频数。
- live test 默认使用 dry-run。
- 只有显式设置 `ALLOW_LIVE_TELEGRAM_SEND=true` 时才发送真实 Telegram 消息。
- 缺少 secrets 时给出明确跳过原因。

自动化测试：

- CI 默认跳过 live tests。
- 设置 live test 环境变量时执行真实链路测试。
- 缺少 secrets 时测试标记为 skipped，而不是 failed。

## 平台合规约束

这些约束贯穿所有故事，不单独作为后置功能实现：

- 使用 YouTube Data API 检查更新。
- yt-dlp 只用于获取公开视频字幕或自动字幕，不下载视频本体。
- 不保存、不重新分发完整 transcript。
- Telegram 只发送摘要和原视频链接。
- 如果未来扩展为多人使用，需要重新评估 YouTube、Telegram、Gemini 的使用条款和隐私告知。

## 不能完全自动化测试的部分

- Telegram 是否真的在用户手机上弹出通知。代码只能验证 Telegram API 接受消息。
- GitHub Actions 是否每天精确在 12:05 Brisbane 触发。可以校验 cron，但 GitHub 可能延迟。
- Gemini Free Tier 当天是否一定有额度。可以测试限流处理，不能保证未来额度。
- yt-dlp 对 YouTube 页面变化的长期稳定性。可以做 live smoke test，但不可完全确定。
- 摘要是否达到 NotebookLM 级别的主观质量。可以自动检查结构、语言、来源标记和低置信度提示，但深度准确性仍需要人工抽样。
- YouTube、Telegram、Gemini 平台条款未来是否变化。可以记录约束和减少风险，不能通过自动化测试保证长期合规。

## 第一版完成定义

- US-001 到 US-020 均完成对应验收标准。
- 核心流程有离线测试覆盖。
- GitHub Actions 可每天自动运行，并支持手动触发。
- 配置文件可维护 20 个以内频道。
- 新视频会生成简体中文摘要并发送到 Telegram。
- 重复运行不会重复发送同一视频。
- state 使用 `state/seen_videos.sqlite` 持久化，并由私有 repo 保存。
- 无字幕、API 失败、消息过长、限流、secrets 缺失等常见异常路径有自动化测试。
- 真实服务 smoke test 可手动开启，默认 CI 不消耗外部额度。
