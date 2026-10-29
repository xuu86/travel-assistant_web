# assistant 实施计划

> 版本：v0.3｜状态：已批准｜批准日期：2026-10-29（北京时间）
> 对应规格：[SPEC-assistant](../../docs/SPEC-assistant.md) v0.3（已批准）。本计划已获批准；任务清单与实现仍须分别审批。

## 1. 目标与范围

在现有 React／FastAPI 工作区中交付 AI 旅行问答与条件建议流程：后端接收严格、最小化的对话上下文，经 provider adapter 生成回答和候选 patch；前端提供独立对话视图、每轮上下文开关、未核实资料提示和 patch 预览。默认无模型配置时明确显示 `unconfigured`；patch 不直接更改工作区。

首版遵循 SPEC-assistant v0.3：仅将用户主动选择的消息、显式开启时的白名单旅行上下文和用户明确选择的结构化资料发给模型；客户端来源元数据一律视为未核实，不作为实时事实认证；聊天仅存当前页面内存；一次用户操作总尝试最多 5 次，首次调用计入。模型 endpoint、Key、模型名全部只在服务端配置。

本计划不授权真实 provider 资格确认、密钥配置、真实外网请求或质量宣称。E-007 仍未通过核实；代码流程使用 fake provider 离线验证。默认运行配置不实例化 fake，也不自动回退到 fixture/demo。未来如需开展真实 provider Gate，需有单独的外部验证步骤和明确授权。

## 2. 冻结口径与实现决策

1. API：`POST /api/assistant/chat`，由 FastAPI + Pydantic 严格校验；请求 ID、公共错误、CORS 和日志规则复用 foundation。
2. provider 配置：扩展现有 Settings，新增 `model_base_url` 与 `model_timeout_seconds`，复用 `model_api_key`、`model_name`；对应环境变量为 `APP_MODEL_BASE_URL`、`APP_MODEL_API_KEY`、`APP_MODEL_NAME`、`APP_MODEL_TIMEOUT_SECONDS`。Base URL 必须由服务端配置，客户端不得传 URL。
3. provider adapter 使用项目已安装的 `httpx`，按 OpenAI-compatible Chat Completions 格式发送请求；无 Key／URL／模型名时不发请求并返回 `unconfigured`。构造客户端时注入 fake transport，自动化测试不访问外网。
4. 默认关闭“将当前行程条件用于本次回答”。开启时只发送 TripContext 白名单 DTO；evidence 默认不附加且需用户显式选用，但客户端来源状态不可作为可信验证。
5. 一次请求总尝试最多 5 次（首次调用计入）；仅网络错误、超时、502/503/504 可进行有限退避重试。429、其他 4xx、无效 JSON／schema 不重试。超时预算 30 秒，等待总时长需由测试界限量化。
6. 模型输出格式使用可解析 JSON；严格验证 reply 长度、patch 允许字段、字段类型和禁止额外字段。客户端 evidence/source 的 `verified` 状态不可信，服务端将其降级为 `user_provided`；不将客户端来源回传为回答依据。
7. 前端聊天消息只存在 React 当前视图状态中；切换目的地或返回城市选择时清空 assistant 状态，符合当前 workspace 重置约定。不加 IndexedDB、服务端会话存储或新增依赖。
8. 页面用纯文本／安全 Markdown 子集渲染模型回复，不允许 HTML。`candidate_patch` 仅作为字段级差异预览，不能更改 App 的 trip/workspace 状态。

## 3. 组件与依赖顺序

| 顺序 | 组件 | 主要责任 | 依赖 | 检查点 |
|---:|---|---|---|---|
| 0 | 实现基线复核 | 检查 Settings、共享契约、OpenAPI 导出、前端导航和现有测试命令 | foundation／transport 验收 | 确认不新增依赖；所有命令均指向现有脚本 |
| 1 | assistant 严格契约 | 消息、History、TripContext、AssistantEvidence、CandidatePatch、ChatResponse 和状态不变量 | foundation | 合法／非法 payload 测试先行通过 |
| 2 | provider 协议与 fake | 可注入 provider、合成成功和错误响应、无配置状态 | 1 | 默认无网络／fake；调用次数可断言 |
| 3 | service、HTTP provider 与设置 | 白名单组装、有限重试、JSON 解析、来源限制、错误归一化及服务端配置 | 1、2 | 所有失败状态、密钥和用户数据脱敏测试通过 |
| 4 | FastAPI router 与 API 测试 | 注册 `/api/assistant/chat`、request ID、validation/error 映射和 OpenAPI | 1–3 | API 安全集成测试与 schema 通过 |
| 5 | OpenAPI 与前端类型 | 导出 API schema 并生成 TS 类型 | 4 | 重复生成字节稳定，生成类型可消费 |
| 6 | 前端 API 与 AssistantPanel | 对话、上下文/evidence 显式选择、loading/error、未核实资料提示、候选 patch 预览 | 5 | 组件单测、键盘和移动断点检查通过 |
| 7 | App 导航与生命周期 | 增加 assistant 视图，切换／目的地变化清理，迟到响应保护 | 6 | 相邻 weather/budget/transport 不回归 |
| 8 | Playwright、回归与验收 | 桌面／Pixel 流程，隐私、无配置、错误、事实边界、patch 不应用 | 1–7 | 全量测试、OpenAPI 稳定性、密钥扫描、acceptance 记录完成 |

依赖图：`1 → 2 → 3 → 4 → 5 → 6 → 7 → 8`；组件 0 为进入实现前的环境检查。assistant router、main.py 和 OpenAPI 串行修改；provider 及 service 测试不可并行更改共享 Settings。UI 可在契约固定后开展，但集成导航依赖 UI 组件。

## 4. 预期文件范围

候选实现范围如下；Phase 3 任务清单会将每个任务约束为约 5 个文件以内，并列出明确验收和命令。

```text
backend/app/core/config.py
backend/app/modules/assistant/__init__.py
backend/app/modules/assistant/contracts.py
backend/app/modules/assistant/providers/__init__.py
backend/app/modules/assistant/providers/base.py
backend/app/modules/assistant/providers/openai_compatible.py
backend/app/modules/assistant/service.py
backend/app/modules/assistant/router.py
backend/app/main.py
backend/tests/unit/test_assistant_contracts.py
backend/tests/unit/test_assistant_provider.py
backend/tests/unit/test_assistant_service.py
backend/tests/integration/test_assistant_api.py
frontend/src/shared/openapi.json                         # generated
frontend/src/shared/api-contracts.ts                     # generated
frontend/src/features/assistant/api.ts
frontend/src/features/assistant/api.test.ts
frontend/src/features/assistant/AssistantPanel.tsx
frontend/src/features/assistant/assistant-panel.css
frontend/src/features/assistant/AssistantPanel.test.tsx
frontend/src/App.tsx
frontend/src/App.test.tsx
frontend/e2e/assistant.spec.ts
docs/acceptance/assistant.md
```

不添加 SDK、Markdown 渲染器、数据库、缓存、模型客户端第三方库或真实 Key。若验证发现必须加依赖，暂停并单独说明用途、体积、维护状态和替代方案，等待批准。

## 5. 验证门

### Gate A：严格契约与数据最小化

用 Pydantic 契约测试覆盖空／超长消息、控制字符、history 条数和总字数、默认无 context/evidence、context 显式启用、非白名单字段、禁止 patch 字段、金额整数分、日期格式和额外字段拒绝。捕获 fake provider payload，断言仅发送当前消息、限制内 history、可选 TripContext/evidence 和系统提示。

### Gate B：provider 与 service 离线状态

用注入 transport 测试成功 JSON、code fence／额外文本、非法 JSON、无效结构、越权 patch、超时、网络错误、429、4xx、502/503/504 和重试耗尽。断言总尝试上限为 5、仅批准状态重试、429 不重试、provider 原文／Key 不进入公共错误或日志；客户端 evidence 来源状态降级、source ID 不进入模型消息且响应不认证客户端来源。生产默认未配置时调用计数必须为零。

### Gate C：API、安全与 OpenAPI

测试 `/api/assistant/chat` 的 200 状态 envelope、422 字段校验、安全公共错误、request ID 与 header 一致、CORS 边界、请求正文和 response sentinel 不进入日志；OpenAPI 只含 schema 和空配置示例，无真实 URL、Key、prompt 或用户内容。重复导出 schema 稳定。

### Gate D：前端交互与状态不变性

验证默认未配置时聊天输入和原有表单仍可用；上下文开关每轮默认关闭且关闭时 payload 不含工作区信息；evidence 逐项显式选择且标注未核实；响应不认证客户端来源；patch 仅显示差异、工作区值不变；发送中禁用重复提交并可取消本地等待；修改输入／切换视图后旧结果不能覆盖当前会话；恶意链接／HTML 不执行。

### Gate E：E2E、隐私和回归

Playwright 只 mock 本地 assistant API。桌面与 Pixel 7 覆盖未配置、live fake 回答、无证据实时事实追问、带 evidence 来源显示、context 默认关闭、候选 patch 不应用、429／故障、重试状态、切目的地清空和窄屏无溢出。之后执行后端／前端全量回归、OpenAPI/types 重复生成、Secretlint 和已有 E2E。

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 用户隐私上下文被默认上传 | 用户未意识到旅行条件进入第三方服务 | 每轮显式开启；默认 false；捕获请求的隐私断言 |
| 模型伪造实时旅行事实 | 用户按错误天气／票价行动 | 客户端摘要一律视为未核实资料，不认证其来源；模型不能自造 sources |
| Prompt injection 或额外 patch 字段 | 越权变更或泄露系统信息 | 服务器端固定指令、严格输出模型、字段 allowlist；不依赖提示词作为唯一安全控制 |
| API Key 泄露至浏览器或日志 | 凭证滥用 | 服务端 SecretStr、窄日志 schema、secret scanning 与 sentinel 测试 |
| 超时重试导致延迟／额度消耗 | 影响免费额度和交互体验 | 最多 5 次总尝试、仅重试网络及特定 5xx、总超时预算测试 |
| 实际 provider 资格尚未核实 | 误把接口可调用说成可用／合规 | E-007 通过前不配置真实凭证、不做真实请求、不宣称已接入 |
| 后续 itinerary patch 契约不兼容 | 候选字段错误或 UI 预览失真 | 首版候选 patch 只限偏好 DTO；itinerary 落地前复核字段与版本，不提交写操作 |

## 7. 计划完成定义

本计划后续任务完成后必须同时具备：

1. Strict DTO、模型白名单组包、patch 整体校验及 fake provider 离线覆盖；
2. 默认无配置时无任何上游请求，失败状态、request ID、重试边界及脱敏符合规格；
3. FastAPI schema 和前端生成类型一致，重复生成稳定；
4. 前端问答、每轮上下文显式开关、未核实资料提示、差异预览、错误/取消/并发状态及响应式体验通过；
5. patch 预览绝不改变当前 workspace；聊天不进 IndexedDB 或服务端；
6. 后端、前端、E2E、构建、Lint、类型和密钥扫描通过，完成 `docs/acceptance/assistant.md`；
7. E-007 的 provider 权限／质量状态单独报告为未验证或按后续独立证据更新，不和流程测试混为一谈。

## 8. 本阶段边界

本计划获批后，下一阶段仅生成 `tasks/assistant/todo.md`：逐项列出红绿测试顺序、精确文件、验收与命令。未另行批准任务清单及编码授权前，不修改应用代码、不运行真实模型请求、不配置 Key、不提交或推送。

## 9. 审批记录

- 审阅人／日期：用户／2026-10-29（北京时间）
- 结论：批准
- 修改摘要：确认实施计划；模型调用总尝试最多 5 次且首次计入。后续仅进入任务清单阶段。
