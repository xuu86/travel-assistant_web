# SPEC-destination-workspace：目的地优先工作区

> 版本：v0.1｜状态：已批准｜批准日期：2026-10-28（北京时间）  
> 对应已批准 Capability Map v0.4 中新增的 `destination-workspace`。能力图批准不代表本 SPEC、实施计划、任务清单或代码获批。

## 0. 已确认假设与边界

1. 目的城市只允许 foundation 已注册的五城：上海、苏州、无锡、嘉兴、杭州；不接受注册表以外的自由文本。
2. 用户进入应用后必须先选择目的城市并确认，随后才开放预算、天气和交通工具。
3. 当前 destination 只在页面内存中存在；不写 URL、后端、日志、浏览器持久化或账号数据。刷新后重新选择。
4. destination-workspace 只负责目的地上下文和视图编排。天气、预算、交通的领域契约、业务规则和 API 仍由各自模块拥有。
5. 本次只改变前端工作流和模块输入上下文；不新增 API、数据库、依赖、供应商请求或共享持久化能力。

## 1. 元数据

- **模块 ID：** `destination-workspace`
- **关联能力图：** [Web Capability Map v0.4](../Web-Capability-Map.md)
- **依赖模块：** `foundation`、`budget`、`weather`、`transport`
- **消费者：** 用户及预算、天气、交通视图
- **关联验收：** 用户可先建立唯一五城目的地上下文，再使用预算、天气和交通；错误城市／旧城市结果不得混入当前上下文。

## 2. Objective 与范围

### 目标

建立一个目的地优先的旅行工作区。用户先从五个已注册城市中选择目的地；确认后可在预算、天气和交通工具之间切换，且各工具显示并使用同一个当前目的地。

### 首版包含

- 初始页面提供有可见标签的目的城市选择控件和明确的继续操作。
- 未选择目的城市时不显示可进入预算、天气或交通的导航，也不发出这些模块的 API 请求。
- 确认目的地后显示工作区和预算／天气／交通导航；切换视图时当前目的地保持可见且不变。
- 天气不再提供独立城市选择器；查询请求使用当前目的地对应的既有 registry `city_id`。天气日期区间和现有覆盖规则保持不变。
- 预算显示当前目的地上下文；费用类别、金额、计算公式、API payload 和来源语义保持不变。目的城市不作为费用或报价事实。
- 交通面板以当前目的城市预填终点；起点、目标日期、人数、交通方式和可选出发时间仍由用户明确输入。用户可在交通面板内按原有交互调整查询终点。
- 在同一工作区的模块视图切换时保留各面板的当前页面内状态；不因浏览天气或交通而丢失预算草稿。
- 用户主动更改目的城市时，提示本页预算草稿和天气／交通结果都会清除；确认切换后重置该工作区的模块状态，防止旧目的地数据被误认为新城市数据。
- 响应式、键盘可达、可见 label、focus 状态和 screen-reader 语义沿用现有前端约定。

### 首版不包含

- 任意地点文本、城市搜索／地理编码、附近城市、跨城市行程或自动选择最近注册城市。
- 依据目的城市自动填预算金额、费用、出发点、票价或交通结论。
- 强制预算必须填写后才能查天气／交通；目的地确认是唯一的工作区入口门槛。
- 自动把目的城市写入 weather/transport/budget 后端契约或请求日志；仅 weather 使用已有 registry ID，transport 按现有用户输入地点契约发送终点。
- IndexedDB、刷新恢复、游客／账号隔离、服务器端行程或 destination 持久化。
- 修改现有天气、预算、交通领域规则，连接真实 provider，添加 Key、SDK 或依赖。

## 3. 输入、状态与模块映射

### 工作区状态

| 字段 | 类型 | 必填 | 语义 |
|---|---|---:|---|
| `destination_city_id` | foundation 已注册城市 ID | 确认工作区后是 | 只允许上海、苏州、无锡、嘉兴、杭州之一；不接受客户端自由 ID |
| `destination_name` | 对应注册城市展示名 | 确认工作区后是 | 从本地注册城市选项解析，不信任未映射的用户文本 |
| `workspace_status` | `setup` / `active` / `changing_destination` | 是 | `setup` 不展示模块入口；`active` 开放工具；`changing_destination` 表示待用户确认清空当前内存状态 |

目的地切换是显式用户操作。打开切换流程时保留当前工作区，展示将清除本页预算草稿和查询结果的说明；用户确认后才应用新 `destination_city_id` 并重置面板。取消切换不改写任何现有面板状态。

### 与现有模块的边界映射

- **weather：** 使用 `destination_city_id` 作为既有 `WeatherQuery.city_id`；目标日期仍由用户输入。切换目的城市时使天气请求 token 失效并清除旧结果；不对其他城市发送请求。
- **budget：** 接收 `destination_name` 仅用于 UI 上下文标题／说明，不扩展 `BudgetRequest`，不影响纯计算 API。预算内容在工具间切换时保留；确认切换目的城市后按明确提示清空。
- **transport：** `TransportPanel` 接收 `destination_name` 作为初始终点显示值。起点仍为空并由用户输入；所有既有显式日期、逐方式隔离、unknown/null、来源和迟到响应规则保持有效。切换目的城市时清除旧面板状态。
- **不匹配／配置：** UI 目的地名称和 `city_id` 必须来自同一个已注册选项。无法映射时继续操作不可用；不得静默回退到上海或上次选中城市。

### 页面内状态生命周期

- 初始值为空；不从系统日期、浏览器存储、默认城市或 URL 推导目的地。
- 当前工作区选择在 SPA 视图切换期间只存在于 React 内存。
- 刷新／关闭页面会回到 `setup`，不承诺恢复预算草稿或查询状态。
- 切换目的地仅在用户确认后清理状态；未确认或取消时旧工作区保持完整。

## 4. 交互与公共状态

| 场景 | 预期行为 |
|---|---|
| 初始打开 | 展示目的城市选择；预算／天气／交通视图不可进入；无 API 请求 |
| 未选择直接继续 | 不进入工作区；在控件附近显示可访问的必填错误 |
| 选择五城之一并确认 | 创建 active 工作区；城市名在工作区头部显示；三个工具可导航 |
| 打开天气 | 使用当前 city ID；保持明确日期、16 天范围、加载／未配置／失败／结果状态 |
| 打开预算 | 显示当前目的城市；仍由用户设置金额与费用；不调用任何新的目的地 API |
| 打开交通 | 终点预填当前目的城市；起点未预填；默认不发交通请求 |
| 模块间切换 | 当前城市和已输入的面板状态保留，不产生新 API 请求 |
| 请求中或有结果时改目的地 | 先展示清除影响并要求确认；取消保留状态，确认后清空旧结果并使迟到响应失效 |
| 页面刷新 | 回到初始选择；不显示旧目的地或上一页数据 |

提示文案不得暗示目的城市已经 geocode、天气已覆盖、路线已核实、交通已查询或预算已保存。

## 5. 权限、隐私与数据保留

- 用户选择的城市只属于页面当前内存状态，不写 URL、console、analytics、服务器日志或浏览器持久化。
- 天气查询只发送当前已注册 `city_id` 和用户显式选择日期；沿用 weather 现有脱敏和 provider gate。
- 预算金额、费用和交通起终点沿用各自模块的既有隐私规则；目的地工作区不收集或集中记录这些 payload。
- 不加入账号、owner scope、服务端存储、Key、地图／地理编码服务或跨设备同步。

## 6. 命令、结构与代码约定

### 技术栈

沿用现有 React、TypeScript、Vite、Vitest、Testing Library、Playwright，不新增运行时或开发依赖，不修改 Python API schema。

### 预期项目结构

```text
frontend/src/App.tsx                         # 工作区状态、城市确认和视图编排
frontend/src/App.test.tsx                    # 入口门槛、映射、切换和状态生命周期
frontend/src/features/budget/BudgetPanel.tsx # 接收并展示当前城市上下文
frontend/src/features/transport/TransportPanel.tsx # 以城市上下文预填终点
frontend/src/features/weather/*              # 复用当前 city_id，不新增 provider 行为
frontend/e2e/destination-workspace.spec.ts    # 桌面／375px 跨模块工作流
docs/acceptance/destination-workspace.md     # 通过范围与边界留证
```

### 代码风格示例

```tsx
type Destination = { id: WeatherQuery["city_id"]; name: string };

function confirmDestination(destination: Destination | undefined) {
  if (!destination) {
    setDestinationError("请选择目的城市。");
    return;
  }
  setWorkspace({ status: "active", destination });
}
```

城市展示名与 ID 必须作为同一个注册选项传递；不要通过自由文本推导 ID，不要为状态展示添加副作用请求。

### 验证命令

在 `frontend/` 使用项目锁定 Node 运行时：

```powershell
npm.cmd run test:unit -- --run
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e -- --grep destination-workspace
```

若仅修改前端且没有契约／后端变更，不重导 OpenAPI；最终回归仍按实施计划和任务清单执行。

## 7. 测试策略

- **组件／集成测试：** 初始 setup 不调用 API；缺少城市不能继续；五个注册城市均可选且 city ID/name 映射正确；不接受 registry 外值。
- **Weather 测试：** active destination 的 ID 被提交；修改城市会清除旧结果并忽略旧请求迟到响应；日期边界原有测试继续通过。
- **Budget 测试：** 显示当前目的地；金额计算 payload 与现有契约完全一致；跨视图切换不清空草稿；确认更换目的地后草稿清空。
- **Transport 测试：** 终点预填选中城市、起点为空；编辑终点按原行为工作；切换目的地后旧路线／报价不保留。
- **E2E：** 桌面 Chromium 和 Pixel 7 覆盖 setup → 确认城市 → budget/weather/transport 切换 → 变更确认／取消 → 刷新回到 setup；断言 API 只由明确查询操作触发，375px 无水平溢出。
- **回归：** 保留全部 weather、budget、transport 单元和 E2E 测试；不以 mock 结果宣称真实 provider 能力。

## 8. 边界规则

- **Always：** 先确认注册城市后开放工具；ID/name 成对映射；改变目的地需明确确认并清理旧上下文；组件有可见 label、键盘操作和可读状态；沿用既有领域模块契约。
- **Ask first：** 增加城市、改变五城注册表、持久化目的地、跨刷新恢复、后端／OpenAPI 修改、引入地理编码或其他供应商依赖。
- **Never：** 用默认城市绕过选择；把目的地文本当已解析坐标；用户未查询时发 provider 请求；改城市后保留或重新标记旧结果；从目的地自动编造预算或交通事实；提交／推送未经确认的仓库变更。

## 9. Success Criteria

1. 全新会话只能先选择五个已注册城市之一；未确认前，budget/weather/transport 无法打开且无相关网络请求。
2. 确认后，城市上下文在三个视图中一致；weather 请求使用对应 `city_id`，budget API schema 不变，transport 终点默认采用所选城市。
3. 模块间切换保留当前面板状态；显式更改城市前说明清理范围，取消无副作用，确认后清除旧预算草稿和天气／交通结果并忽略迟到响应。
4. 刷新后回到城市选择，不恢复任何目的地／预算／查询数据。
5. 前端单测、类型检查、Lint、build、桌面与 375px E2E 通过；不新增依赖、不改后端契约。
6. 验收记录只声称工作区流程完成，不将 fake／fixture 写成真实天气或交通能力完成。

## 10. Open Questions

- 无产品口径待确认。具体切换目的地确认交互和 React 状态组织在实施计划阶段展开，不改变本 SPEC 的成功条件或边界。

## 审批记录

- 能力图：用户于 2026-10-28 批准新增 `destination-workspace`；目的地仅限 foundation 注册的五城。
- SPEC v0.1：用户于 2026-10-28 批准；允许进入实施计划阶段，不代表计划、任务清单或代码获批。
