# transport-live-provider 任务清单

> 版本：v0.1｜状态：执行中（TLP-00 核查完成；两来源 Gate blocked）｜用户确认：2026-10-29
> 对应已批准文件：[SPEC](../../docs/SPEC-transport-live-provider.md)、[实施计划](plan.md)。来源 Gate 未通过的 provider 不得编写/启用 live adapter；真实请求仍需单独授权。

## 通用规则

- 以当前工作树为基线，保留用户已有的 `child_count`、定位起点、assistant 及其他未提交改动。不要覆盖或整理无关差异。
- 后端自动化测试默认禁网；真实 provider 测试使用 `httpx.MockTransport` 与合成响应。生产默认 provider 为空，不回退 fixture/demo。
- 不复制上游 `baizhexue/fly-flight` 代码；该仓库未声明许可证。不得使用 `eval`、`exec`、shell 或 JavaScript runtime 执行远端内容，不得关闭 TLS 证书校验。
- 不记录地点、日期、乘客构成、票价、车次、原始响应或凭证。日志/错误只允许稳定状态、provider id 和 request ID 等已批准信息。
- 每项任务先补失败测试再实现；每项最多五个文件。任务结束后验证后再继续。
- 条款/数据语义不通过的 provider 不实现或配置；一方 Gate 通过不自动授权另一方。

## 任务（按依赖顺序）

### TLP-00 — 供应商来源与用途 Gate（不调用班次/票价接口）

- [x] **验收：** 已分别审阅同程、12306 官方页面并标注未有证据的自动化访问、展示、限流、价格字段、覆盖和地点映射结论；未从网页可访问性或上游 skill 描述推断授权。
- [x] **验证：** 仅请求供应商法律/帮助/规程网页和项目首页；未调用班次/票价查询端点，未提交地点/日期/乘客信息。逐来源记录 Gate 结论和证据缺口。
- [x] **文件：** `docs/transport-provider-gate.md`（1 个）。结果：同程、12306 均 BLOCKED；后续 live adapter 与 smoke 保持 deferred。
- **依赖：** 用户已批准 SPEC 与计划。

### TLP-01 — 固定脱敏 payload 与映射测试

- [ ] **验收：** 为通过 Gate 的来源建立最小合成铁路 JSON 和/或同程服务端渲染 HTML 样例；定义仅基于已核验字段的 normalized mapping。测试日期/地点不匹配、单位未识别、字段缺失和畸形输入 fail closed；儿童票不支持时不可按成人结果冒充。样例不含真实用户查询或原始供应商响应。
- [ ] **验证：** `uv run pytest tests/unit/test_fly_flight_provider.py -q`；Ruff 检查新增测试。无通过 Gate 的来源时，其对应 parser 测试/fixture 标明 deferred，不伪造通过。
- [ ] **文件：** `backend/tests/unit/test_fly_flight_provider.py`、`backend/tests/fixtures/transport/fly_flight/rail_response.json`、`backend/tests/fixtures/transport/fly_flight/flight_page.html`（最多 3 个）。
- **依赖：** TLP-00。

### TLP-02 — 实现 12306 铁路 provider

- [ ] **验收：** 仅在铁路 Gate 通过时实现固定 HTTPS 主机请求、默认 TLS 校验、受限 JSON/车站表解析、有限超时/响应大小、日期和地点映射、CNY 单位/价格语义、可用性及安全错误映射。儿童人数无法按已核实规则查询时返回 `policy_unavailable`。每项 Offer 的 source_id 与 SourceRef 一致；未知数据保持 null/unknown。
- [ ] **验证：** `uv run pytest tests/unit/test_fly_flight_provider.py -q`；MockTransport 覆盖正常/空/畸形响应、超时、429、403、500、响应超限、单位、字段缺失、儿童人数、目标日期和 request_id；断言不产生实际网络访问。
- [ ] **文件：** `backend/app/modules/transport/providers/rail_12306.py`、`backend/tests/unit/test_fly_flight_provider.py`（最多 2 个；依赖 TLP-01 样例）。
- **依赖：** TLP-00、TLP-01；Gate 未通过则 deferred。

### TLP-03 — 实现同程航班 provider（严格 SSR 解析）

- [ ] **验收：** 仅在航班 Gate 通过且 SSR HTML 可稳定、安全解析时实现；固定主机、TLS 校验、限长响应、有限超时和安全字段映射。不得处理或执行 Nuxt JavaScript payload；页面结构变化时返回 `unavailable`，不回退脚本执行或合成结果。价格单位/基准无法确认时不输出数值票价。
- [ ] **验证：** `uv run pytest tests/unit/test_fly_flight_provider.py -q`；MockTransport 覆盖 SSR 页面、缺字段、结构变更、脚本 payload 未执行、超时、状态码、响应超限、日期/地点校验和 source 关联；断言无外网请求。
- [ ] **文件：** `backend/app/modules/transport/providers/tongcheng_public.py`、`backend/tests/unit/test_fly_flight_provider.py`（最多 2 个；依赖 TLP-01 样例）。
- **依赖：** TLP-00、TLP-01；Gate/安全解析不通过则 deferred。

### TLP-04 — 配置与应用注入

- [ ] **验收：** 增加窄 provider 设置并保持默认空值；显式设置后只注入 Gate 已通过且已实现的 mode provider。未知配置 fail closed，不选 fake、不切其他来源；route provider 继续不配置。`child_count` 与当前 PlaceRef 请求原样传递，所有配置/错误不泄露凭证。
- [ ] **验证：** `uv run pytest tests/unit/test_config.py tests/integration/test_transport_live_provider.py -q`；默认启动和查询断言无网络请求，显式设置用 MockTransport 验证 wiring，未知设置/未通过来源不得开启请求。
- [ ] **文件：** `backend/app/core/config.py`、`backend/app/main.py`、`backend/.env.example`、`backend/tests/unit/test_config.py`、`backend/tests/integration/test_transport_live_provider.py`（5 个）。
- **依赖：** TLP-02 和/或 TLP-03；仅接入通过 Gate 的 mode。

### TLP-05 — 集成隐私与全量回归

- [ ] **验收：** API 响应符合已有 FareResult/FareOffer；每个结果日期、mode、人数语义匹配 query，来源可追溯，`live`/`partial`/失败状态一致。地点、日期、金额、车次、provider payload sentinel 不进入日志/错误；OpenAPI 无 schema 变化，除非实现发现契约缺口（契约缺口先回到 SPEC 审批）。更新 transport 验收记录，明确代码接入与真实能力状态分开。
- [ ] **验证：** `uv run pytest -q`、`uv run ruff check .`；前端 `npm run test:unit -- --run`、`npm run typecheck`、`npm run lint`、`npm run build`；检查默认禁网和 Secretlint。仅 mock 的通过不得标成真实数据验证。
- [ ] **文件：** `backend/tests/integration/test_transport_live_provider.py`、`docs/acceptance/transport.md`（最多 2 个；共享集成测试按 TLP-04 后扩展）。
- **依赖：** 已获批来源的 TLP-02/TLP-03、TLP-04。

### TLP-06 — 受控 live smoke（独立授权条件任务）

- [ ] **验收：** 仅在对应来源 Gate 通过且用户另行确认测试地点/日期/次数/运行环境后，按批准范围进行有限真实查询。分别核实来源、覆盖、时间、票价单位和价格基准；脱敏留证，不保存原始响应、用户位置或完整班次响应，不扩大测试范围。
- [ ] **验证：** 在 `docs/acceptance/transport.md` 记录 provider、请求条件范围、查询时间、脱敏结果摘要和异常；live 结果必须可对应当前 query。未授权或 Gate 未通过则保持未执行/blocked，不以 mock 替代。
- [ ] **文件：** `docs/acceptance/transport.md`（1 个）。
- **依赖：** TLP-00、TLP-05、额外的 live request 明确授权；无授权时不执行。

## 审批记录

- 对应 SPEC：用户于 2026-10-29 批准。
- 对应计划：用户于 2026-10-29 批准。
- 本清单：用户于 2026-10-29 确认开始执行；仅开始 TLP-00 Gate 审阅，未授权编码或真实查询。

## 执行记录

- 2026-10-29：TLP-00 官方资料审阅完成；同程和 12306 均 BLOCKED。详见 `docs/transport-provider-gate.md`。TLP-01 至 TLP-06 未开始；不得发真实交通查询请求。
