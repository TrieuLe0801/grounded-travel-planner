"""Accessible, presentation-only map for source-backed itinerary coordinates."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class MappedStop:
    """A chronological stop whose coordinates came from a visual provider."""

    number: int
    name: str
    day_index: int
    latitude: float
    longitude: float


def render_map_html(ordered_stops: Sequence[MappedStop]) -> str:
    """Return a self-contained iframe document; untrusted labels stay JSON data.

    The only map drawing code is static. Names enter the DOM through
    ``textContent`` and are never parsed as markup.
    """

    stops = [
        {
            "number": stop.number,
            "name": stop.name,
            "day": stop.day_index,
            "lat": stop.latitude,
            "lng": stop.longitude,
        }
        for stop in ordered_stops
        if type(stop.number) is int
        and 1 <= stop.number <= 999
        and type(stop.day_index) is int
        and 1 <= stop.day_index <= 7
        and math.isfinite(stop.latitude)
        and math.isfinite(stop.longitude)
        and -90 <= stop.latitude <= 90
        and -180 <= stop.longitude <= 180
    ]
    payload = json.dumps(stops, ensure_ascii=False).replace("<", "\\u003c")
    return _MAP_HTML.replace("__STOP_DATA__", payload)


_MAP_HTML = r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
 integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoD8ZxWfaiR+2M=" crossorigin="">
<style>
:root { color-scheme: light; --ink:#0f172a; --muted:#334155; --line:#d4dbe1;
  --paper:#fff7ed; --accent:#ea580c; --route:#0891b2; --focus:#9a3412; }
* { box-sizing:border-box; }
body { margin:0; font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
  background:var(--paper); color:var(--ink); }
.shell { display:grid; grid-template-columns:minmax(0,2fr) minmax(240px,1fr); gap:12px;
  height:100vh; padding:8px; }
.map-wrap { position:relative; min-width:0; min-height:300px; border:1px solid var(--line);
  border-radius:14px; overflow:hidden; background:#e8f4f7; }
#map { height:100%; width:100%; }
.panel { min-width:0; padding:12px; border:1px solid var(--line); border-radius:14px;
  background:white; overflow:auto; }
h2 { margin:0 0 4px; font-size:1.08rem; }
p { margin:0 0 12px; color:var(--muted); font-size:.9rem; }
.stop-list { display:grid; gap:8px; }
button { width:100%; min-height:48px; padding:9px 12px; text-align:left; color:var(--ink);
  border:1px solid var(--line); border-radius:10px; background:white;
  font:inherit; cursor:pointer; touch-action:manipulation; }
button:hover { background:#fff2df; }
button:active { background:#ffe1bf; }
button[aria-pressed="true"] { border:2px solid var(--accent); background:#fff0df;
  font-weight:650; }
button:focus-visible, input:focus-visible, a:focus-visible { outline:3px solid var(--focus);
  outline-offset:2px; }
.motion { display:flex; align-items:center; gap:8px; min-height:44px; margin:8px 0; }
.motion input { width:20px; height:20px; accent-color:var(--accent); }
.legend { font-size:.82rem; }
.legend a { color:#075c75; }
.marker { display:grid; place-items:center; width:30px; height:30px; border-radius:50%;
  border:2px solid white; background:#0891b2; color:white; font-weight:700;
  box-shadow:0 2px 8px #0f172a80; }
.car { display:grid; place-items:center; width:36px; height:36px; border-radius:50%;
  background:#fff; box-shadow:0 2px 8px #0f172a88; border:2px solid #ea580c; }
.car svg { width:23px; height:23px; }
.fallback { display:none; position:absolute; inset:0; padding:24px; background:#e8f4f7;
  align-items:center; justify-content:center; text-align:center; }
@media (max-width:640px) {
  .shell { grid-template-columns:minmax(0,1fr); grid-template-rows:310px minmax(0,1fr); }
  .map-wrap { min-height:0; }
  .panel { padding:10px; }
}
@media (prefers-reduced-motion:reduce) { *,*::before,*::after {
  scroll-behavior:auto !important; transition-duration:0ms !important; animation-duration:0ms !important;
} }
</style>
</head>
<body>
<main class="shell">
 <div class="map-wrap"><div id="map" aria-label="Bản đồ các điểm tham quan"></div>
  <div class="fallback" id="fallback">Không tải được nền bản đồ. Bạn vẫn có thể xem thứ tự điểm ở bên cạnh.</div>
 </div>
 <section class="panel" aria-labelledby="route-title">
  <h2 id="route-title">Lộ trình theo lịch</h2>
  <p>Đường nối thẳng chỉ minh họa thứ tự tham quan, không phải đường lái xe.</p>
  <label class="motion"><input type="checkbox" id="motion" checked> Hiệu ứng xe di chuyển</label>
  <div class="stop-list" id="stops"></div>
  <p id="status" role="status" aria-live="polite"></p>
  <p class="legend">Nền bản đồ © <a href="https://www.openstreetmap.org/copyright"
   target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a> ·
   <a href="https://leafletjs.com" target="_blank" rel="noopener noreferrer">Leaflet</a></p>
 </section>
</main>
<script id="stop-data" type="application/json">__STOP_DATA__</script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
 integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
(() => {
  'use strict';
  const stops = JSON.parse(document.getElementById('stop-data').textContent);
  const list = document.getElementById('stops');
  const status = document.getElementById('status');
  const motion = document.getElementById('motion');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const buttons = [];
  let car, map, frame = 0, generation = 0, selected = 0;

  function announce(index) {
    status.textContent = 'Xe đang ở điểm ' + stops[index].number + ': ' + stops[index].name;
    buttons.forEach((button, n) => button.setAttribute('aria-pressed', String(n === index)));
  }
  function select(index) {
    if (!car || !map) return;
    generation += 1;
    cancelAnimationFrame(frame);
    const ticket = generation;
    const start = car.getLatLng();
    const target = L.latLng(stops[index].lat, stops[index].lng);
    selected = index;
    announce(index);
    const animate = motion.checked && !reduced.matches;
    if (!animate) { car.setLatLng(target); return; }
    const from = map.latLngToLayerPoint(start);
    const to = map.latLngToLayerPoint(target);
    const distance = from.distanceTo(to);
    const duration = Math.min(1100, Math.max(350, distance * 2));
    let began;
    function step(now) {
      if (ticket !== generation) return;
      if (began === undefined) began = now;
      const progress = Math.min(1, (now - began) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const point = L.point(from.x + (to.x - from.x) * eased,
                            from.y + (to.y - from.y) * eased);
      car.setLatLng(map.layerPointToLatLng(point));
      if (progress < 1) frame = requestAnimationFrame(step);
      else car.setLatLng(target);
    }
    frame = requestAnimationFrame(step);
  }
  stops.forEach((stop, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Điểm ' + stop.number + ' · Ngày ' + stop.day + ' · ' + stop.name;
    button.addEventListener('click', () => select(index));
    button.setAttribute('aria-pressed', 'false');
    list.appendChild(button);
    buttons.push(button);
  });
  motion.addEventListener('change', () => {
    if (!motion.checked && car) {
      generation += 1;
      cancelAnimationFrame(frame);
      car.setLatLng([stops[selected].lat, stops[selected].lng]);
    }
  });
  reduced.addEventListener('change', () => {
    if (reduced.matches && car) {
      generation += 1;
      cancelAnimationFrame(frame);
      car.setLatLng([stops[selected].lat, stops[selected].lng]);
    }
  });
  if (!stops.length || typeof L === 'undefined') {
    document.getElementById('fallback').style.display = 'flex';
    if (!stops.length) status.textContent = 'Chưa có địa điểm có tọa độ xác minh.';
    return;
  }
  map = L.map('map', {scrollWheelZoom:false}).setView([stops[0].lat, stops[0].lng], 12);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom:18, attribution:'© OpenStreetMap contributors'
  }).addTo(map);
  const points = stops.map(stop => [stop.lat, stop.lng]);
  if (points.length > 1) {
    L.polyline(points, {color:'#0891b2',weight:3,dashArray:'6 7',opacity:.85}).addTo(map);
    map.fitBounds(points, {padding:[40,40],maxZoom:14});
  }
  stops.forEach((stop, index) => {
    const icon = L.divIcon({className:'', html:'<span class="marker">' + stop.number + '</span>',
      iconSize:[30,30],iconAnchor:[15,15]});
    L.marker([stop.lat, stop.lng], {icon, title:'Điểm ' + stop.number})
      .addTo(map).on('click', () => select(index));
  });
  const carIcon = L.divIcon({className:'',iconSize:[36,36],iconAnchor:[18,18],
    html:'<span class="car" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="#ea580c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 17h14l-1-7a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2l-1 7Z"/><path d="M3 12h2m14 0h2M8 17v2m8-2v2M7 13h10"/></svg></span>'});
  car = L.marker(points[0], {icon:carIcon,interactive:false,zIndexOffset:1000}).addTo(map);
  announce(0);
})();
</script>
</body>
</html>"""
