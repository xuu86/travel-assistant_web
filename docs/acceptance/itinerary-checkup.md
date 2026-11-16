# 行程体检（L6）验收记录

验收日期：2026-11-16（北京时间）。本版是当前 owner 工作区内的本地只读五维分析；不持久化单独报告，不调用路线/地图/天气/预算 provider，不自动修改行程。

## 功能验收

- 行程安排支持可选用户填写的停留分钟、下一段通行分钟、室内/户外/未知、步行公里、台阶和换乘次数；空值保持未知，旧快照继续兼容，负数、非整数计数和越界值拒绝。
- 时间维度仅用显式开始、停留和非末项交通分钟计算每日缓冲；预算维度读取当前 owner 的预算上限、预留金和费用明细快照；任一未知金额都会令预算不足。
- 体力维度依据用户提供步行/台阶/换乘/连续户外数据；天气只消费当前 App 天气结果、有效 coverage 和已核实非 demo 来源，不借邻日数据补齐。
- L2 待核实项复用 owner-scoped ledger 当前视图及 complete coverage；高/中/低按 20/10/5 扣分，不按提醒到期重复扣分。五维全部有分时才显示综合分。
- 维度显示缺项、说明、来源和覆盖；建议排序确定、最多三条，涵盖时段冲突、可补充字段、低预算余量、高天气风险和账本项。来源按钮回到输入模块；关联锁定安排只读，不自动变更。
- 桌面与 375px 手机 E2E 验证数据不足状态、回源聚焦和锁定安排不变；无横向溢出。

## 自动化验证

- 前端 Vitest：27 个测试文件，155 tests passed。
- TypeScript：应用与 E2E 两份 tsconfig 检查通过。
- ESLint：全前端通过。
- Vite production build：通过，输出内容哈希资源。
- Playwright：桌面 Chromium 与手机 Chromium 全量 56/56 通过；含 L6 缺项与锁定回源测试。
- 后端 pytest：428 passed；仅有现存 Starlette/httpx 弃用提示。L6 未修改后端。
- Secretlint：对 `backend/app`、`frontend/src` 与 `frontend/dist` 扫描通过，无发现。

Playwright 使用合成数据与 loopback fixture，不调用真实供应商。

## GitHub 与服务器发布

- GitHub 分支：`feature/itinerary-checkup`；代码提交：`5485d789be718b64a756f331a652de1ed5cdd273`，已推送至 `origin`。后续任务状态/验收记录提交单独更新文档。
- 从该提交构建的前端资源已部署至 `http://43.143.125.176:18080/`。首页 HTTP 200；`/api/health` HTTP 200，响应 `{"status":"ok","version":"0.1.0"}`。
- Caddy 静态目录部署前后 inode 均为 `65025:1091679`。旧产物备份：`/opt/travel-assistant/backups/frontend-before-itinerary-checkup-5485d78/frontend-dist.tar.gz`，SHA-256 `b1cd1d8155ba4c766e24201d16b7e3924e9b7d356884b38c35855e580d72f0ca`。
- 线上 HTML 引用 JS SHA-256 `08cc5db0284490a7e76888bb7e1ec18b77979485bd97fde9d122135cc9266841`、CSS SHA-256 `f510ba8bdbc02a0c4ca34af2d1b4b6471a9af8780508c9754db0341d851f1113`，均与本地提交构建产物及 HTTP 下载字节一致。
- HTTP 页面 `window.isSecureContext === false`；登录控件保持禁用并回退游客模式。未增加凭据、放宽登录门禁、修改后端环境变量或代理配置。API 服务未因本次部署重启；仅替换静态文件。

## 边界

0–100 分仅表示已提供输入下的产品规则归一化结果，不代表医学、路线安全结论或真实供应商核实。服务器目前使用 HTTP；本次不得放宽凭据登录安全门禁或更改服务器密钥/环境配置。
