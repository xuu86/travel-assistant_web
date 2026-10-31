# transport-live-provider 实施计划

> 版本：v0.2｜状态：已批准，航班 adapter 已实现｜原批准：2026-10-29｜执行口径更新：2026-10-30（北京时间）
> 对应规格：[SPEC-transport-live-provider](../../docs/SPEC-transport-live-provider.md)。
> 本计划扩展已完成的 fake-only transport；真实数据验收与铁路/市内路线接入仍是独立任务。

## 1. 目标与范围

在现有 `FareProvider` 协议内，以服务端显式配置接入官方交通数据 Provider，并保持结果契约、儿童人数语义和默认无网络行为。

已确定的拆分：

1. **航班**：独立实现 Amadeus Flight Offers Search adapter。官方 API 优先，网页抓取不是实施依赖。
2. **铁路 / 高铁**：保持 blocked/deferred，等待正式授权的 Railway Provider 与稳定契约。
3. **公交 / 地铁 / 步行 / 出租车**：没有获批的路线 Provider，维持现状。
4. **上游 skill**：只做能力与风险分析；不复制 `baizhexue/fly-flight` 代码，不安装/执行其脚本，不关闭 TLS，不执行远端页面代码。

本计划不包含预订、支付、锁价、锁位、地图 SDK、预算写入或售票跳转。

## 2. 配置与默认行为

- `APP_TRANSPORT_FARE_PROVIDER` 只允许空值或 `amadeus`；默认空值。
- 只有 provider + Client ID + Client Secret 全部显式配置时，`runtime.create_transport_service()` 才构造 live provider。
- `APP_TRANSPORT_AMADEUS_ENV` 只允许 `test` / `production`，对应固定官方 HTTPS 主机。
- route provider 不受上述配置影响，继续默认未配置。
- 空白凭据、未知 provider、畸形配置 fail closed；不 fallback 到 fake、fixture、同程网页或其他供应商。
- 测试默认不触网；live provider 通过 `httpx.MockTransport` 或注入 client 验证。

## 3. Gate 状态

| 来源 | 状态 | 允许的工作 | 阻塞的事实 |
|---|---|---|---|
| Amadeus Flight Offers Search | CONDITIONAL | 已完成 adapter、配置接线、mock/API/前端/E2E 验收；可显式配置 | 生产资格、商业条款、中国国内覆盖、CNY/税费/儿童口径、配额/缓存/署名、最终确认价、live smoke |
| 同程公开航班页面 | BLOCKED | 只保留资料与风险分析 | 自动化访问、再展示授权、字段/价格语义、限流 |
| 12306 网页/内部接口 | BLOCKED | 暂不实现 adapter | 无第三方正式 API 授权与稳定契约；金额/余票/儿童语义未确认 |
| 市内路线 | BLOCKED / deferred | 保持路线 fake 流程与原契约 | 无路线 Provider、许可、额度、计价语义与规格 |

详见 [交通真实数据 Provider Gate](../../docs/transport-provider-gate.md)。

## 4. 技术方案与执行状态

依赖方向：`Provider contract → conservative mapping → adapter → config/wiring → API/UI tests → acceptance evidence → authorized live smoke`。

| 顺序 | 组件 | 状态 | 关键要求 |
|---:|---|---|---|
| 1 | Amadeus mapping tests | 已完成 | 合成 payload；覆盖完整/空/畸形、旅客合计、CNY 精度、日期/机场/人数校验、时区未知、OAuth 缓存、超时/状态码/响应上限 |
| 2 | Amadeus adapter | 已完成（条件） | 固定官方主机、TLS 校验、关闭 redirect/环境代理、有限 timeout/body、安全错误映射、凭据不泄露 |
| 3 | Settings 与 app wiring | 已完成 | 窄枚举、完整凭据才启用、默认无网络、注入 client 可测 |
| 4 | 前端 IATA 输入 | 已完成 | 航班要求三字 IATA、小写转大写、同机场/总人数 > 9 阻断；铁路不要求 IATA |
| 5 | API / 前端回归 | 已完成 | 默认 `unconfigured`、429/权限/不可用映射、request ID、无敏感日志；仅 mock 外发 |
| 6 | 真实数据验收 | 未完成 | 必须额外取得 Gate 证据、凭据和 live smoke 授权；不能以 mock 通过代替 |
| 7 | Railway provider | blocked | 找到正式授权、稳定契约与票价/儿童/余票语义后另立任务 |
| 8 | 市内路线 provider | deferred | 独立供应商、单独规格、权限和计价核验 |

## 5. 文件范围

```text
backend/app/modules/transport/providers/amadeus.py
backend/app/modules/transport/runtime.py
backend/app/core/config.py
backend/app/main.py
backend/.env.example
backend/tests/unit/test_amadeus_provider.py
backend/tests/unit/test_config.py
backend/tests/integration/test_transport_live_provider.py
frontend/src/features/transport/TransportPanel.tsx
frontend/src/features/transport/TransportPanel.test.tsx
frontend/e2e/transport.spec.ts
docs/transport-provider-gate.md
docs/acceptance/transport.md
```

公共 `FareResult` / `FareOffer` schema 未因 Amadeus adapter 改变，因此无需重生成 OpenAPI/types。不得以本计划为由覆盖工作区中其他未提交改动。

## 6. 验证门

### Gate A：映射与安全 — 已完成（mock）

- 合成 payload 覆盖 total、travelerPricings、币种、精度、人数类型与机场时间。
- 不满足语义的金额为 null/unknown；未识别时区为 partial。
- TLS、redirect、timeout、body limit、401/403/429/5xx 与敏感日志均有测试。

### Gate B：默认关闭与显式接线 — 已完成（mock）

- 默认 Settings 不构造 Provider，MockTransport 请求数为 0。
- 完整配置才注入 Amadeus；凭证只以 `SecretStr` 保存。
- API 到 Provider 的请求/响应映射、错误隔离和 request ID 通过集成测试。

### Gate C：前端与全量回归 — 已完成

- 航班 IATA 表单、输入校验和条件变更清理旧结果的单元/E2E 通过。
- 后端全量、Ruff、前端全量、TypeScript、ESLint、构建、Playwright、Secretlint 通过。
- 所有 E2E 外发交通接口均被同源 mock 拦截。

### Gate D：真实能力验收 — 未完成

只有以下条件同时满足才可通过：

1. Amadeus 账户/环境/生产资格与条款已留证；
2. 目标航线覆盖、CNY、税费、儿童和最终确认价语义已核验；
3. 用户另行批准限定地点、日期、次数和环境的 live smoke；
4. 脱敏结果与实际 query 对应，且不宣称锁价/锁位或最终支付价。

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

## 8. 不在本计划授权范围

- 不抓取、解析或执行同程/12306 网页脚本，不调用 12306 内部查询接口。
- 不使用真实 Amadeus 凭据进行 live query，除非另有明确授权。
- 不宣称真实供应商数据已验收、铁路已接通或市内路线已接通。
- 不自动猜测机场/车站、时区、票价单位、汇率、缓存 TTL 或供应商额度。
- 不添加预订、支付、锁价、锁位、地图、预算写入或售票跳转功能。

## 9. 审批与执行记录

- 2026-10-29：用户批准 SPEC 与计划；开始来源 Gate 审阅。
- 2026-10-29：同程、12306 Gate 结论为 BLOCKED；未发真实票价查询。
- 2026-10-30：用户多次确认继续任务。执行口径收敛为“Amadeus 官方航班条件接入；铁路等待独立授权 Provider”，完成 adapter、配置、前端 IATA 和 mock 回归。
- 2026-10-30：真实数据与铁路接入仍未验收；保持默认关闭。