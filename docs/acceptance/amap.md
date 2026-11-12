# 高德 API 验收记录

> 验收日期：2026-11-04（北京时间）
> 更新日期：2026-11-07（北京时间）
> 环境：本机 FastAPI + React/Vite；高德 Web 服务 Key 仅保存在被 Git 忽略的 `backend/.env`，本文不记录密钥。

## 接入范围

| 模块 | 后端调用 | 用途 |
|---|---|---|
| 酒店 | `POST /api/hotels/search` → 高德 `/v5/place/text`，类型 `100000` | 城市内酒店地点资料 |
| 活动 | `POST /api/activities/search` → 高德 `/v5/place/text`，类型 `080000` | 娱乐休闲场馆地点资料 |
| 景点 | `POST /api/attractions/search` → 高德 `/v5/place/text`，类型 `110000` | 景点、公园和地标地点资料 |
| 地图 | `POST /api/maps/search` → 高德 `/v5/place/text`；`POST /api/maps/static` → `/v3/geocode/geo`、`/v3/staticmap` | 地点搜索、城市中心和静态地图预览 |

所有高德请求均由后端固定代理，前端只调用同源 `/api`。地点坐标明确标为 GCJ02；无坐标地点保留文字信息但不能定位。地图是静态预览，可缩放，不承诺拖动、导航或路线规划。

## 自动化证据

- `backend`: `uv run pytest -q`，**407 passed**；包含无 Key 不联网、城市限制、供应商错误/限流、坏响应、分页、GCJ02、静态图 MIME/大小和日志密钥脱敏。
- `frontend`: `npm run test:unit -- --run`，**98 passed**；包含四模块请求、加载/空/错误状态、过时响应取消、分页、无坐标按钮、地图 Blob 生命周期和城市切换。
- `frontend`: `npm run typecheck` 与 `npm run lint` 通过。
- `frontend`: 高德 Playwright E2E 桌面与 Pixel 7 共 **4 passed**；覆盖四模块搜索、POI 选点、地图缩放/重试、切换城市清理和移动端无横向溢出。
- 地图视口截图复核：1440、768、390 px 均无横向溢出；调整地图工具栏控件对比度。检查使用 mock 图片，仅验证布局，不作为地图瓦片内容验收。
- OpenAPI 已导出到 `frontend/src/shared/openapi.json`，生成类型位于 `frontend/src/shared/api-contracts.ts`。

## 真实连通性快照

使用本地配置 Key 对上海执行一次受控检查：酒店、活动场馆、景点和地图地点搜索均返回 10 条高德 POI；城市中心静态地图和选中 POI 静态地图均返回 PNG。响应不包含 Key，日志中的高德请求参数已脱敏。

这只是一次本地连通性快照，不代表高德生产配额、持续可用性、商业许可或所有城市数据质量已验收。酒店价格/余房、活动日期/场次/票价、景点开放/预约状态均保持未知，需要另行授权的数据源或人工核实。
