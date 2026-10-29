# SPEC-weather：天气查询与预报覆盖

> 版本：v0.1｜状态：已批准｜批准日期：2026-10-27（北京时间）  
> 本规格只定义 Capability Map 中的 `weather` 模块，已于 2026-10-27 获用户批准。该批准允许进入计划阶段；真实供应商资格／调用仍受 E-001 及本规格许可门禁约束。

## 0. 已批准假设与后续待决事项

1. 本模块只服务已注册的单个城市和明确的日期范围；城市坐标取自 `foundation`，客户端不得提交任意坐标。
2. 本模块提供逐日天气预报和实际日期覆盖信息，不提供历史实况、气候统计、活动推荐、附近城市推荐、路线或空气质量。
3. 天气预报是模型输出，不是确定天气事实；必须显示来源、取数时间、有效日期及缺失日期。
4. Open-Meteo 已作为**本地非商业试用 provider**接入。官方 Forecast API 文档记载最多请求 16 天；daily 变量请求必须提供 timezone；具体覆盖以响应的逐日数据为准。
   provider 会返回 WGS84 网格位置，不一定与输入城市锚点重合；不同模型／地区的逐日变量可用性可能不同。五城于 2026-10-29 完成一次同日单日 smoke test，当前试验记录见 [provider gate](weather-provider-gate.md)；不代表持续覆盖或准确度保证。[Forecast API](https://open-meteo.com/en/docs)
5. Open-Meteo Free API 仅限非商业用途。Terms 列出每分钟 600、每小时 5,000、每日低于 10,000 次的限额；免费服务无 uptime 保证。数据使用 CC BY 4.0，需署名并说明修改。教育内容被列为可能的非商业用途示例；比赛公开展示、广告／商业推广和未来商业部署不得由本地试用授权推断许可，须先确认用途或获取适用许可。
   服务按“现状”提供，不保证无错误或持续可用；在 E-001 与用途许可获批前不得启用 live provider。[Terms](https://open-meteo.com/en/terms)｜[Pricing](https://open-meteo.com/en/pricing)｜[Data licence](https://open-meteo.com/en/licence)
6. 未经授权不以 demo/fixture 替代 live。Fixture 仅用于测试并始终标 `demo`。
7. 工程默认值（已随本规格批准）：单次超时 8 秒；仅对超时／连接错误／上游 502、503、504 最多重试 1 次；429 和其他 4xx 不重试；成功／部分结果进程内缓存 15 分钟；不缓存错误，也不在缓存过期后以旧数据回退。所有值可配置、可测试且不触发计费回退。
8. 规格批准仅冻结模块行为，不等于供应商许可、真实覆盖、AC-06 或整个 Web 首版已验收。

## 1. 元数据

- **模块 ID：** `weather`
- **负责人角色：** 数据集成负责人；开发负责人负责契约、UI 与测试
- **依赖模块：** `foundation`
- **被依赖模块：** `recommendations`、`itinerary`
- **关联决策：** D-001、D-002、D-006、D-008、D-012
- **关联待办／外部核实：** E-001（五城已完成一次单日连通性检查；持续覆盖、稳定性及真实用途许可仍需核实）；Q-009（真实调用失败时 demo 语义仍待决）；Q-014（供应商缓存、报价新鲜度与限流的一般问题；本 SPEC 提供天气 TTL／限流提案）
- **关联验收：** AC-01（天气方面）、AC-03、AC-06、AC-25；依赖方需配合 AC-02/03。
- **SPEC 批准前状态：** 供应商未配置、未调用；没有任何实时天气能力可对外宣称完成。

## 2. Objective 与范围

### 目标

在指定试点城市与行程日期查询可追溯的逐日预报，并准确表达数据实际覆盖区间。用户成功条件：看得出哪些日期有预报、哪些缺失；知道温度、降水和天气现象字段的单位与来源；缺失值不会伪装为晴天、零降雨或零气温；服务未配置、无覆盖、限流和故障可区分。

### 首版包含

- 注册城市 ID、`start_date`、`end_date` 的单城市预报查询。
- 每日天气摘要：WMO 天气码、最高／最低气温、最高降水概率、降水总量、最大风速（供应商确实提供时）。可选指标独立为 `null`，不能因一项缺失丢掉其他有效指标。
- 实际请求范围、已覆盖日期段、缺失日期段、提供方查询时间、来源和覆盖网格位置（提供方返回时）。
- Provider adapter 接口、可替换的 mock/fake、精确错误状态、调用限额保护与短期内存缓存。
- 前端逐日预报卡片／列表的 loading、部分覆盖、未配置、无覆盖、限流、错误和空数据呈现；清晰标注预报有效日期、当前取数时间和来源。若使用 Open-Meteo，数据位置旁展示其要求的 attribution 和许可链接。
- 中国业务日期固定 `Asia/Shanghai`；后端采集时间 UTC；温度统一摄氏度，降水毫米，降水概率百分比，风速 km/h。
- Open-Meteo 候选适配器只在供应商用途许可、E-001 与接入条件重新核实且获批后实现并启用；不在本 SPEC 批准时立即进行真实调用。

### 首版不包含

- 历史实况、气候常年值、气候变化分析、历史预报回溯、分钟级雷达或预警通知。
- 多城市合并查询、天气驱动城市推荐、活动查询、行程自动改写和自动取消／确认。
- 将预报概率解释为确定发生；由天气模块独自判断“适合旅行”。
- 将第三方天气响应长期落盘、关联用户身份、采集精确设备位置或在日志记录行程日期／坐标。
- 多供应商自动切换、付费供应商自动回退、无上限重试、无上限 provider 请求或未经审批的模型选择。
- Open-Meteo 的商业使用许可或免费使用资格的法律判定；这些仍是待核实项。

## 3. 输入输出契约

### API 请求

建议内部 API：`POST /api/weather/forecast`。使用 JSON body，避免把目的地和行程日期放入 URL 访问日志。

| 字段 | 类型 | 必填 | 空值语义 | 校验 | 来源／权限 |
|---|---|---:|---|---|---|
| `city_id` | 稳定字符串 ID | 是 | `null` 不选默认城市 | 必须存在于 foundation registry；未知城市不调用供应商 | 用户选择；公开天气查询，无 owner scope |
| `start_date` | ISO `YYYY-MM-DD` 日期 | 是 | 不自动替换为今天 | 业务日按 Asia/Shanghai；不得传 datetime 或时区偏移伪装日期 | 用户请求 |
| `end_date` | ISO `YYYY-MM-DD` 日期 | 是 | 不自动延伸日期 | 闭区间，且不早于 start_date；单次闭区间最多 16 个当地日；超过返回 422 且不调用 provider、不拆批（已随本规格批准） | 用户请求 |
| `request_id` | 服务端 UUID | 否（用户不可指定） | 由 request middleware 生成 | 仅用于响应／脱敏日志关联 | 服务端 |

### 日预报输出

成功／部分结果使用 `ResultEnvelope[WeatherDay]`；天气 schema 不复制 foundation 的公共 Result/Error/Source 语义。

| 字段 | 类型 | 可空 | 单位／语义 | 来源／时间 |
|---|---|---:|---|---|
| `date` | `date` | 否 | `Asia/Shanghai` 日历日，非 UTC 午夜时间戳 | provider 返回的当地 daily 日期；只能返回请求区间内日期 |
| `weather_code` | 非负整数 | 是 | 原样保存的 WMO 天气码；不识别的未来代码保留整数，UI 显示“天气现象待识别” | provider 原值；不得猜测映射 |
| `temperature_max_c` | 有限数值 | 是 | 当日 2 米最高气温，°C | provider |
| `temperature_min_c` | 有限数值 | 是 | 当日 2 米最低气温，°C；两者都有时不得低于最高温 | provider |
| `precipitation_probability_max_pct` | 0–100 数值 | 是 | 日最高降水概率，% | provider；不得四舍五入到 0 来隐藏小概率 |
| `precipitation_sum_mm` | 非负有限数值 | 是 | 日总降水量，mm | provider |
| `wind_speed_10m_max_kmh` | 非负有限数值 | 是 | 当日 10 米最大风速，km/h | provider；缺少变量时为 null |
| `missing_fields` | 字段 ID 数组 | 否 | 本日未取得的指标；须与 null 字段一致 | adapter 归一化 |

`null` 仅表示该指标未提供／无法解析；绝不表示 0、晴天或无降水。有效的逐日记录至少有一个非空天气指标。所有数值必须有限；概率不得超出 0–100；负降水／负风速或最高低于最低按供应商 payload 无效处理，不自行修正或钳制。

### 响应覆盖与来源

- `coverage.requested` 精确等于用户闭区间。
- `live`：请求的每个日期恰有一条有效日记录；`partial`：存在至少一条有效日期但也有缺失日期；`no_coverage`：无有效日期并且已确认所请求日期超出 provider 当前覆盖；`empty`：请求成功但 provider 在声称支持的范围返回空数据。未配置／限流／故障时不能假装知道 provider 覆盖：`coverage=null`。
- 对 `live`/`partial`/`no_coverage`，`covered` 和 `missing` 日期区间必须互不重叠、排序，并完整分割 `requested`，无日期遗漏或重复。超出预报范围的日期列入 missing，不以旧预报、历史实况、气候均值或其他 provider 结果补齐。
- 若 provider 返回额外日期，丢弃区间外记录；若返回重复日期，视为无效 payload 并安全降级，不自行取第一条。
- `SourceRef.retrieved_at` 与 `ResultEnvelope.queried_at` 用 UTC 表示原始实际请求时间；缓存命中不得重置来源取数时间。`request_id` 每个 HTTP 请求新建，即便返回缓存数据。
- 附 `WeatherLocationMetadata`：`city_id`、请求坐标（WGS84）、provider 实际网格坐标（WGS84，可空）、provider elevation（m，可空）。原始请求坐标和网格点不得混为一个“城市坐标”。不推断未返回的模型／网格来源。
- 响应不得包含 provider 原始错误文字、原始 URL 查询串、API Key、堆栈或环境配置。

### 建议 Provider 查询

- 使用 foundation 城市 registry 中的经纬度，不接受客户端自由经纬度。
- Open-Meteo 候选 adapter 显式指定 `timezone=Asia/Shanghai`、metric units 和获批的 daily variables。官方文档说明 daily 请求需要 timezone；各逐日变量日期按该时区生成。
  [Forecast 参数与响应说明](https://open-meteo.com/en/docs#api-documentation)
- Open-Meteo 只返回数值 WMO code，展示端按审阅过的静态映射转中文；未识别码保留原码，不因 mapping 缺失拒绝整天数据。[WMO code 表](https://open-meteo.com/en/docs#weathervariables)
- 严格请求必要变量，减少额度占用；不请求当前实况、小时数据、扩展指数或历史 API，除非另行审阅模块范围。

## 4. 状态与错误

| 状态／错误码 | 触发条件 | 用户提示原则 | 重试 | 覆盖／部分结果 |
|---|---|---|---:|---|
| `live` | 所有请求日期均有有效逐日数据 | 标“天气预报”，展示当地日期、单位、来源与取数时间 | 不需要 | 完整闭区间 |
| `partial` | 至少部分日期有效，其余日期未覆盖或字段缺失 | 明确列出已有及缺失日期；不补旧值；有效日期仍可查看 | 用户可手动重查；服务不循环 | 必须给准确覆盖分割 |
| `no_coverage` | provider 对请求日期／地点确认无预测覆盖 | 显示“该日期暂无可用预报”与日期范围；不暗示该地确定无天气 | 覆盖窗口改变后可重试 | `covered=[]`、全部日期 missing |
| `empty` | 请求成功且范围在 provider 声明能力内，但没有返回任何日期项目 | “未获取到天气数据”，不解释为晴或无雨 | 由用户触发一次重查 | 不虚构缺失日期原因 |
| `unconfigured` | provider 未经配置／未被批准启用 | 说明天气服务尚未配置；不展示演示值 | 配置获批后 | `coverage=null` |
| `rate_limited` | 上游 429 或模块／供应商限额已达 | 提示暂受查询额度限制；无自动付费、切换或紧密重试 | 不自动重试 429 | 不返回过期缓存伪装实时结果 |
| `policy_unavailable` | 供应商许可、权限或访问资格阻止使用 | 说明暂不可用；不得输出上游细节 | 仅在权限条件改变后 | `coverage=null`，并记录 E-001 阻塞 |
| `unavailable` | 网络、DNS、超时、上游 5xx、无效结构／数值、非预期上游 4xx | 简短提示暂不可用，附 request ID | 仅按 §7 有限重试规则 | 默认无结果；不得回旧值 |
| `VALIDATION_ERROR` | city_id/date 区间输入非法 | 安全字段级提示；无 provider 请求 | 用户修正输入 | 无结果 |
| `INTERNAL_ERROR` | 未知内部错误 | 通用提示和 request ID；无 traceback | 不自行重试非幂等后续操作 | 无结果 |

上游 429→`rate_limited`；超时／网络／502-504→`unavailable`；401/403→`policy_unavailable`；已验证的 provider 明确“日期超出预报范围”才→`no_coverage`；其余 4xx 默认视为配置／请求故障 `unavailable`，不通过模糊文本推断状态。错误映射须用脱敏 fixture 固定并逐项测试。

## 5. 权限、隐私与数据保留

- 预报查询不需要账号；不能用天气接口为其他资源授权，也不建立用户画像。
- 仅将 city registry 坐标和日期范围发送给 provider；不发送用户姓名、预算、旅客人数、行程文本、文件内容、会话 ID 或账户标识。
- 服务端日志只记录 request ID、模块名、最终状态、耗时和重试次数；禁止记录请求体、城市／行程日期、坐标、完整供应商 URL、Key、原始 provider payload 和异常原文。
- 不持久化天气历史记录。仅建议进程内缓存已校验的 `live`/`partial` 结果最多 15 分钟；缓存仅按 provider、城市 ID、闭区间、单位和 schema version 分区，不含 user ID；进程退出即清除。错误状态不缓存；过期即重新查，禁止 stale-if-error。
- Key（若将来采用需付费服务）只保留在服务端 SecretStr 环境配置，不返回前端；不在此 SPEC 授权申请付费计划、购买、充值或设置账单。
- provider 数据按许可显示 attribution；无授权／来源信息时，不把数据标记为已核实/已授权。

## 6. 业务规则与不变量

1. 单次输入只能指定一个已注册 city_id；坐标由 `foundation` 管理，固定 WGS84。
2. 日期为闭区间的日历日期，按 `Asia/Shanghai` 解释；start>end 返回 422；无默认日期、无机器本地时区转换、无未经确认的 14 天行程上限。
3. Forecast 服务不得把预测当成观测实况；查询日期早于当前 `Asia/Shanghai` 业务日的部分标为未覆盖，不调用 Historical Weather API、不向用户呈现实况替代预报；若区间同时含过去与未来，仅查询未来段并将过去段记入 missing。无法提供时按 coverage/error 状态返回。
4. 每个请求每个日期最多一条天气记录；完整覆盖、部分覆盖和未覆盖精确区分；不利用旧天气、邻近城市天气、均值或代码映射补缺。
5. 数值单位由服务端固定为 °C、mm、%、km/h；不由未验证 provider 默认值决定；单位未识别即 provider payload 无效。
6. 天气码为 provider 原码；所有代码翻译必须保留 mapping 来源，未知码可见但不能崩溃或被误标晴天。
7. 天气状态按 foundation `ResultState`；模块级错误采用 `PublicError`。空、未知、零、无覆盖、未配置与失败不可互换。
8. 任何 provider 调用不自动升级到付费 endpoint、自动充值、无限重试或切换未经核准的供应商。
9. 天气不可用不阻止用户查看其他数据；recommendations 可按其 SPEC 选择活动降级，但天气模块不导入 activities 或替其作决定。
10. Open-Meteo 文档所述最多 16 天为候选 provider 当前能力，不自动等同产品查询上限。建议单请求最多 16 个当地日且不拆批；产品查询跨度待用户批准。所有请求都必须有有限的日期跨度与供应商额度预算，禁止无上限日期区间。

## 7. 依赖、配置与运行语义

- **内部依赖：** `foundation` 的 `CityRecord`/城市 lookup、日期范围、`ResultEnvelope`、`SourceRef`、`Coverage`、统一错误、`Asia/Shanghai` 与 request ID。
- **公开接口：** `WeatherProvider.fetch(city, requested_range) -> ProviderForecastPayload`；`weather service` 负责输入、状态归一化、coverage、缓存、request ID；router 不调用上游 SDK。
- **建议配置名：** `APP_WEATHER_PROVIDER`（默认未配置）；未来若确认候选，仅允许静态注册的 provider ID，例如 `open_meteo`。不接受任意客户端 endpoint，避免 SSRF。付费 Key 配置另经审批后才加入 `.env.example` 空模板。
- **Provider 候选：** Open-Meteo Forecast API；E-001 仍待核实。其 Free API 仅限非商业使用；资格未核实前不得启用 live 调用或宣称已接入。
  [Pricing](https://open-meteo.com/en/pricing)｜[Terms](https://open-meteo.com/en/terms)
- **尝试／超时建议：** 总尝试最多 2 次；单次请求 8 秒；一次性 retry 仅用于网络／超时／502/503/504，并采用有限短退避；429 与其他 4xx 不重试。绝对等待时间须在计划及 fake transport 测试中量化。
- **缓存建议：** 进程内 TTL 15 分钟；仅对 schema 校验通过的 `live`/`partial` 结果；缓存命中保留原 `queried_at`/SourceRef `retrieved_at`，用新 request_id，不能把缓存命中伪装为 provider 刚查询。
- **测试替身：** `FakeWeatherProvider`、固定 UTC clock、手动 cache clock、上游 JSON fixtures、超时/429/5xx 注入；默认测试禁网，真实烟雾测试需独立人工启动并留脱敏证据。
- **本轮不新增依赖。** Open-Meteo 调用优先使用锁定运行时自带 `httpx`；解析由 Pydantic 契约完成；不引入 SDK/缓存服务。

## 8. 目录与代码风格

计划阶段可采用以下落点；具体文件仍由批准的 `tasks/todo.md` 冻结：

```text
backend/app/modules/weather/
  contracts.py              # WeatherQuery, WeatherDay, WeatherLocationMetadata
  providers/base.py         # Provider protocol and normalized payload
  providers/open_meteo.py   # candidate adapter; gated by E-001 approval
  service.py                # coverage, cache, bounded retry, state mapping
  router.py                 # POST /api/weather/forecast
backend/tests/unit/test_weather.py
backend/tests/integration/test_weather_api.py
backend/tests/fixtures/weather/
frontend/src/features/weather/
  WeatherPanel.tsx
  weather-code-labels.ts
frontend/src/features/weather/WeatherPanel.test.tsx
```

遵循现有格式：Python 3.14、严格 Pydantic 契约、Ruff 100 列；TS/TSX 使用 ESLint、Vitest、Playwright。Provider 数据只在 adapter 边界解析；领域服务只处理 normalized contract。

示例（草案，展示空值／单位语义，不是实现代码）：

```python
from datetime import date
from pydantic import Field

from app.core.contracts import ContractModel


class WeatherDay(ContractModel):
    date: date
    weather_code: int | None = Field(default=None, ge=0)
    temperature_max_c: float | None = None
    temperature_min_c: float | None = None
    precipitation_probability_max_pct: float | None = Field(default=None, ge=0, le=100)
    precipitation_sum_mm: float | None = Field(default=None, ge=0)
    wind_speed_10m_max_kmh: float | None = Field(default=None, ge=0)
```

## 9. 命令

### 现有仓库已验证命令

在 `backend/`：

```powershell
uv run pytest -q
uv run ruff check .
uv lock --check
```

在 `frontend/`：

```powershell
npm run lint
npm run test:unit -- --run
npm run typecheck
npm run build
npm run test:e2e
```

以上是 foundation 现有脚本，不代表天气模块已经有专属测试。天气实现任务获批并创建相应文件后，再使用下列模块专属命令；计划阶段按实际落地路径校对：

```powershell
# backend/：天气单元／API 集成测试文件创建后
uv run pytest tests/unit/test_weather.py tests/integration/test_weather_api.py -q
# backend/：静态检查
uv run ruff check app/modules/weather tests
# frontend/：天气组件测试文件创建后
npm run test:unit -- --run
npm run lint
npm run typecheck
npm run build
```

真实供应商烟雾测试目前没有获批命令，不在自动化全量测试里运行；先完成功能许可／城市覆盖核实及测试凭证配置审批。

## 10. 测试与验收策略

| 场景 | 输入／前置 | 预期 | 层级 | 证据 |
|---|---|---|---|---|
| 城市／日期请求 | 五城各一个 city ID；闭区间、同日、跨月、闰日 | 城市查 registry；本地日期保持不偏移；未知 ID／逆序日期在调用前拒绝 | 单元 + API | pytest 报告、请求计数为 0 的 fake provider |
| 全量覆盖 | fixture 每日所有 requested date 有有效记录 | state live；覆盖完整、日期无重复；单位固定 | service + API | 请求／响应 fixture |
| 部分覆盖 | fixture 覆盖中间或边界日期，其他日 absent/null | state partial；准确显示已覆盖／缺失段；不以旧日数据补齐 | service + UI/E2E | 脱敏响应与截图 |
| 预报范围之外 | 请求日期完全在已确认覆盖范围外 | no_coverage 或候选 provider documented error 转换；不回历史数据 | fixture；真实验证另记 E-001 | 错误状态、coverage 分割 |
| 某字段缺失 | 某天只有温度或天气码，或某个 daily value null | 当日其余字段保留，null 有 `missing_fields`；0 保持明确零 | unit + component | JSON fixture、UI 快照 |
| 数值／码错误 | NaN/Inf、负降水、概率越界、max<min、未知 WMO 码 | malformed 数值安全降级；未来未知 WMO code 保留并显示待识别 | unit | 错误响应及边界报告 |
| Provider 不可用 | 未配置、超时、网络断开、429、403、5xx、bad JSON | 依状态表分类；无异常文本、Key或堆栈泄漏；重试次数有上限 | fake transport + API | request ID日志断言、计数 fixture |
| 缓存 | 同城市/区间命中、TTL 到期、缓存过期后上游失败 | 新 request_id；来源时间不刷新；TTL 到期查新；失败不返 stale；cache hit 计数为零 upstream call | unit + integration | 固定 clock 报告 |
| CORS／隐私 | allow-origin/non-allow-origin、payload sentinel | 精确 origin；请求 body、城市、日期和坐标不进入应用日志 | API + log capture | 脱敏日志快照 |
| 无真实 fallback | fixture demo、provider 失败 | demo 只在显式 test context；live 查询失败不展示 demo/weather yesterday | unit + UI | 状态测试与截图 |
| Provider 实测 | E-001 许可通过后，对五城及目标日期按人工步骤调用 | 实际支持日期逐城记录；不覆盖日期保持缺失；来源/授权/查询时间可追溯 | opt-in 外部验收 | 脱敏请求摘要、response、日期矩阵；不得提交 Key |

**AC 映射：** AC-01 天气侧日期／缺失数据状态；AC-06 请求日与实际覆盖/缺失日；AC-25 unconfigured/rate_limited/policy 状态且无付费回退；AC-03 由 recommendations 基于天气 coverage 决定是否仅用已核实活动或“依据不足”，weather 不负责推荐。

**通过门槛：** 全部 provider/service 单测和 API/UI state tests 通过；完整、部分、全缺失及服务失败每类有证据；AC-06 fixture 分支可验收但真实能力状态保持待测；真实 Open-Meteo 五城覆盖只在 E-001 实际测试通过后独立标记。未运行的实时 API、UI/真机和许可不能被声明完成。

## 11. 风险、开放问题与批准记录

| 问题 | 影响 | 建议／缓解 | 需要决定 | 状态 |
|---|---|---|---|---|
| Open-Meteo Free API 的非商业资格是否适用于本项目参赛公开展示／未来部署 | 可能不能用于选定产品用途 | 供应商列出教育内容作为非商业示例，但须核对本产品实际比赛、公开展示和部署条件；确认前不启用 live provider | 项目负责人 | 待确认 |
| 单次天气查询的最大日期跨度及拆批调用策略 | 超长区间可能扩大供应商调用数／额度 | 已批准：最多 16 个当地日；超限返回 422、不自动拆批。真实 provider quota 在 E-001 实测记录 | 项目负责人 | 已批准行为；实测待办 |
| 五城所选城市锚点与 provider 天气网格点距离 | 影响“该城天气”代表性 | 显示城市名及 provider resolved grid coords/elevation；不把它说成行政区站点实测；按 AC-01/06留证 | 数据集成负责人 | 需 provider 实测 |
| 每日最高降水概率变量不同模型／日期可能为空 | 误当作零降水或无雨 | 保持 null 和 missing_fields；不根据 null 推断无雨 | 开发负责人 | 本规格提案 |
| 最长预测跨度随实际模型可用性变化；当前候选文档上限不是产品限制 | 超出时误用 stale/历史值 | 每次请求逐日对齐 provider 返回；E-001复核；覆盖范围之外只标缺失 | 数据集成负责人 | 待实测 |
| 缓存 TTL 15 分钟、8 秒 timeout、1 retry | 影响新鲜度、耗时、调用量 | 已批准默认值；先 fake clock/transport 测；不自动升级服务 | 开发负责人 | 已批准 |
| Q-014 的供应商缓存/限流一般语义 | 不同 provider 可能不同 | 本模块仅冻结 weather 提案；真实来源参数每次调用前重查并加限额配置 | 项目负责人／数据集成 | 未整体解决 |
| Q-009 显式 demo 模式是否允许生产 UI | 影响演示数据可见范围 | 测试 fixture 使用 demo；生产 weather provider 错误不回退 demo | 项目负责人 | 待决 |

批准记录：

- 审阅人／日期：用户／2026-10-27
- 结论：批准
- 修改摘要：按 v0.1 规格批准；真实 provider 许可资格／覆盖仍受 E-001 与本规格门禁约束。
## 12. 三层边界

- **Always：** 只使用注册城市；以北京时间解释业务日；明确每个真实覆盖日与缺失日；保存来源、单位、查询／有效时间；未知值保持 null；请求和日志不泄露行程；错误与限流诚实表达；所有真实供应商结果按能力留证。
- **Ask first：** 确认 Open-Meteo 许可资格／新增或替换供应商；新增 API Key、付费服务、实时定位、持久化、历史天气、跨城市查询、改变缓存／重试限额、把天气状态用于自动改写行程或替代用户确认。
- **Never：** 用旧天气、邻城、演示值或气候均值填补缺失日期；把预报称作实况/保证；把 null 当 0 或晴天；把代码表未知值擅自标成明确天气；自动购买、充值、切换收费 provider、无限重试；泄漏 Key、raw query/body、供应商错误详情或旅行资料。




