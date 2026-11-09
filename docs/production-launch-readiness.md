# 生产上线准备与 API 清单

> 更新日期：2026-11-07（北京时间）
> 当前结论：本项目适合本机演示/内部评审，尚未达到公网真实旅游服务上线门槛。本文记录现有 API、外部供应商申请项和配置位置；列出不代表已申请、获批或接入。

## 1. 当前 API 状态

| 能力 | 当前接口/来源 | 当前状态 | 上线前所需外部 API |
|---|---|---|---|
| 城市注册表 | `GET /api/foundation/cities`、`GET /api/foundation/cities/{city_id}` | 五城静态注册数据；运行时不调用地理 API | 无必要的运行时 API；若扩城或改坐标，需继续核验数据来源、许可和坐标证据 |
| 预算 | `POST /api/budget/calculate` | 本地无状态计算，不产生供应商报价 | 无；如将来展示真实费用，必须接入并区分对应报价来源 |
| 天气 | `POST /api/weather/forecast` | Open-Meteo adapter 已实现；2026-10-29 五城各一次单日 smoke 通过。仅为历史连通性快照，免费服务用途资格、持续可用性和未来覆盖未获保证 | 公网/商业用途先取得相应许可；生产另需配额、可用性监控与运行保障 |
| 航班 | `POST /api/transport/fares/search` | Amadeus adapter 与 mock 验收已完成，默认关闭；真实航班数据未验收 | Amadeus 账号资格、商业条款、目标航线、价格/税费语义和 live smoke 仍待确认 |
| 铁路 | `POST /api/transport/fares/search` | FlyAI 官方 CLI provider 已接入；一次本地真实 API 查询通过，但返回金额及余票未知，不构成价格/库存验收 | 账户权限、配额、用途、缓存及价格语义仍待核实；不以未知值推断可购或确定票价 |
| 市内路线 | `POST /api/transport/routes/search` | 契约与 fake 流程已实现；未接入路线 provider | 地图/路径规划 API；需按步行、公交、驾车/出租车逐项确认覆盖、计费、许可和路线数据用途 |
| AI 助手 | `POST /api/assistant/chat` | 服务端 adapter 已实现；无配置时为 `unconfigured`，未验证真实模型 | 支持当前 OpenAI-compatible Chat Completions 的模型 API；E-007 尚未核准供应商、模型、价格、地区、隐私条款与质量 |
| 行程 | 当前无服务端读写接口 | 前端手动草稿只存当前页面内存 | 若需要刷新恢复/跨设备，须先建设身份、owner scope 和行程存储 API；不能用模型 API 替代 |
| 酒店/活动/景点/地图 | 高德 Web 服务 POI、地理编码、静态地图代理已接入；`/api/{hotels,activities,attractions,maps}/search` 与 `/api/maps/static` 已有前端调用和自动化测试；上海真实连通性快照通过 | 可本机演示；生产仍需确认高德 Web 服务 Key 的主体、配额、白名单、商业/展示许可和监控。POI 不包含酒店库存/报价、活动档期或景点开放预约状态 | 生产前完成高德账号与用途授权、配额/费用告警、真实生产 origin smoke；价格/库存/活动档期/开放预约须另接有授权的数据源 |

酒店、活动、景点与地图能力已完成本地实现与验收，但高德生产授权、配额、商业用途和持续可用性仍待上线前确认；导入、推荐、认证、持久化和导出未实现，行程仅为前端内存手工草稿。地图 POI 搜索不等同市内路线 provider。模块状态详见 [Web Capability Map](../Web-Capability-Map.md)、[Amap SPEC](SPEC-amap-integration.md) 与 [Amap 验收记录](acceptance/amap.md)。

现有 REST 路径的 schema 可在运行服务的 `/docs` 和 `/openapi.json` 查看。路径存在只说明 API 契约，不表示后端已有真实数据来源。

## 2. API 申请与配置位置

### AI 模型 API

先由项目负责人确定供应商/模型，再核对其账号资格、数据处理和保留条款、服务地区、价格、额度、限流、结构化 JSON 输出能力及服务可用性。当前 adapter 要求兼容 Chat Completions，并在配置的 base URL 后拼接 `/chat/completions`。OpenAI-compatible 不等于任意厂商都兼容，需用获批账号做单独集成验收。

配置名与位置：

- 开发机：在仓库根目录执行 `Copy-Item backend/.env.example backend/.env`，然后编辑未纳入版本库的 `backend/.env`，填写 `APP_MODEL_BASE_URL`、`APP_MODEL_NAME`、`APP_MODEL_API_KEY`；可选调整 `APP_MODEL_TIMEOUT_SECONDS`（1–30 秒）。填写后重启后端。
- 生产环境：配置在部署平台的**后端服务 Secret/Environment 设置**或专用密钥管理器，不配置到前端 `.env`、Vite `VITE_*`、Git、浏览器或聊天记录中。
- 更换 provider、模型、API 请求格式或配置名之前，更新 assistant SPEC/adapter 并跑 fake、集成和真实供应商验收。真实 Key 不要写入本文件或 `.env.example`。

供应商申请入口尚未作为生产选型批准。可供项目负责人评估的官方平台入口包括 [智谱开放平台](https://open.bigmodel.cn/) 和 [DeepSeek 开放平台](https://platform.deepseek.com/)，这不是已批准供应商清单；应在平台确认账号资格、模型 ID、兼容 endpoint、地区可用性、费用、隐私条款和结构化输出行为后再选择。本机开发配置与生产选型、真实模型验收相互独立；不要在文档或聊天中记录本机 Key 状态。配置齐全只会使 adapter 发起调用，不代表 E-007 已通过。

### 天气 API

- Open-Meteo adapter 已实现；官方条款、价格、许可和 API 文档于 2026-10-29 核查，五城各一次单日连通性检查已留证：[验收记录](acceptance/weather-provider.md)、[Gate](weather-provider-gate.md)。数据需署名；免费服务仅限非商业用途且无 uptime 保证。
- 现有 smoke 不证明持续可用、准确性、未来日期覆盖或比赛展示/部署的使用资格。用途若超出已核实的非商业本机试用，应先重新核验并取得相应许可；生产还需配额和可用性监控。

### 航班、铁路、地图路线 API

- 先选供应商并完成开发者/合作方申请、生产调用授权、地区覆盖、字段语义和价格/额度确认。航班/铁路价格与库存多为商业合作能力；申请未成功时继续显示 `unconfigured`，不以爬网页、用户 Key 或模拟数据替代。
- 地图展示/POI 当前使用[高德开放平台](https://lbs.amap.com/)的 Web 服务 API；本项目调用 [地点搜索](https://lbs.amap.com/api/webservice/guide/api/search)、[地理编码](https://lbs.amap.com/api/webservice/guide/api/georegeo) 和 [静态地图](https://lbs.amap.com/api/webservice/guide/api/staticmap) endpoint，统一由后端代理，Key 配在 `backend/.env` 的 `APP_AMAP_API_KEY`，不进入前端。高德 Key 类型、IP 白名单、配额、商业许可与用户端地图能力仍需上线前核验。市内路线尚未使用高德路线 API，仍归 transport 模块。
- 只有供应商获批后，才在后端加入对应 Settings、SecretStr、静态 provider 注册和 `.env.example` 空变量，并加供应商 mock 测试、脱敏日志及真实覆盖验收。密钥只进后端 Secret Manager。

### 酒店、景点、活动 API

酒店、景点、活动模块当前复用高德 POI 目录能力，分别按酒店、娱乐休闲场馆、景点类型筛选；这不是酒店预订、活动票务或景点预约 API。上线前需核验可展示字段、内容版权、更新时间和商业用途；不要把地图 POI 接口默认当成酒店余房/价格 API，也不要把目录数据标为实时库存。

## 3. 公网部署前的工程门槛

1. **访问控制与费用保护：** 设计游客/登录身份、owner scope、敏感写操作保护；为 AI 和所有高成本外部 API 加按主体/IP 限流、并发上限、配额/预算告警和供应商账单告警。CORS 不是认证。生产限流需支持多 worker/多实例，不能依赖单进程内存计数。
2. **持久化与隐私：** 若承诺保存行程，先定义数据库、迁移、备份/恢复、数据删除/导出、保留期限、加密和访问审计；未实现前要明确告知草稿刷新即丢失，不收集不必要的敏感旅行凭证。
3. **HTTPS 和网络边界：** 生产静态资源用构建产物 `frontend/dist`，由 CDN/静态托管/反向代理服务；FastAPI 用受管 ASGI 进程运行在私网，禁止直接公开开发端口。设置域名、TLS 自动续期、HTTP→HTTPS、HSTS、可信代理头、Host 校验、防火墙及请求体上限。
4. **生产配置：** 设置 `APP_ENV=production`、实际前端 HTTPS origin 的 `APP_ALLOWED_ORIGINS`、`APP_LOG_LEVEL=INFO`。当前 Settings 会拒绝 production 下的 HTTP origin；不要用 `*` 放开 CORS。生产密钥放云 Secret Manager，轮换而不落日志。
5. **可观测性与恢复：** 当前 `/api/health` 仅检查进程可响应，不是依赖 readiness。补充部署平台 liveness/readiness、错误率/延迟/provider 状态与额度告警、日志访问控制、备份恢复演练和回滚方案；监控标签不得携带请求正文、地点坐标、聊天内容或密钥。
6. **发布验证：** CI 通过后，在真实生产 origin 做 HTTPS/CORS、登录/owner scope、速率限制、模型/天气/交通供应商沙箱、迁移/备份恢复、移动端、依赖与构建产物密钥扫描。填写 [Web 验收矩阵](../../travel-assistant/docs/Web验收矩阵.md) 证据；没有证据的能力标未通过/阻塞。

## 4. 当前可配置环境变量

| 变量 | 用途 | 当前实现/要求 | 配置位置 |
|---|---|---|---|
| `APP_ENV` | 环境标识 | `development`/`test`/`production`；production 要求 CORS origin 为 HTTPS | 后端环境变量/Secret Manager |
| `APP_ALLOWED_ORIGINS` | 精确允许的浏览器来源 | 必须是唯一、规范的 origin；禁止 `*`；生产只能 HTTPS | 后端环境变量/Secret Manager |
| `APP_LOG_LEVEL` | 后端日志级别 | 默认 `INFO` | 后端环境变量 |
| `APP_MODEL_BASE_URL` | OpenAI-compatible provider base URL | 服务端配置；代码追加 `/chat/completions`；不得包含 URL 凭证/query/fragment | `backend/.env`（本机）或后端 Secret Manager |
| `APP_MODEL_NAME` | 供应商模型 ID | 必须与所申请的账号和 endpoint 对应 | `backend/.env` 或后端 Secret Manager |
| `APP_MODEL_API_KEY` | 模型服务密钥 | `SecretStr`；只允许后端读取 | `backend/.env`（不提交）或后端 Secret Manager |
| `APP_MODEL_TIMEOUT_SECONDS` | 单次模型请求 timeout | 默认 30，范围 1–30；总操作可能因有限重试更久，代理超时需匹配 | 后端环境变量 |
| `APP_AMAP_API_KEY` | 高德 Web 服务 Key；酒店、活动、景点 POI 与静态地图共用 | `SecretStr`；只允许后端读取，不能放入 `VITE_*` 或浏览器 | `backend/.env`（不提交）或后端 Secret Manager |
| `APP_AMAP_TIMEOUT_SECONDS` | 高德单次请求 timeout | 默认 10 秒；后端限制请求体大小并禁止重定向 | 后端环境变量 |

当前没有数据库、认证、Redis 的生产配置项。地图/地点已有后端配置入口，但高德生产授权与持续可用性仍有上述缺口。不要在前端添加 Key，也不要把未实现能力或配置变量当作已接入功能。

## 5. 本地启动与当前对外边界

本机开发命令见 README。默认监听 `127.0.0.1`，只供当前电脑访问；Vite 开发服务器不是生产 Web 服务器。没有 HTTPS、身份/授权、成本防护、供应商实测和隐私/用途确认前，不要端口转发或将开发服务公开到互联网。
