# 智能旅游助手 Web

本项目工作区位于 `AI WEB网页开发挑战赛/智能旅游助手`，与 `D:\传智杯\travel-assistant` 中的旧草稿分开。后续经审批的应用代码只放在本目录内。

## 项目基线

- PC 与手机浏览器响应式 Web，面向中国大陆单城市旅行规划；试点城市为上海、苏州、无锡、嘉兴、杭州。
- 前端：React + TypeScript + Vite；后端：Python + FastAPI、Pydantic；模块化单体。
- 首版范围、数据真实性要求、隐私和安全规则以现行开发手册、决策台账和验收矩阵为准。

## 当前阶段

- Capability Map 已于 2026-10-27 确认：[Web Capability Map](Web-Capability-Map.md)。
- `foundation`、`weather` 和 `budget` 的本地流程验收记录已完成，见 [foundation](docs/acceptance/foundation.md)、[weather](docs/acceptance/weather.md)、[budget](docs/acceptance/budget.md)。
- `transport` fake-only 流程已按批准的 SPEC、计划和任务清单完成：[SPEC](docs/SPEC-transport.md)、[实施计划](tasks/transport/plan.md)、[任务清单](tasks/transport/todo.md)、[验收记录](docs/acceptance/transport.md)。已实现条件 Amadeus 航班 adapter 和 FlyAI 官方 CLI 铁路 provider；铁路本地真实 API 查询已通过，缺价显示“票价未返回”。航班真实数据、市内路线及铁路确定票价仍未验证。
- `assistant` 模块已有离线/fake 流程和 OpenAI-compatible provider adapter：[SPEC](docs/SPEC-assistant.md)、[实施记录](docs/acceptance/assistant.md)。真实模型供应商、资格、价格、隐私条款、额度和质量仍待 E-007 核验；不配置密钥时接口返回 `unconfigured`。
- `itinerary` 当前是前端内存中的手工草稿，不是服务端行程 API；刷新后不保留，也没有账号、owner scope 或跨设备同步。
- 以上只表示对应模块的契约、交互或测试流程状态；不代表真实数据能力已验证，也不代表 Web 首版整体完成。其他首版模块仍须各自过规格、实现和验收门禁。
- 当前可本机演示，尚无公网生产部署方案。公网发布门槛和 API 申请/配置清单见[生产上线准备清单](docs/production-launch-readiness.md)。
- 不复制旧目录内未经验证的后端草稿作为本项目实现。

## 参考文档

- 项目级 FlyAI Skill 已放入 `.agents/skills/flyai/`，在本项目目录启动 Codex 后可用 `$flyai`；来源、CLI 和密钥配置见[使用说明](docs/flyai-project-skill.md)。Web 铁路已通过后端封装固定官方 CLI 接入并完成本地真实 API 查询验收；安装、配置及重启步骤见使用说明。

现行基线和验收文档位于旧项目文档目录，作为只读参考：

- [开发手册](../../travel-assistant/docs/开发手册.md)
- [决策与待办台账](../../travel-assistant/docs/决策与待办台账.md)
- [Web 验收矩阵](../../travel-assistant/docs/Web验收矩阵.md)
- [模块规格模板](../../travel-assistant/docs/模块规格模板.md)
- [本地开发与安全操作手册](../../travel-assistant/docs/本地开发与安全操作手册.md)
- [GitHub 使用方法总结](../GitHub使用方法总结.md)

旧项目上下文和未验证后端草稿保留在原位置；本工作区不修改它们，也不将其视为已验收实现。

