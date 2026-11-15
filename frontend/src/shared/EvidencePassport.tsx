import { useEffect, useState } from "react";
import type { components } from "./api-contracts";
import "./evidence-passport.css";

type EvidenceState = components["schemas"]["EvidenceState"];
type EvidenceSource = {
  source_id?: string;
  display_name: string;
  url?: string | null;
  retrieved_at?: string | null;
  valid_from?: string | null;
  valid_to?: string | null;
  attribution?: string | null;
  evidence_state: EvidenceState;
};
type DateRange = { start: string; end: string };
type Coverage = { requested?: DateRange | null; covered?: DateRange[]; missing?: DateRange[] } | null;

const EVIDENCE_LABELS: Record<EvidenceState, string> = {
  verified: "已核实",
  unverified: "待核实",
  user_provided: "用户提供",
  estimate: "估算",
  demo: "测试数据",
  unknown: "状态未知",
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间无法识别";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Shanghai",
  }).format(date);
}

function formatRange(range: DateRange | null | undefined): string {
  if (!range) return "未提供";
  return range.start === range.end ? range.start : `${range.start} 至 ${range.end}`;
}

function formatRanges(ranges: DateRange[] | undefined): string {
  if (!ranges?.length) return "未提供";
  return ranges.map(formatRange).join("、");
}

function safeSourceUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

export function EvidencePassport({
  source,
  coverage,
  subject = "这条信息",
}: {
  source: EvidenceSource;
  coverage?: Coverage;
  subject?: string;
}) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(() => setNow(Date.now()), 0);
    return () => window.clearTimeout(timer);
  }, []);
  const sourceUrl = safeSourceUrl(source.url);
  const validTo = source.valid_to ? new Date(source.valid_to) : null;
  const isExpired = now !== null && validTo !== null && !Number.isNaN(validTo.getTime()) && validTo.getTime() < now;
  const isUserProvided = source.evidence_state === "user_provided";

  return (
    <details className={`evidence-passport evidence-passport--${source.evidence_state}`}>
      <summary aria-label={`查看${subject}的信息护照`}>
        <span className="evidence-passport__dot" aria-hidden="true" />
        <span>{EVIDENCE_LABELS[source.evidence_state]} · 信息护照</span>
      </summary>
      <div className="evidence-passport__details">
        <dl>
          <div><dt>来源</dt><dd>{source.display_name}</dd></div>
          {source.source_id && <div><dt>来源标识</dt><dd>{source.source_id}</dd></div>}
          <div><dt>{isUserProvided ? "录入时间" : "取数时间"}</dt><dd>{formatDateTime(source.retrieved_at)}</dd></div>
          <div><dt>建议有效期</dt><dd>
            {source.valid_from || source.valid_to
              ? `${formatDateTime(source.valid_from)} 至 ${formatDateTime(source.valid_to)}${isExpired ? "（已过期）" : ""}`
              : "来源未提供；当前无法判断是否仍有效"}
          </dd></div>
          {coverage && <>
            <div><dt>请求范围</dt><dd>{formatRange(coverage.requested)}</dd></div>
            <div><dt>已覆盖</dt><dd>{formatRanges(coverage.covered)}</dd></div>
            <div><dt>未覆盖</dt><dd>{formatRanges(coverage.missing)}</dd></div>
          </>}
          {source.attribution && <div><dt>说明</dt><dd>{source.attribution}</dd></div>}
        </dl>
        {sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer">打开来源 ↗</a>}
      </div>
    </details>
  );
}

export type { EvidenceSource };
