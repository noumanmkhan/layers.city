/* ---------- The map: MapLibre GL, drawn on the GPU ----------
   This part is the toolkit the rest of map.js draws with. It keeps the shape of the Leaflet calls the engine was
   written with (map.getZoom(), groups with addTo/remove, labels, markers) so the panel, card, search and links
   code reads the same, while every shape, name and icon is drawn by WebGL.

   - Zoom: the engine counts zoom the Leaflet way (config, links, CSS classes z9…z16 all use it). MapLibre's zoom is
     one less for the same scale (512 px tiles): LZ() converts, and `map` (the facade below) speaks Leaflet zoom.
   - Style: colours, widths and fonts are not copied here. Each look is read from the engine's CSS (template.html,
     city.css) by styling a hidden SVG path, label or icon with the same class names inside #map, once per zoom
     class (z9…z16). So light/dark, every city's colours, and CSS rules like "#map:not(.z13) .stn{display:none}"
     (which become the layer's zoom range) carry over, and a theme switch only repaints.
   - Panes: Leaflet's panes become anchor layers ("slot:<pane>"); a layer is inserted at the top of its pane.
     Names and icons all sit in one pane ("sym"), stacked by LABEL_PRIORITY: MapLibre places the topmost layer's
     names first, so that order is the declutter order.
   - Groups (G): what L.layerGroup was. A group's layers are made once and shown or hidden; points (names, icons,
     dots) are items in a shared source per pool, and showing one just puts it back in its source's data. */
/* The few geometry helpers the engine used from Leaflet (L.latLng, L.latLngBounds, L.point, L.geoJSON(f).getBounds()),
   so the library itself isn't loaded. Same shapes and method names as Leaflet's. */
const L = (() => {
  class LatLng {
    constructor(lat, lng){ this.lat = +lat; this.lng = +lng; }
    equals(o, m){ if (!o) return false; o = latLng(o); return Math.max(Math.abs(this.lat - o.lat), Math.abs(this.lng - o.lng)) <= (m == null ? 1e-9 : m); }
    distanceTo(o){ o = latLng(o); const k = Math.PI / 180, a = Math.sin((o.lat - this.lat) * k / 2) ** 2 + Math.cos(this.lat * k) * Math.cos(o.lat * k) * Math.sin((o.lng - this.lng) * k / 2) ** 2; return 12742000 * Math.asin(Math.sqrt(a)); }
    toString(){ return 'LatLng(' + this.lat + ', ' + this.lng + ')'; }
  }
  const latLng = (a, b) => a instanceof LatLng ? a : Array.isArray(a) ? new LatLng(a[0], a[1]) : a && typeof a === 'object' ? new LatLng(a.lat, a.lng != null ? a.lng : a.lon) : new LatLng(a, b);
  class Bounds {
    constructor(a, b){ this.s = Infinity; this.w = Infinity; this.n = -Infinity; this.e = -Infinity; if (a) (b ? [a, b] : a).forEach(p => this.extend(p)); }
    extend(p){ if (p instanceof Bounds){ this.extend([p.s, p.w]); return this.extend([p.n, p.e]); } p = latLng(p); this.s = Math.min(this.s, p.lat); this.n = Math.max(this.n, p.lat); this.w = Math.min(this.w, p.lng); this.e = Math.max(this.e, p.lng); return this; }
    getSouth(){ return this.s; } getNorth(){ return this.n; } getWest(){ return this.w; } getEast(){ return this.e; }
    getSouthWest(){ return new LatLng(this.s, this.w); } getNorthEast(){ return new LatLng(this.n, this.e); }
    getCenter(){ return new LatLng((this.s + this.n) / 2, (this.w + this.e) / 2); }
    isValid(){ return isFinite(this.s) && isFinite(this.w); }
    pad(r){ const dy = (this.n - this.s) * r, dx = (this.e - this.w) * r; return new Bounds([this.s - dy, this.w - dx], [this.n + dy, this.e + dx]); }
    contains(p){ if (p instanceof Bounds) return this.contains([p.s, p.w]) && this.contains([p.n, p.e]); p = latLng(p); return p.lat >= this.s && p.lat <= this.n && p.lng >= this.w && p.lng <= this.e; }
    intersects(b){ b = latLngBounds(b); return b.n >= this.s && b.s <= this.n && b.e >= this.w && b.w <= this.e; }
  }
  const latLngBounds = (a, b) => a instanceof Bounds ? a : new Bounds(a, b);
  class Point {
    constructor(x, y){ this.x = +x; this.y = +y; }
    add(o){ return new Point(this.x + o.x, this.y + o.y); } subtract(o){ return new Point(this.x - o.x, this.y - o.y); }
    multiplyBy(k){ return new Point(this.x * k, this.y * k); } divideBy(k){ return new Point(this.x / k, this.y / k); }
    distanceTo(o){ return Math.hypot(o.x - this.x, o.y - this.y); }
  }
  // Only getBounds() was used: the box around any GeoJSON geometry, feature or collection.
  const geoJSON = g => ({getBounds(){ const b = new Bounds(); const walk = c => typeof c[0] === 'number' ? b.extend([c[1], c[0]]) : c.forEach(walk);
    const geomOf = x => x.type === 'FeatureCollection' ? x.features.forEach(f => geomOf(f)) : x.type === 'Feature' ? geomOf(x.geometry) : x.type === 'GeometryCollection' ? x.geometries.forEach(geomOf) : walk(x.coordinates);
    geomOf(g); return b; }});
  return {latLng, latLngBounds, point: (x, y) => new Point(x, y), geoJSON, LatLng, LatLngBounds: Bounds};
})();
const LZ = z => z - 1, ZL = z => z + 1;
const LEVELS = [8, 9, 10, 11, 12, 13, 14, 15, 16];   // the engine's zoom classes: z9 … z16
const CLOSE = 1e-6;
const gl = new maplibregl.Map({
  container: 'map',
  style: {version: 8, glyphs: '/glyphs/{fontstack}/{range}.pbf', sources: {}, layers: [{id: 'water', type: 'background', paint: {'background-color': '#CFE7F7'}}]},
  bounds: [[CITY.view.city[0][1], CITY.view.city[0][0]], [CITY.view.city[1][1], CITY.view.city[1][0]]],
  minZoom: LZ(8.5), maxZoom: LZ(17), attributionControl: false, renderWorldCopies: false,
  dragRotate: false, pitchWithRotate: false, touchPitch: false, boxZoom: true, fadeDuration: 120,
});
gl.touchZoomRotate.disableRotation();
gl.keyboard.disableRotation && gl.keyboard.disableRotation();
const glReady = new Promise(r => gl.on('load', r));
const toLL = c => L.latLng(c.lat, c.lng);
const lngLat = x => { const p = L.latLng(x); return [p.lng, p.lat]; };
const lnglatBounds = b => { b = L.latLngBounds(b); return [[b.getWest(), b.getSouth()], [b.getEast(), b.getNorth()]]; };
const padOf = o => {
  if (!o) return 0;
  if (o.padding != null){ const p = [].concat(o.padding); return {top: p[1] ?? p[0], bottom: p[1] ?? p[0], left: p[0], right: p[0]}; }
  const tl = o.paddingTopLeft || [0, 0], br = o.paddingBottomRight || [0, 0];
  return {top: tl[1], left: tl[0], bottom: br[1], right: br[0]};
};
// MapLibre refuses padding wider than the map: shrink it to fit small screens.
const fitPad = p => { if (!p) return p; const c = gl.getContainer(), w = c.clientWidth, h = c.clientHeight;
  if (w < 100 || h < 100) return 0;
  const sx = p.left + p.right > w - 40 ? (w - 40) / (p.left + p.right) : 1, sy = p.top + p.bottom > h - 40 ? (h - 40) / (p.top + p.bottom) : 1;
  return {top: p.top * sy, bottom: p.bottom * sy, left: p.left * sx, right: p.right * sx}; };
const wrapE = e => { e = e || {}; if (e.lngLat) e.latlng = toLL(e.lngLat); if (e.point) e.containerPoint = L.point(e.point.x, e.point.y); return e; };
/* The facade: the Leaflet map calls the engine makes, answered by MapLibre. */
const map = {
  gl,
  getZoom: () => ZL(gl.getZoom()),
  getCenter: () => toLL(gl.getCenter()),
  getBounds: () => { const b = gl.getBounds(); return L.latLngBounds([b.getSouth(), b.getWest()], [b.getNorth(), b.getEast()]); },
  getSize: () => { const c = gl.getContainer(); return L.point(c.clientWidth, c.clientHeight); },
  getContainer: () => gl.getContainer(),
  setView(ll, z, o){ const v = {center: lngLat(ll), zoom: LZ(z == null ? map.getZoom() : z)}; if (o && o.animate === false) gl.jumpTo(v); else gl.easeTo(Object.assign(v, {duration: 350})); return map; },
  flyTo(ll, z, o){ gl.flyTo({center: lngLat(ll), zoom: LZ(z == null ? map.getZoom() : z), duration: ((o && o.duration) || .8) * 1000, essential: true}); return map; },
  fitBounds(b, o){ o = o || {}; gl.fitBounds(lnglatBounds(b), Object.assign({padding: fitPad(padOf(o)), duration: o.animate === false ? 0 : 350}, o.maxZoom != null ? {maxZoom: LZ(o.maxZoom)} : {})); return map; },
  flyToBounds(b, o){ o = o || {}; gl.fitBounds(lnglatBounds(b), Object.assign({padding: fitPad(padOf(o)), duration: (o.duration || .8) * 1000, essential: true}, o.maxZoom != null ? {maxZoom: LZ(o.maxZoom)} : {})); return map; },
  latLngToContainerPoint: ll => { const p = gl.project(lngLat(ll)); return L.point(p.x, p.y); },
  containerPointToLatLng: p => toLL(gl.unproject([p.x, p.y])),
  invalidateSize: () => { gl.resize(); return map; },
  setMaxBounds: b => { gl.setMaxBounds(lnglatBounds(b)); return map; },
  dragging: {disable: () => gl.dragPan.disable(), enable: () => gl.dragPan.enable(), moved: () => false},
  on(types, fn){ types.split(' ').forEach(t => { if (t === 'layeradd' || t === 'layerremove') return; if (t === 'preclick'){ PRECLICK.push(fn); return; } const h = e => fn(wrapE(e)); (fn._gl = fn._gl || {})[t] = h; gl.on(t, h); }); return map; },
  once(types, fn){ types.split(' ').forEach(t => gl.once(t, e => fn(wrapE(e)))); return map; },
  off(types, fn){ types.split(' ').forEach(t => { if (fn && fn._gl && fn._gl[t]) gl.off(t, fn._gl[t]); }); return map; },
  hasLayer: g => !!(g && g.live && g.live()),
  addLayer: g => { if (g) g.addTo(map); return map; },
  removeLayer: g => { if (g) g.remove(); return map; },
  eachLayer: () => {},
  closePopup: () => { POPUPS.forEach(p => p.remove()); POPUPS.clear(); },
  getPane: () => document.createElement('div'),
  attributionControl: {getContainer: () => gl.getContainer().querySelector('.maplibregl-ctrl-attrib') || document.createElement('div'), addAttribution(){}, setPrefix(){}},
};
window.cityMap = map;
const POPUPS = new Set(), PRECLICK = [];

/* ---------- styles read from the CSS ---------- */
const NS = 'http://www.w3.org/2000/svg';
const probe = document.createElement('div');
probe.className = 'gl-probe'; probe.setAttribute('aria-hidden', 'true');
probe.innerHTML = '<svg xmlns="' + NS + '" width="2" height="2"></svg>';
gl.getContainer().appendChild(probe);
const probeSvg = probe.firstChild;
const cvs = document.createElement('canvas'); cvs.width = cvs.height = 1;
const cctx = cvs.getContext('2d', {willReadFrequently: true});
const colourCache = new Map();
/* Any CSS colour (color-mix() comes back as color(srgb …)) as rgba() MapLibre can read. */
function colour(v){
  if (!v || v === 'none' || v === 'transparent' || v === 'rgba(0, 0, 0, 0)') return null;
  if (/^rgba?\(/.test(v)) return v;
  if (colourCache.has(v)) return colourCache.get(v);
  cctx.clearRect(0, 0, 1, 1); cctx.fillStyle = '#000'; cctx.fillStyle = v; cctx.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = cctx.getImageData(0, 0, 1, 1).data, out = 'rgba(' + r + ',' + g + ',' + b + ',' + +(a / 255).toFixed(3) + ')';
  colourCache.set(v, out);
  return out;
}
const SENTINEL = 0.123;   // a stroke width no CSS sets: the class didn't set one, so the layer's own weight applies
const PROBES = new Map();   // key -> {el, read, vals: {level: values}}
let probesDirty = false;
function makeProbe(key, build, read){
  let p = PROBES.get(key);
  if (!p){ p = {el: build(), read, vals: null}; PROBES.set(key, p); probesDirty = true; }
  return p;
}
const textOf = s => {
  const w = +s.fontWeight, it = s.fontStyle === 'italic';
  const font = 'Inter ' + (it ? (w >= 600 ? 'SemiBold' : 'Medium') + ' Italic' : w >= 700 ? 'Bold' : w >= 600 ? 'SemiBold' : w >= 500 ? 'Medium' : 'Regular');
  const sh = s.textShadow && s.textShadow !== 'none' ? s.textShadow : '';
  const halo = (sh.match(/(rgba?\([^)]*\)|color\([^)]*\)|#[0-9a-f]{3,8})/i) || [])[1];
  const size = parseFloat(s.fontSize) || 11;
  return {font, size, color: colour(s.color), halo: halo ? colour(halo) : null, upper: s.textTransform === 'uppercase',
    ls: s.letterSpacing === 'normal' ? 0 : (parseFloat(s.letterSpacing) || 0) / size, disp: s.display !== 'none' && s.visibility !== 'hidden',
    op: +s.opacity, lh: s.lineHeight === 'normal' ? 1.2 : (parseFloat(s.lineHeight) || size * 1.2) / size,
    wrap: s.whiteSpace === 'normal' ? (parseFloat(s.maxWidth) || 0) / size : 0};
};
// A path styled by its Leaflet class names.
function pathProbe(cls){
  return makeProbe('p:' + cls, () => { const el = document.createElementNS(NS, 'path'); el.setAttribute('class', cls); el.setAttribute('d', 'M0 0'); el.setAttribute('stroke-width', SENTINEL); probeSvg.appendChild(el); return el; },
    el => { const s = getComputedStyle(el), w = parseFloat(s.strokeWidth);
      return {fill: colour(s.fill), fo: +s.fillOpacity, stroke: colour(s.stroke), so: +s.strokeOpacity, w: Math.abs(w - SENTINEL) < 1e-3 ? null : w,
        dash: s.strokeDasharray && s.strokeDasharray !== 'none' ? s.strokeDasharray.split(/[ ,]+/).map(parseFloat) : null, op: +s.opacity, disp: s.display !== 'none' && s.visibility !== 'hidden'}; });
}
// A name, styled as the Leaflet tooltip with these classes.
function labelProbe(cls){
  return makeProbe('l:' + cls, () => { const el = document.createElement('div'); el.className = 'leaflet-tooltip lbl ' + cls; el.textContent = 'Ag'; probe.appendChild(el); return el; },
    el => textOf(getComputedStyle(el)));
}
// Any HTML (icons, shields, street names): read(el) picks what it needs from the probe element.
function htmlProbe(key, html, read){
  return makeProbe('h:' + key, () => { const d = document.createElement('div'); d.innerHTML = html; const el = d.firstElementChild; probe.appendChild(el); return el; }, read);
}
function evalProbes(all){
  const todo = [...PROBES.values()].filter(p => all || !p.vals);
  probesDirty = false;
  if (!todo.length) return;
  const el = gl.getContainer(), had = LEVELS.slice(1).map(t => el.classList.contains('z' + t));
  todo.forEach(p => { p.vals = {}; });
  LEVELS.forEach(l => {
    LEVELS.slice(1).forEach(t => el.classList.toggle('z' + t, l >= t));
    todo.forEach(p => { p.vals[l] = p.read(p.el); });
  });
  LEVELS.slice(1).forEach((t, i) => el.classList.toggle('z' + t, had[i]));
}
const vals = p => { if (!p.vals) evalProbes(false); return p.vals; };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
/* One value of a probe as a zoom expression: a constant, or a step across the zoom classes where the CSS changes it. */
function byZoom(p, f, dflt){
  const v = vals(p), out = LEVELS.map(l => { const x = f(v[l]); return x == null ? dflt : x; });
  if (out.every(x => same(x, out[0]))) return out[0];
  const e = ['step', ['zoom'], out[0]];
  for (let i = 1; i < out.length; i++) if (!same(out[i], out[i - 1])) e.push(LZ(LEVELS[i]), out[i]);
  return e;
}
const at = (p, f, l) => f(vals(p)[l == null ? Math.max(8, Math.min(16, Math.floor(map.getZoom() + CLOSE))) : l]);
// The zoom range the CSS shows a look in ("display:none" outside it), as [minzoom, maxzoom] for MapLibre.
function zoomRange(p){
  const v = vals(p), on = LEVELS.filter(l => v[l].disp);
  if (!on.length) return [24, 24];
  const lo = on[0], hi = on[on.length - 1];
  return [lo > 8 ? LZ(lo) : 0, hi < 16 ? LZ(hi + 1) : 24];
}
/* Weights: a number, or Leaflet zoom steps [[fromZoom, weight]…] as a GL expression. */
const steps = (pairs, k = 1) => typeof pairs === 'number' ? pairs * k : ['step', ['zoom'], pairs[0][1] * k, ...pairs.slice(1).flatMap(([z, w]) => [LZ(z), w * k])];

/* ---------- panes and layers ---------- */
const PANES = ['base', 'fill', 'streets', 'badges', 'lines', 'civic', 'hwy', 'pfdim', 'rail', 'mask', 'focus', 'hwytop', 'transit', 'evcourse', 'pfdim2', 'pfline', 'stlbl', 'pts', 'sym', 'pin'];
const symRank = new Map();   // sym layer id -> rank (0 = placed first)
const layerPane = new Map();
let nextId = 0;
const uid = p => p + (nextId++);
function slotAfter(pane){ const i = PANES.indexOf(pane); return i >= 0 && i + 1 < PANES.length ? 'slot:' + PANES[i + 1] : 'slot:end'; }
function addL(def, pane, rank){
  pane = pane || 'fill';
  let before = slotAfter(pane);
  if (pane === 'sym'){
    // Bottom to top: least important first. Go under the first layer that outranks this one.
    const r = rank == null ? 999 : rank;
    symRank.set(def.id, r);
    const order = gl.getStyle().layers.map(l => l.id).filter(id => symRank.has(id) && id !== def.id);
    const above = order.find(id => symRank.get(id) < r);
    if (above) before = above;
  }
  gl.addLayer(def, before);
  layerPane.set(def.id, pane);
  return def.id;
}
/* Stylers: each layer's look as a function of the probes; re-run on theme or state changes. */
const STYLERS = new Map();   // layer id -> fn returning {paint, layout, range}
const applied = new Map();
let holdStyles = false;
function styled(id, fn){ STYLERS.set(id, fn); if (!holdStyles) applyStyle(id); }
function applyStyle(id){
  const fn = STYLERS.get(id); if (!fn || !gl.getLayer(id)) return;
  const st = fn(); if (!st) return;
  const prev = applied.get(id) || {}, now = {};
  Object.entries(st.paint || {}).forEach(([k, v]) => { now['p:' + k] = v; if (!same(prev['p:' + k], v)) gl.setPaintProperty(id, k, v); });
  Object.entries(st.layout || {}).forEach(([k, v]) => { now['l:' + k] = v; if (!same(prev['l:' + k], v)) gl.setLayoutProperty(id, k, v); });
  if (st.range){ now.range = st.range; if (!same(prev.range, st.range)) gl.setLayerZoomRange(id, st.range[0], st.range[1]); }
  applied.set(id, now);
}
const BAKERS = new Set();   // per-feature colours baked into data: re-run with the styles
function restyle(all){
  evalProbes(all);
  gl.setPaintProperty('water', 'background-color', colour(getComputedStyle(gl.getContainer()).backgroundColor) || colour(getComputedStyle(document.documentElement).getPropertyValue('--water').trim()));
  STYLERS.forEach((fn, id) => applyStyle(id));
  BAKERS.forEach(f => f());
  ICONSETS.forEach(s => s.redraw());
}
let restyleQueued = false;
function queueRestyle(){ if (!restyleQueued){ restyleQueued = true; requestAnimationFrame(() => { restyleQueued = false; restyle(true); }); } }
// The look follows the theme and the map's state classes (city view, election, focus…); the zoom classes are sampled already.
new MutationObserver(queueRestyle).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', queueRestyle);
let lastCls = '';
new MutationObserver(() => {
  const c = [...gl.getContainer().classList].filter(k => !/^z\d+$/.test(k) && !k.startsWith('maplibregl')).sort().join(' ');
  if (c !== lastCls){ lastCls = c; queueRestyle(); }
}).observe(gl.getContainer(), {attributes: true, attributeFilter: ['class']});

/* ---------- groups ---------- */
class G {
  constructor(ids){ this.ids = ids || []; this.kids = new Set(); this.parent = null; this._on = false; this.ev = {}; this._v = false; }
  live(){ return this.parent ? this.parent.live() : this._on; }
  _sync(){
    const v = this.live();
    if (v !== this._v){ this._v = v; this.ids.forEach(id => { if (gl.getLayer(id)) gl.setLayoutProperty(id, 'visibility', v ? 'visible' : 'none'); }); if (this._vis) this._vis(v); }
    this.kids.forEach(k => k._sync());
  }
  addTo(){ const was = this.live(); this._on = true; this._sync(); if (!was) this.fire('add'); return this; }
  remove(){ if (this.parent){ this.parent.removeLayer(this); return this; } const was = this.live(); this._on = false; this._sync(); if (was) this.fire('remove'); return this; }
  addLayer(k){ if (!k) return this; if (k.parent && k.parent !== this) k.parent.kids.delete(k); const was = k.live(); this.kids.add(k); k.parent = this; k._sync(); if (!was && k.live()) k.fire('add'); return this; }
  removeLayer(k){ if (k && this.kids.delete(k)){ const was = k.live(); k.parent = null; k._on = false; k._sync(); if (was) k.fire('remove'); } return this; }
  hasLayer(k){ return this.kids.has(k); }
  clearLayers(){ [...this.kids].forEach(k => this.removeLayer(k)); return this; }
  eachLayer(f){ this.kids.forEach(f); return this; }
  getLayers(){ return [...this.kids]; }
  on(t, f){ t.split(' ').forEach(k => (this.ev[k] = this.ev[k] || []).push(f)); return this; }
  fire(t){ (this.ev[t] || []).forEach(f => f({target: this})); this.kids.forEach(k => { if (t === 'add' || t === 'remove') k.fire(t); }); }
}
const grp = ids => new G(ids);
// Layers are made hidden and shown by their group.
const hidden = def => Object.assign(def, {layout: Object.assign({visibility: 'none'}, def.layout || {})});

/* ---------- features, taps and hover names ---------- */
const FEAT = [];   // _gid -> the original feature (or point item)
const gidOf = f => { if (f.properties._gid == null){ f.properties._gid = FEAT.length; FEAT.push(f); } return f.properties._gid; };
const TAP = new Map(), HOVER = new Map(), DRAG = {moved: false};
const coarse = matchMedia('(pointer:coarse)').matches;
function hitAt(point, wanted){
  const ids = [...wanted.keys()].filter(id => gl.getLayer(id) && gl.getLayoutProperty(id, 'visibility') !== 'none');
  if (!ids.length) return null;
  const r = coarse ? 8 : 3, box = [[point.x - r, point.y - r], [point.x + r, point.y + r]];
  const hits = gl.queryRenderedFeatures(box, {layers: ids});
  for (const h of hits){ const gid = h.properties && h.properties._gid; if (gid != null && wanted.has(h.layer.id)) return [h.layer.id, FEAT[gid], h]; }
  return null;
}
let onMapTap = null;   // set by the engine (tapMap)
gl.on('click', e => {
  const ev = wrapE(e);
  PRECLICK.forEach(f => f(ev));
  const h = hitAt(e.point, TAP);
  if (h){ const r = TAP.get(h[0])(h[1], ev); if (r !== false) return; }
  if (onMapTap) onMapTap(ev);
});
const tip = document.createElement('div');
tip.className = 'leaflet-tooltip hover-tip gl-tip'; tip.hidden = true;
gl.getContainer().appendChild(tip);
let hoverQueued = null;
if (matchMedia('(hover:hover)').matches){
  gl.on('mousemove', e => {
    if (hoverQueued){ hoverQueued = e; return; }
    hoverQueued = e;
    requestAnimationFrame(() => {
      const ev = hoverQueued; hoverQueued = null;
      const h = hitAt(ev.point, HOVER), t = hitAt(ev.point, TAP);
      gl.getCanvas().style.cursor = h || (t && (!(t[1] instanceof Item) || t[1].p.tap)) ? 'pointer' : '';
      let txt = h && HOVER.get(h[0])(h[1]);
      if (typeof txt === 'function') txt = txt();
      if (!txt){ tip.hidden = true; return; }
      tip.innerHTML = txt; tip.hidden = false;
      tip.style.left = ev.point.x + 'px'; tip.style.top = (ev.point.y - 10) + 'px';
    });
  });
  gl.getCanvas().addEventListener('mouseleave', () => { tip.hidden = true; });
  gl.on('movestart', () => { tip.hidden = true; });
}

/* ---------- sources ---------- */
function source(fc){
  const id = uid('s');
  fc.features.forEach(gidOf);
  gl.addSource(id, {type: 'geojson', data: fc, tolerance: .3, buffer: 64});
  return id;
}
const kindOfGeom = g => !g ? null : /Polygon/.test(g.type) ? 'poly' : /LineString/.test(g.type) ? 'line' : 'pt';
const lineJoin = {'line-join': 'round', 'line-cap': 'round'};
/* Shapes, styled by their classes (what L.geoJSON with className did). Features are grouped by class string and
   each group gets its own layers, so a class's look can change with zoom (its CSS rules) like any other layer.
   opts: pane, cls(f), weight(f) (a number or Leaflet zoom steps, used where the CSS sets no stroke-width),
   radius(f) for points, hover(f), tap(f, e), interactive (false: taps fall through to the map). */
function geo(fc, opts){
  opts = opts || {};
  if (!fc.features) fc = {type: 'FeatureCollection', features: [fc.type === 'Feature' ? fc : {type: 'Feature', properties: {}, geometry: fc}]};
  // Each layer styles its own copy: the same features feed several layers (the base, the mask, the suburbs lens), and
  // MapLibre reads a source's data a moment later, so marks written on shared features would cross over.
  // FEAT (taps, hover names) still points at the original feature.
  fc = {type: 'FeatureCollection', features: fc.features.map(f => { gidOf(f); return {type: 'Feature', geometry: f.geometry, properties: Object.assign({}, f.properties)}; })};
  const src = source(fc), g = grp(), groups = new Map();
  g.src = src; g.fc = fc;
  const addL0 = addL;
  const addL_ = (def, pane, rank) => addL0(opts.minzoom ? Object.assign(def, {minzoom: LZ(opts.minzoom)}) : def, pane, rank);
  fc.features.forEach(f => {
    const k = kindOfGeom(f.geometry); if (!k) return;
    const c = opts.cls ? opts.cls(f) : '', key = k + '|' + c;
    if (!groups.has(key)) groups.set(key, {k, c, i: groups.size, f});
    f.properties._k = groups.get(key).i;
    if (opts.color){ const c = opts.color(f); if (c) f.properties._col = c; }
  });
  groups.forEach(({k, c, i, f}) => {
    const P = pathProbe(c), filter = ['==', ['get', '_k'], i], wt = opts.weight ? opts.weight(f) : 1;
    const width = () => { const css = byZoom(P, v => v.w, null); return css === null || (Array.isArray(css) && css.includes(null)) ? steps(wt) : css; };
    const opa = (a, b) => byZoom(P, v => (v.disp ? 1 : 0) * v.op * (a(v) == null ? 1 : a(v)), 1);
    if (k === 'poly'){
      const fid = addL_(hidden({id: uid('f'), type: 'fill', source: src, filter}), opts.pane);
      styled(fid, () => ({paint: {'fill-color': byZoom(P, v => v.fill, 'rgba(0,0,0,0)'), 'fill-opacity': byZoom(P, v => v.fill ? (v.disp ? 1 : 0) * v.op * v.fo : 0, 0)}}));
      g.ids.push(fid); if (opts.interactive !== false) reg(fid);
    }
    if (k === 'poly' || k === 'line'){
      const lid = addL_(hidden({id: uid('l'), type: 'line', source: src, filter, layout: Object.assign({}, lineJoin)}), opts.pane);
      styled(lid, () => { const d = at(P, v => v.dash, 13); const w = width();
        const dd = d || opts.dash; const lc = byZoom(P, v => v.stroke, 'rgba(0,0,0,0)');
        return {paint: Object.assign({'line-color': opts.color ? ['coalesce', ['get', '_col'], lc] : lc, 'line-width': w,
          'line-opacity': byZoom(P, v => (v.stroke || opts.color) ? (v.disp ? 1 : 0) * v.op * (v.stroke ? v.so : 1) : 0, 0)}, dd ? {'line-dasharray': dd.map(x => x / Math.max(1, typeof w === 'number' ? w : 3))} : {}), range: zoomRange(P)}; });
      g.ids.push(lid); if (opts.interactive !== false && k === 'line') reg(lid);
    }
    if (k === 'pt'){
      fc.features.forEach(x => { if (x.properties._k === i) x.properties._r = opts.radius ? opts.radius(x) : 4; });
      const cid = addL_(hidden({id: uid('c'), type: 'circle', source: src, filter}), opts.pane || 'pts');
      styled(cid, () => ({paint: {'circle-radius': opts.radiusZ ? steps(opts.radiusZ) : ['get', '_r'], 'circle-color': byZoom(P, v => v.fill, 'rgba(0,0,0,0)'), 'circle-opacity': opa(v => v.fill ? v.fo : 0),
        'circle-stroke-color': opts.color ? ['coalesce', ['get', '_col'], byZoom(P, v => v.stroke, 'rgba(0,0,0,0)')] : byZoom(P, v => v.stroke, 'rgba(0,0,0,0)'), 'circle-stroke-width': (() => { const w = byZoom(P, v => v.w, null); return w === null || Array.isArray(w) && w.includes(null) ? 1.5 : w; })(),
        'circle-stroke-opacity': opa(v => v.stroke ? v.so : 0)}, range: zoomRange(P)}));
      g.ids.push(cid); if (opts.interactive !== false) reg(cid);
    }
  });
  function reg(id){ if (opts.hover) HOVER.set(id, f => opts.hover(f)); if (opts.tap) TAP.set(id, opts.tap); }
  g.setData = d => { d.features.forEach(gidOf); g.fc = d; gl.getSource(src).setData(d); };
  return g;
}
/* Shapes whose class changes per feature at run time (lens tiers, party colours): one fill and one line layer, the
   colours baked into each feature from its current classes. g._recls() re-reads them. */
function baked(fc, opts){
  const src = source(fc), g = grp();
  const fid = addL(hidden({id: uid('bf'), type: 'fill', source: src, paint: {'fill-color': ['coalesce', ['get', '_fc'], 'rgba(0,0,0,0)'], 'fill-opacity': ['coalesce', ['get', '_fo'], 0]}}), opts.pane);
  const lid = addL(hidden({id: uid('bl'), type: 'line', source: src, layout: Object.assign({}, lineJoin),
    paint: {'line-color': ['coalesce', ['get', '_sc'], 'rgba(0,0,0,0)'], 'line-opacity': ['coalesce', ['get', '_so'], 0], 'line-width': ['coalesce', ['get', '_sw'], 1]}}), opts.pane);
  g.ids.push(fid, lid);
  const bake = () => {
    fc.features.forEach(f => { const P = pathProbe(opts.cls(f)); const v = at(P, x => x);
      Object.assign(f.properties, {_fc: v.fill, _fo: v.fill && v.disp ? v.op * v.fo : 0, _sc: v.stroke, _so: v.stroke && v.disp ? v.op * v.so : 0, _sw: v.w == null ? (opts.weight || 1) : v.w}); });
    if (gl.getSource(src)) gl.getSource(src).setData(fc);
  };
  BAKERS.add(bake);
  g._recls = () => { evalProbes(false); bake(); };
  g._recls();
  if (opts.interactive !== false){ if (opts.hover) HOVER.set(fid, opts.hover); if (opts.tap) TAP.set(fid, opts.tap); }
  return g;
}

/* ---------- point items: names, icons, dots ----------
   A pool is one source and a layer per look (class string); an item is shown by being in its pool's data. */
const POOLS = [];
/* Focus on a place (the engine sets FZ): each point item is 0 inside the place, 1 outside (faded, as the CSS's
   "#map.pfocus .fz-out" says for its kind), or 2 (hidden: a route number for a route that doesn't pass through). */
let FZ = null;
const refocus = () => POOLS.forEach(p => p.queue());
const fade = (base, k) => k >= .999 ? base : ['case', ['==', ['get', 'fz'], 1], base * k, base];
const fzLabel = cls => at(labelProbe(cls + ' fz-out'), v => v.op);
const fzPath = cls => at(pathProbe(cls + ' fz-out'), v => v.op);
const fzMarker = html => at(htmlProbe('fz:' + html, '<div class="leaflet-marker-icon fz-out">' + html + '</div>', el => ({op: +getComputedStyle(el).opacity, disp: true})), v => v.op);
class Pool {
  constructor(name, make){ this.name = name; this.make = make; this.items = new Set(); this.keys = new Map(); this.src = null; this.queued = false; POOLS.push(this); }
  ensure(){ if (!this.src){ this.src = uid('pool'); gl.addSource(this.src, {type: 'geojson', data: {type: 'FeatureCollection', features: []}, tolerance: 0, buffer: 128}); } }
  key(k, item){
    this.ensure();
    if (!this.keys.has(k)){ const i = this.keys.size; this.keys.set(k, i); this.make(this.src, ['==', ['get', '_k'], i], item, i); }
    return this.keys.get(k);
  }
  set(item, on){ if (on) this.items.add(item); else this.items.delete(item); this.queue(); }
  queue(){ if (!this.queued){ this.queued = true; Promise.resolve().then(() => { this.queued = false; this.flush(); }); } }
  flush(){ this.ensure(); gl.getSource(this.src).setData({type: 'FeatureCollection', features: [...this.items].map(it => {
    const z = FZ ? FZ(it) : 0; if (z === 2) return null; const f = it.feature(); f.properties.fz = z; return f; }).filter(Boolean)}); }
}
class Item extends G {
  constructor(pool, at, props){ super(); this.pool = pool; this.at = at; this.p = props; this.properties = props; this._gid = FEAT.length; FEAT.push(this); this._k = pool.key(props._key, this); }
  _vis(v){ this.pool.set(this, v); }
  feature(){ const ll = L.latLng(this.at); return {type: 'Feature', geometry: {type: 'Point', coordinates: [ll.lng, ll.lat]}, properties: Object.assign({}, this.p.data || {}, {_gid: this._gid, _k: this._k, t: this.p.text || '', s: this.p.sort || 0, img: this.p.img || ''})}; }
  setLatLng(ll){ this.at = ll; if (this._v) this.pool.queue(); return this; }
  getLatLng(){ return L.latLng(this.at); }
  setContent(t){ this.p.text = plain(t); if (this._v) this.pool.queue(); return this; }
  getElement(){ return null; }
  bindTooltip(t){ this.p.hover = t; return this; }
}
const plain = t => { if (t == null) return ''; const d = document.createElement('div'); d.innerHTML = String(t).replace(/<br\s*\/?>/gi, '\n'); return d.textContent; };
/* Where a name, icon or line badge ranks in the declutter order (LABEL_PRIORITY, defined by the engine). */
function rankOf(el){
  const i = LABEL_PRIORITY.findIndex(sel => { try { return el.matches(sel) || !!el.querySelector(sel); } catch (e) { return false; } });
  return i < 0 ? LABEL_PRIORITY.length : i;
}
const textLayout = (t, extra) => Object.assign({'text-font': [t.font], 'text-letter-spacing': t.ls, 'text-transform': t.upper ? 'uppercase' : 'none', 'text-line-height': t.lh,
  'text-max-width': t.wrap || 100}, extra || {});
const textPaint = t => ({'text-color': t.color || '#000', 'text-halo-color': t.halo || 'rgba(0,0,0,0)', 'text-halo-width': t.halo ? 1.5 : 0, 'text-halo-blur': .5, 'text-opacity': t.op == null ? 1 : t.op});
/* Names (what permanent Leaflet tooltips were): one layer per class string and direction. */
const NAMES = new Pool('names', (src, filter, item) => {
  const cls = item.p.cls, P = labelProbe(cls), id = uid('n'), dir = item.p.dir || 'center', off = item.p.offset || [0, 0];
  const anchor = dir === 'right' ? 'left' : dir === 'left' ? 'right' : dir === 'top' ? 'bottom' : dir === 'bottom' ? 'top' : 'center';
  addL(({id, type: 'symbol', source: src, filter, layout: {'text-field': ['get', 't'], 'symbol-sort-key': ['get', 's'], 'text-anchor': anchor, 'text-padding': 2, 'text-rotate': ['coalesce', ['get', 'rot'], 0]}}), 'sym', rankOf(P.el));
  styled(id, () => { const t = at(P, x => x); const size = byZoom(P, v => v.size, 11);
    const hide = item.p.hideOn && gl.getContainer().classList.contains(item.p.hideOn);
    return {layout: textLayout(t, {'text-size': size, 'text-offset': [off[0] / t.size, off[1] / t.size], visibility: hide ? 'none' : 'visible'}), paint: Object.assign(textPaint(t), {'text-opacity': fade(t.op, fzLabel(cls))}), range: zoomRange(P)}; });
  NAMES.ids.add(id);
  TAP.set(id, it => it.p.tap ? it.p.tap() : false);
});
NAMES.ids = new Set();
function label(text, cls, latlng, opts){
  opts = opts || {};
  const it = new Item(NAMES, latlng, {text: plain(text), cls, dir: opts.direction, offset: opts.offset, sort: opts.sort || 0, data: opts.rotate ? {rot: +opts.rotate} : null, hideOn: opts.hideOn,
    _key: cls + '|' + (opts.direction || '') + '|' + (opts.offset || '') + '|' + (opts.hideOn || ''), interactive: opts.interactive});
  return it;
}
/* Icons with a name beside them (the engine's .lm markers): the icon is drawn from the CSS of ".lm <classes> i",
   the name styled from ".lm <classes> b". One layer per class string; the glyph picks the image. */
const ICONSETS = [], LMSETS = new Map();
const imgCache = new Map();
/* Add an image to the map's sprite, or replace it in place. Removing an image a layer uses and adding it back leaves
   that layer's symbols unplaced until its tiles reload, so a same-size redraw (a theme change) updates instead. */
function putImage(key, img, opts){
  const w = img.width, h = img.height;
  if (gl.hasImage(key)){
    const cur = gl.getImage(key), d = cur && cur.data;
    if (d && d.width === w && d.height === h){ gl.updateImage(key, img); return; }
    gl.removeImage(key);
  }
  gl.addImage(key, img, Object.assign({pixelRatio: PR}, opts || {}));
}
function svgImage(key, svgText, opts){
  return new Promise(res => { const im = new Image(); im.onload = () => {
    // Through a canvas, so updateImage gets pixels it can compare by size.
    const c = document.createElement('canvas'); c.width = im.naturalWidth || im.width; c.height = im.naturalHeight || im.height;
    c.getContext('2d').drawImage(im, 0, 0); putImage(key, c.getContext('2d').getImageData(0, 0, c.width, c.height), opts); res();
  }; im.onerror = () => res(); im.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgText); });
}
const PR = Math.min(3, Math.max(2, Math.ceil(devicePixelRatio || 1)));
// The rings a CSS box-shadow draws ("0 0 0 1.5px colour"): [[colour, spread]…], innermost first.
const rings = sh => !sh || sh === 'none' ? [] : sh.split(/,(?![^(]*\))/).map(s => s.trim()).map(s => {
  const c = (s.match(/(rgba?\([^)]*\)|color\([^)]*\)|#[0-9a-f]{3,8})/i) || [])[1], n = s.replace(c || '', '').trim().split(/\s+/).map(parseFloat);
  return n.length >= 4 && n[0] === 0 && n[1] === 0 && n[2] === 0 && n[3] > 0 ? [colour(c), n[3]] : null; }).filter(Boolean);
function boxSvg(s, glyphSvg, gs){
  const w = parseFloat(s.width) || 18, h = parseFloat(s.height) || 18, rad = Math.min(w, h) / 2, br = s.borderRadius.includes('%') ? rad : Math.min(parseFloat(s.borderRadius) || 0, rad);
  const rs = rings(s.boxShadow), out = rs.reduce((a, r) => Math.max(a, r[1]), 0), pad = out + 1, W = w + 2 * pad, H = h + 2 * pad;
  const bw = parseFloat(s.borderTopWidth) || 0, bc = colour(s.borderTopColor), dashed = s.borderTopStyle === 'dashed';
  const rr = (k, fill, stroke, sw, dash) => '<rect x="' + (pad - k) + '" y="' + (pad - k) + '" width="' + (w + 2 * k) + '" height="' + (h + 2 * k) + '" rx="' + (br ? br + k : 0) + '" fill="' + (fill || 'none') + '"' + (stroke ? ' stroke="' + stroke + '" stroke-width="' + sw + '"' + (dash ? ' stroke-dasharray="3 2"' : '') : '') + '/>';
  let body = rs.slice().reverse().map(([c, sp]) => rr(sp, c)).join('');
  body += rr(0, colour(s.backgroundColor) || 'none');
  if (bw && bc) body += rr(-bw / 2, null, bc, bw, dashed);
  const g = glyphSvg ? '<g transform="translate(' + (pad + (w - gs) / 2) + ' ' + (pad + (h - gs) / 2) + ') scale(' + gs / 24 + ')" fill="' + (colour(s.color) || '#000') + '" stroke="' + (colour(s.color) || '#000') + '" stroke-width="0" color="' + (colour(s.color) || '#000') + '">' + glyphSvg + '</g>' : '';
  return {svg: '<svg xmlns="' + NS + '" width="' + W * PR + '" height="' + H * PR + '" viewBox="0 0 ' + W + ' ' + H + '">' + body + g + '</svg>', W, H, w, h};
}
const ICONS = new Pool('icons', (src, filter, item) => {
  const {cls, wrap, glyphs} = item.p, id = uid('i');
  const P = htmlProbe('lm:' + cls, '<span class="' + wrap + ' ' + cls + '"><i></i><b>Ag</b></span>', el => {
    const i = el.querySelector('i'), b = el.querySelector('b'), si = getComputedStyle(i), sv = i.querySelector('svg');
    return Object.assign(textOf(getComputedStyle(b)), {box: {width: si.width, height: si.height, borderRadius: si.borderRadius, boxShadow: si.boxShadow, backgroundColor: si.backgroundColor, color: si.color,
      borderTopWidth: si.borderTopWidth, borderTopColor: si.borderTopColor, borderTopStyle: si.borderTopStyle}, gap: parseFloat(getComputedStyle(el).columnGap) || 6, gs: sv ? parseFloat(getComputedStyle(sv).width) : 13,
      idisp: getComputedStyle(el).display !== 'none' && si.display !== 'none', bdisp: getComputedStyle(b).display !== 'none'});
  });
  P.el.querySelector('i').innerHTML = '<svg viewBox="0 0 24 24"></svg>';
  addL(({id, type: 'symbol', source: src, filter, layout: {'icon-image': ['get', 'img'], 'text-field': ['get', 't'], 'symbol-sort-key': ['get', 's'],
    'text-anchor': 'left', 'text-optional': true, 'icon-padding': 1, 'text-padding': 2}}), 'sym', rankOf(P.el));
  const set = {glyphs: new Set(), queued: false,
    redraw(){ const v = at(P, x => x, 14); set.glyphs.forEach(gk => { const b = boxSvg(v.box, GLYPH[gk] || '', v.gs); svgImage('lm|' + cls + '|' + gk, b.svg); }); },
    want(gk){ if (set.glyphs.has(gk)) return; set.glyphs.add(gk); if (!set.queued){ set.queued = true; Promise.resolve().then(() => { set.queued = false; set.redraw(); }); } }};
  ICONSETS.push(set); LMSETS.set(cls, set);
  styled(id, () => {
    const v = at(P, x => x, 14), bx = boxSvg(v.box, '', v.gs);
    // The name shows from the zoom the CSS shows "b", the icon from the zoom it shows the marker.
    const txtOn = LEVELS.filter(l => vals(P)[l].bdisp && vals(P)[l].idisp), iconOn = LEVELS.filter(l => vals(P)[l].idisp);
    const lo = iconOn.length ? iconOn[0] : 99, tlo = txtOn.length ? txtOn[0] : 99;
    return {layout: textLayout(v, {'text-size': byZoom(P, x => x.size, 11), 'text-offset': [(bx.w / 2 + v.gap) / v.size, 0],
      'text-field': tlo <= 8 ? ['get', 't'] : ['step', ['zoom'], '', LZ(tlo), ['get', 't']]}), paint: Object.assign(textPaint(v), (k => ({'text-opacity': fade(v.op, k), 'icon-opacity': fade(1, k)}))(fzMarker('<span class="' + wrap + ' ' + cls + '"></span>'))), range: [lo > 8 ? LZ(lo) : 0, 24]};
  });
  if (item.p.tapping) TAP.set(id, it => it.p.tap ? it.p.tap() : false);
  HOVER.set(id, it => it.p.hover);
});
function icon(latlng, cls, glyph, name, opts){
  opts = opts || {};
  const it = new Item(ICONS, latlng, {cls, wrap: opts.wrap || 'lm', text: plain(name), sort: opts.sort || 0, img: 'lm|' + cls + '|' + glyph, _key: cls, hover: opts.hover, tap: opts.tap, tapping: true});
  LMSETS.get(cls).want(glyph);
  return it;
}
/* Dots (what circleMarkers were): one layer per class string, radius per item. */
const DOTS = new Pool('dots', (src, filter, item) => {
  const P = pathProbe(item.p.cls), id = uid('d');
  addL(({id, type: 'circle', source: src, filter, paint: {'circle-radius': ['get', 'r']}}), item.p.pane || 'pts');
  styled(id, () => ({paint: {'circle-color': byZoom(P, v => v.fill, 'rgba(0,0,0,0)'), 'circle-opacity': fade(at(P, v => v.fill ? v.op * v.fo : 0), fzPath(item.p.cls)),
    'circle-stroke-color': ['coalesce', ['get', 'col'], byZoom(P, v => v.stroke, 'rgba(0,0,0,0)')], 'circle-stroke-width': byZoom(P, v => v.w == null ? 1.5 : v.w, 1.5),
    'circle-stroke-opacity': fade(at(P, v => v.stroke ? v.op * v.so : 0), fzPath(item.p.cls))}, range: zoomRange(P)}));
  TAP.set(id, it => it.p.tap ? it.p.tap() : false);
  HOVER.set(id, it => it.p.hover);
});
function dot(latlng, cls, r, opts){
  opts = opts || {};
  return new Item(DOTS, latlng, {cls, data: opts.color ? {r, col: opts.color} : {r}, pane: opts.pane, _key: cls + '|' + (opts.pane || ''), hover: opts.hover, tap: opts.tap});
}
/* Highway shields: the CSS ".shield <classes>" box, stretched around the route number. */
const SHIELDS = new Pool('shields', (src, filter, item) => {
  const cls = item.p.cls, wrap = item.p.wrap || 'shield', id = uid('h'), img = 'sh|' + wrap + '|' + cls;
  const P = htmlProbe('sh:' + wrap + '|' + cls, '<span class="' + wrap + ' ' + cls + '">Ag</span>', el => { const s = getComputedStyle(el);
    return Object.assign(textOf(s), {box: {width: '20px', height: s.height, borderRadius: s.borderTopLeftRadius || s.borderRadius, boxShadow: s.boxShadow, backgroundColor: s.backgroundColor, color: s.color,
      borderTopWidth: s.borderTopWidth, borderTopColor: s.borderTopColor, borderTopStyle: s.borderTopStyle}, minw: parseFloat(s.minWidth) || 20, padx: parseFloat(s.paddingLeft) || 4}); });
  addL(({id, type: 'symbol', source: src, filter, layout: {'icon-image': img, 'icon-text-fit': 'both', 'text-field': ['get', 't'], 'symbol-sort-key': ['get', 's'], 'text-padding': 2, 'icon-padding': 1}}), 'sym', rankOf(P.el));
  const set = {redraw(){ const v = at(P, x => x, 13), b = boxSvg(v.box, '', 0), pad = (b.W - b.w) / 2, h = b.h;
    const st = Math.round((pad + Math.min(h / 2, 6)) * PR), en = Math.round((b.W - pad - Math.min(h / 2, 6)) * PR);
    svgImage(img, b.svg, {stretchX: [[st, en]], stretchY: [[Math.round((pad + h / 2 - 1) * PR), Math.round((pad + h / 2 + 1) * PR)]],
      content: [Math.round((pad + v.padx) * PR), Math.round(pad * PR), Math.round((b.W - pad - v.padx) * PR), Math.round((b.H - pad) * PR)]}); }};
  ICONSETS.push(set); Promise.resolve().then(() => set.redraw());
  styled(id, () => { const v = at(P, x => x, 13); return {layout: textLayout(v, {'text-size': byZoom(P, x => x.size, 11)}), paint: (k => ({'text-color': v.color, 'text-opacity': fade(v.op, k), 'icon-opacity': fade(v.op, k)}))(fzMarker('<span class="' + wrap + ' ' + cls + '"></span>')), range: zoomRange(P)}; });
  TAP.set(id, it => it.p.tap ? it.p.tap() : false);
  HOVER.set(id, it => it.p.hover);
});
const shield = (latlng, cls, text, wrap, opts) => new Item(SHIELDS, latlng, Object.assign({cls, wrap, text: plain(text), _key: (wrap || 'shield') + '|' + cls}, opts || {}));

/* ---------- HTML markers (the pin, voting marks): real elements, few of them ---------- */
class Mk extends G {
  constructor(latlng, html, opts){
    super(); opts = opts || {};
    const el = document.createElement('div'); el.className = 'gl-mk ' + (opts.className || ''); el.innerHTML = html;
    if (opts.size) Object.assign(el.style, {width: opts.size[0] + 'px', height: opts.size[1] + 'px'});
    this.el = el; this.at = L.latLng(latlng);
    this.m = new maplibregl.Marker({element: el, anchor: opts.anchor || 'center', offset: opts.offset || [0, 0]}).setLngLat(lngLat(this.at));
    if (opts.z != null) el.style.zIndex = opts.z;
    if (!opts.interactive) el.style.pointerEvents = 'none';
  }
  _vis(v){ if (v) this.m.addTo(gl); else this.m.remove(); }
  setLatLng(ll){ this.at = L.latLng(ll); this.m.setLngLat(lngLat(this.at)); return this; }
  getLatLng(){ return this.at; }
  getElement(){ return this.el; }
}
const mk = (latlng, html, opts) => new Mk(latlng, html, opts);
/* A filled circle of a given radius in metres (the "you are here" accuracy ring). */
function circlePoly(latlng, m){
  const c = L.latLng(latlng), k = 111320, pts = [];
  for (let i = 0; i <= 64; i++){ const a = i / 64 * 2 * Math.PI; pts.push([c.lng + Math.cos(a) * m / (k * Math.cos(c.lat * Math.PI / 180)), c.lat + Math.sin(a) * m / k]); }
  return {type: 'Feature', properties: {}, geometry: {type: 'Polygon', coordinates: [pts]}};
}
/* A popup (info boxes for some points), in the engine's .info-pop style. */
function popup(latlng, html, opts){
  const p = new maplibregl.Popup({closeButton: true, maxWidth: ((opts && opts.maxWidth) || 300) + 'px', className: 'info-pop gl-pop', offset: (opts && opts.offset) || 10})
    .setLngLat(lngLat(latlng)).setHTML(html).addTo(gl);
  POPUPS.add(p); p.on('close', () => POPUPS.delete(p));
  return p;
}
/* Before the first build: panes as anchors, zoom buttons, credits. */
glReady.then(() => {
  PANES.forEach(n => gl.addLayer({id: 'slot:' + n, type: 'background', layout: {visibility: 'none'}, paint: {'background-color': '#000'}}));
  gl.addLayer({id: 'slot:end', type: 'background', layout: {visibility: 'none'}, paint: {'background-color': '#000'}});
});
const slotAfterLast = () => 'slot:end';
/* Line badges (subway lines, route numbers): bullets and pills drawn on a canvas with the page's own font, then
   placed by MapLibre along each line. look(): {labels, bg, fg} for a feature; the image is redrawn with the theme. */
const bcv = document.createElement('canvas').getContext('2d');
function badgeImage(id, labs, bg, fg, ring, big){
  const H = big ? 20 : 18, r = 1.5, gap = 2;
  const fn = l => String(l).length > 2 ? '700 ' + (big ? 11.5 : 10.5) + 'px Inter, system-ui, sans-serif' : '700 ' + (big ? 12 : 11) + 'px Inter, system-ui, sans-serif';
  const ws = labs.map(l => { bcv.font = fn(l); return String(l).length > 2 ? Math.ceil(bcv.measureText(String(l)).width) + 12 : H; });
  const W = ws.reduce((a, b) => a + b, 0) + gap * (labs.length - 1) + 2 * r + 2, HH = H + 2 * r + 2;
  const c = document.createElement('canvas'); c.width = Math.ceil(W * PR); c.height = Math.ceil(HH * PR);
  const x = c.getContext('2d'); x.scale(PR, PR);
  let px = r + 1;
  labs.forEach((l, i) => {
    const w = ws[i], y = r + 1, rad = H / 2;
    const pill = (k, fill) => { x.beginPath(); if (x.roundRect) x.roundRect(px - k, y - k, w + 2 * k, H + 2 * k, rad + k); else x.rect(px - k, y - k, w + 2 * k, H + 2 * k); x.fillStyle = fill; x.fill(); };
    if (ring) pill(r, ring);
    pill(0, bg);
    x.fillStyle = fg; x.font = fn(l); x.textAlign = 'center'; x.textBaseline = 'middle';
    x.fillText(String(l), px + w / 2, y + H / 2 + .5);
    px += w + gap;
  });
  putImage(id, x.getImageData(0, 0, c.width, c.height));
}
const inkOn = c => { const m = String(c || '').match(/\d+(\.\d+)?/g); if (!m || m.length < 3) return '#fff';
  const [r, g, b] = m.slice(0, 3).map(Number); return (r * 299 + g * 587 + b * 114) / 1000 > 165 ? '#111' : '#fff'; };
function badges(src, fc, keyOf, look, opts){
  opts = opts || {};
  const id = uid('b'), keys = new Map();
  fc.features.forEach(f => { const k = keyOf(f); f.properties._b = 'bd|' + id + '|' + k; if (!keys.has(k)) keys.set(k, f); });
  // Badges read their key from a source of their own: the caller's source (a line layer's) was built from its own copy
  // of these features before they had one, so a badge layer on it found nothing to draw.
  src = source(fc);
  const draw = () => { const ring = colour(getComputedStyle(document.documentElement).getPropertyValue('--city').trim()) || '#fff';
    keys.forEach((f, k) => { const L_ = look(f); badgeImage('bd|' + id + '|' + k, L_.labels, L_.bg, L_.fg || inkOn(L_.bg), ring, opts.big); }); };
  const set = {redraw: () => (document.fonts ? document.fonts.ready : Promise.resolve()).then(draw)};
  ICONSETS.push(set); set.redraw();
  addL(hidden({id, type: 'symbol', source: src, filter: opts.filter || ['has', '_b'], minzoom: opts.minzoom || 0, maxzoom: opts.maxzoom || 24,
    layout: {'symbol-placement': opts.points ? 'point' : 'line', 'symbol-spacing': opts.spacing || 700, 'icon-image': ['get', '_b'], 'icon-rotation-alignment': 'viewport',
      'icon-padding': 2, 'symbol-avoid-edges': true}}), 'sym', opts.rank == null ? 1 : opts.rank);
  if (opts.hover) HOVER.set(id, opts.hover);
  return id;
}

/* Plain boxes (small HTML marks such as ".cl-pin"): the element's CSS box as an icon, no text. */
const BOXES = new Pool('boxes', (src, filter, item) => {
  const cls = item.p.cls, inner = item.p.inner || '', id = uid('x'), img = 'bx|' + cls;
  const P = htmlProbe('bx:' + cls, '<span class="' + cls + '">' + inner + '</span>', el => { const s = getComputedStyle(el), a = getComputedStyle(el, '::after'), sv = el.querySelector('svg'), ss = sv && getComputedStyle(sv);
    return {disp: s.display !== 'none' && s.visibility !== 'hidden', op: +s.opacity, w: parseFloat(s.width) || 7,
      after: a.content && a.content !== 'none' && a.content !== 'normal' ? a.content.replace(/^["']|["']$/g, '') : '', ac: colour(a.color), af: a.fontWeight, as: parseFloat(a.fontSize) || 8,
      g: ss && ss.display !== 'none' ? colour(ss.fill) : null,
      box: {width: s.width, height: s.height, borderRadius: s.borderTopLeftRadius, boxShadow: s.boxShadow,
      backgroundColor: s.backgroundColor, color: s.color, borderTopWidth: s.borderTopWidth, borderTopColor: s.borderTopColor, borderTopStyle: s.borderTopStyle}}; });
  addL({id, type: 'symbol', source: src, filter, layout: {'icon-image': img, 'icon-allow-overlap': true, 'symbol-sort-key': ['get', 's'], 'text-allow-overlap': true}}, item.p.pane || 'pts');
  // Drawn at its biggest look (zoom 16) and scaled down by zoom; a glyph inside (svg) once the CSS shows it.
  const glyphAt = () => LEVELS.find(l => vals(P)[l].g);
  const set = {redraw(){ const v = at(P, x => x, 16), b = boxSvg(v.box, '', 0); svgImage(img, b.svg);
    const gl_ = glyphAt(); if (gl_ && inner){ const gv = vals(P)[gl_]; const gs = parseFloat(v.box.width) * .7;
      svgImage(img + '|g', boxSvg(Object.assign({}, v.box, {color: gv.g}), inner.replace(/<svg[^>]*>|<\/svg>/g, '').replace('<path', '<path transform="scale(2)"'), gs).svg); } }};
  ICONSETS.push(set); Promise.resolve().then(() => set.redraw());
  styled(id, () => { const big = at(P, x => x.w, 16), gl_ = glyphAt(), aft = LEVELS.find(l => vals(P)[l].after), av = aft && vals(P)[aft];
    return {layout: Object.assign({'icon-size': byZoom(P, v => v.w / big, 1), 'icon-image': gl_ && inner ? ['step', ['zoom'], img, LZ(gl_), img + '|g'] : img},
      av ? {'text-field': ['step', ['zoom'], '', LZ(aft), av.after], 'text-font': [+av.af >= 700 ? 'Inter Bold' : 'Inter SemiBold'], 'text-size': byZoom(P, v => v.as, 8)} : {}),
      paint: Object.assign({'icon-opacity': fade(at(P, v => v.op), fzMarker('<span class="' + cls + '"></span>'))}, av ? {'text-color': av.ac || '#000'} : {}), range: zoomRange(P)}; });
  TAP.set(id, it => it.p.tap ? it.p.tap() : false);
  HOVER.set(id, it => it.p.hover);
});
const box = (latlng, cls, opts) => { opts = opts || {}; return new Item(BOXES, latlng, {cls, inner: opts.inner, hover: opts.hover, tap: opts.tap, pane: opts.pane, sort: opts.sort, _key: cls + '|' + (opts.pane || '')}); };
/* Remove a group's layers for good (when it's rebuilt). */
function drop(g){ if (!g) return; g.remove(); g.kids.forEach(drop); g.ids.forEach(id => { if (gl.getLayer(id)) gl.removeLayer(id); STYLERS.delete(id); TAP.delete(id); HOVER.delete(id); }); g.ids = []; }
/* A whole file of same-looking icons in one layer (heritage diamonds, bike docks…): the icon from the CSS of
   "<wrap cls> i", the name from "<wrap cls> b" (shown from the zoom the CSS shows it). opts: wrap, cls, glyph,
   text(f), minzoom (Leaflet zoom), pane, hover(f), tap(f, e), sort(f). */
function iconLayer(fc, opts){
  const wrap = opts.wrap || 'lm', cls = opts.cls || '', key = wrap + '|' + cls, img = 'il|' + key + '|' + (opts.glyph || '');
  fc.features.forEach(f => { f.properties._t = opts.text ? opts.text(f) || '' : ''; if (opts.sort) f.properties._s = opts.sort(f); });
  const src = source(fc), id = uid('il');
  const P = htmlProbe('il:' + key, '<span class="' + wrap + ' ' + cls + '"><i><svg viewBox="0 0 24 24"></svg></i><b>Ag</b></span>', el => {
    const i = el.querySelector('i'), b = el.querySelector('b'), si = getComputedStyle(i), sv = i.querySelector('svg');
    return Object.assign(textOf(getComputedStyle(b)), {box: {width: si.width, height: si.height, borderRadius: si.borderRadius, boxShadow: si.boxShadow, backgroundColor: si.backgroundColor, color: si.color,
      borderTopWidth: si.borderTopWidth, borderTopColor: si.borderTopColor, borderTopStyle: si.borderTopStyle, transform: si.transform},
      gap: parseFloat(getComputedStyle(el).columnGap) || 5, gs: sv ? parseFloat(getComputedStyle(sv).width) || 12 : 12,
      idisp: getComputedStyle(el).display !== 'none' && si.display !== 'none', bdisp: getComputedStyle(b).display !== 'none'});
  });
  addL(hidden({id, type: 'symbol', source: src, minzoom: opts.minzoom ? LZ(opts.minzoom) : 0, layout: {'icon-image': img, 'text-anchor': 'left', 'text-optional': true,
    'symbol-sort-key': ['coalesce', ['get', '_s'], 0], 'icon-padding': 1, 'text-padding': 2}}), opts.pane || 'sym', opts.rank == null ? 8 : opts.rank);
  const set = {redraw(){ const v = at(P, x => x, 15); let b = boxSvg(v.box, GLYPH[opts.glyph] || '', v.gs);
    // A rotated square (a diamond) keeps its CSS turn.
    if (/matrix/.test(v.box.transform || '')) b = {svg: b.svg.replace('<rect', '<rect transform="rotate(45 ' + b.W / 2 + ' ' + b.H / 2 + ')"').replace(/(<rect)(?![^>]*transform)/g, '$1 transform="rotate(45 ' + b.W / 2 + ' ' + b.H / 2 + ')"')};
    svgImage(img, b.svg); }};
  ICONSETS.push(set); Promise.resolve().then(() => set.redraw());
  styled(id, () => { const v = at(P, x => x, 15), bx = boxSvg(v.box, '', v.gs);
    const tOn = LEVELS.filter(l => vals(P)[l].bdisp && vals(P)[l].idisp), tlo = tOn.length ? tOn[0] : 99;
    return {layout: textLayout(v, {'text-size': byZoom(P, x => x.size, 11), 'text-offset': [(bx.w / 2 + v.gap) / v.size, 0],
      'text-field': tlo <= 8 ? ['get', '_t'] : ['step', ['zoom'], '', LZ(tlo), ['get', '_t']]}), paint: textPaint(v)}; });
  if (opts.hover) HOVER.set(id, opts.hover);
  if (opts.tap) TAP.set(id, opts.tap);
  return grp([id]);
}
/* Election chips (the election view's ward labels): a chip in the election colour with the seat's name, shrinking to
   its number zoomed out, and from zoom 13 a card under it with the race. Drawn on a canvas with the page's font, in
   the theme's --elect-chip, --elect-chip-ink, --elect-card and --ink; shown only while #map has "elect". */
const CHIP_ITEMS = [];
function chipImages(it){
  const cs = getComputedStyle(document.documentElement), v = n => colour(cs.getPropertyValue(n).trim());
  const chip = v('--elect-chip') || '#5B21B6', ink = v('--elect-chip-ink') || '#fff', card = v('--elect-card') || '#fff', text = v('--ink') || '#222';
  const F = 'Inter, system-ui, sans-serif', {head, num, lines} = it.p.chip;
  const draw = (key, chipText, size, pad, rad, withCard) => {
    bcv.font = '800 ' + size + 'px ' + F;
    const cw = Math.ceil(bcv.measureText(chipText).width) + 2 * pad[0], ch = Math.ceil(size * 1.1) + pad[1] + pad[2];
    bcv.font = '600 11.5px ' + F;
    const lw = withCard && lines.length ? Math.ceil(Math.max(...lines.map(l => bcv.measureText(l).width))) + 18 : 0, lh = withCard && lines.length ? lines.length * 16 + 11 : 0;
    const W = Math.max(cw, lw) + 4, H = ch + (lh ? lh + 5 : 0) + 4;
    const c = document.createElement('canvas'); c.width = Math.ceil(W * PR); c.height = Math.ceil(H * PR);
    const x = c.getContext('2d'); x.scale(PR, PR);
    const rr = (x0, y0, w, h, r, fill, stroke) => { x.beginPath(); if (x.roundRect) x.roundRect(x0, y0, w, h, r); else x.rect(x0, y0, w, h); if (fill){ x.fillStyle = fill; x.fill(); } if (stroke){ x.lineWidth = 1.5; x.strokeStyle = stroke; x.stroke(); } };
    rr((W - cw) / 2, 2, cw, ch, rad, chip);
    x.fillStyle = ink; x.font = '800 ' + size + 'px ' + F; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(chipText, W / 2, 2 + pad[1] + size * .55);
    if (lh){
      const y0 = 2 + ch + 5;
      rr((W - lw) / 2 + .75, y0 + .75, lw - 1.5, lh - 1.5, 7, card, chip);
      x.fillStyle = text; x.font = '600 11.5px ' + F; x.textBaseline = 'alphabetic';
      lines.forEach((l, i) => x.fillText(l, W / 2, y0 + 5 + 12 + i * 16));
    }
    putImage('ec|' + it._gid + '|' + key, x.getImageData(0, 0, c.width, c.height));
  };
  draw('s', num, 13, [7, 2, 3], 6, false);
  draw('h', head, 16, [9, 3, 4], 7, false);
  draw('H', head, 19, [11, 4, 5], 7, false);
  draw('f', head, 19, [11, 4, 5], 7, true);
}
const CHIPS = new Pool('chips', (src, filter, item) => {
  const id = uid('ec'), img = k => ['concat', 'ec|', ['to-string', ['get', '_gid']], '|' + k];
  addL({id, type: 'symbol', source: src, filter, minzoom: LZ(10), layout: {visibility: 'none', 'icon-image': ['step', ['zoom'], img('s'), LZ(11), img('h'), LZ(12), img('H'), LZ(13), img('f')],
    'icon-padding': 2, 'symbol-sort-key': ['get', 's']}}, 'sym', item.p.rank == null ? 2 : item.p.rank);
  styled(id, () => ({layout: {visibility: gl.getContainer().classList.contains('elect') ? 'visible' : 'none'}}));
  ICONSETS.push({redraw: () => (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => CHIP_ITEMS.forEach(chipImages))});
  TAP.set(id, it => it.p.tap ? it.p.tap() : false);
  HOVER.set(id, it => it.p.hover);
});
function chip(latlng, head, num, lines, opts){
  const it = new Item(CHIPS, latlng, Object.assign({chip: {head, num: String(num), lines}, _key: 'chip'}, opts || {}));
  CHIP_ITEMS.push(it);
  (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => chipImages(it));
  return it;
}
