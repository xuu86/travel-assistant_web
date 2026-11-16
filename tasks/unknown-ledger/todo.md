# unknown-ledger 任务清单

> 版本：v0.1｜状态：全量回归与发布验收中｜依据：[SPEC-unknown-ledger](../../docs/SPEC-unknown-ledger.md)、[实施计划](plan.md)。用户于 2026-11-16 批准本清单并授权按 L2 → 发布 → L6 顺序编码。

## 固定规则

- 观察项由来源当前状态/owner 快照派生且不独立持久化；仅“已联系/待联系”状态写入现有 WorkspaceStore 的 owner_id 分区；不新增 localStorage、后端存储、推送或依赖。
- 各源模块负责观察值和证据；账本不推断事实。未加载、不可用与扫描后无候选必须分别表示。
- null 不等于 0；user_provided、estimate、unknown 均不得自动升级为 verified；“已联系/待回复”不关闭候选。
- 订单原件、OCR 全文、完整请求体、凭据、无必要的金额和地点细节不进入 observation。
- 每个任务先写失败测试再实现；通过一个工作包后才开始下一个。L2 完成并同步 GitHub/服务器后才开始 L6。

## 任务（按依赖顺序）

### UL-01 — 定义 observation 契约与提醒纯函数

- [x] **验收：** 定义稳定 `source_key`、实体/字段、模块、证据状态、影响等级、旅行日期、取数时刻、coverage 状态和回源动作；支持 verified/needs_review/not_loaded/unavailable。T-7/T-3/T-0 按北京时间日历日正确计算，影响等级顺序稳定；重复/非法键拒绝。
- **验证：** `npm run test:unit -- --run src/features/unknown-ledger/model.test.ts`，覆盖跨午夜/闰日、节点边界、序数排序、source 更新/删除、null/0、幂等键。
- **文件：** `frontend/src/features/unknown-ledger/model.ts`、`model.test.ts`（2 个）。
- **依赖：** 已批准 SPEC/计划。

### UL-02 — 建立 owner 分区的 observation 聚合和生命周期

- [x] **验收：** 建立 owner-scoped ledger workflow 状态保存；观察项由当前模块状态派生并在源更新/卸载时替换/撤回，不独立存储；ready 前不展示旧 owner 状态；旧 snapshot 保持兼容；只读存储失败有明确状态。
- **验证：** provider/repository 测试覆盖 workflow restore、竞态、flush、清空 owner、owner A/B 隔离、切换与登出恢复；刷新后临时 source observation 不残留；不得改动其他 owner 数据。
- **文件：** `WorkspacePersistenceProvider.tsx`、`workspace-context.ts`、ledger repository/model tests（每次改动控制在 5 个文件内）。
- **依赖：** UL-01。

### UL-03 — 接入预算与行程来源适配器

- [x] **验收：** budget 对未知支付/未核实金额、itinerary 对 unknown evidence/缺少已要求字段产生字段级 observations；手工用户输入仍标用户提供；源字段变 verified、移除或清除后对应候选关闭；不把稳定数组序号作为 ID。
- **验证：** 预算/行程 adapter 单测和 BudgetPanel/ItineraryPanel 集成断言；原有预算计算、导入隐私和锁定规则不变。
- **文件：** 各模块 adapter 与 tests（每项不超过 5 个文件）。
- **依赖：** UL-01、UL-02。

### UL-04 — 接入天气、班次与地点来源状态

- [x] **验收：** 以最小字段摘要接入 weather、transport、hotel、activity、attraction 的当前查询/coverage；未查询标 not_loaded，错误/未配置标 unavailable/coverage gap，不误报空清单；来源更新时间变化可见；不保留原请求体或 POI 地址。
- **验证：** 每类 adapter 有 success/partial/empty/unconfigured/error/verified transition 测试；检查 IndexedDB snapshot 无 query text、OCR 或凭证 sentinel。
- **文件：** 相关面板/adapter 与测试分批完成（每批不超过 5 个文件）。
- **依赖：** UL-01、UL-02。

### UL-05 — 实现账本视图、工作区导航和回源动作

- [x] **验收：** 展示到期摘要、按旅行日/节点/影响排序的字段清单、source/evidence、已联系状态和扫描覆盖状态；加载失败、部分覆盖、无候选分开呈现；“前往复核”切换正确视图并聚焦匹配来源条目；沿用现有视觉风格、键盘语义与移动布局。
- **验证：** React Testing Library 检查可见状态、ARIA、focus/return target、空/部分/错误结果；375px 无水平溢出。
- **文件：** `App.tsx`、`App.test.tsx`、账本 panel/style/test（每次提交不超过 5 个文件）。
- **依赖：** UL-02 至 UL-04。

### UL-06 — 完成 E2E、全量回归、留证并逐模块发布

- [ ] **验收：** 桌面/手机覆盖 owner 隔离、登出后恢复、来源被核实后关闭、已联系仍未核实、未加载/不可用/空账本区分、回源动作、T 节点显示和无障碍；Capability Map 与 `docs/acceptance/unknown-ledger.md` 反映实际范围。构建物来自发布提交。
- **验证：** 前端 Vitest、typecheck、lint、build、全量 Playwright、Secretlint；后端 pytest/Ruff 回归；部署后 `/api/health` 为 200、线上 JS/CSS 哈希匹配构建、匿名 HTTP 不可提交凭据。
- **文件：** `frontend/e2e/unknown-ledger.spec.ts`、验收记录、Capability Map（按阶段）。
- **交付：** L2 单独提交并推送 GitHub；从该提交构建并部署服务器，备份配置与旧产物，保留 Caddy 静态目录 inode；发布验证完成后才转入 L6。
- **依赖：** UL-01 至 UL-05。

## 审批记录

- L2 SPEC/计划：用户于 2026-11-16 批准范围和实施计划。
- 任务清单与编码授权：用户于 2026-11-16 批准两份任务清单并授权按依赖顺序实施；L2 发布前不启动 L6。
