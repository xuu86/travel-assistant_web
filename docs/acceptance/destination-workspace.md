# destination-workspace 验收记录

> 状态：通过（2026-10-28）；本文件记录工作区 UI 与本机 mock 验收，不代表天气／交通真实 provider 已接通。

## 范围

- 目的地入口仅接受 foundation 注册的上海、苏州、无锡、嘉兴、杭州及对应稳定 ID。
- setup 不加载预算、天气或交通视图，也不发模块请求；确认后才开放工具导航。
- 工具切换保留页面内面板状态；目的地切换取消不改状态，确认后重建工作区；刷新回到 setup。
- 用户可从工作区通过“返回选择城市”回到 setup；先确认清理影响，取消保留草稿，确认后不刷新页面并清空目的地和模块状态。
- Weather 沿用现有天气 API 与日期规则；Budget 目的地只作展示；Transport 目的地仅用于可编辑的终点初值。

## 验收证据

- 注册表人工核对：`backend/app/core/cities.py` 的五个稳定 ID/name 与前端选项一致；setup 阶段没有 registry 或模块请求。
- 单元测试：Vitest 7 个测试文件、53 项通过；App 入口、慢天气响应及返回城市流程 15 项通过。
- 静态与构建：TypeScript typecheck、ESLint、Vite production build、Secretlint 均通过。
- 浏览器：核心实现全量 Playwright 24 项通过，覆盖 desktop Chromium 与 Pixel 7；destination-workspace 专项在返回城市交互加入后 2 项通过，固定 375px 宽度并验证无水平溢出。
- 后端回归：pytest 191 项通过；Ruff 检查通过。后端与 OpenAPI 未修改。
- 本机 Windows 环境未提供 `npm.cmd`；前端脚本由本地 `node_modules` 中的 Vitest、TypeScript、ESLint、Vite、Playwright 和 Secretlint CLI 直接运行。

## 明确未验证

- 本地 fixture／mock 不构成真实天气、班次、票价或导航服务验证。
- 不验证城市之外的地理编码、精确位置、供应商覆盖或生产部署。
- 本能力完成不等于 Web 首版整体完成。
