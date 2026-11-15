# auth + local-storage 实施计划

> 版本：v0.1｜状态：已确认并实施
> 对应规格：[SPEC-auth](../../docs/SPEC-auth.md)、[SPEC-local-storage](../../docs/SPEC-local-storage.md)（均已确认）。本计划审批仅允许建立任务清单，不代表任务清单或编码获批。

## 1. 目标与范围

为 Web 旅行工作区接入游客/测试账号身份，并使当前用户的操作在刷新、浏览器重启、退出后仍可恢复。游客和五个账号的数据分别保存在当前浏览器 IndexedDB 中；同一账号重新登录时恢复原分区，身份切换时不展示或覆盖其他分区。

本计划不实现公开注册、正式线上账号、云端行程、跨设备同步、游客数据迁移、微信登录、凭证文件持久化、付款或预订。不增加数据库、ORM、SDK 或 npm 依赖。测试账号凭据只能经私密配置提供，不在代码或文档中填写真实凭据。

## 2. 已冻结口径与实施前提

1. 游客免登录；已配置测试账号经后端密码哈希校验后登录，不能仅选择用户名模拟登录。
2. 行程只保存在客户端 IndexedDB，以不可变 `owner_id` 分区；退出不删除数据，切换身份不合并数据。
3. 身份变化时先阻止旧身份渲染和写入，再加载新身份快照。异步保存必须捕获写入时 owner，迟到回调不得读取“当前 owner”后改写归属。
4. 首期沿用现有单 FastAPI 进程运行方式；会话存储为进程内、随机高熵 opaque session，服务重启使会话失效但不影响 IndexedDB 数据。此决策只适用于当前本机/局域网测试账号，不视作多进程或生产部署方案。
5. Cookie `HttpOnly`、`SameSite=Lax`；开发 HTTP 可关闭 `Secure`，生产强制开启。仅同源请求发送认证 Cookie，并校验 `Origin`/CSRF 策略；不扩大现有 CORS。
6. IndexedDB 初始 schema 包含 schema version、owner ID、稳定行程记录 ID、更新时间和可验证的行程快照。瞬时 provider loading/error 状态不作为已确认事实恢复；重新打开时相关查询状态重置并按现有规则刷新或显示待查询。
7. 现有草稿需映射到持久化快照的确切字段、自动保存防抖、会话过期呈现和游客身份生成方式，在任务清单阶段结合当前 `App.tsx` 和子面板 state 清单冻结。

## 3. 技术方案

### 3.1 后端认证

- 新增 `backend/app/modules/auth/`，以 FastAPI router、Pydantic contracts 和 service 隔离凭据校验及会话管理；在 `main.py` 注册路由。
- 在现有 `Settings` 中读取测试账号配置。配置格式只允许在任务阶段选定无歧义且可校验的形式；密码验证用 Python 标准库 PBKDF2-HMAC-SHA256 + 独立随机 salt/常量时间比较，服务仅加载哈希，不记录密码/哈希。
- 会话使用高熵随机 token 的摘要作为服务端进程内索引，原 token 仅通过 HttpOnly Cookie 发给浏览器；会话结构绑定稳定账号 ID、创建/到期时间和撤销状态。未配置账号时游客仍可用，登录明确报告不可用。
- `GET /api/v1/auth/session` 返回 `owner_id`、身份类型、必要显示名；`POST /api/v1/auth/login` 验证并设置 Cookie；`POST /api/v1/auth/logout` 撤销并清 Cookie。无效账号/密码统一响应；对登录失败限流使用进程内按源地址+用户名摘要的轻量计数及退避，避免持久保存密码输入。
- 认证 API 仅支持同源；Origin/CSRF 校验按项目已有 CORS 和 LAN 入口配置实现，不将 Cookie 放进前端存储。

### 3.2 前端身份与持久化

- 新增 `features/auth/` API、状态 hook/context、登录对话框/控件与样式；用户可继续游客使用、登录、查看当前身份并退出。
- API 在同源下 `credentials: "same-origin"`。启动先查询 session，得到 owner 后才挂载/恢复工作区；退出、登录或身份变更时以显式工作区 key 隔离组件状态，避免旧面板缓存泄露。
- 新增 `features/local-storage/` IndexedDB 数据库、事务封装、repository 和 schema migration；不得将行程或秘密放进 localStorage。保存/恢复采用纯数据 DTO 白名单，拒绝运行时 provider 对象、错误对象、控制器、API 原始数据及凭据。
- 对照 `App.tsx`、行程/预算/交通/备注/清单/地点等子面板 state，定义工作区快照映射；保存适合恢复的用户输入和已确认业务编辑，丢弃瞬时加载状态。Provider 查询数据只在契约明确可复用且来源/时间完整时保存，否则重新查询。
- 自动保存采用防抖并报告 saving/saved/error；保存失败保留内存状态和重试入口。切换 owner 前 flush/cancel 当前 writer 并卸载旧 workspace，然后加载对应 owner；从无快照开始时用现有初始状态。
- 登录/登出不做游客到账号的数据合并，不删除任何分区。工作区可在会话之外继续游客使用；只有当前身份分区可进入 UI。

## 4. 组件顺序与检查点

| 顺序 | 组件 | 主要工作 | 依赖 | 检查点 |
|---:|---|---|---|---|
| 0 | 运行基线与快照盘点 | 运行既有命令；列明 `App.tsx` 及子面板可恢复/瞬态 state；冻结 DTO 字段 | 已有 foundation、两份规格 | 基线命令和当前测试可复现；数据清单已审阅且不含秘密/不支持对象 |
| 1 | 后端 auth 契约和配置 | 三个端点契约、配置校验、口令哈希 helper、service 单测 | 0 | 无配置仍允许游客；错误账号不可区分；明文密码不进日志/存储 |
| 2 | 后端会话和路由 | cookie 签发/撤销、Origin/CSRF 检查、限流和 API 集成测试、OpenAPI 输出 | 1 | 登录—session—logout 完整；重启后会话失效；生产 Secure 校验通过 |
| 3 | 前端 auth 状态和交互 | 启动身份检查、游客/登录/退出 UI、通用错误、身份变化隔离工作区 | 2 | session 未知期间不暴露旧分区；失败保留草稿；键盘及移动端可操作 |
| 4 | IndexedDB repository | 数据库 schema、owner 索引、原子 CRUD、迁移与异常处理 | 0、3 的 owner 契约 | fake-indexeddb 环境或浏览器测试覆盖隔离、升级、失败；不增加依赖 |
| 5 | 工作区快照与自动恢复 | DTO 映射、自动保存、启动恢复、刷新/登出/重登恢复和错误反馈 | 3、4 | 在测试中逐字段确认输入恢复；瞬态结果不冒充持久事实 |
| 6 | 集成回归与验收记录 | 桌面/移动 E2E、A/B 隔离、session 失效、全量测试/lint/build/secretlint | 1–5 | 通过的流程与未配置账号/无云同步边界记录在 acceptance |

依赖图：`0 → 1 → 2 → 3 → 4 → 5 → 6`，其中组件 4 可在 owner 契约冻结后与组件 3 后段并行；快照自动恢复必须等待两者完成。OpenAPI 导出在认证路由稳定后进行。

## 5. 验证门

- **Gate A：后端身份：** `uv run pytest` 验证合法/无效账号、相同通用失败、哈希校验、无账号配置、限流、Origin 校验、cookie 属性、登出幂等、重启/撤销后失效和 request ID；sentinel 密码不得出现在日志、响应或错误信息。
- **Gate B：存储隔离：** `npm run test:unit` 验证 IndexedDB 升级、读写删除、A/B/guest owner 隔离、事务失败和损坏快照不静默覆盖；所有异步写在身份切换后仍归原 owner。
- **Gate C：工作区连续性：** `npm run test:unit` 覆盖 snapshot encode/decode、默认快照、数据迁移、自动保存 debounce、保存失败重试和各状态恢复语义。
- **Gate D：用户流程：** Playwright 使用仅限测试进程的 fixture credentials 完成游客编辑→刷新恢复、A 登录→编辑→退出→A 重登恢复、B 登录不可见 A 数据、错误密码不丢游客草稿、会话过期回到游客并保留分区。凭据来自测试进程内 fixture，禁止写到报告和截图。
- **Gate E：回归与发布边界：** 后端 `uv run pytest`、`uv run ruff check .`；前端 `npm run test:unit`、`npm run test:e2e`、`npm run typecheck`、`npm run lint`、`npm run build`、`npm run secretlint`；确认不新增依赖、数据库、API 外发或 CORS wildcard。

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 测试账号配置尚未下发（Q-008） | 无法真实登录验收 | 用仅存在测试运行内存中的 fixture 验证；未配账号时 UI 明确显示登录不可用；不提交密码 |
| 进程内会话被多 worker 分裂 | 请求可能随机未认证 | 明确限制单进程本地/局域网测试；未来多 worker 前必须升级共享会话存储并重新审批 |
| Cookie 在局域网 HTTP 的 SameSite/Secure 行为差异 | 手机端登录不稳定 | 同源部署、Secure 仅生产启用，并在真实桌面/手机浏览器验收 LAN origin |
| 快照遗漏某个面板状态 | 用户以为已保留但刷新后丢失操作 | 以 state 清单驱动快照字段测试，关键 UI 操作逐项纳入 E2E |
| 瞬态查询响应过期后被恢复 | 展示旧天气/价格等数据 | 默认不保存查询响应，恢复业务输入后重新查询，并保留来源与时间规则 |
| 身份切换时旧异步写越权 | A 数据进入 B 分区 | writer 按创建时 owner 绑定；切换等待 flush/cancel；测试控制迟到 promise |
| IndexedDB 配额/升级失败 | 保存失败或旧数据不可读 | 原子迁移、保留旧 store、界面报错并保留内存草稿；不吞掉异常 |

## 7. 预期文件范围

任务清单阶段按每项不超过约 5 个文件拆分。预计会触及：

```text
backend/app/core/config.py
backend/app/main.py
backend/app/modules/auth/{__init__,contracts,service,router}.py
backend/tests/unit/test_auth_service.py
backend/tests/integration/test_auth_api.py
backend/app/scripts 或现有配置说明（仅说明变量名，不含值）
frontend/src/features/auth/{api,AuthProvider,LoginDialog,auth.css}.ts(x|css)
frontend/src/features/local-storage/{database,repository,snapshot}.ts
frontend/src/features/local-storage/*.test.ts
frontend/src/App.tsx
frontend/src/app.css
frontend/src/shared/openapi.json                 # 后端生成
frontend/src/shared/api-contracts.ts              # 生成
frontend/e2e/auth-persistence.spec.ts
docs/acceptance/auth-local-storage.md
```

上述清单是候选范围，不代表获准扩大 `main.py`、已有面板或契约修改；任务拆分时逐项冻结，避免无关重构。

## 8. 计划完成定义

后续实现通过后，应证明游客与五个测试账号均有稳定 owner 分区；配置好的账号必须真实校验而非模拟用户名切换；同一账号退出/重登及刷新后恢复本地工作区；其他身份数据不可见；密码/会话不进入浏览器可读存储、日志、URL 或产物；瞬态查询状态不被冒充为仍然有效；全部后端、前端、E2E、类型、Lint、构建和密钥扫描通过。真实账号凭据未下发时，验收记录必须如实标明受阻的真实账号登录场景，不能据测试 fixture 宣称配置验收完成。

## 9. 本阶段不授权事项

本计划获批后仅进入 `tasks/auth-local-storage/todo.md` 任务拆分阶段。编码需在任务清单获批后另行明确授权。当前不添加测试账号秘密、不创建数据库、不安装依赖、不启用公网/多进程部署、不做云端同步或真实用户迁移。

## 10. 审批记录

- 规格确认：用户已确认 `SPEC-auth` 与 `SPEC-local-storage`。
- 计划审阅人／日期：待确认。
- 结论：待确认。
