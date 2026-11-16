import { useUnknownLedger } from "./context";
import type { LedgerModule } from "./model";
import "./unknown-ledger.css";

const moduleLabels: Record<LedgerModule, string> = {
  weather: "天气",
  transport: "交通班次",
  hotels: "酒店",
  activities: "活动",
  attractions: "景点",
  budget: "预算",
  itinerary: "行程",
};
const evidenceLabels = {
  verified: "已核实",
  unverified: "待核实",
  user_provided: "用户提供",
  estimate: "估算",
  demo: "测试数据",
  unknown: "状态未知",
} as const;
const impactLabels = { high: "高影响", medium: "中影响", low: "低影响" } as const;

function coverageLabel(coverage: string): string {
  if (coverage === "complete") return "当前已加载来源扫描完成";
  if (coverage === "not_loaded") return "来源尚未加载，暂不能确认待核实项是否完整";
  if (coverage === "unavailable") return "来源暂不可用，暂不能确认待核实项是否完整";
  return "部分来源未完整扫描，清单可能不完整";
}

function tripDateLabel(date: string | null): string {
  return date ?? "旅行日期待确认";
}

export function UnknownLedgerPanel({ departureDate, onOpenSource }: {
  departureDate: string;
  onOpenSource: (module: LedgerModule, sourceKey: string) => void;
}) {
  const { view, setContactStatus } = useUnknownLedger(departureDate);
  const grouped = new Map<string, typeof view.items>();
  for (const item of view.items) {
    const key = tripDateLabel(item.travel_date);
    grouped.set(key, [...(grouped.get(key) ?? []), item]);
  }

  return <section className="unknown-ledger" aria-labelledby="unknown-ledger-title">
    <header className="unknown-ledger__heading">
      <div>
        <p className="unknown-ledger__eyebrow">TRIP REVIEW / L2</p>
        <h1 id="unknown-ledger-title">待核实账本</h1>
        <p>未核实的信息保留原状态，不会补成已知事实。</p>
      </div>
      <span className={`unknown-ledger__coverage unknown-ledger__coverage--${view.coverage}`} role="status">
        {coverageLabel(view.coverage)}
      </span>
    </header>

    {view.incomplete_modules.length > 0 && <p className="unknown-ledger__sources" role="note">
      尚未完整扫描：{view.incomplete_modules.map((module) => moduleLabels[module]).join("、")}
    </p>}

    {view.emptyState === "scan_required" ? (
      <p className="unknown-ledger__empty" role="status">来源尚未全部就绪；请稍后查看，当前不能确认没有待核实项。</p>
    ) : view.emptyState === "empty" ? (
      <p className="unknown-ledger__empty" role="status">当前已扫描来源没有待核实项。</p>
    ) : (
      <div className="unknown-ledger__groups">
        {[...grouped.entries()].map(([date, items]) => <section className="unknown-ledger__group" key={date} aria-labelledby={`unknown-ledger-date-${date}`}>
          <h2 id={`unknown-ledger-date-${date}`} className="unknown-ledger__date">{date}<span>{items.length} 项</span></h2>
          <ul className="unknown-ledger__list">
            {items.map((item) => <li className="unknown-ledger__item" key={item.source_key} data-ledger-source-keys={JSON.stringify([item.source_key])} tabIndex={-1}>
              <div className="unknown-ledger__main">
                <div className="unknown-ledger__title-row">
                  <h3>{item.subject}</h3>
                  <span className={`unknown-ledger__impact unknown-ledger__impact--${item.impact}`}>{impactLabels[item.impact]}</span>
                </div>
                <p className="unknown-ledger__field">{item.field}</p>
                <p className="unknown-ledger__meta">
                  {moduleLabels[item.module]} · {evidenceLabels[item.evidence_state]} · 建议 {item.reminder_date} 核实
                  {item.retrieved_at ? ` · 取数 ${new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeZone: "Asia/Shanghai" }).format(new Date(item.retrieved_at))}` : ""}
                </p>
                {item.reminder_status === "due" && <span className="unknown-ledger__due">已到建议核实时间</span>}
                {item.contact_status === "contacted" && <span className="unknown-ledger__contacted">已联系，仍待核实</span>}
              </div>
              <div className="unknown-ledger__actions">
                <button type="button" className="workspace-change" onClick={() => onOpenSource(item.module, item.source_key)}>前往复核</button>
                <button type="button" className="workspace-change" onClick={() => setContactStatus(item.source_key, item.contact_status === "contacted" ? "not_contacted" : "contacted")}>
                  {item.contact_status === "contacted" ? "撤销已联系" : "标记已联系"}
                </button>
              </div>
            </li>)}
          </ul>
        </section>)}
      </div>
    )}
  </section>;
}
