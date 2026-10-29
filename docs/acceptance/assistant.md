# AI 助手验收记录

> 日期：2026-10-29（北京时间）
> 范围：`SPEC-assistant` v0.3、assistant 任务 AST-01 至 AST-12；仅离线流程验收，不代表真实模型或旅行事实准确性已经验证。

## 结论

**AI 旅行问答、条件建议、服务端 API、前端交互及本地自动化流程通过。** 默认未配置模型时返回 `unconfigured`，不会创建 provider 请求；对话仅保留在当前页面内存；候选条件 patch 只预览，不应用到行程。

真实 provider 尚未启用。E-007 的供应商权限、价格、数据处理条件、配额、结构化输出能力与回答质量均未核实；未配置真实 Key，也未发起真实模型请求。

## 实现范围

- `POST /api/assistant/chat` 使用严格的请求／响应合同、request ID 和公共错误；服务端 adapter 从 `APP_MODEL_BASE_URL`、`APP_MODEL_API_KEY`、`APP_MODEL_NAME`、`APP_MODEL_TIMEOUT_SECONDS` 读取配置。
- 上下文每轮默认关闭；历史、上下文、资料摘要均设有长度约束。模型重试一次用户操作总计最多 5 次（首次调用计入），429、其他不可重试错误和非法输出不会重试。
- 客户端提交的资料摘要与来源元数据均不可信。即使请求声称来源 `verified`，服务端仍将状态降为 `user_provided`；模型只接收摘要与来源名称，不接收来源 ID；响应不回传或展示客户端来源作为回答依据。
- 前端资料逐项显式选择并标注未核实；模型输出采用纯文本展示；候选 patch 仅展示字段差异。
- 测试使用 fake provider、HTTPX mock transport 和本地 Playwright route mocks；未新增依赖或持久化聊天。

## 验证结果

| 验证 | 结果 |
|---|---|
| `backend/` `uv run --offline pytest -q` | 245 passed；1 条既有 Starlette TestClient/httpx 弃用警告 |
| `backend/` `uv run --offline ruff check app tests` | 通过 |
| `frontend/` Vitest | 69 passed，11 个测试文件 |
| `frontend/` TypeScript `tsc --noEmit` | 通过 |
| `frontend/` ESLint | 通过 |
| `frontend/` Vite production build | 通过，Vite 8.3.5 |
| assistant Playwright | 10 passed：桌面 Chromium 与 Pixel 7 |
| 全量 Playwright | 34 passed：桌面 Chromium 与 Pixel 7 |
| OpenAPI 与 TS 类型生成 | 连续生成一致；OpenAPI SHA-256 `992C1051B64379C0C5E1A5C15773087E4CE45D16C0EF2D937228DEA0797578A3`；TS SHA-256 `DF96C8D7229440AF6E304F38500E11FE9461ED6E51411BD49F87269CE823771F` |
| Secretlint | `backend/app`、`frontend/src` 和 `frontend/dist` 扫描通过，无发现 |

## 验收映射与边界

| AC | 本模块证据 | 全局边界 |
|---|---|---|
| AC-13 | 候选条件 patch 有差异预览，不调用写 API、不应用到 itinerary；既有 itinerary 面板和导航保留 | 不表示 itinerary 写入／锁定、预订或业务校验全局验收完成 |
| AC-19 / AC-20 | 问答视图、默认未配置、上下文显式开启、资料显式选择、错误重试及桌面／移动流程通过 | 仅证明 mock/fake 流程；模型质量、实时数据和实际供应商覆盖未验证 |
| AC-36 | 本次服务端 assistant 源码、前端源码和构建产物 Secretlint 通过；无真实 Key；客户端来源 ID 不发给模型或响应 | 不代表 Git 历史、未来本机私密配置或供应商侧处理的全局审计 |
| E-007 | 保留 provider adapter；默认无配置 | 供应商资格、权限、价格、地区可用性、隐私条件、额度与质量待另行核实和批准 |

## 开发配置说明

开发者获批并完成 E-007 核验后，可在服务端 `backend/.env` 配置上述四个 `APP_MODEL_*` 环境变量；前端不配置、不接触 API Key。当前工作区保持这些值为空，启动后助手显示“尚未配置”，其余天气、预算、交通和行程模块仍可使用。不要把真实 Key 写入 `.env.example`、前端环境变量或版本库。

## 证据文件

- [SPEC-assistant](../SPEC-assistant.md)
- [实施计划](../../tasks/assistant/plan.md)
- [任务清单](../../tasks/assistant/todo.md)
