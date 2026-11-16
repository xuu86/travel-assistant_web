# unknown-ledger 实施计划

> 版本：v0.1｜状态：已批准｜依据：[SPEC-unknown-ledger](../../docs/SPEC-unknown-ledger.md) v0.1、已批准首期范围与 Capability Map v0.5。

## 1. 目标与边界

在单一 owner 的浏览器工作区提供字段级待核实账本，按旅行日期与影响等级组织 T-7/T-3/T-0 应用内提示，并链接回来源视图。所有状态由现有证据或显式缺失状态得出；来源扫描未完成时展示覆盖缺口，不给出误导性的空账本。

仅使用 React/TypeScript 与当前 IndexedDB workspace store。无服务器写入、Push、系统通知、新 provider、新依赖、原件/OCR 文本持久化。源面板的当前查询状态若未持久化，仅在当前工作区内注册给账本；关闭或刷新后不宣称仍有该查询结果。

## 2. 关键实现设计

- 新增 `unknown-ledger` 纯领域包：统一 `LedgerObservation`、稳定来源键、证据状态、影响序数、出发日、建议节点、更新时间和返回模块 ID；通过显式状态区分 verified、needs-review、unavailable、not-loaded。
- Candidate adapters 由 source module 所有：budget/itinerary 从 owner snapshot 读取；weather/transport/hotels/activities/attractions 在每次数据状态变化时向 workspace ledger 提交最小字段摘要。查询原文、金额详情和 POI 地址不复制，除非必要字段本身就是待核实金额且 UI 必须显示该值；默认只存稳定引用与展示标签。
- Ledger 聚合器幂等合并 observations；来源删除时撤回其键；verified/removed 的 observation 关闭旧候选。用户“已联系/待回复”只作 owner-scoped workflow 状态，不改变证据级别。
- T 节点由旅行开始日按 `Asia/Shanghai` 的日历日差纯计算；建议时间规则由用户确认冻结为高 T-7、中 T-3、低 T-0。当前时间只用于标识提醒是否已到期，不通过后台定时任务触发。
- 目的地工作区增加账本导航/摘要；候选按旅行日、到期、影响级别稳定排序；“前往复核”设置目标 view 和可访问的回退焦点。
- Observation 从各 source 的当前状态与 owner snapshots 派生，不独立持久化；临时天气/交通/地点结果刷新后回到 not_loaded，避免陈旧候选。仅“已联系/待联系”工作流标记通过现有 IndexedDB 按 owner 分区保存；owner 未 ready 时不显示任何旧 owner 结果。

## 3. 实施顺序与检查点

| 顺序 | 工作包 | 验收重点 |
|---:|---|---|
| 1 | Contract 与纯计算 | 字段校验、稳定键、状态迁移、T-7/T-3/T-0、北京时间跨日、序数排序、null 与 0 |
| 2 | Owner-scoped observation repository/context | 来源 upsert/remove 幂等、flush/restore、owner 切换隔离、旧快照兼容 |
| 3 | Source adapters | budget、itinerary、weather、transport、POI 每个来源状态与字段级证据匹配；不保存原文件/查询 body |
| 4 | Ledger UI 与 navigation | 到期摘要、状态/来源/节点、扫描覆盖度、回源动作、空/部分/不可用状态、键盘与窄屏 |
| 5 | E2E、全回归、验收记录 | 桌面/移动、登出恢复、owner 隔离、源核实关闭、合成数据和隐私检查 |

共享 `App.tsx`、WorkspaceStore 与导航按顺序串行修改。每个工作包先写失败测试，再实施；任务清单控制每项约不超过五个文件。

## 4. 风险与门禁

- **扫描完整性：** 当前 POI、天气、交通结果部分只在内存；各源必须报告 not-loaded/unavailable，不可把未读到当成没有候选。
- **重复与陈旧：** observation key 由 source module 通过稳定实体/字段 ID 构造；更新和删除必须覆盖旧记录；不能用数组序号作为 ID。
- **证据状态：** 只由 source module 持有的证据驱动关闭；手工“已联系”不等于 verified。
- **时区：** 只按 `Asia/Shanghai` 日历日期比较，不使用执行设备本地时区。
- **存储：** 所有读写必须使用 WorkspaceStore 当前 owner；认证未 ready 或 store read-only 时明确显示，不能回退到全局 localStorage。

## 5. 验证与交付

`npm run test:unit -- --run`、`npm run typecheck`、`npm run lint`、`npm run build`、`npm run test:e2e -- --grep unknown-ledger`、前端 Secretlint。后端无改动时仍运行既有后端回归作为整体交付证据。通过后更新 `docs/acceptance/unknown-ledger.md` 与 Capability Map 状态；然后按用户要求将本模块独立提交、推送 GitHub，并从仓库提交构建后部署服务器，验证健康接口、静态资源哈希、应用内游客/登录安全门状态。部署必须保留 Caddy bind mount 的静态目录 inode 与现有环境配置。

## 6. 本计划不授权事项

不包含 L6 体检实现、服务器端账户、HTTPS/账号凭据配置、后台通知、跨设备同步、城市/字段范围扩展、路线或真实交通查询、真实地点房态/预约核验、自动更改源数据、GitHub PR 合并。

## 审批记录

- SPEC/范围：用户于 2026-11-16 确认 L2 与 L6 均做；L2 应用内 T-7/T-3/T-0，按高/中/低排序。
- 实施计划：用户于 2026-11-16 批准 v0.1。用户随后批准 L2/L6 两份任务清单并授权按依赖顺序编码；L2 完成并独立发布验收前不启动 L6。
