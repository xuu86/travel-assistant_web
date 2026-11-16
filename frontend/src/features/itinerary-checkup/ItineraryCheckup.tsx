import { useContext, useMemo } from "react";
import { WorkspaceStoreContext } from "../local-storage/workspace-context";
import { useUnknownLedger } from "../unknown-ledger/context";
import type { LedgerItem } from "../unknown-ledger/model";
import { calculateBudgetDimension, calculatePhysicalDimension, calculateTimeDimension, calculateUnknownDimension, calculateWeatherDimension, combineCheckupDimensions, rankCheckupSuggestions } from "./checkup";
import type { CheckupItineraryItem, CheckupSuggestion, DimensionResult } from "./checkup";
import type { WeatherPanelState } from "../weather/WeatherPanel";
import { parseYuanToFen } from "../budget/money";
import "./itinerary-checkup.css";

type BudgetCostSnapshot = { id?: string; paid?: string; unpaid?: string };
type ItineraryRecord = CheckupItineraryItem & { note?: string };

function budgetInput(read: <T>(featureId: string) => T | undefined) {
  const total = read<string>("budget.total") ?? "";
  const reserve = read<string>("budget.reserve") ?? "";
  const costs = read<BudgetCostSnapshot[]>("budget.costs") ?? [];
  try {
    return {
      totalBudgetFen: parseYuanToFen(total),
      reserveFen: reserve.trim() ? parseYuanToFen(reserve) : 0,
      costs: costs.map((cost) => {
        const paidFen = parseYuanToFen(cost.paid ?? "");
        const unpaidFen = parseYuanToFen(cost.unpaid ?? "");
        return { id: cost.id, paidFen, unpaidFen, complete: paidFen !== null && unpaidFen !== null };
      }),
    };
  } catch {
    return { totalBudgetFen: null, reserveFen: null, costs: [] };
  }
}

function currentWeather(state: WeatherPanelState) {
  if (state.status !== "success") return { state: "unconfigured" as const, verified: false, coveredRanges: [], days: [] };
  const data = state.data;
  return {
    state: data.state === "live" || data.state === "partial" ? data.state : "demo" as const,
    verified: (data.sources ?? []).some((source) => source.evidence_state === "verified"),
    coveredRanges: (data.coverage?.covered ?? []).map(({ start, end }) => ({ start, end })),
    days: (data.items ?? []).map((day) => ({
      date: day.date, weatherCode: day.weather_code ?? null,
      precipitationPct: day.precipitation_probability_max_pct ?? null,
      temperatureMaxC: day.temperature_max_c ?? null, temperatureMinC: day.temperature_min_c ?? null,
    })),
  };
}

function suggestionRows(items: ItineraryRecord[], unknowns: LedgerItem[], dimensions: DimensionResult[]) {
  const suggestions: CheckupSuggestion[] = [];
  const timed = [...items].sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`));
  for (const item of items) {
    const hasNextItem = timed.some((candidate) => candidate.date === item.date &&
      (candidate.time > item.time || (candidate.time === item.time && candidate.id > item.id)));
    const missing = [
      ...(item.stayMinutes == null ? ["停留分钟"] : []),
      ...(hasNextItem && item.transitMinutes == null ? ["下一段通行分钟"] : []),
      ...(item.environment !== "indoor" && item.environment !== "outdoor" ? ["室内外标签"] : []),
      ...(item.walkKm == null ? ["步行公里"] : []),
      ...(item.stairSteps == null ? ["台阶数"] : []),
      ...(item.transfers == null ? ["换乘次数"] : []),
    ];
    if (missing.length > 0) suggestions.push({
      id: `fields:${item.id}`, title: `${item.date} 可补充体检数据`,
      reason: `${item.title} 尚缺少：${missing.join("、")}。这些值留空时对应维度不打分。`,
      date: item.date, impact: "medium", sourceKey: `itinerary:${item.id}:arrangement`, locked: item.locked,
    });
  }
  for (let index = 1; index < timed.length; index += 1) {
    const previous = timed[index - 1]!;
    const current = timed[index]!;
    if (previous.date !== current.date || previous.stayMinutes == null || previous.transitMinutes == null) continue;
    const end = Number(previous.time.slice(0, 2)) * 60 + Number(previous.time.slice(3, 5)) + previous.stayMinutes + previous.transitMinutes;
    const start = Number(current.time.slice(0, 2)) * 60 + Number(current.time.slice(3, 5));
    if (end > start) suggestions.push({
      id: `overlap:${previous.id}:${current.id}`, title: `${current.date} 存在时段重叠`,
      reason: `${previous.title} 的停留与通行合计超出下一项开始时间；请核对输入。`, date: current.date,
      impact: "high", sourceKey: `itinerary:${previous.id}:arrangement`, locked: previous.locked || current.locked,
    });
  }
  for (const item of items) {
    if (item.environment === "outdoor" && item.stayMinutes != null && item.date) {
      const weather = dimensions.find(({ id }) => id === "weather");
      if (weather?.score !== null && weather?.score !== undefined && weather.score <= 30) suggestions.push({
        id: `weather:${item.id}`, title: `${item.date} 天气风险较高`,
        reason: weather.details.find((detail) => detail.startsWith(item.date)) ?? "当前预报的天气舒适度较低，请核对户外安排。",
        date: item.date, impact: weather.score <= 10 ? "high" : "medium",
        sourceKey: `itinerary:${item.id}:arrangement`, locked: item.locked,
      });
    }
  }
  for (const item of unknowns) suggestions.push({
    id: `unknown:${item.source_key}`, title: `${item.subject}：${item.field}待核实`,
    reason: `${item.impact === "high" ? "高" : item.impact === "medium" ? "中" : "低"}影响待核实项。`,
    date: item.travel_date ?? "9999-12-31", impact: item.impact,
    sourceKey: item.source_key,
    locked: items.find(({ id }) => item.source_key === `itinerary:${id}:arrangement`)?.locked ?? false,
  });
  const budget = dimensions.find(({ id }) => id === "budget");
  if (budget?.score !== null && budget?.score !== undefined && budget.score <= 30) suggestions.push({
    id: "budget:margin", title: "预算余量偏低", reason: budget.details[0] ?? "请核对预算与费用明细。",
    date: "9999-12-31", impact: budget.score === 0 ? "high" : "medium", sourceKey: "budget:budget-total", locked: false,
  });
  return rankCheckupSuggestions(suggestions);
}

function sourceLabel(sourceKey: string): string {
  if (sourceKey === "budget:budget-total") return "预算上限";
  if (sourceKey.startsWith("budget:")) return "预算明细";
  if (sourceKey.startsWith("weather:forecast:")) return `天气预报 ${sourceKey.split(":")[2] ?? ""}`;
  if (sourceKey.startsWith("weather:")) return "待核实天气来源";
  if (sourceKey.startsWith("itinerary:")) return "行程安排";
  return "待核实账本";
}

export function ItineraryCheckup({ items, startDate, weatherState, onFocusSource }: {
  items: ItineraryRecord[];
  startDate: string;
  weatherState: WeatherPanelState;
  onFocusSource: (sourceKey: string) => void;
}) {
  const workspace = useContext(WorkspaceStoreContext);
  const ledger = useUnknownLedger(startDate).view;
  const dimensions = useMemo(() => {
    const budget = budgetInput(workspace.read);
    return [
      calculateTimeDimension(items),
      calculateBudgetDimension(budget),
      calculatePhysicalDimension(items),
      calculateWeatherDimension(items, currentWeather(weatherState)),
      calculateUnknownDimension(ledger.items, ledger.coverage),
    ];
  }, [items, workspace, weatherState, ledger]);
  const score = combineCheckupDimensions(dimensions);
  const suggestions = suggestionRows(items, ledger.items, dimensions);

  return <section className="itinerary-checkup" aria-labelledby="checkup-title">
    <header className="itinerary-checkup__heading">
      <div><p className="itinerary-step">TRIP CHECKUP / L6</p><h2 id="checkup-title">行程体检</h2></div>
      <p role="status">{score === null ? "综合分：数据不足" : `综合分：${score} / 100`}</p>
    </header>
    <p className="itinerary-checkup__note">只读分析 · 分数仅反映当前已提供数据，不代表路线安全或平台核实。</p>
    <div className="itinerary-checkup__dimensions" aria-label="体检维度">
      {dimensions.map((dimension) => <details key={dimension.id} className="itinerary-checkup__dimension">
        <summary><span>{dimension.label}</span><strong>{dimension.score === null ? "数据不足" : `${dimension.score} 分`}</strong></summary>
        {dimension.missing.length > 0 && <p>缺少：{dimension.missing.join("、")}</p>}
        {dimension.details.map((detail) => <p key={detail}>{detail}</p>)}
        <p className="itinerary-checkup__coverage">数据覆盖：{dimension.status === "ready" ? "完整" : `${Math.round(dimension.coverage * 100)}% · 数据不足`}</p>
        {dimension.sourceKeys.length > 0 && <div className="itinerary-checkup__sources"><span>数据来源</span>{dimension.sourceKeys.map((sourceKey) => <button key={sourceKey} type="button" onClick={() => onFocusSource(sourceKey)}>{sourceLabel(sourceKey)}</button>)}</div>}
      </details>)}
    </div>
    <section className="itinerary-checkup__suggestions" aria-labelledby="checkup-suggestions-title">
      <h3 id="checkup-suggestions-title">优先核对</h3>
      {suggestions.length === 0 ? <p>当前没有由已知数据支持的优先核对项。</p> : <ul>{suggestions.map((suggestion) => <li key={suggestion.id}>
        <div><strong>{suggestion.title}</strong><p>{suggestion.reason}{suggestion.locked ? "（关联安排已锁定，体检不会修改）" : ""}</p></div>
        <button type="button" onClick={() => onFocusSource(suggestion.sourceKey)}>查看来源</button>
      </li>)}</ul>}
    </section>
  </section>;
}

