# SPEC-transport-live-provider：真实航班与铁路票价 Provider 扩展

> 版本：v0.1｜状态：待审批｜日期：2026-10-29（北京时间）
> 本规格扩展已批准的 `transport` 模块，不替代 [SPEC-transport](SPEC-transport.md)。批准本文仅授权进入计划阶段；真实供应商调用、数据展示及启用仍须通过对应 Gate。

## 1. 目标与范围

在现有 `FareProvider` 边界实现一个可选的真实票价 provider，参考 `baizhexue/fly-flight` 展示的公开来源：同程国内航班公开页面、12306 公开铁路班次/票价接口。结果映射为现有 `FareOffer` 与 `FareResult`；不直接安装 OpenClaw skill，也不把该仓库未声明许可的代码复制进本项目。provider 未显式启用时继续返回 `unconfigured`。

本次只覆盖航班和铁路/高铁的跨城查询。该 skill 不提供公交、地铁、步行或出租车路线，因此 `/api/transport/routes/search` 保持现状，不伪称已接入。查询仍只读，不预订、不支付、不跳转售票网站。

## 2. 接入和数据契约

- 配置使用窄枚举 `APP_TRANSPORT_FARE_PROVIDER=fly_flight`；默认空值，不允许 `auto`、静默 fallback 或 fixture 生产回退。票价 provider 与路线 provider 分开配置。
- 请求日期必须来自 `FareQuery.travel_date`。地点仅接受可明确映射到来源机场/车站的名称或稳定代码；禁止用城市中心坐标猜测机场/车站。无法唯一解析时返回 `no_coverage`，不得猜测。
- `SourceRef` 分别标识同程公开航班页与 12306 公开查询来源，带安全的无查询参数 URL、抓取时间、署名（仅在核实后填写）和保守 evidence state。每个 offer 必须关联来源。
- 所有金额先按供应商原始单位、币种和舍入规则核实，再转换为 CNY 整数分。不能证明单位或计价基准的金额必须为 null/unknown；不得抽取数字后直接假设精度、乘人数、合并税费或将空值改为 0。
- 航班/铁路班次时间按来源提供的当地时间解析为 `Asia/Shanghai`，并保留时区；缺失字段使用 null 和 `missing_fields`。只有契约必需事实齐全、来源证据等级满足要求的结果可为 `live`；字段不全使用 `partial`，不能编造补齐。
- 12306 当前候选请求只表示成人查询。若 `child_count > 0` 而该来源不提供可验证的儿童票查询语义，返回明确的 `policy_unavailable`，不得把儿童当成人查询。

## 3. 安全与可靠性要求

- HTTPS 必须执行证书校验；禁止关闭 TLS 校验。
- 禁止用 `eval`、`exec`、shell 或 JavaScript runtime 执行远端 HTML/脚本。HTML/JSON 只能由受限解析器解析；格式不符合预期时 fail closed。
- 目标主机固定为已核实的供应商主机；关闭不受限重定向，设置有限连接/读取超时、最大响应字节数和可测并发/请求频率。仅把 429 映射为限流；供应商拒绝/权限错误映射为政策不可用；无效响应映射为 unavailable。
- 请求地点、乘客构成、票价、班次及原始响应不写日志、错误体、URL、遥测或前端 console；不持久化/缓存原始响应。错误只记录 request ID、provider、状态与异常类型。
- 不接受客户端传入任意 URL、文件路径、HTTP 头或 provider 参数；测试 fixture 仅通过依赖注入使用。
- API 默认不触网。启用 provider 是服务端显式配置；配置验证不得将真实凭证或响应内容回显。

## 4. 外部核验 Gate（编码前/真实调用前须有证据）

项目台账 E-004 当前状态为“未找到已验证方案”。以下事项未核实，不得更新为实测通过，也不得在生产默认启用：

1. 同程页面和 12306 各公开接口的当前使用条款、自动化访问限制、用途/再展示许可与署名要求；`fly-flight` 上游仓库没有声明许可证，因此本项目只允许独立编写适配，不复制上游实现。
2. 实际覆盖、班次日期范围、票价与座位字段语义、货币/精度、价格是否单人、税费包含情况及数据新鲜度。
3. 访问频率/限流、账号或资格要求、隐私传输和是否允许用于本项目场景。
4. 五个试点城市及常见机场/车站到供应商稳定代码的明确映射；有歧义时需用户选择，不能自动替代地点。

Gate 记录需附核验日期、官方来源链接、适用条件及脱敏实测摘要。用户提出接入请求不替代条款、来源和数据语义核验。

## 5. 验收

- provider 映射单元测试全用合成响应/mock HTTP，不触网；覆盖校验失败、TLS 默认校验、响应超限、超时、429、权限错误、空结果、价格单位错误、字段缺失、儿童人数、来源关联和 request ID。
- 集成测试验证默认未配置、不产生网络请求；显式 provider 配置后使用注入 mock transport 验证 API 到 provider 的完整映射与错误隔离。
- 检查日志、响应、OpenAPI 和构建产物不含原始地点/响应/凭证；跑 transport 全量测试、Ruff 和前端回归。
- 真实数据验收独立于代码测试：通过 Gate 后，在用户明确指定的测试条件下发起真实请求，记录查询时间、日期/地点覆盖、脱敏班次与金额语义。未实测前只记“provider adapter 已实现/真实数据未验证”。

## 6. 项目结构建议

```text
backend/app/modules/transport/providers/
  fly_flight.py                 # 同程/12306 隔离适配与窄解析器
backend/tests/unit/
  test_fly_flight_provider.py   # 合成 payload 与 mock HTTP
backend/tests/integration/
  test_transport_live_provider.py
docs/acceptance/
  transport.md                  # provider 流程与真实能力分开记录
```

依赖优先复用现有 `httpx`、标准库和现有 Pydantic 契约；若安全解析真实页面需要新增依赖，须在计划中评估许可、维护状态和 Python 3.14 兼容性后再批准。

## 7. 命令

```powershell
# backend/
uv run pytest tests/unit/test_fly_flight_provider.py tests/integration/test_transport_live_provider.py -q
uv run ruff check app/modules/transport tests/unit/test_fly_flight_provider.py tests/integration/test_transport_live_provider.py
uv run pytest -q

# frontend/
npm test -- --run
npm run build
```

## 8. 待确认事项

- 是否接受“该上游仓库无许可证，不复制代码；本项目只独立实现经过核验的公开来源适配”这一边界。
- 若 Gate 通过，是否先只启用铁路，还是同程航班和铁路都启用；当前同程 HTML 包含可执行 Nuxt payload，必须先找到并验证不执行远端代码的解析方式。
- 交通票价真实请求尚需明确测试地点/日期；同意集成不意味着对最终用户查询默认启用。默认保持关闭。
- 市内路线需另找独立供应商并单独核验，本规格不覆盖。
