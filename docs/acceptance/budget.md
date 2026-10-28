# Budget 验收记录

> 日期：2026-10-27（北京时间）  
> 范围：Capability Map `budget`；不代表住宿／机票真实报价、持久化或 Web 首版整体完成。

## 结论

**预算模块实现与本地自动化验收通过。** 已交付严格费用契约、纯预算计算、`POST /api/budget/calculate`、响应式预算表单与摘要，以及 AC-08 至 AC-11 流程证据。该模块只计算请求快照，不落盘、不调用供应商。

## 实现范围

- 费用类别、EvidenceState、完整度、整数分金额与唯一费用／预订主项验证。
- 明确区分未设置／未知（`null`）和 0；未知金额不参加确定结余，已知超支可返回最低超出额。
- 剩余可安排仅按总预算减已支付；预计结余另扣待支付估算和人工预留金。
- 300,000 分预留金提醒仅在预留金为 `null` 时展示；不会自动创建金额。
- 元金额用十进制字符串精确解析，拒绝超过两位小数和超出安全整数范围的金额。
- 用户补填的未报价住宿／往返交通显示“用户填写，非平台报价”，证据状态保持 `user_provided`。
- 页面会话内计算，不声称保存或刷新恢复；真实平台报价、预订修改、导入去重和身份隔离归后续模块。

## 验证结果

| 验证 | 结果 |
|---|---|
| `uv run pytest -q` | 116 passed；Starlette TestClient/httpx 弃用提示 1 条 |
| `uv run ruff check .` | 通过 |
| `npm run lint` | 通过 |
| `npm run test:unit -- --run` | 27 passed，5 个测试文件 |
| `npm run typecheck` | 通过 |
| `npm run build` | 通过，Vite 8.3.5 |
| `npm run test:e2e` | 16 passed：桌面 Chromium 与 Pixel 7 配置各覆盖 weather/budget；预算 375px 无横向溢出 |
| OpenAPI 与 TS 类型重复生成 | 通过；`api-contracts.ts` 前后 SHA-256 一致 |
| Secretlint 源码／构建产物 | 通过；无发现 |

## AC 映射

| AC | Budget 子项 | 全局边界 |
|---|---|---|
| AC-08 | 用户补填住宿／交通金额有明确“用户填写，非平台报价”提示；API 保留 `user_provided`；组件与 E2E 通过 | 无平台真实房价／机票接入；D-016 只授权补填流程阶段验收 |
| AC-09 | 已支付、剩余可安排、已知待支付与预计结余分别计算和展示；部分支付只在单费用项中计入一次 | 费用跨模块聚合和锁定预订修改属于 itinerary/provider 后续能力 |
| AC-10 | null 与 0 区分；费用缺项保持待核实；已知支出超过预算时报告最低超出额 | 真实报价与全费用覆盖仍未验证 |
| AC-11 | 预留金由用户设置；3,000 元阈值及 `reserve=null/0` 边界通过 | 无自动推荐或持久保存预留金 |

## 安全与数据边界

- 集成测试确认 request ID 在响应体与 `X-Request-ID` 一致，重复费用返回统一 `VALIDATION_ERROR`。
- 合成 sentinel 金额、行程 ID 和预订 ID 不出现在请求日志中。
- 使用固定合成 ID 和金额进行测试；无真实费用、订单、密钥、行程文件或供应商请求。
- 本地 Vite `/api` 代理只转发到 `127.0.0.1:8000`；没有公网监听、DNS 或 GitHub remote 配置。

## 未完成能力

- 真实酒店／机票／铁路报价未接入或核实；本次 E2E 用 API 拦截验证界面，API 计算用本地集成测试验证。
- 预算与费用刷新恢复、IndexedDB、游客／账号 owner scope 未实现。
- 锁定预订防修改由 itinerary 模块负责；导入去重由 imports 负责。
- Git 仓库尚未初始化、未配置 GitHub remote、未提交或推送。
