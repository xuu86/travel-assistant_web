# SPEC：服务器交通查询能力补齐

> 版本 v0.1，2026-11-12，用户已批准继续实施。本规格扩展现有交通契约、Amadeus 航班规格和 FlyAI 铁路规格。现状与已部署页面修复见 [核验记录](acceptance/transport-server-2026-11-12.md)。能力以验收记录为准。

## 目标与假设

用户反馈服务器“所有交通查询”不可正常使用。目标是让铁路、航班、公交/地铁、步行、出租车/驾车通过应用接口查询实际来源，准确显示缺失数据和失败原因。

本规格采用以下假设：保留已接通的 FlyAI 铁路；航班增加 FlyAI 选项并保留 Amadeus 兼容；市内路线接入高德；复用已有服务端凭据和现有依赖。仅查询与展示，不包含预订或支付。FlyAI 航班权限及实际输出字段仍需限定真实查询验证，不能从铁路成功推断航班成功。

## 已知问题与范围

- 铁路真实查询可返回车次，但缺少确定票价；该缺失继续明确展示。
- 航班现仅支持 Amadeus，服务器未配置对应凭据，因此返回 `unconfigured`。
- 路线服务没有实际 RouteProvider；服务器现有高德 Key 的步行、驾车、公交方向接口均已通过一次实际调用。
- 页面提前误报未配置已单独修复并部署，不纳入待实现能力。

本规格补齐航班供应商、三种市内路线、查询城市上下文及必要的状态展示。维持现有 API 响应封装和模块边界，不引入网页抓取、隐式供应商切换或模拟结果。

## 技术栈

沿用 Python 3.14、FastAPI、Pydantic、httpx；前端沿用 React 19.3.1、TypeScript 5.9.3、Vite 8.3.5。FlyAI 使用已有 Node 24.22.1 和固定 `@fly-ai/flyai-cli@1.0.16` 官方 bundle，不新增全局安装。

## 能力与契约

### 航班

- 将 `APP_TRANSPORT_FARE_PROVIDER` 扩展为显式选择 `amadeus` 或 `flyai`，默认仍关闭。铁路仍使用独立 `APP_TRANSPORT_TRAIN_PROVIDER`，两者互不影响；不自动选择或回退供应商。
- FlyAI 航班复用服务端 SecretStr Key、受控 CLI 执行器及官方 `search-flight`。保留固定 bundle 完整性校验，SHA256 为 `194a66eb84094f3d8ee20fac0a2d6cae10a405cd59ac100b7e7880ebc97297da`。
- CLI 启动器只放行与本次查询类型匹配的官方工具；铁路仅允许 `search_domestic_train`，航班工具名依固定官方 CLI 的实际调用契约核对并测试后放行。禁止通配工具、shell 命令及客户端指定工具名。
- 保留当前 IATA 输入边界，传递明确的起降代码和出发日期；按实际返回的机场、分段、航班号、时间和舱等映射，不从城市名猜机场。
- 单成人字段 `adultPrice` 仅在币种、精度、覆盖范围和计价人数语义可证明时映射为对应单人价；不能证明时金额为 null，不按人数乘出整单价格。儿童票或混合乘客的价格无法证明时保留未知，并明确查询未验证儿童报价和所选人数可售情况。
- 时间只有具备明确偏移或受控机场时区时才转换；无法确定时保留未知。缺少价格、余票或时间等字段时返回 `partial` 与对应缺失信息。
- 仅保留通过现有官方 HTTPS 域名校验的详情链接；平台提示按纯文本展示。账户无权限返回 `policy_unavailable`，不伪装成空结果。

### 公交、步行与出租车/驾车

- 新增显式 `APP_TRANSPORT_ROUTE_PROVIDER=amap`，默认关闭；仅在现有 `APP_AMAP_API_KEY` 或其兼容别名非空时构造 RouteProvider。
- 固定调用高德官方 `restapi.amap.com`：步行 `/v3/direction/walking`、驾车 `/v3/direction/driving`、公交 `/v3/direction/transit/integrated`；所需地理编码/POI/坐标转换也仅使用已核实的官方路径。
- `RouteQuery` 增加兼容的可选 `city_id`，复用项目现有城市标识和目录映射。页面允许用户明确选择路线城市，并可使用当前已选目的地城市作为可见默认值。没有城市上下文且不能唯一解析地点时提示补充，不猜测同名地址。
- 地点已有经纬度时使用坐标；只有名称时按城市进行受限地点解析。只接受足够明确的地点，多个无法消歧的候选返回 `no_coverage` 和补充具体地址的说明。响应保留实际解析的起终点名称，便于用户判断。
- 现有 PlaceRef 与路线 geometry 使用 WGS84；高德使用 GCJ-02。必须在供应商边界显式转换：GPS 输入使用官方转换能力，返回轨迹采用经验证的逆转换并标注处理方式；如果无法提供契约要求的可靠坐标，省略 geometry 并返回 `partial`，不得把 GCJ-02 标为 WGS84 或生成直线冒充路线。
- 返回实际供应商给出的距离、时长、公交线路和换乘步骤，缺失字段保持未知。没有证据证明实时拥堵或指定出发时刻能力时，耗时标为通常估算，不把当前结果当作未来指定时间的实况。
- 公交票价仅使用明确的来源金额及计价语义；出租车金额只展示高德实际返回的打车估算，使用 `meter_estimate` 等契约字段和“估算”标识，不代表最终收费。未返回金额时不计算或补零。
- 解析、转换与方向查询的调用总数必须有硬上限：每个应用请求最多 8 次上游调用，整体超时不超过 30 秒，无自动重试。超过边界返回明确服务状态，不继续请求。

### 交互与状态

- 首次打开和条件变化后处于待查询状态；请求结束后使用真实 API 的状态。
- 铁路、航班和每种路线维持独立请求状态；旧请求不能覆盖新条件或其他模式的结果。
- 仅在确定配置缺失时展示“服务尚未配置”；权限、限流、未覆盖、网络故障和部分结果分别解释。
- 如需要展示已启用模式，使用只包含布尔能力的服务端配置状态，不返回密钥、路径或原始环境信息；配置成功不能表述为某条查询一定有结果。

## 安全与可靠性边界

- 沿用现有传输错误映射：401/403 为 `policy_unavailable`，429 为 `rate_limited`，网络/协议异常为 `unavailable`；无方案和失败分别处理。
- FlyAI 沿用每次查询至多一次受控官方 MCP 请求、45 秒请求与 50 秒父进程超时、1 MiB 输出限制和最多 2 个并发进程。Key 仅环境传入，不使用默认试用凭据，不放宽 TLS、代理或 Node 注入边界。
- 高德请求校验 TLS、禁止重定向、限制响应体和超时，复用现有可审计网络处理约定。客户端不得传入任意 URL、Header 或供应商参数。
- 日志不保存凭据、查询地点、日期、出行人构成或供应商原文；错误和测试断言不得泄露这些内容。SourceRef、请求 ID 和查询时间贯穿映射。
- 始终保留未知字段，不构造票价、余票、税费、儿童优惠和路线。不得以单次成功承诺全部城市、线路、权限或配额。

## 项目结构与代码风格

```text
backend/app/core/config.py                     # 显式配置与完整性判断
backend/app/modules/transport/runtime.py       # 构造独立 Fare/Route Provider
backend/app/modules/transport/contracts.py     # 兼容城市上下文
backend/app/modules/transport/providers/       # FlyAI 航班与高德路线适配
backend/tests/unit/                           # 合成映射与网络/进程边界测试
backend/tests/integration/                    # API、配置与 Provider 注入测试
frontend/src/features/transport/              # 查询城市、状态、结果展示
frontend/src/shared/                          # 更新生成的 OpenAPI 类型
frontend/e2e/transport.spec.ts                 # 桌面和手机交互
docs/acceptance/                              # 代码与真实能力分开记录
```

遵循现有 Ruff 100 字符行宽和 Python snake_case；TypeScript 沿用类型明确的 QueryState。示例沿用项目接口，不创建返回演示数据的分支：

```python
def search_routes(self, query: RouteQuery, *, request_id: UUID) -> RouteResult:
    if not self.supports(query.mode):
        raise TransportProviderError("no_coverage")
    return self._search(query, request_id=request_id)
```

## 验证命令与测试策略

在完整检出并具备现有锁定依赖的目录执行，不额外升级依赖。常用 PowerShell 命令：

```powershell
# backend/
uv run pytest -q
uv run ruff check .

# frontend/
npm run typecheck
npm run lint
npm run test:unit -- --run
npm run build
npm run test:e2e -- e2e/transport.spec.ts
npm run secretlint -- "src/**/*.{ts,tsx}" "e2e/**/*.ts"

# 仓库根目录
git diff --check
```

默认测试使用合成 payload、httpx MockTransport 和 CLI executor 注入，不触网。覆盖无配置、模式隔离、人数/日期/机场校验、分段顺序、缺失与异常金额、未知时区、地址歧义、坐标系边界、超时/响应上限/调用预算、供应商错误、敏感信息及旧请求隔离。

集成测试验证完整配置才启用、无配置不调用上游、响应契约兼容与 request_id 保留。Vitest 与 Playwright 验证三种路线和两种票务在桌面/手机端的待查询、加载、成功、部分结果及错误状态。

实现后的真实 smoke 使用现有已配置账户和本次故障核验范围：航班单程一次、铁路一次、三种市内路线各一次应用 API 调用，无循环重试，仅记录脱敏统计。出发日选择服务器当前日期之后的有效日期；不能以合成测试代替真实接口验收。账户权限不足时如实记录结果，不将该能力标为恢复。

## 操作边界

- 始终：先验证后部署，保留当前生产备份与已可用铁路能力，必要配置显式启用，服务器密钥不进入 Git，生成 API 类型后校验一致性。
- 需要再次确认：新增付费账户或依赖、引入预订/支付、修改数据库或扩大到批量持续真实查询。这些不属于本次修复。
- 禁止：硬编码密钥、跳过失败测试、改变固定官方 CLI bundle、自动抓取售票网页、静默切换供应商、伪造缺失信息。

## 成功标准

1. 无配置测试不发送上游请求，铁路与航班配置互不覆盖，原铁路回归测试通过。
2. FlyAI 航班实际查询返回可映射班次，或准确解释账户权限/覆盖问题；只有成功后才宣称航班恢复。
3. 公交、步行、驾车在服务器通过应用 API 返回来源路线，并显示实际起终点、距离/时间及可核实费用；不再因缺少 RouteProvider 返回 `unconfigured`。
4. 坐标、城市消歧、儿童/人数/金额未知信息通过有辨别力的测试，页面不提前显示配置故障或复用旧结果。
5. 测试、类型检查、Lint、构建及密钥扫描通过；生产部署后核验健康与静态资源版本，记录真实能力的范围和仍存在的字段缺口。

## 未解决问题

- 现有 FlyAI Key 是否拥有航班权限，以及真实航班输出能证明哪些价格与余票字段，需要实现后的限定查询确认。
- 高德地址消歧、轨迹转换和所需来源署名按现有项目契约落实；本次直接方向接口成功不能代替这些应用级验收。
- 铁路与航班供应商可能不返回确定票价；恢复查询不等于恢复全部价格、儿童票或余票信息。

用户已批准“FlyAI 航班 + 高德市内路线，保留既有铁路和 Amadeus 兼容”并要求继续实施。实现、部署与限定真实验收已于 2026-11-13 完成，具体结果见验收记录。
