# weather 实施计划

> 版本：v0.1｜状态：已批准｜批准日期：2026-10-27（北京时间）  
> 对应已批准规格：[SPEC-weather](../../docs/SPEC-weather.md)；依赖已验收的 `foundation`。计划仅覆盖天气能力；批准后仍须建立模块专属任务清单，未获任务清单批准前不得编码或调用供应商。

## 1. 目标与范围

按已批准 `weather` SPEC 提供已注册单城的逐日预报契约、完整／部分／无覆盖表达、服务状态、短期进程缓存、安全来源与时间信息，并提供响应式天气展示界面。

本阶段不实现 recommendations、activities、itinerary 或其他 capability；不接真实 Open-Meteo、不申请账号或 Key、不构造实时天气演示值、不新增外部依赖。真实 provider 只有在 E-001 用途许可／实际接入条件经核实并获得项目负责人批准后，才能通过单独任务实施与启用。

## 2. 前置决策与技术基线

- 保持既有技术栈：Python 3.14.10、FastAPI、Pydantic、httpx；React、TypeScript、Vite；依赖继续由 `backend/uv.lock` 与 `frontend/package-lock.json` 管理。
- 现有通用契约复用 `foundation`：城市 registry、北京时间、`ResultEnvelope`、`Coverage`、`SourceRef`、`PublicError`、request ID；天气专属 schema 位于 `backend/app/modules/weather/`。
- OpenAPI 仍是前端契约来源；不再手工重复定义 provider 输出类型。天气模块 route、公共错误及 schema 变化须重导出 `frontend/src/shared/openapi.json` 并重生成 `api-contracts.ts`。
- 本模块不得新增 SDK、数据库、缓存服务器、付费服务或新的 runtime dependency。天气缓存仅进程内实现；缓存条目不可持久化。
- Open-Meteo 为候选而非已授权供应商。**Gate 0 未通过前，只允许开发 provider protocol、fixture、fake transport、缺失／失败状态和不依赖实时数据的 UI；不得编写、运行或开启真实 adapter。**
- 本规格批准的单次跨度最多 16 个当地日；超限 422，不自动拆批。超出预测覆盖的日期按缺失处理，不是供应商调用参数截断后再伪装完整。

## 3. Gate 0：供应商与用途核验（真实 adapter 的硬门禁）

负责人按台账 E-001 记录并审批：

1. 参赛／公开展示／未来部署是否满足候选 provider 当前非商业许可，数据署名如何呈现；必要时选另一个明确获批的 provider，重新评审而不暗中替换。
2. 五城目标坐标、目标日期及所需 daily variables 的实际返回覆盖；provider 解析的网格位置／高程及 WMO 映射条件。
3. 当前免费额度和 forecast horizon 条件、请求单位计数、用量观测／限流方式；不得只凭文档默认值宣布完成。
4. 是否获准进行受控 live test，以及允许的环境／次数／城市／日期与脱敏证据保存方式。

Gate 0 输出应是有日期、来源、许可结论、实际请求摘要、响应覆盖矩阵及明确负责人批准记录。失败或未完成时，计划只完成 mock/fixture 流程和前端缺失状态；live adapter 与真实能力验收保持 **blocked/not verified**，不自动重试到另一服务或启用付费 endpoint。

## 4. 组件、依赖与顺序

| 顺序 | 组件 | 主要责任 | 依赖 | 检查点 |
|---|---|---|---|---|
| 0 | E-001 provider 资格与真实覆盖门 | 许可、额度、城市／日期覆盖核实；决定候选是否可进入真实适配器任务 | 用户批准 SPEC；外部核验 | 有可追溯书面结果与明确授权；否则保持 mock-only |
| 1 | 天气领域契约与 fixture 集 | Query、WeatherDay、位置元数据、单位、missing_fields、provider normalized payload；完整／部分／错误 fixture | foundation contracts | schema 单测覆盖 null/0、单位／数值、唯一日期与闭区间 |
| 2 | Provider protocol 与 mock | 可注入 provider interface、超时／HTTP 429／403／5xx／bad payload fake | 1 | 默认不联网；调用计数和状态可断言 |
| 3 | 服务归一化、coverage、限时重试与缓存 | 日期对齐、coverage 分割、过去日期缺失、安全错误映射、超时、最多 1 次受限重试、15 分钟 TTL | 1、2 | 固定时钟和 fake transport 验证 coverage、错误与缓存不 stale |
| 4 | API router 与 OpenAPI | POST 请求验证、registry city lookup、response_model 和错误响应；不记录 body | 1、3 | API integration、PublicError / request ID、OpenAPI 校验通过 |
| 5 | 天气 UI 与交互状态 | 逐日卡片／列表，loading／partial／缺失／未配置／限流／故障；显式单位、来源与时刻 | OpenAPI、fixture API client | React 单测与 Playwright desktop/mobile；缺失不用 demo 或过期数据填满 |
| 6 | OpenAPI 同步与模块验收 | 导出 schema、生成 TS types、全回归、secret scan、记录分项 AC 结果 | 1–5；若测真实 provider 还需 Gate 0 | 生成哈希稳定；报告流程测试与真实能力分别判定 |
| 7 | Open-Meteo（条件任务） | 只在 Gate 0 通过后增加受限 adapter、真实请求 smoke 与五城覆盖记录 | Gate 0 与 1–6 | 无 Key 出前端／日志；限定调用预算；实测与 fixture 证据分开 |

依赖图：`1 → 2 → 3 → 4 → 5 → 6`。Gate 0 与 fixture 工作可并行开展，但真实 adapter 7 必须等待 Gate 0 和契约测试完成。UI 仅依赖统一天气服务状态／响应，不直接调用 provider。

## 5. 实施阶段与验证门

### Gate A：契约先行

冻结 WeatherQuery／WeatherDay／WeatherLocationMetadata 与 provider normalized payload；以 fixture 覆盖完整、部分、无覆盖、字段 null、数值非法、未知 WMO 码及返回额外／重复日期。所有业务日期按 `Asia/Shanghai`；实际 provider 时间戳为 UTC；覆盖分区必须完整、无重复／遗漏。

### Gate B：mock-only 服务

注入 fake provider、固定 UTC clock、可控 cache clock。验证每日期唯一、closed interval、过去日期 missing、超 16 天 422 且不调用 provider、provider 失败不回 stale cache、null 与 0 区分、retry 最多一次且只针对批准的瞬时错误。

### Gate C：API 与前端

新增 `POST /api/weather/forecast`，前端仅消费生成类型。表格／卡片显示请求日期和实际覆盖／缺失；状态颜色不能是唯一提示；未知天气码可阅读并不崩溃。响应式检查覆盖 375px 与桌面宽度；键盘可达、标签语义清晰、无水平溢出。

### Gate D：供应商 gate

若 Gate 0 未获批，标记 live adapter／真实 coverage 未实施、未验证，继续只做 mock 测试，不阻塞说明 mock branch 的流程结论。若 Gate 0 获批，另行在任务清单中加入 provider adapter 与受控 smoke task，记录每城、日期段、变量、覆盖／缺失、provider grid point、查询时间和脱敏响应摘要。

### Gate E：集成验收

在任务命令实际创建后运行后端测试／Ruff、前端 ESLint／Vitest／typecheck／build／Playwright、OpenAPI／类型确定性与 Secretlint。按 AC-01、AC-03、AC-06、AC-25 分别列结果；fixture 通过不得替代真实覆盖证据；不以天气模块结果宣称 AC-02 推荐完成。

## 6. 并行边界与资源纪律

- 任务 1 完成前，provider、API 和 UI 不得各自创建不一致天气结构。
- 任务 1 冻结后，fixture／mock 服务与前端静态状态组件可并行；API schema 与前端最终类型同步须串行执行。
- Gate 0 是外部状态依赖；若未通过，不阻塞 mock-only 合同测试，但禁止进入 7。
- 对未获批准的 provider、API Key、网络 endpoint、用量增长、cache persistence、跨城请求或新增包一律不执行。
- 单个实现任务列明文件范围并尽量不超过五个文件；跨任务修改共享 contracts 或 OpenAPI 时先串行合并／验证。

## 7. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| Free API 的非商业许可不适用于项目展示或未来部署 | 可能导致未经许可的数据使用 | Gate 0 先确认用途；未通过则不创建／开启 Open-Meteo live adapter |
| 天气网格点不等于城市行政区中心 | 用户误以为城市全域实况 | 返回并显示网格坐标／来源时间；文案称“城市天气预报”，不称气象站实测 |
| 不同模型／地区字段缺失或预报长度变化 | 误补值、错误将区间显示完整 | 以响应日期对齐，缺项为 null/missing，单独 coverage 分段；不补旧值 |
| provider quota 计数与日期区间呈非线性增长 | 免费额度耗尽或意外调用过多 | 16 日请求上限、无拆批、缓存与请求预算；429 不重试、不付费回退 |
| WMO code 新增或翻译遗漏 | 天气现象显示错误或崩溃 | 保留原码，unknown-safe label；映射 fixture 按版本维护 |
| 供应商数据泄露到日志／错误响应 | 位置、Key 或请求参数泄露 | 结构化脱敏日志、只记录 request ID/status/duration/retry count；fake-secret 测试 |
| httpx TestClient 目前有 Starlette 弃用警告 | 将来测试客户端升级需要处理 | 当前按锁文件运行并将警告记为非阻断；本模块不偷偷新增测试 HTTP 依赖 |

## 8. 完成标准

1. 天气领域/API 契约与 `foundation` 公共状态一致；OpenAPI 生成前后字段、nullability 与错误一致。
2. 100% contract/service/UI 状态测试覆盖 live fixture、partial、no_coverage、unconfigured、rate_limited、policy_unavailable、unavailable、null 字段和无效 payload。
3. 16 日跨度上限、过去日、时区边界、重复／越界日期、provider retry 与 cache TTL 均有正反测试。
4. API／日志不含 raw body、provider secret、绝对路径或原始异常文本；OpenAPI／build bundle 不含 server key。
5. 流程和桌面／移动 E2E 通过，状态及缺失日期可读；OpenAPI/types 二次生成哈希稳定。
6. 真实能力状态按 E-001 证据单独记录。若许可或实际数据未验证，weather 流程 fixture 通过只记流程子项通过，Provider 真实能力标“未验证／未完成”；不得将整个 AC-06、真实天气或 Web 首版标为已完成。
7. 未实现 activities、recommendations、itinerary 联动；调用方可依照公共天气 coverage 自行降级，天气模块不决策推荐。

## 9. 本计划不创建的文件

本轮只建立 `tasks/weather/plan.md` 并记录 SPEC 批准。`tasks/weather/todo.md`、天气实现源码、fixture、前后端 tests、Open-Meteo adapter、供应商配置、依赖清单变更与调用凭证均等待本计划获批后的 Tasks 阶段及其单独审批门禁。

## 10. 审批记录

- 审阅人／日期：用户／2026-10-27
- 结论：批准
- 修改摘要：按 v0.1 计划批准；Open-Meteo live adapter 与真实烟雾测试仍须满足 Gate 0 和单独明确授权。

