# SPEC-assistant：AI 旅行问答与条件建议

> 版本：v0.3｜状态：已批准｜批准日期：2026-10-29（北京时间）
> 本文对应已批准 Capability Map 中的 `assistant` 模块；规格批准不等于计划、任务清单或实现获批。

## 1. 元数据

- **模块 ID：** `assistant`
- **负责人角色：** 开发负责人
- **关联决策：** D-011、D-012、D-017、D-019；关联待办 Q-004、E-007
- **关联验收：** AC-13、AC-19、AC-20；问答体验新增模块内验收项
- **依赖模块：** `foundation`
- **被依赖模块：** `itinerary`（后续由其校验并应用已确认的 ChangeSet）

## 2. Objective 与范围

### 目标

在旅行工作区提供一个自然语言助手，让用户可以提出旅行规划问题、补充偏好并请求修改建议。模型输出必须可校验、可追溯；它只能生成回答和候选条件变更，不能直接修改行程、费用或已锁定预订。

### 首版包含

- 在目的地工作区增加独立“AI 助手”视图，支持发送文本问题、显示多轮对话、加载中、错误和未配置状态。
- 后端使用模块化模型 provider；默认无有效模型配置时明确返回 `unconfigured`，不显示伪造回答。
- 让模型回答一般旅行规划问题；对天气、班次、票价、酒店余房、活动、开放时间等实时／外部事实，不得臆测。若本次请求没有经过批准的对应模块结果，应明确提示需查询相应模块。
- 可把用户明确提出的旅行偏好解析为候选 `TripPatch`，在 UI 中逐项展示变更前后；本规格不允许直接应用。只有后续 `itinerary` 模块校验且用户确认后才能提交。
- 所有模型输入采用白名单 DTO；请求中不得包含原始上传文件／OCR 全文、凭证、账号密码、无关身份信息、服务端密钥或日志内容。
- 记录 provider 状态、request ID、模型标识和必要的脱敏诊断信息，不保存聊天正文或模型请求全文。

### 首版不包含

- 自动执行查询、预订、支付、浏览网页或调用任意工具。
- 直接创建／修改／删除已保存行程；不绕过 `itinerary` 的版本校验、用户确认、费用校验及已锁定预订保护。
- 上传文件、从原件抽取上下文、长期保存聊天记录、跨设备同步或训练模型。
- 流式生成、语音输入、图片理解、多模态输入、Markdown 原始 HTML 渲染。
- 自动切换到其他或可能收费的模型；真实模型质量、额度、账号权限和服务政策在 E-007 通过前均视为未验证。

## 3. 输入输出契约

### 输入

| 字段 | 类型 | 必填 | 空值语义 | 校验 | 来源／权限 |
|---|---|---:|---|---|---|
| `message` | string | 是 | 不允许空白 | 去除首尾空白；建议上限 2,000 字符；拒绝控制字符 | 当前用户主动输入 |
| `history` | 有序消息数组 | 否 | 空数组表示新会话 | 每条仅含 `role`、`content`；限制条数和累计字符数；只接受 user/assistant | 当前页面内存；刷新或离开即丢失 |
| `trip_context` | 白名单旅行上下文 | 否 | `null` 表示不提供当前条件 | 仅包含经过用户确认且本轮回答需要的目的地、日期、人数、预算、兴趣、节奏、交通偏好；金额为整数分 | 仅当前轮用户显式开启上下文后由页面工作区构造 |
| `evidence` | 可选的用户选择资料摘要 | 否 | 空数组表示没有可参考资料 | 严格限制体积；客户端提交的摘要与来源元数据一律视为未核实，不可用于认证实时事实 |

### 输出

| 字段 | 类型 | 可空 | 语义 | 来源／时间 | 是否持久化 |
|---|---|---:|---|---|---:|
| `state` | enum | 否 | `live`、`unconfigured`、`rate_limited`、`unavailable`、`policy_unavailable` | provider adapter；当前调用的 UTC 时间和 request ID | 否 |
| `reply` | string | 可在失败状态为空 | 普通文本回答；需安全转义，不把模型输出作为 HTML 执行 | 配置模型的当前响应 | 否 |
| `candidate_patch` | 严格白名单对象 | 是 | 建议的旅行条件变更；不代表已应用 | 模型输出经 Pydantic 校验和业务规则检查后产生 | 否 |
| `sources` | `SourceRef[]` | 是 | 首版固定为空；客户端提交的来源不能作为服务端认证的回答依据 | 服务端不回传客户端来源 | 否 |
| `request_id` | UUID | 否 | 与公共错误／脱敏日志关联 | foundation request middleware | 仅日志保留 ID |
| `message` | string | 否 | 安全、用户可读的状态说明 | 服务端固定文案 | 否 |

`candidate_patch` 首版字段仅包括可编辑的旅行偏好，不包含来源事实、报价、锁定状态、预订、日程条目或任意对象路径。字段清单须与后续 `itinerary` 的 ChangeSet 契约对齐；在该契约存在前，patch 只预览，不应用。

## 4. 状态与错误

| 状态／错误码 | 触发条件 | 用户提示 | 可重试 | 是否返回回答／候选 |
|---|---|---|---:|---:|
| `live` | provider 成功且模型输出通过完整校验 | 正常展示回答；候选变更明确标为待确认 | 用户可继续提问 | 是 |
| `unconfigured` | 模型 endpoint、Key 或模型名缺失／未启用 | 助手尚未配置；说明手动规划入口仍可使用 | 配置后 | 否 |
| `rate_limited` | 上游或本地额度限制 | 当前查询受额度限制；不自动购买或切换 | 由用户稍后重试 | 否 |
| `policy_unavailable` | 模型权限或服务政策阻止调用 | 模型服务暂不可用；不泄露上游细节 | 权限修复后 | 否 |
| `unavailable` | 超时、网络、上游故障、无效 JSON、越权字段或输出不合契约 | 回复未能生成，保留页面现有条件和聊天输入 | 用户触发的有限重试 | 否；拒绝整份无效输出，不部分采纳 patch |
| `VALIDATION_ERROR` | 请求字段、history 或 payload 超限 | 指出可修正的输入问题；无模型调用 | 修正后 | 否 |
| `INTERNAL_ERROR` | 未预期内部异常 | 通用提示及 request ID | 视情况 | 否 |

一次用户操作最多 5 次总尝试（首次调用计入 5 次）；仅网络错误、超时、502/503/504 可按有限退避重试。429、其他 4xx、无效输出不自动重试。此口径用于 assistant；其他模块仍各自定义重试策略。

## 5. 权限、隐私与数据保留

- 请求者身份及 owner scope 由 `auth` 负责；在 auth 未实现前，不持久化聊天／旅行数据，不以客户端传入身份字段授权。
- 默认不保存对话；刷新页面后客户端内存中的聊天清空。具体是否加入会话导出／历史记录不在首版范围。
- 云端模型请求只发送用户主动输入、经用户确认的最少必要上下文，以及用户显式选择的最少必要结构化资料。该资料和来源名均为客户端数据，服务端未核实，模型只能将其作为待核实背景；原件、原图、OCR 全文和未确认导入候选永不发送，遵循 D-019。
- 当前旅行上下文默认不自动附带；UI 提供“将当前行程条件用于本次回答”的显式开关，且每轮默认关闭。只发送当前已确认的白名单字段。
- 服务端模型密钥只从 `APP_*` 私密配置读取；任何 API、异常、日志和 OpenAPI 示例不得回传密钥、endpoint 凭证或原始 provider 响应。
- 日志只记录 request ID、模块、状态、模型 ID、耗时、尝试次数和脱敏错误码；不记录 message、history、trip_context、evidence 或模型原文。
- UI 把回答作为纯文本或安全 Markdown 子集渲染，禁止原始 HTML 和可执行 URL；模型输出始终视为不可信内容。
- 用户取消／离开视图时中止尚未发送的浏览器请求；已发送 provider 请求可能无法撤回，不承诺取消远端推理。

## 6. 业务规则与不变量

1. 模型是建议器，不是业务事实源；客户端提交的摘要／来源状态不能证明真实性，实时事实须由服务端可信模块重新核验后才可认证。
2. 模型不能改变 provider 状态、source、证据状态、金额单位、已支付金额或预算计算结果。
3. patch 必须通过严格 schema 与现有业务校验；未知键、额外字段、非法日期／枚举、越权字段使整个 patch 被拒绝。
4. AI 不可解锁、删除或编辑已锁定的用户核对预订；后续 itinerary 必须再次校验 D-017，不能信任模型声明。
5. 返回候选 patch 不会改变工作区；未来写操作必须有清晰的预览、差异展示、用户确认和并发版本检查。
6. 用户问题包含 prompt injection 或要求编造事实时，模型仍受服务端系统规则约束；即使模型违规，契约和业务校验也不得采纳越权输出。
7. 上下文达到限制时明确拒绝或截断旧 history，并告知用户；不得静默丢掉最新消息或超限发送。
8. provider 失败、输出解析失败或重试耗尽时不改变当前页面任何条件，不把旧回答伪装成本次新回答。

## 7. 依赖与配置

- **内部依赖：** `foundation` 的 Settings、公共状态／错误、request ID、来源与安全日志约定。
- **后续接口：** `itinerary` 提供可编辑条件白名单、ChangeSet 校验与 apply API；assistant 不直接依赖其存储层。
- **外部 provider：** 使用明确配置的 OpenAI-compatible Chat Completions endpoint；不能接受用户提供的 endpoint，避免 SSRF。GLM-4.7-Flash 是历史候选，但 E-007 的权限、价格、JSON 输出、限流及质量均未实测，不能据此启用或宣称已接入。
- **配置项：** `APP_MODEL_BASE_URL`、`APP_MODEL_API_KEY`（SecretStr）、`APP_MODEL_NAME`、`APP_MODEL_TIMEOUT_SECONDS`；值只存本机 `.env`，不得提交真实值。
- **超时／重试：** 单次 provider 请求 timeout 上限 30 秒；一次用户操作的总尝试数最多 5（首次计入）；不自动 fallback 到收费模型。
- **测试替身：** 注入 fake provider 与固定时间；测试均离线，不要求真实 Key 或访问外网。

## 8. 项目结构与代码风格

```text
backend/app/modules/assistant/
  contracts.py             # ChatRequest, ChatMessage, TripContext, CandidatePatch
  providers/base.py        # Provider protocol 与规范化错误
  providers/openai_compatible.py
  service.py               # 数据白名单、输出解析、patch 校验和状态映射
  router.py                # POST /api/assistant/chat
backend/tests/unit/test_assistant_contracts.py
backend/tests/unit/test_assistant_service.py
backend/tests/integration/test_assistant_api.py
frontend/src/features/assistant/
  api.ts
  AssistantPanel.tsx
  assistant-panel.css
```

Python 使用类型注解与 Pydantic 严格模型；router 只做 API 边界，不直连供应商；provider 负责 HTTP 与状态映射；service 做输入白名单、响应解析和业务校验。前端沿用当前模块 API client、React 状态组件与生成的 OpenAPI TypeScript types。示例（字段草案，最终字段要与 itinerary 契约一致）：

```python
class ChatRequest(ContractModel):
    message: str = Field(min_length=1, max_length=2_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    trip_context: TripContext | None = None
    evidence: list[AssistantEvidence] = Field(default_factory=list, max_length=20)
```

## 9. 命令

批准实现后，在 `AI WEB网页开发挑战赛/智能旅游助手/backend` 执行：

```powershell
uv run --offline pytest -q tests/unit/test_assistant_contracts.py tests/unit/test_assistant_service.py
uv run --offline pytest -q tests/integration/test_assistant_api.py
uv run --offline ruff check .
```

前端在 `AI WEB网页开发挑战赛/智能旅游助手/frontend` 执行：

```powershell
npm.cmd run test:unit -- --run
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e
```

以上是基于现有脚本的建议命令，规格阶段未执行命令。

## 10. 测试案例与验收

| 场景 | 输入／前置 | 预期 | 测试层级 | 证据 |
|---|---|---|---|---|
| 普通问答 | fake provider 返回符合契约的文本 | 展示回答，无自动改写工作区 | service + UI | 单测与组件截图 |
| 未配置 | provider 缺少必要配置 | `unconfigured`，无上游 HTTP 请求，表单规划仍可用 | API + UI | 请求计数与截图 |
| 事实边界 | 问实时天气／票价，未提供对应 evidence | 明确说明需查询来源模块，不编造数值／链接 | service fixture + E2E | fixture、截图 |
| 有资料问答 | 用户显式选择带来源和时间的摘要 | 明确作为未核实背景处理；sources 响应为空，不认证客户端来源 | service + UI | 请求／响应 fixture |
| 候选变更 | 请求改预算／偏好 | 返回可预览 patch；尚未确认时 App 状态不变 | unit + E2E | 前后状态断言、截图 |
| 越权 patch | 模型返回金额事实、锁定字段、任意 key 或非法日期 | 整体拒绝，状态为不可用；无部分采纳 | unit + API | 响应与字段断言 |
| provider 故障 | timeout、429、5xx、非法 JSON、超时重试耗尽 | 状态映射正确、次数有界、无收费 fallback、旧状态保留 | fake provider + API + UI | 调用计数、状态断言 |
| 隐私边界 | 捕获出站模型请求及日志 | 仅含白名单必要数据；无文件、OCR、密钥、原文日志 | integration | 脱敏请求／日志快照 |
| prompt injection | history/message 指示绕过规则或输出伪造事实 | 不泄密；无效或越权 patch 不生效 | service/API | 恶意 fixture 与断言 |
| 响应式交互 | 桌面和手机浏览器 | 键盘可发送、焦点与错误可读、窄屏不溢出，加载／失败状态清晰 | Playwright E2E | 桌面和 Pixel 截图 |

**通过门槛：** 所有离线单测、API 集成、前端组件和适用 E2E 通过；请求／日志数据边界测试通过；OpenAPI 与 TS types 生成稳定。只有 E-007 的真实权限、价格、额度和固定评测集实际验证后，才能单独宣称具体 provider 可用。模块流程通过不代表旅游事实正确，也不代表模型真实服务已配置。

## 11. 风险、开放问题与批准记录

| 问题 | 影响 | 建议／缓解 | 需要决定 | 状态 |
|---|---|---|---|---|
| “问答”是否同时包含自然语言修改建议 | 影响 assistant 与 itinerary 接口、UI 复杂度 | 首版包含候选条件 patch，但绝不自动应用 | 项目负责人 | 已批准（2026-10-29） |
| 是否默认将当前旅行条件发往云端模型 | 影响隐私和答案相关性 | 默认关闭，每轮由用户显式打开；只发送白名单字段 | 项目负责人 | 已批准（2026-10-29） |
| 模型能否消费现有查询模块结果回答实时事实 | 影响真实问答能力和来源追溯 | 客户端传入的结构化摘要仅作未核实背景，不认证其来源；实时事实须服务端可信来源校验 | 项目负责人 | 已批准（2026-10-29） |
| provider 模型具体选型／商业资格 | 影响预算、接入、地区可用性和数据策略 | 保持适配层；按 E-007 重新核实并固定评测后再启用 | 项目负责人 | 待核实 |
| Q-004 模型最多重试 5 次的口径 | 影响时延、上游费用和额度 | assistant 一次用户操作最多 5 次总尝试（首次调用计入）；不可重试错误不重复调用，不自动计费切换 | 项目负责人 | 本模块已确认（2026-10-29） |
| 聊天历史保留 | 影响本地存储和隐私 | 首版只保留在当前页面内存，不进 IndexedDB／服务端 | 项目负责人 | 已批准（2026-10-29） |

批准记录：

- 审阅人／日期：用户／2026-10-29（北京时间）
- 结论：批准
- 修改摘要：批准首版问答与候选条件建议、每轮显式上下文开关、内存态聊天及 5 次总尝试（首次计入）。实施核查补充客户端资料与来源均未核实，不认证来源；E-007 仍须核实。

## 12. 三层边界

- **Always：** 使用服务端 provider adapter；输入输出严格校验；只传白名单最小必要数据；客户端来源元数据不认证为事实来源；patch 仅候选、需用户确认及 itinerary 二次校验；不配置或失败时诚实显示状态；离线 fake 覆盖错误路径。
- **Ask first：** 更改隐私传输范围、持久化聊天记录、增添模型供应商／付费来源、启用自动工具调用、自动应用 patch、增加新依赖或启用流式／多模态能力。
- **Never：** 将 Key 放到浏览器；把用户文件／OCR 原文发给云端；模型直接写行程／存储；伪造实时旅行事实或来源；失败时展示演示回答；绕过锁定预订、预算和用户确认规则。
