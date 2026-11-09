import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import "./itinerary-panel.css";

type ItineraryItem = { id: string; date: string; time: string; title: string; note: string; locked: boolean; completed: boolean };

function newItem(date: string): ItineraryItem {
  return { id: crypto.randomUUID(), date, time: "09:00", title: "", note: "", locked: false, completed: false };
}

export function ItineraryPanel({ destinationName, startDate, endDate }: { destinationName: string; startDate: string; endDate: string }) {
  const [items, setItems] = useState<ItineraryItem[]>([]);
  const [draft, setDraft] = useState(() => newItem(startDate));
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dates = useMemo(() => {
    const result: string[] = [];
    const start = new Date(`${startDate}T12:00:00+08:00`);
    const end = new Date(`${endDate}T12:00:00+08:00`);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return [];
    for (let date = start; date <= end; date = new Date(date.getTime() + 86_400_000)) result.push(date.toISOString().slice(0, 10));
    return result;
  }, [startDate, endDate]);

  const draftDate = !editingId && dates.length > 0 && !dates.includes(draft.date) ? dates[0] : draft.date;

  function addItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.title.trim()) { setError("请填写安排名称。"); return; }
    if (!dates.includes(draftDate)) { setError("请选择当前旅行日期范围内的日期。"); return; }
    const currentItem = editingId ? items.find((item) => item.id === editingId) : undefined;
    if (editingId && (!currentItem || currentItem.locked)) {
      setError("该安排已锁定或已不存在，请解锁后重新编辑。");
      return;
    }
    const updated = {
      ...draft,
      date: draftDate,
      locked: currentItem?.locked ?? false,
      completed: currentItem?.completed ?? false,
      title: draft.title.trim(),
      note: draft.note.trim(),
    };
    setItems((current) => (editingId
      ? current.map((item) => item.id === editingId ? updated : item)
      : [...current, updated]
    ).sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`)));
    setDraft(newItem(draftDate));
    setEditingId(null);
    setError(null);
  }

  function removeItem(id: string) { setItems((current) => current.filter((item) => item.id !== id || item.locked)); }
  function toggleLock(id: string) { setItems((current) => current.map((item) => item.id === id ? { ...item, locked: !item.locked } : item)); }
  function toggleCompleted(id: string) { setItems((current) => current.map((item) => item.id === id ? { ...item, completed: !item.completed } : item)); }
  function editItem(item: ItineraryItem) { setDraft({ ...item }); setEditingId(item.id); setError(null); }
  function cancelEdit() { setDraft(newItem(dates[0] ?? startDate)); setEditingId(null); setError(null); }

  const groupedItems = [...new Set(items.map((item) => item.date))].sort().map((date) => ({
    date,
    items: items.filter((item) => item.date === date),
  }));
  const outOfRangeCount = items.filter((item) => !dates.includes(item.date)).length;

  return <section className="itinerary-page" aria-labelledby="itinerary-title">
    <header className="itinerary-heading">
      <div><p className="itinerary-eyebrow">TRIP ITINERARY / 01</p><h1 id="itinerary-title">旅行行程</h1><p>按天整理安排，锁定后仅允许手动解锁修改。</p></div>
      <span className="itinerary-session-note">仅本页草稿 · 不会自动保存</span>
    </header>
    <p className="itinerary-destination">目的地：<strong>{destinationName}</strong> · 日期：{startDate} 至 {endDate}</p>
    <form className="itinerary-form" onSubmit={addItem} noValidate>
      <section className="itinerary-block" aria-labelledby="add-itinerary-title">
        <div className="itinerary-block__heading"><div><p className="itinerary-step">01 / ADD</p><h2 id="add-itinerary-title">{editingId ? "编辑安排" : "添加一项安排"}</h2></div><p>地点、票价与路线请以已核实信息为准</p></div>
        <div className="itinerary-fields">
          <label><span>日期</span><select value={draftDate} onChange={(e) => setDraft({ ...draft, date: e.target.value })}>{dates.map((date) => <option key={date} value={date}>{date}</option>)}{draftDate && !dates.includes(draftDate) && <option value={draftDate}>{draftDate}（超出旅行日期）</option>}</select></label>
          <label><span>时间</span><input type="time" value={draft.time} onChange={(e) => setDraft({ ...draft, time: e.target.value })} /></label>
          <label className="itinerary-title-field"><span>安排名称</span><input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} placeholder="例如：外滩散步" /></label>
          <label className="itinerary-note-field"><span>备注 <small>可选</small></span><input value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} placeholder="集合点、预留时间等" /></label>
        </div>
        {error && <p className="itinerary-error" role="alert">{error}</p>}
        <div className="itinerary-form-actions"><button className="itinerary-submit" type="submit">{editingId ? "保存修改" : "添加到行程"}</button>{editingId && <button className="itinerary-cancel" type="button" onClick={cancelEdit}>取消编辑</button>}</div>
      </section>
    </form>
    <section className="itinerary-block itinerary-list-block" aria-labelledby="itinerary-list-title">
      <div className="itinerary-block__heading"><div><p className="itinerary-step">02 / AGENDA</p><h2 id="itinerary-list-title">我的安排</h2></div><p>{items.length ? `${items.length} 项安排` : "还没有安排"}</p></div>
      {outOfRangeCount > 0 && <p className="itinerary-range-warning" role="status">旅行日期已调整；有 {outOfRangeCount} 项安排在日期范围外。安排已保留，请编辑日期或调整旅行日期。</p>}
      {items.length === 0 ? <p className="itinerary-empty">先添加第一项安排，行程会按日期和时间排列。</p> : <div className="itinerary-days">{groupedItems.map(({ date, items: dayItems }) => <section className="itinerary-day" key={date} aria-labelledby={`itinerary-day-${date}`}><h3 id={`itinerary-day-${date}`} className="itinerary-day__heading">{date}<span>{dayItems.length} 项</span></h3><div className="itinerary-list">{dayItems.map((item) => <article className={`itinerary-item${item.locked ? " is-locked" : ""}${item.completed ? " is-completed" : ""}`} key={item.id}><div className="itinerary-item__time"><strong>{item.time}</strong></div><div className="itinerary-item__body"><h4>{item.title}</h4>{item.note && <p>{item.note}</p>}{item.locked && <span className="itinerary-locked">已锁定</span>}{item.completed && <span className="itinerary-completed-label">已完成</span>}{!dates.includes(item.date) && <span className="itinerary-range-label">超出旅行日期</span>}</div><div className="itinerary-item__actions"><button type="button" onClick={() => toggleCompleted(item.id)}>{item.completed ? "撤销完成" : "已完成"}</button><button type="button" onClick={() => editItem(item)} disabled={item.locked} aria-label={`编辑 ${item.title}`}>编辑</button><button type="button" onClick={() => toggleLock(item.id)}>{item.locked ? "解锁" : "锁定"}</button><button type="button" onClick={() => removeItem(item.id)} disabled={item.locked}>删除</button></div></article>)}</div></section>)}</div>}
      <p className="itinerary-source-note">行程内容来自你的手动输入；本模块不自动生成景点推荐、不连接订票或地图服务。</p>
    </section>
  </section>;
}
