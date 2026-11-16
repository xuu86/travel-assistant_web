import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { usePersistentState } from "../local-storage/useWorkspacePersistence";
import type { components } from "../../shared/api-contracts";
import { EvidencePassport } from "../../shared/EvidencePassport";
import { useLedgerSource } from "../unknown-ledger/context";
import type { LedgerObservation, LedgerScanStatus } from "../unknown-ledger/model";
import { AIRPORTS, airportDistanceKm, nearestAirport, placeCoordinates } from "./airports";
import {
  fetchTransportFares,
  fetchTransportRoute,
  TransportApiError,
  type FareQuery,
  type FareResponse,
  type PlaceRef,
  type RouteQuery,
  type RouteResponse,
} from "./api";
import "./transport-panel.css";

type ResultState = components["schemas"]["ResultState"];
type EvidenceState = components["schemas"]["EvidenceState"];
const EMPTY_PLACE: PlaceRef = { display_name: "", coordinate_system: "WGS84" };

type QueryState<T> =
  | { status: "unconfigured" }
  | { status: "idle" }
  | { status: "loading" }
  | { status: "result"; data: T }
  | { status: "error"; error: TransportApiError };

const RESULT_LABELS: Record<ResultState, string> = {
  live: "已返回来源数据",
  partial: "部分信息待核实",
  empty: "本次查询无结果",
  demo: "测试数据",
  unconfigured: "服务尚未配置",
  no_coverage: "当前条件未覆盖",
  rate_limited: "查询受额度限制",
  unavailable: "服务暂不可用",
  policy_unavailable: "服务权限暂不可用",
};

const EVIDENCE_LABELS: Record<EvidenceState, string> = {
  verified: "来源已核实",
  unverified: "来源待核实",
  user_provided: "用户提供",
  estimate: "估算",
  demo: "测试 fixture",
  unknown: "来源状态未知",
};

function safeTransportError(error: unknown): TransportApiError {
  if (error instanceof TransportApiError) return error;
  return new TransportApiError("交通服务暂不可用，请稍后重试。", {
    code: "PROVIDER_UNAVAILABLE",
    retryable: true,
    status: 0,
  });
}

function formatBeijingDateTime(value: string | null | undefined): string {
  if (!value) return "查询时间待核实";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "查询时间待核实";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Shanghai",
  }).format(parsed);
}

function formatServiceTime(value: string | null | undefined, timezone: string | null | undefined): string {
  if (!value) return "时刻待核实";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "时刻待核实";
  const zone = timezone || "UTC";
  try {
    const formatted = new Intl.DateTimeFormat("zh-CN", {
      dateStyle: "short",
      timeStyle: "short",
      timeZone: zone,
    }).format(parsed);
    return `${formatted} · ${zone}`;
  } catch {
    return `${parsed.toISOString()} · UTC`;
  }
}

function PlaceFields(props: {
  origin: string;
  originHint: string;
  destination: string;
  onOriginChange: (value: string) => void;
  onDestinationChange: (value: string) => void;
}) {
  return (
    <fieldset className="transport-location-fields">
      <legend>查询地点</legend>
      <label className="transport-field">
        <span className="transport-field__label">起点</span>
        <input
          autoComplete="off"
          value={props.origin}
          onChange={(event) => props.onOriginChange(event.target.value)}
          maxLength={240}
          required
          aria-describedby="transport-origin-hint"
        />
        <span className="transport-field__hint" id="transport-origin-hint">{props.originHint}</span>
      </label>
      <label className="transport-field">
        <span className="transport-field__label">目的地</span>
        <input
          autoComplete="off"
          value={props.destination}
          onChange={(event) => props.onDestinationChange(event.target.value)}
          maxLength={240}
          required
          aria-describedby="transport-destination-hint"
        />
        <span className="transport-field__hint" id="transport-destination-hint">请核对地点名称；模糊文本不会被标成已核实。</span>
      </label>
    </fieldset>
  );
}

function ResultNotice<T extends {
  state: ResultState;
  message?: string;
  queried_at?: string;
  error?: { message: string } | null;
}>(
  { state, kind }: { state: QueryState<T>; kind: string },
) {
  if (state.status === "unconfigured") {
    return <p className="transport-result-note transport-result-note--unconfigured" role="status" aria-live="polite">
      <strong>交通服务尚未配置</strong>
      <span>提交查询后仍不会使用测试数据或旧结果填补。</span>
    </p>;
  }
  if (state.status === "idle") {
    return <p className="transport-empty-note">提交查询后显示{kind}与来源；未配置数据源时不会用测试结果或旧结果填补。</p>;
  }
  if (state.status === "loading") {
    return <p className="transport-result-note" role="status" aria-live="polite">正在查询{kind}…</p>;
  }
  if (state.status === "error") {
    return (
      <div className="transport-result-note transport-result-note--error" role="alert">
        <span>{state.error.message}</span>
        {state.error.requestId && <small>请求编号：{state.error.requestId}</small>}
      </div>
    );
  }
  const data = state.data;
  return (
    <div className={`transport-result-note transport-result-note--${data.state}`} role="status" aria-live="polite">
      <strong>{RESULT_LABELS[data.state]}</strong>
      {data.message && <span>{data.message}</span>}
      {data.error?.message && <span>{data.error.message}</span>}
      <small>查询时间：{formatBeijingDateTime(data.queried_at)}</small>
    </div>
  );
}

function ScheduleCards({ data }: { data: FareResponse }) {
  const offers = data.items ?? [];
  if (offers.length === 0) return null;
  return (
    <div className="transport-results" aria-label="班次结果">
      {offers.map((offer) => (
        <article className="transport-result-card" key={offer.offer_id} data-ledger-source-keys={JSON.stringify(offer.segments.flatMap((segment) => [
          ...(!segment.departure_at ? [`transport:schedule:${offer.offer_id}:${segment.segment_id}:departure`] : []),
          ...(!segment.arrival_at ? [`transport:schedule:${offer.offer_id}:${segment.segment_id}:arrival`] : []),
        ]))} tabIndex={-1}>
          <div className="transport-result-card__topline">
            <span className="transport-result-card__eyebrow">{offer.mode === "flight" ? "航班" : "铁路"} · {offer.travel_date}</span>
            <span className={`transport-evidence transport-evidence--${offer.evidence_state}`}>
              {EVIDENCE_LABELS[offer.evidence_state]}
            </span>
          </div>
          <h4 className="transport-result-card__route">{offer.origin_name} <span aria-hidden="true">→</span> {offer.destination_name}</h4>
          <div className="transport-schedule-grid">
            <div>
              <span className="transport-data-label">班次</span>
              <strong>{offer.service_number ?? "编号待核实"}</strong>
            </div>
            <div>
              <span className="transport-data-label">出发 · 到达</span>
              <strong>{formatServiceTime(offer.departure_at, offer.departure_timezone)}</strong>
              <strong>{formatServiceTime(offer.arrival_at, offer.arrival_timezone)}</strong>
            </div>
          </div>
          {offer.segments.length > 0 && (
            <div className="transport-segments">
              <span className="transport-data-label">乘行分段（按来源顺序）</span>
              <ol>
                {offer.segments.map((segment) => (
                  <li key={segment.segment_id}>
                    <div>
                      <strong>
                        {segment.origin_name ?? "起点待核实"} <span aria-hidden="true">→</span> {segment.destination_name ?? "目的地待核实"}
                      </strong>
                      <small>
                        {formatServiceTime(segment.departure_at, segment.departure_timezone)} → {formatServiceTime(segment.arrival_at, segment.arrival_timezone)}
                      </small>
                    </div>
                    <div>
                      <span>{segment.service_number ?? "班次编号待核实"}</span>
                      {segment.seat_class && <small>席别：{segment.seat_class}</small>}
                      {segment.operating_carrier && <small>承运：{segment.operating_carrier}</small>}
                      {segment.transfer_place && <small>换乘地点：{segment.transfer_place}</small>}
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {data.sources?.map((source) => source.source_id === offer.source_id && (
            <div className="transport-source" key={source.source_id}>
              <EvidencePassport source={source} coverage={data.coverage} subject={`班次 ${offer.service_number ?? "查询结果"}`} />
            </div>
          ))}
        </article>
      ))}
    </div>
  );
}

function RouteCards({ data }: { data: RouteResponse }) {
  return <div className="transport-results" aria-label="市内路线结果">
    {(data.items ?? []).map((route, index) => <article className="transport-result-card" key={route.route_id}>
      <div className="transport-result-card__topline">
        <span className="transport-result-card__eyebrow">方案 {index + 1}</span>
        <span className={`transport-evidence transport-evidence--${route.evidence_state}`}>{EVIDENCE_LABELS[route.evidence_state]}</span>
      </div>
      <h4 className="transport-result-card__route">{route.origin_name} <span aria-hidden="true">→</span> {route.destination_name}</h4>
      <div className="transport-schedule-grid">
        <div><span className="transport-data-label">路线距离</span><strong>{route.distance_m == null ? "距离待核实" : `${(route.distance_m / 1000).toFixed(1)} 公里`}</strong></div>
        <div><span className="transport-data-label">参考用时</span><strong>{route.duration_seconds == null ? "用时待核实" : `${Math.ceil(route.duration_seconds / 60)} 分钟`}</strong><small>规划参考，非实时到站或保证到达时间。</small></div>
      </div>
      <div className="transport-segments">
        <span className="transport-data-label">路线步骤（按来源顺序）</span>
        {route.steps?.length ? <ol>{route.steps.map((step, stepIndex) => <li key={stepIndex}>
          <div><strong>{step.instruction ?? "具体指引待核实"}</strong>
            <small>{step.distance_m == null ? "分段距离待核实" : `${step.distance_m} 米`}</small></div>
        </li>)}</ol> : <p>路线步骤待核实</p>}
      </div>
      {(data.sources ?? []).filter((source) => source.source_id === route.source_id).map((source) => <div className="transport-source" key={source.source_id}>
        <EvidencePassport source={source} coverage={data.coverage} subject="市内路线" />
      </div>)}
    </article>)}
  </div>;
}

export function TransportPanel({
  initialDestination,
  initialOrigin = EMPTY_PLACE,
  originLocationStatus = "idle",
}: {
  initialDestination: string;
  initialOrigin?: PlaceRef;
  originLocationStatus?: "idle" | "loading" | "resolved" | "error";
}) {
  const [savedOriginName, setSavedOriginName] = usePersistentState("transport.origin-name", initialOrigin.display_name);
  const [origin, setOrigin] = useState<PlaceRef>(initialOrigin);
  const originWasEdited = useRef(false);
  const [destination, setDestination] = usePersistentState("transport.destination-name", initialDestination);
  const [originAirportCode, setOriginAirportCode] = usePersistentState("transport.origin-airport", "");
  const [destinationAirportCode, setDestinationAirportCode] = usePersistentState("transport.destination-airport", "");
  const originAirportWasEdited = useRef(false);
  const destinationAirportWasEdited = useRef(false);
  const [fareMode, setFareMode] = usePersistentState<FareQuery["mode"]>("transport.fare-mode", "flight");
  const [travelDate, setTravelDate] = usePersistentState("transport.travel-date", "");
  const [adultCount, setAdultCount] = usePersistentState("transport.adult-count", "1");
  const [childCount, setChildCount] = usePersistentState("transport.child-count", "");
  const [fareFormError, setFareFormError] = useState<string | null>(null);
  const [fareState, setFareState] = useState<QueryState<FareResponse>>({ status: "idle" });
  const [queryKind, setQueryKind] = usePersistentState<"schedule" | "city">("transport.query-kind", "schedule");
  const [routeMode, setRouteMode] = usePersistentState<RouteQuery["mode"]>("transport.route-mode", "transit");
  const [routeState, setRouteState] = useState<QueryState<RouteResponse>>({ status: "idle" });
  const [routeFormError, setRouteFormError] = useState<string | null>(null);
  const routeSequence = useRef(0);
  const ledgerObservations = useMemo<LedgerObservation[]>(() => {
    if (fareState.status !== "result" || fareState.data.state === "demo") return [];
    return (fareState.data.items ?? []).flatMap((offer) => offer.segments.flatMap((segment) => {
      const sourceTime = fareState.data.sources?.find((source) => source.source_id === offer.source_id)?.retrieved_at ?? null;
      const subject = offer.mode === "rail" ? "铁路班次" : "航班";
      return [
        ...(!segment.departure_at ? [{
          source_key: `transport:schedule:${offer.offer_id}:${segment.segment_id}:departure`,
          module: "transport" as const, subject, field: "出发时刻", evidence_state: offer.evidence_state,
          impact: "medium" as const, travel_date: offer.travel_date, retrieved_at: sourceTime,
        }] : []),
        ...(!segment.arrival_at ? [{
          source_key: `transport:schedule:${offer.offer_id}:${segment.segment_id}:arrival`,
          module: "transport" as const, subject, field: "到达时刻", evidence_state: offer.evidence_state,
          impact: "medium" as const, travel_date: offer.travel_date, retrieved_at: sourceTime,
        }] : []),
      ];
    }));
  }, [fareState]);
  const ledgerScanStatus: LedgerScanStatus = fareState.status === "result"
    ? fareState.data.state === "live" ? "complete"
      : fareState.data.state === "partial" ? "partial"
        : fareState.data.state === "demo" ? "unavailable" : "complete"
    : fareState.status === "idle" || fareState.status === "loading" ? "not_loaded" : "unavailable";
  useLedgerSource("transport", { module: "transport", status: ledgerScanStatus }, ledgerObservations);
  const fareSequence = useRef(0);
  const originCoordinates = origin.latitude != null && origin.longitude != null
    ? { latitude: origin.latitude, longitude: origin.longitude }
    : placeCoordinates(origin.display_name);
  const destinationCoordinates = placeCoordinates(destination);
  const nearestOriginAirport = nearestAirport(originCoordinates);
  const nearestDestinationAirport = nearestAirport(destinationCoordinates);

  useEffect(() => {
    if (!originAirportWasEdited.current) setOriginAirportCode(nearestOriginAirport?.iata ?? "");
  }, [nearestOriginAirport?.iata, setOriginAirportCode]);

  useEffect(() => {
    if (!destinationAirportWasEdited.current) setDestinationAirportCode(nearestDestinationAirport?.iata ?? "");
  }, [nearestDestinationAirport?.iata, setDestinationAirportCode]);

  useEffect(() => {
    if (!originWasEdited.current) {
      const nextOrigin = savedOriginName === initialOrigin.display_name
        ? initialOrigin
        : { display_name: savedOriginName, coordinate_system: "WGS84" as const };
      setOrigin(nextOrigin);
    }
  }, [initialOrigin, savedOriginName]);

  function clearFareResults() {
    fareSequence.current += 1;
    setFareState({ status: "idle" });
    setFareFormError(null);
  }

  function clearResults() {
    clearFareResults();
    routeSequence.current += 1;
    setRouteState({ status: "idle" });
    setRouteFormError(null);
  }

  useEffect(() => () => {
    fareSequence.current += 1;
    routeSequence.current += 1;
  }, []);

  function validLocations(setError: (message: string) => void): boolean {
    if (!origin.display_name.trim() || !destination.trim()) {
      setError("请填写起点和目的地。");
      return false;
    }
    if (origin.display_name.trim() === "当前位置" && origin.latitude === undefined) {
      setError("尚未取得当前位置，请手动填写起点或重新选择出发地点。");
      return false;
    }
    return true;
  }

  function buildPlace(name: string, place?: PlaceRef) {
    if (place && name.trim() === place.display_name) return { ...place };
    return { display_name: name.trim(), coordinate_system: "WGS84" as const };
  }

  async function handleFareSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearFareResults();
    if (!validLocations(setFareFormError)) return;
    if (!travelDate) {
      setFareFormError("请选择明确的目标出行日期。");
      return;
    }
    const parsedAdultCount = Number(adultCount);
    const parsedChildCount = childCount === "" ? null : Number(childCount);
    if (!Number.isSafeInteger(parsedAdultCount) || parsedAdultCount < 1) {
      setFareFormError("成人数量必须是大于零的整数。");
      return;
    }
    if (parsedChildCount !== null && (!Number.isSafeInteger(parsedChildCount) || parsedChildCount < 0)) {
      setFareFormError("儿童人数必须是零或正整数，也可以留空。");
      return;
    }
    const totalPassengers = parsedAdultCount + (parsedChildCount ?? 0);
    if (!Number.isSafeInteger(totalPassengers)) {
      setFareFormError("乘客总数超出有效范围。");
      return;
    }
    if (origin.display_name.trim().toLocaleLowerCase() === destination.trim().toLocaleLowerCase()) {
      setFareFormError("起点与目的地不能相同。");
      return;
    }

    const originPlace = buildPlace(origin.display_name, origin);
    const destinationPlace = buildPlace(destination);
    if (fareMode === "flight") {
      if (!originAirportCode || !destinationAirportCode) {
        setFareFormError("请选择起飞机场和到达机场。");
        return;
      }
      if (originAirportCode === destinationAirportCode) {
        setFareFormError("起飞机场与到达机场不能相同。");
        return;
      }
      if (totalPassengers > 9) {
        setFareFormError("航班查询的成人加儿童总数不能超过 9 人。");
        return;
      }
      const selectedOriginAirport = AIRPORTS.find((airport) => airport.iata === originAirportCode);
      const selectedDestinationAirport = AIRPORTS.find((airport) => airport.iata === destinationAirportCode);
      if (!selectedOriginAirport || !selectedDestinationAirport) {
        setFareFormError("所选机场信息无效，请重新选择机场。");
        return;
      }
      originPlace.display_name = selectedOriginAirport.name;
      destinationPlace.display_name = selectedDestinationAirport.name;
      originPlace.place_id = originAirportCode;
      destinationPlace.place_id = destinationAirportCode;
    }

    const query: FareQuery = {
      origin: originPlace,
      destination: destinationPlace,
      mode: fareMode,
      travel_date: travelDate,
      passenger_count: totalPassengers,
      child_count: parsedChildCount,
    };
    const sequence = ++fareSequence.current;
    setFareFormError(null);
    setFareState({ status: "loading" });
    try {
      const data = await fetchTransportFares(query);
      if (fareSequence.current === sequence) setFareState({ status: "result", data });
    } catch (error) {
      if (fareSequence.current === sequence) {
        setFareState({ status: "error", error: safeTransportError(error) });
      }
    }
  }

  async function handleRouteSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const sequence = ++routeSequence.current;
    setRouteState({ status: "idle" });
    setRouteFormError(null);
    if (!validLocations(setRouteFormError)) return;
    if (origin.display_name.trim() === destination.trim()) {
      setRouteFormError("起点与目的地不能相同。");
      return;
    }
    setRouteState({ status: "loading" });
    try {
      const data = await fetchTransportRoute({
        origin: buildPlace(origin.display_name, origin), destination: buildPlace(destination),
        mode: routeMode,
      });
      if (routeSequence.current === sequence) setRouteState({ status: "result", data });
    } catch (error) {
      if (routeSequence.current === sequence) setRouteState({ status: "error", error: safeTransportError(error) });
    }
  }

  return (
    <section className="transport-panel" aria-labelledby="transport-title">
      <div className="transport-panel__heading">
        <div>
          <p className="transport-panel__eyebrow">TRANSPORT / 03</p>
          <h1 id="transport-title">交通查询</h1>
          <p>查询航班、铁路班次，或规划市内公交、步行与驾车路线。</p>
        </div>
        <span className="transport-panel__stamp">{queryKind === "city" ? "路线 · 距离 · 用时 · 来源" : "班次 · 时刻 · 来源"}</span>
      </div>

      <section className="transport-guide" aria-labelledby="transport-guide-title">
        <div className="transport-guide__head">
          <p className="transport-panel__eyebrow">READ ME</p>
          <h2 id="transport-guide-title">查询口径</h2>
          <p>按出发地、目的地和日期查询班次；未返回的信息会标为待核实。</p>
        </div>
        <ul>
          <li><strong>查询范围</strong><span>航班、铁路与市内路线独立查询。</span></li>
          <li><strong>结果内容</strong><span>班次时刻或路线步骤、距离、参考用时与来源。</span></li>
          <li><strong>服务状态</strong><span>未配置时不会展示测试班次。</span></li>
        </ul>
      </section>

      <div className="transport-query-switch" role="group" aria-label="交通查询类型">
        <button type="button" aria-pressed={queryKind === "schedule"} onClick={() => { clearResults(); setQueryKind("schedule"); }}>航班 / 铁路班次</button>
        <button type="button" aria-pressed={queryKind === "city"} onClick={() => { clearResults(); setQueryKind("city"); }}>市内路线</button>
      </div>
      <div className="transport-query-card">
        <PlaceFields
          origin={origin.display_name}
          originHint={originLocationStatus === "loading"
            ? "正在获取浏览器当前位置。"
            : originLocationStatus === "error"
              ? "定位未完成；请手动填写起点后查询。"
              : origin.latitude !== undefined
                ? "默认起点来自浏览器定位；可编辑地点，编辑后将按文字地点查询。"
                : "已沿用规划时设置的出发地；可改为站点、机场或其他地点。"}
          destination={destination}
          onOriginChange={(value) => {
            clearResults();
            originWasEdited.current = true;
            originAirportWasEdited.current = false;
            setOriginAirportCode(nearestAirport(placeCoordinates(value))?.iata ?? "");
            setSavedOriginName(value);
            setOrigin({ display_name: value, coordinate_system: "WGS84" });
          }}
          onDestinationChange={(value) => {
            clearResults();
            destinationAirportWasEdited.current = false;
            setDestinationAirportCode(nearestAirport(placeCoordinates(value))?.iata ?? "");
            setDestination(value);
          }}
        />

        {queryKind === "city" ? <form className="transport-search-form" onSubmit={handleRouteSubmit} noValidate>
          <div className="transport-search-form__fields">
            <label className="transport-field"><span className="transport-field__label">市内交通方式</span>
              <select value={routeMode} onChange={(event) => { clearResults(); setRouteMode(event.target.value as RouteQuery["mode"]); }}>
                <option value="transit">公交 / 地铁</option><option value="walking">步行</option><option value="taxi">驾车 / 出租车</option>
              </select>
            </label>
          </div>
          <div className="transport-search-form__footer">
            <span className="transport-field__hint">请填写带城市的具体地点，如“杭州市西湖”。用时仅作规划参考。</span>
            <button type="submit" className="transport-primary-button" disabled={routeState.status === "loading"}>{routeState.status === "loading" ? "正在查询…" : "查询市内路线"}</button>
          </div>
          {routeFormError && <p className="transport-form-error" role="alert">{routeFormError}</p>}
        </form> : <form className="transport-search-form" onSubmit={handleFareSubmit} noValidate>
          <div className="transport-search-form__fields">
              <label className="transport-field">
                <span className="transport-field__label">交通方式</span>
                <select value={fareMode} onChange={(event) => { clearFareResults(); setFareMode(event.target.value as FareQuery["mode"]); }}>
                  <option value="flight">航班</option>
                  <option value="rail">铁路 / 高铁</option>
                </select>
              </label>
              <label className="transport-field">
                <span className="transport-field__label">目标出行日期</span>
                <input type="date" value={travelDate} onChange={(event) => { clearFareResults(); setTravelDate(event.target.value); }} aria-describedby="transport-travel-date-hint" />
                <span className="transport-field__hint" id="transport-travel-date-hint">按显式日期查询，不自动替换为今天。</span>
              </label>
              <label className="transport-field">
                <span className="transport-field__label">成人数量</span>
                <input type="number" min="1" step="1" inputMode="numeric" value={adultCount} onChange={(event) => { clearFareResults(); setAdultCount(event.target.value); }} aria-describedby="transport-adult-count-hint" />
                <span className="transport-field__hint" id="transport-adult-count-hint">至少 1 位成人；与儿童人数合并为查询总人数。</span>
              </label>
              <label className="transport-field">
                <span className="transport-field__label">儿童人数（可选）</span>
                <input type="number" min="0" step="1" inputMode="numeric" value={childCount} onChange={(event) => { clearFareResults(); setChildCount(event.target.value); }} aria-describedby="transport-child-count-hint" />
                <span className="transport-field__hint" id="transport-child-count-hint">可留空；查询人数按成人与儿童合计。</span>
              </label>
              {fareMode === "flight" && (
                <>
                  <label className="transport-field">
                    <span className="transport-field__label">起飞机场</span>
                    <select
                      value={originAirportCode}
                      onChange={(event) => {
                        clearFareResults();
                        originAirportWasEdited.current = true;
                        setOriginAirportCode(event.target.value);
                      }}
                      aria-describedby="transport-origin-airport-hint"
                    >
                      {!originAirportCode && <option value="">选择机场</option>}
                      {AIRPORTS.map((airport) => (
                        <option key={airport.iata} value={airport.iata}>
                          {airport.name} · {airport.iata}{airport.iata === nearestOriginAirport?.iata ? " · 最近" : ""}
                        </option>
                      ))}
                    </select>
                    <span className="transport-field__hint" id="transport-origin-airport-hint">
                      {nearestOriginAirport
                        ? `最近机场${originAirportCode === nearestOriginAirport.iata ? " · 默认选择" : " · 可更改"} · ${nearestOriginAirport.name}（约 ${Math.round(airportDistanceKm(originCoordinates!, nearestOriginAirport))} 公里）`
                        : "无法根据起点定位最近机场，请从列表中选择。"}
                    </span>
                  </label>
                  <label className="transport-field">
                    <span className="transport-field__label">到达机场</span>
                    <select
                      value={destinationAirportCode}
                      onChange={(event) => {
                        clearFareResults();
                        destinationAirportWasEdited.current = true;
                        setDestinationAirportCode(event.target.value);
                      }}
                      aria-describedby="transport-destination-airport-hint"
                    >
                      {!destinationAirportCode && <option value="">选择机场</option>}
                      {AIRPORTS.map((airport) => (
                        <option key={airport.iata} value={airport.iata}>
                          {airport.name} · {airport.iata}{airport.iata === nearestDestinationAirport?.iata ? " · 最近" : ""}
                        </option>
                      ))}
                    </select>
                    <span className="transport-field__hint" id="transport-destination-airport-hint">
                      {nearestDestinationAirport
                        ? `最近机场${destinationAirportCode === nearestDestinationAirport.iata ? " · 默认选择" : " · 可更改"} · ${nearestDestinationAirport.name}（约 ${Math.round(airportDistanceKm(destinationCoordinates!, nearestDestinationAirport))} 公里）`
                        : "无法根据目的地定位最近机场，请从列表中选择。"}
                    </span>
                  </label>
                </>
              )}
          </div>
          <div className="transport-search-form__footer">
            <p className="transport-field__hint">结果仅供班次查询参考，出行前请以承运方信息为准。</p>
            <button className="transport-primary-button" type="submit" disabled={fareState.status === "loading"}>
              {fareState.status === "loading" ? "正在查询…" : fareState.status === "error" ? "重试班次" : "查询班次"}
              <span aria-hidden="true">→</span>
            </button>
          </div>
          {fareFormError && <p className="transport-form-error" role="alert">{fareFormError}</p>}
        </form>}
      </div>

      <div className="transport-query-results">
        <div className="transport-results-heading">
          <h3>{queryKind === "city" ? "市内路线结果" : "班次结果"}</h3>
          <span>{queryKind === "city" ? "规划参考" : "单程班次"}</span>
        </div>
        {queryKind === "city" ? <>
          <ResultNotice state={routeState} kind="市内路线" />
          {routeState.status === "result" && <RouteCards data={routeState.data} />}
        </> : <>
          <ResultNotice state={fareState} kind="班次" />
          {fareState.status === "result" && <ScheduleCards data={fareState.data} />}
        </>}
      </div>
    </section>
  );
}
