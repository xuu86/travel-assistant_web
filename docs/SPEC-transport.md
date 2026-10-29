# SPEC-transport：交通班次、报价与市内路线

> 版本：v0.2｜状态：已批准｜草案日期：2026-10-28（北京时间）  
> 对应已批准模块：Capability Map `transport`。本规格只描述契约和范围；获批后才进入计划。规格批准不等于供应商 Gate、真实 Key、真实调用、费用支付或部署获批。

## 0. 草案假设与重要边界

1. `transport` 按已批准 D-021 拆分两类互不替代的事实：跨城航班／铁路班次与票价，以及公交／地铁／步行／出租车路线。路线距离、用时或路线服务返回的估算金额，不是机票／火车票价。
2. 首版只做查询与展示，不预订、不支付、不跳转售票平台（D-025）。不存在可验证供应商时返回明确未配置／不可用状态；生产运行不返回演示数据，也不把缓存旧结果冒充新查询。
3. 交通报价服务目前没有已验证的免费班次／票价来源（E-004）；高德路线权限、额度和适用条件未验证（E-002）。任何 live adapter 和真实请求均须有单独的供应商 Gate 与明确授权；本 SPEC 不构成该授权。
4. 本版本已冻结 `transport` 的 `Q-017` 口径：航班／铁路请求必须显式携带目标出行日期，不以系统当天静默替代；交通模块不自动把该日期与 itinerary 日期强制绑定，也不以 itinerary 日期覆盖用户输入。若后续 itinerary 需要严格日期一致性，由其边界契约另行校验。
5. 儿童票年龄规则、人数上限、巴士票价范围和报价缓存 TTL／限流（Q-006、Q-014）均未确认；查询可选传递儿童人数，但不推断票种／年龄资格，也不臆造产品上限、报价新鲜度期限或平台覆盖。
6. route geometry 只接受 provider 实际返回的 WGS84 坐标；缺少 geometry 时保留可读文字信息并标注地图路线待核实，不自行插值画线。
7. 规格默认预算与可汇总报价沿用 CNY 整数分；是否首版还要展示非 CNY 原始票价尚未确认。不得把外币数字直接放进 `price_fen` 或在没有获批汇率／舍入契约时自动换算。

## 1. 元数据

- **模块 ID：** `transport`
- **负责人角色：** 开发负责人；外部能力由数据集成负责人核实
- **关联决策：** D-001、D-002、D-006、D-008、D-012、D-021、D-022、D-025、D-026、D-027、D-030、D-031
- **关联待办：** Q-006（乘客数等业务限制）、Q-009（生产 demo 语义）、Q-014（TTL／额度／限流）、Q-017（报价日期语义）
- **关联外部核实：** E-002（高德路线 API 权限／额度／来源）；E-004（机票／铁路班次与票价来源）
- **关联验收：** AC-07、AC-14、AC-23、AC-25、AC-28、AC-36；预算费用输入与 AC-08、AC-09、AC-10 协作
- **依赖模块：** `foundation`
- **被依赖模块：** `budget`（仅已确认费用候选／来源属性）、`itinerary`（路线时间与行程约束）、`maps`（路线呈现）；不拥有地图底图或行程修改

## 2. Objective 与范围

### 目标

用户能分别查看跨城交通班次／票价和城市内路线信息，识别每条结果的来源、查询时间、行程日期、计价单位与未知字段；未配置、失败、无结果或不覆盖时不编造交通事实。

### 首版包含

- 单程跨城交通查询契约，支持航班和铁路／高铁候选；返程作为另一次显式目标日期查询，不假设往返价格能组合。
- 成人数量、可选儿童数量以及报价的金额、币种、计价基准、已包含／不含／未知费用项、可用性和来源字段；查询总人数为成人与儿童之和，儿童票资格和价格只以 provider 规则为准。
- 城市公交／地铁、步行及出租车／驾车路线查询契约；各出行方式独立返回状态，单方式失败不阻断其他方式。
- 路线摘要的距离、预计耗时、分段文字指引、可选费用信息，以及可选的 provider 路线几何；路线和票价使用不同 schema 与来源语义。
- Foundation `SourceRef`、`EvidenceState`、`ResultEnvelope`、公共错误和 request ID；金额沿用整数分与 CNY，缺失报价为 `null` 而非 0。
- 查询时间和“票价及余量可能变化”提示（D-030）；具体有效期只能在 provider 明确返回时展示，不能由 UI 推断。
- 响应式交通查询结果、加载／未配置／失败／无结果／部分字段缺失状态；改变请求条件后不继续展示旧查询结果。
- fake provider／合成 fixture 测试与供应商隔离；默认运行配置无 provider，绝不静默 fallback 到 fixture。

### 首版不包含

- 真实航空公司／铁路售票、支付、下单、改签、退票、余票锁定、订票跳转或自动选择“最便宜／最适合”班次。
- 任何未经 Gate 核实和授权的 live provider、API Key、地理编码、线路请求、交通数据抓取或供应商额度消耗。
- 以直线距离、城市中心连线、模型生成步骤或 fixture 代替真实路线；路线图绘制归 `maps`，行程安排和锁定保护归 `itinerary`。
- 由交通报价直接生成／扣减预算、创建预订或覆盖用户输入；用户确认后的费用进入 budget 的独立契约。
- 自动把火车／巴士路线估算称为可购买的车票价格；不把出租车估算称为实收车费。
- 用户账户、owner scope、服务端持久化、IndexedDB、位置历史、跨设备同步、模型请求或遥测记录。
- 城市之外未经确认的多城市行程编排、实时导航、实时位置跟踪、地图底图。
- 未经确认的乘客年龄／票种、人数或费用上限、报价 TTL、调用次数或 provider-specific 配额。

## 3. 输入输出契约

所有请求为 JSON；日期在线路中使用 `YYYY-MM-DD` 的日历日期字符串，有时区时间使用 RFC 3339 字符串；contract 显式解析为 date／datetime，拒绝无效日期、无时区 datetime 和额外字段。金额使用非负整数分与 `CNY`；拒绝 bool／float 金额和不完整经纬度对。Foundation 会将有时区时间归一到 UTC；前端需在展示时保留供应商／地点的当地时区语义。Route 坐标若存在使用 WGS84。

### 3.1 跨城班次／报价查询

建议端点：`POST /api/transport/fares/search`。每次只查一个方向、一个目标出行日期和一种交通方式；往返由调用方提交两次请求。

| 字段 | 类型 | 必填 | 空值语义 | 校验 | 来源／权限 |
|---|---|---:|---|---|---|
| `origin` | `PlaceRef` | 是 | 不允许空对象 | 有稳定城市／地点 ID 时传 ID；否则需明确提供地点名称；不以城市中心静默代替地点 | 用户或调用方；可含用户位置 |
| `destination` | `PlaceRef` | 是 | 不允许空对象 | 同 origin；必须与 origin 不同（调用方语义确认） | 用户或调用方 |
| `mode` | `flight` / `rail` | 是 | 不允许为空 | 一个请求只指定一个 mode | 用户选择 |
| `travel_date` | date | 是 | 不允许为空 | 必须是显式查询日期；是否强制等同 itinerary 日期按 Q-017 冻结 | 用户选择／itinerary |
| `passenger_count` | 正整数 | 是 | 成人与儿童总人数 | 不设置未经确认的业务最大人数；provider 不支持时返回明确状态 | 用户输入 |
| `child_count` | 非负整数或 null | 否 | 可选儿童人数；不得大于 `passenger_count` | 不推断儿童年龄、免票条件或票价 | 用户输入 |

`PlaceRef` 建议字段：`place_id: string | null`、`display_name: string`、`latitude: number | null`、`longitude: number | null`、`coordinate_system: "WGS84"`。经纬度必须同时为空或同时有效；不得将模糊文本 geocode 成 verified，除非真实 provider 响应提供来源和状态。

`FareOffer` 建议字段：

| 字段 | 类型 | 可空 | 语义 |
|---|---|---:|---|
| `offer_id` | string | 否 | 此次响应内可追溯 ID，不保证跨次稳定 |
| `source_id` | string | 否 | 必须对应 envelope `sources[]` 中唯一 `SourceRef.source_id`，保证每个报价可追溯 |
| `mode` | `flight` / `rail` | 否 | 结果交通类型 |
| `travel_date` | date | 否 | 对应请求的显式目标出行日；不能用 `queried_at` 日期替代 |
| `segments[]` | `FareSegment[]` | 否 | provider 返回的实际乘行分段；direct 结果也保留一个 segment；不得由 transport 合成换乘路线 |
| `service_number` | string | 是 | 航班号／车次；缺失不推断 |
| `departure_at`、`arrival_at` | timezone-aware datetime | 是 | provider 返回的班次时刻；输出 UTC 规范值，缺失仍为 null |
| `departure_timezone`、`arrival_timezone` | IANA timezone string | 是 | 仅 provider 明确给出／可核实地点映射时返回 |
| `origin_name`、`destination_name` | string | 否 | provider 返回或用户查询地点显示名；不可冒称站点已核实 |
| `price_fen` | 非负整数分 | 是 | 仅表示 CNY 整数分报价；null 表示金额未知，0 只能表示来源明确的零价；其他币种不可塞入此字段 |
| `currency_code` | string | 否 | ISO 4217 代码；v0.2 暂仅定义 CNY 金额运算，非 CNY 展示策略列为待确认；不得静默换算或混加 |
| `price_basis` | `per_passenger` / `party_total` / `unknown` | 否 | 金额对应单人、所选人数合计或来源未说明 |
| `passenger_count` | 正整数 | 否 | 对应查询人数，不把单人价误当团队总价 |
| `included_charges[]` | `ChargeComponent[]` | 否 | 税费／行李等每项说明包含状态、金额与适用计价基准；未返回不等于 included |
| `availability` | `available` / `unavailable` / `unknown` | 否 | 只反映 provider 提供的状态；不构成余票锁定保证 |
| `remaining_seats` | 非负整数 | 是 | 只在来源实际返回时提供；不将 null 解释为无票／不限量 |
| `evidence_state` | foundation `EvidenceState` | 否 | 保持来源等级；不可由 transport 升级 |

`FareSegment` 最少含 `segment_id`、`origin_name`、`destination_name`、`departure_at`、`arrival_at`、`departure_timezone`、`arrival_timezone`、`service_number`，以及 provider 有提供时的 `operating_carrier`、`transfer_place`。segments 数组顺序即 provider 的乘行顺序，不由 transport 重排。时间必须带时区并规范为 UTC，同时保留 IANA 当地时区；缺少的分段时刻／站点留空，不由上层推算。Offer 顶层出发／到达时间分别表示旅程首段离发与末段到达；多段 offer 的顶层 `service_number` 设为 null，不能拼成虚构的单个车次。Offer 总价语义应明确是所列分段合计还是单段价；不能把每段价格再次相加造成重复计费。

`price_basis=per_passenger` 表示报价仅对应一位乘客，UI 必须标单人价，不自动乘以查询人数；`party_total` 必须明确对应请求中的同一 `passenger_count`；`unknown` 不得推导个人／团队总价。`child_count` 只记录用户查询构成，不能推断年龄、具体票种、儿童票资格或儿童票价。

`ChargeComponent` 最少含 `charge_type`、`display_name`、`inclusion_state: included | excluded | unknown`、`amount_fen: int | null`、`currency_code`、`amount_basis: per_passenger | party_total | unknown`。金额非空时必须是非负 CNY 整数分；金额为 null 时不得展示 0。排除项的实际金额未知时保持 null，不能从总价倒算；多乘客展示必须明确单人还是所选人数合计。provider 未提供某费用项目时不得自行补充或声称已包含。

响应建议为 `ResultEnvelope[FareOffer]`。空结果、未覆盖、未配置、限流、政策限制和服务错误需明确区分；每个 offer 的 `source_id` 必须匹配 envelope `sources[]`。若 provider 仅提供非 CNY 金额，按待确认的币种范围规则拒绝将其当作 CNY 票价或预算输入，并显示价格能力不可用／待核实，不可静默丢失其币种语义。

### 3.2 市内路线查询

建议端点：`POST /api/transport/routes/search`。每次请求查一种方式，以便各方式独立报告故障；客户端可分别请求 `transit`、`walking`、`taxi`，但不得因一条失败抹掉其他成功结果。

| 字段 | 类型 | 必填 | 空值语义 | 校验 | 来源／权限 |
|---|---|---:|---|---|---|
| `origin`、`destination` | `PlaceRef` | 是 | 不允许为空 | 坐标／地点名称满足 PlaceRef 契约；不使用直线替代路线 | 用户、itinerary 或已确认地点 |
| `mode` | `transit` / `walking` / `taxi` | 是 | 不允许为空 | `transit` 包含 provider 明确返回的公交／地铁分段；不把交通类型猜成结果 | 用户选择／调用方 |
| `depart_at` | timezone-aware datetime 或 `null` | 否 | null 表示不指定出发时间；结果不可声称按实时交通计算 | 有值必须带时区；规范为 UTC | 用户／itinerary |

`RouteOption` 建议字段：`route_id`、`source_id`、`mode`、`origin_name`、`destination_name`、`distance_m: int | null`、`duration_seconds: int | null`、`duration_basis: realtime | scheduled | typical_estimate | unknown`、`steps[]`、`geometry_points[] | null`、`fare_amount_fen: int | null`、`currency_code`、`fare_basis: per_route | per_passenger | meter_estimate | unknown`、`fare_evidence_state`、`evidence_state`。`source_id` 必须匹配 envelope 中的 SourceRef。`duration_seconds` 未知时为 null 且 basis 为 unknown；没有实时交通依据不得标记 realtime。`RouteStep` 可含 provider 指引文本、明确的 `step_mode`（步行／公交／地铁／铁路／出租车等仅在 provider 提供时标记）、距离／耗时和起终点坐标；每个缺失字段保持 null。无 fare 时金额为 null 且 basis 为 unknown；不得由路线长度／直线距离估价。出租车金额若 provider 仅给估算，必须保留 `estimate` 和 `meter_estimate` 并显示估价属性；必须清楚说明金额对应一车／一人／未知，不能按乘客人数自动乘除。

响应建议为 `ResultEnvelope[RouteOption]`；结果来源和查询时间必填。空 geometry 不影响文字路线展示，但应明确指出地图线路未提供；无 RouteOption 不代表起终点无路可走，除非 provider 能确认并给出状态证据。

### 3.3 共用输出与状态

| 字段 | 类型 | 语义 |
|---|---|---|
| `state` | Foundation `ResultState` | `live`、`partial`、`empty`、`unconfigured`、`no_coverage`、`rate_limited`、`policy_unavailable`、`unavailable` 等保留其原义；`demo` 仅测试 fixture，默认应用不可输出 |
| `items` | offers／routes 列表 | 只含当前请求已返回结果；状态或 query 变化即清除旧结果 |
| `sources` | `SourceRef[]` | 每个结果来源 ID 必须有对应元数据、查询时间和 evidence_state |
| `queried_at` | UTC datetime | 此次查询时间；不能拿缓存写入时间冒充供应商查询时间 |
| `coverage` | `Coverage | null` | 仅 provider 支持日期覆盖时填写；null 表示未提供，不表示全覆盖 |
| `request_id` | UUID | 与 HTTP `X-Request-ID` 一致；日志可用来关联，不含地点或金额 |

状态一致性约束：`live` 至少含一个满足本 SPEC 必填字段且可展示的 item；`partial` 必须含一个或多个 schema 合法的可用 item，并标明缺失字段／信息；`empty` 与 `unconfigured`、`no_coverage`、`rate_limited`、`policy_unavailable`、`unavailable` 均不得含 items。`partial` 不能代替无结果或整体 provider 故障。

报价输出不自动转换为 budget `CostItem`；如用户选择记录，调用方必须明确单位、乘客数、含费项和证据等级，再由 budget／itinerary 负责确认与关联。

## 4. 状态与错误

| 状态／错误 | 触发条件 | 用户提示 | 可重试 | 是否返回部分结果 |
|---|---|---|---:|---:|
| `unconfigured` | 对应票价／路线 provider 缺配置或未启用 | 当前交通查询尚未配置；不表示没有班次或路线。费用如需手工录入，走 budget 已批准的用户输入流程 | 配置后由用户重新查询 | 否 |
| `no_coverage` | provider 明确说明该交通方式／地区／日期不覆盖 | 当前来源未覆盖此条件；不代表没有班次或道路 | 改查询条件后可重试 | 否 |
| `empty` | provider 正常查询且确实返回空列表 | 本次查询未返回结果；不推断不存在 | 用户可主动重查 | 否 |
| `partial` | provider 返回一个或多个可用 offer／route，但部分字段、含费信息或 geometry 缺失 | 明确列出缺失字段并保留可用项目 | 可由用户主动重新查询 | 是；必须至少有一个合法 item |
| `rate_limited` | provider 返回额度限制 | 查询受额度限制；不自动切供应商或购买额度 | 遵守 provider 允许频率后用户重试 | 否 |
| `policy_unavailable` | 账号资格、用途政策、API 权限不允许 | 服务权限／政策暂不可用 | 权限确认后重试 | 否 |
| `unavailable` | 超时、服务端故障或无效 provider 响应 | 交通服务暂不可用 | 用户主动重试；不得无限重试 | 否；Foundation ResultEnvelope 禁止该状态携带 items |
| `VALIDATION_ERROR` | 无效日期、空地点、经纬度不完整、非法方式、负金额／非法金额单位 | 请检查查询地点、日期和交通方式 | 修正后可重试 | 否 |
| `INTERNAL_ERROR` | 未预期内部错误 | 通用错误与 request ID；不泄漏堆栈 | 有限、由用户触发 | 否 |

业务无结果使用成功 HTTP 响应中的 ResultEnvelope 状态；契约非法使用 foundation 公共错误响应。若 provider 返回可用且 schema 合法的部分数据，必须用 `partial` 并附缺失说明；若数据无法安全解析或 provider 整体失败，则用 `unavailable` 且 `items=[]`。不得把 `empty` 改写为“确定不存在”，也不得把 `unavailable` 转成 demo 结果。

## 5. 权限、隐私与数据保留

- 本模块不实现身份验证／owner scope、不持久化查询历史、不保存精确位置轨迹；请求处理只使用本次提交的起终点信息。
- 起终点名称和坐标可能是敏感位置信息；不记录请求 body、经纬度、用户地址、乘客信息、服务号或票价到应用日志、遥测、URL、前端 console、E2E trace／截图。
- 请求日志仅沿用 foundation 的 request ID、路由名、状态和耗时；错误和返回文案不得泄露 provider 原始响应、Key、URL query 参数或个人数据。
- 所有 provider 凭证仅允许服务端 secret 配置；禁止 `VITE_*`、源代码、fixture、OpenAPI、前端 bundle 和截图含 Key。
- 在供应商权限、条款、隐私传输、展示署名、额度和服务内容未核实前，不得启用 live provider；必须先记录 Gate 证据和批准范围。
- 不发送云端模型；不收集乘客姓名、证件号、支付信息、手机号或完整预订凭据。预算录入由 budget 单独接收用户确认的金额，不复制原始订票信息。
- 无服务端存储，无清理作业；取消请求后忽略迟到响应，页面状态不可被旧响应覆写。

## 6. 业务规则与不变量

1. 机票／铁路班次与城市公共交通／步行／出租车路线是不同数据类型；路线距离、用时或预计费用不能冒充售票报价（D-021）。
2. 每个结果都保留查询时间、来源、日期、单位与 evidence_state；未知班次、价格、税费、余量和路线字段用 null／unknown，不得默认填 0 或 “免费”。
3. 票价金额须显示计价基准（单人或所选乘客总计）与人数；未返回含费项时标 unknown，不能声称含税／含行李／含服务费。
4. 任何返回报价都显示查询时刻和价格／余量可能变化的提示；不得在来源无 TTL 时编造“有效至”时间（D-030）。
5. `travel_date` 必须来自显式用户／调用方输入；Q-017 关于是否必须与 itinerary 日期绑定，批准前保持开放，不得静默使用“今天”。
6. 各 mode 独立请求与结果；单一供应商失败不得清除其他已成功交通方式结果（AC-28）。
7. 用户改动地点、日期、人数或方式后清除与旧条件不符的结果；取消或新请求发起后忽略之前的迟到响应。多个交通方式并行显示时，各 mode 维护独立请求状态和 request ID；一个 mode 失败只替换该 mode 状态，不清除其他 mode 的成功结果（AC-28）。
8. 未返回道路几何时不画路径；无真实路线时不以 WGS84 两点连线、模型文本、POI 顺序或 fixture 对用户展示“真实路线”（D-022、AC-23）。
9. 不按两点直线估算公交／步行／出租车距离和耗时；如 provider 给出租车估价，保持 `estimate` 和当地单位，不当作收取金额。
10. 免费 provider 不可用、限流或政策未确认时明确显示状态，不自动付费、充值、回退到另一个计费平台或 demo（D-012、AC-25）。
11. `demo` 只用于明确标注的测试输入／fake provider，不在默认应用运行路径中启用（Q-009 待产品决定正式 demo policy）。
12. 交通模块不创建预算费用、修改已锁定预订或应用 itinerary ChangeSet；用户确认费用时再交由相关模块处理。
13. Provider 响应当作不可信数据校验；不执行返回 HTML／脚本，不把内部错误或原始供应商响应直接回传。
14. Offer／RouteOption 的 `source_id` 必须引用同一响应 envelope 中的 SourceRef；source 不完整或无法映射时不得显示为已核实结果。
15. 机票用户补填价格属于 D-016 的用户输入例外，保留在 budget 人工费用流程中并标明“用户填写，非平台报价”；不得把该录入转成 provider FareOffer 或扩大到铁路票价／路线缺失的阶段验收豁免（D-031）。

## 7. 依赖与配置

- **内部依赖：** Foundation `SourceRef`、`ResultEnvelope`、`EvidenceState`、`Coverage`、`PublicError`、城市 ID、request ID 和 UTC 时间规范。
- **查询消费者：** `itinerary` 可使用已核实的交通时段、路线 duration/segments 和来源；`maps` 可消费明确来自真实 provider 的 route geometry；`budget` 仅接收用户确认且有币种／单位语义的金额。
- **候选外部服务：** E-002 高德 Directions（权限、用途、额度、响应单位与署名均须实时核验）；E-004 机票／铁路真实班次票价目前没有已验证的免费来源。不得未经核实指定供应商或写入 Key。
- **环境变量：** 暂无已批准 live provider；若后续 gate 通过，在任务计划中单独列环境变量名、来源、部署方式和 fail-closed 行为，不在本 SPEC 或代码样例中填凭证。
- **重试／缓存／限流：** Q-014 待决。首版不得无限重试或自动跟随多个 provider；缓存和请求合并策略须在 provider 适配器计划前定出可测额度与过期语义。来源时间缺失不得凭缓存时间补造。
- **时间／地理：** 出发／到达时间必须含时区；坐标 WGS84；原始 provider 当地时区与展示转换需要保留来源语义。路线耗时须说明 realtime、scheduled、typical estimate 或 unknown；无法证明实时交通时不得标为 realtime。
- **测试替身：** FakeFareProvider、FakeRouteProvider、固定 UTC 时钟、合成地点与班次；所有测试默认禁网，fake 结果保留 `demo` evidence 并仅通过测试注入。

## 8. 项目结构与代码风格

计划阶段确认实际文件范围，候选如下：

```text
backend/app/modules/transport/
  __init__.py
  contracts.py
  service.py
  router.py
  providers/base.py
backend/tests/unit/
  test_transport_contracts.py
  test_transport_service.py
  test_transport_provider_mapping.py
backend/tests/integration/
  test_transport_api.py
backend/tests/fixtures/transport/
  fares.json
  routes.json
frontend/src/features/transport/
  api.ts
  TransportPanel.tsx
  transport-panel.css
  TransportPanel.test.tsx
frontend/e2e/transport.spec.ts
docs/acceptance/transport.md
```

- 后端沿用 CPython 3.14、FastAPI、Pydantic strict schema、pytest 和 Ruff；provider adapter 通过 Protocol／接口隔离，纯映射和状态归一逻辑不写在 router。
- 前端沿用 React + TypeScript + Vite、Vitest、Playwright 和 ESLint；API 类型由 FastAPI OpenAPI 生成，不手写重复契约。
- 金额字段统一 `_fen` 后缀；时间带时区并转换 UTC；坐标显式标 `WGS84`；状态使用 foundation 枚举或 transport 的窄枚举。
- Route directions 作为纯文本转义展示；不得将 HTML 直接插入 DOM。金额、来源与“估算／待核实”标签相邻，状态不只依赖颜色。

示例（provider 适配层的协议形状，非真实 provider 实现）：

```python
class RouteProvider(Protocol):
    def search_route(self, query: RouteQuery) -> ResultEnvelope[RouteOption]: ...
```

## 9. 命令

以下为任务阶段的目标验证命令；候选文件尚不存在，当前不能作为已执行结果。前端实际 Node/npm 需按项目既有 `%LOCALAPPDATA%\AIWebChallenge\runtime\node-v24.22.1-win-x64` 环境调用 `npm.cmd`。

```powershell
# backend/
uv run pytest tests/unit/test_transport_contracts.py tests/unit/test_transport_service.py tests/unit/test_transport_provider_mapping.py -q
uv run pytest tests/integration/test_transport_api.py -q
uv run ruff check app/modules/transport tests/unit/test_transport_contracts.py tests/unit/test_transport_service.py tests/integration/test_transport_api.py
uv run pytest -q

# frontend/
$node = Join-Path $env:LOCALAPPDATA 'AIWebChallenge\runtime\node-v24.22.1-win-x64'
$env:Path = "$node;$env:Path"
npm run generate:api
npm run typecheck
npm run lint
npm run test:unit -- --run src/features/transport
npm run build
npm run test:e2e -- --grep transport
```

完整回归另需执行 Secretlint 工作区和 `dist` 扫描；没有 live Gate 批准时自动化测试禁网，E2E provider responses 必须显式 route mock。

## 10. 测试案例与验收

| 场景 | 输入／前置 | 预期 | 测试层级 | 证据 |
|---|---|---|---|---|
| 航班／铁路正常结果 | fake response 含班次、人数、单人价格、来源与取数时刻 | 字段保持原单位；逐项显示来源、含费状态和价格变化提示；fixture 明确为测试数据 | contract + API + UI | 合成 JSON、测试报告 |
| 换乘分段 | provider 返回多个真实分段及每段时刻／站点 | 分段次序和来源原样保留；总价计价基准清晰，不重复累计各段金额 | contract + service + UI | 参数化合成响应 |
| 计价单位未知 | 金额存在但 provider 未给 per-person/party basis | basis 为 unknown；UI 不乘人数，不伪称总价 | unit + UI | schema assertion、截图 |
| 金额与余量未知 | fare/seat 为 null | 待核实／未知，不显示 0 元或无余票 | contract + E2E | 响应和页面状态 |
| 目标日期 | travel_date 非今天且 provider 返回对应班次 | 输出保留查询日期、查询时间；不把“查询时间”充作出行时间 | API + UI | 合成请求响应 |
| Q-017 日期边界 | 查询日期和 itinerary 日期不一致 | 在产品决定批准前不宣称日期匹配；条件差异明确提示 | contract + UI | 决策记录／测试 |
| 路线模式隔离 | transit 成功、walking unavailable、taxi success | 各 mode 独立状态／request ID；单方式失败不影响其他 mode 的结果；可分别重试 | frontend integration + E2E | fake provider 调用记录 |
| 无 geometry | provider 只返回文字 steps | 文字路径可读；地图线条标待核实／不可用，不自行连线 | contract + UI + maps contract | fixture、截图 |
| route fare 估算 | 出租车返回 estimate 金额 | 标签保持“估算”，不得当作已收车费或 verified fare | contract + UI | 状态断言 |
| provider 无配置 | 默认应用运行且未配置 provider | `unconfigured` 空列表；不自动发网请求、不显示 demo | integration + E2E | 请求捕获、页面截图 |
| 无覆盖／无结果 | provider 分别明确 no_coverage 或 empty | 状态和文案不同；均不宣称全国无班次／道路不存在 | service + UI | 状态测试 |
| 改条件／慢响应 | 旧请求迟到，新地点／日期已提交 | 旧响应不可覆写新状态；新请求前清除旧结果 | frontend unit + E2E | 可控 promise 测试 |
| request privacy | origin/destination/price sentinel 与假 Key | 日志、错误、trace 和前端 bundle 不含请求 body／Key；ID 可关联 | integration + Secretlint | 脱敏扫描与日志断言 |
| 来源完整性 | offer/route 的 source_id 不存在于 envelope.sources | 响应校验失败或结果降为不可用；不可展示无来源的 verified 事实 | contract + API | 反例测试与公共错误断言 |
| 安全输入 | 坐标单边缺失、越界、额外字段、负／float fare | strict validation failure；无 provider 调用 | contract + API | 参数化测试 |
| 移动与键盘 | 375px／桌面、键盘和 reduced motion | 无横向溢出；标签、状态和来源能被屏幕阅读器感知 | unit + E2E | Playwright 结果／截图 |

**验收映射：** AC-07 的交通子项（班次／报价、日期、单位、人数、包含项分离）；AC-14 的 route duration／时段事实供 itinerary 校验，不能单独宣称 itinerary 通过；AC-23 的路线 geometry 数据契约与地图失败边界由 maps 完成最终验收；AC-25 的未配置／额度／政策状态和无付费回退；AC-28 的分方式失败隔离；AC-36 的 Key 与敏感日志。AC-08 用户补填的机票金额可以由 budget 承接，但不证明平台航班报价。AC-07/14/23 要求真实事实的部分在无 provider Gate 证据时须记为阻塞或部分通过，不能用 fixture 宣称真实能力完成。

**通过门槛：** 契约正反例、不同交通事实类型、unknown/null/0、时间单位、来源、mode 故障隔离、位置隐私、默认未配置、桌面/375px 键盘体验均通过；API 类型同步稳定；AC 流程证据与真实供应商证据分开报告。

## 11. 风险、开放问题与批准记录

| 风险／问题 | 影响 | 缓解 | 需要谁决定 | 状态 |
|---|---|---|---|---|
| Q-017：机票报价是否必须用实际出行日期检索 | 可能出现日期错配报价 | 请求显式包含 travel_date；transport 不静默使用查询当天或覆盖用户日期；itinerary 的跨模块严格绑定另行决定 | 项目负责人 | transport 已冻结；hotels／跨模块口径仍待决 |
| E-004：免费真实机票／铁路票价接口 | 可能无合法／稳定实时票价来源 | 保持 unconfigured；无供应商 Gate 前只做缺失状态和 fake 流程 | 数据集成负责人／项目负责人 | 未找到已验证方案 |
| E-002：路线 API 权限与额度 | 未授权请求、Key 泄露或超过额度 | 请求前核实服务类型、账号资格、Key 域策略与限额；Key 仅服务端 secret | 数据集成负责人 | 待核实 |
| Q-014：报价缓存 TTL／请求预算 | 旧价格误导或重复消耗额度 | UI 显示 queried_at 与变化提示；provider adapter 前另行批准 TTL、并发和限流参数 | 项目负责人／数据集成负责人 | 待决 |
| 乘客价格单位及费用包含项 | 人数乘错、遗漏税费或行李费 | 强制返回 basis 与每个 charge 状态；未知不推算 | 开发负责人 | 草案规则，待审阅 |
| Route geometry 资源与地图坐标转换 | 超大响应、绘制错位或虚假路线 | WGS84 约束；资源限制由 plan 定可测值；maps 只画真实 provider geometry | 开发负责人 | 待计划 |
| 城市／站点地点歧义与隐私 | 错选站点或泄露居住地址 | 地点明确显示并由用户确认；日志不记坐标／名称；不将默认城市中心当始发点 | 项目负责人／开发负责人 | 草案规则，待审阅 |
| Q-006：产品人数与日期范围上限 | 旧草稿约束被误当业务要求 | 不抄写历史上限；provider 约束以明确错误显示并记录，不静默裁剪 | 项目负责人 | 待决 |
| 非 CNY 机票／铁路报价是否属于首版 | CNY-only 会隐藏外币报价；外币自动换算会产生汇率、时间与舍入新规则 | v0.2 暂不转换／汇总外币；请确认首版是否严格 CNY-only，或另批原币展示字段及其精度契约 | 项目负责人 | 待决，草案假设待审阅 |

### v0.2 草案修订记录

- 补充 offer／route 到来源元数据的显式关联与班次分段契约。
- 将 `unavailable` 的 items 语义与 foundation ResultEnvelope 约束对齐；合法部分结果用 `partial`。
- 明确机票用户补填只走 D-016 budget 路径，不扩大铁路票价／路线的阶段验收范围。
- 将非 CNY 报价范围显式列为产品待决问题；不在规格中隐式换算。
- 补充税费／行李费与路线估价的数据字段、计价基准和 `partial` 状态一致性要求。

批准记录：

- 审阅人／日期：用户／2026-10-28（北京时间）
- 结论：批准
- 修改摘要：批准 v0.2；采用显式 `travel_date` 提案，不以系统当天静默替代，也不自动强制绑定 itinerary 日期。非 CNY 展示、Q-014 缓存／限流、Q-006 业务上限以及 E-002／E-004 供应商能力仍保持原有待决或未核实边界；本批准不授权 live provider、Key、真实请求、支付或订票。

## 12. 三层边界

- **Always：** 交通班次报价与路线拆分；来源、查询时间、日期、人数、币种、计价基准、含费项和 unknown/null 保留；无路线 geometry 不画线；供应商状态真实呈现；更新查询后不留旧结果；金额使用整数分。
- **Ask first：** 新增 live provider／Key／供应商条款、缓存 TTL／限流、真实请求测试、乘客类别／业务上限、转换币种、额外外部数据共享、自动路线选择或交易／跳转能力。
- **Never：** 用直线冒充路线；用公交／步行／出租车路线冒充航班／铁路票价；把 null 变 0 或 unknown 变“没有”；将 estimate/demo/user-provided 升级为 verified；静默回退 demo／收费服务；记录精确地址、坐标、乘客资料或票价到日志；预订／支付／退款或改写锁定行程。
