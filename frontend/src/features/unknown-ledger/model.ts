import type { components } from "../../shared/api-contracts";

export type LedgerModule =
  | "weather"
  | "transport"
  | "hotels"
  | "activities"
  | "attractions"
  | "budget"
  | "itinerary";
export type LedgerImpact = "high" | "medium" | "low";
export type LedgerScanStatus = "complete" | "partial" | "not_loaded" | "unavailable";
export type LedgerCoverage = LedgerScanStatus;
export type ContactStatus = "not_contacted" | "contacted";
export type LedgerObservation = {
  source_key: string;
  module: LedgerModule;
  subject: string;
  field: string;
  evidence_state: components["schemas"]["EvidenceState"];
  impact: LedgerImpact;
  travel_date: string | null;
  retrieved_at: string | null;
};
export type LedgerSourceScan = { module: LedgerModule; status: LedgerScanStatus };
export type LedgerItem = LedgerObservation & {
  reminder_date: string;
  reminder_status: "upcoming" | "due";
  contact_status: ContactStatus;
};
export type LedgerView = {
  items: LedgerItem[];
  coverage: LedgerCoverage;
  emptyState: "items" | "empty" | "scan_required";
  scanned_modules: LedgerModule[];
  incomplete_modules: LedgerModule[];
};

const reminderLeadDays: Record<LedgerImpact, number> = { high: 7, medium: 3, low: 0 };
const impactRank: Record<LedgerImpact, number> = { high: 0, medium: 1, low: 2 };
const moduleOrder: LedgerModule[] = [
  "weather", "transport", "hotels", "activities", "attractions", "budget", "itinerary",
];
const sourceKeyPattern = /^[a-z][a-z0-9.-]{0,39}:[a-zA-Z0-9._:%-]{1,159}$/;
const isoDatePattern = /^\d{4}-\d{2}-\d{2}$/;

function assertDate(value: string, label: string): void {
  if (!isoDatePattern.test(value)) throw new Error(`${label}日期无效。`);
  const parsed = new Date(`${value}T00:00:00.000Z`);
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) {
    throw new Error(`${label}日期无效。`);
  }
}

function addDays(date: string, days: number): string {
  const value = new Date(`${date}T00:00:00.000Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

function validateObservations(observations: LedgerObservation[]): void {
  const keys = new Set<string>();
  for (const observation of observations) {
    if (!sourceKeyPattern.test(observation.source_key)) {
      throw new Error("账本 source_key 格式无效。");
    }
    if (keys.has(observation.source_key)) throw new Error("账本 source_key 重复。");
    keys.add(observation.source_key);
    if (!observation.subject.trim() || observation.subject.length > 200 ||
        !observation.field.trim() || observation.field.length > 120) {
      throw new Error("账本字段标签无效。");
    }
    if (observation.travel_date !== null) assertDate(observation.travel_date, "旅行");
    if (observation.retrieved_at !== null && Number.isNaN(Date.parse(observation.retrieved_at))) {
      throw new Error("账本来源时间无效。");
    }
    if (!(observation.impact in impactRank)) throw new Error("账本影响等级无效。");
  }
}

function getCoverage(scans: LedgerSourceScan[]): LedgerCoverage {
  if (scans.length === 0) return "not_loaded";
  const statuses = scans.map((scan) => scan.status);
  if (statuses.every((status) => status === "unavailable")) return "unavailable";
  if (statuses.every((status) => status === "complete")) return "complete";
  if (statuses.every((status) => status === "not_loaded")) return "not_loaded";
  if (statuses.some((status) => status === "partial" || status === "unavailable" || status === "not_loaded")) {
    return "partial";
  }
  return "complete";
}

function validateScans(scans: LedgerSourceScan[]): void {
  const seen = new Set<LedgerModule>();
  for (const scan of scans) {
    if (seen.has(scan.module)) throw new Error("账本来源扫描状态重复。");
    seen.add(scan.module);
  }
}

export function buildLedgerView(
  observations: LedgerObservation[],
  scans: LedgerSourceScan[],
  departureDate: string,
  today: string,
  contactStatuses: Partial<Record<string, ContactStatus>> = {},
): LedgerView {
  assertDate(departureDate, "出发");
  assertDate(today, "当前");
  validateObservations(observations);
  validateScans(scans);

  const items = observations
    .filter(({ evidence_state }) => evidence_state !== "verified" && evidence_state !== "demo")
    .map((observation): LedgerItem => {
      const reminderDate = addDays(departureDate, -reminderLeadDays[observation.impact]);
      return {
        ...observation,
        reminder_date: reminderDate,
        reminder_status: today >= reminderDate ? "due" : "upcoming",
        contact_status: contactStatuses[observation.source_key] ?? "not_contacted",
      };
    })
    .sort((left, right) => {
      const dateOrder = (left.travel_date ?? "9999-12-31").localeCompare(right.travel_date ?? "9999-12-31");
      if (dateOrder !== 0) return dateOrder;
      const reminderOrder = left.reminder_date.localeCompare(right.reminder_date);
      if (reminderOrder !== 0) return reminderOrder;
      const severityOrder = impactRank[left.impact] - impactRank[right.impact];
      if (severityOrder !== 0) return severityOrder;
      return left.source_key.localeCompare(right.source_key);
    });

  const scanned = new Set(scans.filter(({ status }) => status === "complete" || status === "partial").map(({ module }) => module));
  const incomplete = new Set(scans.filter(({ status }) => status !== "complete").map(({ module }) => module));
  const coverage = getCoverage(scans);

  return {
    items,
    coverage,
    emptyState: items.length > 0 ? "items" : coverage === "complete" ? "empty" : "scan_required",
    scanned_modules: moduleOrder.filter((module) => scanned.has(module)),
    incomplete_modules: moduleOrder.filter((module) => incomplete.has(module)),
  };
}

export function createObservationSourceKey(module: LedgerModule, entityId: string, fieldId: string): string {
  const encode = (value: string) => encodeURIComponent(value)
    .replace(/[!'()*]/g, (character) => `%${character.charCodeAt(0).toString(16).toUpperCase()}`);
  return `${module}:${encode(entityId)}:${encode(fieldId)}`;
}
