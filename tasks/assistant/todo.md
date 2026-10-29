# assistant 任务清单

> 版本：v0.2｜状态：实施中｜批准日期：2026-10-29（北京时间）
> 对应已批准文件：[SPEC-assistant](../../docs/SPEC-assistant.md) v0.3、[assistant 实施计划](plan.md) v0.3。本清单获批并授权开始实现。

## 通用执行规则

- 每项任务先新增或扩充失败测试，再实现最小变更；任务通过后才进入下一项。不得将后续任务的代码提前混入。
- 后端在 `backend/` 使用 `uv run --offline pytest ...` 与 `uv run --offline ruff check ...`；前端在 `frontend/` 使用现有 `npm.cmd` 脚本。自动化测试禁网；真实模型调用、真实 Key 与供应商资格验证均不属于本清单授权。
- 默认 Settings 无模型 endpoint／Key／model 时，assistant 返回 `unconfigured` 且 provider 调用次数为零；fake 只通过测试依赖注入，绝不注册为默认 provider 或作为错误回退。
- 严格遵守白名单和数据最小化：默认不附加 trip context；只有当前轮显式选择才发送允许字段；原件、OCR、凭证、用户身份信息、请求正文和模型原文不进日志。客户端 evidence/source 状态不可信，一律降级为 `user_provided`，不回传来源认证。
- 一次用户操作最多 **5 次总尝试（首次调用计入）**；仅网络错误、超时、502/503/504 可重试。429、其他 4xx、非法 JSON／schema 不重试。测试须逐类断言上游调用次数和总尝试上限。
- 不新增依赖、数据库、持久化聊天、实时工具调用、自动应用 patch 或付费 fallback。模型输出只生成候选差异，不能改变当前 itinerary／workspace。
- 工作区现有 `frontend/src/App.tsx` 含有未提交的 itinerary 视图接入；实施时须以当前文件为基线，只增量接入 assistant，不覆盖或重置已有 itinerary 改动。

## 任务（依赖顺序）

### AST-01 — 定义严格 assistant 契约

- [x] **验收：** 新增 ChatMessage、ChatRequest、TripContext、AssistantEvidence、CandidatePatch、ChatResponse 等 Pydantic 契约；限制 message/history/context/evidence 大小，拒绝额外字段、空白文本、非法 role、任意 URL、来源伪造字段和越权 patch 键。金额仍为整数分；输出状态、request ID 与 foundation 公共状态一致。
- [x] **验证：** `uv run --offline pytest -q tests/unit/test_assistant_contracts.py`（13 passed）；`uv run --offline ruff check app/modules/assistant tests/unit/test_assistant_contracts.py` 通过。契约测试先因 assistant 模块缺失而失败，再实现通过。
- [x] **文件：** `app/modules/assistant/__init__.py`、`app/modules/assistant/contracts.py`、`tests/unit/test_assistant_contracts.py`（3 个）。
- **依赖：** 已验收 foundation。

### AST-02 — 建立 provider 协议与 fake transport 测试替身

- [x] **验收：** 定义异步 provider 协议和可注入 fake；支持合法 JSON、无效 JSON、HTTP 429/4xx/5xx、timeout、网络异常；fixture 不含真实用户信息；provider 原始错误内容不得进入公共结果或日志；生产默认不创建 fake。
- [x] **验证：** `uv run --offline pytest -q tests/unit/test_assistant_provider.py`（6 passed）；`uv run --offline ruff check app/modules/assistant/providers tests/unit/test_assistant_provider.py` 通过。验证了 fake 调用计数、错误注入和无网络实现。
- [x] **文件：** `app/modules/assistant/providers/__init__.py`、`app/modules/assistant/providers/base.py`、`app/modules/assistant/providers/fake.py`、`tests/unit/test_assistant_provider.py`（4 个）。
- **依赖：** AST-01。

### AST-03 — 扩展服务端模型配置及安全校验

- [x] **验收：** Settings 增加 APP_MODEL_BASE_URL 与 APP_MODEL_TIMEOUT_SECONDS，复用 SecretStr API Key 和 model name；只有 endpoint、Key、模型名均有效才视为已配置；endpoint 仅来自服务端环境，不接收客户端传入值。无配置对象不泄露 SecretStr，timeout 有界且校验正数。
- [x] **验证：** `uv run --offline pytest -q tests/unit/test_config.py tests/unit/test_assistant_config.py`（24 passed）；`uv run --offline ruff check app/core/config.py tests/unit/test_config.py tests/unit/test_assistant_config.py` 通过；foundation config 回归通过。
- [x] **文件：** `app/core/config.py`、`backend/.env.example`、`tests/unit/test_config.py`、`tests/unit/test_assistant_config.py`（4 个）。
- **依赖：** AST-01。不得重写既有 config 用户改动；如工作区出现相关改动，先阅读并增量合并。

### AST-04 — 实现 OpenAI-compatible HTTP provider

- [x] **验收：** 使用已有 httpx 实现服务端 Chat Completions 请求映射；system instruction、用户消息和白名单 context/evidence 有固定组装顺序；无配置时无 HTTP 请求；认证头只含服务端 Key；限制响应大小并将上游状态安全映射。adapter 默认不构造真实外网客户端供测试使用，HTTPX MockTransport 可离线注入。
- [x] **验证：** `uv run --offline pytest -q tests/unit/test_assistant_provider.py`（12 passed）；`uv run --offline ruff check app/modules/assistant/providers tests/unit/test_assistant_provider.py` 通过；sentinel Key 和 provider 私有错误文本未进入 exception。
- [x] **文件：** `app/modules/assistant/providers/openai_compatible.py`、`app/modules/assistant/providers/base.py`、`tests/unit/test_assistant_provider.py`（3 个既有／新增文件）。
- **依赖：** AST-02、AST-03。

### AST-05 — 实现 assistant service、数据最小化与重试策略

- [x] **验收：** service 只把用户当前 message、限制内 history、可选 context 和显式选择的 evidence 摘要发给 provider；默认关闭 context；客户端 evidence/source 均按未核实用户资料处理，来源 ID 不发送、来源不回传。最多 5 次总尝试（含首次），仅网络／超时／502/503/504 可重试；429、其他 4xx、非法 JSON、超长响应或 schema 错误均不重试并拒绝整个输出。patch 只含允许字段；日志不记录任何输入／输出正文。
- [x] **验证：** assistant service/provider 测试通过；连续 retryable failure 恰好调用 5 次；429／不可重试状态及非法输出只调用一次；覆盖客户端伪造 `verified` 被降级为 `user_provided`、来源 ID 不发模型及 sources 为空。HTTP 集成测试确认 JSON 时间戳／枚举可解析并执行降级；后端全量 `pytest` 245 passed；全量 Ruff 通过。
- [x] **文件：** `app/modules/assistant/service.py`、`app/modules/assistant/providers/base.py`、`tests/unit/test_assistant_service.py`、`tests/unit/test_assistant_provider.py`（4 个）。
- **依赖：** AST-01、AST-04。

### AST-06 — 注册 API 并验证错误／隐私边界

- [x] **验收：** 新增 `POST /api/assistant/chat`，沿用公共错误处理、CORS、request ID；注入 service/provider，不在 router 直接调用上游；默认未配置返回无内容的 `unconfigured`，无 network call；422 不触发 provider；响应不得带 provider 原始 body、Key 或堆栈；日志只保留批准字段。
- [x] **验证：** `uv run --offline pytest -q tests/integration/test_assistant_api.py`（6 passed）；`uv run --offline ruff check app/modules/assistant app/main.py tests/integration/test_assistant_api.py` 通过。覆盖 fake、未配置、422、request ID、CORS、payload sentinel 脱敏。
- [x] **文件：** `app/modules/assistant/router.py`、`app/main.py`、`tests/integration/test_assistant_api.py`（3 个）。
- **依赖：** AST-05。

### AST-07 — 导出 OpenAPI 并生成 TypeScript 类型

- [x] **验收：** OpenAPI 纳入 assistant 请求、响应、CandidatePatch、来源及状态 schema；从 schema 生成 TS types，不手写重复镜像；重复导出与生成字节稳定。
- [x] **验证：** 后端 OpenAPI 导出通过；前端使用项目 Node 24.22.1 bundled executable 调用 openapi-typescript 与 tsc（主机未暴露 npm.cmd），类型生成和 typecheck 通过。
- [x] **文件：** `frontend/src/shared/openapi.json`、`frontend/src/shared/api-contracts.ts`（2 个生成文件）。
- **依赖：** AST-06。

### AST-08 — 实现 assistant API client

- [x] **验收：** 同源 POST `/api/assistant/chat`；使用生成类型；安全解析 response、公共错误与 request ID；传入 AbortSignal 支持浏览器取消；不记录 payload，不提供任意 endpoint；坏 JSON／坏 schema 转换为安全 client error。
- [x] **验证：** assistant/App 前端单测、TypeScript 检查和全量 ESLint 通过。
- [x] **文件：** `src/features/assistant/api.ts`、`src/features/assistant/api.test.ts`（2 个）。
- **依赖：** AST-07。

### AST-09 — 构建问答面板与安全状态展示

- [x] **验收：** 提供对话、输入／发送、加载、失败与重试、未配置、每轮 context 开关和 evidence 显式勾选、candidate patch 差异预览；客户端来源标注为用户提供且未核实，响应不展示/认证客户端来源。patch 不调用写 API、不修改父级状态；模型回复按纯文本显示；键盘可达、语义状态、窄屏无溢出。
- [x] **验证：** assistant/App 单测通过；context 默认关闭、资料显式选择并降级状态、patch 不应用、失败重试、恶意 HTML 文本转义均有测试；typecheck、全量 lint、桌面与手机 E2E 通过。
- [x] **文件：** `src/features/assistant/AssistantPanel.tsx`、`src/features/assistant/assistant-panel.css`、`src/features/assistant/AssistantPanel.test.tsx`（3 个）。
- **依赖：** AST-08。

### AST-10 — 接入 App 工作区导航与生命周期

- [x] **验收：** assistant 导航接入并保留既有 itinerary；已查询天气可显式选为未核实背景；context 默认关闭且只发送白名单；目的地变化清空对话并中止本地等待；旧模块流程通过全量回归。
- [x] **验证：** App 与 assistant 测试、typecheck、全量 lint、build、34 项桌面／手机 E2E 通过；destination-workspace 测试选择器收窄为预算专用元素以兼容保留的 itinerary 面板。
- [x] **文件：** `src/App.tsx`、`src/App.test.tsx`、`src/features/assistant/AssistantPanel.tsx` 及已有 itinerary 相关工作区文件。
- **依赖：** AST-09。

### AST-11 — Playwright 桌面／手机 assistant 流程

- [x] **验收：** 桌面 Chromium 与 Pixel 7 覆盖未配置、回答、显式 context/evidence、未核实资料提示、patch 预览、429／故障重试、目的地清理和无水平溢出；Playwright 只 mock 本地 API。
- [x] **验证：** assistant E2E 10 项通过；全量 Playwright 34 项通过，不连接真实 provider。
- [x] **文件：** `frontend/e2e/assistant.spec.ts`、`frontend/e2e/destination-workspace.spec.ts`（收窄原有歧义选择器）。
- **依赖：** AST-10。

### AST-12 — 全量回归、扫描与验收留证

- [x] **验收：** 新增验收记录；区分离线流程通过、默认未配置、E-007 provider 权限／价格／质量未核实；记录 AC-13、AC-19、AC-20、AC-36 相关子项与证据缺口，不宣称真实模型可用或旅行事实准确。
- [x] **验证：** 后端 244 passed + Ruff；前端 69 passed + TypeScript + ESLint + build；Playwright 34 passed；OpenAPI/types 连续生成哈希稳定；Secretlint 源码与 dist 扫描通过。
- [x] **文件：** `docs/acceptance/assistant.md`。
- **依赖：** AST-01 至 AST-11。

## 阶段边界

- **允许（清单另行批准后）：** 严格契约、fake-only 自动化、无配置真实界面、离线测试、前端候选 patch 预览、配置项模板名和文档记录。
- **需另行批准：** 提交任务清单后开始编码、真实 Key／模型调用、E-007 provider 资格核实、模型产生新付费、自动工具调用、patch 自动应用、聊天持久化、上传或 OCR 输入。
- **禁止：** 将 Key 放浏览器或仓库、把原始文件／OCR 发给模型、把 fake 当 live、静默切换收费模型、服务端保存聊天正文、模型直接写当前行程／预算／锁定预订、覆盖或撤销工作区中既有 itinerary 改动。

## 审批记录

- 审阅人／日期：用户／2026-10-29（北京时间）
- 结论：批准并授权开始编码
- 修改摘要：按任务清单 v0.1 实施；单次用户操作最多 5 次总尝试（首次计入）；保留工作区既有 itinerary 改动；不调用真实模型、不配置 Key。

## 执行记录

- 2026-10-29：任务清单获批并授权编码；按 AST-01 开始契约测试先行。
- 2026-10-29：AST-01/02 完成；19 项契约与 fake provider 单测通过，Ruff 通过。未配置真实 provider、Key 或网络。
- 2026-10-29：AST-03/04 完成；24 项模型配置与现有 config 回归通过，12 项 HTTP provider MockTransport 单测通过；补充了 `.env.example` 空配置项，无真实请求。
- 2026-10-29：AST-05/06 完成；重试／白名单 service、API status、request ID、CORS 和日志脱敏通过；assistant 全部后端测试 68 passed，Ruff 通过（有既有 Starlette/httpx 弃用警告）。
- 2026-10-29：AST-07 完成；OpenAPI 导出、TypeScript 类型生成与类型检查通过。前端环境没有 npm.cmd，改用 bundled Node executable 直接运行已安装的工具。
- 2026-10-29：AST-08 至 AST-12 完成；前端 69 项单测、后端全量 245 项测试、全量 ESLint/Ruff、build、Playwright 34 项及 Secretlint 均通过。OpenAPI SHA-256=`992C1051B64379C0C5E1A5C15773087E4CE45D16C0EF2D937228DEA0797578A3`；TS SHA-256=`DF96C8D7229440AF6E304F38500E11FE9461ED6E51411BD49F87269CE823771F`，重复生成一致。客户端 evidence 来源的 `verified` 状态会被服务端降级为 `user_provided`，来源 ID 不发模型，响应 sources 为空；未配置真实 provider 或调用真实模型。
