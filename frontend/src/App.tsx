import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { fetchWeatherForecast, WeatherApiError, type WeatherQuery } from "./features/weather/api";
import { WeatherPanel, type WeatherPanelState } from "./features/weather/WeatherPanel";
import { BudgetPanel } from "./features/budget/BudgetPanel";
import { TransportPanel } from "./features/transport/TransportPanel";
import { ItineraryPanel } from "./features/itinerary/ItineraryPanel";
import { AssistantPanel } from "./features/assistant/AssistantPanel";
import type { components } from "./shared/api-contracts";
import "./app.css";

type CityOption = {
  id: WeatherQuery["city_id"];
  name: string;
  province: string;
};

const CITY_OPTIONS: CityOption[] = [
  { id: "shanghai", name: "上海", province: "上海市" },
  { id: "suzhou", name: "苏州", province: "江苏省" },
  { id: "wuxi", name: "无锡", province: "江苏省" },
  { id: "jiaxing", name: "嘉兴", province: "浙江省" },
  { id: "hangzhou", name: "杭州", province: "浙江省" },
];

function formatBeijingDate(date: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const part = (type: "year" | "month" | "day") => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

function beijingDateInputValue(): string {
  return formatBeijingDate(new Date());
}

function addDays(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00+08:00`);
  date.setUTCDate(date.getUTCDate() + days);
  return formatBeijingDate(date);
}

function requestedDays(startDate: string, endDate: string): number | null {
  const start = new Date(`${startDate}T00:00:00+08:00`);
  const end = new Date(`${endDate}T00:00:00+08:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
  return Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1;
}

function safeWeatherError(error: unknown): WeatherApiError {
  if (error instanceof WeatherApiError) return error;
  return new WeatherApiError("天气服务暂不可用。", {
    code: "PROVIDER_UNAVAILABLE",
    retryable: true,
    status: 0,
  });
}

export function App() {
  const [activeView, setActiveView] = useState<"weather" | "budget" | "transport" | "itinerary" | "assistant">("weather");
  const [selectedDestinationId, setSelectedDestinationId] = useState("");
  const [destination, setDestination] = useState<CityOption | null>(null);
  const [destinationError, setDestinationError] = useState<string | null>(null);
  const [showDestinationDialog, setShowDestinationDialog] = useState(false);
  const [destinationDialogAction, setDestinationDialogAction] = useState<"change" | "return">("change");
  const destinationDialogRef = useRef<HTMLDialogElement>(null);
  const [workspaceKey, setWorkspaceKey] = useState(0);
  const defaultStartDate = useMemo(() => beijingDateInputValue(), []);
  const activeRequest = useRef(0);
  const [startDate, setStartDate] = useState(defaultStartDate);
  const [endDate, setEndDate] = useState(() => addDays(defaultStartDate, 2));
  const [formError, setFormError] = useState<string | null>(null);
  const [weatherState, setWeatherState] = useState<WeatherPanelState>({ status: "unconfigured" });

  const rangeDays = requestedDays(startDate, endDate);
  const assistantEvidence: components["schemas"]["AssistantEvidence"][] =
    weatherState.status === "success" &&
    (weatherState.data.state === "live" || weatherState.data.state === "partial")
      ? (weatherState.data.sources ?? [])
        .filter((source) => source.evidence_state === "verified")
        .map((source) => ({
          evidence_id: `weather:${weatherState.data.request_id}:${source.source_id}`,
          kind: "weather" as const,
          state: weatherState.data.state as "live" | "partial",
          summary: (weatherState.data.items ?? []).map((day) =>
            `${day.date}: ${day.weather_code === null ? "天气现象待识别" : `天气代码 ${day.weather_code}`}，` +
            `最高 ${day.temperature_max_c ?? "暂无"}°C，最低 ${day.temperature_min_c ?? "暂无"}°C，` +
            `降水 ${day.precipitation_sum_mm ?? "暂无"} mm`,
          ).join("；").slice(0, 2_000),
          source,
        }))
      : [];

  useEffect(() => {
    const dialog = destinationDialogRef.current;
    if (!dialog) return;
    if (showDestinationDialog && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    if (!showDestinationDialog && dialog.open) {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }
  }, [showDestinationDialog]);

  function startWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const selected = CITY_OPTIONS.find((city) => city.id === selectedDestinationId);
    if (!selected) {
      setDestinationError("请选择目的城市。");
      return;
    }
    setDestination(selected);
    setDestinationError(null);
  }

  function resetWorkspaceState() {
    activeRequest.current += 1;
    setWorkspaceKey((key) => key + 1);
    setStartDate(defaultStartDate);
    setEndDate(addDays(defaultStartDate, 2));
    setWeatherState({ status: "unconfigured" });
    setFormError(null);
    setActiveView("weather");
    setShowDestinationDialog(false);
    setDestinationError(null);
  }

  function confirmDestinationAction() {
    if (destinationDialogAction === "return") {
      resetWorkspaceState();
      setSelectedDestinationId("");
      setDestination(null);
      return;
    }
    const selected = CITY_OPTIONS.find((city) => city.id === selectedDestinationId);
    if (!selected) {
      setDestinationError("请选择目的城市。");
      return;
    }
    setDestination(selected);
    resetWorkspaceState();
  }

  function clearPreviousForecast() {
    activeRequest.current += 1;
    setFormError(null);
    setWeatherState({ status: "idle" });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestNumber = ++activeRequest.current;
    setFormError(null);
    setWeatherState({ status: "idle" });

    if (!startDate || !endDate) {
      setFormError("请选择开始日期和结束日期。");
      return;
    }
    if (rangeDays === null) {
      setFormError("请输入有效的日期范围。");
      return;
    }
    if (rangeDays < 1) {
      setFormError("结束日期不能早于开始日期。");
      return;
    }
    if (rangeDays > 16) {
      setFormError("单次最多查询 16 个当地日，请缩短日期范围。");
      return;
    }

    const query: WeatherQuery = {
      city_id: destination!.id,
      start_date: startDate,
      end_date: endDate,
    };

    setWeatherState({ status: "loading" });
    try {
      const data = await fetchWeatherForecast(query);
      if (activeRequest.current === requestNumber) {
        setWeatherState({ status: "success", data });
      }
    } catch (error) {
      if (activeRequest.current === requestNumber) {
        setWeatherState({ status: "error", error: safeWeatherError(error) });
      }
    }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#app-content">跳转到主要内容</a>
      <header className="site-header">
        <a className="brand" href="/" aria-label="行旅智能旅游助手首页">
          <span className="brand__mark" aria-hidden="true">行</span>
          <span>
            <span className="brand__name">行旅</span>
            <span className="brand__tagline">智能旅游助手</span>
          </span>
        </a>
        <div className="header-note">
          <span className="header-note__dot" aria-hidden="true" />
          本地开发预览
        </div>
      </header>

      <main className="app-main" id="app-content">
        {!destination ? (
          <section className="destination-setup" aria-labelledby="destination-setup-title">
            <p className="eyebrow">TRAVEL WORKSPACE / SETUP</p>
            <h1 id="destination-setup-title">先选一座目的城市</h1>
            <p className="destination-setup__copy">确认目的地后，再进入天气、预算与交通工具。</p>
            <form className="destination-setup__form" onSubmit={startWorkspace}>
              <label className="field">
                <span className="field__label">目的城市</span>
                <select value={selectedDestinationId} onChange={(event) => { setSelectedDestinationId(event.target.value); setDestinationError(null); }} aria-describedby={destinationError ? "destination-error" : undefined}>
                  <option value="">请选择</option>
                  {CITY_OPTIONS.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
                </select>
              </label>
              {destinationError && <p id="destination-error" className="form-error" role="alert">{destinationError}</p>}
              <button className="primary-button" type="submit">开始规划 <span aria-hidden="true">→</span></button>
            </form>
          </section>
        ) : (
          <>
            <section className="workspace-bar" aria-label="当前旅行工作区">
              <p>当前目的地 <strong className="workspace-destination">{destination.name}</strong></p>
              <div className="workspace-bar__actions">
                <button type="button" className="workspace-change" onClick={() => { setDestinationDialogAction("change"); setSelectedDestinationId(destination.id); setShowDestinationDialog(true); }}>更换目的地</button>
                <button type="button" className="workspace-change" onClick={() => { setDestinationDialogAction("return"); setSelectedDestinationId(""); setShowDestinationDialog(true); }}>返回选择城市</button>
              </div>
            </section>
            <nav className="feature-nav" aria-label="旅行工具">
              <button type="button" aria-pressed={activeView === "weather"} onClick={() => setActiveView("weather")}>天气</button>
              <button type="button" aria-pressed={activeView === "budget"} onClick={() => setActiveView("budget")}>预算</button>
              <button type="button" aria-pressed={activeView === "transport"} onClick={() => setActiveView("transport")}>交通</button>
              <button type="button" aria-pressed={activeView === "itinerary"} onClick={() => setActiveView("itinerary")}>行程</button>
              <button type="button" aria-pressed={activeView === "assistant"} onClick={() => setActiveView("assistant")}>AI 助手</button>
            </nav>
            <dialog
              ref={destinationDialogRef}
              className="destination-dialog"
              aria-modal="true"
              aria-labelledby="destination-dialog-title"
              aria-describedby="destination-dialog-description"
              onCancel={(event) => { event.preventDefault(); setShowDestinationDialog(false); setDestinationError(null); }}
            >
                  <h2 id="destination-dialog-title">{destinationDialogAction === "return" ? "返回选择城市？" : "更换目的地？"}</h2>
                  <p id="destination-dialog-description">确认后将清除本页预算草稿、天气查询条件与结果，以及交通输入和结果。</p>
                  {destinationDialogAction === "change" && <label className="field">
                    <span className="field__label">新目的城市</span>
                    <select autoFocus value={selectedDestinationId} onChange={(event) => { setSelectedDestinationId(event.target.value); setDestinationError(null); }}>
                      {CITY_OPTIONS.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
                    </select>
                  </label>}
                  {destinationError && <p className="form-error" role="alert">{destinationError}</p>}
                  <div className="destination-dialog__actions">
                    <button type="button" className="workspace-change" onClick={() => { setShowDestinationDialog(false); setDestinationError(null); }}>取消</button>
                    <button type="button" className="primary-button" onClick={confirmDestinationAction}>{destinationDialogAction === "return" ? "确认返回" : "确认更换"}</button>
                  </div>
            </dialog>
            <div className="workspace-view" hidden={activeView !== "weather"}>
        <section className="hero" aria-labelledby="page-title">
          <div className="hero__copy">
            <p className="eyebrow">TRAVEL WEATHER / 01</p>
            <h1 id="page-title">从一座城市，开始规划一段旅程。</h1>
            <p className="hero__description">
              先确认出发日的天气节奏，再决定路线的轻重缓急。这里展示的是可追溯的逐日预报，不用演示数据掩盖未知。
            </p>
            <div className="hero__facts" aria-label="天气查询能力说明">
              <span><strong>5</strong> 个已注册城市</span>
              <span><strong>16</strong> 天单次上限</span>
              <span>北京时间展示</span>
            </div>
          </div>
          <aside className="hero__signal" aria-label="行旅天气查询原则">
            <div className="signal-card__topline">
              <span className="signal-card__label">FIELD NOTE</span>
              <span className="signal-card__index" aria-hidden="true">01</span>
            </div>
            <p className="signal-card__quote">“看见覆盖，也看见缺口。”</p>
            <div className="signal-card__rows">
              <div><span>温度</span><strong>°C</strong></div>
              <div><span>降水</span><strong>mm / %</strong></div>
              <div><span>风速</span><strong>km/h</strong></div>
            </div>
            <p className="signal-card__note">每一项未知值都会保持为“暂无”，不会被当作晴天或零降水。</p>
          </aside>
        </section>

        <section className="query-card" id="weather-query" aria-labelledby="weather-query-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">01 / QUERY</p>
              <h2 id="weather-query-title">查询一段天气</h2>
            </div>
            <p className="section-heading__aside">单城 · 明确日期 · 不自动补齐</p>
          </div>

          <form className="query-form" onSubmit={handleSubmit} noValidate>
            <div className="query-form__fields">
              <label className="field">
                <span className="field__label">开始日期</span>
                <input
                  type="date"
                  value={startDate}
                  onChange={(event) => {
                    setStartDate(event.target.value);
                    clearPreviousForecast();
                  }}
                  aria-describedby="date-help"
                />
              </label>
              <label className="field">
                <span className="field__label">结束日期</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(event) => {
                    setEndDate(event.target.value);
                    clearPreviousForecast();
                  }}
                  aria-describedby="date-help"
                />
              </label>
            </div>
            <div className="query-form__footer">
              <p id="date-help" className="form-help">
                最多查询 16 个当地日 · 以 Asia/Shanghai 解释业务日期
                {rangeDays !== null && rangeDays > 0 && rangeDays <= 16 ? ` · 当前 ${rangeDays} 天` : ""}
              </p>
              <button className="primary-button" type="submit" disabled={weatherState.status === "loading"}>
                <span>{weatherState.status === "loading" ? "正在查询" : "查询天气"}</span>
                <span aria-hidden="true">→</span>
              </button>
            </div>
            {formError && <p className="form-error" role="alert">{formError}</p>}
          </form>
        </section>

          <WeatherPanel cityName={destination.name} state={weatherState} />
            </div>
            <div className="workspace-view" hidden={activeView !== "budget"} key={`budget-${workspaceKey}`}><BudgetPanel destinationName={destination.name} /></div>
            <div className="workspace-view" hidden={activeView !== "transport"} key={`transport-${workspaceKey}`}><TransportPanel key={workspaceKey} initialDestination={destination.name} /></div>
            <div className="workspace-view" hidden={activeView !== "itinerary"} key={`itinerary-${workspaceKey}`}><ItineraryPanel destinationName={destination.name} startDate={startDate} endDate={endDate} /></div>
            <div className="workspace-view" hidden={activeView !== "assistant"} key={`assistant-${workspaceKey}`}><AssistantPanel destinationName={destination.name} startDate={startDate} endDate={endDate} evidence={assistantEvidence} /></div>
          </>
        )}
      </main>

      <footer className="site-footer">
        <span>行旅 · 智能旅游助手</span>
        <span>
          {!destination || activeView === "weather"
            ? "天气模块仅展示已返回的实际日期覆盖"
            : activeView === "budget"
              ? "预算金额仅在本页计算，不连接报价平台"
              : activeView === "transport"
                ? "交通服务未配置时不会显示演示班次或路线"
                : activeView === "itinerary"
                  ? "行程草稿仅保存在当前页面，不连接订票或地图服务"
                  : "AI 回答仅依据本轮明确提供的信息，条件建议不会自动应用"}
        </span>
      </footer>
    </div>
  );
}
