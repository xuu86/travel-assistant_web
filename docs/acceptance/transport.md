# Transport 验收记录

> 首次验收：2026-10-28（北京时间）
>
> 补充验收：2026-10-30（北京时间）
>
> FlyAI v0.2：2026-10-31（北京时间；后端官方 CLI 接入及本地 API 真实查询通过，缺价保持未知）
>
> 范围：已批准的 `SPEC-transport` v0.2、transport 任务 TRN-01 至 TRN-09，以及条件航班 Provider TLP-00 至 TLP-05。**mock/流程验收不代表真实航班、铁路或路线数据已经验收。**

## 2026-10-31 FlyAI v0.2 官方 CLI 网页接入验收

**结果：实现与本地 API 真实铁路查询通过；确定票价未返回。** 用户批准后端封装官方 CLI，并要求缺价显示“票价未返回”。本节为当前状态，下方前置核查和其他日期内容保留历史范围。

- 固定官方 CLI 1.0.16，安装校验 SHA-512，运行校验 bundle SHA-256；Node 与 CLI 未部署返回 unconfigured，不启动全局安装。
- 独立铁路配置，兼容已配置的 FLYAI_API_KEY，SecretStr 保管；无 Key 无上游、不使用试用凭据。runtime 按模式分流，不跨 provider 回退。
- 无 shell；地点/日期经 stdin，Key 只经受限环境；官方目标一次 POST、禁止重定向、无重试、45 秒请求超时加 5 秒退出宽限、1 MiB 响应/stdout、64 KiB stderr、最多 2 个并发。
- HTTP 401/403→policy_unavailable、429→rate_limited，非零业务状态/坏 JSON/异常进程→unavailable，未来日期限制→no_coverage。异常不包含原始响应或地点。
- 保留站点、时刻、车次、分段席别，首段日期及首尾地点校验；国内无偏移时刻使用 Asia/Shanghai，不把日期文本伪造成午夜班次。
- 票价、人数计价基准、余量与可购状态保持未知；铁路缺价显示“票价未返回”。安全官方 HTTPS 详情链接、品牌来源、查询时间、纯文本提示已接入。

### 已授权的真实 API 查询

| 项目 | 结果 |
|---|---|
| 范围 | 本地 FastAPI TestClient→runtime→受控官方 CLI→FlyAI；上海→杭州，2026-11-01；新增 1 次、0 重试 |
| 请求验证 | API HTTP 200、上游 HTTP 200、CLI exit 0、1 次 fetch、认证与本地 Key 匹配；request_id 与响应头一致 |
| 数据映射 | state=partial，10 条方案、13 个分段、13 段席别、10 条金额 null、10 条计价人数未知 |
| 展示边界 | 没有链接通过 HTTPS 官方域名校验，因此不展示详情入口；平台提示未出现；未知字段不补值 |
| 留存 | [脱敏 API 摘要](flyai-train-api-smoke-2026-10-31.json)；原始响应仅内存解析，无 Key、车次、报价或返回链接落盘 |

此前独立 CLI 诊断与本次 API 查询各 1 次。本次 API 验收不等于真实浏览器重复查询；网页渲染与交互使用合成 E2E 验证，不重复消费真实额度。确定价格、余票、全部账户权限/配额、缓存与公网部署用途仍未核实。

### 自动化验证

- 后端最终完整 pytest：367 passed；FlyAI 单元及相关集成定向回归 61 passed。
- 前端完整 Vitest：79 passed；TypeScript、ESLint、Vite 构建通过。
- Playwright 交通场景：桌面及移动共 8 passed，覆盖缺价、席别、官方链接、提示、无横向溢出、航班与路线回归及迟到响应保护。
- 桌面实际视口和手机视口的铁路结果截图已目视检查，缺价文案、分段席别与详情入口显示正常；截图使用合成测试数据。
- Ruff、类型契约生成、Secretlint（应用源码/构建产物/新增 CLI 与测试/相关文档）通过；可提交文件中已配置密钥精确匹配为 0，文档本地链接和 git diff --check 通过。官方 bundle 位于 Git 忽略目录，未纳入源码密钥扫描。
- 本地 backend/.env 已启用铁路 provider；发现天气 provider 误填 URL，已规范为 open_meteo，使后端正常启动，未改动或输出已有密钥。

## 历史：2026-10-31 FlyAI 铁路接入前置核查

已按用户指定的[实施计划](../../tasks/flyai-train-provider-plan.md)核查官方公开文档、官方仓库固定提交和用户服务协议，详见[契约核查记录](../flyai-train-contract-review.md)。

| 项目 | 结果 | 证据／边界 |
|---|---|---|
| CLI 能力存在性 | 已核实 | 官方仓库列出 `search-train` 参数与 `data.itemList[].journeys[].segments[]` 示例 |
| Gate A：服务端契约 | **未通过** | 未取得正式 HTTP/SDK 调用契约、认证传输方式、完整响应 schema、错误码与稳定性承诺 |
| 票价／席别映射依据 | **未确认** | `adultPrice` 字符串示例不能证明确定席别价、币种/单位契约、税费及计价人数基准 |
| 权限与展示 | **部分核实** | 真实 Key 本次铁路查询成功；具体配额、账户全部权限、用途及缓存仍未确认；官方预订链接展示要求与当前规格不提供外部跳转存在差异 |
| Provider、配置、前端及 FlyAI mock 验收 | **未实施** | 按 Gate A 前置依赖暂停，未构造猜测的接口或映射 |
| 真实 Key／CLI 查询 | **通过（独立诊断）** | 单次真实查询 HTTP 200、业务状态 0、10 条结果；票价、应用 Provider 及前端端到端未验收，见下文 |

本次增补文档并执行一次独立官方 CLI 诊断，未修改 FlyAI 运行时代码；历史 Amadeus mock 回归不能作为 FlyAI Gate B/C 或真实铁路验收证据。下方 2026-10-30 与 2026-10-28 内容保留历史测试范围，其“未发真实请求”描述不涵盖本次已授权的 CLI 诊断。

### 真实 API Key 核验（2026-10-31）

用户明确要求使用真实 API Key 并回复“已配置”后，从 Git 忽略的 `backend/.env` 读取 `FLYAI_API_KEY`，完成以下受控核验，无需重复授权。详见[官方契约核查记录](../flyai-train-contract-review.md)和[脱敏机器摘要](flyai-train-live-smoke-2026-10-31.json)。

| 核验项 | 结果 |
|---|---|
| 工具与范围 | 官方 `@fly-ai/flyai-cli@1.0.16`；本地开发环境；上海→杭州；出发日 2026-11-01 |
| 请求边界 | 1 次请求、0 次重试；仅官方 HTTPS 主机，禁止 redirect；45 秒请求超时、1 MiB 响应限制，父进程 55 秒超时 |
| Key 使用 | 守卫确认 Authorization 与本地配置 Key 匹配；经子进程环境传递，无命令行密钥 |
| 协议与业务 | HTTP 200；JSON 12,501 bytes；CLI exit 0；业务 `status=0` |
| 结果结构 | 10 条 `data.itemList`、13 个行程分段；分段发到站/时间、车次、席别等检查字段均存在 |
| 日期 | 13 个分段出发日期均符合 2026-11-01；未独立核对时刻准确性、席位或可购状态 |
| 票价边界 | 10 个条目均缺 `adultPrice`；所检查的 `currency`、`priceUnit`、`priceBasis`、`remainingSeats` 均未出现，不生成确定票价或余量 |
| 展示字段 | 10 个条目有 `jumpUrl`，顶层 `systemMessage` 未出现；链接未保存、未打开 |
| 数据保存 | 原始响应只在内存解析；仅保存本表与机器统计摘要，不落盘 Key、原始结果、价格、车次或返回链接 |

**本次验收通过：配置的真实 Key 可完成该次官方 CLI 铁路查询。** 尚未验收票价语义、错误映射、配额/用途、应用运行时及前端链路；Gate A–D 整体继续保持未通过，生产 FlyAI Provider 未启用。

### 本次验证（2026-10-31）

- `backend/`：`uv run --offline pytest -q tests/unit/test_config.py tests/unit/test_amadeus_provider.py tests/unit/test_transport_service.py tests/integration/test_transport_live_provider.py tests/integration/test_transport_api.py` → **85 passed**；1 条既有 Starlette `TestClient` / httpx 弃用警告。此为既有配置、Amadeus、service/API 的合成数据回归。
- 本次修改的 5 份 Markdown 文档 UTF-8、相对链接及 `git diff --check` 检查通过。
- 未修改运行时代码，未重跑前端/E2E、完整后端或 Secretlint；未将历史通过记录标记为本次 FlyAI 验收。

## 2026-10-30 官方航班 Provider 条件接入

### 结论

Amadeus Flight Offers Search adapter、配置接线、航班 IATA 前端和全部 mock/回归测试已完成。该能力默认关闭，只有服务端完整配置 `amadeus` provider、Client ID 与 Client Secret 时才构造；测试未创建真实凭据，也未向 Amadeus 发出 OAuth 或航班查询请求。

**真实供应商数据仍未验收。** 铁路、公交、地铁、步行、出租车 / 驾车均未接通，不能把本次记录解释为这些能力已完成。

### 交付与证据

| 项目 | 结果 | 边界 |
|---|---|---|
| Amadeus adapter | 已完成（CONDITIONAL） | 固定 test/production 官方 HTTPS 主机；TLS 校验、关闭 redirect/环境代理、timeout/body limit、OAuth 缓存、CNY 精度、旅客合计、余量/班次映射和安全错误状态 |
| Settings / runtime | 已完成 | 默认 provider 为空；provider + 两个凭据完整才启用；未知/缺失配置 fail closed；route provider 仍为空 |
| API 接线 | 已完成（mock） | 默认 Settings 无外部请求；注入 MockTransport 验证 API → Provider 映射、429 公共错误和 request ID |
| 前端航班 IATA | 已完成 | 必须填写三字 IATA；小写提交前转大写；同机场、缺 IATA、总人数 > 9 阻断；铁路不要求 IATA；条件变化清理旧结果 |
| 航班形式时间 | 保守映射 | 受控 IATA → IANA 时区；未识别机场为 partial/null，不猜测时区 |
| 铁路 | **未接入** | 12306 网页/内部接口仍 BLOCKED；等待正式授权的独立 Railway Provider |
| 市内路线 | **未接入** | 公交、地铁、步行、出租车 / 驾车仍无获批 provider；保留 fake 流程和空状态 |

### 自动化回归（2026-10-30）

- `backend/`：`uv run pytest -q` → **309 passed**；有 1 条既有 Starlette `TestClient` / httpx 弃用警告。
- `backend/`：`uv run ruff check .` → **通过**。
- `frontend/`：`vitest --run` → **77 passed，11 个测试文件**。
- `frontend/`：`tsc --noEmit` → **通过**；`eslint .` → **通过**；`vite build` → **通过**。
- `frontend/`：Playwright → **36 passed**（desktop-chromium、mobile-chromium 各 18）；航班 E2E 断言 body 中 IATA 为大写、票价 `¥355.34`、班次 `MU1234`，并验证 375px/横屏无水平溢出。
- transport E2E 只拦截同源 `/api/transport/fares/search` 与 `/api/transport/routes/search`；没有真实 Amadeus/同程/12306 请求。
- Secretlint 对 `backend/app`、`frontend/src`、`frontend/dist` 扫描通过，无发现。

### 未验收与继续条件

1. **真实 Amadeus 数据：未验证。** 需要项目可用的 test/production 资格、条款、目标航线覆盖、CNY/税费/儿童口径、配额/缓存/署名和最终确认价证据。
2. **Live smoke：未执行。** 需用户另行确认测试机场/日期、次数、环境、脱敏证据范围；用户批准代码接入不等于批准真实查询。
3. **铁路：未接通。** 需正式授权的 Railway Provider、稳定 API 契约和独立 Gate；不得调用 12306 内部接口。
4. **公交/地铁/步行/出租车：未接通。** 需独立路线供应商与规格；不能用直线、估算或出租车报价代替其他 mode。
5. 搜索结果不是锁价、锁位或最终支付价；本模块不提供预订/支付/售票跳转。

## 历史验收结论（2026-10-28）

**transport 契约、后端 service/API、前端查询流程、应用导航和本地自动化回归通过。** 默认不配置交通 provider；用户提交查询后，服务明确返回 `unconfigured`，没有 demo/fixture 回退。测试中的所有交通响应均为合成数据或本地 API mock，没有供应商 SDK、Key 或真实交通请求。

真实交通能力仍未验证：航班／铁路班次与票价供应来源（E-004）和路线供应商权限、额度及署名（E-002）均不在本次实施范围。不得将本记录解释为 Web 首版整体完成。

## 交付与证据

| 任务 | 结果 | 证据／边界 |
|---|---|---|
| TRN-01 至 TRN-03 | 通过 | 严格 fare／route 契约、合成 fixture、fake provider、状态归一化和 envelope 来源关联；后端单元测试通过 |
| TRN-04 | 通过 | 两个 transport POST API、默认未配置、公共错误及 request ID；集成测试含敏感地点 sentinel 脱敏断言 |
| TRN-05 | 通过 | OpenAPI 与生成的 TypeScript 类型重复生成稳定；哈希如下 |
| TRN-06 | 通过 | 同源 API client、显式目标日期／人数表单、逐 mode 查询状态、错误 request ID、loading 与显式重试提示、未知值安全显示 |
| TRN-07 | 通过 | 天气／预算／交通导航；航班／铁路分段、来源和计价信息；路线结果隔离、修改条件清除旧结果、迟到响应保护 |
| TRN-08 | 通过 | Playwright 桌面 Chromium 与 Pixel 7；transport 3 项场景共 6 个 project-case 通过；仅 mock 同源 transport API |
| TRN-09 | 通过（本次范围） | 后端、前端、E2E、构建、类型、Lint、OpenAPI/types 稳定性和 Secretlint 验证完成 |
| E-002 / E-004 | **未通过供应商 Gate；未验证** | 未发真实请求、未申请或使用 Key、未评估当前供应商服务权限／额度／署名 |

### 自动化回归（2026-10-28）

- `backend/`：`uv run --offline pytest -q` → **191 passed**；有 1 条既有 Starlette `TestClient`／httpx 弃用警告。
- `backend/`：`uv run --offline ruff check .` → **通过**。
- `frontend/`：`npm run test:unit -- --run` → **42 passed，7 个测试文件**；`npm run typecheck` → **通过**；`npm run lint` → **通过**。
- `frontend/`：`npm run build` → **通过**；`npm run test:e2e` → **22 passed**（桌面 Chromium 与 Pixel 7）；交通 E2E 在 375px portrait、横屏和桌面视口检查无水平溢出。
- transport 相关 Playwright 场景只拦截 `/api/transport/fares/search` 与 `/api/transport/routes/search`；未 mock 的真实交通请求未发出。
- OpenAPI SHA-256：`64087D8AF88602286B720AB2DFD6183B134D61B0B6905A92564733994F6D7142`；`api-contracts.ts` SHA-256：`21A17B99BDAFD22B4B3E6AAFC6B66E9F3443FB4E1B98A3043746AC38A3F5F174`；重复导出／生成结果字节稳定。
- Secretlint 对 `backend/app`、`frontend/src` 和 `frontend/dist` 扫描通过，无发现；另由后端集成测试验证地点 sentinel 不出现在日志／错误响应中。

## AC 分项映射

| AC | Transport 子项结论 | 全局边界／证据缺口 |
|---|---|---|
| AC-07 酒店与交通 | **契约／交互流程通过**：航班和铁路请求显式出行日、人数、金额单位、计价人数基准、来源及费用包含状态；换乘分段按来源顺序显示，未知金额／余量保留未知。 | **真实交通班次与报价未验证**。E-004 无已核实票价来源；铁路报价不能引用 D-016 用户补填例外作为完成证据。预算中的用户手填路径不等同平台报价。 |
| AC-14 每日时段约束 | **交通资料展示子项有 fake 流程证据**：路线时长及其依据可保留、展示。 | itinerary 时段冲突、路线接续、开放／预约等校验不属于 transport；真实 route duration 未验证，AC-14 整体未完成。 |
| AC-23 地图降级 | **transport 路线缺 geometry 的降级子项通过**：显示文字路线和“不绘制直线或估算路径”；geometry 只作契约数据展示，不画地图。 | 地图／列表联动、真实地图失败和真实路线供应商仍未验证；AC-23 整体未完成。 |
| AC-25 免费边界 | **状态流程通过**：`unconfigured`、`no_coverage`、`rate_limited`、`policy_unavailable`、`unavailable` 可区分；没有付费回退、自动充值或 demo fallback。 | 实际供应商的免费条件、额度、政策、权限和限流均未验证。 |
| AC-28 部分故障与并发 | **Transport 子项通过**：transit／walking／taxi 状态互不覆盖；一个方式失败不清除另外方式结果；条件变更和迟到响应保护均有单测及 E2E。 | 不代表其他模块的并发、旧版本与重复 patch 全局验收通过。 |
| AC-36 Key 与敏感日志 | **本次代码范围扫描／日志测试通过**：`backend/app`、前端源码和构建产物 Secretlint 无发现；集成测试验证地点 sentinel 不进日志／错误体；本轮没有 provider Key。 | 不表示 Git 历史、其他团队／工作区或未来 live-provider 配置已完成全局审计；未来接入时须重跑响应、日志、构建及仓库扫描。 |

## 安全与数据边界

- 交通默认 provider 为空；API client 只请求同源路径，测试按需注入 mock/fake。
- 起终点只作为本次提交的请求字段，不写入 URL 或前端日志；请求 body 不进入服务端日志。
- route 未返回 geometry 时不构造直线；出租车估算保持估算标签；路线金额不会显示为机票／铁路票价。
- `null` 金额显示“金额待核实”，不是 ¥0.00；未知余量显示“余量未知”。测试 fixture 明确标为合成数据。
- 未提交或推送本次代码；没有添加供应商 Key、SDK、缓存、地图依赖或真实请求。

## 可复现入口

- 已批准规格：[SPEC-transport](../SPEC-transport.md)
- 已批准计划与任务清单：[实施计划](../../tasks/transport/plan.md)、[任务清单](../../tasks/transport/todo.md)
- 后端：`backend/app/modules/transport/`、`backend/tests/unit/test_transport_*.py`、`backend/tests/integration/test_transport_api.py`
- 前端：`frontend/src/features/transport/`、`frontend/src/App.test.tsx`、`frontend/e2e/transport.spec.ts`
- 生成契约：`frontend/src/shared/openapi.json`、`frontend/src/shared/api-contracts.ts`

## 未验收与继续条件

1. **真实航班／铁路票价与路线：未接入／未验证。** fixture、fake 和 E2E mock 只证明状态流、契约和界面行为。
2. E-002/E-004 的供应商来源、许可、用途、额度、署名、数据覆盖及隐私条件需另行核实并审批；本记录不提供 live provider、Key 或真实请求授权。
3. 任何 live provider、缓存／限流、非 CNY 展示／换汇、地图 SDK、预算写入、订票／支付／外部跳转都需新增规格门禁、任务范围和用户批准。
4. 本次交通模块流程通过不代表 AC-07、AC-14、AC-23、AC-25、AC-28、AC-36 全局目标或 Web 首版整体完成。
