# transport-live-provider 实施计划

> 版本：v0.1｜状态：已批准｜批准日期：2026-10-29（北京时间）
> 对应规格：[SPEC-transport-live-provider](../../docs/SPEC-transport-live-provider.md) v0.1（已批准）。本计划扩展已完成的 fake-only transport，不修改或覆盖 `tasks/transport/` 历史记录。

## 1. 目标与范围

在现有 `FareProvider` 协议内独立实现同程航班与 12306 铁路/高铁票价适配，并在服务器端用显式配置选择 provider。保持当前结果契约、儿童人数改动和默认无网络行为。没有真实数据映射证据的字段仍为 null/unknown；无法满足现有严格 fare 契约的候选结果按 partial 表达，不编造事实。

本计划不改 GitHub 上游 `fly-flight` 仓库，不复制其未授权代码，不接入其脚本或 OpenClaw 运行时；仅参考其公开来源和功能边界。它不提供市内路线，路线 provider、地图、预算写入、订票、支付和售票跳转均不在范围内。

## 2. 前置条件与配置口径

- `APP_TRANSPORT_FARE_PROVIDER` 仅允许 `fly_flight` 或空值；默认空值。创建应用时只在显式配置后注入 live fare provider；配置错误 fail closed。route provider 不受该设置影响。
- 不把真实 provider 放入测试默认路径。测试用注入的 `httpx.MockTransport` 和合成 payload；默认 API 集成测试断言没有外部请求。
- 用户现有的 `child_count`、浏览器定位 PlaceRef 和相关 UI 改动原样保留。对儿童人数不受 provider 支持的查询，明确返回 `policy_unavailable`。
- 只有符合许可/用途/额度 Gate 的来源才进入 live provider；每种来源分别通过 Gate。Gate 不通过的模式不实现或不启用，不以另一模式/来源静默替代。
- live provider 配置虽可在代码完成后手动开启，但在 Gate 和独立 live smoke 授权未通过前，不创建实际供应商请求；生产默认保持关闭。

## 3. Gate 0：来源与用途核验

真实 provider 代码和调用之前完成以下核验，并在项目台账 E-004 留证：

1. 查阅同程、12306 当前官方条款、自动化访问政策、用途及展示/署名条件；确认本项目使用不依赖上游 skill 未声明的代码许可证。
2. 确认 12306 票价字段原始单位、币种/精度、席别、成人/儿童口径、余票含义与接口覆盖窗口；确认同程页面票价和行程字段的单位/价格基准/新鲜度。
3. 确认请求频率/限流、地区和日期覆盖、隐私传输条件及允许的部署环境。
4. 确认五个试点城市及常见机场/车站的无歧义映射。没有唯一映射的地名只允许返回 no_coverage 或让用户改填明确机场/车站。
5. 为后续受控实测确认允许的城市、日期、请求次数、证据保留和脱敏规则；Gate 0 本身不调用班次/票价端点。

若任一来源 Gate 不通过或数据语义无法确认，该来源的实现标为 deferred；另一来源可独立申请继续。不得仅凭 HTTP 200、网页可访问或 sample fixture 宣称 Gate 通过。

## 4. 技术方案与顺序

依赖方向：`Gate 0 → parser/mapping contract tests → provider adapter(s) → app configuration → acceptance evidence`。

| 顺序 | 组件 | 主要责任 | 检查点 |
|---:|---|---|---|
| 0 | 外部来源 Gate | 同程/12306 分别核验条款、字段语义、额度、覆盖、地点映射和脱敏测试授权 | 有官方来源、日期、结论和范围；否则停止该来源 live 开发 |
| 1 | Provider 单位/解析测试 | 定义固定的合成 12306 payload 与同程 SSR HTML 样例，明确字段映射、原始金额精度、地点映射和未知字段 | 无不确定单位被硬编码；儿童请求反例有测试 |
| 2 | 12306 adapter | HTTPS 证书校验、固定主机、有限超时/响应体、受限 JSON/车站表解析、错误状态映射、成人票价/可用状态 | Mock HTTP 测试覆盖 TLS 默认、429、403、异常 JSON、超限和 query-date 对齐 |
| 3 | 同程 adapter | 仅解析经验证的 SSR HTML 数据；禁止解析或执行 Nuxt JavaScript payload，不引入任意 JS runtime | HTML 结构变更时 fail closed；无可靠提取策略则将 flight 留在未配置状态 |
| 4 | Provider 选择与 app wiring | Settings 窄枚举、默认空值、显式配置时注入 fare provider；保持 route service 默认空值 | 默认启动/查询无网络；未授权来源不可被配置开启 |
| 5 | 适配集成与隐私回归 | API 到 provider 映射、source_id、request_id、状态一致性、敏感字段不入日志/错误 | 原始响应、查询地点、日期与金额 sentinel 不外泄 |
| 6 | OpenAPI/全回归与验收记录 | 若 API schema 不变则不重生成类型；更新验收记录，分别报告配置接入、测试和真实数据 Gate 状态 | transport 全回归、Ruff、前端测试/构建、Secretlint 通过；不把 mock 记为 live |
| 7 | 受控 live smoke（条件任务） | 只在来源 Gate 通过且用户明确批准测试条件/调用后，做有限的真实请求并记录脱敏证据 | 日期/地点覆盖、票价单位、来源时间和展示语义均可复核；不保存敏感原始响应 |

不得执行任意 URL/文件路径，重定向只能在经过核实的供应商主机范围内；网络层设置响应大小上限、超时和并发约束。禁止跳过 TLS 证书验证、执行远端脚本、缓存原始响应或向前端暴露供应商原始字段。

## 5. 预期文件范围

实施任务清单阶段按每项不超过约五个文件进一步收敛；当前预期范围：

```text
backend/app/core/config.py
backend/app/main.py
backend/app/modules/transport/providers/fly_flight.py
backend/tests/unit/test_fly_flight_provider.py
backend/tests/integration/test_transport_live_provider.py
backend/.env.example
docs/acceptance/transport.md
travel-assistant/docs/决策与待办台账.md   # 若仓库规范确认需要同步历史决策索引
```

除非映射测试证明现有 schema 无法表达真实来源数据，不改 fare 公共契约；确需改动契约、OpenAPI 或前端时，回到 SPEC 修订并单独列任务。不得触碰其他未提交文件；`backend/app/modules/transport/contracts.py`、相邻 tests、transport UI 和 assistant dirty changes 已有用户修改，实施时需保留并以当前工作树内容为基线。

## 6. 验证门

### Gate A：来源/字段语义

供应商来源、用途、票价单位、精度、人数基准、时间区、覆盖窗口与地点映射都有可追溯核验结论。未知语义不得在映射代码里用假设填补。

### Gate B：完全隔离的 Mock 测试

自动化测试不触网；覆盖完整、partial、empty、rate_limited、policy_unavailable、unavailable、儿童查询不支持、乱序/畸形 provider 数据和请求字段不匹配。

### Gate C：默认关闭与服务注入

默认设置和测试环境不构造 live 网络 client；仅服务器配置能选 provider；未知配置启动失败或 fail closed，不 fallback 到其他供应商或 fake。

### Gate D：隐私和可靠性

测试没有 TLS verify=false、`eval`/`exec`、任意 URL、敏感值日志、原始 provider 响应外泄；验证最大 body、timeout、主机/redirect 限制和安全错误映射。

### Gate E：真实能力验收

单元/集成测试通过不等于真实数据完成。只有 Gate 0、单独的 live request 授权和实际脱敏结果齐备后，才能更新 E-004 与 `docs/acceptance/transport.md` 对应模式的真实能力状态；结果按航班、铁路分别记录。

## 7. 验证命令

```powershell
# backend/
uv run pytest tests/unit/test_fly_flight_provider.py tests/integration/test_transport_live_provider.py -q
uv run ruff check app/core/config.py app/main.py app/modules/transport tests/unit/test_fly_flight_provider.py tests/integration/test_transport_live_provider.py
uv run pytest -q

# frontend/
npm run test:unit -- --run
npm run typecheck
npm run lint
npm run build
```

若 Settings/OpenAPI 未改变，不重复生成 OpenAPI/TypeScript；若契约变更，增加生成稳定性检查和前端回归任务。

## 8. 不在本计划授权范围

- 不安装、修改或发布 GitHub 上游 skill，不复制无许可证代码。
- 不在默认配置启用真实 provider，不发未经 Gate/独立授权的 live 请求。
- 不接入市内路线，不启用地图 API，不写入预算，不订票或支付。
- 不自动设置地点别名、日期范围、人数上限、缓存 TTL、汇率或供应商额度。
- 本计划获批仅允许进入任务拆分阶段；任务清单另行审批后才开始编码。

## 9. 待审阅决策

1. 是否同意 Gate 0 按来源分别执行；一方未通过时，只允许另一方独立进入实现。
2. 是否接受 flight SSR HTML 解析失败即保留航班未配置，而不退回执行上游 Nuxt payload。
3. 本规格中的 provider 默认关闭是否符合预期；如希望默认发出第三方请求，需要另行明确同意数据传输、用途/条款和运行环境。

## 10. 审批记录

- 对应 SPEC 已于 2026-10-29 获用户批准，允许进入计划阶段。
- 计划审批：用户于 2026-10-29 批准 v0.1；允许进入任务拆分阶段，未授权开始编码或 live request。
