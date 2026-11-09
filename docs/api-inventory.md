# 项目 API 来源清单

下表区分“项目自己的接口”和“后端实际调用的外部服务”。外部密钥只在后端读取，前端不保存供应商 Key。

## 外部服务

| 能力 | 调用谁 | 代码中的网址 | 配置/状态 |
|---|---|---|---|
| 五个试点城市中心坐标 | NGA GeoNames 地名记录（静态登记数据） | [NGA GeoNames 服务](https://geonames.nga.mil/geon-ags/rest/services/RESEARCH/GIS_OUTPUT/MapServer) | 坐标及记录 ID 已固化在后端注册表；运行时不请求该服务 |
| 天气 | Open-Meteo Forecast API | [Forecast API](https://api.open-meteo.com/v1/forecast)；[文档](https://open-meteo.com/en/docs) | 无 Key；`APP_WEATHER_PROVIDER` 启用时调用 |
| 酒店、活动场馆、景点 POI | 高德地图 Web 服务 | [地点搜索](https://restapi.amap.com/v5/place/text)；[官方说明](https://lbs.amap.com/api/webservice/guide/api/search) | `APP_AMAP_API_KEY`，服务端 `SecretStr` |
| 城市中心地理编码 | 高德地图 Web 服务 | [地理编码](https://restapi.amap.com/v3/geocode/geo)；[官方说明](https://lbs.amap.com/api/webservice/guide/api/georegeo) | 与高德 POI 共用 Key |
| 静态地图 | 高德地图 Web 服务 | [静态地图](https://restapi.amap.com/v3/staticmap)；[官方说明](https://lbs.amap.com/api/webservice/guide/api/staticmap) | 与高德 POI 共用 Key，后端代理图片 |
| 航班报价 | Amadeus Self-Service APIs | [测试 Token](https://test.api.amadeus.com/v1/security/oauth2/token)、[测试航班报价](https://test.api.amadeus.com/v2/shopping/flight-offers)、[文档](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search) | 需要 `APP_TRANSPORT_FARE_PROVIDER=amadeus` 和 Amadeus 凭证；当前真实航班数据未验收 |
| 铁路查询 | FlyAI 官方 CLI / Fliggy FlyAI | [官网](https://flyai.open.fliggy.com/)、[文档](https://flyai.open.fliggy.com/docs) | `APP_TRANSPORT_TRAIN_PROVIDER=flyai` 和后端 Key；已留一次真实查询记录，价格/余票未知 |
| AI 助手 | OpenAI-compatible Chat Completions；当前本机配置指向 DeepSeek | [DeepSeek 平台](https://platform.deepseek.com/)、[API 文档](https://api-docs.deepseek.com/) | `APP_MODEL_BASE_URL`、`APP_MODEL_NAME`、`APP_MODEL_API_KEY`；需按供应商条款单独验收 |

市内路线尚无真实路线 provider；酒店/活动/景点使用高德 POI，不含价格、库存、档期或预约状态。预算在本地计算，行程草稿目前仅保存在前端页面内存中，没有服务端行程 API。

## 本项目内部接口

| 模块 | 路径 |
|---|---|
| 基础城市 | `GET /api/foundation/cities`、`GET /api/foundation/cities/{city_id}` |
| 天气 | `POST /api/weather/forecast` |
| 预算 | `POST /api/budget/calculate` |
| 交通票价/路线 | `POST /api/transport/fares/search`、`POST /api/transport/routes/search` |
| AI 助手 | `POST /api/assistant/chat` |
| 酒店/活动/景点/地图地点 | `POST /api/hotels/search`、`POST /api/activities/search`、`POST /api/attractions/search`、`POST /api/maps/search` |
| 地图图片 | `POST /api/maps/static` |

接口 schema 以运行服务的 [`/docs`](http://127.0.0.1:8000/docs) 和 [`/openapi.json`](http://127.0.0.1:8000/openapi.json) 为准。地图 POI 搜索不等于市内路线规划；酒店 POI 也不等于房价或库存接口。
