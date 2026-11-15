# auth + local-storage 任务清单

> 版本：v0.1｜状态：实施完成；真实账号凭据尚未配置
> 对应规格：[SPEC-auth](../../docs/SPEC-auth.md)、[SPEC-local-storage](../../docs/SPEC-local-storage.md)；对应[实施计划](plan.md)。任务已获确认并实施。

## 通用执行规则

- 每项先补失败测试，再实现最小行为；按依赖顺序逐项验证，不跳过失败测试。
- 后端使用既有 Python 3.14、`uv`、pytest、Ruff；前端使用既有 Node/npm、Vitest、Playwright、TypeScript、ESLint、Vite 和 Secretlint。不增加生产或测试依赖。
- 不提交测试账号密码、明文口令、Cookie、token、测试报告中的凭据或真实用户数据；Playwright 测试仅用进程内合成测试账号。
- 当前 worktree 已有未提交的预算订单导入修改（含 `BudgetPanel.tsx`、样式、`order-import.ts` 和依赖清单）；后续 STORE-04 必须在这些现有修改之上集成，禁止覆盖或回退它们；本功能不因此新增或改写依赖。
- IndexedDB 的身份分区使用服务端 auth 返回的稳定 `owner_id`，游客 ID 由浏览器本机生成并持久化；严禁以用户名、用户可编辑字段或每次启动随机值作为账号分区键。
- 刷新/登录恢复只恢复用户输入和已确认业务状态；不把旧 loading/error 或无有效期证明的外部查询结果当作当前事实。身份变化需卸载旧工作区、隔离 writer 并加载目标分区。
- 除所列文件外，不顺手重构模块；若实现发现需新增依赖、数据库或扩大范围，暂停并重新审阅。

## 任务（按依赖顺序）

### AUTH-01 — 测试账号配置与安全口令验证

- [x] **验收：** 在 `Settings` 增加可选的测试账号配置；仅在配置有效时允许账号登录。服务端将用户名规范化策略固定并校验重名/格式；密码以随机 salt 的 PBKDF2-HMAC-SHA256 哈希校验，使用常量时间比较。配置缺失或格式错误不妨碍游客启动；不得回显、记录或存储明文密码。
- [x] **验证：** `uv run pytest tests/unit/test_auth_config.py -q`（10 passed）与 auth 文件 Ruff 检查（通过）；测试错误配置、有效哈希、未知用户/错误密码路径、空配置和敏感值不出现在 repr/日志。
- [x] **文件：** `app/core/config.py`、`app/modules/auth/__init__.py`、`app/modules/auth/credentials.py`、`scripts/configure_test_accounts.py`、`tests/unit/test_auth_config.py`（5 个）。
- **依赖：** 无。

### AUTH-02 — 会话服务与三个认证端点

- [x] **验收：** 实现 `GET /api/v1/auth/session`、`POST /api/v1/auth/login`、`POST /api/v1/auth/logout`。登录成功设置 HttpOnly、SameSite=Lax Cookie；Secure 按 environment 配置且生产必须为真。Opaque session 原文只存在 Cookie，后端索引存摘要；支持过期、幂等撤销和进程重启失效。游客响应提供稳定契约，不信任客户端提交 owner；用户名不存在和密码错误返回同一状态/文案。认证仅接受同源请求并执行已冻结的 Origin/CSRF 校验。
- [x] **验证：** `uv run pytest tests/unit/test_auth_service.py tests/integration/test_auth_api.py -q`（10 passed）与 auth 文件 Ruff 检查（通过）；覆盖 Cookie flags、会话到期/撤销、失败限流、恶意 Origin 和 sentinel 凭据无泄露。
- [x] **文件：** `app/modules/auth/contracts.py`、`app/modules/auth/service.py`、`app/modules/auth/router.py`、`app/main.py`、`tests/integration/test_auth_api.py`（5 个；service 单测随 AUTH-03 文件组安排）。
- **依赖：** AUTH-01。

### AUTH-03 — 认证 API 契约与后端单元覆盖

- [x] **验收：** OpenAPI schema 精确描述认证请求/响应、Cookie 与公共错误，不暴露账号表、hash 或 session 原文；auth service 对有效会话、失败登录、退出和 session 读取有独立单测。
- [x] **验证：** `uv run pytest tests/unit/test_auth_service.py -q`；`uv run python scripts/export_openapi.py ../frontend/src/shared/openapi.json` 后在 `frontend/` 执行 `npm.cmd run generate:api`、`npm.cmd run typecheck`；再次导出并生成确认输出稳定。
- [x] **文件：** `tests/unit/test_auth_service.py`、`frontend/src/shared/openapi.json`（生成）、`frontend/src/shared/api-contracts.ts`（生成）（3 个）。
- **依赖：** AUTH-02。

### AUTH-04 — 前端认证 API 与登录交互

- [x] **验收：** 前端提供同源 session/login/logout API 和游客/登录状态；用户可打开登录对话框、继续游客、看到安全错误提示、查看当前非敏感账号名并退出。认证 Cookie 不进入 JS 可读存储；登录失败不清空当前内存工作区。
- [x] **验证：** `npm run test:unit -- src/features/auth`、`npm run typecheck`、`npm run lint`；组件测试覆盖游客、成功/失败登录、登出、会话 API 不可用和无凭据配置状态。
- [x] **文件：** `src/features/auth/api.ts`、`src/features/auth/AuthProvider.tsx`、`src/features/auth/LoginDialog.tsx`、`src/features/auth/auth.css`、`src/features/auth/AuthProvider.test.tsx`（5 个）。
- **依赖：** AUTH-03。

### AUTH-05 — 应用启动身份门与账号切换隔离

- [x] **验收：** 应用启动先解析 session，再以稳定 owner key 挂载工作区；loading 时不闪现旧 owner 内容。登录、登出或会话过期改变 owner 后卸载旧树并加载目标身份；游客无后端 session 服务时保留显式可见错误/重试而不假称登录。所有工作区子面板均随 owner key 重新初始化。
- [x] **验证：** `npm run test:unit -- src/App.test.tsx src/features/auth`、`npm run typecheck`、`npm run lint`；测试认证加载延迟、身份切换时旧内容不渲染、认证错误重试。
- [x] **文件：** `src/App.tsx`、`src/main.tsx`、`src/app.css`、`src/App.test.tsx`（4 个）。
- **依赖：** AUTH-04。

### STORE-01 — IndexedDB schema、owner 分区 repository

- [x] **验收：** 新增应用专用 IndexedDB 数据库和版本化 schema；repository 所有查询/写入/删除都显式要求 owner ID，使用事务写入；游客和账号记录不会互见。升级失败、数据库拒绝、QuotaExceeded 和损坏快照不得静默删除旧数据。
- [x] **验证：** `npm run test:e2e -- e2e/local-storage.spec.ts` 使用真实浏览器 IndexedDB 验证 CRUD、空分区、跨 owner 隔离、事务失败/损坏记录处理及版本升级；`npm run typecheck`、`npm run lint`。不添加 fake-indexeddb 或其他依赖。
- [x] **文件：** `src/features/local-storage/database.ts`、`src/features/local-storage/repository.ts`、`src/features/local-storage/types.ts`、`e2e/local-storage.spec.ts`（4 个）。
- **依赖：** AUTH-05（owner 契约）。

### STORE-02 — 持久化快照与迁移纯函数

- [x] **验收：** 定义版本化 workspace snapshot DTO；只包含已批准的目的地/日期/工作区选择、手工业务状态和恢复所需的表单输入；不包含密码、token、内部错误、AbortController、loading 标志或无时间语义外部结果。encode/decode 和 schema migration 可确定、可重复；未知版本保留原记录并报告不可读取。
- [x] **验证：** `npm run test:unit -- src/features/local-storage`；参数化测试覆盖 null/空值、非法/未知版本、缺字段迁移、敏感字段拒绝和往返稳定性。
- [x] **文件：** `src/features/local-storage/snapshot.ts`、`src/features/local-storage/snapshot.test.ts`、`src/features/local-storage/migrations.ts`（3 个）。
- **依赖：** STORE-01。

### STORE-03 — 工作区级条件与导航恢复

- [x] **验收：** 持久化 App 顶层目的地、起终点、开始/结束日期、当前工作区视图及可恢复的表单条件；地理位置只保存用户明确选择/输入的地点，不保存精确设备坐标，除非已有单独同意。恢复时重新初始化 provider 状态，不恢复旧查询结果或加载状态。空分区仍使用现有默认首次体验。
- [x] **验证：** `npm run test:unit -- src/App.test.tsx src/features/local-storage` 与 `npm run typecheck`；测试刷新后条件/视图恢复，目的地切换、会话过期和 owner 变化不串数据。
- [x] **文件：** `src/App.tsx`、`src/features/local-storage/useWorkspacePersistence.ts`、`src/features/local-storage/useWorkspacePersistence.test.ts`、`src/features/local-storage/snapshot.ts`（4 个）。
- **依赖：** STORE-02。

### STORE-04 — 行程与预算手工数据恢复

- [x] **验收：** 将 `ItineraryPanel` 安排/锁定/完成/当前编辑草稿，以及 `BudgetPanel` 总额、预留金和费用草稿接入受控 snapshot props 或明确的持久化 adapter。计算请求、loading、provider 响应和错误不保存；锁定状态不能被恢复逻辑重置。订单导入的原始文件、识别候选、进度与错误不持久化；用户确认后形成的费用明细必须保留。
- [x] **验证：** `npm run test:unit -- src/features/itinerary src/features/budget`；新增刷新恢复、编辑中恢复、锁定项保持锁定、异步计算结果不落盘、订单确认后的费用可恢复/未确认候选不恢复测试。
- [x] **文件：** `src/features/itinerary/ItineraryPanel.tsx`、`src/features/itinerary/ItineraryPanel.test.tsx`、`src/features/budget/BudgetPanel.tsx`、`src/features/budget/BudgetPanel.test.tsx`、`src/features/local-storage/snapshot.ts`（5 个）。
- **依赖：** STORE-03。

### STORE-05a — 行前清单与笔记恢复

- [x] **验收：** 持久化 Checklist 勾选/自定义条目，以及 Notes 已保存笔记/编辑草稿。刷新恢复勾选和笔记；已删除条目不得复活。
- [x] **验证：** `npm run test:unit -- src/features/checklist src/features/notes`；覆盖勾选、自定义条目、笔记新增/编辑/删除与刷新恢复。
- [x] **文件：** `src/features/checklist/ChecklistPanel.tsx`、`src/features/checklist/ChecklistPanel.test.tsx`、`src/features/notes/NotesPanel.tsx`、`src/features/notes/NotesPanel.test.tsx`（4 个）。
- **依赖：** STORE-04。

### STORE-05b — 地点搜索条件恢复

- [x] **验收：** 持久化 Places 搜索关键词与分类；地点查询结果不作为持久化事实。刷新恢复搜索条件，搜索由用户重新触发，不复用旧 POI 响应。
- [x] **验证：** `npm run test:unit -- src/features/places`；测试搜索词恢复、条件编辑清空旧结果，查询结果不复用。
- [x] **文件：** `src/features/places/PlacesPanel.tsx`、`src/features/places/PlacesPanel.test.tsx`、`src/features/local-storage/snapshot.ts`（3 个）。
- **依赖：** STORE-05a。

### STORE-06 — 交通和地图选择恢复

- [x] **验收：** 持久化 transport 已提交查询输入与用户选择的地点引用；地图当前选中地点仅在地点属于当前工作区且必要字段有效时恢复。所有班次/路线/POI 外部响应和地图加载状态不落盘。
- [x] **验证：** `npm run test:unit -- src/features/transport src/features/maps`；测试表单查询条件恢复、来源结果重载/清空、地图选择与新 owner 隔离。
- [x] **文件：** `src/features/transport/TransportPanel.tsx`、`src/features/transport/TransportPanel.test.tsx`、`src/features/maps/MapPanel.tsx`、`src/features/maps/MapPanel.test.tsx`、`src/features/local-storage/snapshot.ts`（5 个）。
- **依赖：** STORE-05b。

### STORE-07 — 自动保存、错误反馈与身份切换写入保护

- [x] **验收：** 工作区变更经可控防抖保存；界面可访问地显示 saving/saved/error 和重试。保存错误保留内存草稿并不假报成功。owner 变化时旧 writer 完成或取消，写操作始终绑定创建时 owner，目标身份加载完成前屏蔽旧内容。
- [x] **验证：** `npm run test:unit -- src/features/local-storage` 与 Playwright 的快速连续编辑/身份切换/保存失败用例；验证迟到写入未污染另一分区，`npm run lint`、`npm run typecheck`。
- [x] **文件：** `src/features/local-storage/useWorkspacePersistence.ts`、`src/features/local-storage/useWorkspacePersistence.test.ts`、`src/App.tsx`、`src/App.test.tsx`、`src/app.css`（5 个）。
- **依赖：** STORE-03 至 STORE-06。

### STORE-08 — 登录、退出和刷新连续性 E2E

- [x] **验收：** 使用测试进程合成凭据覆盖游客草稿→刷新恢复、账号 A 编辑→退出→A 重登恢复、B 登录看不到 A 数据、错误密码不清空当前草稿、会话失效转游客但保留各分区；测试不将凭据写入快照/报告。
- [x] **验证：** `npm run test:e2e -- e2e/auth-persistence.spec.ts`，桌面和 375px viewport 通过，禁止水平溢出；截图和 trace 不包含凭据。
- [x] **文件：** `frontend/e2e/auth-persistence.spec.ts`、`frontend/e2e/fixtures/auth.ts`、`frontend/playwright.config.ts`、`backend/tests/integration/test_auth_api.py`（4 个）。
- **依赖：** AUTH-01 至 STORE-07。

### STORE-09 — 全量回归和验收记录

- [x] **验收：** 形成 `docs/acceptance/auth-local-storage.md`，分别记录真实配置账号与仅测试 fixture 的结果；明确本地 IndexedDB、登出保留、无云同步、进程重启 session 失效与未验证的部署边界。
- [x] **验证：** 后端全量 pytest/Ruff 通过（428 passed）；Vitest 110 passed、TypeScript、ESLint、Vite build、Secretlint 通过；本机 Chrome 下全量 Playwright 桌面/移动 52 passed。真实账号仍待凭据所有者配置。
- [x] **文件：** `docs/acceptance/auth-local-storage.md`（1 个）。
- **依赖：** STORE-08。

## 未决事项

- Q-008 的真实测试用户名、初始密码和重置方式须由负责人私下配置；不阻塞无秘密的单测/E2E fixture，但未配置前真实账号验收保持未完成。
- 认证 Cookie 的本机/局域网 HTTP、生产 Secure 与 Origin 策略需在 AUTH-02 开始前从当前 Vite proxy 与 LAN 运行配置核实；若需要改部署/CORS，先更新计划并征求批准。
- IndexedDB 快照确切字段以 STORE-02 对当前面板 state 的白名单映射为准；若用户预期包括未保存的跨浏览器内容或外部查询结果，应先修改规格而非扩大快照。
