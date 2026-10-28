# Weather Provider Gate 0 记录

> 记录日期：2026-10-27（北京时间）  
> 任务：WTH-00  主题：Open-Meteo 候选供应商用途、额度、能力与五城覆盖  
> 结论：**Gate 0 未通过；保持 mock-only。** 本记录没有发起实时 API 请求，没有使用 API Key，也没有把文档能力写成真实覆盖证据。

## 1. 官方资料核对

| 项目 | 当前官方资料摘要 | 对本项目的结论 |
|---|---|---|
| Forecast horizon | Forecast API 文档说明默认 7 天，最多可请求 16 天；指定 daily 变量时需要提供 `timezone`。 | 可作为天气模块候选接口能力；不等于五城实际覆盖已验证。 |
| Free API 用途 | Free API 仅限非商业使用；Terms 将教育内容列为可能的非商业用途示例，同时将商业产品／宣传活动列为商业用途。 | 本项目的比赛展示、公开展示、未来部署和商业推广边界尚未由项目负责人确认；因此不启用 live provider。 |
| Free API 限额 | Terms／Pricing 当前列出 600 次／分钟、5,000 次／小时、低于 10,000 次／日，以及 300,000 次／月；超限或滥用可能被限制。 | 实现前必须保留调用预算、429 状态和不自动付费／切换规则。 |
| 调用计数 | Pricing FAQ 说明，超过 10 个变量或超过两周的单地点请求可能按多个 API call units 计数。 | 16 日上限和不自动拆批仍需在服务中测试；真实额度尚未实测。 |
| 数据许可 | Open-Meteo 说明天气数据使用 CC BY 4.0，需要适当署名并说明修改；数据服务不保证无错误或持续可用。 | UI 若未来使用该数据，必须保留 attribution；当前不对许可适用性作法律判断。 |
| 坐标／响应 | Forecast API 接受 WGS84 latitude／longitude；provider 可能返回解析后的网格位置。 | 需要保留请求城市锚点和 provider resolved location，不能称为气象站实测。 |

官方来源（均于 2026-10-27 查阅）：

- https://open-meteo.com/en/docs
- https://open-meteo.com/en/terms
- https://open-meteo.com/en/pricing
- https://open-meteo.com/en/licence

## 2. 五城与目标日期覆盖

| 城市 | registry ID | 实时请求 | 覆盖结论 |
|---|---|---:|---|
| 上海 | `shanghai` | 未执行 | 未验证 |
| 苏州 | `suzhou` | 未执行 | 未验证 |
| 无锡 | `wuxi` | 未执行 | 未验证 |
| 嘉兴 | `jiaxing` | 未执行 | 未验证 |
| 杭州 | `hangzhou` | 未执行 | 未验证 |

没有执行真实天气请求，因此没有实际响应日期、网格坐标、高程、变量缺失或配额消耗证据。后续如获明确 live-test 授权，须另建脱敏覆盖矩阵，逐城记录请求日期、实际返回日期、缺失日期、变量可用性、provider 坐标、取数时间和状态。

## 3. Gate 决定

- `WTH-00`：**记录完成，但 Gate 结果为未通过／待项目负责人确认**。
- `WTH-10` Open-Meteo adapter：**blocked**，不得实施或启用。
- `WTH-11` 真实覆盖烟雾测试：**blocked**，需要新的明确 live-test 授权。
- `WTH-01` 至 `WTH-09`：可以继续做禁网的契约、fixture、fake provider、API 状态和前端降级流程；这些结果只能证明流程行为，不能证明真实天气能力。

## 4. 证据边界

本记录只保存公开资料摘要和“未执行实时请求”的状态，不保存 Key、真实请求 URL、个人数据、真实位置轨迹或原始 provider payload。官方条款可能更新；在任何真实接入前必须重新查看并更新本记录。
