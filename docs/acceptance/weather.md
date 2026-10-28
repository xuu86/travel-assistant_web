# 天气模块验收记录

> 日期：2026-10-27（北京时间）  
> 范围：WTH-00 至 WTH-09、WTH-12 的 mock-only 阶段；不代表真实天气供应商已接入。

## 结论

**天气模块的契约、后端服务/API、前端状态流、响应式界面和 mock-only 自动化验收通过。** Open-Meteo Gate 0 尚未通过；没有发出实时天气请求、使用 API Key、验证五城真实覆盖或对供应商许可作法律判断。WTH-10/WTH-11 仍为 blocked。页面初始状态保持“天气服务尚未配置”，只有用户提交查询才会请求同源 `/api/weather/forecast`；demo 结果只存在于明确标记的测试 fixture 中。

## 范围与证据

| 任务 | 结果 | 证据／边界 |
|---|---|---|
| WTH-00 | 记录完成；Gate 0 未通过 | [`weather-provider-gate.md`](../weather-provider-gate.md)：未做实时请求；用途资格、额度实测、五城覆盖待确认 |
| WTH-01 至 WTH-05 | 通过 | 契约、fake provider、覆盖归一化、缓存／有限重试和 API 测试均通过 |
| WTH-06 至 WTH-07 | 通过 | OpenAPI 3.1 与 TypeScript 类型稳定；前端同源 API client 状态测试通过 |
| WTH-08 | 通过 | 城市／日期查询表单、逐日卡片、缺失日期、来源和取数时间、未知值与状态降级均有测试；默认未配置，无自动请求 |
| WTH-09 | 通过 | Playwright 共 10 项通过：桌面与移动 Chromium；完整 fixture、部分覆盖、未配置、失败、旧结果清除、375px、横屏和 reduced-motion；weather endpoint 仅 mock |
| WTH-10 / WTH-11 | **Blocked** | 不编写／启用 Open-Meteo adapter，不做真实覆盖烟雾测试，除非各自门禁获批 |
| WTH-12 | 通过（mock-only 范围） | 下列回归结果和 AC 子项结论 |

### 自动化回归（2026-10-27）

- `backend/`：`uv run pytest -q` → **98 passed**；有 1 条 Starlette `TestClient` / httpx deprecation warning，不影响结果。
- `backend/`：`uv run ruff check .` → **通过**；`uv lock --check` → **通过**。
- `frontend/`：ESLint → **通过**；`tsc --noEmit` → **通过**；Vitest → **17 passed（3 个测试文件）**；Vite production build → **通过**。
- `frontend/`：Playwright → **10 passed**（桌面与移动 Chromium 共 2 个 project）。所有天气响应均由 route mock 提供；初始页面未发请求。
- OpenAPI 导出重复生成 SHA-256 稳定；`api-contracts.ts` 重复生成 SHA-256：`90ED5F696344C14387AA984021018223966C734CE7743EA7C26D6769812112AD`。
- Secretlint recommended preset：工作区扫描与 `dist` 构建产物扫描均**通过，无发现**。
- 375px 手机、桌面和横屏视口未发现水平溢出；reduced-motion 下加载动画关闭。桌面与手机页面已作视觉检查。

## AC 分项映射

| AC | 天气子项结论 | 全局边界 |
|---|---|---|
| AC-01 | **流程通过**：注册城市选择、Asia/Shanghai 日期输入和日期范围展示已接入；仅接受 registry ID。 | 不表示上海、苏州、无锡、嘉兴、杭州已有任何真实天气覆盖证据。 |
| AC-03 | **边界通过**：weather 只输出逐日天气、来源与覆盖，不生成活动推荐、不替用户重排行程。 | 推荐能力／天气影响规则须由 recommendations／itinerary 各自规格验收。 |
| AC-06 | **fixture 流程通过**：完整及 partial 日期段可见；缺失日期明确显示；null 保持“暂无”；改变查询条件会清除先前结果。 | provider 对目标城市／未来日期的真实可用范围仍未验证。 |
| AC-25 | **状态流程通过**：unconfigured、rate_limited、policy_unavailable、unavailable/no_coverage 与请求失败分开展示；无付费回退或 demo fallback。 | 实际供应商额度、政策资格、真实限流行为未验证；Gate 0 未通过。 |

## 可复现入口

- 任务清单：[`tasks/weather/todo.md`](../../tasks/weather/todo.md)
- 批准规格：[`SPEC-weather.md`](../SPEC-weather.md)
- Gate 0 证据：[`weather-provider-gate.md`](../weather-provider-gate.md)
- 后端：`backend/app/modules/weather/`、`backend/tests/unit/test_weather_*.py`、`backend/tests/integration/test_weather_api.py`
- 前端：`frontend/src/features/weather/`、`frontend/src/App.test.tsx`、`frontend/e2e/weather.spec.ts`
- 合同：`frontend/src/shared/openapi.json`、`frontend/src/shared/api-contracts.ts`

## 未验收与继续条件

1. **真实天气数据：未接入／未验证。** 本记录中的示例数据仅为 `demo` fixture，不可用于宣称实时天气或供应商覆盖。
2. WTH-10 只有在用途许可、额度及接入条件由项目负责人另行确认并批准后才可解锁；本记录不构成授权。
3. WTH-11 需要单独明确授权，限定 provider、城市、日期、请求次数和证据留存后方可执行。
4. 如项目展示或部署用途变化，须重新检查 provider 许可、署名与额度条件并更新 Gate 记录。

