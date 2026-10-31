# FlyAI 铁路 Provider 实施计划

> 对应[规格 v0.2](../docs/SPEC-flyai-train-provider.md)。2026-10-31 用户批准“后端封装官方 CLI，实现网页铁路查询；未返回的票价显示‘票价未返回’”。已完成实现及本地真实 API 验收。

## 实施清单

- [x] 官方资料核查、字段与用途边界记录，见[契约核查](../docs/flyai-train-contract-review.md)。
- [x] 官方 Skill 按固定提交迁入 `.agents/skills/flyai/`，含参考资料与许可证。
- [x] 固定 `@fly-ai/flyai-cli@1.0.16`；安装脚本校验 npm 包 SHA-512，执行前校验 bundle SHA-256。
- [x] 独立铁路配置 `APP_TRANSPORT_TRAIN_PROVIDER=flyai`，兼容已有 `FLYAI_API_KEY`；默认关闭、不回退到内置试用 Key。
- [x] 无 shell 子进程；地点/日期经 stdin，密钥只经受限环境；官方目标、单次 POST、无重定向、无自动重试。
- [x] 最多 2 个并发进程、45 秒请求及额外 5 秒退出宽限、1 MiB 上游响应和 stdout 上限、64 KiB stderr 上限。
- [x] 铁路类型、首段日期、站点、时间顺序校验；国内无偏移时刻按 Asia/Shanghai 解释；保留中转分段与席别。
- [x] 金额与计价语义未确认时保持 null，网页铁路卡片显示“票价未返回”；人数、余量、可购状态和费用不猜测。
- [x] 来源品牌、查询时间、纯文本平台提示及通过校验的官方 HTTPS 详情链接；不执行 HTML、不在应用内购票。
- [x] runtime 按 mode 分流；铁路失败不调用航班，未配置模式返回 unconfigured。
- [x] 后端、前端、桌面/移动交通 E2E、类型生成、Lint、构建与密钥检查，详见[验收记录](../docs/acceptance/transport.md)。
- [x] 既有真实 Key 独立 CLI 诊断通过（1 次、0 重试）；新增后端 API 链路真实查询通过（另 1 次、0 重试），仅保存脱敏摘要。

## 真实验收范围

本地开发环境，上海→杭州，2026-11-01。后端 API → runtime → 固定 CLI → FlyAI 返回 10 条方案、13 个分段，13 段均含席别；10 条金额均为 null，响应 state 为 partial。该批次没有链接通过 HTTPS 官方域名校验，网页省略外部详情入口。网页展示与状态流另经合成数据 E2E 验证，不自动重复真实查询。

[API 脱敏证据](../docs/acceptance/flyai-train-api-smoke-2026-10-31.json)与[首次 CLI 证据](../docs/acceptance/flyai-train-live-smoke-2026-10-31.json)分别留存。

## 部署与使用

按照[项目配置说明](../docs/flyai-project-skill.md)安装固定 CLI，在后端配置 provider 和密钥，重启后端。网页进入交通→班次与票价→铁路/高铁，填写明确地点与未来日期后查询。Key 不进入浏览器，未配置不调用网络。

## 保留边界

v0.1 原先要求稳定独立 HTTP/SDK，因资料缺口停止；v0.2 经用户批准采用官方 CLI，该前置依赖已被替代。历史核查保留于[契约记录](../docs/flyai-train-contract-review.md)，不作为重复请求授权的依据。

票价、余票、儿童规则、账户全部权限/配额、缓存期限及公网用途未因此获全面验证；当前不做缓存、不自动重试、不接入 12306 内部接口、不发布公网服务。CLI 升级需重新固定完整性、核查输出和回归。异常或不支持的响应返回明确状态，不生成补充数据。
