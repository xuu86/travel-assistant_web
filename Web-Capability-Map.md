# Web Capability Map

> **状态：已批准｜版本：v0.4｜批准日期：2026-10-27；`destination-workspace` 增补批准：2026-10-28**  
> 本图稳定 Web 首版模块 ID、职责边界、依赖方向和分层顺序。各模块仍须单独完成 SPEC 审阅；地图获批不等于模块规格、计划、任务或实现获批。

| module id | 责任边界 | 依赖 |
|---|---|---|
| `foundation` | 配置、共享契约、来源／错误状态、北京时间、城市和坐标注册表 | — |
| `destination-workspace` | 目的城市前置选择、当前工作区上下文和 budget/weather/transport 视图编排；不拥有各模块业务规则 | foundation、budget、weather、transport |
| `weather` | 天气查询、请求日期和实际覆盖范围 | foundation |
| `transport` | 机票／铁路信息与报价、市内路线和费用属性；报价和路线分开 | foundation |
| `hotels` | 酒店地点资料与特定日期报价分开 | foundation |
| `activities` | 有有效日期、来源和状态的当地活动 | foundation |
| `attractions` | 景点／地标及开放、预约字段的核实状态 | foundation |
| `imports` | 上传会话、本机解析／OCR、候选与证据、确认、去重、清理 | foundation、auth |
| `budget` | 费用 ID、支付拆分、用户预留、来源、完整性和超预算判断 | foundation |
| `assistant` | 模型供应商适配、自然语言理解和候选变更，不直接提交业务状态 | foundation |
| `recommendations` | 天气／活动城市推荐、附近城市、图片降级 | foundation、weather、activities |
| `itinerary` | 单城市日程、时段／事实约束、锁定保护和 ChangeSet 原子应用 | 上述查询、imports、budget、assistant |
| `auth` | 游客会话和五个测试账号校验，提供稳定 owner scope | foundation |
| `local-storage` | IndexedDB 行程与凭证分区、版本和删除 | auth、itinerary |
| `maps` | 地图展示和日程联动；不拥有路线查询 | itinerary、transport |
| `exports` | 用户主动打印 PDF，输出费用与事实状态 | itinerary、budget、local-storage |

## 当前实现状态（2026-11-04）

本图描述目标模块边界，不代表模块已交付。当前 Web 已有 foundation、destination-workspace、weather、transport（机票/铁路/路线查询流程）、budget、assistant 和 itinerary 的部分实现；状态边界如下：

- 天气：Open-Meteo adapter 已实现；2026-10-29 完成五个注册城市各一次、单日真实连通性检查。该快照不证明持续可用、精度、未来覆盖或公网/商业使用资格，见 [天气 Provider 验收](docs/acceptance/weather-provider.md) 与 [Gate](docs/weather-provider-gate.md)。
- 交通：Amadeus 航班 adapter 已实现但真实航班数据未验收；FlyAI 官方 CLI 铁路 provider 已接入，2026-10-31 完成本地真实 API 查询，票价与余票保持未知；市内公交、地铁、步行及出租车路线仍无 provider。
- 酒店、活动、景点和地图：高德 Web 服务 POI/静态地图代理、四个后端路由、前端搜索工作区、分页、选点联动、地图缩放和失败状态已实现；后端 407 项测试、前端 98 项单测及上海真实连通性快照已记录。地点查询不提供酒店报价/余房、活动档期或景点开放/预约事实，地图不拥有路线查询。
- 行程：仅前端内存中的单城市手工草稿；尚无服务端 API、持久化、账号、owner scope、跨设备同步、地图联动或 PDF 导出。
- 导入、推荐及账号模块未实现；local-storage 与 exports 未实现。
- 助手已有离线/fake 流程和 provider adapter；真实模型服务的资格、条款、费用、隐私及质量仍待核验。

以上状态不改变获批的模块职责与依赖方向；实时数据、持久化和生产能力必须依据各自验收证据判断。

## 批准的依赖方向与分层顺序

`foundation` → 查询模块、`auth`、`budget`、`assistant` → `destination-workspace`、`imports`、`recommendations`、`itinerary` → `local-storage`、`maps`、`exports`。

该顺序表示依赖层级，不要求同层模块必须并行开发。核心边界：

- `maps` 不反向依赖路线实现；交通模块拥有路线查询，地图只展示。
- `assistant` 输出候选 patch，`itinerary` 校验并提交；模型不能解除锁定或更改事实来源。
- `imports` 经用户确认才输出旅行事实；其他模块不读取其临时文件。
- `auth` 提供主体标识；`local-storage` 才按该标识分区。

## 审阅记录

| 项目 | 结果 |
|---|---|
| 模块边界／稳定 ID | 已批准 |
| 依赖方向／循环 | 已批准；按上表依赖方向执行 |
| 分层建议顺序 | 已批准 |
| 批准日期／备注 | 原图于 2026-10-27 获批；用户于 2026-10-28 批准新增 `destination-workspace`，目的城市仅限 foundation 注册的五城；该模块 SPEC、计划和任务仍须独立审阅 |
