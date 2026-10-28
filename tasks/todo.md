# foundation 任务清单

> 版本：v0.1｜状态：实施中｜用户批准：2026-10-27  
> 对应已批准内容：[Capability Map](../Web-Capability-Map.md)、[SPEC-foundation](../docs/SPEC-foundation.md)、[foundation 实施计划](plan.md)。此清单只覆盖 `foundation`；本轮按已批准任务逐项执行，未完成项仍不提前实施。

## 工具链提案（批准本清单即确认此基线）

- 后端使用 **CPython 3.14.10 + uv**；项目精确运行版本固定在 `.python-version`，依赖范围和完整解析结果分别由 `pyproject.toml`、`uv.lock` 管理。主机当前为 Python 3.12.4、uv 0.12.13；Python 3.14.10 可通过官方 Windows x64 安装器用户级安装，不覆盖既有 Python。
- 前端使用 **Node.js 24.22.1 LTS + npm 11.19.1**，版本记入 `.node-version`，依赖由 `package-lock.json` 锁定。当前 shell 只有 Codex 隔离运行时的 Node 24.22.1，`npm` 不在 PATH；任务将使用官方 Windows x64 ZIP 并在 `%LOCALAPPDATA%` 用户目录保存，不安装系统级 MSI、不改全局 PATH；校验官方 SHASUM 后再使用。
- 工具：后端 `pytest` + `ruff`；前端 `Vitest` + React Testing Library、ESLint + TypeScript ESLint、Playwright E2E、Secretlint + recommended rules preset；用 `openapi-typescript` 从 FastAPI OpenAPI 生成前端 API 类型。所有包的确切版本经兼容性验证后写入锁文件，不使用浮动依赖安装作为验证结果。
- 兼容依据（2026-10-27 查阅）：[Python 3.14.10 官方 Windows 安装器与校验信息](https://www.python.org/downloads/release/python-31410/)、[Node 24.22.1 LTS 官方 x64 ZIP 与 npm 版本／SHASUM](https://nodejs.org/download/release/v24.22.1/)、[Vite Node 版本要求](https://vite.dev/guide/)、[FastAPI Python 3.14 包元数据](https://github.com/fastapi/fastapi/blob/master/pyproject.toml)、[Pydantic 2.14 发布说明](https://pydantic.dev/articles/pydantic-v2-14-release)、[Secretlint 安装与 CLI](https://github.com/secretlint/secretlint)。若工具链安装、依赖解析或平台兼容测试失败，先停在该任务记录事实，不静默降级 Python／Node 主版本或改用未审阅工具。

## 任务（按依赖顺序）

### FND-00 — 准备用户级 Python／Node 工具链

- [x] **验收：** Python 3.14.10 与 Node 24.22.1/npm 11.19.1 可在项目命令中准确调用；Python 安装到 `%LOCALAPPDATA%` 独立目录，Node ZIP 解压到 `%LOCALAPPDATA%` 项目工具目录；已有 Python 3.12.4 和 Codex Node 不被覆盖；安装包／归档 SHA-256 与官方校验值一致；不修改系统级 PATH 或防火墙。若需要管理员权限，暂停并报告。
- **验证：** 在 PowerShell 临时调用独立运行时，不改全局 PATH：

```powershell
$python = Join-Path $env:LOCALAPPDATA 'AIWebChallenge\runtime\python-3.14.10\python.exe'
& $python --version  # Python 3.14.10
$node = Join-Path $env:LOCALAPPDATA 'AIWebChallenge\runtime\node-v24.22.1-win-x64'
$env:Path = "$node;$env:Path"
node --version       # v24.22.1
npm --version        # 11.19.1
```

- **文件：** 无项目跟踪文件；只涉及用户级工具目录（Python 安装器、Node ZIP）。
- **依赖：** 无。
### FND-01 — 固定 Python 后端环境与锁文件

- [x] **验收：** 建立可复现的后端包清单；项目解释器固定为 3.14.10；FastAPI、Pydantic、pytest、httpx、ruff 等依赖有兼容范围且全部解析锁定；空白环境能按锁同步。
- **验证：** 在 `backend/` 当前 PowerShell 会话设置 `$env:UV_PYTHON="$env:LOCALAPPDATA\AIWebChallenge\runtime\python-3.14.10\python.exe"`，执行 `uv sync --locked`、`uv run python --version`、`uv run pytest --version`、`uv run ruff --version`；Python 为 3.14.10，依赖可安装且重复 `uv lock --check` 不改锁文件；以 `uv tree --locked` 和项目依赖导入 smoke test 验证依赖图，不调用默认未安装的 pip。
- **文件：** `backend/.python-version`、`backend/pyproject.toml`、`backend/uv.lock`（共 3 个）。
- **依赖：** FND-00。

### FND-02 — 固定前端依赖与 npm 锁文件

- [x] **验收：** React、TypeScript、Vite、React 插件、类型检查、Vitest、React Testing Library、ESLint/TypeScript ESLint、Playwright、OpenAPI 类型生成器全部纳入明确的依赖分类与 npm 锁文件；Node 主／次补丁基线写入版本文件。
- **验证：** 从 `frontend/` 执行 `npm ci`；`node --version`／`npm --version` 精确匹配提案；执行 `npm exec -- vite --version`、`npm exec -- vitest --version`、`npm exec -- playwright --version`、`npm exec -- secretlint --help`、`npm exec -- openapi-typescript --help` 成功；`@secretlint/secretlint-rule-preset-recommend@13.0.7` 已在锁文件中，`.secretlintrc.json` 启用了该规则集。
- **文件：** `frontend/.node-version`、`frontend/package.json`、`frontend/package-lock.json`、`frontend/.secretlintrc.json`（共 4 个）。
- **依赖：** FND-00。

### FND-03 — 建立 React + TypeScript + Vite 最小应用壳

- [x] **验收：** 有可运行的前端入口和语义化占位页；不提前加入天气、旅游供应商、行程规划等其他模块 UI；Vite 与 TypeScript 使用锁定依赖。
- **验证：** `npm run typecheck` 与 `npm run build` 通过；`npm run dev -- --host 127.0.0.1` 可本机打开；不以 `0.0.0.0` 对局域网暴露。
- **文件：** `frontend/index.html`、`frontend/src/main.tsx`、`frontend/src/App.tsx`、`frontend/vite.config.ts`、`frontend/tsconfig.json`（共 5 个）。
- **依赖：** FND-02。

### FND-04 — 配置前端 Lint、单元测试和 E2E 基线

- [x] **验收：** ESLint 能检查 TS/TSX；Vitest + React Testing Library 至少覆盖应用壳的渲染和可访问语义；Playwright 有本机 smoke 测试配置，且只访问本机测试服务器。
- **验证：** `npm run lint`、`npm run test:unit -- --run`、`npx playwright install chromium`、`npm run test:e2e`、`npm run typecheck` 全部通过；E2E 失败时保留诊断而非跳过测试。
- **文件：** `frontend/eslint.config.js`、`frontend/vitest.config.ts`、`frontend/src/App.test.tsx`、`frontend/playwright.config.ts`、`frontend/e2e/smoke.spec.ts`（共 5 个）。
- **依赖：** FND-03。

### FND-05 — 实现共享结果、来源、金额及公共错误契约

- [x] **验收：** 按获批 SPEC 建立严格的 Pydantic 类型；区分每种公共结果状态、未知金额与零、来源事实与核实状态；公共错误稳定且不携带内部秘密。
- **验证：** 在 `backend/` 执行 `uv run pytest tests/unit/test_contracts.py tests/unit/test_errors.py`；覆盖合法／非法状态、金额边界、`null`/0、额外字段和错误脱敏。
- **文件：** `backend/app/core/contracts.py`、`backend/app/core/errors.py`、`backend/tests/unit/test_contracts.py`、`backend/tests/unit/test_errors.py`、`backend/pyproject.toml`（pytest 根路径设置；共 5 个）。
- **依赖：** FND-01。

### FND-06 — 实现北京时间、UTC 与可替换时钟

- [x] **验收：** 日期-only 与 datetime 分开建模；无时区 datetime 拒绝；输出 UTC 时间戳；业务日固定 `Asia/Shanghai`，不依赖机器时区。
- **验证：** `uv run pytest tests/unit/test_time.py`；使用固定时钟覆盖 UTC 跨日／北京时间边界、闰日和无时区输入。
- **文件：** `backend/app/core/time.py`、`backend/tests/unit/test_time.py`、`backend/pyproject.toml`、`backend/uv.lock`（tzdata 为 Windows IANA 时区数据；共 4 个）。
- **依赖：** FND-01。

### FND-07 — 建立五城 WGS84 注册表及只读 API

- [x] **验收：** 五个试点城市具有稳定 ID；中心坐标范围有效、标明 WGS84、来源和核实状态；数据来源可追溯；注册城市不被表述为数据供应商覆盖；API 输出符合共享契约，错误符合公共模型。
- **验证：** `uv run pytest tests/unit/test_cities.py tests/integration/test_foundation_api.py`；检查五城、坐标边界、来源元数据、未知 ID 与 API schema。
- **文件：** `backend/app/core/cities.py`、`backend/app/modules/foundation/router.py`、`backend/app/main.py`、`backend/tests/unit/test_cities.py`、`backend/tests/integration/test_foundation_api.py`（共 5 个）。
- **依赖：** FND-01、FND-05。

### FND-08A — 建立严格配置与本地环境模板

- [x] **验收：** 使用 `pydantic-settings`／`python-dotenv` 支持 `.env` 解析，从环境变量与本地 `.env` 读取配置；只允许明确列出的 CORS origins；禁止 `*`、路径、凭证和非规范 Origin；无效配置 fail closed，验证输出不回显输入；可选 provider 缺少必需配置时返回未配置状态。
- **验证：** `uv run pytest tests/unit/test_config.py`；覆盖合法／非法环境、通配符、带路径 Origin、隐藏输入及 provider 配置缺失；全新锁定环境同步成功。
- **文件：** `backend/app/core/config.py`、`backend/.env.example`、`backend/pyproject.toml`、`backend/uv.lock`、`backend/tests/unit/test_config.py`（5 个；`pydantic-settings==2.16.1` 与 `python-dotenv==1.2.4` 已写入锁文件）。
- **依赖：** FND-01。

### FND-08B — 加入请求 ID、CORS 与公共异常处理

- [x] **验收：** 每个响应含随机 UUID `X-Request-ID`；错误体 request ID 与响应头一致；校验／业务／未知异常统一映射为安全 PublicError；日志只含 request ID、路由名、状态和耗时，不含异常消息／堆栈／凭证；CORS 使用精确来源，不允许 `*`，且不替代身份授权。
- **验证：** `uv run pytest tests/integration/test_config_security.py`；以模拟输入和 fake secret 覆盖合法／不合法 Origin、不同请求 ID、ValidationError、ServiceError 和未知异常响应／日志。
- **文件：** `backend/app/core/request_context.py`、`backend/app/main.py`、`backend/app/modules/foundation/router.py`、`backend/tests/integration/test_config_security.py`（4 个）。
- **依赖：** FND-05、FND-07、FND-08A。

### FND-09 — 导出 OpenAPI 并生成前端 API 类型

- [x] **验收：** FastAPI 是契约源；city API 和公共错误模型包含在 OpenAPI schema；`openapi-typescript` 生成的 TypeScript 文件可重复生成且前后端字段／可空性一致。
- **验证：** 在 `backend/` 执行 `uv run python scripts/export_openapi.py ../frontend/src/shared/openapi.json`；在 `frontend/` 执行 `npm run generate:api`、`npm run typecheck`；二次生成后 `api-contracts.ts` 文件哈希不变。
- **文件：** `backend/scripts/export_openapi.py`、`frontend/src/shared/openapi.json`、`frontend/src/shared/api-contracts.ts`（共 3 个；生成器依赖及 script 已由 FND-02 纳入）。
- **依赖：** FND-02、FND-05、FND-07、FND-08A、FND-08B。

### FND-10 — 完成 foundation 回归与验收留证

- [x] **验收：** foundation 范围的自动化检查全部通过；按 AC-01、AC-06、AC-25、AC-28、AC-36 记录实际通过／阻塞／证据缺口；不把 fixture 结果写成真实供应商验证，也不宣称 Web 首版完结。
- **验证：** `uv run pytest`、`uv run ruff check .`、`npm run lint`、`npm run test:unit -- --run`、`npm run test:e2e`、`npm run typecheck`、`npm run build`、`npm exec -- secretlint "../**/*" --secretlintrc=.secretlintrc.json`、`npm exec -- secretlint "dist/**/*" --secretlintrc=.secretlintrc.json --no-gitignore`；保存脱敏扫描摘要。
- **文件：** `docs/acceptance/foundation.md`（共 1 个验收记录文件；若需要改源代码修复，新增修复任务而不扩大本任务范围）。
- **依赖：** FND-01 至 FND-07、FND-08A、FND-08B、FND-09。

## 阶段边界

本清单已于 2026-10-27 获用户批准；`foundation` 任务 FND-00 至 FND-10 已完成并留存验收记录。每项完成后先验证，若失败则先修当前任务，不跳过失败测试、不顺手扩展其他模块。尚未批准的天气、交通、酒店、活动、景点、推荐、预算、导入、助手、行程、账号、本地存储、地图及 PDF 模块不会纳入本批编码。

## 审批记录

- 审阅人／日期：用户／2026-10-27
- 结论：批准
- 修改摘要：按 v0.1 任务清单批准。


## 实施备注

- FND-02 首次锁定失败的原因是 Secretlint 13.1.0 发布元数据引用尚未发布的 @secretlint/config-loader@13.1.0。按 npm registry 实测，使用 13.0.7 全套包后成功生成锁文件、完整安装、CLI smoke 和重复安装 dry-run；版本选择已调整为可解析且一致的 13.0.7，不更改 Secretlint 工具范围。







## 实施记录

- 用户于 2026-10-27 确认继续修订后的任务清单；FND-08A 的 Settings 依赖采用 `pydantic-settings`，`.env` 解析由其 `python-dotenv` 依赖提供，版本已锁定于 `uv.lock`。


# budget 任务清单

> 版本：v0.1｜状态：已完成｜用户批准及实施授权：2026-10-27  
> 对应已批准内容：[SPEC-budget](../docs/SPEC-budget.md)、[budget 实施计划](plan.md)。仅覆盖 `budget`；不接入供应商、不持久化、不修改 foundation/weather 行为。

## 固定实施规则

- 用户明确批准预算计划并授权代码编写；本清单按该授权实施，不扩展计划范围。
- 金额请求使用整数分；前端只接受不多于两位小数的十进制字符串，拒绝隐式舍入。
- 费用类别固定为往返交通、住宿、餐饮、市内交通、门票、活动、其他；不把费用类别当作事实来源。
- 保留现有 foundation 和 weather 的回归覆盖；预算为纯快照计算，页面刷新不承诺保留。
- 不新增依赖、不连接互联网、不初始化 Git、不设置 remote、不提交或推送。

## 任务（按依赖顺序）

### BUD-01 — 建立预算契约与纯计算测试

- [x] **验收：** Pydantic strict schema 覆盖预算快照、费用项、唯一 ID、预订关联、CNY 整数分、来源证据、完整度与响应字段；区分 `null`/0；重复 `cost_id`、同一 reservation 多主项、bool/float/负值拒绝。金额公式、阈值和状态真值表有单测。
- **验证：** `uv run pytest tests/unit/test_budget_contracts.py tests/unit/test_budget_service.py -q`
- **文件：** `backend/app/modules/budget/contracts.py`、`backend/app/modules/budget/service.py`、`backend/tests/unit/test_budget_contracts.py`、`backend/tests/unit/test_budget_service.py`。
- **依赖：** 已完成 foundation。

### BUD-02 — 接入预算计算 API 与隐私测试

- [x] **验收：** `POST /api/budget/calculate` 返回契约结果；重用公共错误和 request ID；验证错误体／响应头 ID 一致；日志不包含费用金额、订单关联 ID 或请求体。
- **验证：** `uv run pytest tests/integration/test_budget_api.py -q`
- **文件：** `backend/app/modules/budget/router.py`、`backend/app/modules/budget/__init__.py`、`backend/app/main.py`、`backend/tests/integration/test_budget_api.py`。
- **依赖：** BUD-01。

### BUD-03 — 建立前端金额工具和预算工作台

- [x] **验收：** 金额十进制字符串精确转分，空值与 0 区分，超过两位小数报错；可增删费用、编辑支付／待支付金额、总预算和人工预留金；响应展示剩余可安排与预计结余独立；用户填写报价标签、待核实、至少超支和预留提醒符合 SPEC；键盘和 375px 布局通过组件测试。
- **验证：** `npm run test:unit -- --run src/features/budget`
- **文件：** `frontend/src/features/budget/money.ts`、`frontend/src/features/budget/api.ts`、`frontend/src/features/budget/BudgetPanel.tsx`、`frontend/src/features/budget/budget-panel.css`、`frontend/src/features/budget/BudgetPanel.test.tsx`、`frontend/src/App.tsx`、`frontend/src/app.css`、`frontend/vite.config.ts`（同源 `/api` 到 loopback 后端代理）。
- **依赖：** BUD-01；API 类型可先按批准 schema 实现，最终须由 BUD-04 同步。

### BUD-04 — 同步 OpenAPI 与生成类型

- [x] **验收：** API schema 包含预算请求／响应及错误模型；生成类型与 OpenAPI 可空性一致，连续生成结果稳定。
- **验证：** 后端执行 `uv run python scripts/export_openapi.py ../frontend/src/shared/openapi.json`；前端执行 `npm run generate:api`、`npm run typecheck`。
- **文件：** `frontend/src/shared/openapi.json`、`frontend/src/shared/api-contracts.ts`。
- **依赖：** BUD-02。

### BUD-05 — 端到端、回归与验收留证

- [x] **验收：** E2E 覆盖完整预算、缺价/未知、用户补填标签、3000 元预留提醒、已知超支下界和 375px 无横向滚动；全项目前后端回归、Lint、typecheck、build、密钥扫描通过；AC-08 至 AC-11 逐项记录，真实报价及跨刷新持久化明确标为未实现。
- **验证：** 后端 `uv run pytest -q`、`uv run ruff check .`；前端 `npm run lint`、`npm run test:unit -- --run`、`npm run typecheck`、`npm run build`、`npm run test:e2e`；Secretlint 工作区和 `dist` 扫描；`npm run generate:api` 后确认重复生成无 diff。
- **文件：** `frontend/e2e/budget.spec.ts`、`docs/acceptance/budget.md`；修复只限上述 budget 文件范围和已列入口。
- **依赖：** BUD-01 至 BUD-04。

## 审批与边界

- 用户／日期：用户明确批准计划并授权代码编写／2026-10-27
- 本任务清单依该授权执行；不包含 GitHub 初始化、remote 配置、commit 或 push。
- 如测试发现 SPEC 未定义的高影响规则或必须新增依赖，暂停该具体决策并说明，不以实现细节静默扩大范围。
- 结论：BUD-01 至 BUD-05 全部完成；验收证据见 [`docs/acceptance/budget.md`](../docs/acceptance/budget.md)。



