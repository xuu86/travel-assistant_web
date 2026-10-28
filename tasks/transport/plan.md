# transport 实施计划

> 版本：v0.1｜状态：已批准｜批准日期：2026-10-28（北京时间）  
> 对应规格：[SPEC-transport](../../docs/SPEC-transport.md) v0.2（已批准）。本计划只覆盖 `transport`，不代表任务清单或实现已获批准。

## 1. 目标与范围

在已验收的 `foundation` 上实现交通查询的第一版流程：

- 跨城航班／铁路班次与报价使用独立的 fare 契约；
- 公交／地铁、步行、出租车路线使用独立的 route 契约；
- 每个结果保留来源、查询时间、目标日期、人数、币种、计价基准、含费状态和 unknown/null 语义；
- 默认应用保持 `unconfigured`，仅通过注入的 fake provider 验证流程，不把 fixture 当真实数据；
- 前端提供响应式查询与结果展示，逐方式隔离 loading／成功／失败状态；
- 改变条件或发起新请求时清除旧结果，迟到响应不能覆盖当前条件。

本计划不实现真实航空／铁路／路线 provider，不申请或使用 Key，不进行网络请求、缓存供应商原始响应、地图绘制、预算写入、订票、支付或外部跳转。路线 geometry 只作为契约字段保留，地图展示归 `maps` 模块。

## 2. 已冻结口径与未决边界

### 2.1 本计划采用的口径

1. `travel_date` 是用户显式提供的目标出行日期；不得静默使用查询当天，也不得由 transport 覆盖用户输入。transport 不自动强制 itinerary 日期一致性。
2. `passenger_count` 只要求正整数；不从 Q-006 历史草稿继承人数上限、票种或年龄规则。provider 限制必须作为明确状态或公共错误返回，不能静默裁剪。
3. 预算计算只接受明确的非负 CNY 整数分；非 CNY 不自动换算、不放入 CNY 汇总。非 CNY 能力不进入本轮实现验收。
4. 不实现外部缓存、报价 TTL 或自动限流策略；Q-014 仍需单独冻结后，才能设计 live adapter 的缓存与请求预算。
5. fake provider 只通过依赖注入进入测试；默认运行配置没有 provider 时返回空 items 的 `unconfigured`，不回退到 fake／demo。

### 2.2 仍需单独决定或核实的事项

- E-002 高德路线权限、额度、署名和适用条款；
- E-004 航班／铁路真实班次与票价来源；
- Q-014 报价缓存 TTL、新鲜度、并发和限流；
- 非 CNY 原币展示、精度和预算边界；
- 真实请求测试、供应商 Key、支付／订票和外部跳转。

这些事项不作为本计划的隐含授权。若以后要实现 live adapter，必须建立独立 provider Gate、记录证据并重新审批任务范围。

## 3. 技术方案

- **后端契约：** 在 `backend/app/modules/transport/contracts.py` 定义严格 Pydantic 模型，复用 foundation 的 `ContractModel`、`ResultEnvelope`、`SourceRef`、`EvidenceState`、`ResultState`、金额与 UTC 规范。请求／响应拒绝额外字段、无时区时间、半坐标、负值、float／bool 金额和非法日期。
- **来源完整性：** service 在返回前确认每个 offer／route 的 `source_id` 都存在于同一 envelope 的 `sources`；来源映射失败不得展示为可核实结果。`unavailable`、`empty`、`unconfigured` 等无 items 状态遵守 foundation 约束；合法但字段缺失的结果使用 `partial`。
- **provider 隔离：** `providers/base.py` 只声明 `FareProvider`／`RouteProvider` 协议；fake 实现放在测试支持范围，使用合成数据和固定时钟。生产服务不导入 fixture 作为默认 provider。
- **服务归一化：** `service.py` 负责 query 校验后的 provider 调用、状态归一化、顶层时间／分段语义、来源链接、缺失字段和错误映射；router 不承担业务聚合或 provider 字段猜测。
- **API：** 增加 `POST /api/transport/fares/search` 与 `POST /api/transport/routes/search`，沿用公共异常、CORS、request ID 和脱敏日志。请求 body、地点、坐标、票价、服务号和 provider 原始响应不得写入日志或错误文案。
- **前端：** 新增 transport API client 和 `TransportPanel`。fare 与 route 使用明显分区；route 的 transit／walking／taxi 各自维护状态。金额、来源、查询时间、估算／待核实、无 geometry 文案相邻展示；不画两点连线，不把路线费用当票价。
- **OpenAPI：** FastAPI 作为唯一契约源；仅在后端 API 稳定后导出 `frontend/src/shared/openapi.json` 并生成 `api-contracts.ts`，不手写重复公共 schema。
- **UI/UX：** 沿用现有 React 设计 tokens 和语义结构；移动端优先，表单有可见 label、提交 loading／错误反馈、键盘焦点和 `aria-live` 状态，375px 不产生水平溢出；状态不能只靠颜色区分。

## 4. 组件、依赖与实施顺序

| 顺序 | 组件 | 主要责任 | 依赖 | 检查点 |
|---:|---|---|---|---|
| 0 | 运行基线复核 | 确认现有 Python／Node／锁文件和模块命令可复用，不新增依赖 | foundation 验收 | 命令在当前工作区可执行；无未授权安装 |
| 1 | fare／route 领域契约 | PlaceRef、FareQuery、FareOffer、FareSegment、ChargeComponent、RouteQuery、RouteOption、RouteStep 及状态不变量 | foundation | 合法／反例契约测试通过 |
| 2 | provider protocol 与 fake | 协议、合成 fixture、未配置 provider 和错误／部分结果注入 | 1 | 默认无网络；fake 调用次数和来源状态可断言 |
| 3 | service 归一化 | 两类查询的状态、来源、时间、分段、缺失字段、geometry 和错误隔离 | 1、2 | 单元测试覆盖 live／partial／empty／unconfigured／no_coverage／rate_limited／unavailable |
| 4 | FastAPI 路由与集成 | 注册两个 POST 端点，公共错误、request ID、脱敏日志和 OpenAPI | 1–3 | API 集成与 OpenAPI schema 检查通过 |
| 5 | 前端 API 与查询面板 | 生成类型消费、表单、结果卡片、方式独立状态、迟到响应保护和响应式可访问 UI | 4 | 单测、typecheck、lint、375px 检查通过 |
| 6 | E2E、回归与验收记录 | route mock、全模块回归、密钥扫描、transport 分项 AC 记录 | 1–5 | E2E／构建／扫描通过；真实能力与流程能力分开报告 |

依赖图：`1 → 2 → 3 → 4 → 5 → 6`。组件 1 冻结后，fare 与 route 的 fake／service 单测可在不共享可变状态的前提下并行；OpenAPI 类型同步必须等待组件 4。

## 5. 预期文件范围

任务清单阶段将进一步拆分，每项尽量不超过五个文件。候选范围如下：

```text
backend/app/modules/transport/__init__.py
backend/app/modules/transport/contracts.py
backend/app/modules/transport/service.py
backend/app/modules/transport/router.py
backend/app/modules/transport/providers/base.py
backend/app/modules/transport/providers/fake.py
backend/app/main.py
backend/tests/unit/test_transport_contracts.py
backend/tests/unit/test_transport_service.py
backend/tests/unit/test_transport_provider_mapping.py
backend/tests/integration/test_transport_api.py
backend/tests/fixtures/transport/fares.json
backend/tests/fixtures/transport/routes.json
frontend/src/shared/openapi.json                 # 生成文件
frontend/src/shared/api-contracts.ts             # 生成文件
frontend/src/features/transport/api.ts
frontend/src/features/transport/TransportPanel.tsx
frontend/src/features/transport/transport-panel.css
frontend/src/features/transport/TransportPanel.test.tsx
frontend/src/App.tsx
frontend/e2e/transport.spec.ts
docs/acceptance/transport.md
```

不在任务清单中自动新增 provider SDK、地图 SDK、数据库、持久化缓存、环境密钥或依赖；若发现依赖缺口，先暂停当前任务并说明影响。

## 6. 验证门

### Gate A：契约先行

固定字段和状态真值表；测试日期、时区、地点坐标、人数、金额、币种、计价基准、分段顺序、含费项、来源链接、geometry 和额外字段。验证 `null`／`0`、`unknown`／`unavailable`、路线估算／票价的边界不被混淆。

### Gate B：fake-only service

使用固定 UTC 时钟与合成 provider 响应，验证 fare 与 route 的来源映射、部分字段、空结果、未配置、无覆盖、额度限制、服务故障和非法 provider payload。所有自动化测试禁网；fake 结果明确为 `demo`／测试证据，不进入默认应用。

### Gate C：API 与隐私

验证两个端点的成功／错误 schema、HTTP 状态、`X-Request-ID` 一致性和 body 不进入日志；扫描 sentinel 地点、服务号、金额、假 Key、provider URL 和原始异常文本不出现在日志、错误、OpenAPI 或前端 bundle。

### Gate D：前端交互

验证 fare／route 表单有可见 label；查询条件变化清除旧结果；取消／迟到响应不覆盖新条件；transit 成功、walking 失败、taxi 成功时互不清除；未知金额不显示为 0；无 geometry 不画线；状态有文字和辅助技术语义。

### Gate E：端到端与回归

Playwright 只拦截本地 API 并注入合成响应，覆盖桌面和 375px：未配置、班次部分字段、换乘分段、路线失败隔离、估价标签、无 geometry、改条件／慢响应和无水平滚动。然后执行完整后端／前端回归、OpenAPI 二次生成稳定性和 Secretlint。

## 7. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 票价与路线事实混用 | 用户误把路线估算当成可购买票价 | 独立 schema、API、UI 分区和反例测试 |
| `null`／unknown 被渲染为 0 | 产生虚假费用或余票结论 | 严格模型、显示函数和 E2E 断言 |
| 旧响应覆写新条件 | 页面显示不匹配查询条件的结果 | 每个 mode 的 request token／Abort 语义和可控 promise 测试 |
| source_id 无法追溯 | 来源事实不可核验 | envelope 内 source 映射校验，映射失败不展示 |
| 供应商未授权或免费来源不存在 | 误接入或泄露 Key | 默认 unconfigured；live provider 另行 Gate，不写 SDK／Key |
| geometry 缺失被自行连线 | 伪造路线 | geometry 为 null 时只展示文字并明确地图路线待核实 |
| 用户地点／票价进入日志 | 隐私泄露 | 结构化日志仅保留 request ID、路由、状态、耗时；集成测试使用 sentinel 扫描 |

## 8. 计划完成定义

本计划对应的后续实现完成后，必须同时具备：

1. 严格 fare／route 契约、状态不变量和 provider 来源链接测试；
2. 默认无 provider 时安全返回 `unconfigured`，fake-only 流程可独立验收；
3. 两个 API 端点和生成 OpenAPI／TypeScript 类型一致；
4. 前端逐方式状态隔离、未知／估算／测试证据标签、迟到响应保护和移动／键盘体验通过；
5. 后端、前端、E2E、构建、Lint、类型检查和密钥扫描通过；
6. `docs/acceptance/transport.md` 分开记录流程通过、真实 provider 未验证和受阻 AC，不把 fake 当真实交通能力。

## 9. 本阶段不授权事项

计划获批仅允许建立 transport 任务清单；不等于任务清单获批，也不授权开始写实现代码。任务清单需逐项列出验收、验证命令和文件范围，再单独审批。当前不初始化 Git、不配置 GitHub remote、不提交或推送。

## 10. 审批记录

- 审阅人／日期：用户／2026-10-28（北京时间）
- 结论：批准
- 修改摘要：批准 v0.1；继续保持 fake-only、默认 unconfigured、无 live provider／Key／真实网络请求边界。允许进入 transport 任务清单阶段，不等于任务清单或实现获批。
