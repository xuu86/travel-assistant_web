# Foundation 验收记录

> 日期：2026-10-27（北京时间）  
> 范围：Capability Map 中的 `foundation`；不代表其他 capability 或 Web 首版整体完成。

## 结论

**Foundation 阶段实现通过本地自动化验收。** 共享契约、北京时间工具、五城注册表、配置校验、请求 ID、统一公共错误、OpenAPI 导出与 TypeScript 类型生成已落地。

真实天气、交通、酒店、活动、景点、模型、OCR、地图／路线和用户行程尚未接入；未进行真实供应商调用、局域网手机上传或公网部署。本记录不将 fixture、城市注册表或本地占位页表述为真实旅行数据能力完成。

## 环境与锁定版本

- OS：Windows 11 x64。
- Python：CPython 3.14.10；uv 0.12.13。
- 后端依赖由 `backend/pyproject.toml` 与 `backend/uv.lock` 锁定；实装包含 FastAPI、Pydantic、`pydantic-settings`、`python-dotenv`、`tzdata`、pytest、httpx、Ruff。
- Node.js：24.22.1；npm：11.19.1。前端依赖由 `frontend/package.json` 与 `frontend/package-lock.json` 精确锁定。
- 工具运行时安装在用户本机独立目录；未覆盖系统 Python／Node，也未修改全局 PATH。
- `.env.example` 只含空白模型配置模板；没有真实服务端 Key、用户凭证、旅行原件或行程数据。

## 自动化验证结果

| 验证 | 结果 | 说明 |
|---|---|---|
| `uv run pytest -q` | 通过 | 63 passed；Starlette `TestClient` 与当前 httpx 兼容路径发出 1 条弃用提示，未导致失败 |
| `uv run ruff check .` | 通过 | 全后端检查无错误 |
| `uv lock --check` / `uv sync --locked` | 通过 | 锁文件可解析且环境可按锁同步 |
| `npm ci --ignore-scripts --dry-run --no-audit --no-fund` | 通过 | 前端锁文件安装预演成功 |
| `npm run lint` | 通过 | ESLint 无错误 |
| `npm run test:unit -- --run` | 通过 | 2 passed |
| `npm run typecheck` | 通过 | TypeScript 无错误 |
| `npm run build` | 通过 | Vite 8.3.5 生产构建成功 |
| `npm run test:e2e` | 通过 | Playwright 桌面与移动 Chromium 各 1 项，共 2 passed；仅访问 loopback 测试服务器 |
| Secretlint 工作区扫描 | 通过 | 启用 recommended rules preset；扫描源码／文档工作区无发现 |
| Secretlint 构建产物扫描 | 通过 | 使用 `--no-gitignore` 扫描 `dist`，无发现 |
| OpenAPI／TypeScript 稳定性 | 通过 | 重复导出与生成哈希一致；OpenAPI 3.1.0 包含 `CityRecord`、`PublicError`，city 列表与详情错误响应指向公共错误契约 |

## 本模块安全与契约检查

- 业务日用 `Asia/Shanghai`；固定时钟测试覆盖 UTC 日期边界和闰日；日期-only 保持日历日期语义，无时区 datetime 被拒绝。
- 金额以整数分表达；`null`（未知）与 `0`（明确为零）分别测试。
- 城市注册表包含上海、苏州、无锡、嘉兴、杭州，坐标标为 WGS84 并保留来源 ID、核实时间与记录类型；这些点是官方 gazetteer 的行政驻地地图锚点，不声称是行政区边界质心，也不表示旅游供应商覆盖。
- 配置拒绝通配符 CORS、路径／query／fragment、凭证及非规范 Origin；production 配置只允许 HTTPS origins。服务端 API Key 使用 SecretStr；非法配置、异常响应和请求日志不回显测试秘密。
- 每个 HTTP 响应提供随机 UUID `X-Request-ID`；公共错误体 ID 与响应头一致。统一处理校验、业务、HTTP 与意外异常；日志仅含 request ID、路由名、状态和耗时，不记录异常消息或堆栈。
- 未允许来源的浏览器请求不会收到 CORS allow-origin；CORS 只限定浏览器跨域读取，不替代会话、身份授权或上传配对。

## 验收矩阵映射

| AC | Foundation 子项结果 | 全局状态与未完成边界 |
|---|---|---|
| AC-01 五城与北京时间 | foundation 子项通过：城市稳定 ID、WGS84 注册表、北京时间跨日测试均通过 | **全局部分通过／未完成**：前端城市选择与真实覆盖缺失状态尚未实现 |
| AC-06 天气部分覆盖 | 公共 Coverage 契约支持请求、覆盖与缺失区间 | **全局阻塞／未验证**：天气供应商、实际覆盖和 UI 尚未实现；无旧数据补齐的供应商级证据 |
| AC-25 免费边界 | `unconfigured`、`rate_limited`、`policy_unavailable` 等状态有独立公共语义；缺配置映射已测试 | **全局部分通过**：真实 provider 额度、政策、免费状态未核实，且无供应商适配 |
| AC-28 部分故障与并发 | request ID、公共错误、安全异常边界通过 | **全局部分通过／未完成**：多 provider 并行、独立故障隔离及重复 patch 并发尚未实现 |
| AC-36 Key 与敏感日志 | fake-secret 单测、日志断言、源码工作区与构建产物 Secretlint 扫描通过 | **Foundation 子项通过**；后续接入 provider／真实本地配置时必须重跑完整构建、响应和日志扫描 |

## 未覆盖／后续门禁

- 各 provider SPEC、真实数据覆盖与来源／授权核实。
- auth／owner scope、手机配对授权、文件上传／OCR／临时文件清理。
- budget、itinerary、assistant、local-storage、maps、exports 的独立 SPEC、计划与任务审批。
- GitHub 私有仓库、提交历史扫描、实际局域网真机验收、部署。
- `httpx` 测试客户端兼容路径的 Starlette 弃用提示后续升级时需重新评估；本轮不静默引入新的测试 HTTP 依赖。

## 证据与复现入口

- 自动化代码：`backend/tests/unit/`、`backend/tests/integration/`、`frontend/src/App.test.tsx`、`frontend/e2e/smoke.spec.ts`。
- API 契约：`frontend/src/shared/openapi.json`、`frontend/src/shared/api-contracts.ts`。
- 锁文件：`backend/uv.lock`、`frontend/package-lock.json`。
- 所有测试使用本地 fixture／合成数据；无真实密钥或旅行原件进入证据。
