# destination-workspace 任务清单

> 版本：v0.1｜状态：已完成｜批准日期：2026-10-28（北京时间）  
> 对应已批准文件：[Capability Map v0.4](../../Web-Capability-Map.md)、[SPEC-destination-workspace v0.1](../../docs/SPEC-destination-workspace.md)、[实施计划 v0.1](plan.md)。任务清单已获批准并完成实施。

## 固定执行规则

- 目的城市仅限上海、苏州、无锡、嘉兴、杭州，ID 为 foundation registry 当前五个稳定 ID；不加入自由文本、地理编码或 fallback 默认城市。
- 页面首次进入不加载子模块、不调用天气／预算／交通 API；城市选项由已批准的前端五城清单展示，不在 setup 时发 registry 请求。与 `backend/app/core/cities.py` 不一致时停止并报告，不静默增删城市。
- 只改前端和验收记录，不改 Python、OpenAPI、生成类型、后端 API、锁文件、依赖、provider 或存储。
- 先写失败测试，再实现；每个任务完成后运行该任务列出的验证，跨模块共享 `App.tsx` 依赖顺序串行处理。
- 用户切换目的地必须显式确认清理范围。取消无副作用；确认后清理新旧地点之间的预算草稿、天气／交通输入结果和进行中请求状态。导航切换本身不得清理面板状态。
- 不提交、不推送；不加入真实城市位置、API 请求、Key、精确坐标或供应商数据。

## 任务（按依赖顺序）

### DWS-01 — 锁定注册城市选项与 ID/name 映射

- [x] **验收：** 前端目的地选项恰为 foundation 五城及稳定 ID；提交工作区状态时以单个 `{ id, name }` 选项传递，不由任意文本推导 ID，不提供自动默认值。若与后端注册表不一致则测试／审查失败，不扩大范围。
- [x] **验证：** 五城 ID/name 映射和无默认值测试先失败后通过；全量 Vitest 51 项通过，typecheck 通过。
- [x] **文件：** `frontend/src/App.tsx`、`frontend/src/App.test.tsx`。
- **依赖：** 已批准 SPEC／计划；已完成 foundation registry。

### DWS-02 — 建立 setup 入口与工作区导航门

- [x] **验收：** 初始页面先展示有标签的目的城市选择和继续操作；未选时不能进入预算、天气或交通，并显示关联错误；active 后显示当前目的地和三个工具导航；初始 setup 不挂载子模块、不发任何模块请求；桌面和 375px 无水平溢出。
- [x] **验证：** Vitest、destination E2E 覆盖 setup 与五城；Playwright 桌面 Chromium／Pixel 7 均通过。
- [x] **文件：** `frontend/src/App.tsx`、`frontend/src/App.test.tsx`、`frontend/src/app.css`。
- **依赖：** DWS-01。

### DWS-03 — 将当前目的地接入天气视图

- [x] **验收：** 天气移除重复城市选择并使用 workspace `city_id`；显式日期、16 天边界及所有天气状态保留；杭州使用既有 weather endpoint 的 `hangzhou` ID。
- [x] **验证：** App 请求断言、天气回归、全量 Vitest、typecheck、lint 通过。
- [x] **文件：** `frontend/src/App.tsx`、`frontend/src/App.test.tsx`、`frontend/src/features/weather/WeatherPanel.tsx`。
- **依赖：** DWS-02。

### DWS-04 — 将当前目的地接入预算视图

- [x] **验收：** BudgetPanel 显示当前城市只读上下文；金额、费用草稿、request payload 和 API 契约不变；跨工具切换保留草稿。
- [x] **验证：** 预算 API payload 原有断言及 workspace 草稿生命周期测试通过；typecheck、lint 通过。
- [x] **文件：** `frontend/src/App.tsx`、`frontend/src/App.test.tsx`、`frontend/src/features/budget/BudgetPanel.tsx`、`frontend/src/features/budget/BudgetPanel.test.tsx`。
- **依赖：** DWS-03。

### DWS-05 — 预填交通终点并保持用户可编辑

- [x] **验收：** 当前城市名仅作为 transport 终点初值；起点为空、地点可编辑、初始无请求；fare／route 原状态及迟到保护保留。
- [x] **验证：** transport props、空起点／终点初值／编辑／无请求测试通过；typecheck、lint 通过。
- [x] **文件：** `frontend/src/App.tsx`、`frontend/src/features/transport/TransportPanel.tsx`、`frontend/src/features/transport/TransportPanel.test.tsx`。
- **依赖：** DWS-04。

### DWS-06 — 实现目的地变更确认和 workspace 生命周期

- [x] **验收：** 工具导航保留面板状态；换城确认清理旧状态，取消无副作用；慢天气响应不写入新 workspace；刷新回 setup。
- [x] **验证：** 可控 Promise、取消／确认／重置单测和浏览器刷新 E2E 通过。
- [x] **文件：** `frontend/src/App.tsx`、`frontend/src/App.test.tsx`。
- **依赖：** DWS-03 至 DWS-05。

### DWS-07 — 建立桌面／移动 E2E 与全量验收记录

- [x] **验收：** 桌面 Chromium 与 Pixel 7 E2E 覆盖 workspace 生命周期和 375px；mock/provider 边界有记录，不宣称真实天气／交通或 Web 首版完成。
- [x] **验证：** Vitest 53 passed；typecheck、lint、build、Secretlint 通过；Playwright 全量 24 passed、destination-workspace 专项 2 passed；后端 pytest 191 passed、Ruff 通过。Node scripts 由项目本地 `node_modules` CLI 运行（环境未提供 npm.cmd）。
- [x] **文件：** destination-workspace E2E、验收文档；并更新现有预算／天气／交通／smoke E2E 以遵循目的地入口。
- **依赖：** DWS-01 至 DWS-06。

## 计划边界

- **允许：** 前端 setup／workspace、五城映射、三模块 destination props、页面内状态生命周期、fake/mock-only 测试与验收文档。
- **需另行批准：** 新增城市、自由文本／地理编码、后端接口或 OpenAPI 修改、目的地持久化／账号隔离、真实 provider、Key、地图、预算写入、Git commit／push。
- **禁止：** 默认静默选上海、未确认即丢弃预算草稿、工具导航期间重置面板、把 registry 城市误称为天气覆盖，或以 fixture 宣称真实 provider 已验证。

## 审批记录

- 审阅人／日期：用户／2026-10-28
- 结论：批准 v0.1；授权实施。全部 DWS-01 至 DWS-07 验收完成，2026-10-28。
