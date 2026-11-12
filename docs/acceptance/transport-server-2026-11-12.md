# 交通模块服务器修复与验收

实施日期：2026-11-12 至 2026-11-13（北京时间）。站点：<http://43.143.125.176:18080/>；应用目录：`/opt/travel-assistant/app`。本记录不保存密钥或供应商原始响应。

## 修复结果

原先页面在查询前误报所有交通服务未配置；服务器航班未接入现有 FlyAI 账户，市内路线没有 RouteProvider。现已部署 FlyAI 航班、高德步行/公交/驾车适配，保留铁路与 Amadeus 兼容。`APP_TRANSPORT_FARE_PROVIDER=flyai`、`APP_TRANSPORT_ROUTE_PROVIDER=amap` 已显式启用，铁路仍独立启用。

页面首次打开为待查询，条件变化清除旧结果；路线包含可见城市选择。高德地点匹配优先完整名称，再匹配去除城市前缀的名称；无法区分多个同名地点时停止，并提示确认城市、补充具体站点或地址。GPS 输入通过官方接口转换，未提供可靠 WGS84 轨迹时省略地图线路。

## 真实应用 API 验收

以下均通过服务器应用 API 查询，HTTP 200、响应与响应头 request ID 一致，有实际来源；不是 fixture 或直接方向接口的替代验证。

| 能力 | 条件 | 结果 | 首个方案的可核实字段 |
| --- | --- | --- | --- |
| 铁路 | 上海 → 杭州，服务器当天之后两天，1 成人 | `partial`，10 条；`flyai.search-train` | 真实车次与分段；价格、人数计价与余量未知 |
| 航班 | PVG → PEK，同上日期，1 成人 | `partial`，10 条；`flyai.search-flight` | 真实机场、时间、航班与舱等；价格、人数计价与余量未知 |
| 步行 | 上海人民广场 → 外滩-陈毅广场，上海 | `partial`，1 条；`amap.direction` | 2321 米、1857 秒、10 个步骤 |
| 公交/地铁 | 同上 | `partial`，5 条；`amap.direction` | 2817 米、2360 秒、12 个步骤，单人费用 ¥3.00 |
| 出租车/驾车 | 同上 | `partial`，1 条；`amap.direction` | 10460 米、3158 秒、11 个步骤，打车估算 ¥42.00 |

市内路线耗时均为 `typical_estimate`，不代表指定时刻路况；打车费用为 `meter_estimate`，不代表最终收费。距离直接取自供应商。

初次使用“人民广场 → 外滩”时，高德返回多个同名或近似地点，三种路线均为 `no_coverage`；已加入完整名称优先匹配和明确补充地址提示。使用明确地标复测后，步行/公交成功；驾车先遇到 `rate_limited`，间隔后单独复测成功。应用没有自动重试或静默回退。

请求 ID 留证：

- 铁路：`fa837939-e4c0-4104-9826-9165d6b0181d`
- 航班：`c3157ee4-c173-4080-b80d-159f72cdd7ea`
- 步行：`686f084f-523f-40e2-b271-da1e5f8c0f5c`
- 公交：`649a9fbf-3798-4c95-b087-30544930a375`
- 驾车成功：`741a75cd-2ecb-445d-82ca-653ddb2daa19`；此前限流：`142d56f9-4649-4fa1-86ce-ba511ec8d512`

## 回归与构建

- 后端全量 Pytest：445 项通过；Ruff 通过。现有依赖产生一条 Starlette/httpx 弃用提示。
- 前端 Vitest：103 项通过；类型检查、ESLint、Vite 生产构建通过。
- 交通 Playwright：桌面和手机共 8 项通过，包含城市参数、首次待查询、铁路/航班、路线模式隔离、旧响应隔离及 375px 无横向溢出。测试拦截 API，真实供应商能力见上表。
- E2E 首次收尾挂起，确认并结束该次 Vite 后退出码 0；随后复用显式启动的测试服务器再次运行，8 项通过、退出码 0，`.last-run.json` 为 `passed`。手机截图已人工检查。
- OpenAPI 与 TypeScript 类型重新生成后哈希稳定；前端、E2E、生产静态产物及后端源码 Secretlint 通过；`git diff --check` 通过。

## 部署与回滚

生产 Python 3.14.10、Node 24.22.1；FlyAI CLI 1.0.16 bundle SHA256 为 `194a66eb84094f3d8ee20fac0a2d6cae10a405cd59ac100b7e7880ebc97297da`。未新增依赖、数据库变更或账户。

暂存：`/opt/travel-assistant/releases/transport-full-repair-20261112`。部署只复制明确列出的后端文件和前端构建；保留旧静态资源，原子替换 HTML。修改配置前保存受限权限的环境文件备份，重启后检查健康。部署脚本在健康检查失败时恢复备份；本次未触发回滚。

备份：

- `/opt/travel-assistant/backups/transport-before-full-repair-20261112`：原始受影响代码、完整前端 dist、backend.env、文件存在性 manifest。
- `/opt/travel-assistant/backups/transport-route-match-20261113`：地点匹配补丁前的 `amap.py`、`service.py`。
- 更早的页面修复备份仍保留在 `/opt/travel-assistant/backups/frontend-before-transport-ui-repair-20261112`。

完整回滚应先恢复地点补丁备份，再恢复首次代码/静态资源及 backend.env，按 manifest 删除首次部署新增的供应商文件，最后重启 `travel-assistant.service` 并验证健康。备份含凭据，仅服务器 root 可读，不进入仓库。

生产入口与本地构建内容一致，公网首页和 `/api/health` 均返回 200，新资源版本可见；最后部署的 `amap.py`、`service.py` 与本地 SHA256 一致。备份目录权限为 700，配置与配置备份权限为 600。产物哈希：

```text
dist/index.html
1fc7755372143ed37bf529e2b20fc2ac2a12bc016018892daa0e05eb549fe268
dist/assets/index-GSzUKAyq.js
028046902c64c88fcc9df82d1e35fc2e88a6644f810f41cd3706e46d887a2cc9
```

## 仍存在的字段与覆盖限制

铁路和航班的报价覆盖人数、税费、儿童价格与余量语义无法从现有字段证明，故金额和余量保持未知，不把 `adultPrice` 推算为整单价格。市内路线缺少可核实的 WGS84 geometry，返回 `partial`，不画直线。步行没有金额也不补零。页面保留这些缺失说明、来源、查询时间和平台提示。

本次验证上海地标及一组铁路/机场条件，不保证任意城市、名称、日期、权限和未来配额。高德实际发生过限流，后续查询仍可能遇到配额限制。代码已完成并部署，真实成功与字段缺口分别记录。
