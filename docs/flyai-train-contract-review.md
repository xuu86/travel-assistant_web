# FlyAI 铁路官方契约核查

> 核查日期：2026-10-31（Asia/Shanghai）
> 当前结论：用户已批准规格 v0.2 官方 CLI 适配，Provider、网页展示及本地 API 真实查询已完成；价格继续未知。下方 v0.1 稳定 HTTP/SDK Gate 核查为历史，已被 CLI 方案替代。
> 对应：[规格](SPEC-flyai-train-provider.md)、[实施计划](../tasks/flyai-train-provider-plan.md)。

## 可复核的官方资料

以下页面在公开资料核查阶段均返回 HTTP 200，该阶段仅审阅文档。用户随后配置真实 Key 并授权核验后的独立 CLI 查询见文末；未登录控制台。

| 官方来源 | 已核实内容 | 不能据此证明的事项 |
|---|---|---|
| [官网](https://flyai.open.fliggy.com/)与[能力概览](https://flyai.open.fliggy.com/docs) | 官网直接链接 `alibaba-flyai/flyai-skill` 仓库，提供 Skill 接入说明 | 独立后端 HTTP/SDK 契约、铁路账户权限 |
| [快速开始](https://flyai.open.fliggy.com/docs/quickstart) | 安装 Skill、从控制台获取正式 API Key、通过 `flyai config set FLYAI_API_KEY` 配置 CLI | API Key 的服务端传输位置、正式 endpoint、协议版本 |
| [官方 README（固定提交）](https://github.com/alibaba-flyai/flyai-skill/blob/86fe2cc3e25464d0e0bd6a769b27b5f9f3b04128/README.md) | 存在 `search-train`；调用链描述为 Skill → CLI → Fliggy MCP API | 第三方服务端可依赖的 MCP endpoint、初始化/认证和错误契约 |
| [铁路命令参考（固定提交）](https://github.com/alibaba-flyai/flyai-skill/blob/86fe2cc3e25464d0e0bd6a769b27b5f9f3b04128/skills/flyai/references/search-train.md) | CLI 参数、席别示例和 JSON 输出示例 | 完整响应 schema、字段可空性、票价计价基准、错误码、稳定性承诺 |
| [官方展示要求（固定提交）](https://github.com/alibaba-flyai/flyai-skill/blob/86fe2cc3e25464d0e0bd6a769b27b5f9f3b04128/skills/flyai/SKILL.md) | 返回 `jumpUrl` 时展示预订链接；展示图片、平台提示 `systemMessage` 和品牌来源 | 这些要求在自建 Web 应用中的具体适用方式、是否允许省略链接 |
| [FAQ](https://flyai.open.fliggy.com/docs/faq) | 日期应为未来日期、城市使用中文全称；部分产品不返回价格，建议通过 `jumpUrl` 查看 | 铁路专用日期窗口、站点目录、缺价规则和价格确定性 |
| [用户服务协议](https://terms.alicdn.com/legal-agreement/terms/common_product_agreement/20260325101742636/20260325101742636.html) | 当前面向成年个人开发者，实际调用前需实名认证；免费服务配额可能受限；面向下游服务有书面告知要求 | 本项目账户已实名认证、铁路权限/具体配额、允许缓存期限、项目用途已核准 |
| [推广者指南](https://flyai.open.fliggy.com/docs/partner) | 介绍 Agent 中集成 Skill 的推广流程；交通类商品暂不参与分佣 | 铁路服务端调用权限、票价精度或本项目展示许可 |

官方仓库核查提交为 `86fe2cc3e25464d0e0bd6a769b27b5f9f3b04128`，GitHub 返回提交时间 `2026-09-16T06:38:58Z`。本文引用该固定版本，后续官方材料变更应重新核查。README 的推广描述、代码开源许可证均不替代在线服务的接口契约或账户权限。

## 参数与字段：仅记录，不定义实现映射

CLI 参考将 `--origin` 标为必填，`--destination`、`--dep-date`、日期区间、席别、车次、换乘、时间筛选、价格上限与排序标为可选。`--max-price` 标注 CNY 仅说明输入过滤条件，不能外推输出价格的币种、单位或人数基准。参考接受城市或车站；FAQ 要求城市中文全称，没有提供可核验的 station id 目录。

| 输出示例字段 | 示例所表达的内容 | 仍缺语义 |
|---|---|---|
| `data.itemList[]` | 结果条目 | 分页、最大条数、缺字段与空结果契约 |
| `adultPrice` | 带 `¥` 符号的价格字符串 | 元/分的正式定义、明确 CNY、成人单人/整单、起价/具体席别价、税费及与分段价格的关系 |
| `journeys[].segments[].marketingTransportNo` | 车次标签 | 格式约束、唯一标识及跨日规则 |
| `depStationName` / `arrStationName` | 发到站名 | 官方 station id、别名、歧义处理 |
| `depDateTime` / `arrDateTime` | 无时区偏移的日期时间字符串 | 时区、跨日和合法范围 |
| `seatClassName` | 席别标签 | 枚举、具体价格关联、余票字段；示例未提供余票 |
| `jumpUrl` / `systemMessage` | 跳转与平台提示 | Web 展示适用要求、可信 URL 边界、内容安全与留存要求 |
| `status` / `message` | 示例包含成功状态 `0` | 失败状态、HTTP 与业务错误关系、401/403/429 的正式语义 |

上述内容是官方文档示例的结构观察，未作为真实结果保存，也没有构造 FlyAI fixture 或将其标记为映射验收。取得正式金额和计价依据前不得把 `adultPrice` 转为确定的 `price_fen`；其他字段也须先确认服务端契约。

## v0.1 历史 Gate 决策与恢复条件（已被 v0.2 CLI 方案替代）

Gate A 三项均未通过。已审阅条款及部分 CLI 参数，不等于已取得所要求的完整服务端契约。Gate B/C 等待实现后验证；Gate D 的生产 Provider 端到端验收未完成，独立 CLI 诊断结果见文末。

1. 取得官方支持的服务端 HTTP/SDK 或明确受支持的 MCP 调用文档，包含固定 endpoint、认证传输、协议/版本、请求和响应 schema、错误码、超时及频率约束。不从 CLI 包内部提取未公开 endpoint 作为正式接口。
2. 确认本项目账户的铁路搜索权限、实名认证、配额、用途、缓存/存储/再展示期限与署名要求。服务协议未承诺商用标准，不应推断为全面禁止商用，也不能推断本项目已获准。
3. 取得输出价格、币种、单位、计价人数、税费、席别和余票的明确语义；无法确认的价格继续保留 null，不补估算。
4. 解决官方 Skill 预订链接展示要求与本规格不提供外部跳转之间的差异，确认是否适用于本项目；若需扩展跳转，先更新规格与链接安全边界。
5. Gate A 通过后依次执行配置、映射、runtime、前端及测试阶段。用户授权的独立 CLI 诊断已完成；生产 Provider 的端到端 live smoke 仍需 Gate A–C、账户/用途核验及相应测试范围落实。

按计划“找不到官方稳定服务端契约”停止条件，生产实现阶段 2–6 及生产端到端验收继续暂停。之后按用户授权执行的独立官方 CLI 诊断，不将包内实现提升为正式服务端契约，不修改生产运行时代码。

## 用户授权后的首次本地检查（历史，2026-10-31）

用户明确要求“使用真实apikey进行核验”，已记录这项授权，无需重复申请同一操作的权限。检查进程、Windows User/Machine 环境中的 `FLYAI_API_KEY`、`APP_FLYAI_API_KEY`、`APP_TRANSPORT_FLYAI_API_KEY`，以及项目 `.env` / `.env.local`、`backend/.env` / `.env.local`、常见 CLI 配置位置后，未发现已配置的 FlyAI Key。仅检查配置存在性，未打印或保存密钥值，也未读取其他供应商的凭据。

首次检查时尚未发送认证或搜索请求。用户随后回复“已配置”，已从 Git 忽略的 `backend/.env` 取得 `FLYAI_API_KEY` 并完成以下核验。

## 真实 Key 官方 CLI 核验（2026-10-31，Asia/Shanghai）

**结论：真实 Key 与本次铁路查询能力通过；票价映射及生产接入未验收。** 证据见[验收记录](acceptance/transport.md)及[脱敏机器摘要](acceptance/flyai-train-live-smoke-2026-10-31.json)。

- 使用官方 npm 包 `@fly-ai/flyai-cli@1.0.16` 的独立 bundle，下载后校验 registry SHA-512 integrity；仅解压到临时目录，无安装脚本、无项目依赖变更。
- 官方命令：`flyai search-train --origin "上海" --destination "杭州" --dep-date 2026-11-01`。本地开发环境；仅一次请求、无重试、无购票操作。
- Key 只经子进程环境传入。网络守卫确认 Authorization 使用该 Key、仅允许官方 `https://flyai.open.fliggy.com/mcp`、禁止重定向、最多一次 fetch、45 秒超时及 1 MiB 响应上限；父进程 55 秒超时。不启用 debug，不输出原始 stdout/stderr。
- 实测：fetch 1 次，HTTP 200，JSON 响应 12,501 bytes，CLI exit 0，业务 `status=0`，`data.itemList` 共 10 条；结论依据业务结果，不只依据 HTTP 或退出码。
- 10 条结果均有 `journeys` 和 `jumpUrl`；共 13 个分段，每段均含发到城市/站名/时间、时长、交通类型、车次、席别字段，所有分段出发日期均为 2026-11-01。字段存在性与日期检查不代表已核实其全部语义、时刻准确性或可购余量。
- 10 条结果的 `adultPrice` 均未提供，所检查的条目字段 `currency`、`priceUnit`、`priceBasis`、`remainingSeats` 均未出现；不能证明没有其他价格相关字段，更不能由此构造确定票价。顶层 `systemMessage` 未出现；10 个条目有 `jumpUrl`，未保存或打开链接。
- 原始响应只在内存中解析；仅持久化统计、字段存在性和测试范围，无 Key、原始结果、价格、车次或返回链接。单次成功不证明账户全部权限、剩余额度、用途核准、错误分支或正式服务端契约。

## v0.2 实施结果（2026-10-31）

用户批准“后端封装官方 CLI”后，独立 HTTP/SDK 缺口不再阻止本地实施。固定 CLI 1.0.16，采用官方命令和严格输出校验；没有自行实现提取的 MCP 协议。已增加纯文本提示、品牌来源和受控 HTTPS 详情链接展示，原规格的外部跳转冲突已解决。

[本地 API 真实验收](acceptance/flyai-train-api-smoke-2026-10-31.json)通过：10 条结果、13 个分段、全部金额 null；13 段有席别，没有链接通过本项目允许列表。前端以“票价未返回”展示缺价；详情链接和提示的安全展示另由合成数据测试验证。详细验证与范围见[验收记录](acceptance/transport.md)。首次独立 CLI 查询与新增 API 查询共各 1 次，均无重试；公开部署、确定报价及账户全部权限/配额仍未验收。
