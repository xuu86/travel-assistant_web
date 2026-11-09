import { useEffect, useState } from "react";
import { fetchStaticMap, type Place } from "../places/api";
import { PlacesPanel } from "../places/PlacesPanel";

function MapPreview({ cityId, title, place, zoom }: {
  cityId: string; title: string; place: Place | null; zoom: number;
}) {
  const [image, setImage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = "";
    void fetchStaticMap({ city_id: cityId, location: place?.location ?? null, zoom }, controller.signal)
      .then((blob) => {
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setImage(objectUrl);
      }).catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "地图暂不可用。");
      });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [cityId, place, zoom]);
  return <div className="map-preview" aria-busy={!image && !error}>
    {image ? <img src={image} alt={`${title}的高德地图位置，标记 A 为选中位置`} width={750} height={400}
      onError={() => setError("地图图片加载失败，请重新加载。")} hidden={!!error} /> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : !image ? <p role="status">正在加载{title}地图…</p> : null}
  </div>;
}

export function MapPanel({ cityId, cityName, selectedPlace, onSelect }: {
  cityId: string; cityName: string; selectedPlace: Place | null; onSelect: (place: Place | null) => void;
}) {
  const [zoom, setZoom] = useState(13);
  const [revision, setRevision] = useState(0);
  const title = selectedPlace?.name ?? cityName;
  return <section className="maps-panel" aria-label="高德地图">
    <div className="map-heading"><div><p className="eyebrow">AMAP / CITY ATLAS</p><h1>{cityName} · 地图</h1></div>
      <span className="places-city">GCJ-02</span></div>
    <p className="places-intro">选择地点查看周边道路与位置。地图为静态预览，可缩放查看；暂不支持拖动或实时导航。</p>
    <div className="map-toolbar"><h2>{title}</h2><div>
      <button type="button" className="workspace-change" aria-label="缩小地图" disabled={zoom <= 3} onClick={() => setZoom((z) => z - 1)}>−</button>
      <span aria-live="polite">{zoom} 级</span>
      <button type="button" className="workspace-change" aria-label="放大地图" disabled={zoom >= 18} onClick={() => setZoom((z) => z + 1)}>＋</button>
      <button type="button" className="workspace-change" onClick={() => { onSelect(null); setZoom(13); }}>城市中心</button>
      <button type="button" className="workspace-change" onClick={() => setRevision((r) => r + 1)}>重新加载</button>
    </div></div>
    <MapPreview key={`${selectedPlace?.id ?? cityId}-${zoom}-${revision}`} cityId={cityId} title={title} place={selectedPlace} zoom={zoom} />
    <p className="places-source">地图 © 高德地图 · 标记 A：{title} · 坐标系 GCJ-02</p>
    {selectedPlace && <p className="map-address">{selectedPlace.address ?? "地址待补充"}</p>}
    <PlacesPanel category="maps" cityId={cityId} cityName={cityName} onSelect={(place) => { onSelect(place); setZoom(15); }} />
  </section>;
}
