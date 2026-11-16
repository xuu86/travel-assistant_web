import type { OptionalCheckupFields } from "./types";

export type CheckupItineraryItem = Pick<OptionalCheckupFields,
  "stayMinutes" | "transitMinutes" | "walkKm" | "stairSteps" | "transfers" | "environment"> & {
  id: string;
  date: string;
  time: string;
  title: string;
  locked: boolean;
};

export type CheckupBudgetInput = {
  totalBudgetFen: number | null;
  reserveFen: number | null;
  costs: { id?: string; paidFen: number | null; unpaidFen: number | null; complete: boolean }[];
};

export type CheckupWeatherInput = {
  state: "live" | "partial" | "unavailable" | "demo" | "unconfigured";
  verified: boolean;
  coveredRanges: { start: string; end: string }[];
  days: {
    date: string;
    weatherCode: number | null;
    precipitationPct: number | null;
    temperatureMaxC: number | null;
    temperatureMinC: number | null;
  }[];
};

export type DimensionResult = {
  id: "time" | "budget" | "physical" | "weather" | "unknown";
  label: string;
  score: number | null;
  status: "ready" | "insufficient";
  coverage: number;
  missing: string[];
  details: string[];
  sourceKeys: string[];
};

const timePattern = /^(?:[01]\d|2[0-3]):[0-5]\d$/;

function clamp(value: number, low = 0, high = 1): number {
  return Math.max(low, Math.min(high, value));
}

function scoreAtThirtyPercent(ratio: number): number {
  return Math.round(clamp(ratio / 0.3) * 100);
}

function insufficient(id: DimensionResult["id"], label: string, missing: string[], sourceKeys: string[] = []): DimensionResult {
  return {
    id, label, score: null, status: "insufficient", coverage: 0,
    missing: [...new Set(missing)], details: [], sourceKeys,
  };
}

export function calculateTimeDimension(items: CheckupItineraryItem[]): DimensionResult {
  const label = "时间宽松度";
  if (items.length === 0) return insufficient("time", label, ["至少一项行程安排"]);

  const byDate = new Map<string, CheckupItineraryItem[]>();
  for (const item of items) byDate.set(item.date, [...(byDate.get(item.date) ?? []), item]);
  const missing: string[] = [];
  const details: string[] = [];
  const dateScores: number[] = [];
  let possibleDays = 0;

  for (const [date, dayItems] of [...byDate.entries()].sort(([left], [right]) => left.localeCompare(right))) {
    const sorted = [...dayItems].sort((left, right) => left.time.localeCompare(right.time) || left.id.localeCompare(right.id));
    const hasValidTimes = sorted.every(({ time }) => timePattern.test(time));
    const hasStays = sorted.every(({ stayMinutes }) => Number.isFinite(stayMinutes) && stayMinutes! >= 0);
    const hasLegs = sorted.slice(0, -1).every(({ transitMinutes }) => Number.isFinite(transitMinutes) && transitMinutes! >= 0);
    if (!hasValidTimes) missing.push(`${date}：开始时间`);
    if (!hasStays) missing.push(`${date}：每项停留分钟`);
    if (!hasLegs) missing.push(`${date}：相邻安排的通行分钟`);
    if (!hasValidTimes || !hasStays || !hasLegs) continue;

    const startMinutes = sorted.map(({ time }) => Number(time.slice(0, 2)) * 60 + Number(time.slice(3, 5)));
    const stays = sorted.map(({ stayMinutes }) => stayMinutes!);
    const legs = sorted.slice(0, -1).map(({ transitMinutes }) => transitMinutes!);
    const plannedSpan = startMinutes[startMinutes.length - 1]! + stays[stays.length - 1]! - startMinutes[0]!;
    if (plannedSpan <= 0) {
      missing.push(`${date}：大于零的计划时长`);
      continue;
    }

    possibleDays += 1;
    const knownActivity = stays.reduce((total, value) => total + value, 0) + legs.reduce((total, value) => total + value, 0);
    const buffer = Math.max(0, plannedSpan - knownActivity);
    const conflicts = sorted.slice(0, -1).some((_, index) => {
      const end = startMinutes[index]! + stays[index]! + legs[index]!;
      return end > startMinutes[index + 1]!;
    });
    const dayScore = scoreAtThirtyPercent(buffer / plannedSpan);
    dateScores.push(dayScore);
    details.push(`${date}：计划 ${plannedSpan} 分钟，已知活动 ${knownActivity} 分钟，公式缓冲 ${buffer} 分钟；${conflicts ? `另有时段重叠，宽松度公式得 ${dayScore} 分` : `宽松度 ${dayScore} 分`}。`);
  }

  if (missing.length > 0 || possibleDays === 0) {
    return { ...insufficient("time", label, missing.length ? missing : ["可计算的日程跨度"]), coverage: byDate.size ? possibleDays / byDate.size : 0, details };
  }
  return {
    id: "time", label, score: Math.min(...dateScores), status: "ready", coverage: 1,
    missing: [], details, sourceKeys: items.map(({ id }) => `itinerary:${id}:time`).sort(),
  };
}

export function calculateBudgetDimension(input: CheckupBudgetInput): DimensionResult {
  const label = "预算余量";
  const missing: string[] = [];
  if (!Number.isSafeInteger(input.totalBudgetFen) || input.totalBudgetFen === null || input.totalBudgetFen <= 0) {
    missing.push("大于零的总预算");
  }
  if (input.costs.length === 0) missing.push("完整费用明细");
  for (const cost of input.costs) {
    if (!cost.complete || !Number.isSafeInteger(cost.paidFen) || cost.paidFen === null ||
        !Number.isSafeInteger(cost.unpaidFen) || cost.unpaidFen === null) {
      missing.push("每项已支付与待支付金额");
      break;
    }
  }
  if (input.reserveFen !== null && (!Number.isSafeInteger(input.reserveFen) || input.reserveFen < 0)) {
    missing.push("有效的用户预留金额");
  }
  if (missing.length > 0) return insufficient("budget", label, missing);

  const totalBudget = input.totalBudgetFen!;
  const costsTotal = input.costs.reduce((total, cost) => total + cost.paidFen! + cost.unpaidFen!, 0);
  const plannedSpend = costsTotal + (input.reserveFen ?? 0);
  const marginRate = (totalBudget - plannedSpend) / totalBudget;
  const score = scoreAtThirtyPercent(marginRate);
  return {
    id: "budget", label, score, status: "ready", coverage: 1, missing: [],
    details: [`计划支出 ${plannedSpend} 分，预算 ${totalBudget} 分，余量率 ${Math.round(marginRate * 100)}%；余量率达到 30% 得满分。`],
    sourceKeys: ["budget:budget-total", ...input.costs.flatMap((cost) => cost.id ? [`budget:${cost.id}:paid`, `budget:${cost.id}:unpaid`] : [])],
  };
}

export function calculatePhysicalDimension(items: CheckupItineraryItem[]): DimensionResult {
  const label = "体力舒适度";
  if (items.length === 0) return insufficient("physical", label, ["行程安排"]);
  const byDate = new Map<string, CheckupItineraryItem[]>();
  for (const item of items) byDate.set(item.date, [...(byDate.get(item.date) ?? []), item]);
  const missing: string[] = [];
  const details: string[] = [];
  const scores: number[] = [];

  for (const [date, dayItems] of [...byDate.entries()].sort(([left], [right]) => left.localeCompare(right))) {
    const sorted = [...dayItems].sort((left, right) => left.time.localeCompare(right.time) || left.id.localeCompare(right.id));
    const fields: ("walkKm" | "stairSteps" | "transfers" | "stayMinutes" | "environment")[] = ["walkKm", "stairSteps", "transfers", "stayMinutes", "environment"];
    const absent = fields.filter((field) => {
      const isValid = (value: unknown) => typeof value === "number" && Number.isFinite(value) && value >= 0;
      return sorted.some((item) => field === "environment"
        ? item.environment !== "indoor" && item.environment !== "outdoor"
        : !isValid(item[field]));
    });
    if (absent.length > 0) {
      const fieldLabels: Record<(typeof fields)[number], string> = {
        walkKm: "步行公里", stairSteps: "台阶数", transfers: "换乘次数", stayMinutes: "停留分钟", environment: "室内外标签",
      };
      missing.push(`${date}：${absent.map((field) => fieldLabels[field]).join("、")}`);
      continue;
    }

    const walkKm = sorted.reduce((total, item) => total + item.walkKm!, 0);
    const stairSteps = sorted.reduce((total, item) => total + item.stairSteps!, 0);
    const transfers = sorted.reduce((total, item) => total + item.transfers!, 0);
    let outdoorRun = 0;
    let maxOutdoorRun = 0;
    for (const item of sorted) {
      if (item.environment === "outdoor") {
        outdoorRun += item.stayMinutes!;
        maxOutdoorRun = Math.max(maxOutdoorRun, outdoorRun);
      } else {
        outdoorRun = 0;
      }
    }
    const load = Math.max(walkKm / 10, stairSteps / 100, transfers / 8, maxOutdoorRun / 480);
    const score = Math.round(clamp(1 - load) * 100);
    scores.push(score);
    details.push(`${date}：步行 ${walkKm} 公里、台阶 ${stairSteps} 级、换乘 ${transfers} 次、连续户外 ${maxOutdoorRun} 分钟；舒适度 ${score} 分。`);
  }

  if (missing.length > 0 || scores.length === 0) return { ...insufficient("physical", label, missing.length ? missing : ["可计算的体力数据"]), coverage: byDate.size ? scores.length / byDate.size : 0, details };
  return {
    id: "physical", label, score: Math.min(...scores), status: "ready", coverage: 1,
    missing: [], details, sourceKeys: items.map(({ id }) => `itinerary:${id}:physical`).sort(),
  };
}

function isDateCovered(date: string, ranges: CheckupWeatherInput["coveredRanges"]): boolean {
  return ranges.some((range) => range.start <= date && date <= range.end);
}

export function calculateWeatherDimension(items: CheckupItineraryItem[], weather: CheckupWeatherInput): DimensionResult {
  const label = "天气舒适度";
  if (items.length === 0) return insufficient("weather", label, ["行程安排"]);
  if (!weather.verified || (weather.state !== "live" && weather.state !== "partial")) {
    return insufficient("weather", label, ["当前已核实的非演示天气数据"]);
  }
  const byDate = new Map<string, CheckupItineraryItem[]>();
  for (const item of items) byDate.set(item.date, [...(byDate.get(item.date) ?? []), item]);
  const missing: string[] = [];
  const details: string[] = [];
  const scores: number[] = [];

  for (const [date, dayItems] of [...byDate.entries()].sort(([left], [right]) => left.localeCompare(right))) {
    const daily = weather.days.find((day) => day.date === date);
    if (!isDateCovered(date, weather.coveredRanges) || !daily) {
      missing.push(`${date}：天气日期覆盖`);
      continue;
    }
    const hasOutdoorData = dayItems.every((item) =>
      (item.environment === "indoor" || item.environment === "outdoor") &&
      typeof item.stayMinutes === "number" && Number.isFinite(item.stayMinutes) && item.stayMinutes >= 0,
    );
    if (!hasOutdoorData) missing.push(`${date}：室内外标签与停留分钟`);
    if (daily.weatherCode === null || !Number.isInteger(daily.weatherCode) || daily.precipitationPct === null ||
        daily.temperatureMaxC === null || daily.temperatureMinC === null ||
        ![daily.precipitationPct, daily.temperatureMaxC, daily.temperatureMinC].every(Number.isFinite) ||
        daily.precipitationPct < 0 || daily.precipitationPct > 100) {
      missing.push(`${date}：天气现象、降水概率与温度字段`);
    }
    if (!hasOutdoorData || daily.weatherCode === null || !Number.isInteger(daily.weatherCode) || daily.precipitationPct === null ||
        daily.temperatureMaxC === null || daily.temperatureMinC === null || daily.precipitationPct < 0 || daily.precipitationPct > 100) continue;

    const outdoorMinutes = dayItems.reduce((total, item) =>
      total + (item.environment === "outdoor" ? item.stayMinutes! : 0), 0);
    const rainRiskMinutes = outdoorMinutes * daily.precipitationPct / 100;
    const extremeCode = (daily.weatherCode >= 95 && daily.weatherCode <= 99) ||
      (daily.weatherCode >= 66 && daily.weatherCode <= 67) || daily.weatherCode === 75 || daily.weatherCode === 86;
    const extremeTemperature = daily.temperatureMaxC > 35 || daily.temperatureMinC < -5;
    const risk = extremeCode || extremeTemperature ? 100 : Math.round(clamp(rainRiskMinutes / 60) * 100);
    const score = 100 - risk;
    scores.push(score);
    details.push(`${date}：户外 ${outdoorMinutes} 分钟，按 ${daily.precipitationPct}% 降水概率计算雨险 ${Math.round(rainRiskMinutes)} 分钟；${extremeCode || extremeTemperature ? "达到极端天气阈值" : `天气舒适度 ${score} 分`}。`);
  }

  if (missing.length > 0 || scores.length === 0) return { ...insufficient("weather", label, missing.length ? missing : ["可计算的天气数据"]), coverage: byDate.size ? scores.length / byDate.size : 0, details };
  return {
    id: "weather", label, score: Math.min(...scores), status: "ready", coverage: 1,
    missing: [], details, sourceKeys: [...byDate.keys()].sort().map((date) => `weather:forecast:${date}`),
  };
}

export function calculateUnknownDimension(items: { impact: "high" | "medium" | "low"; source_key: string }[], coverage: string): DimensionResult {
  const label = "待核实项";
  if (coverage !== "complete") return insufficient("unknown", label, ["待核实账本完整扫描"]);
  const penalties = { high: 20, medium: 10, low: 5 } as const;
  const score = Math.max(0, 100 - items.reduce((total, item) => total + penalties[item.impact], 0));
  return {
    id: "unknown", label, score, status: "ready", coverage: 1, missing: [],
    details: [`${items.length} 项待核实：高影响每项扣 20 分、中影响扣 10 分、低影响扣 5 分；到期状态不重复扣分。`],
    sourceKeys: items.map(({ source_key }) => source_key).sort(),
  };
}

export type CheckupSuggestion = {
  id: string;
  title: string;
  reason: string;
  date: string;
  impact: "high" | "medium" | "low";
  sourceKey: string;
  locked: boolean;
};

export function combineCheckupDimensions(dimensions: DimensionResult[]): number | null {
  if (dimensions.length !== 5 || dimensions.some(({ score }) => score === null)) return null;
  return Math.round(dimensions.reduce((total, dimension) => total + dimension.score!, 0) / dimensions.length);
}

export function rankCheckupSuggestions(suggestions: CheckupSuggestion[]): CheckupSuggestion[] {
  const impactRank = { high: 0, medium: 1, low: 2 } as const;
  return [...suggestions].sort((left, right) =>
    Number(!left.id.startsWith("overlap:")) - Number(!right.id.startsWith("overlap:")) ||
    impactRank[left.impact] - impactRank[right.impact] ||
    left.date.localeCompare(right.date) || left.id.localeCompare(right.id),
  ).slice(0, 3);
}
