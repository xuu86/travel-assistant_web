# 高德接入规格与实施记录

日期：2026-11-04。依据用户本轮“将高德 API 配置进酒店、活动、景点和地图模块”的实施请求；沿用已批准 Capability Map 的模块 ID 与依赖方向。

## 模块与边界
| 模块 | 本次交付 | 依赖 |
|---|---|---|
| foundation | 服务端高德 Web 服务 Key、固定地址 HTTP 客户端、POI 契约 | — |
| hotels | 城市内酒店地点检索，不提供房价与余房 | foundation |
| activities | 娱乐休闲活动场馆检索，不声称为有日期的活动公告 | foundation |
| attractions | 城市内景点检索，开放/预约信息缺失保持待核实 | foundation |
| maps | 地点检索、点位预览、缩放及来源；后端代理静态地图 | foundation 的地点数据；不拥有路线查询 |

顺序：共享契约/客户端 → 各查询 API → 前端面板/地图选择联动 → 验证。

## 目标与接口
- POST /api/{hotels,activities,attractions,maps}/search 接收 city_id、keywords、page（1–100），城市仅五个注册城市，页大小 10，严格限制城市。
- 返回既有 ResultEnvelope：live/partial/empty/unconfigured/rate_limited/policy_unavailable/unavailable，包含时间、来源与 request_id。
- 地点位置明确 GCJ02；无坐标的地点保留文字资料，但不能在地图中错误定位。
- POST /api/maps/static 接收 GCJ02 点位和 zoom（3–18），仅返回后端代理的图片，真实 Key 不进入前端。
- 高德 v5/place/text 提供 POI；城市中心由 v3/geocode/geo 解析；v3/staticmap 提供预览。
- 酒店报价/余房、活动档期/售票状态及景点预约/开放情况未由本次接口核实，UI 清楚标注未知，不生成假数据。
- 无 Key 时不访问高德；配置放 backend/.env 的 APP_AMAP_API_KEY，可读取兼容 AMAP_API_KEY。静态地图与检索共用 Web 服务 Key。

## 结构与风格
Python FastAPI/Pydantic/httpx；React/TypeScript/Vite；沿用 ResultEnvelope/SecretStr、现有纸色/深蓝界面、显式表单提交与可访问标签。不新增第三方依赖，不改动现有预算/天气/AI 和交通业务。
新增共享客户端 backend/app/core/amap.py、地点契约 backend/app/core/places.py；四个模块各自注册 router；前端复用地点检索面板并提供独立地图面板。
示例：PlaceLocation(longitude=121.47, latitude=31.23, coordinate_system="GCJ02")。

## 验证命令
backend：uv run ruff check app tests；uv run pytest -q；uv run python scripts/export_openapi.py ../frontend/src/shared/openapi.json。
frontend：npm run generate:api；npm run typecheck；npm run lint；npm run test:unit -- --run；npm run build。
测试边界：MockTransport 检验供应商错误/限流、空数据、无 Key 不联网、城市约束、未知字段和 GCJ02；地图代理检验 MIME/大小/错误与 Key 不外泄；前端检验请求、切城/过时响应、列表选点、加载与失败状态；桌面/移动视觉检查。

## 始终遵守与限制
不在 Git/日志/响应中公开 Key；固定供应商域名、不允许用户自定义代理 URL；请求有超时/响应体积限制；不删除或覆盖用户既有未提交修改。API 真实连通验证需本地有效 Key，无 Key 时交付接入代码并记录未实测状态。

## 任务
- [x] 共享配置、地点模型、供应商客户端和四模块路由。
- [x] 前端导航、地点搜索、地图预览和选点联动。
- [x] OpenAPI 类型、自动测试、构建与视觉检查。
- [x] 本地 Key 配置及可行的真实 API 连通性检查；更新交付记录。
