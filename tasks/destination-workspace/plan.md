# destination-workspace 实施计划

> 版本：v0.1｜状态：已批准｜批准日期：2026-10-28（北京时间）  
> 对应已批准规格：[SPEC-destination-workspace](../../docs/SPEC-destination-workspace.md) v0.1。计划只覆盖目的地优先的前端工作区；获批后仍须建立独立任务清单，本计划不授权开始编码。

## 1. 目标与范围

在应用入口建立单一已注册目的地上下文。用户先选择上海、苏州、无锡、嘉兴或杭州并确认，之后可在天气、预算和交通工具间切换；各面板消费一致的 destination，保留既有领域规则和 API schema。

实现仅改前端与验收文档：

- setup 初始态、注册城市选择、确认和 active workspace 导航；
- 当前目的地上下文在工具切换期间维持，并显示于各视图；
- weather 使用 registry `city_id`，不再显示重复的城市选择；
- transport 将已选城市名作为终点初值，起点仍为空；
- budget 显示所选目的地但不修改金额计算、费用或 API payload；
- 显式更换城市的确认／取消流程和完整工作区重置。

本计划不改 Python、OpenAPI、provider、天气／预算／交通领域规则，不新增依赖，不添加持久化、账号、城市搜索、地理编码、Git 操作或真实外部请求。

## 2. 前置决策与技术基线

- `destination-workspace` 已列入批准的 Capability Map v0.4；SPEC v0.1 已批准。
- 目的城市集合唯一来源对应 foundation 城市注册表，不复制可被独立修改的城市列表；入口可从现有生成 API 类型或安全的本地适配层取得五城 ID/name。
- React 工作区 state 由 `App.tsx` 持有；当前 active 面板在同一 App 生命周期内保持挂载或由等价方式保留 state，切换 destination 时通过受控 reset key/remount 清除模块内旧状态。
- `WeatherPanel` 与天气查询表单共享上层选中的 city ID；weather API body 保持 `{ city_id, start_date, end_date }`。
- `BudgetPanel` 增加只读 destination display prop；`calculateBudget` payload 及费用草稿结构不变。
- `TransportPanel` 接收目的城市名作为 `initialDestination`；普通面板交互仍能调整终点；初次 mount 不发请求。
- 不新增组件库、路由器、状态管理或对话框依赖；城市变更确认优先使用项目可访问的原生 dialog/确认语义，具体实现由任务测试先行固定。

## 3. 组件与实施顺序

| 顺序 | 组件 | 主要责任 | 依赖 | 检查点 |
|---:|---|---|---|---|
| 0 | registry 映射适配 | 确认当前 frontend API contracts 暴露五城记录，建立单一映射；严格测试五个 ID 和显示名，不允许 fallback | foundation OpenAPI/types | registry 变更时测试能明确失败；不生成第二份漂移数据 |
| 1 | App setup/workspace 状态 | 初始无 destination；城市选择、必填错误、确认后开放工具；header 显示目的城市 | 0 | 初始不挂载工具／不发 API；五城确认均创建有效 workspace |
| 2 | 跨工具上下文集成 | weather 移除重复城市选择并使用当前 ID；budget 展示城市而不改请求；transport 预填终点 | 1 | 各面板集成测试验证对应 props／payload 和初始无请求 |
| 3 | 视图保留与目的地切换 | 工具切换保持各自页面状态；change flow 有确认和取消；确认后清理预算草稿、天气／交通结果及迟到响应 | 1、2 | 可控交互测试证明取消零副作用、确认完整 reset |
| 4 | 响应式 E2E 与全回归 | setup→workspace→三模块→destination change→reload 流程；桌面／Pixel 7、375px、网络副作用和回归验证 | 0–3 | 所有旧模块测试通过、E2E 无横向溢出、刷新回 setup |
| 5 | 验收留证 | 记录 destination workflow 证据和真实 provider 边界；不宣称 weather/transport 真实能力完成 | 4 | AC 子项流程与全局缺口分开写明 |

依赖图：`0 → 1 → 2 → 3 → 4 → 5`。App shell、模块 prop 变更及 reset 策略串行推进，避免并发修改共享 `App.tsx` 和模块生命周期。

## 4. 实施门与验证策略

### Gate A：注册表映射

检查生成 `api-contracts.ts` 的 CityRecord schema 与 `GET /api/foundation/cities` 响应；用当前 API 数据验证五个稳定 ID 和名称。此为开发／测试阶段核验，不在 setup 页面运行时请求城市 API；初始页面仍无网络请求。前端选项只允许与当前 foundation registry 一致的五项，不允许 fallback；若 registry 不一致，暂停并修正规格／计划，不静默扩大城市范围。

### Gate B：目的地入口

先为初始 setup 和城市确认写失败测试。未选择城市点击继续时显示关联错误，不 mount budget/weather/transport、不调用 `fetch`；对五个选项逐个确认并断言一致的 ID/name，导航只在 active 后出现。

### Gate C：模块上下文

- Weather：选择杭州时，只将 `hangzhou` 放入原 weather endpoint 请求；日期和最多 16 天校验不变。城市不再有第二个面板下拉。
- Budget：目的城市标题随工作区变化；所有输入、类别、金额和 API payload 与现有契约一致；工具切换返回后草稿仍在。
- Transport：目的城市作为终点字段初值，起点仍空；地点字段后续编辑不受禁用；只在用户主动点查询时请求。
- 所有模块不因仅切换导航而请求 API。

### Gate D：切换 destination 与并发保护

确认交互列出会清除的页面内草稿／结果；取消后 destination、面板输入、结果和正在进行的当前工作区请求均保持原样。确认后改变 `workspaceKey` 或等价地全量重建工作区，旧 weather／transport promise 不可更新新 workspace；budget 草稿清空。查询 request body、日志与 URL 不新增 destination 明文字段。

### Gate E：E2E、回归与交付

Playwright 仅使用现有本机 API mock；覆盖五城入口样例、weather ID 映射、预算原 payload、交通默认终点、导航状态保留、切换城市取消／确认、刷新重置与 375px 无水平滚动。执行既有 frontend Vitest、typecheck、ESLint、Vite build、全量 Playwright 和 Secretlint。未变更后端或 schema 时不重导 OpenAPI。

## 5. 预期文件范围

任务清单再拆成每项不超过约五个文件的工作包。候选文件：

```text
frontend/src/App.tsx
frontend/src/App.test.tsx
frontend/src/app.css
frontend/src/features/weather/WeatherPanel.tsx
frontend/src/features/weather/WeatherPanel.test.tsx
frontend/src/features/budget/BudgetPanel.tsx
frontend/src/features/budget/BudgetPanel.test.tsx
frontend/src/features/transport/TransportPanel.tsx
frontend/src/features/transport/TransportPanel.test.tsx
frontend/e2e/destination-workspace.spec.ts
docs/acceptance/destination-workspace.md
```

实际任务可因测试先行重排文件，但不得改动 `backend/`、OpenAPI 生成产物、锁文件或 provider 配置。若发现 foundation 的城市 API 缺少可用于 UI 的 registry 信息，先暂停并说明 SPEC 假设与现状差异，不在本计划中新增后端 endpoint。

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| App 目前硬编码城市，而 foundation 已有 registry | UI 与服务端城市 ID/name 可能漂移 | Gate A 检查 schema/API；优先单一 registry 数据源；不一致时停止，不默默扩展契约 |
| 视图条件渲染会卸载面板 | 预算草稿和查询日期切换视图后丢失 | 状态保留测试；active panels 持续挂载或由明确的 workspace-local state 托管 |
| destination 切换后迟到请求返回 | 旧城市天气／路线覆盖新工作区 | workspace generation token/remount guard；确认切换与慢响应并发测试 |
| 用户不理解城市切换会清空内容 | 非预期丢失预算草稿／查询输入 | 在确认步骤清楚列明清理项；取消保持原状；不在目的地选择控件 change 时立即清空 |
| 天气注册城市与供应商覆盖被混淆 | 误认为已能查询任意城市或必有数据 | 只发送注册 ID；天气原有 unconfigured／coverage 状态保留；无 provider fallback |
| transport 终点预填被误解为已定位／已查询 | 形成错误地理／路线事实 | 继续显示既有地点核实提示；预填不触发 API；用户仍可编辑 |

## 7. 完成定义

1. 用户只能从 foundation 注册五城中选择目的地；没有默认值，确认前模块入口不可用且无模块请求。
2. budget/weather/transport 均显示同一个 destination；weather 使用正确 registry ID，budget 后端 payload 不变，transport 终点预填且起点为空。
3. 导航切换保留各面板页面内状态；取消城市切换无副作用，确认后完整清除旧 workspace，迟到响应无法污染新城市。
4. 刷新后回到 setup，目的地和草稿均不恢复。
5. 前端单测、typecheck、lint、build、全量 E2E 和 Secretlint 通过；桌面和 375px 不水平溢出；无新增依赖／API。
6. 验收记录严格区分 workspace 流程证据与真实天气／交通 provider 能力；不宣称 Web 首版整体完成。

## 8. 本计划不授权事项

计划批准仅允许建立 `tasks/destination-workspace/todo.md`。任务清单须另行批准后才可编码。本计划不授权新增城市、地理编码、API／schema／持久化、供应商或 Key、依赖安装、Git commit／push。

## 9. 审批记录

- SPEC 审阅人／日期：用户／2026-10-28
- SPEC 结论：批准 v0.1
- 计划审阅人／日期：用户／2026-10-28
- 结论：批准 v0.1；允许建立 destination-workspace 专属任务清单，不授权开始代码实现。
- 事实修订：将 registry endpoint 更正为 `/api/foundation/cities`；不改变计划范围。
