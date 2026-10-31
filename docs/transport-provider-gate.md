# 交通真实数据 Provider Gate

> 最近核查：2026-10-31（北京时间；本次增补 FlyAI，其他来源保留原核查记录）
> 范围：官方 API 可行性、条款边界与 adapter 实施 Gate；已按用户授权完成首次独立 CLI 诊断及新增后端 API 真实铁路查询，各 1 次、0 重试，仅保存脱敏统计。未调用 Amadeus、同程或 12306 的班次/票价查询接口。
> 结论：Amadeus 航班为 **CONDITIONAL**；FlyAI 铁路官方 CLI 为 **CONDITIONAL（本地真实 API 已验收）**；同程网页、12306 网页/内部接口仍 **BLOCKED**，市内路线待选 Provider。本记录不构成法律意见、供应商授权或真实数据验收。

## 决策摘要

| 来源 | 当前结论 | 已能确认 | 仍未满足 / 阻塞项 |
|---|---|---|---|
| Amadeus Flight Offers Search 官方 API | CONDITIONAL | 官方 Self-Service API 有固定 test/production HTTPS 主机与 Flight Offers Search 接口；可在默认关闭、显式凭据、MockTransport 验收的条件下实现 adapter | 生产环境资格与审核、商业条款、目标中国国内航线覆盖、CNY 报价、儿童年龄口径、配额/频率、缓存与展示/署名、最终确认价语义、受控 live smoke 均未完成项目级核验 |
| FlyAI `search-train` 官方 CLI 1.0.16 | CONDITIONAL；用户批准的本地 API 查询通过 | 固定版本及完整性、受控进程、铁路映射/网页展示、单次 API 真实查询均完成；10 条方案、13 个分段 | 确定票价、余票、全部账户权限/配额、缓存及公开部署用途仍待核实；CLI 升级需复核；不直接实现包内 HTTP 协议 |
| 同程国内航班公开页面 | BLOCKED | 官网存在国内机票服务、服务协议入口和站点法律声明；法律声明对网站资料使用范围有限制 | 未找到允许本项目自动化抓取、存储/再展示航班和价格数据的明确授权；机票预订协议正文、字段精度、计价基准、更新时间、自动化访问和限流不明 |
| 12306 公开铁路查询 / 内部接口 | BLOCKED | 官方网站面向用户提供时刻表、余票和票价信息查询；官方购票说明提示勿使用未授权网站/App | 未找到面向第三方程序化调用 `kyfw.12306.cn` 内部查询/票价接口的官方 API 授权、稳定契约或限额；票价单位、席别、儿童规则、覆盖窗口和自动化边界未确认 |
| 公交 / 地铁 / 步行 / 出租车路线 | BLOCKED / deferred | `fly-flight` 不具备这些路线能力；现有 transport 只保留契约和 fake 流程 | 没有获核验的路线 Provider、许可、额度、署名、计价语义和单独规格 |

Amadeus 与 FlyAI 条件方案均已实现；FlyAI 在已有用户授权范围内完成本地 API 真实验收。仓库默认配置关闭，本地显式启用；此记录不代表公网生产部署或确定票价已通过。

## FlyAI 铁路：v0.2 官方 CLI 适配

v0.1 要求稳定独立 HTTP/SDK，公开材料不足。用户现已明确批准“后端封装官方 CLI”，[规格](SPEC-flyai-train-provider.md)及[实施计划](../tasks/flyai-train-provider-plan.md)已同步；历史核查见[契约记录](flyai-train-contract-review.md)。固定 CLI 1.0.16、完整性检查、密钥环境隔离、无 shell、单次官方目标 POST、无重试、超时/响应/并发限制已实现。

[新增 API 真实验收](acceptance/flyai-train-api-smoke-2026-10-31.json)在本地查询上海→杭州、2026-11-01，HTTP 200、CLI exit 0、10 条结果、13 个分段。金额始终 null，网页显示“票价未返回”。CLI 不支持人数条件，结果不声称按乘客数报价或筛选余票。只展示通过官方 HTTPS 域名校验的详情链接，平台提示按纯文本显示；本次真实结果没有链接通过校验。

网页状态/席别/链接展示由合成测试与 E2E 验证，不重放真实查询。未知价格语义、账户全部权限、配额、缓存和公开部署用途保留未决；不把历史 Gate A 当作阻止已批准 CLI 本地实施的依据。

## Amadeus：条件方案与主机边界

- 官方接口文档：[Flight Offers Search](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search)。
- 固定端点：
  - test：`https://test.api.amadeus.com/v1/security/oauth2/token`、`https://test.api.amadeus.com/v2/shopping/flight-offers`
  - production：`https://api.amadeus.com/v1/security/oauth2/token`、`https://api.amadeus.com/v2/shopping/flight-offers`
- 代码只接受服务端显式配置的 `amadeus` provider、Client ID 和 Client Secret；实现执行 TLS 校验、关闭重定向、禁用环境代理继承、限制超时和响应体，并使用 `httpx.MockTransport` 测试。
- 当前不实现 Flight Offers Price、预订、支付、锁价或锁位。搜索响应的 `price` / `travelerPricings` 只能标记为查询时 party total；最终可购价格和库存仍需供应商确认流程。
- 当前有受控 IATA → IANA 时区 allow-list；未覆盖机场会返回 partial，而非猜测时区。
- 中国国内航线是否普遍返回、是否以 CNY 报价、儿童年龄限制和税费明细，仍须以真实供应商响应与官方条款核验；不能由测试 fixture 推断。

### Amadeus 重新开启完整 Gate 所需证据

1. 项目实际使用的 Amadeus 账户、test/production 环境和生产资格证明；确认 API key 的使用主体、条款版本和商业用途范围。
2. 目标试点城市/机场的覆盖证明、CNY 报价测试、税费与 party-total 语义、儿童年龄口径和最终确认价边界。
3. 配额、并发、频率限制、允许缓存时间、展示期限、署名要求和隐私/日志边界。
4. 对限定查询单独批准 live smoke：地点、日期、次数、环境、证据保存与脱敏方式。用户批准代码接入不等于批准 live smoke。

## 同程：保留的 BLOCKED 证据

1. [同程旅行法律声明](https://www.ly.com/public/law.html)，访问日期 2026-10-29：页面说明资料下载仅供个人学习研究使用，不得用于商业用途；未经网站或版权所有者明确书面同意，不得分发、修改、散布、再使用、再传递或用于公众商业用途。该声明不足以证明本项目可抓取并再展示机票数据。
2. [同程旅行用户协议与隐私条款目录](https://www.ly.com/public/Lawprotocols)，访问日期 2026-10-29：目录列有“同程旅行服务协议”“软件许可使用协议”“机票预订协议”；本次未取得“机票预订协议”正文或第三方自动化访问许可。
3. [同程国内机票入口](https://www.ly.com/flights/home)，访问日期 2026-10-29：存在公开用户网页入口，但不是经核实的第三方 API 文档。
4. [上游 fly-flight 仓库](https://github.com/baizhexue/fly-flight)：未声明可见开源许可证。项目不复制、不安装、不执行其代码，也不把其网页抓取方式视为授权。

**字段/运行语义：** 官方可审阅材料未确认抓取频率、限流/封禁规则、允许缓存时间、再展示范围、价格单位、单人/团队基准、税费包含项、航班时间区、数据更新时间或五城机场映射。现阶段不得把网页数字映射为 CNY 整数分或 `live` 证据。

## 12306：保留的 BLOCKED 证据

1. [12306 互联网购票常见问题](https://kyfw.12306.cn/otn/gonggao/onlineBooking.html)，访问日期 2026-10-29：官方说明 12306 网站提供旅客列车时刻表、余票、票价等客运信息查询；同页建议使用官方网页/客户端购票，并提示不要使用非官方网站或手机 App 购票。该资料描述面向用户的官方服务，不是第三方程序化 API 文档。
2. [铁路旅客运输规程](https://kyfw.12306.cn/otn/gonggao/saleTicketMeans.html?linktypeid=means2)，访问日期 2026-10-29：官方规程说明车票主要信息包括票价、车次、乘车日期和时间；第八条说明票价为旅客购票时的执行票价。儿童票规则需结合符合优惠条件的未成年人资格判断。
3. [12306 官方首页/服务导航](https://kyfw.12306.cn/otn/index/init)，访问日期 2026-10-29：提供“公布票价”“时刻表”等官方信息查询入口；页面同时声明铁路未授权其他网站或 App 开展类似服务内容。查询与购票的适用范围未细分，因此自动采集/再展示资格保持未决并阻止接入。

**字段/运行语义：** 公开材料未提供 `queryG` 或 `queryAllPublicPrice` 的稳定、获授权第三方 API 契约；金额单位/精度、字段索引、余票文本、查询频率、日期覆盖和响应稳定性均未获官方文档确认。

## 地点覆盖与映射

城市级输入无法唯一识别机场/车站：上海、杭州、苏州、无锡、嘉兴等均有多个机场、铁路站或跨城可达站点。当前实现：

- 航班必须由用户输入明确的 IATA 机场代码；
- 不从城市名、地址或浏览器坐标静默生成 IATA；
- IANA 时区只使用代码内受控 allow-list，未知机场保留 null/partial；
- 铁路透传明确城市/车站名称，校验首尾返回站点/城市与请求一致；不从坐标推断车站。市内路线尚无真实 provider。

后续需要可审计的机场/车站目录、版本和歧义选择流程，不能把历史别名或未经批准页面提取值提升为 verified。

## 测试/请求边界

- 本轮没有创建或使用真实 Amadeus 凭据，没有发送 OAuth 或航班查询请求。
- 自动化回归使用合成 payload、MockTransport 或同源 API mock；E2E 不触达供应商。FlyAI 另行执行已授权的有限真实查询，见上述独立记录。
- 更正历史操作：此前分析 `fly-flight` 时，曾两次 GET 同程公开航班结果页 `https://www.ly.com/flights/itinerary/oneway/BJS-SHA?date=2026-11-10`。请求没有携带乘客信息；响应只用于检查 SSR 结构，没有把报价或班次写入项目，也未调用独立 JSON 票价 API。按当前 Gate，该访问不视为获授权的受控 live smoke，也不构成真实数据验收。
- 未请求 12306 班次/票价查询端点。

## 重新开启其他来源所需证据

1. 同程对本项目用途的书面自动化访问和结果展示授权，或明确适用的官方开放 API/合作接口条款；并确认署名、频率、缓存及价格字段语义。
2. 铁路使用正式授权的第三方 Railway Provider 或 12306 明确开放/授权接口；必须先取得接口文档、票价/余票/儿童规则、限流和再展示条件。
3. 市内路线单独选择获准供应商，明确 mode 覆盖、几何数据、实时/估算时长、计价语义、配额与署名。
4. 每个来源独立批准限量 live smoke 的地点、日期、次数、环境、证据保存和脱敏方式。
