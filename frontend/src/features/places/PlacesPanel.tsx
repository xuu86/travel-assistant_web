import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { searchPlaces, type Place, type PlaceCategory, type PlaceResult } from "./api";
import "./places.css";

const CONTENT = {
  hotels: {
    title: "寻找一处落脚点", label: "酒店", kicker: "STAY / HOTELS",
    placeholder: "酒店名称、品牌或商圈", button: "查询酒店",
    note: "查询酒店名称、地址与位置。实时房价、房型和余房尚未接入。",
    missing: "房价与余房待核实",
  },
  activities: {
    title: "找个地方，体验当地", label: "活动场馆", kicker: "EXPLORE / VENUES",
    placeholder: "剧院、运动场馆、休闲娱乐", button: "查询活动场馆",
    note: "查询娱乐休闲场馆。活动日期、演出场次、票价和售票状态需另行核实。",
    missing: "活动档期与门票待核实",
  },
  attractions: {
    title: "发现下一站风景", label: "景点", kicker: "DISCOVER / ATTRACTIONS",
    placeholder: "景点、公园或地标名称", button: "查询景点",
    note: "查询景点与地标的位置。开放时间、门票和预约要求需出发前核实。",
    missing: "开放与预约待核实",
  },
  maps: {
    title: "在地图上找到目的地", label: "地点", kicker: "LOCATE / MAP",
    placeholder: "输入想查看的地点", button: "搜索地点",
    note: "在当前城市内搜索地点，选择结果后查看地图位置。", missing: "地点信息来自高德地图",
  },
};

export function PlacesPanel({ category, cityId, cityName, onSelect }: {
  category: PlaceCategory; cityId: string; cityName: string; onSelect: (place: Place) => void;
}) {
  const content = CONTENT[category];
  const [keywords, setKeywords] = useState("");
  const [result, setResult] = useState<PlaceResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submittedKeywords, setSubmittedKeywords] = useState("");
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  useEffect(() => () => { sequence.current += 1; controller.current?.abort(); }, []);

  async function search(page = 1, term = keywords.trim()) {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const current = ++sequence.current;
    setLoading(true); setError(""); setResult(null); setSubmittedKeywords(term);
    try {
      const data = await searchPlaces(category, { city_id: cityId, keywords: term, page }, abort.signal);
      if (current === sequence.current) setResult(data);
    } catch (reason) {
      if (abort.signal.aborted || current !== sequence.current) return;
      setError(reason instanceof Error ? reason.message : "地点服务暂不可用，请重试。");
    } finally {
      if (current === sequence.current) setLoading(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void search();
  }

  function editKeywords(value: string) {
    sequence.current += 1; controller.current?.abort();
    setKeywords(value); setResult(null); setError(""); setLoading(false);
  }

  const resultTitle = result?.state === "partial" ? "部分地点信息可用" : "查询结果";
  return (
    <section className={`places-panel places-panel--${category}`} aria-labelledby={`${category}-title`}>
      <div className="places-heading">
        <div><p className="eyebrow">{content.kicker}</p><h1 id={`${category}-title`}>{content.title}</h1></div>
        <span className="places-city">{cityName}<span> / 城市内检索</span></span>
      </div>
      <p className="places-intro">{content.note}</p>
      <form className="places-search" onSubmit={submit}>
        <label className="field" htmlFor={`${category}-keywords`}>
          <span className="field__label">{content.label}关键词</span>
          <input id={`${category}-keywords`} value={keywords} maxLength={100}
            onChange={(event) => editKeywords(event.target.value)} placeholder={content.placeholder} />
        </label>
        <button className="primary-button" type="submit" disabled={loading}>{loading ? "正在查询…" : content.button}<span aria-hidden="true">→</span></button>
      </form>
      <div className="places-feedback" aria-live="polite" aria-busy={loading}>
        {loading && <p role="status">正在查询{cityName}的{content.label}…</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        {!loading && !error && !result && <p>输入关键词缩小范围，或直接查询当前城市的{content.label}。</p>}
        {result && <>
          <div className="places-result-heading"><h2>{resultTitle}</h2><span>第 {result.page} 页 · {result.items.length} 个地点</span></div>
          <p role="status">{result.message}</p>
          {result.items.length > 0 && <ol className="places-list">
            {result.items.map((place, index) => <li key={place.id}>
              <span className="place-index" aria-hidden="true">{String((result.page - 1) * 10 + index + 1).padStart(2, "0")}</span>
              <div className="place-details"><h3>{place.name}</h3><p>{place.address ?? "地址待补充"}</p>
                {place.category && <p className="place-category">{place.category.split(";").join(" / ")}</p>}
                {place.telephone && <p>电话：{place.telephone}</p>}
                <span className="place-unknown">{content.missing}</span>
              </div>
              <button className="workspace-change" type="button" disabled={!place.location}
                aria-label={`在地图查看${place.name}`} onClick={() => onSelect(place)}>
                {place.location ? "在地图查看 ↗" : "位置待核实"}
              </button>
            </li>)}
          </ol>}
          {(result.page > 1 || result.has_more) && <nav className="places-pagination" aria-label={`${content.label}结果分页`}>
            <button className="workspace-change" type="button" disabled={loading || result.page <= 1}
              onClick={() => void search(result.page - 1, submittedKeywords)}>上一页</button>
            <span>第 {result.page} 页</span>
            <button className="workspace-change" type="button" disabled={loading || !result.has_more}
              onClick={() => void search(result.page + 1, submittedKeywords)}>下一页</button>
          </nav>}
          {result.sources.length > 0 && <p className="places-source">来源：{result.sources.map((s) => s.display_name).join("、")} · 查询于 {new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", dateStyle: "short", timeStyle: "short" }).format(new Date(result.queried_at))}（北京时间）</p>}
        </>}
      </div>
    </section>
  );
}
