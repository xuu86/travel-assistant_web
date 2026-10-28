# foundation 实施计划

> 版本：v0.1｜状态：已批准｜批准日期：2026-10-27  
> 对应已批准规格：[SPEC-foundation](../docs/SPEC-foundation.md)。本计划仅覆盖 Capability Map 中的 `foundation`；不代表其他模块进入计划或实现。

## 1. 目标与范围

按已批准的 `foundation` SPEC 建立后端共享基础契约与前端消费契约，为后续模块提供稳定的日期／时间、城市与坐标、来源、结果状态、错误、金额和配置边界。

本计划不接入真实供应商，不实现天气／交通／住宿／预算／行程／账号／文件解析／地图 UI，不复制 `D:\传智杯\travel-assistant` 的未验证后端代码，也不执行公网部署、真实 Key 配置或上传真实旅行文件。

## 2. 技术实施方案

- 保持已确认栈：React + TypeScript + Vite，Python + FastAPI + Pydantic，模块化单体。
- 后端为契约与校验的权威边界；前端只消费公开 API 类型，不重复定义业务事实。
- 在任务审批前先完成运行环境和依赖锁定：本机当前检测到 Python 3.12.4、`uv` 可用、Node.js 24.22.1；当前 shell 未找到 `npm` 命令。须在执行前核对官方兼容要求、确定可复现的包管理／锁文件方案，并记录能在该工作区实际运行的命令；不得现在臆造安装或测试命令。
- API 类型采用生成还是手写镜像，以及前端测试／Lint 工具，按 Q-013 在任务审批前明确；若选择会改变 SPEC 公共边界，则先修订并重新审阅 SPEC。
- 将 Q-009 的 `demo` 表达实现为显式状态和测试 fixture；本计划不新增面向生产用户的演示开关，也不允许真实查询失败后静默回退到 demo。
- 不从旧草稿继承 Q-006 中未确认的天数、人数、预算等业务约束。

## 3. 主要组件与依赖

| 顺序 | 组件 | 主要责任 | 依赖 | 交付检查点 |
|---|---|---|---|---|
| 0 | 运行与依赖基线 | 核实 Python／Node 兼容版本，确定包管理与锁文件、脚本命令；建立可复现环境 | SPEC、E-009、Q-013 | 新环境可按文档安装；锁文件一致性检查通过 |
| 1 | 公共契约与错误类型 | Pydantic 类型、状态枚举、来源、公共错误、金额与 request ID 语义 | 0 | 契约单测通过；`null` 与 0、empty 与 no_coverage 等边界明确 |
| 2 | 时间与城市注册表 | Asia/Shanghai 业务日期、UTC 时间戳、可替换时钟；五城 WGS84 注册及来源元数据 | 0、1 | UTC 跨日测试通过；城市 ID、坐标范围和来源断言通过 |
| 3 | 配置与安全集成 | 服务端配置解析／fail-closed、可选 provider 未配置状态、安全错误映射、允许来源配置和 request ID 日志边界 | 0、1 | 无密钥泄露；配置缺失与配置错误可区分 |
| 4 | 跨端契约与集成验证 | OpenAPI／前端类型一致性检查；只使用 fake provider 和合成数据进行接口级验证 | 1、2、3 | 类型检查、构建、单元／集成测试和 AC 对照证据通过 |

依赖关系：`0 → 1 → {2, 3a} → 3b → 4`。组件 2 与配置基线（3a）可在公共契约（1）冻结后并行；请求安全集成（3b）依赖配置基线；组件 4 等待两条链完成。

## 4. 实施顺序与验证门

### Gate A：工具链可复现

在任何应用源码前，记录 Python／Node 版本、包管理器、依赖锁、环境变量模板和安装／测试命令。用全新虚拟环境验证依赖安装与锁文件同步。若官方兼容范围与当前检测版本不符，先提出版本调整，不静默更改基线。

### Gate B：契约先行

先建立结果状态、来源、错误、时间戳、金额、坐标和 request ID 的类型与正反测试；状态名与错误码以已批准 SPEC 为准。fixture 必须明确区分 live、demo、empty、partial、unconfigured、no_coverage、rate_limited、unavailable、policy_unavailable。

### Gate C：时间与注册表

使用固定时钟验证 UTC／北京时间边界；注册表包含五个试点城市，坐标统一 WGS84 并保留核实来源。验证注册城市不被误解为供应商覆盖城市。

### Gate D：配置与安全边界

以假密钥和模拟异常执行配置、响应、日志及构建扫描；不使用真实凭证。确认 CORS 不使用通配符，异常和错误响应不包含秘密、堆栈、绝对路径或敏感请求内容。

### Gate E：集成验收

运行已锁定的单元、集成、类型检查、Lint 和构建命令；提交脱敏测试摘要。按 AC-01、AC-06、AC-25、AC-28、AC-36 逐项记录 foundation 所负责的证据，并明确其不代表其他模块或 Web 首版整体验收通过。

## 5. 并行与顺序约束

- **必须顺序：** 运行／锁文件基线 → 公共契约 → 依赖该契约的时间、城市、配置组件 → 跨端集成与验收。
- **可并行：** 契约冻结后，时间／城市测试与配置安全测试可分开实现；集成门必须等各自结果汇合。
- **不并行扩展：** 不同时启动其他 capability 的 SPEC/实现；依赖 foundation 的模块须各自过 SPEC 门禁。
- **文件冲突控制：** 任务阶段将切成单次专注任务，每项列出文件范围；同一公共契约文件只由一个任务修改，避免跨任务并发改接口。

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 当前 shell 无 `npm` 命令，Node 版本尚未兼容性实测 | 前端无法可靠安装／测试 | Gate A 先核对受支持版本和可复现安装方式；未打通前不开始功能实现 |
| Python／前端依赖尚无 lockfile | 安装不可复现，验证证据无效 | 任务阶段先固定版本及锁文件，使用干净环境验证 |
| Q-009 演示数据策略仍有生产 UI 未决点 | demo 可能被误当真实数据 | 本模块仅定义状态与测试 fixture；不加生产切换入口，不静默回退；后续 UI/provider SPEC 单独决定 |
| 旧后端草稿包含未确认业务限制 | 无意将草稿变成产品规则 | 新工作区按 SPEC 从最小基础结构创建，不复制旧草稿；对 Q-006 逐条保持范围外 |
| 城市坐标来源／核实记录不足 | 错误中心点影响附近城市计算 | 只在来源可核实时标记 verified；未知状态不得隐藏或用猜测填补 |
| CORS 被误当作访问授权 | 局域网暴露边界不完整 | 配置只允许明确来源；会话、owner scope 和配对授权留给 auth/imports SPEC，不由 CORS 替代 |

## 7. 验证策略与完成定义

`foundation` 可提议验收为完成，须同时满足：

1. 清洁环境可按锁文件安装，所有实际验证命令已记录版本与结果。
2. 公共类型校验覆盖未知／零、无时区时间、坐标边界和每一种结果状态。
3. 固定时钟测试证明 UTC 日界转换严格遵从 Asia/Shanghai，且不依赖宿主时区。
4. 五个试点城市稳定注册，坐标 WGS84、有来源与核实状态；城市登记不声称数据覆盖。
5. 可选 provider 缺失、配置结构错误、额度／政策／服务失败语义可区分；无自动付费或 demo 静默回退。
6. API 响应、前端产物、日志、异常与测试报告中均无服务端密钥和敏感 payload。
7. 单元、集成、类型检查、Lint、构建均通过；脱敏证据映射到 AC-01、06、25、28、36。
8. 未执行真实供应商、OCR、模型、地图、局域网手机上传或完整 Web 流程时，明确标记未验证，不宣称相关 AC／Web 首版已完成。

## 8. 本阶段不创建的文件

遵循阶段门禁，本轮只建立 `tasks/plan.md`。`tasks/todo.md`、应用源码、依赖清单／锁文件及测试代码须待本计划获批后，在 Tasks 阶段建立；未经任务清单批准不实施。

## 9. 审批记录

- 审阅人／日期：用户／2026-10-27
- 结论：批准
- 修改摘要：按 v0.1 计划批准；任务清单阶段再细化可复现工具链与逐项验证命令。


# budget 实施计划

> 版本：v0.1｜状态：已批准并完成｜批准日期：2026-10-27（北京时间）  
> 对应已批准规格：[SPEC-budget](../docs/SPEC-budget.md)。本计划仅覆盖 `budget`，不代表任务清单或实现已获批准；foundation 既有计划与记录保持不变。

## 1. 目标与范围

实现整趟单城市旅行预算的严格契约、纯计算服务、API、响应式编辑与摘要界面，以及预算范围自动化验收。支持整数分、已支付／待支付分离、预留金、未知金额和费用完整性；重复费用拒绝，用户填写的未报价住宿／机票金额显式标记。

本模块不持久化预算或费用、不读取身份、不接入供应商，不实现导入去重、预订锁定／解锁、支付、退款、云端同步或跨刷新恢复。锁定写入保护由 `itinerary` 负责；持久化边界由 `local-storage`／`auth` 后续规格定义。fixture 仅证明流程与计算，不代表真实报价。

## 2. 技术方案与需冻结规则

- 后端沿用 foundation 已锁定的 CPython 3.14.10、uv、FastAPI、Pydantic strict contract、pytest 和 Ruff；前端沿用 Node.js 24.22.1、npm、React 19、TypeScript、Vite、Vitest、Playwright 与 ESLint。无需新增依赖。
- 计算集中于无副作用的 budget service；Pydantic 请求／响应契约负责字段、空值和重复 ID 校验；router 只负责 HTTP 映射。新增路由后更新 FastAPI OpenAPI，再生成 `frontend/src/shared/api-contracts.ts`。
- 前端金额输入采用十进制字符串转分：最多两位小数，超过两位即提示并拒绝，不进行隐式舍入；展示使用 `Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY" })`，账值始终以整数分为准。此转换规则由本计划提出，需随计划审批。
- completeness 由调用方明确提供并经服务端校验；空费用数组不推断所有类别均已核实。预算内结论必须要求预算、费用覆盖、已支付和待支付金额均可确定；有未知项时保留 `needs_review`。具体可判定条件通过契约测试冻结，不把未知转成 0。
- 输入快照无服务端持久化；预算面板状态仅在当前页面会话内保留，刷新后不承诺恢复。页面不得显示已保存或跨刷新保留的暗示。
- 本期类别采用 SPEC 列出的固定枚举（往返交通、住宿、餐饮、市内交通、门票、活动、其他）；类别仅用于归类，不代表报价事实。

## 3. 组件与依赖

| 顺序 | 组件 | 主要责任 | 依赖 | 检查点 |
|---|---|---|---|---|
| 0 | 契约与边界冻结 | 明确 completeness 判定、金额范围安全策略、费用／预订唯一映射错误，以及输入/响应 schema | 已批准 SPEC、foundation | 决策表与正反契约测试案例可直接映射 |
| 1 | 后端预算契约与计算 | 严格校验、聚合、剩余可安排、预计结余、最低已知超支、预留提醒和预算状态 | 0、foundation MoneyAmount/EvidenceState/PublicError | 纯函数单测覆盖关键公式、null/0 和状态组合 |
| 2 | 后端 API | 注册预算计算端点、公共错误与 request ID；日志不记录费用 payload | 1、foundation API/error handling | 集成测试覆盖合法请求、非法请求、错误脱敏和日志 |
| 3 | 前端金额工具与预算界面 | 十进制字符串转换、费用编辑、预算摘要、缺价标注、预留提示、待核实/超支状态 | 1 的冻结契约、Foundation UI、OpenAPI | 单测覆盖转换与交互；键盘和 375px/桌面布局可用 |
| 4 | 契约同步与端到端验收 | OpenAPI 导出／类型生成、前后端回归、Secretlint、AC 留证 | 2、3 | 全套命令通过，AC-08 至 AC-11 结果分别记录 |

依赖顺序：`0 → 1 → 2 → 3 → 4`；组件 3 的静态 UI 与后端实现可在 API schema 冻结后并行，但集成测试必须等契约类型生成完成。

## 4. 实施阶段与验证门

### Gate A：业务计算契约

冻结费用类别、金额解析、完整度与状态真值表；验证负数、布尔值、浮点、重复 `cost_id`、同一 reservation 多主项均拒绝。`null` 与 0 分别贯穿请求、计算和输出。

### Gate B：纯计算与 API

用合成快照实现已支付、待支付和预留金计算；确保 `remaining_to_allocate = total_budget - paid_total`，`expected_balance = total_budget - paid - known_unpaid - reserve`，不重复加总订单原价。未知项存在时不得输出确定预算内结论；可证明的超支显示最低已知超出额。API 集成测试验证 request ID 一致、错误稳定、日志不含金额或订单关联值。

### Gate C：前端交互

实现总预算、预留金和费用编辑；明确显示 CNY、待核实、来源证据和“用户填写，非平台报价”；已支付与剩余可安排、预计结余分别呈现。预留提醒在 300,000 分阈值边界测试，不自动写入 reserve。提供空状态、校验错误和超支／不完整状态，不因状态颜色单独传达信息。

### Gate D：契约、回归与验收

更新 OpenAPI 并稳定生成 TS API 类型；运行预算后端单元／集成、前端单元／E2E、lint、typecheck、build 和密钥扫描。E2E 覆盖用户补填报价标签、未知金额、阈值提醒、至少超支及 375px 无横向溢出。按 AC-08、AC-09、AC-10、AC-11 分别保存脱敏证据；AC-13、AC-12、AC-22 只记录边界归属，不将其计为 budget 完成。

## 5. 候选文件范围

以下是任务阶段预计的跟踪文件范围；新增／修改清单须在 `tasks/todo.md` 再逐任务冻结。不得覆盖其他模块或既有基础契约的无关内容。

```text
backend/app/modules/budget/__init__.py
backend/app/modules/budget/contracts.py
backend/app/modules/budget/service.py
backend/app/modules/budget/router.py
backend/app/main.py
backend/tests/unit/test_budget_contracts.py
backend/tests/unit/test_budget_service.py
backend/tests/integration/test_budget_api.py
frontend/src/shared/openapi.json
frontend/src/shared/api-contracts.ts
frontend/src/features/budget/api.ts
frontend/src/features/budget/money.ts
frontend/src/features/budget/BudgetPanel.tsx
frontend/src/features/budget/budget-panel.css
frontend/src/features/budget/BudgetPanel.test.tsx
frontend/src/App.tsx
frontend/e2e/budget.spec.ts
docs/acceptance/budget.md
```

不新增依赖或修改 lockfile；如实现发现确有依赖缺口，停止该任务并先说明理由、影响和替代方案，需另行批准。

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 未知金额与完整度组合复杂 | 可能错误显示预算内 | 先冻结状态真值表；金额边界和组合状态均以测试锁定 |
| 元输入转换发生精度损失 | 产生分级差异 | 只用十进制字符串解析；超两位小数拒绝；边界／超大整数测试 |
| 用户填写报价被误读为平台报价 | 事实误导 | 表单、摘要、API evidence_state 同步保留 `user_provided` 与固定文案 |
| 汇总重复预订费用 | 双重计算 | 重复 cost ID 和 reservation 主项冲突均校验失败；部分支付在同一 cost item 表达 |
| 刷新后数据丢失 | 用户误以为已保存 | 不呈现持久化承诺；显式说明页面会话内计算，持久化交给后续模块 |
| 上限未决（Q-006） | 臆造产品限制 | 不增加业务金额／数量上限；另评估并测试运行时安全资源限制 |
| foundation API／App 入口已有文件 | 可能引入回归或改坏已有功能 | 仅小范围注册 router／入口；跑完整已有回归与 E2E，不改 foundation/weather 行为 |

## 7. 完成定义

1. 预算 schema 严格区分未知与零，拒绝非法金额、重复 ID 和重复预订主项。
2. 所有聚合公式、状态、完整度、阈值提醒和已知超支下界有正反单元测试。
3. API 使用统一公共错误与 request ID；测试证明日志不含金额、订单关联 ID 或请求 body。
4. UI 明确区分已支付、待支付估算、剩余可安排、预计结余和预留金；报价来源不失真；键盘、375px 与桌面 E2E 通过。
5. OpenAPI 与生成 TS 类型一致且可重复生成；后端 pytest/Ruff、前端 lint/unit/typecheck/build/E2E 与源码/构建产物密钥扫描通过。
6. `docs/acceptance/budget.md` 分别报告 AC-08 至 AC-11；任何真实住宿／机票供应商报价、持久化、锁定预订、导入去重未被本轮实现或冒称完成。

## 8. 本计划不授权事项

本计划获批仅允许建立 budget 任务清单；不等于批准任务清单或开始实现。`tasks/todo.md` 需按每个任务列明文件、验收和可执行命令，再单独审批。此阶段不初始化 GitHub remote、不提交／推送，不处理其他模块。

## 9. 审批记录

- 审阅人／日期：用户／2026-10-27
- 结论：批准并明确授权代码编写
- 修改摘要：按 v0.1 预算计划实施；十进制金额最多两位小数，超出即拒绝。

