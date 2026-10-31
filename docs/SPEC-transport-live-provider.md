# SPEC-transport-live-provider：真实交通票价 Provider 扩展

> 版本：v0.2｜状态：已批准｜原批准：2026-10-29｜执行口径更新：2026-10-30（北京时间）
> 本规格扩展已批准的 [SPEC-transport](SPEC-transport.md)，不替代该规格。官方 API 优先；网页抓取不是实施前提。代码接入、真实供应商调用和真实数据验收是三个不同结论，不得互相替代。

## 1. 目标与范围

在现有 `FareProvider` 边界内，以服务端显式配置接入可审计的官方交通数据 Provider，并把结果保守映射到现有 `FareResult` / `FareOffer` 契约。

当前获批的首个条件方案是 **Amadeus Flight Offers Search**：只查询单程航班，只接受三字 IATA 机场代码，只展示供应商返回的班次、报价与可售座位信息。`baizhexue/fly-flight` 仅用于理解航班/铁路查询能力边界；本项目不复制其代码，不安装或执行其 OpenClaw skill，也不依赖其对同程页面或 12306 内部接口的抓取实现。

范围边界：

- 航班：Amadeus 官方 API adapter，条件启用；默认关闭。
- 铁路 / 高铁：未接入。必须使用具有正式授权和稳定契约的独立 Railway Provider；12306 网页或内部接口不作为生产来源。
- 公交、地铁、步行、出租车 / 驾车：未接入。`/api/transport/routes/search` 维持现状，不伪称已有真实路线能力。
- 查询只读；不预订、不支付、不锁价、不锁位、不跳转售票网站。

## 2. 配置与数据契约

- `APP_TRANSPORT_FARE_PROVIDER` 只允许 `amadeus` 或空值，默认空值。只有 provider、Client ID、Client Secret 三项均显式配置时才构造航班 Provider；否则返回 `unconfigured`，不允许 `auto`、网页 fallback、fixture fallback 或静默切换来源。
- `APP_TRANSPORT_AMADEUS_ENV` 只允许 `test` / `production`，分别固定到以下官方 HTTPS 主机：
  - `test.api.amadeus.com`
  - `api.amadeus.com`
- 航班请求必须由用户填写起降机场 IATA。不得从城市名、地址或浏览器坐标猜测机场；无法提供 IATA 时前端阻止请求，后端返回 `no_coverage`。
- 日期必须来自 `FareQuery.travel_date`。成人加儿童总人数不得超过 9，且至少 1 名成人；儿童人数按 `CHILD` traveler 传递，不能把儿童静默当作成人。
- 每个 offer 必须带 `SourceRef`、请求 ID 和保守 evidence state。搜索结果展示的是查询时报价，不能表述为最终可购票价或余票锁定。
- 金额只接受 CNY、最多两位小数，并精确转为整数分。offer 总价必须等于全部 `travelerPricings` 合计，且 traveler 类型数量必须与查询一致；不满足时金额置 `null`/`unknown`，不得估算、乘人数或补 0。
- 搜索结果使用 `price_basis=party_total`、`price_scope=entire_journey`。用户最终支付价仍需供应商的价格确认/预订流程；本模块不实现该流程。
- Amadeus 返回的机场本地时间必须通过受控 IANA 时区表转换。当前 IANA 表未覆盖的机场返回 `partial`，相关时间/时区字段保留 `null`，不得按 `Asia/Shanghai` 或 UTC 猜测。
- 铁路若未来接入，必须使用独立配置名称和独立 Gate；儿童票语义无法证明时返回 `policy_unavailable`，不得复用 Amadeus 航班配置。

## 3. 安全与可靠性要求

- 所有请求执行 TLS 证书校验；禁止 `verify=False`、绕过代理安全设置或跟随不受控重定向。
- 固定官方主机，只使用服务端构造的 query 参数；不接受客户端传入 URL、文件路径、任意 Header、供应商凭据或额外 provider 参数。
- 设置有限连接/读取超时与响应体上限；畸形 JSON、超时、连接错误、超大响应均 fail closed。
- OAuth token 可短时缓存，并在过期前刷新；凭据使用 `SecretStr`，不得进入日志、错误、响应、OpenAPI、构建产物或前端。
- 401/403 映射 `policy_unavailable`，429 映射 `rate_limited`，其他上游错误映射 `unavailable`；不得把失败伪装成空结果或 demo 数据。
- 请求地点、日期、乘客构成、班次、票价、token 和上游正文不得写入日志或错误体。测试 fixture 只能通过依赖注入使用，默认测试与启动路径不得触网。
- 真实调用仍有频率、缓存、署名、展示期限、商业用途和供应商条款约束；代码默认关闭不代表生产资格已通过。

## 4. 外部核验 Gate

项目台账 E-004 仍不能标记为“已验证真实数据方案”。当前状态如下：

1. **Amadeus：CONDITIONAL。** 官方 Self-Service API 可用于条件实现和 mock 验收；生产资格、商业条款、目标航线覆盖、CNY 计价、儿童票年龄口径、配额、缓存/展示/署名要求、最终确认价语义及 live smoke 尚未完成项目级核验。
2. **同程公开页面：BLOCKED。** 未取得允许自动化抓取并在本项目再展示航班/价格数据的明确依据；页面数据字段语义和频率限制也未被证明。上游仓库无可见许可证，不复制其实现。
3. **12306 网页/内部接口：BLOCKED。** 未取得面向第三方程序化查询的官方 API 授权、稳定字段契约和限额；不得以网页可访问或 HTTP 200 代替授权。
4. **市内路线：BLOCKED / deferred。** 需要独立路线供应商、许可、额度、署名、计价语义和单独规格，不属于本规格。

Gate 记录需附核验日期、官方链接、适用条件及脱敏证据。用户批准接入任务不等于供应商生产资格、真实数据展示权或 live smoke 已通过。

## 5. 验收

- Provider 单元测试全部使用合成 Amadeus payload 与 `httpx.MockTransport`，覆盖正常/空结果、畸形 JSON、超时、连接错误、429、401/403、响应超限、日期/机场/人数校验、币种/精度、旅客合计、未知机场时区、OAuth 缓存与敏感日志。
- 集成测试验证默认 Settings 不产生外部请求；显式完整配置时通过注入 client 验证 API → Service → Provider 的完整映射、错误隔离和 request ID。
- 前端测试验证航班必须填写 IATA、自动转大写、同机场/超 9 人阻断、铁路不要求 IATA、条件变化清除旧结果；E2E 只拦截同源 API，不向 Amadeus 发请求。
- 全量测试、类型检查、Lint、构建、Ruff 和 Secretlint 通过只证明代码与 mock 流程，不证明真实供应商数据已验收。
- 真实数据验收必须在 Gate 补充证据且用户单独给出测试地点、日期、次数和环境后进行；未执行前只能写“adapter 已实现 / 真实数据未验证”。

## 6. 当前项目结构

```text
backend/app/modules/transport/providers/
  amadeus.py                    # 官方 Flight Offers Search 隔离适配
backend/app/modules/transport/
  runtime.py                    # 依据完整服务端配置构造 Provider
backend/tests/unit/
  test_amadeus_provider.py      # 合成 payload 与 MockTransport
backend/tests/integration/
  test_transport_live_provider.py
docs/acceptance/
  transport.md                  # 代码验收与真实能力分开记录
```

依赖复用现有 `httpx`、标准库和 Pydantic 契约。不得为绕过官方 API 而引入网页自动化、浏览器脚本执行、TLS 绕过或 12306 内部接口依赖。

## 7. 验证命令

```powershell
# backend/
uv run pytest tests/unit/test_amadeus_provider.py tests/unit/test_config.py tests/integration/test_transport_live_provider.py -q
uv run ruff check .
uv run pytest -q

# frontend/
./node_modules/.bin/vitest.cmd --run
./node_modules/.bin/tsc.cmd --noEmit
./node_modules/.bin/eslint.cmd .
./node_modules/.bin/vite.cmd build
./node_modules/.bin/playwright.cmd test
```

## 8. 仍待确认

- Amadeus 生产账户/环境资格、适用条款、配额、航线覆盖、展示与缓存规则。
- CNY 报价、税费包含项、儿童年龄口径和最终确认价；搜索结果不能替代确认流程。
- 机场 IATA 与 IANA 时区的完整受控目录，以及城市到机场歧义时的用户选择流程。
- 正式 Railway Provider 的授权、接口契约、票价/余票/儿童票语义和 live smoke。
- 公交、地铁、步行、出租车 / 驾车路线的独立供应商与单独 Gate。