# transport-live-provider 任务清单

> 版本：v0.2｜状态：航班 adapter 与 mock 验收完成；真实数据/铁路/路线未完成｜更新：2026-10-30（北京时间）
> 对应规格与计划：[SPEC](../../docs/SPEC-transport-live-provider.md)、[实施计划](plan.md)。代码接入不等于真实供应商授权或真实数据验收。

## 通用规则

- 保留用户已有的 `child_count`、定位起点、assistant 及其他未提交改动，不覆盖无关差异。
- 后端测试默认禁网；live provider 测试使用 `httpx.MockTransport` 和合成响应，生产默认 provider 为空。
- 不复制 `baizhexue/fly-flight` 代码；不执行远端 HTML/JS，不调用 12306 内部接口，不关闭 TLS。
- 不记录地点、日期、乘客构成、票价、班次、原始响应、token 或凭据。日志/错误仅保留稳定状态、provider id、request ID 等批准字段。
- 官方 API 优先；网页抓取不是当前实施方案。真实请求需单独 Gate 与 live smoke 授权。

## 已完成

### TLP-00 — 来源与用途 Gate

- [x] 分别审阅同程、12306 与官方航班 API 的可用边界；同程/12306 标为 BLOCKED，Amadeus 标为 CONDITIONAL。
- [x] 未调用任何真实班次/票价查询接口，未创建或使用真实 Amadeus 凭据。
- [x] 记录固定主机、授权缺口、价格语义、地点映射和 live smoke 前提。
- [x] **文件：** `docs/transport-provider-gate.md`。

### TLP-01 — Amadeus 合成 payload 与映射测试

- [x] 使用合成 Flight Offers Search payload 定义单程、CNY、整数分、party-total、travelerPricings 和 remaining seats 映射。
- [x] 覆盖空/畸形响应、日期/机场不匹配、人数类型不匹配、币种/金额精度错误、未知 IANA 时区、OAuth 缓存、超时、连接错误、429、401/403、响应上限和敏感日志。
- [x] 无法确认的金额置 null/unknown；未识别时区返回 partial，不猜测时间。
- [x] **文件：** `backend/tests/unit/test_amadeus_provider.py`。

### TLP-02 — Amadeus 航班 Provider

- [x] 实现固定 test/production HTTPS 官方端点，默认 TLS 校验、关闭 redirect、禁用环境代理继承。
- [x] 使用 Client Credentials token 短时缓存；凭据使用 `SecretStr`，不向上游发送 request ID。
- [x] 实现严格 IATA、最多 9 人、ADULT/CHILD traveler 与 CNY party total 映射；搜索结果不宣称锁价/锁位。
- [x] 401/403 → `policy_unavailable`，429 → `rate_limited`，其他上游错误 → `unavailable`。
- [x] **文件：** `backend/app/modules/transport/providers/amadeus.py`。

### TLP-03 — Settings 与应用注入

- [x] 新增 `APP_TRANSPORT_FARE_PROVIDER=amadeus|空`、Amadeus env/ID/Secret/timeout/body limit 配置；空值归一为关闭。
- [x] 只有 provider 与两项凭据完整显式配置时才构造 Provider；默认 Settings 不产生外部请求。
- [x] 未知 provider/空白凭据/畸形配置 fail closed，不 fallback fixture 或其他来源。
- [x] **文件：** `backend/app/core/config.py`、`backend/app/main.py`、`backend/app/modules/transport/runtime.py`、`backend/.env.example`、`backend/tests/unit/test_config.py`。

### TLP-04 — API 接线与前端 IATA

- [x] 航班表单新增起降机场 IATA；小写转大写；同机场、缺 IATA、人数 > 9 时前端阻断；铁路不要求 IATA。
- [x] IATA/日期/人数/交通方式变化会清除旧结果，迟到响应不能覆盖新查询。
- [x] API 集成测试通过注入 MockTransport 验证默认 `unconfigured`、完整映射、429 公共错误和 request ID。
- [x] **文件：** `backend/tests/integration/test_transport_live_provider.py`、`frontend/src/features/transport/TransportPanel.tsx`、`frontend/src/features/transport/TransportPanel.test.tsx`、`frontend/e2e/transport.spec.ts`。

### TLP-05 — 全量回归与验收记录

- [x] 后端：`309 passed`；Ruff `All checks passed`。
- [x] 前端：Vitest `77 passed`；TypeScript、ESLint、Vite production build 通过；Playwright `36 passed`（桌面 + Pixel 7）。
- [x] 航班 E2E 验证小写 IATA 在上游 body 转大写、价格 `¥355.34`、班次 `MU1234`，并检查移动端/横屏无水平溢出。
- [x] 更新验收记录，明确 mock 验证不等于真实供应商数据验收。
- [x] **文件：** `docs/acceptance/transport.md`。

## 未完成且阻塞

### TLP-06 — Amadeus 受控 live smoke

- [ ] **阻塞：** 未提供可授权使用的 Amadeus 账户/环境，未确认生产资格、商业条款、目标航线覆盖、CNY/税费/儿童口径、配额/缓存/署名和最终确认价语义。
- [ ] **需要用户单独确认：** 测试机场/日期、请求次数、运行环境、脱敏证据范围。
- [ ] **验收：** 按批准范围发起有限真实查询，分别记录来源、覆盖、时间、金额语义与异常；不保存原始响应或完整班次响应；不宣称为锁价/锁位。
- **依赖：** TLP-00 至 TLP-05、Gate 补证、单独 live 授权。当前不执行。

### TLP-R1 — 铁路 / 高铁 Provider

- [ ] **阻塞：** 12306 网页/内部接口没有获批的第三方 API 契约；同程/上游 skill 也不授权铁路数据抓取。当前没有正式 Railway Provider。
- [ ] **解法：** 选择具有授权、稳定文档和再展示许可的铁路数据供应商；另立配置名、映射测试、票价/余票/席别/儿童/Gate 和 live smoke 任务。
- [ ] **状态：** BLOCKED / deferred；不得复用 Amadeus 配置，也不得以合成 fixture 冒充真实铁路数据。

### TLP-R2 — 公交 / 地铁 / 步行 / 出租车路线

- [ ] **阻塞：** `fly-flight` 不含市内路线能力；当前没有已核验路线供应商、许可、额度、几何/时长/计价语义。
- [ ] **解法：** 独立选择路线供应商并新增规格、配置与 Gate；不得自动用直线、估算路径或出租车价格替代其他 mode。
- [ ] **状态：** deferred。

## 当前结论

- 航班：官方 Amadeus adapter 已实现并接入，但默认关闭，真实数据未验收。
- 铁路：未接通。
- 公交、地铁、步行、出租车：未接通。
- 任何 mock/E2E 通过均只证明契约、映射、界面和故障隔离，不代表供应商生产可用。