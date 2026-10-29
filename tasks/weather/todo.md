# weather 任务清单

> 版本：v0.2｜状态：非商业试用 provider 已配置；WTH-10/WTH-11 限定范围验收完成｜用户批准：2026-10-29
> 对应已批准文件：[SPEC-weather](../../docs/SPEC-weather.md)、[weather 实施计划](plan.md)。真实 provider 结论仅适用于本次非商业试用与单日 smoke test，不构成商业／公网生产许可。

## 通用执行规则

- 依赖由 `backend/uv.lock` 和 `frontend/package-lock.json` 固定；不得因本模块擅自新增包、数据库、外部服务、持久化缓存或真实密钥。
- backend 命令在 `backend/` 运行；frontend 命令在 `frontend/` 运行。测试默认禁网，Provider 使用 fake/fixture。
- 天气模块的流程验收与真实 provider 状态分开记录。mock/fixture 通过不能写为真实天气能力已验证。
- 各任务文件范围不超过 5 项；共享 OpenAPI/生成类型只有 WTH-06 修改，确保串行更新。

## 任务（按依赖顺序）

### WTH-00 — 建立供应商 Gate 0 证据记录（不发 API 请求）

- [x] **验收：** 在实施 provider adapter 前记录 Open-Meteo（或另一个后来获批候选）的当前官方用途条款、署名要求、额度定义、Forecast 字段／最大日期请求、五城实际覆盖状态和核实日期。公开资料不足以判断本产品参赛／公开展示用途时，如实记为“待项目负责人确认”，Gate 0 保持未通过；不得推断许可或发起真实 API 请求。
- **验证：** 逐项对照 E-001；引用官方材料与访问日期；报告不含 Key、个人数据或未经授权的实时请求结果。未核实或需授权时，该任务结论为“阻塞并保留证据缺口”，WTH-10／WTH-11 必须维持不可执行。
- **文件：** `docs/weather-provider-gate.md`（1 个）。结果：Gate 0 未通过；WTH-10/WTH-11 保持 blocked。
- **依赖：** 无；该 Gate 仅决定是否允许条件任务。

### WTH-01 — 冻结天气领域契约与基础 fixture

- [x] **验收：** 建立 `WeatherQuery`、`WeatherDay`、位置元数据及 normalized provider payload；只接受 foundation 注册城市 ID；请求日闭区间且最多 16 个当地日；错误日期／超限输入在调用 provider 前拒绝；统一单位和 `null`／0 语义符合 SPEC。
- **验证：** 在 `backend/` 执行 `uv run pytest tests/unit/test_weather_contracts.py -q` 与 `uv run ruff check app/modules/weather/contracts.py tests/unit/test_weather_contracts.py`；覆盖同日、16/17 日、逆序日期、非法 city ID、概率／温度／降水边界、额外字段、NaN/Inf 与 null/0。
- **文件：** `app/modules/weather/contracts.py`、`tests/unit/test_weather_contracts.py`、`tests/fixtures/weather/payloads.json`（3 个）。
- **依赖：** foundation 已验收。

### WTH-02 — 定义 provider protocol 与默认 mock

- [x] **验收：** 实现可注入 `WeatherProvider` protocol 和仅供本地测试的 fake provider；fake 可按 case 返回完整、部分、空、异常和错误 payload，并可检查请求计数；生产配置默认仍 `unconfigured`，不偷偷使用 fake 结果。
- **验证：** `uv run pytest tests/unit/test_weather_provider.py -q`；验证 default/no-provider、fake 覆盖请求 city/range、fixture 被标成 `demo`，实时服务失败时无 demo 回退。
- **文件：** `app/modules/weather/providers/base.py`、`app/modules/weather/providers/fake.py`、`app/modules/weather/providers/__init__.py`、`tests/unit/test_weather_provider.py`（4 个）。
- **依赖：** WTH-01。

### WTH-03 — 实现日期对齐、覆盖分割与状态归一化

- [x] **验收：** service 逐日校验 provider 返回；闭区间每个日期至多一条记录；超出请求区间记录被丢弃、重复日期／非法 payload 安全降级；过去日期标 missing、不查历史 API；完整、部分、empty、no_coverage、unconfigured、限流和 unavailable 按 SPEC 区分；不以旧天气、邻城、demo 或气候均值填补。
- **验证：** `uv run pytest tests/unit/test_weather_service.py -q`；fixture 覆盖完整／首尾缺失／中间缺失／全空／重复日期／越界日期／空字段／无效温度与未来未知天气码；断言 coverage 精确分割 requested range。
- **文件：** `app/modules/weather/service.py`、`tests/unit/test_weather_service.py`、`tests/fixtures/weather/payloads.json`（3 个；共享 fixture 按任务依赖顺序扩展）。
- **依赖：** WTH-01、WTH-02。

### WTH-04 — 实现有限重试与 15 分钟进程内缓存

- [x] **验收：** 单次 timeout 8 秒；最多重试 1 次，仅连接／超时／502、503、504；429 与其他 4xx 不重试；缓存仅 live/partial，进程内 TTL 15 分钟；命中保留原来源 `retrieved_at`，HTTP request_id 每次新建；过期失败不 stale-if-error；无状态／用户数据落盘。
- **验证：** `uv run pytest tests/unit/test_weather_runtime.py -q`；用 fake clock、fake transport 验证 retry 次数、等待上限、TTL 边界、cache key、缓存命中 0 次上游请求、过期后故障不返旧值。
- **文件：** `app/modules/weather/runtime.py`、`tests/unit/test_weather_runtime.py`、`tests/fixtures/weather/payloads.json`（3 个）。
- **依赖：** WTH-01 至 WTH-03。

### WTH-05 — 添加天气 API 与 OpenAPI 声明

- [x] **验收：** 实现 `POST /api/weather/forecast`；由请求 city_id 查 foundation registry 并使用登记坐标；body 不进日志；返回 `ResultEnvelope[WeatherDay]` 与统一 `PublicError`；request_id／CORS 沿用 foundation；未配置 provider 时返回 unconfigured，不返回 demo。
- **验证：** `uv run pytest tests/integration/test_weather_api.py -q`；FastAPI `TestClient` 仅使用 fake provider，覆盖正常、16/17 日、未知 city、状态、公共错误 schema、request_id、非允许 Origin 和 body sentinel 未进入捕获日志。
- **文件：** `app/modules/weather/router.py`、`app/main.py`、`tests/integration/test_weather_api.py`（3 个）。
- **依赖：** WTH-01 至 WTH-04。

### WTH-06 — 导出天气 OpenAPI 并同步前端类型

- [x] **验收：** OpenAPI 包含 weather 请求／逐日响应／位置元数据／coverage／PublicError；`openapi-typescript` 生成的类型准确表达可空字段、天气状态和日期字段；重复导出／生成哈希稳定。
- **验证：** backend 执行 `uv run python scripts/export_openapi.py ../frontend/src/shared/openapi.json`；frontend 执行 `npm run generate:api`、`npm run typecheck` 两次；第二次 `openapi.json` 和 `api-contracts.ts` SHA-256 与首次一致。
- **文件：** `frontend/src/shared/openapi.json`、`frontend/src/shared/api-contracts.ts`（2 个生成文件）。
- **依赖：** WTH-05。

### WTH-07 — 建立前端天气 API client 与状态测试

- [x] **验收：** client 使用同源 `/api/weather/forecast`、传入生成的 OpenAPI 类型；暴露 loading/data/error，不直接访问 provider；错误保留公共状态和 request_id；请求体不写浏览器日志。
- **验证：** `npm run test:unit -- --run src/features/weather/api.test.ts`、`npm run typecheck`、`npm run lint`；使用 mock fetch 覆盖成功、partial、unconfigured、429/503、422 及无效 JSON。
- **文件：** `frontend/src/features/weather/api.ts`、`frontend/src/features/weather/api.test.ts`（2 个）。
- **依赖：** WTH-06。

### WTH-08 — 实现逐日天气界面并集成应用壳

- [x] **验收：** 展示单城日期范围、每日数据及单位、来源／取数时间、loading/partial/missing/unconfigured/rate_limited/policy_unavailable/unavailable；null 不当作 0；未知 WMO 码可读；响应式、键盘可达、语义标签完整、无水平溢出；无 provider 时明确显示未配置，不造实时数据。
- **验证：** `npm run test:unit -- --run src/features/weather/WeatherPanel.test.tsx`、`npm run lint`、`npm run typecheck`；测试 375px 与桌面视口下主要状态和可访问名称。
- **文件：** `frontend/src/features/weather/WeatherPanel.tsx`、`frontend/src/features/weather/weather-panel.css`、`frontend/src/App.tsx`、`frontend/src/features/weather/WeatherPanel.test.tsx`（4 个）。
- **依赖：** WTH-07。

### WTH-09 — 建立天气桌面／移动 E2E 状态验收

- [x] **验收：** Playwright 只 mock `/api/weather/forecast`，不出网、不调用真实 provider；桌面／移动视口覆盖完整预报、部分覆盖和未配置／失败；缺失日期清晰可见；无旧值、无 demo fallback、无水平滚动。
- **验证：** `npm run test:e2e -- --grep weather`；Playwright trace 只在失败时保留，不保存真实位置／行程资料。
- **文件：** `frontend/e2e/weather.spec.ts`（1 个）。
- **依赖：** WTH-08。

### WTH-10 — 实现 Open-Meteo adapter

- [x] **验收：** 固定官方 endpoint、仅由后端配置选择、daily 变量、`Asia/Shanghai` 和 metric 单位；设 8 秒 timeout、限长响应、稳定错误映射和署名；无需密钥；默认未配置时不出网。
- [x] **验证：** MockTransport 覆盖参数、映射、null/missing、状态、超大／畸形响应和网络错误；后端全量 `uv run pytest -q` 262 项通过，`uv run ruff check .` 通过。
- **文件：** `backend/app/modules/weather/providers/open_meteo.py`、`backend/app/core/config.py`、`backend/tests/unit/test_open_meteo_adapter.py`。
- **依赖：** WTH-00、WTH-01 至 WTH-04；2026-10-29 用户批准非商业试用配置。

### WTH-11 — 受控真实覆盖烟雾测试

- [x] **验收：** 2026-10-29 按用户批准的非商业试用范围，对五个注册城市各发 1 次 2026-10-29 单日请求；记录日期、变量缺失、网格坐标和高程，不保存原始 payload；结果不外推。
- [x] **验证：** 五城均成功且六项变量齐全；另有一次后端路由三日端到端验证。具体摘要见 `docs/acceptance/weather-provider.md`。官方非商业条款、限额、署名及无 uptime 保证见 `docs/weather-provider-gate.md`。
- **文件：** `docs/acceptance/weather-provider.md`（1 个证据文件）。
- **依赖：** WTH-00、WTH-10；授权仅限非商业试用和上述五次单日请求。

### WTH-12 — 天气模块回归与分项验收记录

- [x] **验收：** mock-only 模块范围后端／前端回归通过；分别记录 AC-01、AC-03、AC-06、AC-25 天气子项；live provider 未通过 Gate 0 时明确标未验证／阻塞，不宣称真实天气或天气能力整项完成；AC-03 推荐责任不归 weather。
- **验证：** `uv run pytest -q`、`uv run ruff check .`；`npm run lint`、`npm run test:unit -- --run`、`npm run typecheck`、`npm run build`、`npm run test:e2e`；OpenAPI/types 重复生成稳定；Secretlint 工作区与 `dist` 扫描通过。
- **文件：** `docs/acceptance/weather.md`（1 个；若代码缺陷需修复，先回到对应实现任务）。
- **依赖：** WTH-00 至 WTH-09；若报告真实 provider 状态，则还需 WTH-10/WTH-11 条件通过。

## 审批记录

- 审阅人／日期：
- 结论：批准 / 需修改 / 暂停
- 修改摘要：

## 执行记录

- 2026-10-27：WTH-00 已完成记录。仅查阅官方公开资料，未发起实时天气请求；Open-Meteo 用途资格、五城实际覆盖和额度实测仍未确认。WTH-10/WTH-11 保持 blocked。
- 2026-10-27：WTH-01 至 WTH-09 与 WTH-12 已完成 mock-only 实施、回归和分项验收；证据见 `docs/acceptance/weather.md`。真实 provider 未接入，WTH-10/WTH-11 继续 blocked。
- 2026-10-29：后续用户明确要求非商业 API 配置，已完成 WTH-10/WTH-11 限定范围工作；本次状态覆盖上述历史 blocked 记录，具体用途和证据边界见 `docs/weather-provider-gate.md` 与 `docs/acceptance/weather-provider.md`。
- 2026-10-29：按用户请求启用本地 Open-Meteo 非商业 provider；WTH-10 adapter 与 WTH-11 五城单日 smoke test 已完成。商业／公网生产许可仍需另行确认。

