# 未知项账本（L2）验收记录

验收日期：2026-11-16（北京时间）。当前范围为本地浏览器单 owner 工作区中的待核实字段聚合、应用内 T-7/T-3/T-0 提示与来源回跳；不含系统通知、云端存储或自动修改行程。

## 功能验收

- 天气、班次、酒店、活动、景点、预算和行程来源以最小字段摘要注册 observation；未知、未核实、用户提供和估算状态保留原证据等级。
- 行程字段已核实或移除、来源结果更新时，账本随当前来源状态更新；来源未加载、不可用、部分覆盖和完整扫描无候选分别呈现。
- 观察项由当前 owner 的模块状态派生，不独立持久化；“已联系”通过现有 owner 分区 IndexedDB 保存，但不会关闭候选。登出后重新登录可恢复来源工作区与联系状态。
- 提醒节点按 `Asia/Shanghai` 日历日计算，高/中/低影响依次使用 T-7/T-3/T-0；候选按旅行日、提醒日、影响等级及稳定键排序。
- “前往复核”切换到来源模块，并按 `source_key` 定位、滚动和聚焦对应条目；目标不可用时仍进入所属来源模块。桌面和 375px 手机视口无横向溢出。
- IndexedDB ledger contact snapshot 不含来源查询文本、订单/OCR 全文、POI 地址或凭据；临时天气/交通/地点查询在刷新后不会冒充仍有效。

## 自动化验证

- 前端 Vitest：25 个文件、139 tests passed。
- TypeScript：应用与 E2E 两份 tsconfig 检查通过。
- ESLint：通过。
- Vite production build：通过；产物含内容哈希 CSS/JS。
- Playwright：桌面 Chromium 与手机 Chromium 全量 54/54 通过；新增账本流程覆盖回源聚焦、已联系仍待核实、登出重登恢复及移动端溢出。
- Secretlint：通过。
- 后端：pytest 428 passed，Ruff 全项通过；仅有现存 Starlette/httpx 弃用提示。L2 未修改后端。

Playwright 仅访问本机 Vite 与 loopback 测试 fixture；未调用真实天气、交通、地图或账号供应商。Chrome 由本机安装路径启动。生产构建来自 GitHub 提交 `7c492c196352f05bd61cfcf1d251fab0bda13bf5`，已推送到 `feature/unknown-ledger` 并部署至 `http://43.143.125.176:18080/`。

线上验收：首页 HTTP 200；`/api/health` HTTP 200，响应 `{"status":"ok","version":"0.1.0"}`。线上 JS SHA-256 `2c5985191ec29ed776c600c31415d840a5231a35b3ba2abea42b411258d2376c`、CSS SHA-256 `6bb8c913ac43dabe30a60559863f7faaa3725c1fd8da08421e4a405c2df8870c`，均与提交构建产物一致。Caddy 静态目录部署前后 inode 均为 `65025:1091679`；旧静态产物备份在服务器 `/opt/travel-assistant/backups/frontend-before-unknown-ledger-7c492c1/frontend-dist.tar.gz`（SHA-256 `c4be5e382b6378563edc13871651bd92cab4dd961e75ef9e36d1b788ba79bc37`）。API 服务仍为 active，未更改 backend environment、Caddy 配置或服务单元。

真实 HTTP 页面检查显示 `window.isSecureContext === false`，登录控件保持禁用（两个登录按钮均 `disabled=true`），只以游客身份运行；没有为 HTTP 发布放宽凭据提交安全门。

## 发布限制

服务器现有入口为 `http://43.143.125.176:18080/`。HTTP 非安全上下文会按认证安全门禁禁用凭据提交；本次仅计划部署静态/后端代码，不放宽此门禁、不添加账号凭据、不更换服务器环境配置。该入口不构成 HTTPS 生产认证或公开服务验收。
