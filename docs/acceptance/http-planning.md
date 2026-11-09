# HTTP IP 访问后规划页白屏

核实日期：2026-11-09（北京时间）。修复基线：服务器部署提交 `7c00e93`。

## 线上复现

- 地址：`http://43.143.125.176:18080/`。
- Chromium 实测 `isSecureContext === false`，`typeof crypto.randomUUID === "undefined"`。
- 选择杭州并点击“开始规划”后抛出 `crypto.randomUUID is not a function`，`#root` 文本变为空。
- `/api/health` 返回正常；前端没有在此步骤切换 URL。
- 预算、行程组件在进入工作区时同时挂载（即使视图被 hidden 隐藏），初始化草稿时直接调用该 API，导致整个 React 树卸载。

## 修复

- 共用 `createDraftId()`：支持时使用原生 randomUUID，否则用普通 HTTP 下可用的 getRandomValues 生成 UUID v4。
- 两处草稿初始化均改用共用函数；预算初始状态改用惰性初始化。
- 不增加依赖，保留 UUID 格式及现有预算接口契约。

## 验证

- UUID、预算、行程、App 相关单测：4 个文件、31 项通过。
- 桌面 Chromium 与手机 Chromium 的缺少 randomUUID 回归：2 项通过；覆盖开始规划、新增/删除费用和新增多项行程。
- 两份 TypeScript 配置检查、修改文件 ESLint 检查、生产构建通过。
- 在浏览器中拦截 HTTP IP 页面的静态资源请求，用本地生产构建响应，不修改服务器：实际非安全上下文、randomUUID 不存在时，进入工作区、新增费用、新增行程均成功，pageerror 为零。API 请求使用合成失败响应，避免测试调用真实供应商。

以上为部署前验证记录，不包含线上发布后的验收结果。
