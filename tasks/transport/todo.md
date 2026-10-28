# transport 任务清单

> 版本：v0.1｜状态：已完成（fake-only 流程范围）｜批准日期：2026-10-28（北京时间）  
> 对应已批准文件：[SPEC-transport](../../docs/SPEC-transport.md) v0.2、[transport 实施计划](plan.md)。本清单只覆盖 `transport`；批准本清单后仍需用户明确授权开始实现。

## 通用执行规则

- 后端使用项目已锁定的 Python 3.14.10、`uv`、pytest、Ruff；前端使用 Node 24.22.1/npm 11.19.1、React、TypeScript、Vite、Vitest、Playwright、ESLint 和 Secretlint。不得因本模块新增依赖、SDK、数据库、缓存服务器或地图服务。
- 后端自动化测试默认禁网；fake provider 只通过测试依赖注入使用。生产默认 provider 为空，必须返回 `unconfigured` 空列表，不得静默回退 fixture/demo。
- 所有任务先写或补充失败测试，再写最小实现；任务通过后再进入下一依赖任务。共享契约、`main.py`、OpenAPI 和生成类型按任务顺序串行修改。
- 不记录起终点名称、坐标、票价、服务号、乘客信息、请求 body、provider 原始响应或凭证；日志只允许 request ID、路由名、状态和耗时等已批准字段。
- 不实现 live provider、Key、真实网络请求、支付、订票、外部售票跳转、地图绘线或预算写入。真实 provider 若未来进入，必须新增 Gate、任务和批准记录。
- fixture 必须明确标注测试证据；测试结果只证明流程和契约，不得写成真实交通能力已验证。

## 任务（按依赖顺序）

### TRN-01 — 建立 fare／route 严格领域契约与合成 fixture

- [x] **验收：** 定义 `PlaceRef`、`FareQuery`、`FareSegment`、`ChargeComponent`、`FareOffer`、`RouteQuery`、`RouteStep`、`RouteOption` 及必要的窄枚举；复用 foundation 的金额、来源、时间、状态和结果 envelope。拒绝额外字段、无效日期、无时区 datetime、单边坐标、越界坐标、非正人数、负／float／bool 金额和非法方式；保持 `null`、`0`、`unknown`、`estimate`、`demo` 语义。显式验证 offer／route 的 `source_id` 最终必须能关联 envelope 来源。
- [x] **验证：** 在 `backend/` 执行 `uv run pytest tests/unit/test_transport_contracts.py -q`（38 passed）与 `uv run ruff check app/modules/transport tests/unit/test_transport_contracts.py`（通过）；参数化覆盖航班／铁路、换乘分段、三种路线方式、CNY 金额、未知价格／余量、额外字段、日期／坐标／时间反例。
- [x] **文件：** `app/modules/transport/__init__.py`、`app/modules/transport/contracts.py`、`tests/unit/test_transport_contracts.py`、`tests/fixtures/transport/fares.json`、`tests/fixtures/transport/routes.json`（5 个）。
- **依赖：** 已验收 foundation。

### TRN-02 — 定义 provider protocol 与 fake provider 映射

- [x] **验收：** 定义 `FareProvider`／`RouteProvider` 协议和可注入 fake；fake 能返回完整、部分、空、无覆盖、额度限制、政策不可用、服务不可用及非法映射场景；所有合成来源使用 `EvidenceState.DEMO`。provider 调用可记录查询参数与次数供测试断言，但默认应用不实例化 fake，不发网络请求。
- [x] **验证：** `uv run pytest tests/unit/test_transport_provider_mapping.py -q`（10 passed）；已确认 fare／route 查询不会互换，fixture 顺序保持、provider 来源引用由严格结果契约校验、fake 错误不携带原始响应。
- [x] **文件：** `app/modules/transport/providers/__init__.py`、`app/modules/transport/providers/base.py`、`app/modules/transport/providers/fake.py`、`tests/unit/test_transport_provider_mapping.py`（4 个）。
- **依赖：** TRN-01。

### TRN-03 — 实现交通 service 的状态归一化与来源校验

- [x] **验收：** service 分别处理 fare 与 route；未配置时返回 `unconfigured` 且 items 为空；合法合成结果保留来源、查询时间、目标日期、人数、金额基准、费用项、分段、路线耗时基准和 geometry；字段缺失但 item 合法时返回 `partial`；empty、no_coverage、rate_limited、policy_unavailable、unavailable 均不带 items；不把路线费用当票价、不按直线距离补路线、不把 null 当 0。provider 异常映射为公共状态并带同一 request ID。
- [x] **验证：** `uv run pytest tests/unit/test_transport_service.py -q`（20 passed；相关四组回归 75 passed）与对应 Ruff 检查（通过）；覆盖 query mismatch、来源完整性、live/demo evidence、查询时刻、party_total 人数、无 geometry、taxi estimate、实时耗时边界、各失败状态和默认无 provider。
- [x] **文件：** `app/modules/transport/service.py`、`tests/unit/test_transport_service.py`（2 个）。
- **依赖：** TRN-01、TRN-02。

### TRN-04 — 注册交通 API 与安全集成测试

- [x] **验收：** 实现 `POST /api/transport/fares/search` 和 `POST /api/transport/routes/search`；router 只负责 HTTP 映射并注入 service，复用 request ID、公共错误、CORS 和脱敏日志。默认配置不发请求并返回 `unconfigured`；非法输入在 provider 调用前返回 `VALIDATION_ERROR`；fare／route 的 OpenAPI schema 可区分。服务 request ID 与 `X-Request-ID`、嵌套错误 ID 一致。
- [x] **验证：** `uv run pytest tests/integration/test_transport_api.py -q`（7 passed）与 `uv run ruff check app/modules/transport app/main.py tests/integration/test_transport_api.py`（通过）；覆盖 fake 结果、默认未配置、非法 body、request ID、非允许 Origin 及敏感地点 sentinel 不出现在日志／错误体。
- [x] **文件：** `app/modules/transport/router.py`、`app/main.py`、`tests/integration/test_transport_api.py`（3 个）。
- **依赖：** TRN-01 至 TRN-03。

### TRN-05 — 导出 OpenAPI 并同步生成前端类型

- [x] **验收：** OpenAPI 包含两个 transport 请求、fare／route 响应、枚举、来源、coverage、公共错误和可空字段；从同一 schema 生成的 `api-contracts.ts` 不手写镜像。重复导出和生成结果字节稳定。
- [x] **验证：** 后端执行 `uv run python scripts/export_openapi.py ../frontend/src/shared/openapi.json`；前端使用 Node 24.22.1/npm 11.19.1 执行 `npm.cmd run generate:api`、`npm.cmd run typecheck` 两次；OpenAPI SHA-256=`64087D8AF88602286B720AB2DFD6183B134D61B0B6905A92564733994F6D7142`，TS SHA-256=`21A17B99BDAFD22B4B3E6AAFC6B66E9F3443FB4E1B98A3043746AC38A3F5F174`，两次一致。
- [x] **文件：** `frontend/src/shared/openapi.json`、`frontend/src/shared/api-contracts.ts`（2 个生成文件）。
- **依赖：** TRN-04。

### TRN-06 — 建立 transport API client 与查询面板骨架

- [x] **验收：** API client 只访问同源 `/api/transport/...`，消费生成类型，暴露安全的成功／公共错误状态，不记录请求体。`TransportPanel` 提供 fare 查询（起点、终点、方式、日期、人数）与 route 查询（起点、终点、方式、可选出发时间）表单；每个 route mode 独立维护 loading／success／error／unconfigured；提交、失败和重试反馈清晰，键盘可达且移动端无水平溢出。
- [x] **验证：** mock fetch/API 响应单测通过；`npm.cmd run test:unit -- --run src/features/transport`（14 passed，2 个测试文件）、`npm.cmd run typecheck`、`npm.cmd run lint` 均通过；payload 字段、错误 request ID、方式隔离和可见 label／状态语义均有断言。
- [x] **文件：** `frontend/src/features/transport/api.ts`、`frontend/src/features/transport/api.test.ts`、`frontend/src/features/transport/TransportPanel.tsx`、`frontend/src/features/transport/transport-panel.css`（4 个）。
- **依赖：** TRN-05。

### TRN-07 — 集成应用导航并完成 transport 组件测试

- [x] **验收：** 将交通入口接入现有 `App.tsx`，未改变 weather／budget 已有行为；支持在天气、预算、交通视图间切换。测试覆盖初始未配置、fare 换乘分段／来源／日期／计价标签、route 三方式独立状态、unknown/null 展示、无 geometry 文案、改变条件清除旧结果和迟到响应保护。
- [x] **验证：** `npm.cmd run test:unit -- --run src/App.test.tsx src/features/transport/TransportPanel.test.tsx`（12 passed）、`npm.cmd run typecheck`、`npm.cmd run lint`、`npm.cmd run build` 均通过；E2E 在 375px 与桌面／横屏视口断言无横向滚动，Testing Library 使用可访问查询。
- [x] **文件：** `frontend/src/App.tsx`、`frontend/src/App.test.tsx`、`frontend/src/features/transport/TransportPanel.test.tsx`（3 个）。
- **依赖：** TRN-06。

### TRN-08 — 建立交通桌面／移动 E2E 验收

- [x] **验收：** Playwright 只 mock 本地 transport API，绝不出网；桌面与 Pixel 7 覆盖默认未配置、fare 换乘分段／未知金额、transit 成功 + walking 失败 + taxi 成功、出租车估价、无 geometry、修改条件清空旧结果、慢响应不覆写新请求和 375px 无水平滚动。页面不出现 demo 作为默认真实结果的暗示。
- [x] **验证：** 设置项目 Node 路径后执行 `npm.cmd run test:e2e -- --grep transport`（6 passed）；全量 `npm.cmd run test:e2e`（22 passed）。测试只使用合成地点／票价和本地 route mock，未保存含真实位置、行程、Key 或敏感票价的 trace。
- [x] **文件：** `frontend/e2e/transport.spec.ts`（1 个）。
- **依赖：** TRN-07。

### TRN-09 — 全量回归与 transport 验收留证

- [x] **验收：** 完成 `docs/acceptance/transport.md`；分别报告流程测试通过、真实航班／铁路／路线 provider 未验证、E-002/E-004 阻塞和适用 AC-07、AC-14、AC-23、AC-25、AC-28、AC-36 的证据缺口。没有把 fake／fixture 写成真实交通能力完成，也没有宣称 Web 首版整体完成。
- [x] **验证：** 后端 `uv run --offline pytest -q`（191 passed）、`uv run --offline ruff check .`；前端 `npm.cmd run lint`、`npm.cmd run test:unit -- --run`（42 passed）、`npm.cmd run typecheck`、`npm.cmd run build`、`npm.cmd run test:e2e`（22 passed）；重复 OpenAPI/types 生成稳定；Secretlint 扫描前端 `src`、`dist` 及后端 `app` 通过。
- [x] **文件：** `docs/acceptance/transport.md`（1 个；若发现代码缺陷，回到对应实现任务并新增修复记录）。
- **依赖：** TRN-01 至 TRN-08。

## 阶段边界

- **允许：** 合成 fixture、fake provider、契约／状态／隐私测试、前端降级和流程展示。
- **需另行批准：** live provider、Key、真实网络请求、报价缓存／限流、非 CNY 展示／汇率、地图 SDK、预算写入、订票／支付／外部跳转。
- **禁止：** 直线冒充路线、路线费用冒充票价、null 当 0、unknown 当无票、demo 当 live、记录敏感 payload、默认静默回退 fixture。

## 审批记录

- 审阅人／日期：用户／2026-10-28（北京时间）
- 结论：批准并授权开始代码编写
- 修改摘要：按 v0.1 任务范围实施；保持默认 unconfigured、fake-only 测试和不连接真实交通 provider 的边界。

## 执行记录

- 2026-10-28：用户批准任务清单并明确授权代码编写；按依赖顺序从 TRN-01 开始，先写契约失败测试。
- 2026-10-28：TRN-01 红绿循环完成。初始测试在缺少 `app.modules.transport` 时失败；实现严格模型和合成 fixture 后，38 项契约单测通过，Ruff 检查通过。
- 2026-10-28：TRN-02 fake-only provider 协议和错误隔离完成；10 项 provider 映射测试通过，Ruff 检查通过。provider 不持久化、不联网，未配置时不会生成 demo 回退。
- 2026-10-28：TRN-03 service 状态归一化与来源校验完成；20 项 service 单测和相邻模块契约／provider 回归通过。错误响应使用稳定公共文案，保留 source `retrieved_at`，查询时刻使用 provider 响应携带的 `queried_at`。
- 2026-10-28：TRN-04 两个 API 路由与安全集成测试完成；7 项集成测试通过，默认未配置路径不创建 fake、不发网络请求，非法日期／地点／金额均在 provider 调用前校验。
- 2026-10-28：TRN-05 OpenAPI 与 TS 类型同步完成；连续两次生成和 typecheck 通过、哈希一致。后端全量回归 `uv run pytest -q` 为 191 passed（1 条已有 Starlette/httpx 弃用警告），`uv run ruff check .` 通过。
- 2026-10-28：TRN-06 API client 与 `TransportPanel` 完成；增加同源请求、显式日期／人数、unknown/null／来源／估算展示、逐方式状态隔离、公共错误和重试反馈；前端 transport 单测 14 passed，typecheck 和 lint 通过。
- 2026-10-28：TRN-07 交通入口接入 `App.tsx`；天气／预算／交通导航和交通组件测试完成；验证换乘分段、来源／日期／计价标签、无 geometry、条件变更清空和迟到响应保护。
- 2026-10-28：TRN-08 Playwright transport E2E 完成；桌面 Chromium 与 Pixel 7 的 transport 场景 6 passed，仅拦截本地 API，使用合成数据。
- 2026-10-28：TRN-09 完成全量回归与验收留证；后端 191 passed，前端 Vitest 42 passed、Playwright 22 passed，构建／Lint／类型／Secretlint 通过，OpenAPI SHA-256=`64087D8AF88602286B720AB2DFD6183B134D61B0B6905A92564733994F6D7142`，TS SHA-256=`21A17B99BDAFD22B4B3E6AAFC6B66E9F3443FB4E1B98A3043746AC38A3F5F174`。真实 provider 与 E-002/E-004 仍明确未验证。
