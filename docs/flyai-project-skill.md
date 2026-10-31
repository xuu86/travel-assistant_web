# FlyAI 项目级 Skill

2026-10-31 已将官方 Skill 迁入本仓库的 [`.agents/skills/flyai/SKILL.md`](../.agents/skills/flyai/SKILL.md)，保留上游原始指令、8 份命令参考及许可证。项目级 Skill 为开发代理提供旅行查询操作说明；Web 后端的 Provider 实现仍按[实施计划](../tasks/flyai-train-provider-plan.md)推进。

## 来源与版本

- 官方仓库：[alibaba-flyai/flyai-skill](https://github.com/alibaba-flyai/flyai-skill)。
- 固定提交：`86fe2cc3e25464d0e0bd6a769b27b5f9f3b04128`，源目录 `skills/flyai`。
- Skill 元数据版本：`1.0.15`；此前真实 Key 核验使用的独立 CLI 版本为 `1.0.16`，二者版本号独立。
- 许可证：[上游 LICENSE](../.agents/skills/flyai/LICENSE)。Skill 文档与 CLI 独立管理；后端现已通过固定 CLI 提供铁路查询，不需要 Codex 在线执行 Skill。

## 在 Codex 中使用

在 `D:\传智杯\AI WEB网页开发挑战赛\智能旅游助手` 或其子目录中启动 Codex，下轮可通过 `$flyai` 调用，例如：

```text
使用 $flyai，先阅读 search-train 参考和项目核验记录，说明上海到杭州铁路查询需要的参数。
```

[Codex 官方说明](https://developers.openai.com/codex/skills/)规定，项目 Skill 从当前目录向上至仓库根的 `.agents/skills` 加载。从父目录 `D:\传智杯` 启动时，不会因此自动扫描这个嵌套项目；应将工作目录切换到项目中。若新增 Skill 未出现，重启 Codex 后再查看。

## CLI 与密钥配置

网页后端需要 Node.js 及固定官方 CLI。在项目根目录执行：

```powershell
& .\backend\.venv\Scripts\python.exe .\backend\scripts\setup_flyai.py
```

脚本从 npm 官方 registry 下载固定 1.0.16 包并校验 SHA-512，只写入被 Git 忽略的 `.tools/flyai/`，不执行安装脚本。后端执行前还会校验 bundle SHA-256；禁止直接替换为其他版本。

在 `backend/.env` 中设置：

```dotenv
APP_TRANSPORT_TRAIN_PROVIDER=flyai
FLYAI_API_KEY=your-server-side-key
APP_TRANSPORT_FLYAI_NODE_PATH=node
APP_TRANSPORT_FLYAI_TIMEOUT_SECONDS=45
APP_TRANSPORT_FLYAI_MAX_RESPONSE_BYTES=1048576
```

也支持 `APP_TRANSPORT_FLYAI_API_KEY`，与 `FLYAI_API_KEY` 同时存在时优先使用前者。若 Node 不在后端 PATH，填写其绝对路径。然后从 backend 目录重启 FastAPI 服务：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

网页进入“交通”→“班次与票价”→“铁路 / 高铁”，填写城市/车站和未来日期后查询。无 provider、无 Key、缺 Node 或 CLI 均不会调用供应商；航班和市内路线独立配置。CLI 不按人数报价，余量、金额未知时如实展示。

真实 Key 继续保存在被 Git 忽略的 `backend/.env` 的 `FLYAI_API_KEY` 中。官方 CLI 从进程环境或其独立配置读取 Key，**不会自动加载项目 `backend/.env`**；调用时由受控进程读取该字段，再仅通过子进程环境传入。不要把 Key 填入 Skill、示例、命令行参数或前端，也不要使用 `--debug` 输出请求与响应。

本项目查询使用明确 Key，缺 Key 时停止，不依赖上游试用凭据。日期必须取用户指定的有效出发日，不直接使用上游参考文档中已过期的日期示例。真实查询按已落实的范围执行，无自动重试；只保存脱敏统计。

## 与网页接入的关系

已完成[本地 API 真实核验](acceptance/flyai-train-api-smoke-2026-10-31.json)：10 条方案、13 个分段，全部价格为 null；前端显示“票价未返回”。网页渲染、席别、纯文本提示和官方 HTTPS 详情链接经合成数据测试与桌面/移动 E2E 验证。

后端用无 shell 受控子进程执行官方 bundle，密钥只进环境、地点与日期走 stdin。单次请求、无自动重试、45 秒请求超时、1 MiB 输出上限、最多 2 个并发进程。仅返回通过允许列表的官方 HTTPS 链接；本次真实结果没有链接通过校验，详情入口省略。上游错误只返回稳定状态，不把原始输出放入日志或响应。公网部署及未知票价语义不属于本次验收。
