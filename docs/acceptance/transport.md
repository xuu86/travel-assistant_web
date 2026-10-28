# Transport 验收记录

> 日期：2026-10-28（北京时间）  
> 范围：已批准的 `SPEC-transport` v0.2、transport 任务 TRN-01 至 TRN-09；**fake-only 流程验收**，不代表真实航班、铁路或路线服务已经接入或验证。

## 结论

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
