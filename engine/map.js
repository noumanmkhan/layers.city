/* Layers.City map engine. Everything city-specific comes from CITY (cities/<city>/city.json),
   inlined above this script by engine/assemble.py, and from the city's data/ folder. */
(() => {
const DATA = 'data/';
const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
/* Feature counts (docs/stats.js, which also enforces this): an event name and short config ids, true/false
   or a tour step number only. Never place names, search text, pins or coordinates. Logged where a person acts, not
   where the tour, a View or a shared link replays the same functions. */
const logEvent = (name, data) => { try { if (window.lcTrack) window.lcTrack(name, data); } catch (e) {} };

/* Text templates from the config: "{name}" fills from a feature's properties, "{f.num}" walks into
   nested objects, a list becomes "a, b". A part in [square brackets] is dropped when a field inside it
   is missing; a missing field outside brackets blanks the whole text. */
function fill(tpl, ctx){
  const val = k => k.split('.').reduce((o, p) => o == null ? undefined : o[p], ctx);
  const sub = (s, miss) => s.replace(/\{([\w.]+)\}/g, (m, k) => {
    const v = val(k);
    if (v == null || v === '') { miss(); return ''; }
    return Array.isArray(v) ? v.join(', ') : v;
  });
  let missing = false;
  const out = sub(tpl.replace(/\[([^\]]*)\]/g, (m, inner) => { let gone = false; const r = sub(inner, () => { gone = true; }); return gone ? '' : r; }), () => { missing = true; });
  return missing ? '' : out;
}

const LAYERS = CITY.groups.flatMap(([, items]) => items);
const byKind = k => LAYERS.find(it => it.kind === k);
const UNITS = byKind('units'), METRO = byKind('metro');
const AREA_KINDS = ['fill', 'units', 'outline', 'patches', 'districts'];   // polygon layers the "What's here" card tests against
/* School board wards ("boards" kind): one file holds every board's wards, each feature tagged with its
   board. The panel shows one board at a time (it.boards: [id, short, long], the first is the default);
   the card looks up the spot's ward in every board. */
const BOARDS = LAYERS.filter(it => it.kind === 'boards');
const boardPick = {};
BOARDS.forEach(it => { boardPick[it.id] = it.boards[0][0]; });
const boardOf = (it, id) => it.boards.find(b => b[0] === id);
const boardCtx = (it, f) => { const b = boardOf(it, f.properties.board) || []; return Object.assign({}, f.properties, {short: b[1], long: b[2]}); };
function boardHits(it, x, y){
  const out = {}, fc = data.layers[it.id]; if (!fc) return out;
  fc.features.forEach(f => { if (!out[f.properties.board] && contains(f.geometry, x, y)) out[f.properties.board] = f; });
  return out;
}

/* Neighbourhood lenses (tiers from the city's profile data). One shows at a time. */
const LENSES = {};
CITY.lens.lenses.forEach(L_ => { LENSES[L_.id] = L_; });
/* A transit lens with "hubs" lets the viewer pick where the trip ends (New York: Penn Station or Grand Central).
   Each hub carries its own figures (key, minutes) and words (short, note, filter); the first is the default, and
   the lens's own fields repeat it for apps and the static pages. The pick is remembered in this browser. */
const HUB_STORE = 'hub:' + CITY.id;
const hubLens = CITY.lens.lenses.find(L_ => L_.hubs && L_.hubs.length > 1);
function useHub(L_, id){
  const h = L_.hubs.find(x => x.id === id) || L_.hubs[0];
  ['key', 'minutes', 'short', 'note', 'source'].forEach(k => { if (h[k] != null) L_[k] = h[k]; });
  L_.hub = h.id;
  return h;
}
const hubOf = L_ => L_.hubs.find(h => h.id === L_.hub) || L_.hubs[0];
if (hubLens){ let saved = null; try { saved = localStorage.getItem(HUB_STORE); } catch (e) {} useHub(hubLens, saved); }
const FILTERS = CITY.lens.filters;
/* A "pick a type" lens (e.g. housing type) shades units by the share of one category the viewer picks:
   d[L_.field] is a list of shares, L_.pick names the categories in the same order, L_.cuts splits a
   share into the lens's tiers. Every other lens reads a precomputed tier, d[L_.key]. */
const pick = {};
CITY.lens.lenses.forEach(L_ => { if (L_.pick) pick[L_.id] = L_.pick[0][0]; });
function keyOf(L_, d){
  if (!d) return null;
  if (!L_.pick) return d[L_.key];
  const i = L_.pick.findIndex(p => p[0] === pick[L_.id]), v = d[L_.field] && d[L_.field][i];
  if (v == null) return null;
  const t = L_.cuts.findIndex(c => v < c);
  return L_.tiers[t < 0 ? L_.tiers.length - 1 : t][0];
}
const FIRST_LENS = CITY.lens.lenses[0].id;
// Each lens tier's fill colour, written once from the config.
const tierCss = document.createElement('style');
tierCss.textContent = CITY.lens.lenses.map(L_ => L_.tiers.map(([k, , v]) => '.lens.' + L_.id + '-' + k + '{fill:var(' + v + ')}').join(' ')).join('\n');
document.head.appendChild(tierCss);
// The shortlist: tiers picked in any lens, plus a maximum for a "minutes" lens. Empty means "any".
const filt = {};
const clearFilters = () => FILTERS.forEach(f => { filt[f.lens] = f.max ? 0 : new Set(); });
clearFilters();
const filtOn = () => FILTERS.some(f => f.max ? filt[f.lens] > 0 : filt[f.lens].size);
// A "top" filter on a pick lens (housing type) keeps units whose largest share is one of the picked categories.
const topOf = (L_, d) => { const v = d[L_.field]; if (!v || !v.length) return null;
  let i = 0; v.forEach((x, j) => { if (x > v[i]) i = j; }); return L_.pick[i][0]; };
FILTERS.forEach(f => { if (f.top && !f.options) f.options = LENSES[f.lens].pick.map(([v, t]) => [v, t]); });
const matches = d => !!d && FILTERS.every(f => {
  const L_ = LENSES[f.lens];
  if (f.max) return !filt[f.lens] || (d[L_.minutes] != null && d[L_.minutes] <= filt[f.lens]);
  if (f.top) return !filt[f.lens].size || filt[f.lens].has(topOf(L_, d));
  return !filt[f.lens].size || filt[f.lens].has(keyOf(L_, d));
});
const lensClass = d => { const L_ = LENSES[lens], k = keyOf(L_, d); return 'lens ' + (k ? L_.id + '-' + k : 'none') + (filtOn() && !matches(d) ? ' out' : ''); };
let lens = FIRST_LENS;
const TIER_LABEL = {};
Object.values(LENSES).forEach(L_ => (L_.hubs ? L_.hubs.map(h => h.key) : [L_.key]).forEach(key => L_.tiers.forEach(([k, label, v]) => { TIER_LABEL[key + ':' + k] = [label, v]; })));
const tierOf = d => { const L_ = LENSES[lens], k = keyOf(L_, d); if (!k) return '';
  return L_.pick ? pickLabel(L_) + ': ' + TIER_LABEL[L_.key + ':' + k][0] : TIER_LABEL[L_.key + ':' + k][0]; };
const pickOf = L_ => L_.pick.find(p => p[0] === pick[L_.id]) || L_.pick[0];
const pickLabel = L_ => pickOf(L_)[1], pickLong = L_ => pickOf(L_)[2] || pickOf(L_)[1].toLowerCase();

const map = L.map('map', {zoomSnap:.25, zoomDelta:.5, minZoom:8.5, maxZoom:17, attributionControl:true, zoomControl:false, preferCanvas:false});
// Bottom-left, just beside the layer panel: the panel covers the top-left corner and the What's here card the right side. Phones pinch to zoom, so the buttons are hidden there.
L.control.zoom({position:'bottomleft'}).addTo(map);
map.attributionControl.setPrefix(false);
window.cityMap = map;
map.attributionControl.addAttribution(CITY.attribution);
const CITY_BOUNDS = L.latLngBounds(CITY.view.city);
const REGION_VIEW = L.latLngBounds(CITY.view.region);
const wide = () => !matchMedia('(max-width:760px)').matches;
map.fitBounds(CITY_BOUNDS, wide() ? {paddingTopLeft:[330,20], paddingBottomRight:[350,20]} : {paddingTopLeft:[0,150], paddingBottomRight:[0,90]});
map.setMaxBounds(L.latLngBounds(CITY.view.max));  // the region plus a margin

const panes = [['base',200],['fill',350],['lines',420],['streets',400],['badges',410],['civic',430],['hwy',450],['pfdim',455],['rail',460],['mask',465],['focus',468],['hwytop',469],['transit',470],['evcourse',471],['pfdim2',472],['pfline',473],['stlbl',475],['pts',480],['pin',620]];
panes.forEach(([n,z]) => { map.createPane(n); map.getPane(n).style.zIndex = z; });
map.getPane('base').style.pointerEvents = 'none';
map.getPane('stlbl').style.pointerEvents = 'none';
map.getPane('badges').style.pointerEvents = 'none';
map.getPane('mask').style.pointerEvents = 'none';
map.getPane('focus').style.pointerEvents = 'none';
['pfdim', 'pfdim2', 'pfline'].forEach(n => { map.getPane(n).style.pointerEvents = 'none'; });

const layers = {}; const data = {layers: {}};
const get = f => fetch(DATA + (f.includes('.') ? f : f + '.geojson')).then(r => { if (!r.ok) throw new Error(f); return r.json(); });

function zoomClasses(){
  const z = map.getZoom(), el = map.getContainer();
  [9,10,11,12,13,14,15,16].forEach(t => el.classList.toggle('z'+t, z >= t - .01));
}
map.on('zoomend', zoomClasses); zoomClasses();

/* Label declutter: after each move, place labels in priority order and hide any that would overlap
   a label already placed. Icons stay; hovering an icon still shows its name. */
const LABEL_PRIORITY = ['.lbl-focus', '.sub-b', '#map.elect .lbl-ward.el', '.rt-b.pick', '.lm.t1 b', '.lm.t2 b', '.lm.tw.sup b', '.lm.inst b', '.lm.tw b', '.lbl-stn.end', '.lbl-go.end', '.shield', '.lbl-stn', '.lbl-go', '.rt-b', '.lbl-cult', '.lbl-area', '.lbl-nbhd', '.lbl-ward, .lbl-prov, .lbl-fed, .lbl-sbw', '.lbl-bia', '.lbl-hd'];
let declutterQueued = false;
function declutter(){
  declutterQueued = false;
  const box = map.getContainer().getBoundingClientRect(), kept = [], seen = new Set();
  const el = map.getContainer();
  el.querySelectorAll('.clash').forEach(n => n.classList.remove('clash'));
  // Focused on a place: every label inside it is placed before any outside it.
  const passes = el.classList.contains('pfocus') ? [n => !n.closest('.fz-out'), n => !!n.closest('.fz-out')] : [() => true];
  passes.forEach(pass => LABEL_PRIORITY.forEach(sel => el.querySelectorAll(sel).forEach(n => {
    if (seen.has(n) || !pass(n)) return;  // e.g. a line-end label matches both '.lbl-stn.end' and '.lbl-stn'
    seen.add(n);
    const r = n.getBoundingClientRect();
    if (!r.width || r.right < box.left || r.left > box.right || r.bottom < box.top || r.top > box.bottom) return;
    const pad = 2;
    if (kept.some(k => r.left < k.right + pad && r.right > k.left - pad && r.top < k.bottom + pad && r.bottom > k.top - pad)) n.classList.add('clash');
    else kept.push(r);
  })));
}
function queueDeclutter(){ if (!declutterQueued){ declutterQueued = true; requestAnimationFrame(() => requestAnimationFrame(declutter)); } }
map.on('zoomend moveend layeradd layerremove', queueDeclutter);

function label(text, cls, latlng){
  return L.tooltip({permanent:true, direction:'center', className:'lbl ' + cls, pane:'tooltipPane', interactive:false}).setLatLng(latlng).setContent(text);
}
const ll = p => [p[1], p[0]];
function hoverTip(layer, text){ layer.bindTooltip(text, {sticky:true, className:'hover-tip', direction:'top', offset:[0,-8]}); }

function polyLayer(fc, opts){
  const g = L.layerGroup();
  const geo = L.geoJSON(fc, {pane: opts.pane || 'fill', style: f => ({className: opts.cls(f), weight: 1}),
    onEachFeature: (f, lyr) => { if (opts.hover) hoverTip(lyr, opts.hover(f)); lyr.on('click', tapMap); }});
  g.addLayer(geo);
  if (opts.label) fc.features.forEach(f => { const t = opts.label(f); if (!t) return;
    const lb = label(t, opts.lcls(f), ll(f.properties.lp));
    if (opts.focusId) tapToFocus(lb, opts.focusId, f);
    g.addLayer(lb); });
  return g;
}

/* ---------- geometry helpers for "What's here" ---------- */
function inRing(x, y, r){ let ins = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++){ const xi=r[i][0], yi=r[i][1], xj=r[j][0], yj=r[j][1]; if (((yi>y)!==(yj>y)) && (x < (xj-xi)*(y-yi)/(yj-yi)+xi)) ins = !ins; } return ins; }
function inPoly(x, y, c){ if (!inRing(x, y, c[0])) return false; for (let k = 1; k < c.length; k++) if (inRing(x, y, c[k])) return false; return true; }
function contains(geom, x, y){ if (!geom) return false; if (geom.type === 'Polygon') return inPoly(x, y, geom.coordinates); if (geom.type === 'MultiPolygon') return geom.coordinates.some(c => inPoly(x, y, c)); return false; }
function hit(fc, x, y){ return fc ? fc.features.find(f => contains(f.geometry, x, y)) : null; }
function metres(a, b){ const k = Math.PI/180, dx = (a[0]-b[0])*k*Math.cos(a[1]*k)*6371000, dy = (a[1]-b[1])*k*6371000; return Math.hypot(dx, dy); }

/* ---------- build layers ---------- */
function buildBase(fc, regions){
  const g = L.geoJSON(fc, {pane:'base', interactive:false, style: f => ({className: {city:'base-city', neighbour:'base-out', outside:'base-far', annex:'base-annex'}[f.properties.kind]})});
  g.addTo(map);
  // An annex (kind annex): land beyond the city limits that the map treats as part of the city view (Vancouver's
  // University Endowment Lands): shaded and outlined apart, never masked, and inside the footprint, so taps there get
  // the full card. The city's units file names it (as one of its units); city-only layers simply stop at the line.
  // A municipality marked minor (a small town in a dense region, such as New Jersey's boroughs) is named from zoom 12 only.
  fc.features.filter(f => f.properties.kind === 'neighbour').forEach(f => label(f.properties.name, 'lbl-muni' + (f.properties.minor ? ' minor' : ''), ll(f.properties.lp)).addTo(map));
  regions.features.forEach(f => label(f.properties.name, 'lbl-region', ll(f.geometry.coordinates)).addTo(map));
  // A water label may turn to follow a river ("rotate", degrees clockwise) and be set smaller (cls "river").
  (CITY.water || []).forEach(w => label(w.rotate ? '<span class="rot" style="transform:rotate(' + (+w.rotate) + 'deg)">' + esc(w.name) + '</span>' : w.name, 'lbl-lake ' + w.cls, w.at).addTo(map));
  map.on('click', tapMap);
}

const GLYPH = {
  university: '<path d="M12 3 1 9l11 6 9-4.9V16h2V9zM5 13.2V17l7 4 7-4v-3.8L12 17z"/>',
  college: '<path d="M2 5.5c3.2-1.6 6.6-1.4 9.2.8V20c-2.6-2.1-6-2.3-9.2-.8zm20 0c-3.2-1.6-6.6-1.4-9.2.8V20c2.6-2.1 6-2.3 9.2-.8z"/>',
  hospital: '<path d="M9.5 3h5v6.5H21v5h-6.5V21h-5v-6.5H3v-5h6.5z"/>',
  sports: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 2.2a7.8 7.8 0 0 1 7.2 4.8H4.8A7.8 7.8 0 0 1 12 4.2zM4.8 15h14.4a7.8 7.8 0 0 1-14.4 0z"/>',
  park: '<path d="M12 2 6.5 9.5h3L5 16h6v6h2v-6h6l-4.5-6.5h3z"/>',
  music: '<path d="M20 2 8 4.3v11.1A3.5 3.5 0 1 0 10 18.5V9.2l8-1.5v5.7a3.5 3.5 0 1 0 2 3.1z"/>',
  civic: '<path d="M12 1.5 2 6.5V9h20V6.5zM4 10.5v7h3v-7zm6.5 0v7h3v-7zm6.5 0v7h3v-7zM2 19v2.5h20V19z"/>',
  campus: '<path d="M12 3 1 9l11 6 9-4.9V16h2V9zM5 13.2V17l7 4 7-4v-3.8L12 17z"/>',
  culture: '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
  airport: '<path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/>',
  // Places of worship, by the symbol each faith's own map signage uses, and the food-shop basket.
  mosque: '<path d="M16.53 4.66A9.5 9.5 0 1 0 16.53 19.34 7.5 7.5 0 1 1 16.53 4.66z"/><path d="M18.9 8.6l.8 2.15 2.3.08-1.8 1.42.62 2.2-1.92-1.28-1.92 1.28.62-2.2-1.8-1.42 2.3-.08z"/>',
  gurdwara: '<path fill-rule="evenodd" d="M12 7.6a5.4 5.4 0 1 1 0 10.8 5.4 5.4 0 0 1 0-10.8zm0 1.8a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2z"/><path d="M12 1.5 13.5 4.8v12.4L12 20l-1.5-2.8V4.8z"/><path fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" d="M5.2 8.6c-2.6 5.4-.2 11 6 12.6M18.8 8.6c2.6 5.4.2 11-6 12.6"/>',
  synagogue: '<path d="M12 1.5 15 6.7h6l-3 5.3 3 5.3h-6l-3 5.2-3-5.2H3l3-5.3-3-5.3h6z"/>',
  hindu: '<path d="M12 1.5l1.3 2.4h-2.6zM10.3 5h3.4l3.4 7H6.9zM5 13h14v2.2H5zM6.4 16.2h11.2V22h-3.9v-3.4h-3.4V22H6.4z"/>',
  buddhist: '<path fill-rule="evenodd" d="M12 2.5a9.5 9.5 0 1 1 0 19 9.5 9.5 0 0 1 0-19zm0 2.1a7.4 7.4 0 1 0 0 14.8 7.4 7.4 0 0 0 0-14.8zM12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6z"/><path fill="none" stroke="currentColor" stroke-width="1.6" d="M14.6 12h4.8M13.84 13.84l3.39 3.39M12 14.6v4.8M10.16 13.84l-3.39 3.39M9.4 12H4.6M10.16 10.16 6.77 6.77M12 9.4V4.6M13.84 10.16l3.39-3.39"/>',
  church: '<path d="M10.4 1.5h3.2v5h5v3.2h-5V22.5h-3.2V9.7h-5V6.5h5z"/>',
  elementary: '<path d="M12 2 3 7.2V9h18V7.2zM4.5 10.5h15V21h-5v-5h-5v5h-5zm2 1.5v2.5h2.5V12zm8.5 0v2.5h2.5V12z"/>',
  secondary: '<path d="M2 7h20v2.5H2zM3 10.5h18V21h-6.5v-4.5h-5V21H3zm2 1.5v2.5h2.5V12zm4.25 0v2.5h2.5V12zm4.25 0v2.5H16V12zm3.75 0v2.5H19V12zM12 2l5 4H7z"/>',
  library: '<path d="M3 4.5c3.2-.6 6.2-.2 8 1.4V20c-1.8-1.4-4.8-1.8-8-1.2zm18 0c-3.2-.6-6.2-.2-8 1.4V20c1.8-1.4 4.8-1.8 8-1.2z"/>',
  centre: '<path d="M12 2 1.5 10.2h2.6V22h15.8V10.2h2.6zM9.5 12a2.5 2.5 0 1 1 5 0 2.5 2.5 0 0 1-5 0zm-2 8c0-2.6 2-4.2 4.5-4.2s4.5 1.6 4.5 4.2z"/>',
  // A community centre (category cc, where a city's centre already means something else): a hall with two people.
  cc: '<path fill-rule="evenodd" d="M12 2 1.5 10.2h2.6V22h15.8V10.2h2.6zM7.2 12.6a1.8 1.8 0 1 0 3.6 0 1.8 1.8 0 1 0-3.6 0zm6 0a1.8 1.8 0 1 0 3.6 0 1.8 1.8 0 1 0-3.6 0zM6 20c0-2 1.3-3.4 3-3.4s3 1.4 3 3.4zm6 0c0-2 1.3-3.4 3-3.4s3 1.4 3 3.4z"/>',
  otherfaith: '<path d="M12 2 2.5 9.2v12.8h7v-6.2h5V22h7V9.2z"/>',
  halal: '<path d="M2.5 9h19v2.3h-1.2L18.6 21H5.4L3.7 11.3H2.5zM6.6 8.2 10.4 2.6l1.5 1-3.1 4.6zm10.8 0-3.8-5.6-1.5 1 3.1 4.6z"/>',
  kosher: '<path d="M2.5 9h19v2.3h-1.2L18.6 21H5.4L3.7 11.3H2.5zM6.6 8.2 10.4 2.6l1.5 1-3.1 4.6zm10.8 0-3.8-5.6-1.5 1 3.1 4.6z"/>',
  // Schools: a mortarboard, one colour for French-language schools and one for immersion.
  frschool: '<path d="M12 2 1.5 7.5 12 13l8.5-4.45V15h2V7.5zM5.5 12.1v4.4L12 20l6.5-3.5v-4.4L12 15.5z"/>',
  immersion: '<path d="M12 2 1.5 7.5 12 13l8.5-4.45V15h2V7.5zM5.5 12.1v4.4L12 20l6.5-3.5v-4.4L12 15.5z"/>',
  // Sports & recreation, one glyph per sport.
  pool: '<path d="M2 15.5c2.5 0 2.5-1.6 5-1.6s2.5 1.6 5 1.6 2.5-1.6 5-1.6 2.5 1.6 5 1.6v2.2c-2.5 0-2.5-1.6-5-1.6s-2.5 1.6-5 1.6-2.5-1.6-5-1.6-2.5 1.6-5 1.6zm0 4.3c2.5 0 2.5-1.6 5-1.6s2.5 1.6 5 1.6 2.5-1.6 5-1.6 2.5 1.6 5 1.6V22c-2.5 0-2.5-1.6-5-1.6S14.5 22 12 22s-2.5-1.6-5-1.6S4.5 22 2 22zM13.6 3.2l2.2-.8 3.4 9.2-2.2.8-.9-2.5-6.8 2.6-1.3-1.9 7.3-2.8zM5.5 8.5a2.5 2.5 0 1 1 5 0 2.5 2.5 0 0 1-5 0z"/>',
  rink: '<path d="M6 3h4v7.5l8.4 2.2c1.6.4 2.6 1.8 2.6 3.4V17H6zM3 19h17.5a1.5 1.5 0 0 0 1.5-1.5h1.5a3 3 0 0 1-3 3H3z"/>',
  diamond: '<path fill-rule="evenodd" d="M12 2.5 21.5 12 12 21.5 2.5 12zm0 3.4L5.9 12l6.1 6.1 6.1-6.1z"/><circle cx="12" cy="12" r="2"/>',
  field: '<path fill-rule="evenodd" d="M2 5h20v14H2zm2 2v10h7V14.9a3 3 0 0 1 0-5.8V7zm9 0v2.1a3 3 0 0 1 0 5.8V17h7V7z"/>',
  tennis: '<path fill-rule="evenodd" d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zM4.3 9.5A7.9 7.9 0 0 0 4.1 13a7 7 0 0 1 5.6 6.8 7.9 7.9 0 0 0 3.4.1A9 9 0 0 0 4.3 9.5zm15.4 5a7.9 7.9 0 0 0 .2-3.5 7 7 0 0 1-5.6-6.8 7.9 7.9 0 0 0-3.4-.1 9 9 0 0 0 8.8 10.4z"/>',
  pickleball: '<path d="M10.2 2.5a6.5 6.5 0 0 1 7.3 7.3l-.5 3.2-5.8 1.6-1.6 1.6-3.3-3.3L8 11.3l1.6-5.8zM7.2 15.3l1.5 1.5-4 4.2-1.7-1.7zM19 15.5a2.6 2.6 0 1 1 0 5.2 2.6 2.6 0 0 1 0-5.2z"/>',
  basketball: '<path fill-rule="evenodd" d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm-1 2.1a7.9 7.9 0 0 0-4.4 1.8A9 9 0 0 1 8.9 11H11zm2 0V11h2.1a9 9 0 0 1 2.3-5.1A7.9 7.9 0 0 0 13 4.1zm5.8 3.2A7 7 0 0 0 17.1 11h2.8a7.9 7.9 0 0 0-1.1-3.7zm-13.6 0A7.9 7.9 0 0 0 4.1 11h2.8a7 7 0 0 0-1.7-3.7zM4.1 13a7.9 7.9 0 0 0 1.1 3.7A7 7 0 0 0 6.9 13zm4.8 0a9 9 0 0 1-2.3 5.1 7.9 7.9 0 0 0 4.4 1.8V13zm4.1 0v6.9a7.9 7.9 0 0 0 4.4-1.8 9 9 0 0 1-2.3-5.1zm4.1 0a7 7 0 0 0 1.7 3.7 7.9 7.9 0 0 0 1.1-3.7z"/>',
  skatepark: '<path d="M2 10.5h20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2zM6.5 14a2.2 2.2 0 1 1 0 4.4 2.2 2.2 0 0 1 0-4.4zm11 0a2.2 2.2 0 1 1 0 4.4 2.2 2.2 0 0 1 0-4.4z"/>',
  cricket: '<path d="M16.9 2.3 19.7 5.1l-2.3 2.3-.9-.9-8.9 8.9-3.5.7.7-3.5 8.9-8.9-.9-.9zM18 15.5a3 3 0 1 1 0 6 3 3 0 0 1 0-6zM3.2 18.4l2.4 2.4-1.4 1.4-2.4-2.4z"/>',
  // Skyscrapers, by use: office floors as bands, homes as a grid of windows, mixed use as both.
  'tw-com': '<path fill-rule="evenodd" d="M5 1.5h14v21H5zM7.6 4.5v2.2h8.8V4.5zm0 4v2.2h8.8V8.5zm0 4v2.2h8.8v-2.2zm0 4v2.2h8.8v-2.2z"/>',
  'tw-res': '<path fill-rule="evenodd" d="M5 1.5h14v21H5zM7.6 4.5h3.2v3.2H7.6zm5.6 0h3.2v3.2h-3.2zM7.6 10h3.2v3.2H7.6zm5.6 0h3.2v3.2h-3.2zM7.6 15.5h3.2v3.2H7.6zm5.6 0h3.2v3.2h-3.2z"/>',
  'tw-mix': '<path fill-rule="evenodd" d="M5 1.5h14v21H5zM7.6 4.5h3.2v3.2H7.6zm5.6 0h3.2v3.2h-3.2zM7.6 10h3.2v3.2H7.6zm5.6 0h3.2v3.2h-3.2zM7.6 15v2.2h8.8V15zm0 3.6v2h8.8v-2z"/>',
};
const svg = d => '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">' + d + '</svg>';
const SWATCH = {knownas: 'Aa', landmarks: svg(GLYPH.culture), badges: svg('<path d="M2 20h20v1.6H2zM3.5 20v-7h4v7zM9 20V6.5h4.5V20zM15 20v-9.5h2.4V8.4h1.6v2.1H20.5V20z"/>')};
/* Places layers: one category ("cat"), or several in one toggle ("cats": [[cat, chip label, singular noun]…]),
   each a chip in the panel that hides or shows it (any mix; at least one stays on). "icon" picks the row's glyph. */
const placeCats = it => it.cats ? it.cats.map(c => c[0]) : [it.cat];
const featCats = p => p.cats || [p.cat];   // a feature's categories: p.cats when it has several
const placeNoun = (it, cat) => ((it.cats || []).find(c => c[0] === cat) || [])[2] || it.place || it.name;
const placeIcon = it => it.icon || placeCats(it)[0];
const catPick = {};   // layer id -> Set of categories shown (null: all)
const catOn = (id, cat) => !catPick[id] || catPick[id].has(cat);
const swatchOf = it => it.kind === 'spots' ? '<i class="sp ' + it.mark + ' c-' + Object.keys(it.classes || {x: 1})[0] + ' z-2"></i>' : it.kind === 'places' ? svg(GLYPH[placeIcon(it)] || GLYPH.culture) : it.kind === 'towers' ? svg(GLYPH['tw-com']) : (SWATCH[it.kind] || '');
// Representation layers draw in one of three styles, by level of government.
const OUTLINE = {city:'ward', state:'prov', national:'fed'};
/* Party colours: a representation layer with "party" in city.json ({table, key}) can be shaded by the
   party of each seat's sitting member (representatives.json), with CITY.party.parties mapping party
   names to a colour ([label, colour, [names]]). One layer is shaded at a time: the most recent one
   wins, and it stands in for the area fills and the lens, which come back when the shading ends.
   Shaded, the layer's own lines switch to a contrasting edge so borders show between seats of one colour. */
/* Election view: a representation layer with "election" in city.json ({table, key, date, until, wording}) shows,
   from now until its "until" date (when the new members take office), each seat's race from representatives.json.
   It is shaded like party colours, but every seat in one neutral colour (no party's), so it shares that machinery:
   one layer shaded at a time, standing in for the area fills and the lens. While it's on, each seat's label grows
   (bigger, bolder) and, zoomed in, lists the election date, the sitting member and how many are running; the card
   opens on its Representatives section with the candidates under the member. */
const dayStart = s => new Date(...s.split('-').map((v, i) => +v - (i === 1)));
const ELECT = Object.fromEntries(LAYERS.filter(it => it.kind === 'outline' && it.election && new Date() < dayStart(it.election.until)).map(it => [it.id, it]));
const PTY = CITY.party || {parties: []};
const PARTY = Object.fromEntries(LAYERS.filter(it => it.kind === 'outline' && (it.party || ELECT[it.id])).map(it => [it.id, it]));
const PTY_RANK = {city: 0, state: 1, national: 2};
// When several shaded layers come on at once: an election under way first, then national over state over city.
const prank = id => ELECT[id] ? 9 : PTY_RANK[PARTY[id].level];
const electShading = () => !!(shade && ELECT[shade]);
let shade = null, partyBusy = false, partyStack = [], partyDisplaced = [];
const partyPref = {};
function partyOf(it, f){   // [class, label] for one seat
  if (ELECT[it.id]) return ['elect', ''];
  const R = data.reps && data.reps[it.party.table], k = String(f.properties[it.party.key]);
  if (!R || !(k in R)) return ['nd', ''];
  const r = R[k]; if (!r) return ['vac', PTY.vacant || 'Vacant'];
  const p = PTY.parties.find(x => x[2].includes(r.party));
  return p ? [p[1], p[0]] : ['other', r.party || PTY.other || 'Other'];
}

// One seat's race for its election label: [heading, detail lines].
function electLines(it, f){
  const E = it.election, k = String(f.properties[E.key]), R = data.reps || {};
  // The sitting member: the card's office for this layer and key (e.g. the councillor, not the MPP on the same lines).
  const O = ((CITY.card.reps || {}).offices || []).find(o => o.layer === it.id && o.key === E.key);
  const r = (R[E.table] || {})[k], inc = O && (R[O.table] || {})[k];
  const lines = [fill(E.when, {date: longDay(E.date)})];
  if (r && r.winner) lines[0] = fill(r.acclaimed ? E.acclaimed : E.elected, {winner: r.winner});
  else if (new Date() >= dayStart(E.date)) lines[0] = E.counting;
  const ew = r && r.incumbentRunning === false && r.incumbentElsewhere, elsewhere = ew && (E.elsewhere || {})[ew.office];
  if (inc && inc.name) lines.push(fill(elsewhere || (r && r.incumbentRunning === false ? E.retiring : E.incumbent), Object.assign({name: inc.name}, ew || {})));
  else if (E.open) lines.push(E.open);
  if (r && !r.winner){ const n = r.candidates.length; lines.push(fill(E.running, {n, s: n === 1 ? '' : 's'})); }
  return [fill(E.head, f.properties), lines];
}
const longDay = s => dayStart(s).toLocaleDateString(CITY.locale, {month:'short', day:'numeric'});
/* Suburban lens: free-flow drive time to the downtown hub, by municipality, in the regional view only. */
const DRIVE_TIERS = [['d1', 'Under 30 min', '--drv-1', 30], ['d2', '30–60 min', '--drv-2', 60], ['d3', '60–90 min', '--drv-3', 90], ['d4', '90 min or more', '--drv-4', Infinity]];
const driveTier = m => m == null ? null : DRIVE_TIERS.find(t => m < t[3]);
const SUBURBS = LAYERS.find(it => it.kind === 'suburbs');

/* One builder per kind of layer. Each gets its config entry and its loaded data. */
const KINDS = {
  fill: (it, fc) => {
    const major = it.size === 'major';
    return polyLayer(fc, {cls: f => (major ? 'fill-major ' : 'fill-minor ') + slug(f.properties.name), label: f => f.properties.name, lcls: () => major ? 'lbl-boro' : 'lbl-area', hover: f => f.properties.name, focusId: it.id});
  },
  units: (it, fc) => polyLayer(fc, {pane:'lines', cls: () => 'nbhd', label: f => f.properties.name, lcls: () => 'lbl-nbhd', hover: f => fill(it.hover || '{name}', f.properties), focusId: it.id}),
  outline: (it, fc) => {
    const c = OUTLINE[it.level];
    // Election view: the label carries the race too, shown (and the number enlarged) only while the view is on.
    const lab = !ELECT[it.id] ? f => fill(it.label, f.properties) : f => { const [h, ls] = electLines(it, f);
      // The chip reads "Ward 19"; zoomed out to the whole city it shrinks to the number (el-s) so all 25 fit.
      return '<span class="el-n"><span class="el-h">' + esc(h) + '</span><span class="el-s">' + esc(String(f.properties[it.election.key])) + '</span></span><span class="el-x">' + ls.map(esc).join('<br>') + '</span>'; };
    const g = polyLayer(fc, {pane:'civic', cls: () => c, label: lab, lcls: () => 'lbl-' + c + (ELECT[it.id] ? ' el' : ''),
      hover: f => !it.party ? fill(it.hover, f.properties) : () => { const p = shade === it.id && partyOf(it, f)[1]; return esc(fill(it.hover, f.properties)) + (p ? ' · ' + esc(p) : ''); }});
    // Party colours sit in the fill pane, under the lines; the lines on top still take hovers and taps.
    // A halo under the lines (lines pane, below civic) makes the contrasting edge read on any colour.
    if (PARTY[it.id]) g._party = L.layerGroup([L.geoJSON(fc, {pane:'fill', interactive:false, style: f => ({className: 'pty p-' + partyOf(it, f)[0], weight: 0})}),
      L.geoJSON(fc, {pane:'lines', interactive:false, style: () => ({className: 'pty-case'})})]);
    return g;
  },
  // Protected districts (heritage, landmark): a dashed outline with a light wash, so the streets inside still read.
  districts: (it, fc) => polyLayer(fc, {pane:'civic', cls: () => 'hd', label: f => fill(it.label, f.properties), lcls: () => 'lbl-hd', hover: f => fill(it.hover, f.properties)}),
  // Trustee wards: only the picked board's wards are drawn; g._pick swaps boards.
  boards: (it, fc) => {
    const g = L.layerGroup(), per = {};
    it.boards.forEach(([b]) => { per[b] = polyLayer({type: 'FeatureCollection', features: fc.features.filter(f => f.properties.board === b)},
      {pane:'civic', cls: () => 'sbw', label: f => fill(it.label, boardCtx(it, f)), lcls: () => 'lbl-sbw', hover: f => fill(it.hover, boardCtx(it, f))}); });
    g.addLayer(per[boardPick[it.id]]);
    g._pick = b => { Object.values(per).forEach(l => g.removeLayer(l)); g.addLayer(per[b]); };
    return g;
  },
  // clsBy: one more class per feature from a property ("evac evac-3"), for patches shaded by category in city.css.
  patches: (it, fc) => polyLayer(fc, {pane:'civic', cls: f => (it.cls || 'bia') + (it.clsBy ? ' ' + (it.cls || 'bia') + '-' + f.properties[it.clsBy] : ''), label: f => fill(it.label, f.properties), lcls: () => it.lcls || 'lbl-bia', hover: f => fill(it.hover, f.properties)}),
  lens: (it, [fc, prof]) => {
    const g = L.geoJSON(fc, {pane:'fill', style: f => {
      return {className: lensClass(prof[String(f.properties.code)])};
    }, onEachFeature: (f, lyr) => {
      lyr.bindTooltip(() => { const t = tierOf(prof[String(f.properties.code)]); return f.properties.name + (t ? ' · ' + t : ''); },
        {sticky:true, className:'hover-tip', direction:'top', offset:[0,-8]});
      lyr.on('click', e => inspect(e.latlng));
    }});
    g._restyle = () => g.eachLayer(l => {
      const d = prof[String(l.feature.properties.code)], el = l.getElement && l.getElement();
      if (el) el.setAttribute('class', lensClass(d) + ' leaflet-interactive');
    });
    return g;
  },
  rail: (it, [lines, stns, linesInner]) => {
    const g = L.layerGroup();
    // Two versions of the lines: the full routes (region view) and clipped at the city limits (city view).
    const full = L.layerGroup(), inner = L.layerGroup();
    // Lines that share track near the hub fan out sideways as you zoom in (offset in screen pixels).
    const gap = () => { const z = map.getZoom(); return z < 11 ? 0 : z < 12 ? 2 : z < 13 ? 3 : 4; };
    const w = () => { const z = map.getZoom(); return z < 11 ? 2.2 : z < 13 ? 3 : 3.5; };
    const segs = [];
    [[lines, full], [linesInner, inner]].forEach(([fc, grp]) => fc.features.forEach(f => {
      const parts = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.coordinates;
      parts.forEach(part => {
        // it.pane: a layer whose lines run on water (ferries) draws above the mask that fades what's beyond the city's land.
        const pl = L.polyline(part.map(ll), {pane: it.pane || 'rail', className:'go-line', color: f.properties.color, weight: w(), offset: f.properties.offset * gap(), feat: f});
        hoverTip(pl, fill((it.lineHover || {})[f.properties.line] || it.hover, f.properties));
        pl.on('click', e => inspect(e.latlng));
        grp.addLayer(pl); segs.push([pl, f]);
      });
    }));
    g.addLayer(full);
    g._scope = s => { const [on, off] = s === 'inner' ? [inner, full] : [full, inner]; g.removeLayer(off); g.addLayer(on); };
    map.on('zoomend', () => segs.forEach(([pl, f]) => { pl.setStyle({weight: w()}); if (pl.setOffset) pl.setOffset(f.properties.offset * gap()); }));
    // A station is a line end if it is the last stop on any line.
    const ends = lines.features.map(f => f.geometry.coordinates[f.geometry.coordinates.length - 1]);
    stns.features.forEach(f => {
      const c = f.geometry.coordinates, p = f.properties;
      const end = ends.some(e => Math.abs(e[0] - c[0]) < .01 && Math.abs(e[1] - c[1]) < .008);
      const out = !it.pane && !hit(data.footprint, c[0], c[1]) ? ' go-out' : '';   // a water layer's landings sit just off the land: never "outside"
      const m = L.circleMarker(ll(c), {pane:'pts', radius: p.hub ? 6 : end ? 4.5 : 3.5, className: 'go-stn' + (p.hub ? ' hub' : '') + (end ? ' end' : '') + out});
      hoverTip(m, p.name + ' · ' + p.lines.join(', '));
      m.on('click', e => inspect(e.latlng));
      g.addLayer(m);
      g.addLayer(L.tooltip({permanent:true, direction:'right', offset:[6, 0], className:'lbl lbl-go' + (end || p.hub ? ' end' : '') + out, interactive:false}).setLatLng(ll(c)).setContent(esc(p.name)));
    });
    return g;
  },
  // Institutions by category (universities, colleges, hospitals…): one file, one layer per category.
  // Icons from zoom 11, names from 14. Describe only: name and what it is, nothing ranked.
  // A layer with "groups" (e.g. churches by family) shows one group at a time, picked with chips in the panel;
  // with "groupsFor", the groups narrow only that category (churches among all places of worship).
  // "minZoom" (12-14) holds a busy layer's icons back until that zoom; "wide" (a few places spread over the region,
  // such as headquarters) shows the icons from zoom 9 and names from 11 instead. With "popup", a tap opens the place's details
  // (placePopup) instead of the What's here card.
  // A place may be in several categories (p.cats, e.g. a park with tennis courts and a pool): it shows while any of
  // them is picked, its pin taking the first picked one's glyph and colour.
  places: (it, fc) => {
    const g = L.layerGroup(), marks = [], cats = placeCats(it);
    const icon = (p, c) => L.divIcon({className:'', iconSize:[0, 0], html:'<span class="lm inst in-' + c + (p.ed ? ' ed' : '') + (it.minZoom ? ' mz' + it.minZoom : '') + (it.wide ? ' wide' : '') + '"><i>' + svg(GLYPH[c] || GLYPH.culture) + '</i><b>' + esc(p.name) + '</b></span>'});
    fc.features.filter(f => featCats(f.properties).some(c => cats.includes(c))).forEach(f => {
      const p = f.properties;
      const m = L.marker(ll(f.geometry.coordinates), {pane:'pts', keyboard:false, riseOnHover:true, icon: icon(p, p.cat)});
      hoverTip(m, fill(it.hover || '{name}[ · {sub}]', p) + (p.ed && it.edText ? ' · ' + it.edText : ''));
      m.on('click', e => { if (it.popup){ L.DomEvent.stop(e); placePopup(it, p, fc, m.getLatLng()); } else goTo(L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]), p.name, false); });
      marks.push([m, p.grp, p.cat, p, p.cat]);
    });
    const grouped = cat => it.groups && (!it.groupsFor || cat === it.groupsFor);
    const shown = ([, grp, cat, p]) => { const k = placePick[it.id] || 'all'; return featCats(p).some(c => catOn(it.id, c)) && (!grouped(cat) || k === 'all' || grp === k); };
    const repin = x => { if (!x[3].cats) return; const c = x[3].cats.find(c => catOn(it.id, c)) || x[3].cat; if (c !== x[4]){ x[4] = c; x[0].setIcon(icon(x[3], c)); } };
    g._draw = () => { g.clearLayers(); marks.forEach(x => { if (shown(x)){ repin(x); g.addLayer(x[0]); } }); };
    g._count = () => marks.filter(x => grouped(x[2]) && shown(x)).length;
    g._draw();
    return g;
  },
  // Skyscrapers: a square badge per tower, its glyph showing use (residential, commercial, mixed);
  // filled once open for occupancy, hollow while under construction; a gold ring at 300 m+ (supertall).
  // Supertall icons from zoom 12 and names from 13; the rest from 14 and 15. Names declutter.
  towers: (it, fc) => {
    const g = L.layerGroup();
    fc.features.forEach(f => {
      const p = f.properties;
      const m = L.marker(ll(f.geometry.coordinates), {pane:'pts', keyboard:false, riseOnHover:true, zIndexOffset: p.super ? 200 : 0,
        icon: L.divIcon({className:'', iconSize:[0, 0], html:'<span class="lm tw u-' + p.use + (p.uc ? ' uc' : '') + (p.super ? ' sup' : '') + '"><i>' + svg(GLYPH['tw-' + p.use]) + '</i><b>' + esc(p.name) + '</b></span>'})});
      hoverTip(m, esc(p.name) + ' · ' + towerHeight(p, true) + (p.uc ? ' · ' + esc(it.ucText || 'Under construction') + (p.year ? ' · ' + esc((it.expectedText || 'Expected').toLowerCase()) + ' ' + p.year : '') : ''));
      m.on('click', () => goTo(L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]), p.name, false));
      g.addLayer(m);
    });
    return g;
  },
  landmarks: (it, fc) => {
    const g = L.layerGroup();
    fc.features.forEach(f => {
      const p = f.properties;
      const m = L.marker(ll(f.geometry.coordinates), {pane:'pts', keyboard:false, riseOnHover:true,
        icon: L.divIcon({className:'', iconSize:[0, 0], html:'<span class="lm ' + p.cat + ' t' + p.tier + '"><i>' + svg(GLYPH[p.cat]) + '</i><b>' + esc(p.name) + '</b></span>'})});
      hoverTip(m, p.name + ' · ' + p.catLabel);
      m.on('click', () => goTo(L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]), p.name, false));
      g.addLayer(m);
    });
    return g;
  },
  knownas: (it, fc) => {
    const g = L.layerGroup();
    fc.features.forEach(f => g.addLayer(label(f.properties.name, 'lbl-cult' + (f.properties.kind === 'enclave' ? ' enclave' : ''), ll(f.geometry.coordinates))));
    return g;
  },
  streets: (it, fc) => {
    // Arterial roads, with names laid along the line. Labels are re-placed after every
    // move so they never overlap each other; majors win over minors, longer streets first.
    const g = L.layerGroup(), labels = L.layerGroup();
    const w = () => { const z = map.getZoom(); return z < 11 ? [2, 1] : z < 12 ? [3, 1.6] : z < 13 ? [4.2, 2.6] : z < 14 ? [6, 4] : [8, 5.6]; };
    // Collectors (their own layer, under Main streets) draw thinner, from zoom 13, named from 15.
    const k = f => f.properties.cls === 'major' ? 1 : f.properties.cls === 'coll' ? .55 : .75;
    const cas = L.geoJSON(fc, {pane:'streets', interactive:false, style: f => ({className:'st-case ' + f.properties.cls, weight: w()[0] * k(f)})});
    const core = L.geoJSON(fc, {pane:'streets', style: f => ({className:'st-core ' + f.properties.cls, weight: w()[1] * k(f)}),
      onEachFeature: (f, lyr) => { if (f.properties.name) hoverTip(lyr, f.properties.name); lyr.on('click', e => inspect(e.latlng)); }});
    map.on('zoomend', () => { cas.eachLayer(l => l.setStyle({weight: w()[0] * k(l.feature)})); core.eachLayer(l => l.setStyle({weight: w()[1] * k(l.feature)})); });
    g.addLayer(cas); g.addLayer(core); g.addLayer(labels);
    const streets = fc.features.map(f => {
      const parts = (f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.coordinates).map(p => p.map(c => L.latLng(c[1], c[0])));
      return {name: f.properties.name, cls: f.properties.cls, parts: parts.map(p => ({pts: p, b: L.latLngBounds(p)}))};
    });
    const ctx = document.createElement('canvas').getContext('2d');
    const rect = (x, y, hw, hh, r) => ({x, y, hw, hh, ax: [[Math.cos(r), Math.sin(r)], [-Math.sin(r), Math.cos(r)]]});
    const overlap = (A, B) => [...A.ax, ...B.ax].every(([ux, uy]) => {
      const ext = R => R.hw * Math.abs(R.ax[0][0] * ux + R.ax[0][1] * uy) + R.hh * Math.abs(R.ax[1][0] * ux + R.ax[1][1] * uy);
      return Math.abs((B.x - A.x) * ux + (B.y - A.y) * uy) < ext(A) + ext(B);
    });
    const pointAt = (px, d, t) => { let i = 1; while (i < d.length - 1 && d[i] < t) i++; const s = (t - d[i-1]) / ((d[i] - d[i-1]) || 1); return L.point(px[i-1].x + (px[i].x - px[i-1].x) * s, px[i-1].y + (px[i].y - px[i-1].y) * s); };
    function place(){
      labels.clearLayers();
      const z = map.getZoom();
      if (!map.hasLayer(g) || z < (it.labelZoom || 12)) return;
      const size = map.getSize(), view = map.getBounds(), boxes = [], seen = {}, fam = getComputedStyle(document.body).fontFamily;
      const SP = z < 13 ? 420 : z < 14 ? 340 : 280;
      // Keep clear of other labels, shields and the panels floating over the map.
      const mr = map.getContainer().getBoundingClientRect();
      // A layer that yields (collectors) also keeps clear of the main streets' names, placed just before.
      document.querySelectorAll('#search, #here, #panel, .leaflet-tooltip.lbl, .shield, .lm i, .lm b, .stn, .sub-b, .leaflet-pin-pane > *' + (it.yieldLabels ? ', .st-lbl:not(.coll)' : '')).forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width && r.height) boxes.push(rect((r.left + r.right) / 2 - mr.left, (r.top + r.bottom) / 2 - mr.top, r.width / 2 + 3, r.height / 2 + 3, 0));
      });
      let count = 0;
      for (const s of streets){
        if (!s.name || (s.cls === 'minor' && z < 13) || count >= 90) continue;   // unnamed stretches draw but carry no label
        ctx.font = (s.cls === 'major' ? '600 11.5px ' : s.cls === 'coll' ? '500 10px ' : '500 10.5px ') + fam;
        const tw = ctx.measureText(s.name).width + 8, th = s.cls === 'major' ? 15 : 14;
        const mine = seen[s.name] || (seen[s.name] = []);
        for (const part of s.parts){
          if (!view.intersects(part.b)) continue;
          const px = part.pts.map(p => map.latLngToContainerPoint(p));
          const d = [0]; for (let i = 1; i < px.length; i++) d.push(d[i-1] + px[i].distanceTo(px[i-1]));
          const total = d[d.length-1];
          if (total < tw * 1.3) continue;
          for (let at = Math.max(tw / 2, Math.min(SP / 2, total / 2)); at + tw / 2 <= total; at += 40){
            const a = pointAt(px, d, at - tw / 2), b = pointAt(px, d, at + tw / 2), c0 = pointAt(px, d, at);
            if (c0.x < 20 || c0.y < 20 || c0.x > size.x - 20 || c0.y > size.y - 20) continue;
            if (a.distanceTo(b) < tw * .94) continue;               // too curvy here
            if (mine.some(p => p.distanceTo(c0) < SP)) continue;     // same street labelled nearby
            let ang = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
            if (ang > 90) ang -= 180; if (ang < -90) ang += 180;     // keep text upright
            const r = ang * Math.PI / 180;
            // On the street if there's room, otherwise just beside it (e.g. where a subway runs along it).
            let c = null, box;
            for (const off of [0, th / 2 + 9, -(th / 2 + 9)]){
              const q = L.point(c0.x - Math.sin(r) * off, c0.y + Math.cos(r) * off);
              const bx = rect(q.x, q.y, tw / 2, th / 2, r);
              if (!boxes.some(o => overlap(o, bx))) { c = q; box = bx; break; }
            }
            if (!c) continue;
            boxes.push(box); mine.push(c0); count++;
            labels.addLayer(L.marker(map.containerPointToLatLng(c), {pane:'stlbl', interactive:false, keyboard:false,
              icon: L.divIcon({className:'', iconSize:null, html:'<span class="st-lbl ' + s.cls + '" style="transform:translate(-50%,-50%) rotate(' + ang.toFixed(1) + 'deg)">' + esc(s.name) + '</span>'})}));
          }
        }
      }
    }
    // A yielding layer places its names after the main streets' (their handler may be registered later).
    map.on('moveend', () => it.yieldLabels ? setTimeout(place) : place()); g.on('add', () => setTimeout(place));
    return g;
  },
  highways: (it, [fc, outer, outerShields]) => {
    const g = L.layerGroup();
    const w = () => { const z = map.getZoom(); return z < 11 ? [5, 2.4] : z < 13 ? [7, 3.6] : [10, 5.5]; };
    // A feature marked "over" (a ring road that leaves the city and comes back) draws above the mask, so it reads whole
    // in the city view; the rest sit under it.
    [false, true].forEach(over => {
      const part = {type: 'FeatureCollection', features: fc.features.filter(f => !!f.properties.over === over)}, pane = over ? 'hwytop' : 'hwy';
      if (!part.features.length) return;
      const cas = L.geoJSON(part, {pane, interactive:false, style: f => ({className:'hwy-case', weight: w()[0]})});
      const core = L.geoJSON(part, {pane, style: f => ({className:'hwy-core ' + f.properties.kind, weight: w()[1]}),
        onEachFeature: (f, lyr) => { hoverTip(lyr, f.properties.name); lyr.on('click', e => inspect(e.latlng)); }});
      map.on('zoomend', () => { cas.eachLayer(l => l.setStyle({weight: w()[0]})); core.eachLayer(l => l.setStyle({weight: w()[1]})); });
      g.addLayer(cas); g.addLayer(core);
    });
    // Beyond the city limits (OpenStreetMap): same look, shields stay visible when zoomed out to the region.
    const gcas = L.geoJSON(outer, {pane:'hwy', interactive:false, style: () => ({className:'hwy-case outer', weight: w()[0]})});
    const gcore = L.geoJSON(outer, {pane:'hwy', style: () => ({className:'hwy-core outer', weight: w()[1]}),
      onEachFeature: (f, lyr) => { hoverTip(lyr, f.properties.name); lyr.on('click', e => inspect(e.latlng)); }});
    map.on('zoomend', () => { gcas.eachLayer(l => l.setStyle({weight: w()[0]})); gcore.eachLayer(l => l.setStyle({weight: w()[1]})); });
    g.addLayer(gcas); g.addLayer(gcore);
    outerShields.features.forEach(f => {
      const p = f.properties, html = '<span class="shield outer' + (p.toll ? ' toll' : '') + '">' + esc(p.toll ? it.tollShield : p.route) + '</span>';
      g.addLayer(L.marker(ll(f.geometry.coordinates), {pane:'pts', interactive:false, keyboard:false, icon: L.divIcon({className:'', html, iconSize:null})}));
    });
    fc.features.forEach(f => {
      const parts = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.coordinates;
      const longest = parts.reduce((a, b) => b.length > a.length ? b : a);
      const at = (it.repeat || {})[f.properties.route] || [.5];
      at.forEach((t, i) => {
        const p = longest[Math.floor((longest.length - 1) * t)];
        const html = '<span class="shield ' + (f.properties.kind === 'city' ? 'city' : '') + (i ? ' minor' : '') + '">' + esc(it.shields[f.properties.route] || f.properties.route) + '</span>';
        g.addLayer(L.marker(ll(p), {pane:'pts', interactive:false, keyboard:false, icon: L.divIcon({className:'', html, iconSize:null})}));
      });
    });
    return g;
  },
  suburbs: (it, base) => polyLayer({type: 'FeatureCollection', features: base.features.filter(f => f.properties.kind === 'neighbour')}, {
    cls: f => { const t = driveTier(f.properties.drive); return 'drv ' + (f.properties.rest || !t ? 'rest' : t[0]); },
    hover: f => f.properties.name + (f.properties.drive != null && !f.properties.rest ? ' · about ' + f.properties.drive + ' min' : '')}),
  metro: (it, [lines, stns]) => {
    const g = L.layerGroup();
    const w = () => { const z = map.getZoom(); return z < 11 ? 3 : z < 13 ? 4.5 : 6; };
    const lg = L.geoJSON(lines, {pane:'transit', style: f => ({className:'sub-line l' + f.properties.line, weight: w()}),
      onEachFeature: (f, lyr) => { hoverTip(lyr, f.properties.name); lyr.on('click', e => inspect(e.latlng)); }});
    map.on('zoomend', () => lg.eachLayer(l => l.setStyle({weight: w()})));
    g.addLayer(lg);
    const names = L.layerGroup();
    stns.features.forEach(f => {
      const x = f.properties.lines.length > 1, end = f.properties.terminus;
      const m = L.circleMarker(ll(f.geometry.coordinates), {pane:'pts', radius: x || end ? 5 : 3.5, className: 'stn' + (x ? ' x' : '') + (end ? ' end' : '')});
      hoverTip(m, fill(it.stationHover || '{name}', f.properties));
      m.on('click', e => inspect(e.latlng));
      g.addLayer(m);
      names.addLayer(L.tooltip({permanent:true, direction:'right', offset:[6,0], className:'lbl lbl-stn' + (f.properties.terminus ? ' end' : ''), interactive:false}).setLatLng(ll(f.geometry.coordinates)).setContent(f.properties.name));
    });
    g._names = names;
    // Stations (dots and names) show from zoom 13 (CSS); zoomed out, each line carries a badge instead.
    g.addLayer(lineBadges(it, lines, lg, g));
    return g;
  },
  // Streetcar routes with daytime service, each numbered along its line (badges from zoom 12).
  streetcars: (it, fc) => routeLines(fc.features, false),
  // Bus routes: one family at a time (frequent, express, overnight). Shapes load the first time it's on.
  buses: it => {
    const g = L.layerGroup(); let cur = null;
    g._draw = () => {
      if (cur){ g.removeLayer(cur); cur = null; }
      if (!routeGeo) return;
      // With two families on, the express routes are dashed (class dash) so they read apart from the locals
      // they shadow. Showing the overnight family, every route drawn gets the night class.
      const mixed = busFams.size > 1;
      cur = routeLines(routeGeo.features.filter(f => busShows(f.properties)), false, p => mixed && p.f.includes('exp') ? ' dash' : '', {night: busFams.has('night')});
      g.addLayer(cur);
    };
    g.on('add', () => ensureRoutes().then(() => { g._draw(); drawBusBox(); }));
    return g;
  },
  // How addresses work (engine/addresses.py). A grid city: its baselines (0) bold and every mile line
  // dashed, each labelled with its number (westmost or northmost end). A city split by one street: that
  // street bold, and the streets it splits tinted East and West, with "West · East" marks along it.
  addresses: (it, fc) => {
    const g = L.layerGroup();
    if (fc.kind === 'grid'){
      const longest = {};
      fc.features.forEach(f => {
        const p = f.properties, c = f.geometry.coordinates;
        const pl = L.polyline(c.map(ll), {pane:'civic', className: 'ag-line' + (p.role === 'base' ? ' base' : '')});
        hoverTip(pl, esc(p.street) + ' · ' + esc(p.label));
        pl.on('click', e => inspect(e.latlng));
        g.addLayer(pl);
        const k = p.axis + p.label, len = span(c);
        if (!longest[k] || len > longest[k][1]) longest[k] = [f, len];
      });
      Object.values(longest).forEach(([f]) => {
        const p = f.properties, c = f.geometry.coordinates;
        const end = p.axis === 'ns' ? c.reduce((a, b) => b[0] < a[0] ? b : a) : c.reduce((a, b) => b[1] > a[1] ? b : a);
        g.addLayer(L.tooltip({permanent:true, direction: p.axis === 'ns' ? 'right' : 'bottom', offset: p.axis === 'ns' ? [4, 0] : [0, 4], interactive:false,
          className:'lbl lbl-ag' + (p.role === 'base' ? ' base' : '')}).setLatLng(ll(end)).setContent(esc(p.role === 'base' ? p.street + ' · 0' : p.label)));
      });
    } else {
      fc.features.forEach(f => {
        const p = f.properties;
        const pl = L.polyline(f.geometry.coordinates.map(ll), {pane:'civic', className: 'ag-' + p.role});
        hoverTip(pl, esc(p.street) + (p.role === 'divide' ? '' : ' · ' + esc(p.role === 'e' ? it.eastText : it.westText)));
        pl.on('click', e => inspect(e.latlng));
        g.addLayer(pl);
      });
      // "West · East" marks along the dividing street, at a few points spread along it.
      const div = fc.features.filter(f => f.properties.role === 'divide').map(f => f.geometry.coordinates).reduce((a, b) => span(b) > span(a) ? b : a, []);
      if (div.length > 1) [.12, .45, .8].forEach(t => g.addLayer(L.tooltip({permanent:true, direction:'center', interactive:false, className:'lbl lbl-ag div'})
        .setLatLng(ll(along(div, t))).setContent('<i>' + esc(it.westText) + '</i><b>' + esc(fc.street) + '</b><i>' + esc(it.eastText) + '</i>')));
    }
    return g;
  },
  // Heritage buildings: a small diamond per individually protected property, only from zoom it.minZoom (15)
  // and only those in view (redrawn after each move), so a phone never holds more than a street's worth;
  // names (when the record has one) from zoom 16. Tap for its name, year, architect and designation.
  heritage: (it, fc) => {
    const g = L.layerGroup(), shown = new Map(), minZ = it.minZoom || 15;
    const make = f => {
      const p = f.properties;
      const m = L.marker(ll(f.geometry.coordinates), {pane:'pts', keyboard:false, riseOnHover:true,
        icon: L.divIcon({className:'', iconSize:[0, 0], html:'<span class="hbm"><i></i>' + (p.n ? '<b>' + esc(p.n) + '</b>' : '') + '</span>'})});
      hoverTip(m, esc(p.n || p.a) + (p.y ? ' · ' + esc(p.y) : ''));
      m.on('click', e => { L.DomEvent.stop(e); hbPopup(it, p, e.latlng); });
      return m;
    };
    const draw = () => {
      if (!map.hasLayer(g)) return;
      const on = map.getZoom() >= minZ - .01, b = map.getBounds().pad(.25);
      fc.features.forEach(f => {
        const c = f.geometry.coordinates, want = on && b.contains([c[1], c[0]]), m = shown.get(f);
        if (want && !m){ const mk = make(f); shown.set(f, mk); g.addLayer(mk); }
        else if (!want && m){ g.removeLayer(m); shown.delete(f); }
      });
    };
    map.on('moveend', draw);
    g.on('add', () => setTimeout(draw));
    g.on('remove', () => { shown.forEach(m => g.removeLayer(m)); shown.clear(); });
    return g;
  },
  // Neighbourhood badges (engine/badges.py): a one-colour drawing for a few curated places, laid like a watermark
  // just over the street lines (faint enough to show them) and under outlines and every label, turned square to the city grid (data angle) and sized to a share (it.scale) of the largest
  // box of its shape that fits inside its unit, so it never spills into a neighbour. Shown once it is it.minWidth px
  // wide, up to it.maxWidth px. No text: the name is the units layer's own label. Loads on first use (it.lazy).
  badges: it => {
    const g = L.layerGroup(), items = [];
    const SCALE = it.scale || .7, MINW = it.minWidth || 60, MAXW = it.maxWidth || 220;
    let angle = 0;
    const size = () => {
      if (!map.hasLayer(g)) return;
      const z = map.getZoom();
      items.forEach(o => {
        const mpp = 40075016.686 * Math.cos(o.u.c[0] * Math.PI / 180) / Math.pow(2, z + 8);   // metres per screen px
        const w = Math.min(o.u.wm * SCALE / mpp, MAXW);
        const el = o.m.getElement(), s = el && el.firstChild;
        if (!s) return;
        s.style.display = w >= MINW ? '' : 'none';
        s.setAttribute('width', w.toFixed(1)); s.setAttribute('height', (w * o.u.h / o.u.w).toFixed(1));
        s.style.transform = 'translate(-50%,-50%) rotate(' + (-angle) + 'deg)';
        if (it.opacity) s.style.opacity = it.opacity;
      });
    };
    g.on('add', () => ensureBadges().then(d => {
      if (!d) return;
      angle = d.angle || 0;
      if (!items.length) d.units.forEach(u => {
        const m = L.marker(u.c, {pane: 'badges', interactive: false, keyboard: false,
          icon: L.divIcon({className: '', iconSize: [0, 0], html: '<svg class="bdg" viewBox="0 0 ' + u.w + ' ' + u.h + '" role="img" aria-label="' + esc(u.n) + '">' + u.svg + '</svg>'})});
        items.push({m, u});
        g.addLayer(m);
      });
      else items.forEach(o => g.addLayer(o.m));
      size();
    }));
    map.on('zoomend', size);
    return g;
  },
  // What's changing: a dot per site, coloured by stage; demolitions dashed. Loads on first use (it.lazy).
  // Stage chips (several at once) narrow it. Tap a dot for what it is, its stage and date, and a link.
  changes: it => {
    const g = L.layerGroup(); let cur = null;
    g._draw = () => {
      if (cur){ g.removeLayer(cur); cur = null; }
      if (!data.changes) return;
      cur = L.layerGroup();
      data.changes.features.forEach(f => {
        const p = f.properties; if (!chgStages.has(p.s)) return;
        const m = L.circleMarker(ll(f.geometry.coordinates), {pane:'pts', radius: chgR(), className: 'chg s-' + p.s + (p.k === 'demolition' ? ' demo' : '')});
        hoverTip(m, esc(CHG.kinds[p.k] || p.k) + ' · ' + esc(p.a) + ' · ' + esc(CHG.stages[p.s][0]));
        m.on('click', e => { L.DomEvent.stop(e); chgPopup(p, e.latlng); });
        cur.addLayer(m);
      });
      g.addLayer(cur);
    };
    map.on('zoomend', () => cur && cur.eachLayer(m => m.setRadius(chgR())));
    g.on('add', () => ensureChanges().then(() => g._draw()));
    return g;
  },
  // Bike lanes: the City's bike network, one line per segment, styled by class (it.classes: separated, painted,
  // shared, trails). Class chips (several at once) pick what's drawn. Loads on first use (it.lazy).
  // Drawn in the highway pane, above the area outlines, so a tap on a lane reaches it rather than the neighbourhood.
  // Tap a stretch for its type, street, ends and year installed.
  bikes: it => {
    const g = L.layerGroup(); let cur = null;
    g._draw = () => {
      if (cur){ g.removeLayer(cur); cur = null; }
      if (!data.bikes) return;
      const fs = data.bikes.features.filter(f => bkClasses.has(f.properties.t));
      const fc = {type: 'FeatureCollection', features: fs};
      cur = L.layerGroup();
      // A light casing under the lanes on the street, so they read over a main street's grey.
      cur.addLayer(L.geoJSON({type: 'FeatureCollection', features: fs.filter(f => f.properties.t === 'prot' || f.properties.t === 'paint')},
        {pane: 'hwy', interactive: false, style: f => ({className: 'bk-case t-' + f.properties.t, weight: bkW(f.properties.t) + 2.4})}));
      cur.addLayer(L.geoJSON(fc, {pane: 'hwy', style: f => ({className: 'bk t-' + f.properties.t, weight: bkW(f.properties.t)}),
        onEachFeature: (f, lyr) => {
          const p = f.properties;
          hoverTip(lyr, esc(p.d) + (p.n ? ' · ' + esc(p.n) : ''));
          lyr.on('click', e => { L.DomEvent.stop(e); bkPopup(p, e.latlng); });
        }}));
      g.addLayer(cur);
    };
    map.on('zoomend', () => cur && cur.eachLayer(l => l.eachLayer(s => s.setStyle({weight: bkW(s.feature.properties.t) + (s.options.interactive === false ? 2.4 : 0)}))));
    g.on('add', () => ensureBikes().then(() => g._draw()));
    return g;
  },
  // Parks: outlines shaded green, one path per park. Amenity chips (it.amenities, any mix) narrow it: a park that lacks
  // one of the picked amenities fades to a faint wash, so the green space still reads. Drawn in the civic pane, above the
  // neighbourhood fills, so a tap reaches the park; the wash is light enough for the streets to show through.
  // Tap for its name, what it has and its City page. Loads on first use (it.lazy).
  parks: it => {
    const g = L.layerGroup(); let cur = null;
    g._draw = () => {
      if (!data.parks) return;
      if (!cur){
        cur = L.geoJSON(data.parks, {pane: 'civic', style: () => ({className: 'pk'}), onEachFeature: (f, lyr) => {
          hoverTip(lyr, esc(pkTip(f.properties)));
          lyr.on('click', e => { L.DomEvent.stop(e); pkPopup(f.properties, e.latlng); });
        }});
        g.addLayer(cur);
      }
      let n = 0;
      cur.eachLayer(l => { const ok = pkMatch(l.feature.properties), el = l.getElement && l.getElement();
        if (ok) n++; if (el) el.classList.toggle('dim', !ok); l.options.className = 'pk' + (ok ? '' : ' dim'); });
      const note = document.getElementById('pknote');
      if (note) note.textContent = pkWant.size ? fill(it.matchText || '{n} of {total} parks', {n: n.toLocaleString(CITY.locale), total: data.parks.features.length.toLocaleString(CITY.locale)}) : '';
    };
    g.on('add', () => ensureParks().then(() => g._draw()));
    return g;
  },
  // Bike share stations (engine/bikeshare.py), nested under Bike lanes: a small ringed dot per station, filled where it
  // charges e-bikes, from zoom it.minZoom (12) and only those near the view (redrawn after each move). A wider clear
  // circle over each dot takes the tap. Tap for its name, docks, e-bike charging and whether the kiosk takes cards.
  // No live counts of bikes or free docks. Loads on first use (it.lazy).
  docks: it => {
    const g = L.layerGroup(), shown = new Map(), minZ = it.minZoom || 12;
    const make = f => {
      const p = f.properties, at = ll(f.geometry.coordinates), r = dkR();
      const dot = L.circleMarker(at, {pane: 'pts', radius: r, interactive: false, className: 'dk' + (p.e ? ' e' : '')});
      const hit = L.circleMarker(at, {pane: 'pts', radius: r + 6, className: 'dk-hit'});
      hoverTip(hit, esc(p.n) + (p.d ? ' · ' + esc(fill(it.docksText || '{n} docks', {n: p.d})) : ''));
      hit.on('click', e => { L.DomEvent.stop(e); dkPopup(p, at); });
      return L.layerGroup([dot, hit]);
    };
    const draw = () => {
      if (!map.hasLayer(g) || !data.docks) return;
      const on = map.getZoom() >= minZ - .01, b = map.getBounds().pad(.25);
      data.docks.features.forEach(f => {
        const c = f.geometry.coordinates, want = on && b.contains([c[1], c[0]]), m = shown.get(f);
        if (want && !m){ const mk = make(f); shown.set(f, mk); g.addLayer(mk); }
        else if (!want && m){ g.removeLayer(m); shown.delete(f); }
      });
    };
    map.on('moveend', draw);
    map.on('zoomend', () => { const r = dkR(); shown.forEach(m => m.eachLayer(c => c.setRadius(c.options.className === 'dk-hit' ? r + 6 : r))); });
    g.on('add', () => ensureDocks().then(() => setTimeout(draw)));
    g.on('remove', () => { shown.forEach(m => g.removeLayer(m)); shown.clear(); });
    return g;
  },
  // Parking spots (car parks and EV chargers) from one shared points file (it.file, e.g. parking.geojson), the layer's own
  // ones picked by p.c === it.cat. it.mark is "lot" (a square: filled for a garage, outlined for a surface lot, sized
  // by spaces) or "charger" (a dot: filled with a heavier ring where DC fast charging is, ringed where Level 2 only;
  // grey and dashed when listed as temporarily unavailable). Drawn from it.minZoom and only near the view, like docks;
  // a wider clear target takes the tap. Chips (it.classes) narrow it by class. Loads on first use (it.lazy).
  spots: it => {
    const g = L.layerGroup(), shown = new Map(), minZ = it.minZoom || 12;
    const make = f => {
      const p = f.properties, at = ll(f.geometry.coordinates), c = spotClass(it, p);
      const m = L.marker(at, {pane: 'pts', keyboard: false, riseOnHover: true, zIndexOffset: c === 'dc' || c === 'g' ? 100 : 0,
        icon: L.divIcon({className: '', iconSize: [0, 0], html: '<span class="sp ' + it.mark + ' c-' + c + ' z-' + spotSize(it, p) + (p.off ? ' off' : '') + (p.tes ? ' tes' : '') + '">' + (it.mark === 'charger' ? BOLT : '') + '</span>'})});
      hoverTip(m, esc(spotTip(it, p)));
      m.on('click', e => { L.DomEvent.stop(e); spotPopup(it, p, at); });
      return m;
    };
    const draw = () => {
      const D = loaded[it.file];
      if (!map.hasLayer(g) || !D) return;
      const pick = spotPick[it.id], on = map.getZoom() >= minZ - .01, b = map.getBounds().pad(.25);
      D.features.forEach(f => {
        if (f.properties.c !== it.cat) return;
        const c = f.geometry.coordinates, want = on && b.contains([c[1], c[0]]) && (!pick || pick.has(spotClass(it, f.properties))), m = shown.get(f);
        if (want && !m){ const mk = make(f); shown.set(f, mk); g.addLayer(mk); }
        else if (!want && m){ g.removeLayer(m); shown.delete(f); }
      });
      const n = document.getElementById('spnote-' + it.id);
      if (n) n.textContent = map.getZoom() < minZ - .01 ? fill(it.zoomText || 'Zoom in to see them.', {z: minZ}) : '';
    };
    g._draw = draw;
    map.on('moveend', draw);
    g.on('add', () => ensureSpots(it).then(() => setTimeout(draw)));
    g.on('remove', () => { shown.forEach(m => g.removeLayer(m)); shown.clear(); });
    return g;
  },
  // Another agency's buses (it.mode, e.g. GO): every route in the regional view; in the city view only the
  // routes with a stop in the city, numbered where they run inside it. Lines sit in the rail pane, under the
  // mask, so a route's stretch outside the city fades with the rest of the region. Shapes load on first use.
  regional: it => {
    const g = L.layerGroup(); let full = null, inner = null;
    const inCity = c => !data.footprint || hit(data.footprint, c[0], c[1]);
    g._scope = s => { if (!full) return; g.removeLayer(full); g.removeLayer(inner); g.addLayer(s === 'inner' ? inner : full); };
    g.on('add', () => ensureRoutes().then(() => {
      if (!full && routeGeo){
        const fs = routeGeo.features.filter(f => f.properties.m === it.mode);
        full = routeLines(fs, false, null, {pane: 'rail'});
        inner = routeLines(fs.filter(f => f.properties.in), false, null, {pane: 'rail', within: inCity});
        g._scope(scope);
      }
      drawStops();
    }));
    return g;
  },
  // Lines being built: dashed in the line's colour over a casing, hollow stations, names from zoom 13.
  // Tap a line or station for what it is, who builds it and when it's due.
  construction: (it, fc) => {
    const g = L.layerGroup();
    const w = () => { const z = map.getZoom(); return z < 11 ? 2.5 : z < 13 ? 3.5 : 5; };
    const lines = fc.features.filter(f => f.properties.part !== 'station'), stns = fc.features.filter(f => f.properties.part === 'station');
    const byId = {}; lines.forEach(f => { byId[f.properties.id] = f.properties; });
    const cas = L.geoJSON({type:'FeatureCollection', features: lines}, {pane:'transit', interactive:false, style: () => ({className:'cx-case', weight: w() + 3})});
    const core = L.geoJSON({type:'FeatureCollection', features: lines}, {pane:'transit', style: f => ({className:'cx-line', color: f.properties.color, weight: w(), dashArray: '7 6'}),
      onEachFeature: (f, lyr) => { hoverTip(lyr, esc(f.properties.name) + ' · ' + esc(it.ucText || 'under construction')); lyr.on('click', e => cxPopup(it, f.properties, e.latlng)); }});
    map.on('zoomend', () => { cas.eachLayer(l => l.setStyle({weight: w() + 3})); core.eachLayer(l => l.setStyle({weight: w()})); });
    g.addLayer(cas); g.addLayer(core);
    stns.forEach(f => {
      const p = f.properties, line = byId[p.id] || {};
      const m = L.circleMarker(ll(f.geometry.coordinates), {pane:'pts', radius: 4.5, className:'cx-stn', color: line.color});
      hoverTip(m, esc(p.name) + ' · ' + esc(line.short || line.name || ''));
      m.on('click', e => cxPopup(it, line, e.latlng, p.name));
      g.addLayer(m);
      g.addLayer(L.tooltip({permanent:true, direction:'right', offset:[6, 0], className:'lbl lbl-stn lbl-cx', interactive:false}).setLatLng(ll(f.geometry.coordinates)).setContent(esc(p.name)));
    });
    return g;
  },
  // Road closures and lane restrictions from transit construction (refreshed daily). Arterials at any
  // zoom; full closures of local streets from zoom 15. Permits that have ended are hidden; ones starting
  // within the week are drawn faint. Dates are permit dates, not a forecast of when a road reopens.
  closures: (it, fc) => {
    const g = L.layerGroup(), today = cityToday(it.tz);
    const w = () => { const z = map.getZoom(); return z < 13 ? 4 : z < 15 ? 6 : 8; };
    const shown = fc.features.filter(f => (f.properties.end || '9999').slice(0, 10) >= today);
    const lyrs = [];
    shown.forEach(f => {
      const p = f.properties, soon = (p.start || '').slice(0, 10) > today;
      const cls = 'cl ' + p.kind + (p.art ? '' : ' local') + (soon ? ' soon' : '');
      const lyr = f.geometry.type === 'Point'
        ? L.circleMarker(ll(f.geometry.coordinates), {pane:'transit', radius: 6, className: cls})
        : L.polyline(f.geometry.coordinates.map(ll), {pane:'transit', className: cls, weight: w()});
      // Most permits cover a block or less, too short to see zoomed out: a dot marks each one until zoom 15.
      const c = f.geometry.coordinates, mid = f.geometry.type === 'Point' ? null : c[Math.floor((c.length - 1) / 2)];
      const dot = mid && L.marker(ll(c.length === 2 ? [(c[0][0] + c[1][0]) / 2, (c[0][1] + c[1][1]) / 2] : mid), {pane:'pts', keyboard:false, riseOnHover:true,
        icon: L.divIcon({className:'', iconSize:[0, 0], html:'<span class="cl-pin ' + p.kind + (p.art ? '' : ' local') + (soon ? ' soon' : '') + '"></span>'})});
      const tip = esc(p.street) + ' · ' + esc(p.kind === 'closed' ? it.closedText : it.narrowedText) + (soon ? ' · ' + esc(fill(it.startsText, {date: niceDate(p.start)})) : '');
      [lyr, dot].filter(Boolean).forEach(x => { hoverTip(x, tip); x.on('click', e => clPopup(it, p, e.latlng, soon, fc.asof)); g.addLayer(x); });
      if (f.geometry.type !== 'Point') lyrs.push(lyr);
    });
    map.on('zoomend', () => lyrs.forEach(l => l.setStyle({weight: w()})));
    // The panel row says how fresh the data is.
    stampLive(it, fc.asof);
    return g;
  },
  // Road closures for special events (races, parades, street parties), refreshed daily: engine/events.py.
  // Drawn in the event colour so a race course reads as one line. Each closure has its own times (race
  // closures open in waves): ones in force now are solid, later ones faint, ended ones go. Checked again
  // every few minutes while the page is open, so the map keeps up through race day.
  events: (it, fc) => {
    const g = L.layerGroup(), names = {};
    (fc.events || []).forEach(e => { names[e.id] = e; });
    const w = () => { const z = map.getZoom(); return z < 13 ? 5 : z < 15 ? 7 : 9; };
    const items = fc.features.map(f => {
      const p = f.properties, line = f.geometry.type !== 'Point';
      const lyr = line ? L.polyline(f.geometry.coordinates.map(ll), {pane:'transit', className: 'ev ' + p.kind, weight: w()})
        : L.circleMarker(ll(f.geometry.coordinates), {pane:'transit', radius: 6, className: 'ev ' + p.kind});
      lyr.on('click', e => evPopup(it, p, names[p.ev], e.latlng, fc.asof));
      return [lyr, p, line];
    });
    function refresh(){
      const now = cityNow(it.tz);
      items.forEach(([lyr, p]) => {
        const over = (p.end || '9999') <= now, soon = (p.start || '') > now;
        if (over){ if (g.hasLayer(lyr)) g.removeLayer(lyr); return; }
        if (!g.hasLayer(lyr)) g.addLayer(lyr);
        lyr.unbindTooltip(); hoverTip(lyr, esc(p.street) + ' · ' + esc(evWhen(it, p, now)));
        const el = lyr.getElement && lyr.getElement(); if (el) el.classList.toggle('soon', soon);
        lyr.options.className = 'ev ' + p.kind + (soon ? ' soon' : '');
      });
    }
    // A race course the organizer publishes (engine/events.py): a thin line over the closures, a mark at
    // every kilometre (every fifth until zoomed in, by CSS), and start and finish flags. Shown until the
    // event ends.
    const courses = [];
    (fc.events || []).forEach(e => (e.courses || []).forEach(c => {
      const cg = L.layerGroup(), tip = esc(fill(it.courseText || '{name}', {name: c.name, km: c.km, event: e.short}));
      const line = L.polyline(c.line.map(ll), {pane:'evcourse', className:'ev-course', weight: 2.5});
      hoverTip(line, tip); cg.addLayer(line);
      c.marks.forEach((m, i) => cg.addLayer(L.marker(ll(m), {pane:'pts', keyboard:false, interactive:false,
        icon: L.divIcon({className:'', iconSize:[0, 0], html:'<span class="ev-km' + ((i + 1) % 5 ? '' : ' k5') + '">' + (i + 1) + '</span>'})})));
      [['start', c.start, it.startText || 'Start'], ['finish', c.finish, it.finishText || 'Finish']].forEach(([k, at, t]) => {
        const fl = L.marker(ll(at), {pane:'pts', keyboard:false,
          icon: L.divIcon({className:'', iconSize:[0, 0], html:'<span class="ev-flag ' + k + '"><i></i><b>' + esc(t) + '</b></span>'})});
        hoverTip(fl, tip); cg.addLayer(fl);
      });
      courses.push([cg, e.end]);
    }));
    function refreshCourses(){
      const now = cityNow(it.tz);
      courses.forEach(([cg, end]) => { const on = end > now; if (on && !g.hasLayer(cg)) g.addLayer(cg); if (!on && g.hasLayer(cg)) g.removeLayer(cg); });
    }
    refresh(); refreshCourses();
    g.on('add', () => { refresh(); refreshCourses(); });
    setInterval(() => { if (map.hasLayer(g)) { refresh(); refreshCourses(); } }, 5 * 60e3);
    map.on('zoomend', () => items.forEach(([l, , line]) => { if (line) l.setStyle({weight: w()}); }));
    stampLive(it, fc.asof);
    return g;
  },
};
// The time where the city is, as YYYY-MM-DDTHH:MM, to compare with closure times (which are in city time).
function cityNow(tz){ try { return new Date().toLocaleString('sv-SE', {timeZone: tz}).replace(' ', 'T').slice(0, 16); } catch (e) { return new Date().toISOString().slice(0, 16); } }
// "Sun 8:00 a.m." from a city-time "YYYY-MM-DDTHH:MM" (the weekday only when asked for).
function evClock(s, day){
  const d = new Date(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10), +s.slice(11, 13), +s.slice(14, 16));
  return (day ? d.toLocaleDateString(CITY.locale, {weekday:'short'}) + ' ' : '') + d.toLocaleTimeString(CITY.locale, {hour:'numeric', minute:'2-digit'});
}
// When a closure is in force: "Closed now · until 3:30 p.m." or "Sun 8:00 a.m. to 3:30 p.m.".
function evWhen(it, p, now){
  const same = (p.start || '').slice(0, 10) === (p.end || '').slice(0, 10), endDay = (p.end || '').slice(0, 10) !== now.slice(0, 10);
  if ((p.start || '') <= now) return fill(it.nowText, {until: evClock(p.end, endDay)});
  return fill(it.whenText, {from: evClock(p.start, true), to: evClock(p.end, !same)});
}
function evPopup(it, p, ev, latlng, asof){
  const now = cityNow(it.tz), rows = [[it.whenLabel, evWhen(it, p, now)], ev && [it.eventLabel, ev.name]].filter(Boolean);
  L.popup({className:'info-pop', maxWidth: 290, autoPanPadding:[24, 24]}).setLatLng(latlng).setContent(
    '<b>' + esc(p.street) + '</b><small class="ev-k ' + p.kind + '">' + esc(p.kind === 'closed' ? it.closedText : it.narrowedText) + '</small>' +
    (p.extent && p.extent !== p.street ? '<p>' + esc(p.extent) + '</p>' : '') +
    rows.map(([k, v]) => '<div class="kv"><span>' + esc(k) + '</span><span>' + esc(v) + '</span></div>').join('') +
    (p.desc ? '<p class="desc">' + esc(p.desc) + '</p>' : '') +
    (ev && ev.notice ? '<a href="' + esc(ev.notice) + '" target="_blank" rel="noopener">' + esc(it.noticeText) + '</a>' : '') +
    '<p class="fine">' + esc(fill(it.fineText, {date: niceDate(asof)})) + '</p>').openOn(map);
}
// Today's date (YYYY-MM-DD) where the city is, so a permit ending today still shows until midnight there.
function cityToday(tz){ try { return new Date().toLocaleDateString('en-CA', {timeZone: tz}); } catch (e) { return new Date().toISOString().slice(0, 10); } }
function niceDate(s, year){
  if (!s) return '';
  const d = new Date(s.slice(0, 10) + 'T12:00:00'), y = d.getFullYear() !== new Date().getFullYear();
  return d.toLocaleDateString(CITY.locale, {month:'short', day:'numeric', ...(y || year ? {year:'numeric'} : {})});
}
function cxPopup(it, p, latlng, station){
  const rows = [p.owner && ['Built by', p.owner], p.opens && ['Opening', p.opens], p.length && ['Length', p.length]].filter(Boolean);
  L.popup({className:'info-pop', maxWidth: 280, autoPanPadding:[24, 24]}).setLatLng(latlng).setContent(
    '<b>' + esc(station ? station : p.name) + '</b><small>' + esc(station ? (p.name || '') + ' · ' : '') + esc(it.ucText || 'Under construction') + '</small>' +
    (p.about ? '<p>' + esc(p.about) + '</p>' : '') +
    rows.map(([k, v]) => '<div class="kv"><span>' + esc(k) + '</span><span>' + esc(v) + '</span></div>').join('') +
    (p.link ? '<a href="' + esc(p.link) + '" target="_blank" rel="noopener">' + esc(it.linkText || 'Project page') + '</a>' : '')).openOn(map);
}
/* ---------- Heritage buildings ---------- */
const HB = byKind('heritage');
const hbFeatures = () => (HB && loaded[HB.file] ? loaded[HB.file].features : []);
const hbWhen = p => [p.y && fill(HB.builtText, {y: p.y}), p.ar && fill(HB.byText, {ar: p.ar}), p.d && fill(HB.designatedText, {d: p.d})].filter(Boolean).join(' · ');
function hbPopup(it, p, latlng){
  L.popup({className:'info-pop', maxWidth: 280, autoPanPadding:[24, 24]}).setLatLng(latlng).setContent(
    '<b>' + esc(p.n || p.a) + '</b><small>' + esc(it.place) + (p.t ? ' · ' + esc(p.t) : '') + '</small>' +
    (p.n ? '<p class="chg-a">' + esc(p.a) + '</p>' : '') + '<p>' + esc(hbWhen(p)) + '</p>' +
    (p.b ? '<div class="kv"><span>' + esc(it.bylawText) + '</span><span>' + esc(p.b) + '</span></div>' : '') +
    (p.hcd ? '<div class="kv"><span>' + esc(it.hcdText) + '</span><span>' + esc(p.hcd.replace(/ HCD$/, '')) + '</span></div>' : '')).openOn(map);
}
// The card's Heritage building row: the protected property the spot is on (within 40 m, or the one a
// searched name matches within 150 m). [label, text] or null.
function heritageRow(r, x, y, title){
  let best = null, bd = Infinity;
  hbFeatures().forEach(f => { const p = f.properties, d = metres([x, y], f.geometry.coordinates);
    if (d < ((title && p.n === title) ? 150 : 40) && d < bd){ best = p; bd = d; } });
  if (!best) return null;
  return [r.label, (best.n || best.a) + (best.y || best.d ? ' (' + [best.y && fill(HB.builtText, {y: best.y}), best.d && fill(HB.designatedText, {d: best.d})].filter(Boolean).join(', ') + ')' : '')];
}
/* ---------- What's changing ----------
   Sites from engine/changes.py: kind (rezoning, siteplan, subdivision, building, demolition), stage
   (proposed, approved, building, finished), date and what kind of date (applied, issued, finished). */
const CHG = byKind('changes'), CC = CITY.card.changes;
const chgStages = new Set(CHG ? Object.keys(CHG.stages) : []);
let chgP = null;
function ensureChanges(){
  if (!CHG) return Promise.resolve(null);
  return chgP || (chgP = get(CHG.file).then(d => { data.changes = d; if (CHG.live) stampLive(CHG, d.asof); return d; }).catch(() => { chgP = null; return null; }));
}
const chgR = () => { const z = map.getZoom(); return z < 12 ? 2.8 : z < 14 ? 4 : 5.5; };
const chgWhen = p => fill(CHG.dates[p.dl] || '{date}', {date: niceDate(p.date, true)});
const chgKind = p => CHG.kinds[p.k] || p.k;
function chgPopup(p, latlng){
  const also = (p.also || []).map(([k, s, d, u]) => '<li>' + esc(CHG.kinds[k] || k) + ' · ' + esc(CHG.stages[s][0]) + (d ? ' · ' + esc(d.slice(0, 4)) : '') + '</li>').join('');
  L.popup({className:'info-pop chg-pop', maxWidth: 300, autoPanPadding:[24, 24]}).setLatLng(latlng).setContent(
    '<b>' + esc(chgKind(p)) + '</b><small><i class="chg-dot s-' + p.s + '"></i>' + esc(CHG.stages[p.s][0]) + ' · ' + esc(chgWhen(p)) + '</small>' +
    '<p class="chg-a">' + esc(p.a) + (p.units ? ' · ' + esc(fill(CHG.unitsText, {n: p.units})) : '') + '</p>' +
    (p.d ? '<p>' + esc(p.d) + '</p>' : '') +
    (also ? '<div class="chg-also"><span>' + esc(CHG.alsoText) + '</span><ul>' + also + '</ul></div>' : '') +
    (p.u ? '<a href="' + esc(p.u) + '" target="_blank" rel="noopener">' + esc(CHG.linkText) + '</a>' : '')).openOn(map);
}
function setChgStage(s){
  if (chgStages.has(s) && chgStages.size > 1) chgStages.delete(s); else chgStages.add(s);
  document.querySelectorAll('[data-chg]').forEach(b => b.setAttribute('aria-pressed', String(chgStages.has(b.dataset.chg))));
  if (layers[CHG.id] && layers[CHG.id]._draw) layers[CHG.id]._draw();
  queueHash();
}

/* ---------- bike lanes ----------
   Segments from engine/bikes.py: t class (prot, paint, shared, trail), d the City's type in plain words,
   n street or trail, fr / to its ends, y year installed. it.classes {id: [short, long]}, it.default the classes
   drawn at first (else all). */
const BADGES = byKind('badges');
let bdgP = null;
function ensureBadges(){
  if (!BADGES) return Promise.resolve(null);
  return bdgP || (bdgP = get(BADGES.file).catch(() => { bdgP = null; return null; }));
}
const BIKE = byKind('bikes');
const BIKE_DEFAULT = BIKE ? (BIKE.default || Object.keys(BIKE.classes)) : [];
const bkClasses = new Set(BIKE_DEFAULT);
let bkP = null;
function ensureBikes(){
  if (!BIKE) return Promise.resolve(null);
  return bkP || (bkP = get(BIKE.file).then(d => {
    data.bikes = d;
    const n = document.getElementById('bknote'); if (n && d.asof) n.textContent = fill(BIKE.asofText || '{date}', {date: niceDate(d.asof, true)});
    return d;
  }).catch(() => { bkP = null; return null; }));
}
const bkW = t => { const z = map.getZoom(), k = z < 12 ? .7 : z < 13 ? .85 : z < 15 ? 1 : 1.3; return ({prot: 3.4, paint: 2.4, shared: 2, trail: 2.2}[t] || 2) * k; };
function bkPopup(p, latlng){
  const rows = [(p.fr || p.to) && [BIKE.betweenText || 'Between', [p.fr, p.to].filter(Boolean).join(' – ')], p.y && [BIKE.yearText || 'Installed', String(p.y)]].filter(Boolean);
  L.popup({className: 'info-pop bk-pop', maxWidth: 280, autoPanPadding: [24, 24]}).setLatLng(latlng).setContent(
    '<b>' + esc(p.n || p.d) + '</b><small><i class="bk-key t-' + p.t + '"></i>' + esc(p.d) + (p.d.toLowerCase().includes(BIKE.classes[p.t][0].toLowerCase()) ? '' : ' · ' + esc(BIKE.classes[p.t][0])) + '</small>' +
    rows.map(([k, v]) => '<div class="kv"><span>' + esc(k) + '</span><span>' + esc(v) + '</span></div>').join('') +
    (BIKE.fine ? '<p class="bk-fine">' + esc(BIKE.fine) + '</p>' : '')).openOn(map);
}
/* ---------- parks ----------
   Outlines from cities/<city>/parks.py: n name, a the amenities it has (keys of it.amenities), u its page id on the
   City's site (it.linkUrl with {u}), w "splash", "wading" or "both" for the kind of water play. Top level asof
   {parks, outlines, water} and count. Picked chips (pkWant) narrow it: a park must have all of them. */
const PARK = byKind('parks');
const pkWant = new Set();
let pkP = null;
function ensureParks(){
  if (!PARK) return Promise.resolve(null);
  return pkP || (pkP = get(PARK.file).then(d => {
    data.parks = d;
    const n = document.querySelector('label[for="lyr-' + PARK.id + '"] .tx > span');
    if (n && PARK.countNote) n.textContent = fill(PARK.countNote, {n: (d.count || d.features.length).toLocaleString(CITY.locale)});
    return d;
  }).catch(() => { pkP = null; return null; }));
}
const pkMatch = p => { for (const k of pkWant) if (!(p.a || []).includes(k)) return false; return true; };
const pkHas = p => (p.a || []).map(k => k === 'water' && p.w && PARK.waterText ? PARK.waterText[p.w] : PARK.amenities[k][0]);
const pkTip = p => p.n + (p.a && p.a.length ? ' · ' + pkHas(p).join(', ') : '');
function pkPopup(p, latlng){
  const D = data.parks || {}, A = D.asof || {}, has = pkHas(p);
  const fine = fill(PARK.fine || '', {parks: A.parks ? niceDate(A.parks, true) : '', water: A.water ? niceDate(A.water, true) : ''});
  L.popup({className: 'info-pop pk-pop', maxWidth: 280, autoPanPadding: [24, 24]}).setLatLng(latlng).setContent(
    '<b>' + esc(p.n) + '</b><small><i class="pk-key"></i>' + esc(PARK.place || 'Park') + '</small>' +
    (has.length ? '<div class="kv"><span>' + esc(PARK.hasLabel || 'Has') + '</span><span>' + has.map(esc).join(', ') + '</span></div>' : '') +
    (p.w && PARK.seasonText ? '<p class="bk-fine">' + esc(PARK.seasonText) + '</p>' : '') +
    (p.u && PARK.linkUrl ? '<p><a href="' + esc(fill(PARK.linkUrl, {u: p.u})) + '" target="_blank" rel="noopener">' + esc(PARK.linkText || 'Park page') + '</a></p>' : '') +
    (fine ? '<p class="bk-fine">' + esc(fine) + '</p>' : '')).openOn(map);
}
function setParkWant(want){
  pkWant.clear(); (want || []).filter(k => PARK && k in PARK.amenities).forEach(k => pkWant.add(k));
  document.querySelectorAll('[data-pk]').forEach(b => b.setAttribute('aria-pressed', String(pkWant.has(b.dataset.pk))));
  if (PARK && layers[PARK.id] && layers[PARK.id]._draw) layers[PARK.id]._draw();
}
function tapParkAmenity(k){
  pkWant.has(k) ? pkWant.delete(k) : pkWant.add(k);
  setParkWant([...pkWant]);
  queueHash();
}
/* ---------- bike share stations ----------
   Points from engine/bikeshare.py: n name, d docks, e 1 when it charges e-bikes, nc 1 when the kiosk takes no card.
   Top level asof, system, count. The layer's note gains the count once the file is in. */
const DOCK = byKind('docks');
let dkP = null;
function ensureDocks(){
  if (!DOCK) return Promise.resolve(null);
  return dkP || (dkP = get(DOCK.file).then(d => {
    data.docks = d;
    const n = document.querySelector('label[for="lyr-' + DOCK.id + '"] .tx > span');
    if (n && d.count && DOCK.countNote) n.textContent = fill(DOCK.countNote, {n: d.count.toLocaleString(CITY.locale), system: d.system || ''});
    return d;
  }).catch(() => { dkP = null; return null; }));
}
const dkR = () => { const z = map.getZoom(); return z < 13 ? 2.2 : z < 15 ? 3.3 : 4.6; };
// A places layer's details on tap (it.popup: rows [[property, label]…], linkText for the feature's u, fine with {asof}).
function placePopup(it, p, fc, latlng){
  const P = it.popup, rows = (P.rows || []).filter(([k]) => p[k]).map(([k, label]) => [label, p[k]]);
  L.popup({className: 'info-pop', maxWidth: 280, autoPanPadding: [24, 24]}).setLatLng(latlng).setContent(
    '<b>' + esc(p.name) + '</b><small><i class="pl-dot" style="background:var(--in-' + p.cat + ')"></i>' + esc(p.cats && p.sub ? p.sub : placeNoun(it, p.cat)) + '</small>' +
    rows.map(([k, v]) => '<div class="kv"><span>' + esc(k) + '</span><span>' + esc(v) + '</span></div>').join('') +
    (p.u && /^https?:\/\//.test(p.u) && P.linkText ? '<p class="pp-link"><a href="' + esc(p.u) + '" target="_blank" rel="noopener">' + esc(P.linkText) + ' ↗</a></p>' : '') +
    (P.fine ? '<p class="bk-fine">' + esc(fill(P.fine, {asof: (fc && fc.asof) || ''})) + '</p>' : '')).openOn(map);
}
function dkPopup(p, latlng){
  const D = data.docks || {};
  const rows = [p.d && [DOCK.docksLabel || 'Docks', String(p.d)], p.e && [DOCK.chargeLabel || 'E-bikes', DOCK.chargeText || 'Charging station'],
    p.nc && [DOCK.payLabel || 'Paying', DOCK.noCardText || 'No card reader']].filter(Boolean);
  L.popup({className: 'info-pop dk-pop', maxWidth: 280, autoPanPadding: [24, 24]}).setLatLng(latlng).setContent(
    '<b>' + esc(p.n) + '</b><small><i class="dk-key' + (p.e ? ' e' : '') + '"></i>' + esc(fill(DOCK.kindText || '{system} station', {system: D.system || ''})) + '</small>' +
    rows.map(([k, v]) => '<div class="kv"><span>' + esc(k) + '</span><span>' + esc(v) + '</span></div>').join('') +
    (DOCK.fine ? '<p class="bk-fine">' + esc(fill(DOCK.fine, {date: D.asof ? niceDate(D.asof, true) : ''})) + '</p>' : '')).openOn(map);
}
/* ---------- parking spots (kind "spots") ----------
   One points file shared by its layers (e.g. parking.geojson: Green P car parks and EV chargers), each layer's own
   picked by p.c === it.cat. Top level asof {cat: date} and count. Lots: n name or address, t "g" garage or "s"
   surface, cap spaces, h clearance (m), ttc 1 for a transit commuter lot, and where given a address, h24 or hrs
   hours, note (a closure the operator announces). Chargers: n name, a address, l1, l2, dc
   ports, kw fastest DC power, net network, h24 1 for 24 hours (else hrs as listed), fee, tes 1 Tesla only, off 1
   temporarily unavailable, conf the listing's last confirmed date. asof is keyed by cat. Text lives on the layer (city.json). */
const SPOTS = LAYERS.filter(it => it.kind === 'spots');
const BOLT = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M7 1 2.5 7H6l-1 4 4.5-6H6z"/></svg>';
const spotPick = {};   // layer id -> Set of classes shown (none: all)
const spotFiles = {};
function ensureSpots(it){
  if (loaded[it.file]) return Promise.resolve(loaded[it.file]);
  return spotFiles[it.file] || (spotFiles[it.file] = get(it.file).then(d => {
    loaded[it.file] = d;
    SPOTS.filter(s => s.file === it.file && s.countNote).forEach(s => {
      const n = document.querySelector('label[for="lyr-' + s.id + '"] .tx > span'), c = (d.count || {});
      const ctx = {n: (c[s.countKey || s.cat] || 0).toLocaleString(CITY.locale)};
      Object.entries(c).forEach(([k, v]) => { ctx[k] = Number(v).toLocaleString(CITY.locale); });
      if (n) n.textContent = fill(s.countNote, ctx);
    });
    return d;
  }).catch(() => { spotFiles[it.file] = null; return null; }));
}
const spotClass = (it, p) => it.mark === 'lot' ? (p.t === 'g' ? 'g' : 's') : (p.dc ? 'dc' : 'l2');
const spotPorts = p => (p.l1 || 0) + (p.l2 || 0) + (p.dc || 0);
const spotSize = (it, p) => it.mark === 'lot' ? (!p.cap || p.cap < 100 ? 1 : p.cap < 400 ? 2 : 3) : (spotPorts(p) <= 2 ? 1 : spotPorts(p) <= 8 ? 2 : 3);
const plural = (n, [one, many]) => fill(n === 1 ? one : many, {n: n.toLocaleString(CITY.locale)});
function spotTip(it, p){
  if (it.mark === 'lot') return p.n + (p.cap ? ' · ' + plural(p.cap, it.spacesText) : '');
  return p.n + ' · ' + [p.dc && it.dcLabel + ' ' + p.dc, p.l2 && it.l2Label + ' ' + p.l2].filter(Boolean).join(', ') + (p.off ? ' · ' + it.offText : '');
}
function spotPopup(it, p, latlng){
  const D = loaded[it.file] || {}, c = spotClass(it, p), rows = [];
  let kind;
  if (it.mark === 'lot'){
    kind = it.typeText[c];
    if (p.cap) rows.push([it.spacesLabel, plural(p.cap, it.spacesText)]);
    if (p.h) rows.push([it.heightLabel, fill(it.heightText, {h: p.h.toFixed(2)})]);
    if (p.ttc) rows.push([it.ttcLabel, it.ttcText]);
    if (p.a) rows.push([it.addressLabel, p.a]);
    if (p.h24 || p.hrs) rows.push([it.hoursLabel, p.h24 ? it.h24Text : p.hrs]);
    if (p.note) rows.push([it.noteLabel, p.note]);
  } else {
    kind = p.dc && p.l2 ? it.bothText : it.typeText[c];
    if (p.dc) rows.push([it.dcLabel, plural(p.dc, it.portText) + (p.kw ? ' · ' + fill(it.kwText, {kw: p.kw}) : '')]);
    if (p.l2) rows.push([it.l2Label, plural(p.l2, it.portText)]);
    if (p.l1) rows.push([it.l1Label, plural(p.l1, it.portText)]);
    if (p.a && !p.n.includes(p.a.split(' ')[0])) rows.push([it.addressLabel, p.a]);   // not when the name already holds it
    if (p.op) rows.push([it.operatorLabel, p.op]);
    if (p.net) rows.push([it.networkLabel, p.net]);
    if (p.h24 || p.hrs) rows.push([it.hoursLabel, p.h24 ? it.h24Text : p.hrs]);
    if (p.fee) rows.push([it.priceLabel, p.fee]);
    if (p.tes) rows.push([it.accessLabel, it.teslaText]);
    if (p.off) rows.push([it.statusLabel, it.offText]);
  }
  const fine = fill(it.fine || '', {date: D.asof && D.asof[it.cat] ? niceDate(D.asof[it.cat], true) : '', conf: p.conf ? niceDate(p.conf, true) : ''});
  L.popup({className: 'info-pop sp-pop', maxWidth: 300, autoPanPadding: [24, 24]}).setLatLng(latlng).setContent(
    '<b>' + esc(p.n) + '</b><small><i class="sp ' + it.mark + ' c-' + c + ' z-1' + (p.off ? ' off' : '') + '"></i>' + esc(kind) + '</small>' +
    rows.map(([k, v]) => '<div class="kv"><span>' + esc(k) + '</span><span>' + esc(v) + '</span></div>').join('') +
    (fine ? '<p class="bk-fine">' + esc(fine) + '</p>' : '')).openOn(map);
}
function tapSpotClass(id, k){
  const it = LAYERS.find(l => l.id === id), all = Object.keys(it.classes);
  const want = new Set(spotPick[id] || all);
  if (want.has(k) && want.size > 1) want.delete(k); else want.add(k);
  spotPick[id] = want.size === all.length ? null : want;
  document.querySelectorAll('[data-sp="' + id + '"]').forEach(b => b.setAttribute('aria-pressed', String(!spotPick[id] || spotPick[id].has(b.dataset.k))));
  if (layers[id] && layers[id]._draw) layers[id]._draw();
}
function setBikeClasses(want){
  bkClasses.clear(); want.filter(k => k in BIKE.classes).forEach(k => bkClasses.add(k));
  if (!bkClasses.size) BIKE_DEFAULT.forEach(k => bkClasses.add(k));
  document.querySelectorAll('[data-bk]').forEach(b => b.setAttribute('aria-pressed', String(bkClasses.has(b.dataset.bk))));
  if (layers[BIKE.id] && layers[BIKE.id]._draw) layers[BIKE.id]._draw();
}
function tapBikeClass(k){
  const want = new Set(bkClasses);
  if (want.has(k) && want.size > 1) want.delete(k); else want.add(k);
  setBikeClasses([...want]);
  queueHash();
}
/* The card's Changing nearby section: sites within the radius, nearest first, each with what it is, its
   stage and date, the address and distance, a short description and the City's page when there is one. */
function changesHere(x, y){
  const D = data.changes; if (!CC || !CHG || !D) return '';
  const near = D.features.map(f => [f, metres([x, y], f.geometry.coordinates)]).filter(a => a[1] <= CC.radius).sort((a, b) => a[1] - b[1]);
  if (!near.length) return '<div class="live"><p class="chg-none">' + esc(CC.none) + '</p><p>' + esc(fill(CC.note, {date: niceDate(D.asof, true)})) + '</p></div>';
  const rows = near.slice(0, CC.max || 6).map(([f, d]) => { const p = f.properties;
    return '<dt><i class="chg-dot s-' + p.s + (p.k === 'demolition' ? ' demo' : '') + '"></i>' + esc(chgKind(p)) + '</dt><dd>' + esc(p.a) + ' <span class="chg-sub">' + esc(CHG.stages[p.s][0]) + ' · ' + esc(chgWhen(p)) + ' · ' + dist(d) + ' away</span>' +
      (p.d ? '<span class="chg-d">' + esc(p.d.length > 110 ? p.d.slice(0, 110).replace(/\s+\S*$/, '') + '…' : p.d) + '</span>' : '') + (p.u ? '<a class="chg-l" href="' + esc(p.u) + '" target="_blank" rel="noopener">' + esc(CHG.linkText) + '</a>' : '') + '</dd>'; }).join('');
  const more = near.length > (CC.max || 6) ? '<p>' + esc(fill(CC.more, {n: near.length - (CC.max || 6)})) + '</p>' : '';
  return '<div class="live chg"><dl>' + rows + '</dl>' + more + '<p>' + esc(fill(CC.note, {date: niceDate(D.asof, true)})) + '</p></div>';
}
/* The card's Road closures section (card.closures in city.json): closures and lane restrictions from the
   closures layer's file within the radius, nearest first, closed roads ahead of narrowed lanes at the same
   distance. Shown only when there's one nearby, whether or not the layer is on. Permit dates, not forecasts. */
const CLS = byKind('closures'), CLC = CITY.card.closures;
function closuresHere(x, y){
  const D = CLS && CLC && loaded[CLS.file]; if (!D || !D.features.length) return '';
  const today = cityToday(CLS.tz);
  const near = D.features.filter(f => (f.properties.end || '9999').slice(0, 10) >= today).map(f => {
    const c = f.geometry.type === 'Point' ? [f.geometry.coordinates] : f.geometry.coordinates;
    return [f, Math.min(...c.map(pt => metres([x, y], pt)))];
  }).filter(a => a[1] <= CLC.radius).sort((a, b) => (a[1] - b[1]) || (a[0].properties.kind === 'closed' ? -1 : 1));
  if (!near.length) return '';
  const max = CLC.max || 4;
  const rows = near.slice(0, max).map(([f, d]) => { const p = f.properties, soon = (p.start || '').slice(0, 10) > today;
    const long = p.end && p.end.slice(0, 4) - new Date().getFullYear() >= 2;
    const when = (soon ? fill(CLS.startsText, {date: niceDate(p.start)}) + ' · ' : '') + fill(CLS.untilText, {date: niceDate(p.end, long)}) + (long ? ' · ' + CLS.longText : '');
    const hrs = p.hours === '24h' ? CLS.allDayText : p.hours ? p.hours + (p.days ? ' ' + p.days : '') : '';
    return '<dt><i class="cl-key ' + p.kind + '"></i>' + esc(p.kind === 'closed' ? CLS.closedText : CLS.narrowedText) + '</dt><dd>' + esc(p.street) +
      ' <span class="chg-sub">' + esc([when, hrs, p.name, dist(d) + ' away'].filter(Boolean).join(' · ')) + '</span>' +
      (p.extent && p.extent !== p.street ? '<span class="chg-d">' + esc(p.extent) + '</span>' : '') + '</dd>'; }).join('');
  const more = near.length > max ? '<p>' + esc(fill(CLC.more, {n: near.length - max})) + '</p>' : '';
  return '<div class="live chg cls"><dl>' + rows + '</dl>' + more + '<p>' + esc(fill(CLC.note, {date: niceDate(D.asof)})) + '</p></div>';
}
function clPopup(it, p, latlng, soon, asof){
  const long = p.end && p.end.slice(0, 4) - new Date().getFullYear() >= 2;
  const when = (soon ? fill(it.startsText, {date: niceDate(p.start)}) + ' · ' : '') + fill(it.untilText, {date: niceDate(p.end, long)}) + (long ? ' · ' + it.longText : '');
  const hrs = p.hours === '24h' ? it.allDayText : p.hours ? p.hours + (p.days ? ' ' + p.days : '') : '';
  const rows = [[it.whenLabel, when], hrs && [it.hoursLabel, hrs], [it.projectLabel, p.name], p.who && [it.whoLabel, p.who]].filter(Boolean);
  L.popup({className:'info-pop', maxWidth: 290, autoPanPadding:[24, 24]}).setLatLng(latlng).setContent(
    '<b>' + esc(p.street) + '</b><small class="cl-k ' + p.kind + '">' + esc(p.kind === 'closed' ? it.closedText : it.narrowedText) + (p.both && p.kind !== 'closed' ? ' · ' + esc(it.bothText) : '') + '</small>' +
    (p.extent && p.extent !== p.street ? '<p>' + esc(p.extent) + '</p>' : '') +
    rows.map(([k, v]) => '<div class="kv"><span>' + esc(k) + '</span><span>' + esc(v) + '</span></div>').join('') +
    (p.desc ? '<p class="desc">' + esc(p.desc) + '</p>' : '') +
    '<p class="fine">' + esc(fill(it.fineText, {date: niceDate(asof)})) + '</p>').openOn(map);
}
/* ---------- Streetcars and buses ----------
   Routes and stops come from the agency's schedule (engine/surface.py). transit.json (the route list and every
   stop) loads after the map; route shapes for the bus families load the first time they're needed. Families
   describe the service (frequent, express, overnight); nothing is ranked. A route can be picked, from the card,
   search, a link or a tap on its line: it's drawn in ink with its stops, whichever layers are on. */
const TRAMS = byKind('streetcars'), BUSES = byKind('buses'), TR = CITY.card.transit;
const picked = new Set();
/* Bus families on show: any mix of the combinable ones (frequent, express), or one listed in the layer's
   "solo" (overnight) on its own. Daytime streetcars stay on the Streetcars layer, so turning that off
   clears them; streetcars that run only overnight show in the overnight family. */
// The families that can be combined (all but the solo ones); "All" means every one of them is on.
const COMBO = BUSES ? BUSES.families.map(f => f[0]).filter(k => !(BUSES.solo || []).includes(k)) : [];
// What the layer starts with: "all" (every combinable family) or a family id; the first family otherwise.
const BUS_DEFAULT = !BUSES ? [] : BUSES.default === 'all' ? COMBO.slice() : [BUSES.default || BUSES.families[0][0]];
const busFams = new Set(BUS_DEFAULT);
let routeGeo = null, routeGeoP = null;
// "reg" is worked out here too (daytime, neither frequent nor express), so a browser still holding route
// data cached from before the family existed shows the right routes.
const inFam = (r, k) => r.f.includes(k) || (k === 'reg' && r.day !== false && !r.f.includes('freq') && !r.f.includes('exp'));
const busShows = r => (r.m === 'bus' || r.m === 'tram') && [...busFams].some(k => inFam(r, k)) && (!TRAMS || r.m !== 'tram' || r.day === false);
// Other agencies' bus layers (kind "regional"), e.g. GO buses: their stops show from zoom it.stopZoom (default 12).
const REGIONAL = LAYERS.filter(it => it.kind === 'regional');
const allOn = () => COMBO.length > 1 && COMBO.every(k => busFams.has(k));
const busKey = () => !BUSES ? '' : allOn() ? 'all' : BUSES.families.map(f => f[0]).filter(k => busFams.has(k)).join('+');
function ensureRoutes(){
  if (!TR) return Promise.resolve(null);
  return routeGeoP || (routeGeoP = get(TR.routes).then(d => { routeGeo = d; return d; }).catch(() => { routeGeoP = null; return null; }));
}
const routeName = r => r.r + (r.n ? ' ' + r.n : '');
// Classes a route's line, number badge and card chip carry, so a city's CSS can style them the way its
// agency does: freq, exp, night (overnight-only routes always, every route when night says so) and any
// card.transit.routeClasses [[pattern, class]] whose pattern matches the route number (e.g. "^X").
const RCLS = ((TR && TR.routeClasses) || []).map(([re, c]) => [new RegExp(re), c]);
const routeCls = (r, night) => (r.f.includes('freq') ? ' freq' : '') + (r.f.includes('exp') ? ' exp' : '') +
  (night || r.day === false ? ' night' : '') + RCLS.filter(([re]) => re.test(r.r)).map(([, c]) => ' ' + c).join('');
const routeTip = p => esc(routeName(p)) + (p.h ? ' · ' + esc(fill(TR.every, {h: p.h})) : '') + (p.day === false ? ' · ' + esc(TR.nightOnly) : '');
// A point a fraction t of the way along a line (lengths roughly in metres-per-degree at these latitudes).
function along(c, t){
  const d = [0];
  for (let i = 1; i < c.length; i++) d.push(d[i - 1] + Math.hypot((c[i][0] - c[i - 1][0]) * .72, c[i][1] - c[i - 1][1]));
  const T = d[d.length - 1] * t; let i = 1;
  while (i < d.length - 1 && d[i] < T) i++;
  const s = (T - d[i - 1]) / ((d[i] - d[i - 1]) || 1);
  return [c[i - 1][0] + (c[i][0] - c[i - 1][0]) * s, c[i - 1][1] + (c[i][1] - c[i - 1][1]) * s];
}
const span = c => c.reduce((a, p, i) => i ? a + Math.hypot((p[0] - c[i - 1][0]) * .72, p[1] - c[i - 1][1]) : 0, 0);
/* Rapid-transit line badges: each line's number, letters or name in its own colour, sitting on the line.
   it.badges maps a line id to its label: a string, or a list for a trunk that carries several services
   (New York's A C E). One or two characters make a round bullet; a word makes a pill. With the whole line
   in view the badge goes near its outer end, the way transit maps mark lines; zoomed in, it is re-placed
   after every move on the longest stretch of the line in the open part of the map (clear of the panels,
   other badges and, where there's room, names), so a line on screen always says which it is. A badge keeps
   its spot while that spot stays in view, so panning doesn't make them jump. */
function lineBadges(it, fc, lg, owner){
  const g = L.layerGroup(), B = it.badges || {}, last = {};
  let lastZ = null;
  // The line's colour: the variable its CSS rule strokes with (so it follows the theme), else what's drawn.
  const rule = id => { for (const sh of document.styleSheets){ let rs; try { rs = sh.cssRules; } catch (e) { continue; }
    for (const r of rs) if (r.selectorText === '.sub-line.l' + id && r.style.stroke) return r.style.stroke; } return null; };
  const ink = c => { const m = String(c).match(/\d+(\.\d+)?/g); if (!m || m.length < 3) return '#fff';
    const [r, gg, b] = m.slice(0, 3).map(Number); return (r * 299 + gg * 587 + b * 114) / 1000 > 165 ? '#111' : '#fff'; };
  const paths = {}; lg.eachLayer(l => { paths[l.feature.properties.line] = l; });
  const items = fc.features.map(f => {
    const p = f.properties, parts = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.coordinates;
    const labs = [].concat(B[p.line] != null ? B[p.line] : p.line);
    // A part's end is the end of the line if no other part of it carries on from there (not a junction).
    const near = (a, b) => Math.abs(a[0] - b[0]) < 2e-4 && Math.abs(a[1] - b[1]) < 2e-4;
    const loose = (pt, i) => !parts.some((q, j) => j !== i && q.some(v => near(v, pt)));
    const ends = parts.map((c, i) => [loose(c[0], i), loose(c[c.length - 1], i)]);
    const w = labs.reduce((a, s) => a + (String(s).length > 2 ? String(s).length * 6.6 + 12 : 18) + 2, 0);
    return {f, p, parts, labs, ends, w, v: rule(p.line)};
  });
  const html = x => {
    const el = paths[x.p.line] && paths[x.p.line].getElement(), c = x.v || x.p.color || (el && getComputedStyle(el).stroke) || 'var(--ink)';
    const seen = el ? getComputedStyle(el).stroke : x.p.color, fg = ink(seen || '');
    return '<span class="sub-b">' + x.labs.map(s => '<i class="' + (String(s).length > 2 ? 'w' : '') + '" style="background:' + c + ';color:' + fg + '">' + esc(s) + '</i>').join('') + '</span>';
  };
  const len = r => r.reduce((a, q, i) => i ? a + q.distanceTo(r[i - 1]) : 0, 0);
  const at = (r, d) => { for (let i = 1; i < r.length; i++){ const s = r[i].distanceTo(r[i - 1]); if (d <= s) return r[i - 1].add(r[i].subtract(r[i - 1]).multiplyBy(s ? d / s : 0)); d -= s; } return r[r.length - 1]; };
  function place(){
    g.clearLayers();
    if (!map.hasLayer(owner)) return;
    const size = map.getSize(), mr = map.getContainer().getBoundingClientRect(), m = 16;
    const view = L.bounds([m, m], [size.x - m, size.y - m]), mid = size.divideBy(2);
    const rects = sel => [...document.querySelectorAll(sel)].map(el => el.getBoundingClientRect()).filter(r => r.width && r.height)
      .map(r => [r.left - mr.left - 4, r.top - mr.top - 4, r.right - mr.left + 4, r.bottom - mr.top + 4]);
    // Hard: the panels and controls floating over the map, then each badge as it's placed. Soft (kept clear of
    // where there's room): names of streets and stations, station dots, route numbers.
    const hard = saving ? [] : rects('#panel, #search, #here, #ptabs, .leaflet-control');
    const soft = rects('.st-lbl, .leaflet-tooltip.lbl, .stn, .rt-b, .shield, .lm i');
    const hits = (b, list) => list.some(o => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]);
    // Busiest lines first, so the trunks with several services get the best spots.
    [...items].sort((a, b) => b.labs.length - a.labs.length).forEach(x => {
      const box = q => [q.x - x.w / 2 - 2, q.y - 11, q.x + x.w / 2 + 2, q.y + 11];
      const inView = q => q.x - x.w / 2 > m && q.x + x.w / 2 < size.x - m && q.y > m + 10 && q.y < size.y - m - 10;
      const ok = (q, strict) => inView(q) && !hits(box(q), hard) && (!strict || !hits(box(q), soft));
      // The line's stretches in view (screen points), noting which ends are the end of the line.
      const runs = [];
      x.parts.forEach((c, i) => {
        const px = c.map(v => map.latLngToContainerPoint([v[1], v[0]]));
        let cur = null;
        for (let k = 1; k < px.length; k++){
          const s = L.LineUtil.clipSegment(px[k - 1], px[k], view, false, false);
          if (!s){ if (cur){ runs.push(cur); cur = null; } continue; }
          if (!cur || cur.pts[cur.pts.length - 1] !== s[0]){ if (cur) runs.push(cur); cur = {pts: [s[0]], a: k === 1 && s[0] === px[0] && x.ends[i][0], b: false}; }
          cur.pts.push(s[1]);
          if (k === px.length - 1 && s[1] === px[k] && x.ends[i][1]) cur.b = true;
        }
        if (cur) runs.push(cur);
      });
      if (!runs.length){ delete last[x.p.line]; return; }
      runs.forEach(r => { r.len = len(r.pts); });
      const cands = [];
      // Where it was, if that's still in view and the zoom hasn't changed (a new zoom starts afresh).
      if (last[x.p.line] && lastZ === map.getZoom()) cands.push(map.latLngToContainerPoint(last[x.p.line]));
      // Near an end of the line, outermost first (the ends spread out; the middles bunch up downtown).
      const tips = [];
      runs.forEach(r => { if (r.len < 40) return;
        if (r.a) tips.push([r.pts, r.pts[0]]);
        if (r.b){ const rev = [...r.pts].reverse(); tips.push([rev, rev[0]]); } });
      tips.sort((a, b) => b[1].distanceTo(mid) - a[1].distanceTo(mid))
        .forEach(([pts]) => [x.w / 2 + 16, x.w / 2 + 40, x.w / 2 + 70].forEach(d => cands.push(at(pts, d))));
      // Otherwise along the longest stretches in view, from their middles outward.
      runs.sort((a, b) => b.len - a.len).slice(0, 4).forEach(r => [.5, .4, .6, .3, .7, .2, .8, .1, .9].forEach(t => cands.push(at(r.pts, r.len * t))));
      // Where every spot is crowded, the one that covers the fewest names.
      const cover = q => soft.filter(o => { const b = box(q); return b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]; }).length;
      const best = cands.filter(q => ok(q, false)).map(q => [q, cover(q)]).reduce((a, b) => !a || b[1] < a[1] ? b : a, null);
      const q = cands.find(q => ok(q, true)) || (best && best[0]);
      if (!q) return;
      hard.push(box(q));
      const ll_ = map.containerPointToLatLng(q); last[x.p.line] = ll_;
      const mk = L.marker(ll_, {pane:'pts', keyboard:false, zIndexOffset: 500,
        icon: L.divIcon({className:'', iconSize:[0, 0], html: html(x)})});
      hoverTip(mk, x.p.name);
      mk.on('click', e => inspect(e.latlng));
      g.addLayer(mk);
    });
    lastZ = map.getZoom();
  }
  map.on('moveend', place); owner.on('add', () => setTimeout(place));
  // A new theme changes the lines' colours (and so whether the text on a badge reads better dark or light).
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => setTimeout(place));
  new MutationObserver(() => setTimeout(place)).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
  setTimeout(place);
  return g;
}
// Route lines with number badges. Line widths follow the zoom through CSS (.z12, .z14 on the map).
// opts.pane: the map pane (default 'transit'); opts.within(c): badges go mid-way along the longest stretch
// of the route where it's true (e.g. inside the city), or nowhere if there's none.
function longestRun(c, ok){
  let best = [], cur = [];
  c.forEach(p => { if (ok(p)) cur.push(p); else { if (span(cur) > span(best)) best = cur; cur = []; } });
  return span(cur) > span(best) ? cur : best;
}
function routeLines(feats, pick, extra, opts){
  const pane = (opts && opts.pane) || 'transit', within = opts && opts.within;
  // Every casing goes in before any line, or a casing's rounded end would nick the line drawn before it.
  const g = L.layerGroup(), cases = L.layerGroup(), lines = L.layerGroup();
  g.addLayer(cases); g.addLayer(lines);
  feats.forEach(f => {
    const p = f.properties, parts = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.coordinates;
    const x = ' ' + p.m + (pick ? ' pick' : '') + routeCls(p, opts && opts.night) + (extra ? extra(p) : '');
    parts.forEach(c => {
      cases.addLayer(L.polyline(c.map(ll), {pane, className:'rt-case' + x, interactive:false, feat: f}));
      const pl = L.polyline(c.map(ll), {pane, className:'rt' + x, bubblingMouseEvents:false, feat: f});
      hoverTip(pl, routeTip(p));
      pl.on('click', () => focusRoute(p.r));
      lines.addLayer(pl);
    });
    // Number badges: tapping one shows that route alone too.
    let long = parts.reduce((a, b) => span(b) > span(a) ? b : a);
    if (within) long = parts.map(c => longestRun(c, within)).reduce((a, b) => span(b) > span(a) ? b : a, []);
    if (long.length < 2) return;
    (pick ? [0, .5, 1] : within ? [.5] : [.25, .75]).forEach(t => {
      const m = L.marker(ll(along(long, t)), {pane:'pts', keyboard:false, title: routeName(p), feat: f,
        icon: L.divIcon({className:'', iconSize:[0, 0], html:'<span class="rt-b' + x + '">' + esc(p.r) + '</span>'})});
      m.on('click', () => focusRoute(p.r));
      g.addLayer(m);
    });
  });
  return g;
}
const pickLayer = L.layerGroup().addTo(map);
/* Focus: tapping a route's line or number shows it alone. It's drawn like a picked route, everything
   else on the map's route layers fades (CSS: #map.rt-focus) and only its stops show. Tapping it again,
   anywhere else on the map, or Escape brings the rest back. Not kept in links: it's a passing look. */
let focusR = null;
function focusRoute(r){
  focusR = focusR === r ? null : r;
  map.getContainer().classList.toggle('rt-focus', !!focusR);
  ensureRoutes().then(drawPicks);
}
function unfocus(){ if (focusR) focusRoute(focusR); }
// While a route is shown alone, the next tap elsewhere only brings the rest back (no card). Leaflet fires
// 'preclick' before any layer's click; inspect() skips the tap that's being swallowed.
let swallowTap = false;
map.on('preclick', () => { if (focusR){ swallowTap = true; unfocus(); setTimeout(() => { swallowTap = false; }); } });
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
  if (focusR) unfocus(); else if (placeF) setPlaceFocus(null, null, false);
});
function drawPicks(){
  pickLayer.clearLayers();
  if (routeGeo && picked.size) pickLayer.addLayer(routeLines(routeGeo.features.filter(f => picked.has(f.properties.r) && f.properties.r !== focusR), true));
  if (routeGeo && focusR) pickLayer.addLayer(routeLines(routeGeo.features.filter(f => f.properties.r === focusR), true, () => ' focus'));
  drawStops(); drawBusBox();
  here.querySelectorAll('[data-route]').forEach(b => b.setAttribute('aria-pressed', String(picked.has(b.dataset.route))));
}
function pickRoute(r, on){
  if (on) picked.add(r); else picked.delete(r);
  ensureRoutes().then(drawPicks); queueHash();
}
// From search: pick the route and frame the whole of it.
function goRoute(r){
  showResults(''); q.value = routeName(r);
  pickRoute(r.r, true);
  if (matchMedia('(max-width:760px)').matches) panel.classList.add('collapsed');
  frame(L.latLngBounds([[r.b[1], r.b[0]], [r.b[3], r.b[2]]]));
}
// Stops from zoom 15 for the routes each layer is drawing (daytime streetcars; the bus families on show), and a
// picked route's from zoom 13; only in view. A stop whose routes aren't drawn stays hidden, so no stop floats.
const stopLayer = L.layerGroup().addTo(map);
function drawStops(){
  stopLayer.clearLayers();
  const T = data.transit; if (!T) return;
  const z = map.getZoom() + .01, b = map.getBounds().pad(.1);
  const tram = TRAMS && state[TRAMS.id] && z >= 15, bus = BUSES && state[BUSES.id] && z >= 15;
  const reg = new Set(REGIONAL.filter(it => state[it.id] && z >= (it.stopZoom || 12)).map(it => it.mode));
  const want = r => focusR ? r.r === focusR : picked.has(r.r);
  const pk = (picked.size || focusR) && z >= 13 ? new Set(T.routes.map((r, i) => want(r) ? i : -1).filter(i => i >= 0)) : null;
  if (!tram && !bus && !pk && !reg.size) return;
  T.stops.forEach(s => {
    if (!b.contains([s[1], s[0]])) return;
    if (focusR && !(pk && s[3].some(i => pk.has(i)))) return;   // showing one route: only its stops
    const rs = s[3].map(i => T.routes[i]), isTram = rs.some(r => r.m === 'tram' && r.day), onPick = pk && s[3].some(i => pk.has(i));
    const onBus = bus && rs.some(busShows), onReg = rs.find(r => reg.has(r.m));
    if (!(onPick || (tram && isTram) || onBus || onReg)) return;
    // In the city view, another agency's stops outside the city stay hidden with the rest of the region.
    if (!onPick && !onBus && !(tram && isTram) && scope === 'inner' && data.footprint && !hit(data.footprint, s[0], s[1])) return;
    // Another agency's stops are few (terminals, highway stops), so they're a size up and named from zoom 14.
    const regOnly = !onPick && !onBus && !(tram && isTram);
    const m = L.circleMarker([s[1], s[0]], {pane:'pts', radius: (z >= 16 ? 4 : 3) + (regOnly ? 1.5 : 0), className:'stop ' + (onPick ? 'pick' : isTram ? 'tram' : onBus ? 'bus' : onReg.m), bubblingMouseEvents:false, stopOf: s[3]});
    hoverTip(m, esc(s[2]) + ' · ' + esc(rs.map(r => r.r).join(', ')));
    m.on('click', () => inspect(L.latLng(s[1], s[0]), s[2]));
    stopLayer.addLayer(m);
    if (regOnly && z >= 14) stopLayer.addLayer(L.tooltip({permanent:true, direction:'right', offset:[7, 0], className:'lbl lbl-go', interactive:false}).setLatLng([s[1], s[0]]).setContent(esc(s[2])));
  });
}
map.on('moveend', drawStops);
// The bus layer's panel box: pick a family; routes picked elsewhere are listed with a way to clear them.
function drawBusBox(){
  if (!BUSES) return;
  const box = document.getElementById('busbox'); if (!box) return;
  box.querySelectorAll('[data-fam]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.fam === 'all' ? allOn() : busFams.has(b.dataset.fam) && !allOn())));
  const fams = BUSES.families.filter(f => busFams.has(f[0])), n = data.transit ? data.transit.routes.filter(busShows).length : null;
  document.getElementById('busnote').textContent = (n != null ? fill(BUSES.countText, {n}) + '. ' : '') + (allOn() && BUSES.allNote ? BUSES.allNote : fams.map(f => f[2]).join(' ')) +
    (fams.length > 1 && BUSES.comboText ? ' ' + BUSES.comboText : '') + ' ' + BUSES.hint;
  const pk = document.getElementById('buspick');
  pk.hidden = !picked.size;
  pk.innerHTML = picked.size ? '<small>' + esc(BUSES.pickText) + '</small><div class="chips">' + [...picked].map(r =>
    '<button type="button" data-unpick="' + esc(r) + '" aria-label="' + esc(fill(BUSES.unpickText, {r})) + '">' + esc(r) + ' ×</button>').join('') +
    '<button type="button" class="clr" data-unpick="">' + esc(BUSES.clearText) + '</button></div>' : '';
  pk.querySelectorAll('[data-unpick]').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.unpick) pickRoute(b.dataset.unpick, false); else { picked.clear(); ensureRoutes().then(drawPicks); queueHash(); }
  }));
}
// A chip tap: a solo family replaces the rest; a combinable one toggles (and replaces a solo one).
// At least one family stays on.
// "All" turns every combinable family on. From All, tapping one family narrows to just it.
function tapBusFam(f){
  const solo = BUSES.solo || [];
  if (f === 'all') setBusFams(COMBO);
  else if (solo.includes(f) || [...busFams].some(k => solo.includes(k)) || allOn()) setBusFams([f]);
  else if (!busFams.has(f)) setBusFams([...busFams, f]);
  else if (busFams.size > 1) setBusFams([...busFams].filter(k => k !== f));
}
function setBusFams(list){
  if (!BUSES) return;
  if (list.includes('all')) list = COMBO;
  const ok = list.filter(f => BUSES.families.some(x => x[0] === f)), solo = BUSES.solo || [];
  const pickd = ok.some(f => solo.includes(f)) ? [ok.find(f => solo.includes(f))] : ok;
  if (!pickd.length) return;
  busFams.clear(); pickd.forEach(f => busFams.add(f));
  if (layers[BUSES.id] && layers[BUSES.id]._draw) layers[BUSES.id]._draw();
  drawBusBox(); drawStops(); queueHash();
}
/* The card's transit section: the nearest rapid-transit station, then every route with a stop within the radius,
   by mode, nearest first, and the nearest stop. Numbers are buttons that draw the route. Filled numbers mark
   frequent routes (a description of the service, not a score). */
function transitHere(x, y){
  const T = data.transit; if (!TR || !T) return '';
  const near = new Map(); let best = null;
  const dy = TR.radius / 111000 * 1.2;
  T.stops.forEach(s => {
    if (Math.abs(s[1] - y) > dy) return;
    const d = metres([x, y], s); if (d > TR.radius) return;
    s[3].forEach(i => { if (!near.has(i) || d < near.get(i)) near.set(i, d); });
    if (!best || d < best[1]) best = [s, d];
  });
  const list = [...near].sort((a, b) => a[1] - b[1]).map(([i]) => T.routes[i]);
  const chip = (r, named, night) => '<button type="button" class="rt-chip ' + r.m + routeCls(r, night) + '" data-route="' + esc(r.r) + '" aria-pressed="' + picked.has(r.r) + '" title="' + routeTip(r) + '">' + esc(named ? routeName(r) : r.r) + '</button>';
  let rows = '';
  const stns = METRO && loaded[[].concat(METRO.files)[1]];
  if (TR.station && stns){
    const s = stns.features.map(f => [f, metres([x, y], f.geometry.coordinates)]).sort((a, b) => a[1] - b[1])[0];
    if (s && s[1] < (TR.stationMax || 5000)) rows += '<dt>' + esc(TR.station) + '</dt><dd>' + esc(s[0].properties.name) + '<span>' + esc(fill(TR.stationSub, {lines: s[0].properties.lines, dist: dist(s[1])})) + '</span></dd>';
  }
  TR.rows.forEach(([mode, label, named]) => {
    const rs = list.filter(r => r.m === mode && r.day);
    if (rs.length) rows += '<dt>' + esc(label) + '</dt><dd><span class="rt-chips">' + rs.map(r => chip(r, named)).join('') + '</span></dd>';
  });
  const night = list.filter(r => r.f.includes('night'));
  if (night.length) rows += '<dt>' + esc(TR.night) + '</dt><dd><span class="rt-chips">' + night.map(r => chip(r, false, true)).join('') + '</span></dd>';
  rows += '<dt>' + esc(TR.stop) + '</dt><dd>' + (best ? esc(best[0][2]) + '<span>' + dist(best[1]) + ' away</span>' : '<span>' + esc(TR.none) + '</span>') + '</dd>';
  // Bike share (TR.bikeshare): the nearest station within its radius, with its docks and e-bike charging.
  const BS = TR.bikeshare, DK = data.docks;
  if (BS && DK && DK.features){
    let bs = null;
    DK.features.forEach(f => { const c = f.geometry.coordinates; if (Math.abs(c[1] - y) > BS.radius / 111000 * 1.2) return;
      const d = metres([x, y], c); if (d <= BS.radius && (!bs || d < bs[1])) bs = [f.properties, d]; });
    rows += '<dt>' + esc(BS.label) + '</dt><dd>' + (bs ? esc(bs[0].n) + '<span>' + esc(fill(BS.sub, {dist: dist(bs[1]), docks: bs[0].d})) +
      (bs[0].e && BS.charge ? ' · ' + esc(BS.charge) : '') + '</span>' : '<span>' + esc(BS.none) + '</span>') + '</dd>';
  }
  return '<div class="live transit"><dl>' + rows + '</dl><p>' + esc(fill(TR.note, {week: niceDate(T.week)})) + '</p></div>';
}
// Drawing order: the order layers join the map decides which sits on top within a pane.
const RANK = it => ({fill: it.size === 'major' ? 0 : 1, lens: 2, suburbs: 2, patches: 3, parks: 2.8, districts: 3, units: 4, boards: 4.5, badges: 8.5, outline: {national: 5, state: 6, city: 7}[it.level], knownas: 8, streets: it.under ? 8.9 : 9, bikes: 9.2, docks: 13.8, spots: 13.85, highways: 10, addresses: 9.5, rail: 11, changes: 12.4, heritage: 13.5, regional: 11.2, buses: 11.5, streetcars: 11.6, metro: 12, construction: 12.3, closures: 12.6, events: 12.7, landmarks: 13, places: 14, towers: 14.5})[it.kind];
const ORDER = LAYERS.map(it => it).sort((a, b) => RANK(a) - RANK(b));

/* ---------- panel ---------- */
const state = {};
// The group picked on each places layer that has "groups" ('all' when none is picked).
const placePick = {};
const host = document.getElementById('layers');
/* Groups fold: tap a group's heading to hide its toggles (layers that are on stay on; the heading
   then says how many). Which groups are folded is remembered in this browser, per city. */
const FOLD_KEY = 'groupsFolded-' + CITY.id;
let foldedGroups = [];
try { foldedGroups = JSON.parse(localStorage.getItem(FOLD_KEY) || '[]') || []; } catch (e) {}
const CHEVRON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
function foldGroup(g, fold, save){
  g.classList.toggle('folded', fold);
  g.querySelector('.gh').setAttribute('aria-expanded', String(!fold));
  g.querySelector('.gb').hidden = fold;
  if (!save) return;
  foldedGroups = foldedGroups.filter(t => t !== g.dataset.group);
  if (fold) foldedGroups.push(g.dataset.group);
  try { if (foldedGroups.length) localStorage.setItem(FOLD_KEY, JSON.stringify(foldedGroups)); else localStorage.removeItem(FOLD_KEY); } catch (e) {}
}
// "3 on" beside a folded group's heading.
function groupCounts(){
  host.querySelectorAll('.grp').forEach(g => {
    const n = [...g.querySelectorAll('.row input[type=checkbox]')].filter(cb => cb.checked).length;
    const c = g.querySelector('.gon'); if (c) c.textContent = n ? fill(CITY.groupOnText || '{n} on', {n}) : '';
  });
}
const PLINK_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="14" rx="3"/><path d="M5 11h14M8 17v3M16 17v3"/><circle cx="8.5" cy="14" r=".6" fill="currentColor"/><circle cx="15.5" cy="14" r=".6" fill="currentColor"/></svg>';
CITY.groups.forEach(([title, items]) => {
  const grpOuter = document.createElement('div'); grpOuter.className = 'grp'; grpOuter.dataset.group = title;
  const gid = 'grp-' + title.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  grpOuter.innerHTML = '<h2><button type="button" class="gh" aria-expanded="true" aria-controls="' + gid + '"><span>' + title + '</span><small class="gon"></small>' + CHEVRON + '</button></h2><div class="gb" id="' + gid + '"></div>';
  const body = grpOuter.querySelector('.gb');
  grpOuter.querySelector('.gh').addEventListener('click', () => { const f = !grpOuter.classList.contains('folded'); foldGroup(grpOuter, f, true); logEvent(f ? 'group_fold' : 'group_open', {id: gid.slice(4)}); });
  items.forEach(it => {
    // Each layer's row and its boxes sit in one wrapper, so a panel tab can hide them together.
    const grp = document.createElement('div'); grp.className = 'it'; grp.dataset.live = it.live ? '1' : '';
    body.appendChild(grp);
    const row = document.createElement('label'); row.className = 'row' + (it.under ? ' child' : ''); row.htmlFor = 'lyr-' + it.id;
    row.innerHTML = '<span class="sw ' + it.id + ' k-' + (it.kind === 'outline' ? it.level : it.kind) + (it.kind === 'places' ? ' in-' + placeIcon(it) : '') + '">' + swatchOf(it) + '</span><span class="tx"><b>' + it.name + '</b><span>' + it.note + '</span></span>' +
      '<input type="checkbox" id="lyr-' + it.id + '"' + (it.on ? ' checked' : '') + '><span class="tg" aria-hidden="true"></span>';
    grp.appendChild(row);
    row.querySelector('input').addEventListener('change', e => { setLayer(it.id, e.target.checked); if (e.target.checked) logEvent('layer_on', {id: it.id}); });
    if (it.kind === 'lens'){
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'lensbox'; box.hidden = !it.on;
      box.innerHTML = '<div class="seg" role="radiogroup" aria-label="' + esc(CITY.lens.label) + '">' +
        Object.entries(LENSES).map(([k, L_]) => '<button type="button" role="radio" data-lens="' + k + '" aria-checked="' + (k === lens) + '">' + L_.short + '</button>').join('') +
        '</div><div class="legend" id="legend"></div>' +
        '<div class="finder"><b>Narrow it down</b><span>Pick what you’re looking for. ' + cap(CITY.units.plural) + ' that don’t fit fade out.</span>' +
        FILTERS.map(f => '<div class="frow"><small data-flab="' + f.lens + '">' + (hubLens && f.lens === hubLens.id ? hubOf(hubLens).filter || f.label : f.label) + '</small><div class="chips">' +
            f.options.map(([v, t]) => '<button type="button" aria-pressed="false" data-f="' + f.lens + '" data-v="' + v + '">' + t + '</button>').join('') + '</div></div>').join('') +
        '<div class="fres" id="fres" hidden><span id="fcount"></span><button type="button" id="fclear">Clear</button></div><div class="flist" id="flist"></div></div>';
      grp.appendChild(box);
      box.querySelectorAll('[data-lens]').forEach(b => b.addEventListener('click', () => { setLens(b.dataset.lens); logEvent('lens', {id: b.dataset.lens}); }));
      box.querySelectorAll('[data-f]').forEach(b => b.addEventListener('click', () => {
        const k = b.dataset.f, v = b.dataset.v;
        if (typeof filt[k] === 'number') filt[k] = filt[k] === +v ? 0 : +v;
        else filt[k].has(v) ? filt[k].delete(v) : filt[k].add(v);
        applyFilter(); queueHash();
      }));
      box.querySelector('#fclear').addEventListener('click', () => { clearFilters(); applyFilter(); queueHash(); });
    }
    if (it.kind === 'boards' && it.boards.length > 1){   // one board: nothing to pick
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'brd-' + it.id; box.hidden = !it.on;
      box.innerHTML = '<div class="chips pick" role="radiogroup" aria-label="' + esc(it.name) + '">' + it.boards.map(([b, short, long]) =>
        '<button type="button" role="radio" data-board="' + b + '" data-layer="' + it.id + '" title="' + esc(long) + '" aria-checked="' + (b === boardPick[it.id]) + '">' + esc(short) + '</button>').join('') +
        '</div><div class="legend"><small id="brdnote-' + it.id + '"></small></div>';
      grp.appendChild(box);
      box.querySelectorAll('[data-board]').forEach(b => b.addEventListener('click', () => setBoard(it.id, b.dataset.board)));
    }
    if (it.kind === 'buses'){   // one family at a time, plus any routes picked from the card or search
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'busbox'; box.hidden = !it.on;
      // First row: All and the families that combine; then the solo ones (overnight) on their own row.
      const chip = ([f, short]) => '<button type="button" data-fam="' + f + '" aria-pressed="false">' + esc(short) + '</button>';
      const solo = it.solo || [], combo = it.families.filter(f => !solo.includes(f[0]));
      box.innerHTML = '<div class="chips pick" role="group" aria-label="' + esc(it.name) + '">' + (it.allText && combo.length > 1 ? chip(['all', it.allText]) : '') + combo.map(chip).join('') +
        '</div>' + (solo.length ? '<div class="chips pick" role="group" aria-label="' + esc(it.name) + '">' + it.families.filter(f => solo.includes(f[0])).map(chip).join('') + '</div>' : '') +
        '<div class="legend"><small id="busnote"></small></div><div class="buspick" id="buspick" hidden></div>';
      grp.appendChild(box);
      box.querySelectorAll('[data-fam]').forEach(b => b.addEventListener('click', () => tapBusFam(b.dataset.fam)));
    }
    if (it.kind === 'places' && it.cats){   // categories, any mix; each chip with a dot in its pins' colour
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'pc-' + it.id; box.hidden = !it.on;
      box.innerHTML = '<div class="chips pick" role="group" aria-label="' + esc(it.name) + '">' + it.cats.map(([c, short]) =>
        '<button type="button" data-pc="' + it.id + '" data-c="' + c + '" aria-pressed="' + !it.narrow + '"><i class="pl-dot" style="background:var(--in-' + c + ')"></i>' + esc(short) + '</button>').join('') +
        '</div>' + (it.catNote ? '<div class="legend"><small>' + esc(it.catNote) + '</small></div>' : '');
      grp.appendChild(box);
      box.querySelectorAll('[data-pc]').forEach(b => b.addEventListener('click', () => { tapPlaceCat(it.id, b.dataset.c); logEvent('place_cat', {id: it.id + ':' + b.dataset.c}); }));
    }
    if (it.kind === 'places' && it.groups){   // one group at a time, All first
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'pg-' + it.id; box.hidden = !it.on;
      box.innerHTML = (it.groupLabel ? '<small class="pc-lab">' + esc(it.groupLabel) + '</small>' : '') + '<div class="chips pick" role="radiogroup" aria-label="' + esc(it.groupLabel || it.name) + '">' +
        [['all', it.allText || 'All']].concat(it.groups).map(([g, short]) => '<button type="button" role="radio" data-pg="' + g + '" aria-checked="' + (g === 'all') + '">' + esc(short) + '</button>').join('') +
        '</div><div class="legend"><small id="pgnote-' + it.id + '"></small></div>';
      grp.appendChild(box);
      box.querySelectorAll('[data-pg]').forEach(b => b.addEventListener('click', () => setPlacePick(it.id, b.dataset.pg)));
    }
    if (it.kind === 'changes'){   // stages, any mix, each chip its own colour key
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'chgbox'; box.hidden = !it.on;
      box.innerHTML = '<div class="chips pick" role="group" aria-label="' + esc(it.name) + '">' + Object.entries(it.stages).map(([s, [short, long]]) =>
        '<button type="button" data-chg="' + s + '" aria-pressed="true" title="' + esc(long) + '"><i class="chg-dot s-' + s + '"></i>' + esc(short) + '</button>').join('') +
        '</div><div class="legend"><small>' + esc(it.legend) + '</small></div>';
      grp.appendChild(box);
      box.querySelectorAll('[data-chg]').forEach(b => b.addEventListener('click', () => setChgStage(b.dataset.chg)));
    }
    if (it.kind === 'bikes'){   // classes, any mix, each chip with a key to its line
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'bkbox'; box.hidden = !it.on;
      box.innerHTML = '<div class="chips pick" role="group" aria-label="' + esc(it.name) + '">' + Object.entries(it.classes).map(([k, [short, long]]) =>
        '<button type="button" data-bk="' + k + '" aria-pressed="' + bkClasses.has(k) + '" title="' + esc(long) + '"><i class="bk-key t-' + k + '"></i>' + esc(short) + '</button>').join('') +
        '</div><div class="legend"><small>' + esc(it.legend || '') + ' <span id="bknote"></span></small></div>';
      grp.appendChild(box);
      box.querySelectorAll('[data-bk]').forEach(b => b.addEventListener('click', () => tapBikeClass(b.dataset.bk)));
    }
    if (it.kind === 'parks'){   // amenities, any mix; none picked shows every park
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'pkbox'; box.hidden = !it.on;
      box.innerHTML = '<div class="chips pick" role="group" aria-label="' + esc(it.name) + '">' + Object.entries(it.amenities).map(([k, [short, long]]) =>
        '<button type="button" data-pk="' + k + '" aria-pressed="' + pkWant.has(k) + '" title="' + esc(long) + '">' + esc(short) + '</button>').join('') +
        '</div><div class="legend"><small>' + esc(it.legend || '') + ' <span id="pknote"></span></small></div>';
      grp.appendChild(box);
      box.querySelectorAll('[data-pk]').forEach(b => b.addEventListener('click', () => tapParkAmenity(b.dataset.pk)));
    }
    if (it.kind === 'spots' && it.classes){   // classes, any mix; the chips double as the key to the markers
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'spbox-' + it.id; box.hidden = !it.on;
      box.innerHTML = '<div class="chips pick" role="group" aria-label="' + esc(it.name) + '">' + Object.entries(it.classes).map(([k, [short, long]]) =>
        '<button type="button" data-sp="' + it.id + '" data-k="' + k + '" aria-pressed="true" title="' + esc(long) + '"><i class="sp ' + it.mark + ' c-' + k + ' z-1"></i>' + esc(short) + '</button>').join('') +
        '</div><div class="legend"><small>' + esc(it.legend || '') + ' <span id="spnote-' + it.id + '"></span></small></div>';
      grp.appendChild(box);
      box.querySelectorAll('[data-sp]').forEach(b => b.addEventListener('click', () => tapSpotClass(it.id, b.dataset.k)));
    }
    if (it.kind === 'towers'){   // key to the badges, shown while the layer is on
      const box = document.createElement('div'); box.className = 'lensbox child'; box.id = 'twkey-' + it.id; box.hidden = !it.on;
      const key = (cls, use, text) => '<div><span class="lm tw u-' + use + ' ' + cls + '"><i>' + svg(GLYPH['tw-' + use]) + '</i></span>' + esc(text) + '</div>';
      box.innerHTML = '<div class="legend twkey">' + key('', 'res', it.key.res) + key('', 'com', it.key.com) + key('', 'mix', it.key.mix) +
        key('uc', 'res', it.key.uc) + key('sup', 'com', it.key.sup) + '</div>';
      grp.appendChild(box);
    }
    if (it.kind === 'suburbs'){
      row.classList.add('outer-only'); row.id = 'row-' + it.id;
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'drvbox'; box.hidden = true;
      grp.appendChild(box);
    }
    if (PARTY[it.id]){   // "Colour by party", with a key to the colours while it's on
      const box = document.createElement('div'); box.className = 'lensbox'; box.id = 'ptybox-' + it.id; box.hidden = !it.on;
      const E = ELECT[it.id];   // an election layer's tick is the election view, with its note instead of a party key
      box.innerHTML = '<label class="sub"><input type="checkbox" id="pty-' + it.id + '"> ' + esc(E ? E.election.tick : PTY.label || 'Colour by party') + '</label>' +
        '<div class="legend" id="ptyleg-' + it.id + '" hidden>' + (E ? '<p class="el-also" id="elalso-' + it.id + '" hidden></p>' : '<div class="ptykey" id="ptykey-' + it.id + '"></div>') + '<small>' + esc(E ? E.election.note : it.party.note || PTY.note || '') + '</small></div>';
      grp.appendChild(box);
      box.querySelector('input').addEventListener('change', e => { partyTick(it.id, e.target.checked); logEvent('party', {id: e.target.checked ? it.id : 'none'}); });
    }
    if (it.sub){
      const s = document.createElement('label'); s.className = 'sub';
      s.innerHTML = '<input type="checkbox" id="' + it.sub.id + '"' + (it.sub.on ? ' checked' : '') + '> ' + it.sub.label;
      grp.appendChild(s);
      s.querySelector('input').addEventListener('change', () => { syncStnNames(); queueHash(); });
    }
    state[it.id] = !!it.on;
  });
  // Pages of the site that belong with this group (city.json "pageLinks": {group, id, name, note, href}), as rows
  // that open the page instead of a switch. They count as Basic, not Live, for the panel tabs.
  (CITY.pageLinks || []).filter(l => l.group === title).forEach(l => {
    const w = document.createElement('div'); w.className = 'it'; w.dataset.live = '';
    w.innerHTML = '<a class="row plink" href="' + esc(l.href) + '"><span class="sw k-plink" aria-hidden="true">' + PLINK_ICON + '</span>' +
      '<span class="tx"><b>' + esc(l.name) + '</b><span>' + esc(l.note || '') + '</span></span><span class="pgo" aria-hidden="true">→</span></a>';
    w.querySelector('a').addEventListener('click', () => logEvent('page_link', {id: l.id || l.href}));
    body.appendChild(w);
  });
  host.appendChild(grpOuter);
  if (foldedGroups.includes(title)) foldGroup(grpOuter, true, false);
});
groupCounts();
/* Panel tabs: All, Basic (data that rarely changes: census, boundaries, landmarks, routes) and Live
   (layers marked "live" in city.json, refreshed daily or weekly from city feeds). A tab only filters
   the list: layers that are on stay on. Shown only when the city has live layers. */
const PT = Object.assign({all: 'All', basic: 'Basic', live: 'Live',
  liveNote: 'Refreshed from city feeds every day or week. Dates show when each was last updated.'}, CITY.panelTabs || {});
let ptab = 'all';
function setPanelTab(t){
  ptab = t;
  document.querySelectorAll('[data-ptab]').forEach(b => b.setAttribute('aria-checked', String(b.dataset.ptab === t)));
  host.querySelectorAll('.it').forEach(el => { el.hidden = t === 'basic' ? !!el.dataset.live : t === 'live' ? !el.dataset.live : false; });
  host.querySelectorAll('.grp').forEach(g => { g.hidden = ![...g.querySelectorAll('.it')].some(el => !el.hidden); });
  const n = document.getElementById('ptabNote'); n.hidden = t !== 'live'; n.textContent = PT.liveNote;
}
if (LAYERS.some(it => it.live)){
  const box = document.getElementById('ptabs'); box.hidden = false;
  box.querySelector('.seg').innerHTML = ['all', 'basic', 'live'].map(t =>
    '<button type="button" role="radio" data-ptab="' + t + '" aria-checked="' + (t === 'all') + '">' + (t === 'live' ? '<i class="live-dot" aria-hidden="true"></i>' : '') + esc(PT[t]) + '</button>').join('');
  box.querySelectorAll('[data-ptab]').forEach(b => b.addEventListener('click', () => { setPanelTab(b.dataset.ptab); logEvent('panel_tab', {id: b.dataset.ptab}); }));
}
// A live layer's row says how fresh its data is ("as of Oct 14"); older than it.staleDays (default 3) shows in the accent colour.
function stampLive(it, asof){
  const row = document.getElementById('lyr-' + it.id), note = row && row.closest('label').querySelector('.tx span');
  if (!note || !asof) return;
  const days = (Date.now() - new Date(asof.slice(0, 10) + 'T12:00:00')) / 864e5;
  note.innerHTML = it.note + '<span class="asof' + (days > (it.staleDays || 3) ? ' old' : '') + '">' + esc(cap(fill(it.asofText || 'as of {date}', {date: niceDate(asof)}))) + '</span>';
}
function syncStnNames(){
  const L_ = METRO && layers[METRO.id]; if (!L_) return;
  const want = state[METRO.id] && document.getElementById(METRO.sub.id).checked;
  if (want && !map.hasLayer(L_._names)) L_._names.addTo(map);
  if (!want && map.hasLayer(L_._names)) map.removeLayer(L_._names);
}
function drawDriveLegend(){
  const el = document.getElementById('drvbox'); if (!el || !data.layers) return;
  const subs = (data.outer || {features: []}).features;
  const used = new Set(subs.filter(f => !f.properties.rest).map(f => (driveTier(f.properties.drive) || [])[0]));
  const rest = subs.some(f => f.properties.rest);
  el.innerHTML = '<div class="legend">' + DRIVE_TIERS.filter(t => used.has(t[0])).map(([k, label, v]) => '<div><i style="background:var(' + v + ')"></i>' + label + '</div>').join('') +
    (rest ? '<div><i class="rest"></i>Unincorporated land</div>' : '') +
    '<small>Typical drive to ' + esc(CITY.drive.hubName) + ' with no traffic: the median across each municipality, on empty roads at posted speeds. Most trips take longer; use it to compare places. Tap a spot for the time from there. Source: OpenStreetMap roads, routed with OSRM.</small></div>';
}
function drawLegend(){
  const el = document.getElementById('legend'); if (!el) return;
  const L_ = LENSES[lens];
  const picker = L_.pick ? '<div class="chips pick" role="radiogroup" aria-label="' + esc(L_.short) + '">' + L_.pick.map(([v, t]) =>
    '<button type="button" role="radio" data-pick="' + v + '" aria-checked="' + (pick[L_.id] === v) + '">' + esc(t) + '</button>').join('') + '</div>' : '';
  const hubs = L_.hubs && L_.hubs.length > 1 ? (CITY.lens.hubLabel ? '<small class="pc-lab">' + esc(CITY.lens.hubLabel) + '</small>' : '') +
    '<div class="chips pick" role="radiogroup" aria-label="' + esc(CITY.lens.hubLabel || L_.short) + '">' + L_.hubs.map(h =>
    '<button type="button" role="radio" data-hub="' + h.id + '" aria-checked="' + (L_.hub === h.id) + '">' + esc(h.name) + '</button>').join('') + '</div>' : '';
  el.innerHTML = picker + hubs + L_.tiers.map(([k, label, v]) => '<div><i style="background:var(' + v + ')"></i>' + label + '</div>').join('') +
    '<small>' + (L_.pick ? fill(L_.note, {type: pickLong(L_)}) : L_.note) + ' Source: ' + (L_.source || CITY.lens.source) + '</small>';
  el.querySelectorAll('[data-pick]').forEach(b => b.addEventListener('click', () => setPick(L_.id, b.dataset.pick)));
  el.querySelectorAll('[data-hub]').forEach(b => b.addEventListener('click', () => { setHub(b.dataset.hub); logEvent('lens_hub', {id: b.dataset.hub}); }));
}
function setBoard(id, b){
  const it = LAYERS.find(l => l.id === id); if (!it || !boardOf(it, b)) return;
  boardPick[id] = b;
  document.querySelectorAll('[data-layer="' + id + '"][data-board]').forEach(el => el.setAttribute('aria-checked', String(el.dataset.board === b)));
  const n = document.getElementById('brdnote-' + id); if (n) n.textContent = boardOf(it, b)[2] + '. ' + (it.boardNote || '');
  if (layers[id] && layers[id]._pick) layers[id]._pick(b);
  queueHash();
}
// Pick the transit lens's hub: its figures shade the map, the filter, the card's row and the share link.
function setHub(id, remember = true){
  if (!hubLens || !hubLens.hubs.some(h => h.id === id)) return;
  const h = useHub(hubLens, id);
  if (remember) try { if (id === hubLens.hubs[0].id) localStorage.removeItem(HUB_STORE); else localStorage.setItem(HUB_STORE, id); } catch (e) {}
  document.querySelectorAll('[data-lens="' + hubLens.id + '"]').forEach(b => { b.textContent = hubLens.short; });
  document.querySelectorAll('[data-flab="' + hubLens.id + '"]').forEach(b => { const f = FILTERS.find(x => x.lens === hubLens.id); b.textContent = h.filter || (f && f.label) || ''; });
  if (lens === hubLens.id) drawLegend();
  const LL = byKind('lens') && layers[byKind('lens').id];
  if (LL && LL._restyle) LL._restyle();
  if (filtOn()) applyFilter();
  try { if (lastInspect) redrawCard(); } catch (e){}
  queueHash();
}
function setPick(id, v){
  const L_ = LENSES[id]; if (!L_ || !L_.pick || !L_.pick.some(p => p[0] === v)) return;
  pick[id] = v;
  drawLegend();
  const LL = byKind('lens') && layers[byKind('lens').id];
  if (LL && LL._restyle) LL._restyle();
  queueHash();
}
function applyFilter(){
  document.querySelectorAll('[data-f]').forEach(b => {
    const k = b.dataset.f, v = b.dataset.v;
    b.setAttribute('aria-pressed', String(typeof filt[k] === 'number' ? filt[k] === +v : filt[k].has(v)));
  });
  const LL = byKind('lens') && layers[byKind('lens').id];
  if (LL && LL._restyle) LL._restyle();
  const on = filtOn(), res = document.getElementById('fres'), list = document.getElementById('flist');
  res.hidden = !on; list.innerHTML = '';
  if (!on || !data.profiles) return;
  const hits = data.units.features.filter(f => matches(data.profiles[String(f.properties.code)])).sort((a, b) => a.properties.name.localeCompare(b.properties.name));
  document.getElementById('fcount').textContent = hits.length ? hits.length + ' of ' + data.units.features.length + ' ' + CITY.units.plural + ' fit' : 'No ' + CITY.units.plural + ' fit all of that';
  hits.forEach(f => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = f.properties.name;
    b.addEventListener('click', () => {
      const lp = f.properties.lp, ll_ = L.latLng(lp[1], lp[0]);
      map.flyToBounds(L.geoJSON(f).getBounds(), {padding:[60, 60], maxZoom:14, duration:.8});
      if (matchMedia('(max-width:760px)').matches) panel.classList.add('collapsed');
      inspect(ll_, f.properties.name);
    });
    list.appendChild(b);
  });
}
function setLens(k){
  lens = k;
  document.querySelectorAll('[data-lens]').forEach(b => b.setAttribute('aria-checked', String(b.dataset.lens === k)));
  drawLegend();
  const LL = byKind('lens') && layers[byKind('lens').id];
  if (LL && LL._restyle) LL._restyle();
  queueHash();
}
const kindOf = id => (LAYERS.find(it => it.id === id) || {}).kind;
// Pick a group on a places layer (chips under its row): redraw its pins, the note and an open card.
function setPlacePick(id, g){
  const it = LAYERS.find(x => x.id === id); if (!it || !it.groups) return;
  placePick[id] = g === 'all' || !it.groups.some(x => x[0] === g) ? 'all' : g;
  if (layers[id] && layers[id]._draw) layers[id]._draw();
  drawPlacePick(id); queueHash();
  try { if (lastInspect) redrawCard(); } catch (e){}
}
// Categories on a multi-category places layer (chips under its row): any mix, all when none or every one is picked.
function setPlaceCats(id, want){
  const it = LAYERS.find(l => l.id === id); if (!it || !it.cats) return;
  const all = placeCats(it), w = all.filter(c => want.includes(c));
  catPick[id] = !w.length || w.length === all.length ? null : new Set(w);
  document.querySelectorAll('[data-pc="' + id + '"]').forEach(b => b.setAttribute('aria-pressed', String(it.narrow ? !!(catPick[id] && catPick[id].has(b.dataset.c)) : catOn(id, b.dataset.c))));
  if (layers[id] && layers[id]._draw) layers[id]._draw();
  drawPlacePick(id); queueHash();
  try { if (lastInspect) redrawCard(); } catch (e){}
}
function tapPlaceCat(id, c){
  const it = LAYERS.find(l => l.id === id), want = new Set(catPick[id] || (it.narrow ? [] : placeCats(it)));
  if (want.has(c) && (want.size > 1 || it.narrow)) want.delete(c); else want.add(c);
  setPlaceCats(id, [...want]);
}
function drawPlacePick(id){
  const it = LAYERS.find(x => x.id === id), box = document.getElementById('pg-' + id); if (!it || !box) return;
  if (it.groupsFor) box.hidden = !state[id] || !catOn(id, it.groupsFor);   // church families only while churches show
  const k = placePick[id] || 'all';
  box.querySelectorAll('[data-pg]').forEach(b => b.setAttribute('aria-checked', String(b.dataset.pg === k)));
  const n = layers[id] && layers[id]._count ? layers[id]._count() : null, note = document.getElementById('pgnote-' + id);
  if (note) note.textContent = (n != null && it.countText ? fill(it.countText, {n: n.toLocaleString(CITY.locale)}) + ' ' : '') + (k === 'all' ? it.allNote || '' : it.groupNote || '');
}
function setLayer(id, on){
  state[id] = on; queueHash(); groupCounts();
  const lyr = layers[id]; if (!lyr) return;
  if (on) { lyr.addTo(map); } else { map.removeLayer(lyr); }
  if (METRO && id === METRO.id) syncStnNames();
  if (kindOf(id) === 'towers'){ const box = document.getElementById('twkey-' + id); if (box) box.hidden = !on; }
  if (kindOf(id) === 'buses'){ document.getElementById('busbox').hidden = !on; drawBusBox(); }
  if (kindOf(id) === 'changes'){ const b = document.getElementById('chgbox'); if (b) b.hidden = !on; }
  if (kindOf(id) === 'bikes'){ const b = document.getElementById('bkbox'); if (b) b.hidden = !on; }
  if (kindOf(id) === 'parks'){ const b = document.getElementById('pkbox'); if (b) b.hidden = !on; }
  if (kindOf(id) === 'spots'){ const b = document.getElementById('spbox-' + id); if (b) b.hidden = !on; }
  { const b = document.getElementById('pc-' + id); if (b) b.hidden = !on; }
  { const b = document.getElementById('pg-' + id); if (b){ b.hidden = !on; drawPlacePick(id); } }
  if (kindOf(id) === 'buses' || kindOf(id) === 'streetcars' || kindOf(id) === 'regional') drawStops();
  if (kindOf(id) === 'boards'){ const box = document.getElementById('brd-' + id); if (box) box.hidden = !on; if (on) setBoard(id, boardPick[id]); }
  if (kindOf(id) === 'suburbs'){
    document.getElementById('drvbox').hidden = !on;
    if (on && scope === 'inner') map.removeLayer(lyr);   // shown only in the regional view
  }
  if (kindOf(id) === 'lens'){
    document.getElementById('lensbox').hidden = !on;
    drawLegend();
    // Coloured fills on top of each other turn to mud: the lens replaces the other area fills.
    if (on) LAYERS.filter(it => it.kind === 'fill').forEach(o => { const cb = document.getElementById('lyr-' + o.id); if (cb && cb.checked){ cb.checked = false; setLayer(o.id, false); } });
  }
  if (on && kindOf(id) === 'fill'){ const LN = byKind('lens'), cb = LN && document.getElementById('lyr-' + LN.id); if (cb && cb.checked){ cb.checked = false; setLayer(LN.id, false); } }
  if (PARTY[id]){ const b = document.getElementById('ptybox-' + id); if (b) b.hidden = !on; partyLayer(id, on); }
  // An area fill or the lens switched on after party colours: the most recent wins, so the colours go.
  if (on && shade && !partyBusy && (kindOf(id) === 'fill' || kindOf(id) === 'lens')){ partyPref[shade] = false; shade = null; partyDisplaced = []; partyShow(); }
  // A Nearby row that follows this layer appears or goes on the open card.
  const NB = CITY.card && CITY.card.nearby;
  if (NB && NB.nearest.some(r => r[2] === id)) try { if (lastInspect) redrawCard(); } catch (e){}   // not yet declared during start-up
}
function partyLayer(id, on){
  if (on){ partyPref[id] = true; partyStack = partyStack.filter(x => x !== id).concat(id); partyClaim(id); }
  else { partyStack = partyStack.filter(x => x !== id); if (shade === id) partySettle(); else partyShow(); }
}
// The "Colour by party" tick: on, this layer takes over; off, no layer is shaded until one is ticked or switched on again.
function partyTick(id, on){
  if (on){ partyLayer(id, true); queueHash(); return; }
  Object.keys(PARTY).forEach(x => { if (state[x]) partyPref[x] = false; });
  partySettle(); queueHash();
}
function partyClaim(id){
  if (!layers[id] || !layers[id]._party || !partyPref[id] || !state[id]) return partyShow();
  if (shade !== id){
    partyBusy = true;
    LAYERS.filter(it => it.kind === 'fill' || it.kind === 'lens').forEach(o => {
      const cb = document.getElementById('lyr-' + o.id);
      if (cb && cb.checked){ cb.checked = false; setLayer(o.id, false); if (!partyDisplaced.includes(o.id)) partyDisplaced.push(o.id); }
    });
    partyBusy = false;
  }
  shade = id; partyShow();
}
// After a shaded layer goes: the most recent other one still wanted takes over, else the fills it replaced come back.
function partySettle(){
  const next = partyStack.slice().reverse().find(x => state[x] && partyPref[x]);
  if (next){ shade = null; return partyClaim(next); }
  shade = null;
  if (partyDisplaced.length){
    const back = partyDisplaced; partyDisplaced = []; partyBusy = true;
    // Fills before the lens, as in links: the lens switches fills off, so whichever came last wins.
    back.sort((a, b) => (kindOf(a) === 'lens') - (kindOf(b) === 'lens')).forEach(x => { const cb = document.getElementById('lyr-' + x); if (cb && !cb.checked){ cb.checked = true; setLayer(x, true); } });
    partyBusy = false;
  }
  partyShow();
}
// A link or a view switched several layers at once: national over provincial or state over city, unless the link names one.
function partyFromLink(v){
  partyStack = Object.keys(PARTY).filter(x => state[x]).sort((a, b) => prank(a) - prank(b));
  partyStack.forEach(x => { partyPref[x] = v !== 'none'; });
  if (v && PARTY[v] && state[v]) partyStack = partyStack.filter(x => x !== v).concat(v);
  if (shade && !(state[shade] && partyPref[shade])) shade = null;
  partySettle();
}
function partyShow(){
  const ctr = map.getContainer();
  Object.keys(PTY_RANK).forEach(lv => ctr.classList.toggle('pty-' + lv, !!shade && PARTY[shade].level === lv));
  const wasElect = ctr.classList.contains('elect');
  ctr.classList.toggle('elect', electShading());
  // The card opens on Representatives while the election view is on, so redraw an open card when that changes.
  if (wasElect !== electShading()){ queueDeclutter(); try { if (lastInspect && !here.hidden) redrawCard(); } catch (e){} }
  Object.values(PARTY).forEach(it => {
    const g = layers[it.id], want = shade === it.id;
    if (g && g._party){ if (want && !g.hasLayer(g._party)) g.addLayer(g._party); if (!want && g.hasLayer(g._party)) g.removeLayer(g._party); }
    const cb = document.getElementById('pty-' + it.id); if (cb) cb.checked = want;
    const leg = document.getElementById('ptyleg-' + it.id); if (leg) leg.hidden = !want;
    if (want) partyKey(it);
    if (want && ELECT[it.id]) electAlso(it);
  });
}
// Election view: a race on the same ballot that the map can't draw (a citywide one, election.also), as one line.
function electAlso(it){
  const A = it.election.also, el = document.getElementById('elalso-' + it.id); if (!A || !el) return;
  const r = ((data.reps || {})[A.table] || {})[A.key];
  el.hidden = !r || !!r.winner;
  if (r) el.textContent = fill(A.text, {n: r.candidates.length, s: r.candidates.length === 1 ? '' : 's'});
}
// Key: each party on this layer with its number of seats, most seats first, vacant seats last.
function partyKey(it){
  const el = document.getElementById('ptykey-' + it.id), fc = data.layers && data.layers[it.id]; if (!el || !fc || ELECT[it.id]) return;
  const n = {};
  fc.features.forEach(f => { const [c, lab] = partyOf(it, f); if (c === 'nd') return; const k = c + '|' + lab; n[k] = (n[k] || 0) + 1; });
  el.innerHTML = Object.entries(n).sort((a, b) => (a[0].startsWith('vac|') - b[0].startsWith('vac|')) || b[1] - a[1])
    .map(([k, c]) => { const [cl, lab] = k.split('|'); return '<span><i class="p-' + cl + '"></i>' + esc(lab) + ' ' + c + '</span>'; }).join('');
}
// Reset: back to the starting view (city only, the default layers, the first lens with no filter).
document.getElementById('reset').addEventListener('click', () => {
  shade = null; partyStack = []; partyDisplaced = []; partyShow();
  LAYERS.forEach(it => {
    const cb = document.getElementById('lyr-' + it.id), want = !!it.on;
    if (cb.checked !== want){ cb.checked = want; setLayer(it.id, want); }
    if (it.sub){ const sb = document.getElementById(it.sub.id); if (sb.checked !== !!it.sub.on){ sb.checked = !!it.sub.on; syncStnNames(); } }
  });
  clearFilters(); applyFilter();
  Object.keys(pick).forEach(id => { pick[id] = LENSES[id].pick[0][0]; });
  BOARDS.forEach(it => setBoard(it.id, it.boards[0][0]));
  if (CHG){ Object.keys(CHG.stages).forEach(k => chgStages.add(k)); document.querySelectorAll('[data-chg]').forEach(b => b.setAttribute('aria-pressed', 'true')); if (layers[CHG.id] && layers[CHG.id]._draw) layers[CHG.id]._draw(); }
  if (BUSES) setBusFams(BUS_DEFAULT);
  if (BIKE) setBikeClasses(BIKE_DEFAULT);
  LAYERS.filter(it => it.cats).forEach(it => setPlaceCats(it.id, []));
  if (picked.size){ picked.clear(); drawPicks(); }
  if (placeF) setPlaceFocus(null, null, false);
  setLens(FIRST_LENS);
  setScope('inner', true);
  closeHere();
  clearPreset();
  // Back to a plain URL; the address bar follows again from the next change.
  clearTimeout(hashTimer); linkReady = false; lastHash = '';
  try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {}
  armLink();
});
document.getElementById('allOff').addEventListener('click', () => {
  Object.keys(state).forEach(id => { const cb = document.getElementById('lyr-' + id); if (cb.checked){ cb.checked = false; setLayer(id, false); } });
});
const panel = document.getElementById('panel');
document.getElementById('ph').addEventListener('click', () => { if (matchMedia('(max-width:760px)').matches) panel.classList.toggle('collapsed'); });
// The title's city switcher and the hub link: go there, and don't let the tap fold the phone panel.
const citySwitch = document.getElementById('citySwitch');
if (citySwitch){
  const here0 = citySwitch.value;
  citySwitch.addEventListener('change', () => { const to = citySwitch.value; citySwitch.value = here0; location.href = to; });
}
document.querySelectorAll('.ph .switch, .ph .hub-link').forEach(el => el.addEventListener('click', e => e.stopPropagation()));
if (matchMedia('(max-width:760px)').matches) panel.classList.add('collapsed');
// Desktop: fold the panel away for a full view of the map; remembered in this browser.
const unfold = document.getElementById('unfold');
function setFolded(on){
  panel.classList.toggle('folded', on); unfold.hidden = !on;
  try { if (on) localStorage.setItem('panelFolded', '1'); else localStorage.removeItem('panelFolded'); } catch (e) {}
  (on ? unfold : document.getElementById('fold')).focus({preventScroll: true});
}
document.getElementById('fold').addEventListener('click', e => { e.stopPropagation(); setFolded(true); });
unfold.addEventListener('click', () => setFolded(false));
try { if (localStorage.getItem('panelFolded') && wide()){ panel.classList.add('folded'); unfold.hidden = false; } } catch (e) {}

/* ---------- What's here ---------- */
const here = document.getElementById('here');
let pin = null;
var meRing = null;   // accuracy circle around the phone's location
const money = v => '$' + (v >= 1e6 ? (v / 1e6).toFixed(v % 1e6 ? 1 : 0) + 'M' : Math.round(v / 1e3) + 'K');
function livingHere(unit){
  const d = unit && data.profiles ? data.profiles[String(unit.properties.code)] : null;
  if (!d) return '';
  const T = CITY.card.living;
  // A city without a lens for a figure (Dallas has no getting-to-work lens) shows the figure without a tier.
  const tier = (key, v) => { if (!TIER_LABEL[key + ':' + v]) return ''; const [label, col] = TIER_LABEL[key + ':' + v]; return '<span class="tier"><i style="background:var(' + col + ')"></i>' + esc(label) + '</span>'; };
  const hub = CITY.lens.lenses.find(L_ => L_.minutes);
  return '<div class="live"><dl>' +
    '<dt>Housing</dt><dd>' + tier('cost', d.cost) + '<span>Median home ' + money(d.value) + ' · renters pay $' + d.rent.toLocaleString(CITY.locale) + '/mo</span><span class="caveat">' + esc(T.caveat) + '</span></dd>' +
    (hub && d[hub.minutes] != null ? '<dt>' + esc(hub.hubs ? hub.short : T.hub) + '</dt><dd>' + tier(hub.key, d[hub.key]) + '<span>' + esc(fill(T.hubText, {minutes: d[hub.minutes]})) + '</span></dd>' : '') +
    '<dt>Getting to work</dt><dd>' + tier('commute', d.commute) + '<span>' + d.carPct + '% drive · ' + d.transitPct + '% transit · ' + d.walkBikePct + '% walk or bike</span></dd>' +
    '<dt>Households</dt><dd>' + tier('tenure', d.tenure) + '<span>' + d.renterPct + '% rent</span></dd>' +
    (T.canopy && d.canopy != null ? '<dt>' + esc(T.canopy.label) + '</dt><dd>' + (TIER_LABEL['canopyBand:' + d.canopyBand] ? tier('canopyBand', d.canopyBand) : '') +
      '<span>' + esc(fill(T.canopy.text, {pct: d.canopy})) + '</span>' + (T.canopy.caveat ? '<span class="caveat">' + esc(T.canopy.caveat) + '</span>' : '') + '</dd>' : '') +
    mixRow(T.homes, d.homes, T.homes && T.homes.types.map(t => t[1])) +
    mixRow(T.built, d.built, T.built && T.built.bands) +
    langRow(T.lang, d) +
    mixRow(T.ages, d.ages, T.ages && T.ages.bands) +
    recentRow(T.recent, d) +
    '</dl><p>' + esc(fill(T.footer, {name: d.name})) + '</p></div>';
}
/* Description rows (no tiers, never ranked): how homes split by type or by when they were built, as a
   small stacked bar and the shares in words. Shares under 1% are left out of the words. */
function mixRow(cfg, shares, names){
  if (!cfg || !shares || !names) return '';
  const bar = shares.map((v, i) => v > 0 ? '<i style="width:' + v + '%;background:var(--mix-' + (i + 1) + ')"></i>' : '').join('');
  const words = shares.map((v, i) => [names[i], v, i]).filter(x => x[1] >= 1).map(x => '<b class="dot" style="background:var(--mix-' + (x[2] + 1) + ')"></b>' + esc(x[0]) + ' ' + x[1] + '%').join(' · ');
  return '<dt>' + esc(cfg.label) + '</dt><dd><span class="mix" aria-hidden="true">' + bar + '</span><span>' + words + '</span>' +
    (cfg.caveat ? '<span class="caveat">' + esc(cfg.caveat) + '</span>' : '') + '</dd>';
}
/* Recent immigrants: one share, in words, with the window it covers (each city's own: the 2021 Census
   counts arrivals 2016-2021, the ACS the foreign-born who entered 2010 or later). Card only, never ranked. */
function recentRow(cfg, d){
  if (!cfg || d.recent == null) return '';
  return '<dt>' + esc(cfg.label) + '</dt><dd>' + esc(fill(cfg.text, {pct: d.recent, since: d.recentSince || ''})) +
    (cfg.caveat ? '<span class="caveat">' + esc(cfg.caveat) + '</span>' : '') + '</dd>';
}
/* Home language: the top three, the first always shown and the next two only at 5% or more (the
   config's floor), so a 1% language never reads as a feature of the place. Card only: never a lens,
   a filter or a ranking. */
function langRow(cfg, d){
  if (!cfg || !d.lang || !d.lang.length) return '';
  const floor = cfg.floor == null ? 5 : cfg.floor;
  const top = d.lang.filter((x, i) => i === 0 || x[1] >= floor).slice(0, 3);
  const more = top.length < 2 ? '<span>' + esc(cfg.none || 'No other language above ' + floor + '%') + '</span>' : '';
  return '<dt>' + esc(cfg.label) + '</dt><dd>' + top.map(x => esc(x[0]) + ' ' + x[1] + '%').join(' · ') + more +
    (cfg.note ? '<span class="caveat">' + esc(fill(cfg.note, {multi: d.langMulti})) + '</span>' : '') + '</dd>';
}
// Collapsible card sections. Open/closed is remembered in this browser; phones start with all closed.
const SEC_DEFAULT = matchMedia('(max-width:760px)').matches ? {bounds:false, live:false, schools:false, transit:false, near:false, cls:false, chg:false, reps:false} : {bounds:true, live:true, schools:true, transit:true, near:true, cls:true, chg:true, reps:false};
let secOpen = Object.assign({}, SEC_DEFAULT);
try { Object.assign(secOpen, JSON.parse(localStorage.getItem('cardSections') || '{}')); } catch (e) {}
// While the election view is on, the card opens on Representatives alone; choices made then last only for this visit.
const secElect = {reps: true};
const secState = () => electShading() ? secElect : secOpen;
function section(id, title, body){
  if (!body) return '';
  return '<details class="sec" data-sec="' + id + '"' + (secState()[id] ? ' open' : '') + '><summary>' + title + '</summary>' + body + '</details>';
}
/* Skyscrapers on the card: a tower picked on the map, from search or a shared link (the pin carries its
   name) gets its own block: use, height, floors, year and up to three facts, built ahead of time by
   engine/skyscrapers.py. Heights in the city's unit first (CITY.distance "mi": feet). */
const TOWERS = byKind('towers');
const towerFeatures = () => (TOWERS && loaded[TOWERS.file] ? loaded[TOWERS.file].features : []);
const num = n => Number(n).toLocaleString(CITY.locale || 'en');
function towerHeight(p, short){
  const m = short ? num(Math.round(p.h)) + ' m' : num(p.h) + ' m', ft = num(p.ft) + ' ft';
  if (short) return CITY.distance === 'mi' ? ft : m;
  return CITY.distance === 'mi' ? ft + ' (' + m + ')' : m + ' (' + ft + ')';
}
// The tower a named pin is on: same name (or former name) within 150 m, or any tower within 20 m
// (a landmark inside one, like the Lyric Opera in the Civic Opera House; not the shops next door).
function towerAt(x, y, title){
  if (!title) return null;
  let best = null, bd = Infinity;
  towerFeatures().forEach(f => {
    const p = f.properties, d = metres([x, y], f.geometry.coordinates);
    const named = p.name === title || p.aka === title;
    if (d < (named ? 150 : 20) && d < bd){ best = f; bd = d; }
  });
  return best;
}
function towerCard(f){
  if (!f) return '';
  const p = f.properties, T = TOWERS;
  const stat = (k, v, sub) => '<div><dt>' + k + '</dt><dd>' + v + (sub ? '<small>' + sub + '</small>' : '') + '</dd></div>';
  const [hMain, hSub] = CITY.distance === 'mi' ? [num(p.ft) + ' ft', num(p.h) + ' m'] : [num(p.h) + ' m', num(p.ft) + ' ft'];
  return '<div class="tower"><div class="tw-what"><span class="lm tw u-' + p.use + (p.uc ? ' uc' : '') + (p.super ? ' sup' : '') + '"><i>' + svg(GLYPH['tw-' + p.use]) + '</i></span><span>' +
      esc((T.purpose && T.purpose[p.purpose]) || p.purpose) + (p.super ? ' · ' + esc(T.supText) : '') + (p.uc ? '<em>' + esc(T.ucText) + '</em>' : '') + '</span></div>' +
    '<dl class="tw-stats">' + stat('Height', hMain, hSub) + (p.floors ? stat('Floors', p.floors) : '') +
      (p.uc ? stat(T.expectedText, p.year || 'TBD') : stat(T.builtText, p.year)) + '</dl>' +
    (p.facts && p.facts.length ? '<ul class="tw-facts">' + p.facts.map(t => '<li>' + esc(t) + '</li>').join('') + '</ul>' : '') +
    '<small class="tw-src">' + (p.aka ? esc(fill(T.akaText, p)) + ' · ' : '') + (p.wiki ? '<a href="https://en.wikipedia.org/wiki/' + encodeURIComponent(p.wiki.replace(/ /g, '_')) + '" target="_blank" rel="noopener">' + esc(T.moreText) + '</a>' : esc(T.sourceText)) + '</small></div>';
}
/* Nearby (card only, nothing drawn on the map): the nearest of a few kinds of public place (library,
   community centre, emergency department; a place of worship or food shop while its layer is on)
   with the straight-line distance, and how many of others
   (parks, playgrounds…) are within the radius. Describe only: counts, never a score or a ranking. */
// Distances on the card, in the city's unit (CITY.distance: "km", the default, or "mi").
// km: "600 m" to the nearest 50 m under a kilometre, then "1.8 km". mi: "300 ft" to the nearest 50 ft
// under a tenth of a mile, then "0.4 mi", "1.2 mi" (whole miles from 10).
const MI = 1609.344, FT = 0.3048;
const dist = CITY.distance === 'mi'
  ? m => m < 0.095 * MI ? (Math.round(m / FT / 50) * 50 || 50) + ' ft' : (m / MI).toFixed(m < 9.95 * MI ? 1 : 0) + ' mi'
  : m => m < 950 ? (Math.round(m / 50) * 50 || 50) + ' m' : (m / 1000).toFixed(m < 9950 ? 1 : 0) + ' km';
function nearby(x, y){
  const N = CITY.card.nearby, G = data.nearby && data.nearby.groups; if (!N || !G) return '';
  // A row may name a layer as its third item ("layer", or "layer:category" on a multi-category layer):
  // it then shows only while that layer, and that category's chip, is on.
  const rows = N.nearest.map(([key, label, ref]) => {
    const [layer, cat] = (ref || '').split(':');
    if (layer && (!state[layer] || (cat && !catOn(layer, cat)))) return '';
    // A picked group on that layer narrows the row to it ("Church · Catholic"), from nearby.json's key:group points.
    const it = layer && LAYERS.find(x => x.id === layer), pg = it && it.groups && (!it.groupsFor || it.groupsFor === cat) && placePick[layer] && placePick[layer] !== 'all' ? it.groups.find(x => x[0] === placePick[layer]) : null;
    if (pg){ key = key + ':' + pg[0]; label = label + ' · ' + pg[1]; }
    const best = (G[key] || []).map(p => [p, metres([x, y], p)]).sort((a, b) => a[1] - b[1])[0];
    return best ? '<dt>' + esc(label) + '</dt><dd><span class="dir-row">' + esc(best[0][2]) + dirBtn(best[0][1], best[0][0], best[0][2]) + '</span><span>' + dist(best[1]) + ' away</span></dd>' : '';
  }).join('');
  const counts = N.counts.map(([key, one, many]) => {
    const n = (G[key] || []).filter(p => metres([x, y], p) <= N.radius).length;
    return n + ' ' + (n === 1 ? one : many);
  });
  return '<div class="live"><dl>' + rows + '<dt>' + esc(N.within) + '</dt><dd>' + esc(counts.join(' · ')) + '</dd></dl><p>' + esc(N.note) + '</p></div>';
}
/* Schools (card only, nothing drawn on the map): the school whose attendance area holds the spot, for
   each level the city config lists (e.g. elementary, middle, high), with its grades and the straight-line
   distance to the building. One file, each area tagged with its level. Describe only: no ratings or scores.
   The file is large, so it loads after the map; the open card is redrawn when it arrives. */
function schools(x, y){
  const S = CITY.card.schools, D = data.schools; if (!S || !D) return '';
  const rows = S.levels.map(([lv, label]) => {
    const f = D.features.find(f => f.properties.level === lv && contains(f.geometry, x, y)); if (!f) return '';
    const p = f.properties, at = p.x != null ? [p.x, p.y] : null;
    const name = p.url ? '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">' + esc(p.name) + '</a>' : esc(p.name);
    return '<dt>' + esc(label) + '</dt><dd>' + name + '<span>' + esc(fill(at ? S.sub : S.subNoDist, {grades: p.grades, dist: at ? dist(metres([x, y], at)) : ''})) + '</span>' + (p.note ? '<span>' + esc(p.note) + '</span>' : '') + '</dd>';
  }).join('');
  return rows ? '<div class="live reps"><dl>' + rows + '</dl><p>' + esc(fill(S.note, {year: D.year || ''})) + '</p></div>' : '';
}
// Who represents this spot. Names link to their official pages.
function representatives(hits){
  // Skip the section outside the city: the first office drawn on a layer (a citywide office such as a mayor has none) has no hit.
  const R = data.reps, cfg = CITY.card.reps, first = cfg && cfg.offices.find(o => o.layer); if (!R || !cfg || !first || !hits[first.layer]) return '';
  const link = r => r && r.name ? '<a href="' + esc(r.url) + '" target="_blank" rel="noopener">' + esc(r.name) + '</a>' : '<span class="vacant">Seat currently vacant</span>';
  const row = (role, r, sub) => '<dt>' + role + '</dt><dd>' + link(r) + (sub ? '<span>' + esc(sub) + '</span>' : '') + '</dd>';
  const date = new Date(...R.updated.split('-').map((v, i) => +v - (i === 1))).toLocaleDateString(CITY.locale, {month:'long', day:'numeric', year:'numeric'});
  const raceOn = o => o.race && R[o.race.table] && (cfg.trustees || cfg.ballot);
  // Ballot-only rows (statewide races) come last, after the trustees.
  const offices = cfg.offices.filter(o => !o.ballot), after = cfg.offices.filter(o => o.ballot);
  const one = o => {
      // A ballot-only row (o.ballot {table, key}: a statewide race such as U.S. Senate): no member, just the race,
      // shown only while the race is (see raceRow).
      if (o.ballot){ const race = (R[o.ballot.table] || {})[o.ballot.key]; return race ? raceRow(Object.assign({race: o.ballot}, o), null, race, o.sub || '', link, o.ballot.key) : ''; }
      // A citywide office (o.citywide: the record's key, e.g. a mayor) is the same everywhere in the city.
      if (o.citywide){
        const r = (R[o.table] || {})[o.citywide]; if (!r) return '';
        if (raceOn(o)) return raceRow(o, r, R[o.race.table][o.citywide], o.sub || '', link, o.citywide);
        return row(o.role, r, o.sub || '');
      }
      const h = hits[o.file ? 'file:' + o.file : o.layer]; if (!h) return '';
      const r = R[o.table][String(h.properties[o.key])], sub = fill(o.sub, {f: h.properties, r: r || {}});
      if (raceOn(o)){
        // The race can be keyed by another layer than the member (o.race.layer: Dallas's members sit for the old
        // congressional lines, but November's race is on the new ones the map draws).
        const rh = o.race.layer ? hits[o.race.layer] : h, k = rh && String(rh.properties[o.race.key || o.key]);
        return raceRow(o, r, rh ? R[o.race.table][k] : null, sub, link, k);
      }
      return row(o.role, r, sub);
  };
  return '<div class="live reps"><dl>' + offices.map(one).join('') + trustees(hits) + after.map(one).join('') +
    '</dl><p>' + esc(fill(cfg.note, {date})) + (cfg.trustees && R[cfg.trustees.table] ? ' ' + esc(cfg.trustees.note) : '') +
    (cfg.ballot && cfg.ballot.note && new Date() < ballotEnd(cfg.ballot) ? ' ' + esc(cfg.ballot.note) : '') + '</p></div>';
}
/* School board trustees: one row per board that covers the spot, plus an optional citywide seat
   (T.citywide, e.g. a board president). Before the election the row lists the candidates; while votes
   are counted it can name who leads (r.leader); once there is a winner (or one candidate was
   acclaimed), the winner, marked as taking office on the start date; from that date, just the trustee.
   Dates and wording come from city.json. */
// Candidate names under a caret: a short list runs on with dots; a long one (a mayoral race) is a grid, a name per cell.
const candList = names => names.length > 8 ? '<span class="cand-grid">' + names.map(n => '<i>' + esc(n) + '</i>').join('') + '</span>' : '<span>' + names.map(esc).join(' · ') + '</span>';
const isoDate = s => new Date(...s.split('-').map((v, i) => +v - (i === 1)));
const longDate = s => isoDate(s).toLocaleDateString(CITY.locale, {month:'short', day:'numeric'});
function trusteeRow(T, role, r, sub){
  const today = new Date(), started = today >= isoDate(T.starts);
  const dates = {election: longDate(T.election), starts: longDate(T.starts)};
  let dd;
  if (!r) dd = '<span>' + esc(sub) + '</span>';
  else if (r.winner) dd = '<b>' + esc(r.winner) + '</b><span>' + esc(sub + (started ? '' : ' · ' + fill(r.acclaimed ? T.acclaimed : T.elected, dates))) + '</span>';
  else if (r.leader && T.leading) dd = '<b>' + esc(r.leader) + '</b><span>' + esc(sub + ' · ' + fill(T.leading, dates)) + '</span>';
  else {
    const n = r.candidates.length;
    const head = fill(today >= isoDate(T.election) ? T.counting : T.race, Object.assign({n, s: n === 1 ? '' : 's'}, dates));
    dd = '<details class="cands"><summary>' + esc(head) + '</summary>' + candList(r.candidates) + '</details><span>' + esc(sub) + '</span>';
  }
  return '<dt>' + esc(role) + '</dt><dd>' + dd + '</dd>';
}
/* An office with a race on (o.race, e.g. city council): the sitting member as usual, then where they stand, then the
   candidates under an expandable caret, as for trustees. Wording and dates: card.reps.ballot if the city has one
   (a partisan election with no results feed), else the trustees'. With "through" (ballot), the race shows until the
   end of that day and the row then goes back to just the member; otherwise until the start date, with the winner
   once there is one.
   Where the member stands comes from the member's own record (r.runs {office, district | race}, a partisan ballot:
   engine/ballot.py) or from the race's (race.incumbentRunning / incumbentElsewhere, Toronto's council). */
const ballotEnd = B => new Date(isoDate(B.through).getTime() + 864e5);
function raceRow(o, r, race, sub, link, key){
  const B = CITY.card.reps.ballot, T = Object.assign({}, CITY.card.reps.trustees || {}, B || {}, o.race.text || {}), today = new Date();
  const ended = T.through ? today >= ballotEnd(T) : today >= isoDate(T.starts);
  const who = o.ballot ? '' : link(r);
  if (!race || ended) return o.ballot ? '' : '<dt>' + esc(o.role) + '</dt><dd>' + who + '<span>' + esc(sub) + '</span></dd>';
  if (race.notUp) return '<dt>' + esc(o.role) + '</dt><dd>' + who + '<span>' + esc([sub, T.notUp].filter(Boolean).join(' · ')) + '</span></dd>';
  const dates = {election: longDate(T.election), starts: T.starts ? longDate(T.starts) : '', district: key};
  const E2 = Object.assign({}, T.elsewhere || {}, o.race.elsewhere || {}), txt = k => o.race[k] || T[k];
  let stand = '';
  if (r && r.name && r.runs !== undefined){
    const ru = r.runs;
    stand = !ru ? txt('retiring') : ru.office === o.race.kind && ru.district === key ? txt('again')
      : E2[ru.office] ? fill(E2[ru.office], Object.assign({race: (T.races || {})[ru.race] || ru.race}, ru)) : '';
  } else if (r && !o.ballot){
    const ew = race.incumbentElsewhere;
    stand = race.incumbentRunning ? txt('again') : race.incumbentRunning === false ? (ew && E2[ew.office] ? fill(E2[ew.office], ew) : txt('retiring')) : '';
  }
  const s = [sub, stand].filter(Boolean).join(' · ');
  // A partisan ballot names each candidate's party, shortened (T.party: {"Democratic": "D"}), in ballot order.
  const names = race.parties ? race.candidates.map((n, i) => n + ' (' + ((T.party || {})[race.parties[i]] || race.parties[i]) + ')') : race.candidates;
  let more;
  if (race.winner) more = '<span class="won"><b>' + esc(race.winner) + '</b> ' + esc(fill(race.acclaimed ? T.acclaimed : T.elected, dates)) + '</span>';
  else if (names.length === 1 && T.one) more = '<span class="one">' + esc(fill(T.one, Object.assign({name: names[0]}, dates))) + '</span>';
  else {
    const n = names.length;
    more = '<details class="cands"><summary>' + esc(fill(!T.through && today >= isoDate(T.election) ? T.counting : T.race, Object.assign({n, s: n === 1 ? '' : 's'}, dates))) + '</summary>' + candList(names) + '</details>';
  }
  return '<dt>' + esc(o.role) + '</dt><dd>' + who + (s ? '<span>' + esc(s) + '</span>' : '') + more + '</dd>';
}
function trustees(hits){
  const T = CITY.card.reps.trustees, R = data.reps; if (!T || !R || !R[T.table]) return '';
  const it = LAYERS.find(l => l.id === T.layer), bh = hits[T.layer]; if (!it || !bh) return '';
  const rows = it.boards.filter(([b]) => bh[b]).map(([b]) => {
    const ctx = boardCtx(it, bh[b]);
    return trusteeRow(T, fill(T.role, ctx), (R[T.table][b] || {})[String(ctx.num)], fill(T.ward, ctx));
  });
  const C = T.citywide, cb = C && (R[T.table][C.board] || {})[C.key];
  if (cb && rows.length) rows.push(trusteeRow(T, C.role, cb, C.sub));
  return rows.join('');
}
let pinName = '';
// pinIsMe: the pin is the phone's own location (drawn blue, never written into links).
let pinIsMe = false, meNext = false;
function placePin(latlng, name){
  pinName = name || ''; pinIsMe = meNext; meNext = false; queueHash();
  if (pin) pin.setLatLng(latlng); else pin = L.marker(latlng, {pane:'pin', interactive:false, keyboard:false, icon: L.divIcon({className:'', iconSize:[20, 20], iconAnchor:[10, 10], html:'<span class="pin"></span>'})}).addTo(map);
  const dot = pin.getElement() && pin.getElement().querySelector('.pin');
  if (dot) dot.classList.toggle('me', pinIsMe);
  if (!pinIsMe && meRing){ map.removeLayer(meRing); meRing = null; }
}
const colorOf = (id, f) => { const it = LAYERS.find(l => l.id === id); return 'var(' + ((it && it.colors && it.colors[f.properties.name]) || '--ink-3') + ')'; };
// Outside the city: the nearest named community (a town, village or larger community, not a small
// neighbourhood), if one is close, as a "Near ..." pill. Skipped when the card is already titled with it.
function nearCommunity(x, y, title){
  if (!data.regionPlaces) return '';
  const big = CITY.regionPlaces.near || [];
  const c = data.regionPlaces.filter(p => big.includes(p.kind)).map(p => [p, metres([x, y], p.at)]).filter(a => a[1] < 2500).sort((a, b) => a[1] - b[1])[0];
  if (!c || c[0].name === title) return '';
  return '<span class="pill"><i style="background:var(--cult-enclave)"></i>Near ' + esc(c[0].name) + '</span>';
}
let lastInspect = null;
/* A spot's card, built once into parts so it can be shown alone or beside another spot (Compare).
   null: the spot is beyond the region. Builds HTML only; placing pins is the renderer's job. */
function cardOf(latlng, title, muniName){
  const x = latlng.lng, y = latlng.lat;
  if (!hit(data.footprint, x, y)){
    // A named community already knows its municipality: the map's shapes are trimmed to a coarse
    // shoreline, so a lakeside place can otherwise land just outside them.
    const muni = hit(data.outer, x, y) || (muniName && data.outer.features.find(f => f.properties.name === muniName));
    if (!muni) return null;
    const m = muni.properties, rp = fill(CITY.outside.regionPill, m);
    // Districts drawn beyond the city (card.outsideFacts: layer ids; Dallas's state and congressional districts
    // cover its nine counties) add their card rows and pills here too.
    const OF = CITY.card.outsideFacts || [], oh = {};
    OF.forEach(id => { oh[id] = hit(data.layers[id], x, y); });
    const orows = CITY.card.facts.filter(r => r.layer && oh[r.layer]).map(r => '<dt>' + esc(r.label) + '</dt><dd>' + esc(fill(r.text, oh[r.layer].properties)) + '</dd>').join('');
    const opills = CITY.card.pills.filter(p => p.text && oh[p.layer]).map(p => '<span class="pill"><i style="background:var(' + p.color + ')"></i>' + esc(fill(p.text, oh[p.layer].properties)) + '</span>').join('');
    // CITY.outside.muniLabel: what the areas beyond the city are called on the card (Hyderabad's are mandals).
    const bounds = '<dl class="facts"><dt>' + esc(CITY.outside.muniLabel || 'Municipality') + '</dt><dd>' + esc(m.name) + '</dd><dt>' + esc((CITY.focus && CITY.focus.noun) || 'Region') + '</dt><dd>' + esc(rp) + '</dd>' + orows + '</dl>';
    return {outside: true, x, y, m, heading: title || m.name, boundsSection: OF.length ? bounds : '',
      pills: nearCommunity(x, y, title) + '<span class="pill"><i style="background:var(--land-out-line)"></i>' + esc(m.name) + '</span><span class="pill"><i style="background:var(--muni-label)"></i>' + esc(rp) + '</span>' + opills,
      drive: driveHere(x, y, m),
      // For Compare: the same facts as rows, so they line up with a spot inside the city.
      sections: [['bounds', 'Boundaries', bounds],
                 ['live', 'Living here', driveHere(x, y, m)]]};
  }
  const hits = {};
  LAYERS.filter(it => AREA_KINDS.includes(it.kind)).forEach(it => { hits[it.id] = hit(data.layers[it.id], x, y); });
  BOARDS.forEach(it => { hits[it.id] = boardHits(it, x, y); });
  // Offices whose seats follow lines the map doesn't draw (e.g. the districts sitting members were elected on, before a
  // redistricting takes effect): office.file names a polygon file loaded for the card only.
  REP_FILES.forEach(f => { hits['file:' + f] = hit(data.repAreas[f], x, y); });
  const pillCfg = CITY.card.pills.find(p => p.knownas);
  const near = (data.knownas ? data.knownas.features : []).map(f => [f, metres([x, y], f.geometry.coordinates)]).filter(a => a[1] < 650).sort((a, b) => a[1] - b[1]).slice(0, pillCfg ? pillCfg.knownas : 2);
  const pills = [];
  CITY.card.pills.forEach(p => {
    if (p.knownas) { near.forEach(([f]) => pills.push(['var(--cult-enclave)', f.properties.name])); return; }
    const h = hits[p.layer];
    if (p.else) { if (h) pills.push([colorOf(p.layer, h), h.properties.name]); else if (hits[p.else]) pills.push([colorOf(p.else, hits[p.else]), hits[p.else].properties.name]); return; }
    if (h) pills.push(['var(' + p.color + ')', fill(p.text, h.properties)]);
  });
  const facts = CITY.card.facts.filter(r => !r.onlyInside || hits[r.layer]).map(r => {
    if (r.address) return addressRow(x, y, hits);
    if (r.pickup) return pickupRow(x, y);
    if (r.sweep) return sweepRow(x, y);
    if (r.heritageBuilding) return heritageRow(r, x, y, title);
    if (r.knownas) return [r.label, near.length ? near.map(a => a[0].properties.name).join(', ') : '—'];
    if (r.boards){ const it = LAYERS.find(l => l.id === r.boards), bh = hits[r.boards] || {};
      const t = it.boards.filter(([b]) => bh[b]).map(([b]) => fill(r.text, boardCtx(it, bh[b]))).join(' · ');
      return [r.label, t || r.empty || '—']; }
    const h = hits[r.layer];
    // cover: a second line with how much of the spot's unit (neighbourhood) the layer covers, from the profile
    // field r.cover.field (a percentage), e.g. "62% of Roncesvalles is inside permit areas".
    const cov = r.cover && coverLine(r.cover, hits);
    const withCov = t => cov ? [r.label, esc(t) + '<span class="ag-sub">' + esc(cov) + '</span>', true] : [r.label, t];
    if (h){ const t = fill(r.text, h.properties); return t || !r.skipEmpty ? withCov(t) : null; }   // skipEmpty: no row when the text fills to nothing
    if (r.emptyWithin && Object.entries(r.emptyWithin).some(([id, name]) => hits[id] && hits[id].properties.name === name)) return [r.label, '—'];
    return withCov(r.empty || '—');
  });
  // Title: a searched place keeps its own name; a dropped pin is named by its neighbourhood (or, failing
  // that, the big area it's in). Coordinates are a last resort, for a spot no layer covers.
  const unit = UNITS && hits[UNITS.id];
  const area = LAYERS.filter(it => it.kind === 'fill').map(it => hits[it.id]).find(Boolean);
  const coords = Math.abs(y).toFixed(4) + '° ' + (y >= 0 ? 'N' : 'S') + ', ' + Math.abs(x).toFixed(4) + '° ' + (x < 0 ? 'W' : 'E');
  const heading = title || (unit && unit.properties.name) || (area && area.properties.name) || coords;
  return {outside: false, x, y, hits, heading,
    pills: pills.map(p => '<span class="pill"><i style="background:' + p[0] + '"></i>' + esc(p[1]) + '</span>').join(''),
    focus: focusChips(hits), tower: towerCard(towerAt(x, y, title)), standout: standout(unit, heading),
    sections: [['bounds', 'Boundaries', '<dl class="facts">' + facts.filter(Boolean).map(f => '<dt>' + f[0] + '</dt><dd>' + (f[2] ? f[1] : esc(f[1])) + '</dd>').join('') + '</dl>'],
               ['live', 'Living here', livingHere(unit)],
               ['schools', (CITY.card.schools && CITY.card.schools.title) || 'Schools', schools(x, y)],
               ['transit', (TR && TR.title) || 'Transit', transitHere(x, y)],
               ['near', 'Nearby', nearby(x, y)],
               ['cls', (CLC && CLC.title) || 'Road closures', closuresHere(x, y)],
               ['chg', (CC && CC.title) || 'Changing nearby', changesHere(x, y)],
               ['reps', 'Representatives', representatives(hits)]]};
}
function coverLine(C, hits){
  const u = UNITS && hits[UNITS.id], d = u && data.profiles ? data.profiles[String(u.properties.code)] : null;
  if (!d || d[C.field] == null) return '';
  return fill(d[C.field] ? C.text : (C.none || C.text), {pct: d[C.field], name: u.properties.name});
}
/* The card's pickup row (card.pickup in city.json; a Boundaries row placed by {"label", "pickup": true} in
   card.facts): a city service that comes on set dates to set areas, such as curbside collection or street
   sweeping. The file (kind "pickup") has one feature per area with key `k`, and `sched` {k: [[date, [item…]]]}.
   Shows the area's usual weekday ({day}) or its own fields in `head`, then the next `show` dates from today
   in the city's time zone with what goes out (labels from `items`). `group` joins dates a few days apart into
   one visit ("Oct 27 and 28"). Outside every area: `outside` (or no row); past the last date: `after` (or no
   row). [label, html, true], or null. */
const PU = CITY.card.pickup || null;
/* ---------- Street sweeping (card.sweep) ----------
   The nearest block's schedule, both sides of the street, from squares of about 450 m (docs/<city>/data/<dir>/<i>_<j>.json,
   cities/sf/sweeping.py) fetched when the card first needs one. Each block side: [street, limits, side,
   [[weekday 0-6 from Monday, from hour, to hour, weeks of the month as bits (1 = 1st week)], ...], [lon, lat, ...]]. */
const SW = CITY.card.sweep || null, swTiles = new Map();
const SWD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], SWO = ['1st', '2nd', '3rd', '4th', '5th'];
function swHour(h){ h = ((h % 24) + 24) % 24; return h === 0 ? 'midnight' : h === 12 ? 'noon' : (h % 12) + (h < 12 ? ' am' : ' pm'); }
function swHours(a, b){   // "2–6 am", "10 am–noon", "11 pm–1 am"
  const A = swHour(a), B = swHour(b), same = a % 24 < 12 === b % 24 < 12 && ![0, 12].includes(a % 24) && ![0, 12].includes(b % 24);
  return same ? A.replace(/ [ap]m$/, '') + '–' + B : A + '–' + B;
}
function swWeeks(m){ if (m === 31) return 'every week'; const w = SWO.filter((_, i) => m & (1 << i)); return w.join(' & ').replace(/ & (?=.* & )/g, ', ') + ' week' + (w.length > 1 ? 's' : ''); }
function swNext(sch, tz){   // the next sweep of a side: [date "YYYY-MM-DD", entry], today included while it's still on
  let now; try { now = new Date(new Date().toLocaleString('en-US', {timeZone: tz})); } catch (e) { now = new Date(); }
  for (let k = 0; k < 40; k++){
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + k), wd = (d.getDay() + 6) % 7, wk = Math.ceil(d.getDate() / 7);
    const e = sch.filter(e => e[0] === wd && e[3] & (1 << (wk - 1)) && (k || now.getHours() < e[2])).sort((a, b) => a[1] - b[1])[0];
    if (e) return [k, d, e];
  }
  return null;
}
function swDist(x, y, flat){   // metres from a spot to a block side's line
  const kx = Math.cos(y * Math.PI / 180) * 111320, ky = 110574;
  let best = Infinity;
  for (let i = 0; i + 3 < flat.length; i += 2){
    const ax = (flat[i] - x) * kx, ay = (flat[i + 1] - y) * ky, bx = (flat[i + 2] - x) * kx, by = (flat[i + 3] - y) * ky;
    const dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy, t = L ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / L)) : 0;
    best = Math.min(best, Math.hypot(ax + t * dx, ay + t * dy));
  }
  return best;
}
function sweepRow(x, y){
  if (!SW) return null;
  const key = Math.floor(x / SW.cell) + '_' + Math.floor(y / SW.cell);
  if (!swTiles.has(key)){
    swTiles.set(key, null);
    get(SW.dir + '/' + key + '.json').then(d => { swTiles.set(key, d); redrawCard(); }).catch(() => swTiles.set(key, {s: [], l: [], f: []}));
    return null;
  }
  const T = swTiles.get(key); if (!T) return null;
  const near = T.f.map(f => [f, swDist(x, y, f[4])]).filter(a => a[1] <= (SW.within || 30)).sort((a, b) => a[1] - b[1]);
  if (!near.length) return null;
  const f0 = near[0][0], block = T.f.filter(f => f[0] === f0[0] && f[1] === f0[1]);
  const sides = [f0, ...block.filter(f => f !== f0 && f[2] !== f0[2])];
  const line = f => {
    // Days with the same hours and weeks said together: "Mon & Thu 9–11 am, every week"
    const g = new Map(); f[3].forEach(e => { const k = e[1] + '-' + e[2] + '-' + e[3]; if (!g.has(k)) g.set(k, [e, []]); g.get(k)[1].push(SWD[e[0]]); });
    const days = ds => { const ix = ds.map(d => SWD.indexOf(d)).sort((a, b) => a - b), run = ix.every((v, i) => !i || v === ix[i - 1] + 1);
      return ix.length === 7 ? 'Every day' : ix.join() === '0,1,2,3,4' ? 'Weekdays' : run && ix.length > 2 ? SWD[ix[0]] + '–' + SWD[ix[ix.length - 1]] : ix.map(i => SWD[i]).join(', ').replace(/, ([^,]*)$/, ' & $1'); };
    const when = [...g.values()].map(([e, ds]) => days(ds) + ' ' + swHours(e[1], e[2]) + (e[3] === 31 ? '' : ', ' + swWeeks(e[3]))).join('; ');
    const n = swNext(f[3], SW.tz), next = n ? (n[0] === 0 ? 'today' : n[0] === 1 ? 'tomorrow' : n[1].toLocaleDateString(CITY.locale, {weekday: 'short', month: 'short', day: 'numeric'})) : '';
    return '<span class="ag-sub"><b>' + esc(f[2]) + '</b> ' + esc(when) + (next ? ' · next ' + esc(next) : '') + '</span>';
  };
  return [SW.label, esc(T.s[f0[0]]) + (T.l[f0[1]] ? ' <span class="ag-sub" style="display:inline">(' + esc(T.l[f0[1]]) + ')</span>' : '') + sides.map(line).join('') +
    (SW.note ? '<span class="ag-sub">' + esc(SW.note) + '</span>' : ''), true];
}
function pickupRow(x, y){
  const D = data.pickup; if (!PU || !D) return null;
  const f = D.features.find(f => contains(f.geometry, x, y));
  if (!f) return PU.outside ? [PU.label, '<span class="ag-sub">' + esc(PU.outside) + '</span>', true] : null;
  const all = (D.sched[f.properties.k] || []);
  const today = cityToday(PU.tz), dt = s => new Date(s + 'T12:00:00');
  const left = all.filter(e => e[0] >= today);
  if (!left.length) return PU.after ? [PU.label, '<span class="ag-sub">' + esc(fill(PU.after, {year: D.year})) + '</span>', true] : null;
  // Visits: single dates, or with `group` dates within 4 days of each other joined.
  const visits = [];
  left.forEach(e => { const v = visits[visits.length - 1];
    if (PU.group && v && (dt(e[0]) - dt(v.dates[v.dates.length - 1])) / 864e5 <= 4){ v.dates.push(e[0]); e[1].forEach(i => v.items.includes(i) || v.items.push(i)); }
    else visits.push({dates: [e[0]], items: e[1].slice()}); });
  const wd = d => dt(d).toLocaleDateString(CITY.locale, {weekday: 'long'});
  const days = {}; all.forEach(e => { const w = wd(e[0]); days[w] = (days[w] || 0) + 1; });
  const day = Object.entries(days).sort((a, b) => b[1] - a[1])[0][0];
  const tomorrow = new Date(dt(today).getTime() + 864e5).toISOString().slice(0, 10);
  const when = v => {
    const one = d => d === today ? (PU.todayText || 'Today') : d === tomorrow ? (PU.tomorrowText || 'Tomorrow') : dt(d).toLocaleDateString(CITY.locale, {weekday: 'short', month: 'short', day: 'numeric'});
    if (v.dates.length === 1) return one(v.dates[0]);
    const m = dt(v.dates[0]).getMonth() === dt(v.dates[v.dates.length - 1]).getMonth();
    return dt(v.dates[0]).toLocaleDateString(CITY.locale, {month: 'short', day: 'numeric'}) + ' and ' +
      (m ? dt(v.dates[v.dates.length - 1]).getDate() : dt(v.dates[v.dates.length - 1]).toLocaleDateString(CITY.locale, {month: 'short', day: 'numeric'}));
  };
  const items = v => cap(v.items.map(i => (PU.items || {})[i] || i).join(', '));
  const lines = visits.slice(0, PU.show || 2).map(v => '<span class="ag-sub">' + esc(fill(PU.next || '{when}: {items}', {when: when(v), items: items(v)})) + '</span>').join('');
  const head = fill(PU.head || '{day}', Object.assign({day}, f.properties));
  return [PU.label, esc(head) + lines + (PU.note ? '<span class="ag-sub pu-note">' + esc(fill(PU.note, {year: D.year})) + '</span>' : ''), true];
}
/* The card's address row (card.address in city.json; data from the addresses layer's file). A grid city:
   the spot's address numbers, read off the mile lines ("About 2400 N · 1200 W"). A divided city: which
   side of the dividing street the spot is on, with a nearby street that carries that side's E or W.
   [label, html, true] (html), or null when there's nothing to say. */
const ADDR = byKind('addresses');
function addressRow(x, y, hits){
  const A = CITY.card.address, D = ADDR && loaded[ADDR.file];
  if (!A || !D) return null;
  // A dividing street that only holds in part of the city (card.address.within: New York's Fifth Avenue, Manhattan
  // only): elsewhere the row gives that area's own text (within.elsewhere[name]) or nothing.
  const W = A.within;
  if (W){
    const h = hits && hits[W.layer], nm = h ? h.properties.name : null;
    if (nm !== W.name){ const t = nm && (W.elsewhere || {})[nm]; return t ? [A.label, esc(t), true] : null; }
  }
  if (D.kind === 'grid'){
    // Piecewise-linear between the mile lines; past the last one, the last stretch's pace carries on.
    const at = (pts, v) => {
      let i = 1; while (i < pts.length - 1 && pts[i][0] < v) i++;
      const [a, b] = [pts[i - 1], pts[i]];
      return a[1] + (b[1] - a[1]) * (v - a[0]) / ((b[0] - a[0]) || 1);
    };
    const word = (n, pos, neg) => { const r = Math.round(n / 100) * 100; return r === 0 ? '0' : Math.abs(r) + ' ' + (r > 0 ? pos : neg); };
    const ns = word(at(D.axes.ns, y), 'N', 'S'), ew = word(at(D.axes.ew, x), 'E', 'W');
    return [A.label, esc(fill(A.grid, {ns, ew})) + (A.sub ? '<span class="ag-sub">' + esc(A.sub) + '</span>' : ''), true];
  }
  // Which side: the dividing street's longitude at this latitude (its nearest stretch if none spans it).
  let best = null;
  D.features.filter(f => f.properties.role === 'divide').forEach(f => {
    const c = f.geometry.coordinates;
    for (let i = 1; i < c.length; i++){
      const [p, q] = [c[i - 1], c[i]];
      const lo = Math.min(p[1], q[1]), hi = Math.max(p[1], q[1]);
      const yx = lo <= y && y <= hi && hi > lo ? p[0] + (q[0] - p[0]) * (y - p[1]) / (q[1] - p[1]) : null;
      const d = yx != null ? 0 : Math.min(Math.abs(y - p[1]), Math.abs(y - q[1]));
      if (!best || d < best[1] || (d === best[1] && yx != null && Math.abs(x - yx) < Math.abs(x - best[0]))) best = [yx != null ? yx : (Math.abs(y - p[1]) < Math.abs(y - q[1]) ? p[0] : q[0]), d];
    }
  });
  if (!best) return null;
  const side = x >= best[0] ? 'e' : 'w';
  // An example street on this side, nearest first (within about 1.5 km), else the config's.
  let ex = null, ed = 1500;
  D.features.filter(f => f.properties.role === side).forEach(f => f.geometry.coordinates.forEach(c => { const d = metres([x, y], c); if (d < ed){ ed = d; ex = f.properties.street; } }));
  ex = ex || (A.example || {})[side] || '';
  // Where the city's blocks follow a grid (D.axes, inside D.axesArea), the spot's block numbers too:
  // north-south streets' number, then east-west streets' number with the side (A.blocks).
  let blk = '';
  const ar = D.axesArea;
  if (D.axes && A.blocks && ar && x >= ar[0] && y >= ar[1] && x <= ar[2] && y <= ar[3]){
    const at = (pts, v) => { let i = 1; while (i < pts.length - 1 && pts[i][0] < v) i++; const [a, b] = [pts[i - 1], pts[i]]; return a[1] + (b[1] - a[1]) * (v - a[0]) / ((b[0] - a[0]) || 1); };
    const r = v => Math.max(0, Math.round(Math.abs(v) / 100) * 100);
    const n = at(D.axes.ns, y), e = at(D.axes.ew, x);
    blk = '<span class="ag-blk">' + esc(fill(A.blocks, {ns: r(n), ew: r(e) ? r(e) + ' ' + (e < 0 ? 'W' : 'E') : '0'})) + '</span>';
  }
  return [A.label, esc(side === 'e' ? A.east : A.west) + blk + (A.sub ? '<span class="ag-sub">' + esc(fill(A.sub, {street: ex})) + '</span>' : ''), true];
}
/* Directions: hand a place to a phone's or computer's own maps app for real routes and travel times (the card
   only gives straight-line distances). A [data-dir="lat,lng"] button opens Google Maps' directions to it; on
   Apple devices (iPhone, iPad, Mac) it first offers Apple Maps or Google Maps. Both are plain links: on a phone
   they open the installed app, starting from where the visitor is. Nothing is sent anywhere until they pick. */
const APPLE = /iPhone|iPad|iPod|Macintosh/.test(navigator.userAgent);
const DIR_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.6 14.4 8 8 14.4 1.6 8z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M6.2 10.2V8.4c0-.6.4-1 1-1h3M8.8 5.8l1.6 1.6-1.6 1.6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const DIR_TEXT = Object.assign({title: 'Directions', google: 'Google Maps', apple: 'Apple Maps', pick: 'Get directions in'}, CITY.directions || {});
const dirUrl = (app, lat, lng) => app === 'apple' ? 'https://maps.apple.com/?daddr=' + lat + ',' + lng
  : 'https://www.google.com/maps/dir/?api=1&destination=' + lat + ',' + lng;
const dirAt = (lat, lng, name) => ' data-dir="' + (+lat).toFixed(6) + ',' + (+lng).toFixed(6) + '" data-dir-name="' + esc(name || '') + '"';
// A small icon button (card header, Nearby rows) or a text button (cls "dir-t": the vote box).
const dirBtn = (lat, lng, name, text) => text
  ? '<button type="button" class="dir-t"' + dirAt(lat, lng, name) + '>' + esc(DIR_TEXT.title) + ' ↗</button>'
  : '<button type="button" class="dir"' + dirAt(lat, lng, name) + ' aria-label="' + esc(DIR_TEXT.title + (name ? ' to ' + name : '')) + '" title="' + esc(DIR_TEXT.title) + '">' + DIR_ICON + '</button>';
let dirPop = null;
function closeDirPop(){ if (dirPop){ dirPop.remove(); dirPop = null; } }
function openDirections(btn){
  const [lat, lng] = btn.dataset.dir.split(',');
  const go = app => { logEvent('directions', {app}); closeDirPop(); window.open(dirUrl(app, lat, lng), '_blank', 'noopener'); };
  if (!APPLE) return go('google');
  if (dirPop && dirPop._for === btn) return closeDirPop();
  closeDirPop();
  dirPop = document.createElement('div'); dirPop.className = 'dirpop'; dirPop._for = btn; dirPop.setAttribute('role', 'menu');
  dirPop.innerHTML = '<small>' + esc(DIR_TEXT.pick) + '</small>' + ['apple', 'google'].map(a => '<button type="button" role="menuitem" data-app="' + a + '">' + esc(DIR_TEXT[a]) + '</button>').join('');
  document.body.appendChild(dirPop);
  const r = btn.getBoundingClientRect(), w = dirPop.offsetWidth;
  dirPop.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.right - w)) + 'px';
  dirPop.style.top = (r.bottom + 6) + 'px';
  dirPop.querySelectorAll('[data-app]').forEach(b => b.onclick = () => go(b.dataset.app));
  dirPop.querySelector('button').focus();
}
document.addEventListener('click', e => { if (dirPop && !dirPop.contains(e.target) && e.target.closest('[data-dir]') !== dirPop._for) closeDirPop(); }, true);
addEventListener('resize', closeDirPop);
document.addEventListener('keydown', e => { if (e.key === 'Escape' && dirPop){ const b = dirPop._for; closeDirPop(); b.focus(); } });
const cardHead = (small, heading, extra) => '<div class="hh"><div><small>' + esc(small) + '</small><strong>' + esc(heading) + '</strong></div><div class="hb">' + (extra || '') +
  '<button type="button" class="share" aria-label="Share this spot" title="Share a link to this spot">' + SHARE_ICON + '</button><button type="button" aria-label="Close" id="hereX">×</button></div></div>';
// What every card's buttons do: close, share, route chips, focus chips, compare, section open/closed.
function wireCard(){
  document.getElementById('hereX').onclick = closeHere;
  const sh = here.querySelector('.share'); if (sh) sh.onclick = share;
  here.querySelectorAll('[data-dir]').forEach(b => b.onclick = () => openDirections(b));
  here.onscroll = closeDirPop;
  closeDirPop();
  here.querySelectorAll('[data-route]').forEach(b => b.addEventListener('click', () => pickRoute(b.dataset.route, !picked.has(b.dataset.route))));
  here.querySelectorAll('[data-pf]').forEach(b => b.addEventListener('click', () => { const [id, ...n] = b.dataset.pf.split(':'); setPlaceFocus(id, n.join(':'), true); if (placeF) logEvent('focus', {layer: id, via: 'card'}); }));
  here.querySelectorAll('details.sec').forEach(d => d.addEventListener('toggle', () => { const st = secState(); st[d.dataset.sec] = d.open; if (st === secOpen) try { localStorage.setItem('cardSections', JSON.stringify(secOpen)); } catch (e) {} }));
  const cg = here.querySelector('button.cmp-go'); if (cg) cg.onclick = () => { startCompare(); logEvent('compare'); };
  const ce = here.querySelector('.cmp-else'); if (ce) ce.onclick = () => logEvent('compare_elsewhere');
  const cc = here.querySelector('.cmp-cancel'); if (cc) cc.onclick = () => endCompare(0);
  here.querySelectorAll('[data-drop]').forEach(b => b.addEventListener('click', () => endCompare(+b.dataset.drop)));
}
function inspect(latlng, title, muniName){
  if (swallowTap) return;
  // Comparing: a new spot becomes the second place (B); tapping place A again does nothing.
  if (cmp && !(cmp.a[0].equals(latlng) && !cmp.b)){
    if (cmp.a[0].equals(latlng)) return;
    meNext = false;   // B is never drawn as the phone's own location
    if (!cardOf(latlng, title, muniName)){ renderEmpty(CITY.outside.beyond); here.hidden = false; return; }
    cmp.b = [latlng, title, muniName];
    // A second place beyond the city limits: show the region, so its pin isn't under the mask.
    if (scope === 'inner' && data.footprint && !hit(data.footprint, latlng.lng, latlng.lat)) setScope('outer', false);
    renderCompare(); return;
  }
  // A new spot starts the card at the top; a redraw of the same spot (data arriving) keeps the scroll.
  if (!lastInspect || !lastInspect[0].equals(latlng)) here.scrollTop = 0;
  lastInspect = [latlng, title, muniName];
  const c = cardOf(latlng, title, muniName);
  if (!c){ here.hidden = false; renderEmpty(CITY.outside.beyond); return; }
  placePin(latlng, title);
  here.hidden = false;
  // Waiting for the second place: a note with Cancel stands where the Compare button was.
  // Beside Compare: the site's Compare page, opened on this spot's unit with the closest match in another city.
  const unitHere = !c.outside && UNITS && c.hits[UNITS.id], unitCode = unitHere && String(unitHere.properties.code);
  const elsewhere = unitHere && data.profiles && data.profiles[unitCode] && CMP.elsewhere
    ? '<a class="cmp-go cmp-else" href="/compare/?mode=nbhd&amp;a=' + encodeURIComponent(CITY.id + ':' + unitCode) + '">' + esc(fill(CMP.elsewhere, {name: unitHere.properties.name})) + '</a>' : '';
  const cmpRow = cmp ? '<div class="cmp-wait"><span>' + esc(fill(CMP.wait, {name: c.heading})) + '</span><button type="button" class="cmp-cancel">' + esc(CMP.cancel) + '</button></div>'
    : '<div class="cmp-row"><button type="button" class="cmp-go">' + esc(CMP.start) + '</button>' + elsewhere + '</div>';
  if (c.outside){
    const m = c.m;
    here.innerHTML = cardHead('What’s here', c.heading, dirBtn(c.y, c.x, c.heading)) +
      '<div class="pills">' + c.pills + '</div>' + voteBox(c.x, c.y) + c.drive +
      (regionFeature(m.region) && focusKey !== m.region ? '<button type="button" class="focus-go">' + esc(fill(CITY.focus.show, {name: regionName(m.region)})) + '</button>' : '') +
      cmpRow + (c.boundsSection ? section('bounds', 'Boundaries', c.boundsSection) : '') + '<p class="outside-note">' + esc(CITY.outside.note) + '</p>' + reportBox(c.heading);
    wireCard(); wireReport(latlng, c.heading); drawVoteMark(c.x, c.y);
    const fg = here.querySelector('.focus-go'); if (fg) fg.onclick = () => setFocus(m.region, true);
    return;
  }
  here.innerHTML = cardHead('What’s here', c.heading, dirBtn(c.y, c.x, c.heading)) + '<div class="pills">' + c.pills + '</div>' + voteBox(c.x, c.y) + c.focus + c.tower + c.standout + cmpRow +
    // In the election view Representatives comes first, right under the voting place.
    (electShading() ? c.sections.filter(x => x[0] === 'reps').concat(c.sections.filter(x => x[0] !== 'reps')) : c.sections)
      .map(([id, t, body]) => section(id, t, body)).join('') + reportBox(c.heading);
  wireCard(); wireReport(latlng, c.heading);
  drawVoteMark(c.x, c.y);
}
/* ---------- Report a problem ----------
   A link at the foot of the card opens a small box: pick what's wrong, optionally include this place, then
   "Write the email" opens the person's own email app with a message to CITY.card.report.to ready to edit.
   Nothing leaves the page unless they press Send there; the place (its name and a map link) goes in only
   if they tick the box, which starts unticked. Counted as a bare 'report' event, with no details. */
const RPT = CITY.card && CITY.card.report && CITY.card.report.to ? Object.assign({
  link: 'Report a problem', kindLabel: 'What’s wrong?',
  kinds: ['A boundary or area is wrong', 'A representative or election detail is wrong', 'A road closure is wrong', 'A name, landmark or place is wrong', 'Something else'],
  include: 'Include this place ({name}) so I can find it', send: 'Write the email', copy: 'Copy the address',
  note: 'Opens your email app with a message to {to} ready to edit. Nothing is sent until you press Send, and your email address shows when you do.',
  subject: 'Layers.City · {city}: {kind}', body: 'What’s wrong:\n\n\n', placeText: 'The place: {name}\n{link}\n', footer: '—\nFrom the {city} map on Layers.City',
  copied: 'Address copied'}, CITY.card.report) : null;
function reportBox(name){
  if (!RPT) return '';
  return '<div class="rpt"><button type="button" class="rpt-go" aria-expanded="false">' + esc(RPT.link) + '</button>' +
    '<div class="rpt-box" hidden><label class="rpt-l">' + esc(RPT.kindLabel) + '<select class="rpt-kind">' +
    RPT.kinds.map((k, i) => '<option value="' + i + '">' + esc(k) + '</option>').join('') + '</select></label>' +
    (name ? '<label class="rpt-inc"><input type="checkbox" class="rpt-place"> <span>' + esc(fill(RPT.include, {name})) + '</span></label>' : '') +
    '<a class="rpt-send" href="mailto:' + esc(RPT.to) + '">' + esc(RPT.send) + '</a>' +
    '<p class="rpt-note">' + esc(fill(RPT.note, {to: RPT.to})) + ' <button type="button" class="rpt-copy">' + esc(RPT.copy) + '</button></p></div></div>';
}
function wireReport(latlng, name){
  const box = here.querySelector('.rpt'); if (!box) return;
  const go = box.querySelector('.rpt-go'), panelEl = box.querySelector('.rpt-box');
  go.onclick = () => { const open = panelEl.hidden; panelEl.hidden = !open; go.setAttribute('aria-expanded', String(open)); if (open) box.querySelector('.rpt-kind').focus(); };
  // A real mailto: link (rewritten as the choices change) works in more browsers and in-app views than a script redirect.
  const send = box.querySelector('.rpt-send'), kindSel = box.querySelector('.rpt-kind'), inc = box.querySelector('.rpt-place');
  const refresh = () => {
    const city = CITY.heading || CITY.title, kind = RPT.kinds[+kindSel.value] || '';
    let body = RPT.body;
    if (inc && inc.checked && latlng){
      const y = latlng.lat.toFixed(5), x = latlng.lng.toFixed(5);
      const link = location.origin + location.pathname + '#map=17/' + y + '/' + x + '&pin=' + y + ',' + x + '&name=' + encodeURIComponent(name);
      body += fill(RPT.placeText, {name, link}) + '\n';
    }
    body += fill(RPT.footer, {city});
    send.href = 'mailto:' + RPT.to + '?subject=' + encodeURIComponent(fill(RPT.subject, {city, kind})) + '&body=' + encodeURIComponent(body);
  };
  kindSel.onchange = refresh; if (inc) inc.onchange = refresh; refresh();
  send.onclick = () => logEvent('report');
  box.querySelector('.rpt-copy').onclick = async () => {
    try { await navigator.clipboard.writeText(RPT.to); flash(RPT.copied); } catch (e){ window.prompt('Copy this address:', RPT.to); }
  };
}
/* ---------- Compare two places ----------
   "Compare with another place" on the card, then tap the map or search: the card widens into one table,
   each row's label above the two places' values (A on the left, B on the right), section by section, the
   same rows the card has. Nothing is marked as better or worse. Tapping elsewhere replaces B; removing a
   place goes back to the other one's card. Links keep both (pin2=, name2=). */
const CMP = Object.assign({start: 'Compare with another place', wait: 'Now tap the map or search for a place to compare with {name}.', cancel: 'Cancel',
  title: 'Comparing', remove: 'Remove', stands: 'Stands out', none: '—',
  elsewhere: 'Places like {name} in other cities'}, CITY.card.compare || {});
let cmp = null, pinB = null;
function startCompare(){
  if (!lastInspect) return;
  cmp = {a: lastInspect.slice(), b: null};
  inspect(...lastInspect); queueHash();
}
// Leave Compare keeping one place: drop = 0 removes A (B's card stays), 1 removes B.
function endCompare(drop){
  const keep = cmp && (drop === 0 && cmp.b ? cmp.b : cmp.a);
  cmp = null;
  if (pinB){ map.removeLayer(pinB); pinB = null; }
  document.getElementById('side').classList.remove('cmp');
  pinLabel('');
  if (keep){ lastInspect = null; inspect(...keep); }
  queueHash();
}
function pinLabel(k){ const d = pin && pin.getElement() && pin.getElement().querySelector('.pin'); if (d){ d.textContent = k; d.classList.toggle('lettered', !!k); } }
// The rows of a card section, as [{key, label, html}] (a label seen twice gets a numbered key), and its notes.
function rowsOf(body){
  const t = document.createElement('template'); t.innerHTML = body || '';
  const seen = {}, rows = [], caveats = [];
  // Caveats ("Representative 2021 Census figures…") say the same thing for both places: once, under the section.
  t.content.querySelectorAll('dd span.caveat').forEach(c => { caveats.push(c.innerHTML); c.remove(); });
  t.content.querySelectorAll('dt').forEach(dt => {
    const label = dt.textContent.trim(), dd = dt.nextElementSibling;
    seen[label] = (seen[label] || 0) + 1;
    rows.push({key: label + '#' + seen[label], label: dt.innerHTML, html: dd && dd.tagName === 'DD' ? dd.innerHTML : ''});
  });
  const notes = caveats.concat([...t.content.querySelectorAll('p')].filter(p => !p.closest('dd')).map(p => p.innerHTML));
  return {rows, notes};
}
function renderCompare(){
  clearVoteMark();
  const A = cardOf(...cmp.a), B = cardOf(...cmp.b);
  if (!A || !B){ endCompare(A ? 1 : 0); return; }
  placePin(cmp.a[0], cmp.a[1]); pinLabel('A');
  if (pinB) pinB.setLatLng(cmp.b[0]);
  else pinB = L.marker(cmp.b[0], {pane:'pin', interactive:false, keyboard:false, icon: L.divIcon({className:'', iconSize:[20, 20], iconAnchor:[10, 10], html:'<span class="pin b lettered">B</span>'})}).addTo(map);
  document.getElementById('side').classList.add('cmp');
  here.hidden = false;
  const both = (label, a, b) => '<div class="cmp-r"><div class="cmp-l">' + label + '</div><div class="cmp-v">' + (a || '<span class="cmp-n">' + CMP.none + '</span>') + '</div><div class="cmp-v">' + (b || '<span class="cmp-n">' + CMP.none + '</span>') + '</div></div>';
  const cols = [A, B].map((c, i) => '<div class="cmp-c"><div class="cmp-top"><span class="cmp-k">' + 'AB'[i] + '</span><strong>' + esc(c.heading) + '</strong>' +
    '<button type="button" class="cmp-x" data-drop="' + i + '" aria-label="' + esc(CMP.remove + ' ' + c.heading) + '" title="' + esc(CMP.remove) + '">×</button></div><div class="pills">' + c.pills + '</div></div>').join('');
  const strip = h => h ? h.replace(/^<p class="standout">/, '<span class="standout">').replace(/<\/p>$/, '</span>') : '';
  let html = (A.standout || B.standout) ? '<div class="cmp-rows top">' + both(esc(CMP.stands), strip(A.standout), strip(B.standout)) + '</div>' : '';
  // Sections in the card's order; a section only one place has still shows, with dashes for the other.
  const ids = [], byId = [{}, {}];
  [A, B].forEach((c, i) => c.sections.forEach(([id, t, body]) => { if (!body) return; byId[i][id] = [t, body]; if (!ids.includes(id)) ids.push(id); }));
  ids.forEach(id => {
    const ra = rowsOf((byId[0][id] || [])[1]), rb = rowsOf((byId[1][id] || [])[1]);
    const keys = ra.rows.map(r => r.key).concat(rb.rows.map(r => r.key).filter(k => !ra.rows.some(r => r.key === k)));
    const get = (rs, k) => rs.rows.find(r => r.key === k);
    const rows = keys.map(k => { const a = get(ra, k), b = get(rb, k); return both((a || b).label, a && a.html, b && b.html); }).join('');
    const notes = [...new Set(ra.notes.concat(rb.notes))].map(n => '<p>' + n + '</p>').join('');
    html += section(id, (byId[0][id] || byId[1][id])[0], '<div class="cmp-rows">' + rows + notes + '</div>');
  });
  here.innerHTML = cardHead('What’s here', CMP.title) + '<div class="cmp-cols">' + cols + '</div>' + html;
  wireCard();
  queueHash();
}
// Redraw whatever the card shows (data arrived, focus changed).
function redrawCard(){
  if (here.hidden) return;
  if (cmp && cmp.b) renderCompare();
  else if (lastInspect) inspect(...lastInspect);
}
// What makes the unit stand out among its peers (engine/facts.py, built ahead of time): the strongest fact.
function standout(unit, heading){
  const d = unit && data.profiles ? data.profiles[String(unit.properties.code)] : null;
  const f = d && d.facts && d.facts[0];
  if (!f) return '';
  // The fact is about the unit. When the title already names it, the fact stands alone; otherwise
  // (a searched address or landmark) it says whose it is: "West Town: among the highest home values…".
  const text = heading === d.name ? esc(f.text) : '<b>' + esc(d.name) + ':</b> ' + esc(f.text.charAt(0).toLowerCase() + f.text.slice(1));
  return '<p class="standout"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m8 1.5 1.9 4 4.4.5-3.3 3 .9 4.3L8 11.1l-3.9 2.2.9-4.3-3.3-3 4.4-.5z"/></svg><span>' +
    text + ' <small>' + esc(f.value) + '</small></span></p>';
}
/* ---------- Where to vote ----------
   Until the polls close (card.vote.closes), a box near the top of the card says where people living at the spot
   vote, with a ballot-box mark on the map. The file (card.vote.file) loads after the map, and only while the polls
   haven't closed. Nothing shows after closing or where no area covers the spot. Not part of Compare. Three kinds:
   - A voting subdivision with its place (c code, w ward, n name, a address, e entrance, ae accessible entrance,
     vat, x/y): the place, its distance, entrances, Show on map.
   - A precinct only (p precinct, no x): the precinct and the official lookup.
   - A county of vote centers (k county key, card.vote.counties): anyone registered there can vote at any center,
     so the box lists the nearest few from the file's "centers" ([x, y, name, room, address, k, kind]; kind 1
     election day, 2 early voting, 3 both): early voting sites until early voting ends (card.vote.early), then
     election day centers. A county marked "precinct" (k plus c, and n/a/x/y for its polling place) shows the
     polling place on election day and the early voting sites before. */
const VOTE = CITY.card.vote || null;
const voteMarks = L.layerGroup();
const voteLive = () => !!(VOTE && Date.now() < Date.parse(VOTE.closes));
function voteAt(x, y){
  if (!voteLive() || !data.voting) return null;
  const f = hit(data.voting, x, y);
  return f ? f.properties : null;
}
const VOTE_SHOW = 3;
// 'soon' before early voting, 'early' during it, 'ed' after it (election day itself, and the gap before it).
function votePhase(){
  const E = VOTE.early; if (!E) return 'ed';
  const t = cityToday(VOTE.tz);
  return t < E.from ? 'soon' : t <= E.to ? 'early' : 'ed';
}
// The vote centers nearest a spot in county k, of a kind bit (1 election day, 2 early voting).
function nearCenters(x, y, k, bit){
  return (data.voting.centers || []).filter(c => c[5] === k && c[6] & bit)
    .map(c => [c, metres([x, y], [c[0], c[1]])]).sort((a, b) => a[1] - b[1]).slice(0, VOTE_SHOW);
}
// The places a box points at, for the marks and Show on map: [[lng, lat], ...].
function votePlaces(x, y){
  const v = voteAt(x, y); if (!v) return [];
  const C = v.k && VOTE.counties && VOTE.counties[v.k];
  if (C){
    const ph = votePhase();
    if (C.precinct && ph === 'ed') return v.x != null ? [[v.x, v.y]] : [];
    return nearCenters(x, y, v.k, ph === 'ed' ? 1 : 2).map(([c]) => [c[0], c[1]]);
  }
  if (v.en && VOTE.early && votePhase() !== 'ed') return v.ex != null ? [[v.ex, v.ey]] : [];
  return v.x != null ? [[v.x, v.y]] : [];
}
const shortDate = s => isoDate(s).toLocaleDateString(CITY.locale, {weekday:'short', month:'short', day:'numeric'});
function voteBox(x, y){
  const v = voteAt(x, y); if (!v) return '';
  const today = cityToday(VOTE.tz) === VOTE.date;
  let when = today ? VOTE.today : fill(VOTE.title, {date: shortDate(VOTE.date)}), hours = VOTE.hours;
  const ctx = {sub: v.c ? String(+v.c.slice(2)) : '', ward: v.w, precinct: v.p || v.c, asof: niceDate(data.voting.asof)};
  let link = '<a href="' + esc(VOTE.link ? VOTE.link[1] : '') + '" target="_blank" rel="noopener">' + esc(VOTE.link ? VOTE.link[0] : '') + ' ↗</a>';
  let body, note = VOTE.note;
  const place = (n, a, d, extra) => n ? '<b>' + esc(n) + '</b><span>' + esc([extra, a, dist(d) + ' away'].filter(Boolean).join(' · ')) + '</span>' : '<b>' + esc(a) + '</b><span>' + dist(d) + ' away</span>';
  const C = v.k && VOTE.counties && VOTE.counties[v.k];
  if (C){
    // A county where people can vote at any vote center (or, early, at any early voting site).
    const ph = votePhase(), E = VOTE.early, counts = (data.voting.counts || {})[v.k] || {};
    let firstName = '';
    Object.assign(ctx, {county: C.name});
    link = '<a href="' + esc(C.link[1]) + '" target="_blank" rel="noopener">' + esc(C.link[0]) + ' ↗</a>';
    if (ph !== 'ed'){ when = ph === 'soon' ? fill(E.soon, {from: shortDate(E.from)}) : fill(E.title, {from: shortDate(E.from), to: shortDate(E.to)}); hours = E.hours; }
    if (C.precinct && ph === 'ed'){
      if (v.x == null) return '';
      body = '<p class="vote-lead">' + esc(VOTE.lead) + '</p><p class="vote-pl">' + place(v.n, v.a, metres([x, y], [v.x, v.y]), v.r) + '</p>';
      note = VOTE.precinctNote || note; firstName = v.n;
    } else {
      const list = nearCenters(x, y, v.k, ph === 'ed' ? 1 : 2);
      if (!list.length) return '';
      firstName = list[0][0][2];
      body = '<p class="vote-lead">' + esc(fill(ph === 'ed' ? VOTE.centersLead : VOTE.earlyLead, ctx)) + '</p>' +
        list.map(([c, d]) => '<p class="vote-pl vote-li">' + place(c[2], c[4], d, '') + '</p>').join('') +
        '<p class="vote-ex">' + esc(C.precinct && v.n ? fill(VOTE.precinctEarly, {n: v.n}) :
          fill(ph === 'ed' ? VOTE.centersMore : VOTE.earlyMore, {n: ph === 'ed' ? counts.ed : counts.ev, ed: counts.ed, county: C.name})) + '</p>';
      if (C.precinct) note = VOTE.precinctNote || note;
    }
    const first = votePlaces(x, y)[0];
    body += '<p class="vote-acts"><button type="button" class="vote-go">' + esc(VOTE.show) + '</button>' +
      (first ? dirBtn(first[1], first[0], firstName, true) : '') + link + '</p>';
  } else if (v.en && VOTE.early && votePhase() !== 'ed'){
    // An assigned early voting site (New York: each election district has its own), then the election day site.
    const ph = votePhase(), E = VOTE.early;
    when = ph === 'soon' ? fill(E.soon, {from: shortDate(E.from)}) : fill(E.title, {from: shortDate(E.from), to: shortDate(E.to)}); hours = E.hours;
    const ed = v.n ? fill(VOTE.assignedDay, {n: v.n, a: v.a, date: shortDate(VOTE.date)}) : '';
    body = '<p class="vote-lead">' + esc(VOTE.earlyLead) + '</p><p class="vote-pl">' +
      (v.ex != null ? place(v.en, v.ea, metres([x, y], [v.ex, v.ey]), '') : '<b>' + esc(v.en) + '</b><span>' + esc(v.ea) + '</span>') + '</p>' +
      (ed ? '<p class="vote-ex">' + esc(ed) + '</p>' : '') +
      '<p class="vote-acts">' + (v.ex != null ? '<button type="button" class="vote-go">' + esc(VOTE.show) + '</button>' + dirBtn(v.ey, v.ex, v.en, true) : '') + link + '</p>';
  } else if (v.n && v.x == null){
    // A named site the source couldn't place: name and address, no distance or map.
    body = '<p class="vote-lead">' + esc(VOTE.lead) + '</p><p class="vote-pl"><b>' + esc(v.n) + '</b><span>' + esc(v.a || '') + '</span></p>' +
      '<p class="vote-acts vote-acts-solo">' + link + '</p>';
  } else if (v.x != null){
    // A voting place for the spot: name, address and distance, entrances, Show on map.
    const d = metres([x, y], [v.x, v.y]);
    const more = [v.e && fill(VOTE.entrance, v), v.ae && fill(VOTE.access, v), v.vat && VOTE.vat].filter(Boolean);
    body = '<p class="vote-lead">' + esc(VOTE.lead) + '</p><p class="vote-pl">' + place(v.n, v.a, d, '') + '</p>' +
      (more.length ? '<p class="vote-ex">' + more.map(esc).join('<br>') + '</p>' : '') +
      '<p class="vote-acts"><button type="button" class="vote-go">' + esc(VOTE.show) + '</button>' + dirBtn(v.y, v.x, v.n || v.a, true) + link + '</p>';
  } else {
    // Only the precinct is known (no published polling place list): name it and link to the official lookup.
    body = '<p class="vote-lead">' + esc(VOTE.lead) + '</p><p class="vote-pl"><b>' + esc(fill(VOTE.precinct, ctx)) + '</b>' +
      (VOTE.precinctSub ? '<span>' + esc(fill(VOTE.precinctSub, ctx)) + '</span>' : '') + '</p>' +
      '<p class="vote-acts vote-acts-solo">' + link + '</p>';
  }
  return '<div class="vote" role="note"><i class="vote-ic" aria-hidden="true">' + BALLOT_ICON + '</i><div class="vote-tx">' +
    '<small>' + esc(when) + ' · ' + esc(hours) + '</small>' + body +
    '<p class="vote-note">' + esc(fill(note, ctx)) + '</p></div></div>';
}
const BALLOT_ICON = '<svg viewBox="0 0 24 24"><path d="M9.5 3.5h5l1 6h-7z" fill="currentColor" opacity=".55"/><path d="M4 10.5h16v9.5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z" fill="currentColor"/><rect x="8.5" y="12.6" width="7" height="1.6" rx=".8" fill="var(--vote-slot,#fff)"/><path d="M10.6 6.6l1.2 1.2 2.3-2.4" fill="none" stroke="var(--vote-slot,#fff)" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
// Ballot-box marks at the places the box names for the spot on the card (removed with the card).
function drawVoteMark(x, y){
  voteMarks.clearLayers();
  const pts = votePlaces(x, y);
  if (!pts.length) return;
  pts.forEach(([px, py], i) => voteMarks.addLayer(L.marker(L.latLng(py, px), {pane:'pin', interactive:false, keyboard:false, zIndexOffset:-500 - i,
    icon: L.divIcon({className:'', iconSize:[28, 36], iconAnchor:[14, 36], html:'<span class="vote-mk' + (i ? ' vote-mk2' : '') + '">' + BALLOT_ICON + '</span>'})})));
  if (!map.hasLayer(voteMarks)) voteMarks.addTo(map);
  const go = here.querySelector('.vote-go');
  if (go) go.onclick = () => frame(L.latLngBounds([L.latLng(y, x)].concat(pts.map(([px, py]) => L.latLng(py, px)))).pad(0.2), {maxZoom: 17});
}
function clearVoteMark(){ voteMarks.clearLayers(); }
// Free-flow drive time from the nearest grid point (about 1.5 km apart), and the municipality's typical time.
function driveHere(x, y, m){
  const g = data.driveGrid; if (!g || !CITY.drive) return '';
  let best = null, bd = Infinity;
  g.points.forEach(p => { const d = metres([x, y], p); if (d < bd){ bd = d; best = p; } });
  if (!best || bd > 2000) return '';
  const t = driveTier(best[2]);
  return '<div class="live drive"><dl><dt>Drive to ' + esc(CITY.drive.hubName) + '</dt><dd><span class="tier"><i style="background:var(' + t[2] + ')"></i>About ' + best[2] + ' min from here</span>' +
    (m.drive != null && !m.rest ? '<span>Typical for ' + esc(m.name) + ': ' + m.drive + ' min</span>' : '') +
    '<span class="caveat">With no traffic, at posted speeds. Most trips take longer.</span></dd></dl></div>';
}
function renderEmpty(msg){
  here.scrollTop = 0;
  here.innerHTML = '<div class="hh"><div><small>What’s here</small><strong>Tap the map</strong></div><button type="button" aria-label="Close" id="hereX">×</button></div><div class="hint">' + esc(msg) + '</div>';
  document.getElementById('hereX').onclick = closeHere;
}
// The card scrolls on its own when it's taller than the screen. The slim scrollbar shows on hover and
// while scrolling; the header stays put and gets a hairline once content slides under it.
let hereScrollT = 0;
here.addEventListener('scroll', () => {
  here.classList.toggle('scrolled', here.scrollTop > 0);
  here.classList.add('scrolling'); clearTimeout(hereScrollT);
  hereScrollT = setTimeout(() => here.classList.remove('scrolling'), 900);
}, {passive: true});
// Phones: the card stops above the layer sheet, whatever height the sheet is.
if (window.ResizeObserver) new ResizeObserver(() => {
  document.documentElement.style.setProperty('--panel-h', (matchMedia('(max-width:760px)').matches && !panel.hidden ? panel.offsetHeight : 0) + 'px');
}).observe(panel);
// Desktop: the panel, the card column and the zoom buttons stop just above the
// attribution strip, which wraps to more lines on narrower windows.
if (window.ResizeObserver){
  const attr = map.attributionControl.getContainer();
  new ResizeObserver(() => {
    document.documentElement.style.setProperty('--attr-h', (attr.offsetHeight || 18) + 'px');
  }).observe(attr);
}
function closeHere(){
  here.hidden = true; clearVoteMark(); if (meRing){ map.removeLayer(meRing); meRing = null; }
  if (cmp){ cmp = null; document.getElementById('side').classList.remove('cmp'); }
  if (pinB){ map.removeLayer(pinB); pinB = null; }
  if (pin){ map.removeLayer(pin); pin = null; pinIsMe = false; queueHash(); }
}

/* ---------- Guided first visit ----------
   A short tour of the city through the map (CITY.tour): each step sets the layers (exactly the listed ones),
   the scope and the view, may open a card, and outlines the step's layers in the panel so people learn where
   they are. The map as it was before the tour is kept as a link (linkState) and put back when it ends, by
   Done or by closing it. A first visit (no link in the address, not seen before in this browser) gets a
   small invitation; the Tour button in the panel footer starts it any time. */
const TOUR = CITY.tour && CITY.tour.steps && CITY.tour.steps.length ? CITY.tour : null;
const tourBox = document.getElementById('tour'), tourInv = document.getElementById('tourInv');
let tourI = -1, tourSnap = null;
const TOUR_KEY = 'tourSeen-' + CITY.id;
function tourSeen(){ try { localStorage.setItem(TOUR_KEY, '1'); } catch (e) {} tourInv.hidden = true; }
function startTour(){
  if (!TOUR) return;
  logEvent('tour_start');
  tourSeen();
  tourSnap = linkState();
  if (placeF) setPlaceFocus(null, null, false);
  if (focusKey) setFocus(null, false);
  unfocus();
  showStep(0);
}
function showStep(i){
  if (ptab !== 'all') setPanelTab('all');   // the step outlines rows that a tab could be hiding
  const st = TOUR.steps[i], last = i === TOUR.steps.length - 1;
  tourI = i;
  const want = new Set(st.layers || []);
  LAYERS.forEach(it => { const cb = document.getElementById('lyr-' + it.id); if (!cb) return; const w = want.has(it.id); if (cb.checked !== w){ cb.checked = w; setLayer(it.id, w); } });
  if ((st.scope || 'inner') !== scope) setScope(st.scope || 'inner', false);
  if (st.pin) inspect(L.latLng(st.pin.at || CITY.example.at), st.pin.name || CITY.example.name); else closeHere();
  // Outline the step's layers in the panel (on a phone the panel is folded away to clear the map).
  document.querySelectorAll('#layers .row.tour-hi').forEach(r => r.classList.remove('tour-hi'));
  const rows = (st.hi || []).map(id => document.querySelector('label[for="lyr-' + id + '"]')).filter(Boolean);
  rows.forEach(r => { r.classList.add('tour-hi'); const g = r.closest('.grp.folded'); if (g) foldGroup(g, false, false); });
  if (wide()){ if (rows[0]) rows[0].scrollIntoView({block: 'nearest', behavior: 'smooth'}); }
  else panel.classList.add('collapsed');
  const dots = TOUR.steps.map((_, k) => '<i' + (k === i ? ' class="on"' : '') + '></i>').join('');
  tourBox.innerHTML = '<div class="tr-h"><small>' + esc(fill(TOUR.stepText || '{n} of {of}', {n: i + 1, of: TOUR.steps.length})) + '</small>' +
    '<button type="button" class="tr-x" aria-label="' + esc(TOUR.closeText || 'Close the tour') + '">×</button></div>' +
    '<strong>' + esc(st.title) + '</strong><p>' + esc(st.text) + '</p>' +
    '<div class="tr-b"><button type="button" class="tr-back"' + (i ? '' : ' hidden') + '>' + esc(TOUR.back || 'Back') + '</button><span class="tr-dots" aria-hidden="true">' + dots + '</span>' +
    '<button type="button" class="tr-next">' + esc(last ? (TOUR.done || 'Done') : (TOUR.next || 'Next')) + '</button></div>';
  tourBox.hidden = false;
  tourBox.querySelector('.tr-x').onclick = endTour;
  tourBox.querySelector('.tr-back').onclick = () => showStep(i - 1);
  tourBox.querySelector('.tr-next').onclick = () => last ? endTour() : showStep(i + 1);
  tourBox.querySelector('.tr-next').focus({preventScroll: true});
  frame(st.view === 'region' ? REGION_VIEW : Array.isArray(st.view) ? L.latLngBounds(st.view) : CITY_BOUNDS);
}
function endTour(){
  if (tourI < 0) return;
  if (tourSnap != null) logEvent('tour_end', {step: tourI + 1, done: tourI === TOUR.steps.length - 1});
  tourI = -1; tourBox.hidden = true;
  document.querySelectorAll('#layers .row.tour-hi').forEach(r => r.classList.remove('tour-hi'));
  if (tourSnap != null){ applyHash('#' + tourSnap); queueHash(); }
  tourSnap = null;
}
function tourInvite(){
  if (!TOUR) return;
  document.getElementById('tourBtn').hidden = false;
  let seen = false; try { seen = !!localStorage.getItem(TOUR_KEY); } catch (e) {}
  if (seen || location.hash) return;   // someone opening a shared link came for that view
  tourInv.innerHTML = '<span>' + esc(TOUR.invite) + '</span><button type="button" class="tr-go">' + esc(TOUR.start || 'Take the tour') + '</button>' +
    '<button type="button" class="tr-x" aria-label="' + esc(TOUR.dismissText || 'No thanks') + '">×</button>';
  tourInv.hidden = false;
  tourInv.querySelector('.tr-go').onclick = startTour;
  tourInv.querySelector('.tr-x').onclick = tourSeen;
}
document.getElementById('tourBtn').addEventListener('click', startTour);
document.addEventListener('keydown', e => {
  if (tourI < 0 || /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
  if (e.key === 'Escape') endTour();
  else if (e.key === 'ArrowRight' && tourI < TOUR.steps.length - 1) showStep(tourI + 1);
  else if (e.key === 'ArrowLeft' && tourI > 0) showStep(tourI - 1);
});

/* ---------- Views: named presets (CITY.presets) ----------
   A chip row at the top of the panel. Each view replaces the whole map state: exactly its layers (and
   sub-toggles), its lens, its bus families, the regional or city scope, no filters, picks, focus or card,
   then frames its view. Changing anything after that (a layer, the lens, a chip) marks the view "Custom";
   moving the map, tapping a spot or focusing on a place doesn't. Links carry preset= while it holds.
   A view with "boundaries" (Who represents me) shows one of them at a time, with chips to switch: it leads
   with the layer of the next election within "window" days (CITY.presets.elections), else its "lead". */
const PRESETS = CITY.presets && CITY.presets.items && CITY.presets.items.length ? CITY.presets : null;
const presetBox = document.getElementById('presets'), qHint = document.getElementById('qhint');
var presetOn = null, presetSig = '', presetCustom = false;   // var: queueHash can run before this line
const presetById = id => PRESETS && PRESETS.items.find(p => p.id === id);
// The link without the parts that don't make a view custom: map position, pins, focus and the view itself.
const PRESET_LOOSE = new Set(['map', 'pin', 'name', 'pin2', 'name2', 'focus', 'preset']);
const presetState = () => linkState().split('&').filter(kv => !PRESET_LOOSE.has(kv.split('=')[0])).join('&');
const todayISO = () => { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
// The next election (today counts) within the window, if any.
function nextElection(){
  const t = todayISO(), win = (PRESETS.window || 180) * 864e5;
  return (PRESETS.elections || []).filter(e => e.date >= t && Date.parse(e.date) - Date.parse(t) <= win)
    .sort((a, b) => a.date.localeCompare(b.date))[0] || null;
}
function presetLead(p){
  const e = nextElection(), ok = id => p.boundaries.includes(id) && LAYERS.some(it => it.id === id);
  return e && ok(e.lead) ? e.lead : p.lead || p.boundaries[0];
}
function presetFrame(p){
  frame(p.view === 'region' ? REGION_VIEW : Array.isArray(p.view) ? L.latLngBounds(p.view) : CITY_BOUNDS);
}
function applyPreset(id){
  if (ptab !== 'all') setPanelTab('all');
  const p = presetById(id); if (!p) return;
  if (tourI >= 0){ tourSnap = null; endTour(); }
  const lyr = (p.layers || []).slice();
  if (p.boundaries) lyr.push(presetLead(p));
  const parts = ['layers=' + (lyr.length ? lyr.join(',') : 'none')];
  if (p.scope === 'outer') parts.push('view=region');
  clearFilters(); applyFilter();
  Object.keys(pick).forEach(k => { pick[k] = LENSES[k].pick[0][0]; });
  BOARDS.forEach(it => setBoard(it.id, it.boards[0][0]));
  if (BUSES) setBusFams(BUS_DEFAULT);
  setLens(FIRST_LENS);
  if (p.lens) parts.push('lens=' + p.lens);
  if (p.bus) parts.push('bus=' + p.bus.join('+'));
  if (p.bike) parts.push('bike=' + p.bike.join('+'));
  applyHash('#' + parts.join('&'));
  presetFrame(p);
  presetOn = p.id; presetSig = presetState(); presetCustom = false;
  drawPresets();
  tourInv.hidden = true;   // they've found their way in; the invitation can go
  if (!wide()) panel.classList.add('collapsed');
  queueHash();
}
// Who represents me: show one set of boundaries in place of another, still the same view.
function presetBoundary(id){
  const p = presetById(presetOn); if (!p || !p.boundaries) return;
  p.boundaries.forEach(b => { const cb = document.getElementById('lyr-' + b); if (!cb) return; const w = b === id; if (cb.checked !== w){ cb.checked = w; setLayer(b, w); } });
  presetSig = presetState(); presetCustom = false;
  drawPresets(); queueHash();
}
function drawPresets(){
  if (!PRESETS || !presetBox) return;
  const p = presetById(presetOn);
  // A dropdown, so the views take one line of the panel. "Custom" shows as the selected (disabled)
  // option once the map changes after a view, so picking that view again fires a change.
  const lab = esc(PRESETS.label || 'Views');
  let h = '<label class="pr-row"><b class="pr-h">' + lab + '</b><span class="pr-sel"><select id="presetSel" aria-label="' + lab + '"' + (p && presetCustom ? ' title="' + esc(fill(PRESETS.customNote || 'Changed from {name}', {name: p.name})) + '"' : '') + '>' +
    (!p ? '<option value="" selected disabled>' + esc(PRESETS.placeholder || 'Pick a view') + '</option>' : '') +
    (p && presetCustom ? '<option value="" selected disabled>' + esc(PRESETS.customText || 'Custom') + ' (' + esc(fill(PRESETS.customFrom || 'from {name}', {name: p.name})) + ')</option>' : '') +
    PRESETS.items.map(it => '<option value="' + esc(it.id) + '"' + (it.id === presetOn && !presetCustom ? ' selected' : '') + '>' + esc(it.name) + '</option>').join('') +
    '</select></span></label>';
  if (p && !presetCustom){
    if (p.note) h += '<p class="pr-note">' + esc(p.note) + '</p>';
    if (p.boundaries){
      const on = p.boundaries.filter(b => state[b]);
      h += '<div class="chips pr-b" role="radiogroup" aria-label="' + esc(PRESETS.boundaryLabel || 'Boundaries') + '">' + p.boundaries.filter(b => LAYERS.some(it => it.id === b)).map(b => {
        const it = LAYERS.find(x => x.id === b);
        return '<button type="button" role="radio" data-pb="' + esc(b) + '" aria-checked="' + on.includes(b) + '">' + esc(it.name) + '</button>';
      }).join('') + '</div>';
      const e = nextElection();
      if (e) h += '<p class="pr-note">' + esc(fill(PRESETS.electionText || 'Next: {label}', {label: e.label})) + '</p>';
    }
  }
  presetBox.innerHTML = h;
  presetBox.hidden = false;
  const sel = presetBox.querySelector('#presetSel');
  sel.addEventListener('change', () => { const id = sel.value; if (!id) return; applyPreset(id); logEvent('view', {id}); });
  presetBox.querySelectorAll('[data-pb]').forEach(b => b.addEventListener('click', () => presetBoundary(b.dataset.pb)));
  presetHint();
}
// The search box's hint, while a view asks for an address and no spot is pinned.
function presetHint(){
  if (!qHint) return;
  const p = presetById(presetOn), show = !!(p && p.hint && !presetCustom && !pin);
  if (show) qHint.textContent = p.hint;
  qHint.hidden = !show;
}
// Called whenever the map's state may have changed (from queueHash).
function checkPreset(){
  if (!presetOn) return;
  const c = presetState() !== presetSig;
  if (c !== presetCustom){ presetCustom = c; drawPresets(); } else presetHint();
}
function clearPreset(){ presetOn = null; presetCustom = false; drawPresets(); }
if (qHint) qHint.addEventListener('click', () => document.getElementById('q').focus());

/* ---------- Special events: a view and a banner while a big one is on ----------
   An event marked "banner" in events.geojson (engine/events.py) becomes a view at the top of the Views
   list from a few days before it ("bannerFrom") until its last closure ends: only the layers in the
   events layer's "viewLayers" (streets and the event's closures), framed on its closures. The first time
   someone opens the map in that window, a banner offers the view; tapping it or closing it is remembered
   in this browser, per event, so it doesn't come back on every visit. */
const EVL = byKind('events'), evBanner = document.getElementById('evBanner');
function eventsNow(){
  if (!EVL || !loaded[EVL.file]) return [];
  const today = cityToday(EVL.tz), now = cityNow(EVL.tz);
  return (loaded[EVL.file].events || []).filter(e => e.banner && e.bannerFrom <= today && e.end > now);
}
// "today", "this weekend" or "Oct 24 to Oct 25".
function evPhrase(e){
  const today = cityToday(EVL.tz), s = e.start.slice(0, 10), en = e.end.slice(0, 10);
  if (en === today) return EVL.todayText;
  const t = new Date(today + 'T12:00:00'), sun = new Date(t.getTime() + ((7 - t.getDay()) % 7) * 864e5);
  const sunISO = sun.getFullYear() + '-' + String(sun.getMonth() + 1).padStart(2, '0') + '-' + String(sun.getDate()).padStart(2, '0');
  if (en <= sunISO && [0, 6].includes(new Date(en + 'T12:00:00').getDay())) return EVL.weekendText;
  return s === en ? niceDate(s) : fill(EVL.rangeText, {from: niceDate(s), to: niceDate(en)});
}
function eventPresets(){
  if (!PRESETS) return;
  eventsNow().slice().reverse().forEach(e => {
    if (!presetById('ev-' + e.id)) PRESETS.items.unshift({id: 'ev-' + e.id, name: fill(EVL.viewName, {short: e.short}),
      note: fill(EVL.viewNote, {name: e.name}), layers: EVL.viewLayers, view: e.bounds});
  });
}
function showEvent(e){
  if (presetById('ev-' + e.id)) return applyPreset('ev-' + e.id);
  applyHash('#layers=' + EVL.viewLayers.join(','));
  frame(L.latLngBounds(e.bounds));
  if (!wide()) panel.classList.add('collapsed');
  queueHash();
}
function eventBanner(){
  const e = eventsNow()[0];
  if (!e || !evBanner || state[EVL.id]) return;
  const key = 'eventSeen-' + CITY.id + '-' + e.id;
  let seen = false; try { seen = !!localStorage.getItem(key); } catch (x) {}
  if (seen) return;
  const done = () => { try { localStorage.setItem(key, '1'); } catch (x) {} evBanner.hidden = true; };
  evBanner.innerHTML = '<i class="ev-dot" aria-hidden="true"></i><span>' + esc(fill(EVL.bannerText, {name: e.name, when: evPhrase(e)})) + '</span>' +
    '<button type="button" class="tr-go">' + esc(EVL.bannerGo) + '</button>' +
    '<button type="button" class="tr-x" aria-label="' + esc(EVL.bannerClose) + '">×</button>';
  tourInv.hidden = true;   // one invitation at a time; the tour's comes back on a later visit
  evBanner.hidden = false;
  evBanner.querySelector('.tr-go').onclick = () => { done(); showEvent(e); logEvent('event_view', {id: e.id}); };
  evBanner.querySelector('.tr-x').onclick = () => { done(); logEvent('event_dismiss', {id: e.id}); };
  logEvent('event_banner', {id: e.id});
}

/* ---------- Theme: Auto (device setting), Light or Dark; remembered in this browser ---------- */
function applyTheme(choice){
  if (choice === 'light' || choice === 'dark') document.documentElement.dataset.theme = choice;
  else delete document.documentElement.dataset.theme;
  document.querySelectorAll('[data-theme-choice]').forEach(b => b.setAttribute('aria-checked', String(b.dataset.themeChoice === choice)));
  try { if (choice === 'auto') localStorage.removeItem('theme'); else localStorage.setItem('theme', choice); } catch (e) {}
}
let savedTheme = 'auto';
try { savedTheme = localStorage.getItem('theme') || 'auto'; } catch (e) {}
applyTheme(savedTheme);
document.querySelectorAll('[data-theme-choice]').forEach(b => b.addEventListener('click', () => applyTheme(b.dataset.themeChoice)));

/* ---------- Address search (OpenStreetMap Nominatim; one request per search, per its usage policy) ---------- */
const qf = document.getElementById('qf'), q = document.getElementById('q'), go = document.getElementById('go'), results = document.getElementById('results');
let lastSearch = 0;
function showResults(html){ results.innerHTML = html; results.hidden = !html; }
function placeLabel(r){
  const a = r.address || {};
  const street = a.road || a.pedestrian || a.footway || '';
  if (a.house_number && street) return a.house_number + ' ' + street;
  return r.name || street || r.display_name.split(',')[0];
}
function placeSub(r){
  const a = r.address || {};
  const name = r.name && r.name !== placeLabel(r) ? r.name : '';
  const town = data.footprint && !hit(data.footprint, +r.lon, +r.lat) ? (a.city || a.town || a.village || a.municipality) : '';
  return [name, a.neighbourhood || a.suburb || a.quarter, town, a.postcode].filter(Boolean).join(' · ');
}
function choose(r){ goTo(L.latLng(+r.lat, +r.lon), placeLabel(r), true); }
function goTo(latlng, name, fromSearch, minZoom, muniName){
  showResults('');
  if (fromSearch) logEvent('card', {via: 'search'});
  if (fromSearch) q.value = name;
  // A spot beyond the city limits isn't visible in city-only mode: switch to the region view.
  if (scope === 'inner' && data.footprint && !hit(data.footprint, latlng.lng, latlng.lat)) setScope('outer', false);
  inspect(latlng, name, muniName);  // fill the card first, so a map-move problem can't hide the result
  const zoom = minZoom || Math.max(map.getZoom(), 15);
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  try {
    const size = map.getSize();
    if (calm || !size.x || !size.y) map.setView(latlng, zoom, {animate: false});
    else map.flyTo(latlng, zoom, {duration: .8});
  } catch (err){ try { map.setView(latlng, zoom, {animate: false}); } catch (e2){} }
}
let busy = false;
async function geocode(url){
  // One retry after a pause covers a brief rate-limit (HTTP 429) or network hiccup.
  for (let attempt = 0; ; attempt++){
    try {
      const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), 10000);
      const r = await fetch(url, {signal: ctl.signal, headers: {'Accept-Language': 'en'}});
      clearTimeout(timer);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    } catch (err){
      if (attempt >= 1) throw err;
      await new Promise(r => setTimeout(r, 1500));
    }
  }
}
qf.addEventListener('submit', async e => {
  e.preventDefault();
  const text = q.value.trim();
  if (!text || !data.footprint || busy) return;
  // A place or landmark typed in full goes straight there, without a network search.
  const sugg = suggestions(text), exact = sugg.filter(x => x.s === 0);
  if (exact.length === 1){ exact[0].go(); return; }
  if (exact.length > 1){ showSuggestions(exact, false); return; }
  busy = true;
  const wait = 1100 - (Date.now() - lastSearch);
  if (wait > 0) await new Promise(r => setTimeout(r, wait));
  lastSearch = Date.now();
  go.disabled = true; go.textContent = '…';
  const url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=6&countrycodes=' + CITY.search.country + '&bounded=1' +
    '&viewbox=' + (CITY.search.regionViewbox || CITY.search.viewbox) + '&q=' + encodeURIComponent(text);
  try {
    let list;
    try { list = await geocode(url); }
    catch (err){ showResults('<li class="msg">Address search isn’t responding right now. Try again in a moment, or tap the map instead.</li>'); return; }
    // Keep matches inside the city (and, if the city searches its region too, the municipalities around it,
    // listed after the city's own), and merge repeats of the same address (one per entrance/postcode).
    const inCity = [], inside = r => hit(data.footprint, +r.lon, +r.lat);
    list.filter(r => inside(r) || (CITY.search.regionViewbox && hit(data.outer, +r.lon, +r.lat)))
      .sort((a, b) => inside(b) - inside(a)).forEach(r => {
      const dup = inCity.some(k => placeLabel(k) === placeLabel(r) && metres([+k.lon, +k.lat], [+r.lon, +r.lat]) < 150);
      if (!dup) inCity.push(r);
    });
    if (!inCity.length && sugg.length){
      showSuggestions(sugg, false);   // e.g. a misspelt or partial place name
    } else if (!inCity.length){
      showResults('<li class="msg">' + esc(fill(CITY.search.noMatch, {q: text})) + '</li>');
    } else if (inCity.length === 1){
      choose(inCity[0]);
    } else {
      window.__hits = inCity;
      showResults(inCity.map((r, i) => '<li><button type="button" data-i="' + i + '">' + esc(placeLabel(r)) + (placeSub(r) ? '<span>' + esc(placeSub(r)) + '</span>' : '') + '</button></li>').join(''));
      results.querySelectorAll('button').forEach(b => b.addEventListener('click', () => choose(window.__hits[+b.dataset.i])));
      results.querySelector('button').focus();
    }
  } catch (err){
    console.error(err);
    showResults('<li class="msg">Something went wrong showing that result. Try again, or tap the map instead.</li>');
  } finally { busy = false; go.disabled = false; go.textContent = 'Find'; }
});
q.addEventListener('keydown', e => { if (e.key === 'Escape'){ showResults(''); q.blur(); } });
/* Suggestions as you type: landmarks plus place names (neighbourhoods, known-as names, the city's big
   areas and the municipalities around it). All from data already loaded: instant, no network. Nominatim's
   policy rules out autocomplete-as-you-type, so live suggestions never come from it. */
const norm = s => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/['’]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
let PLACES = [];
function indexPlaces(base){
  const seen = new Set();
  const add = (f, sub, outside) => {
    const key = f.properties.name + '|' + sub;
    if (!f.properties.name || seen.has(key)) return;
    seen.add(key); PLACES.push({f, name: f.properties.name, sub, outside, alt: f.properties.aka});
  };
  LAYERS.filter(it => it.kind === 'fill').forEach(it => data.layers[it.id].features.forEach(f => add(f, it.place || it.name, false)));
  if (UNITS) data.units.features.forEach(f => add(f, CITY.units.singular + (f.properties.code != null ? ' #' + f.properties.code : ''), false));
  if (data.knownas) data.knownas.features.forEach(f => add(f, 'Known-as name', false));
  base.features.filter(f => f.properties.kind === 'neighbour').forEach(f => add(f, fill(CITY.outside.regionPill, f.properties) || 'Nearby', true));
  // The counties or regions themselves: choosing one focuses on it.
  // "DuPage" or "Peel" alone is as good as the full name ("Lake" matches two, so it lists both).
  if (data.regionAreas) data.regionAreas.features.forEach(f => PLACES.push({name: regionName(f.properties.region), sub: (CITY.focus && CITY.focus.noun) || 'Region', outside: true, focus: f.properties.region, rank: 3.5, f,
    alt: [f.properties.region, regionName(f.properties.region).split(/ (?:county|region)\b/i)[0]]}));
  // Named communities in the municipalities around the city (cities/<city> builds region_places.json).
  (data.regionPlaces || []).forEach(p => PLACES.push({name: p.name, alt: p.alt, sub: fill(CITY.regionPlaces.sub, p), outside: true, muni: p.muni,
    community: (CITY.regionPlaces.near || []).includes(p.kind) ? 5 : 6,
    zoom: CITY.regionPlaces.zoom[p.kind] || 13, f: {type: 'Feature', properties: {name: p.name}, geometry: {type: 'Point', coordinates: p.at}}}));
}
function suggestions(text){
  const qq = norm(text), qs = qq.replace(/ /g, '');
  if (qq.length < 2) return [];
  // Spacing and punctuation don't count: "Yonge-St. Clair" finds "Yonge-St.Clair".
  const score = names => {
    let best = null;
    names.forEach((n, i) => {
      const nn = norm(n), ns = nn.replace(/ /g, '');
      const sc = ns === qs ? 0 : ns.startsWith(qs) ? 1 : (' ' + nn).includes(' ' + qq) ? 2 : null;
      if (sc !== null && (!best || sc < best.s)) best = {s: sc, alias: i ? n : null};
    });
    return best;
  };
  const out = [];
  (data.landmarks ? data.landmarks.features : []).forEach(f => {
    const b = score([f.properties.name].concat(f.properties.aliases || []));
    if (b) out.push({s: b.s, rank: f.properties.tier, name: f.properties.name, sub: f.properties.catLabel + (b.alias ? ' · also called ' + b.alias : ''), go: () => goLandmark(f), at: f.geometry.coordinates});
  });
  INSTITUTIONS().forEach(([it, f]) => {
    // Nicknames (U of T, UIC…) come from the layer's "aliases" in city.json.
    const p = f.properties, b = score([p.name + (p.sub && /campus|centre|site/i.test(p.sub) ? ' ' + p.sub : ''), p.name].concat((it.aliases || {})[p.name] || []));
    if (b) out.push({s: b.s, rank: 2.5, name: p.name, sub: [placeNoun(it, p.cat), p.sub].filter(Boolean).join(' · ') + (b.alias && b.alias !== p.name ? ' · also called ' + b.alias : ''), go: () => goLandmark(f)});
  });
  // Heritage buildings with a name, unless a landmark already stands on it (Robie House, Casa Loma).
  const lmAt = out.filter(o => o.at);
  hbFeatures().forEach(f => { const p = f.properties; if (!p.n) return;
    const b = score([p.n]);
    if (b && !lmAt.some(o => metres(o.at, f.geometry.coordinates) < 40)) out.push({s: b.s, rank: 3.2, name: p.n, sub: HB.place + ' · ' + p.a + (p.y ? ' · ' + p.y : ''), go: () => goTo(L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]), p.n, true)}); });
  // Skyscrapers, unless a landmark suggested for the same words stands on it (Willis Tower, the Hancock).
  const lmHits = out.filter(o => o.at);
  towerFeatures().forEach(f => {
    const p = f.properties;
    const b = score([p.name].concat(p.aka ? [p.aka] : []));
    if (b && !lmHits.some(o => metres(o.at, f.geometry.coordinates) < 20)) out.push({s: b.s, rank: p.super ? 2 : 2.8, name: p.name, sub: TOWERS.place + ' · ' + towerHeight(p, true) + (p.uc ? ' · ' + TOWERS.ucText : '') + (b.alias ? ' · also called ' + b.alias : ''), go: () => goLandmark(f)});
  });
  // Streetcar and bus routes, by number or name ("29", "Dufferin", "29 Dufferin"): choosing one draws it.
  (data.transit ? data.transit.routes : []).forEach(r => {
    const b = score([routeName(r), r.r]);
    if (b) out.push({s: b.s, rank: 2.9, name: routeName(r), sub: TR.kinds[r.m] + (r.day ? '' : ' · ' + TR.nightOnly), go: () => goRoute(r)});
  });
  PLACES.forEach(p => {
    const b = score([p.name].concat(p.alt || []));
    if (b) out.push({s: b.s, rank: p.rank || p.community || (p.outside ? 4 : 3), name: p.name, sub: p.sub + (b.alias ? ' · also called ' + b.alias : ''), go: () => goPlace(p)});
  });
  return out.sort((a, b) => a.s - b.s || a.rank - b.rank || a.name.localeCompare(b.name)).slice(0, 6);
}
function showSuggestions(list, more){
  window.__sg = list;
  showResults(list.map((x, i) => '<li><button type="button" data-sg="' + i + '">' + esc(x.name) + '<span>' + esc(x.sub) + '</span></button></li>').join('') +
    (more ? '<li class="msg">' + esc(CITY.search.more) + '</li>' : ''));
  results.querySelectorAll('[data-sg]').forEach(b => b.addEventListener('click', () => window.__sg[+b.dataset.sg].go()));
}
// Institutions for search: every feature of every places-kind layer's own category.
const INSTITUTIONS = () => LAYERS.filter(it => it.kind === 'places' && it.search !== false && loaded[it.file]).flatMap(it => loaded[it.file].features.filter(f => placeCats(it).includes(f.properties.cat)).map(f => [it, f]));
function goLandmark(f){ goTo(L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]), f.properties.name, true); }
// A named area: frame the whole of it and pin its label point. Outside the city, switch to the region view first.
function goPlace(p){
  if (p.focus){ showResults(''); q.value = p.name; setFocus(p.focus, true); return; }
  const g = p.f.geometry;
  if (g.type === 'Point'){ goTo(L.latLng(g.coordinates[1], g.coordinates[0]), p.name, true, p.zoom, p.muni); return; }
  showResults(''); q.value = p.name;
  if (p.outside && scope === 'inner') setScope('outer', false);
  const lp = p.f.properties.lp, bounds = L.geoJSON(p.f).getBounds();
  inspect(lp ? L.latLng(lp[1], lp[0]) : bounds.getCenter(), p.name);
  const opts = Object.assign(wide() ? {paddingTopLeft:[330,40], paddingBottomRight:[350,40]} : {paddingTopLeft:[20,170], paddingBottomRight:[20,110]}, {maxZoom: 15});
  const size = map.getSize(), calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  try {
    if (calm || !size.x || !size.y) map.fitBounds(bounds, Object.assign({animate: false}, opts));
    else map.flyToBounds(bounds, Object.assign({duration: .8}, opts));
  } catch (err){ try { map.fitBounds(bounds, Object.assign({animate: false}, opts)); } catch (e2){} }
}
q.addEventListener('input', () => {
  const m = suggestions(q.value);
  if (!m.length){ showResults(''); return; }
  showSuggestions(m, true);
});
q.addEventListener('keydown', e => { if (e.key === 'ArrowDown'){ const b = results.querySelector('button'); if (b){ e.preventDefault(); b.focus(); } } });
results.addEventListener('keydown', e => {
  const bs = [...results.querySelectorAll('button')], i = bs.indexOf(document.activeElement);
  if (e.key === 'ArrowDown' && i < bs.length - 1){ e.preventDefault(); bs[i + 1].focus(); }
  if (e.key === 'ArrowUp'){ e.preventDefault(); (i > 0 ? bs[i - 1] : q).focus(); }
  if (e.key === 'Escape'){ showResults(''); q.focus(); }
});

/* ---------- Scope: the wider region ("outer") or the city alone ("inner") ---------- */
let mask = null, scope = 'outer';
function frame(bounds, extra){
  // The tour's box sits at the bottom of the map: keep what it's showing above it.
  const tb = tourBox && !tourBox.hidden ? tourBox.offsetHeight + 24 : 0;
  const opts = Object.assign(wide() ? {paddingTopLeft:[330,20], paddingBottomRight:[350,Math.max(20, tb)]} : {paddingTopLeft:[0,150], paddingBottomRight:[0,Math.max(90, tb)]}, extra || {});
  const size = map.getSize(), calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (calm || !size.x || !size.y) map.fitBounds(bounds, Object.assign({animate:false}, opts));
  else map.flyToBounds(bounds, Object.assign({duration:.8}, opts));
}
function setScope(s, move){
  scope = s;
  document.querySelectorAll('[data-scope]').forEach(b => b.setAttribute('aria-checked', String(b.dataset.scope === s)));
  map.getContainer().classList.toggle('mode-inner', s === 'inner');
  if (mask) { if (s === 'inner') mask.addTo(map); else map.removeLayer(mask); }
  ORDER.forEach(it => { if (layers[it.id] && layers[it.id]._scope) layers[it.id]._scope(s); });
  drawStops();
  if (SUBURBS){
    document.getElementById('row-' + SUBURBS.id).hidden = s === 'inner';
    document.getElementById('drvbox').hidden = s === 'inner' || !state[SUBURBS.id];
    const lyr = layers[SUBURBS.id];
    if (lyr){ if (s === 'outer' && state[SUBURBS.id]) lyr.addTo(map); else map.removeLayer(lyr); }
  }
  const fb = document.getElementById('focusBox');
  if (fb) fb.hidden = s === 'inner';
  if (s === 'inner' && focusKey) setFocus(null, false);
  if (s === 'outer' && placeF) setPlaceFocus(null, null, false);
  if (move) frame(s === 'inner' ? CITY_BOUNDS : REGION_VIEW);
  queueDeclutter();
  queueHash();
}

/* ---------- Focus on one county or region (regional view) ----------
   Picking one (from the panel, search, or a spot's card) outlines it, dims everything outside it, frames
   the map on it, labels every municipality inside and lists them in the panel. Outlines come from
   region_areas.geojson (engine/regions.py); municipalities belong to the region named on them in base. */
let focusKey = null, focusLayer = null;
const regionName = k => fill(CITY.outside.regionPill, {region: k}) || k;
const regionFeature = k => k && CITY.focus && data.regionAreas ? data.regionAreas.features.find(f => f.properties.region === k) : null;
function buildFocusUI(){
  if (!CITY.focus || !data.regionAreas) return;
  const keys = data.regionAreas.features.map(f => f.properties.region).sort((a, b) => regionName(a).localeCompare(regionName(b)));
  const box = document.createElement('div'); box.className = 'focus'; box.id = 'focusBox'; box.hidden = scope !== 'outer';
  box.innerHTML = '<label for="focusSel">' + esc(CITY.focus.label) + '</label><select id="focusSel"><option value="">' + esc(CITY.focus.all) + '</option>' +
    keys.map(k => '<option value="' + esc(k) + '">' + esc(regionName(k)) + '</option>').join('') + '</select>' +
    '<div class="focus-res" id="focusRes" hidden><span id="focusCount"></span><button type="button" id="focusClear">Show all</button></div><div class="flist focus-list" id="focusList" hidden></div>';
  document.querySelector('.scope').after(box);
  box.querySelector('select').addEventListener('change', e => { setFocus(e.target.value || null, true); if (e.target.value) logEvent('region_focus'); });
  box.querySelector('#focusClear').addEventListener('click', () => setFocus(null, true));
}
function setFocus(key, move){
  const f = regionFeature(key);
  if (key && !f) return;
  if (f && scope === 'inner') setScope('outer', false);
  focusKey = f ? key : null;
  if (focusLayer){ map.removeLayer(focusLayer); focusLayer = null; }
  map.getContainer().classList.toggle('focused', !!f);
  const sel = document.getElementById('focusSel'); if (sel) sel.value = focusKey || '';
  const list = document.getElementById('focusList'), res = document.getElementById('focusRes');
  if (!f){
    if (list){ list.hidden = true; res.hidden = true; list.innerHTML = ''; }
    if (move) frame(REGION_VIEW);
    queueDeclutter(); queueHash(); return;
  }
  focusLayer = L.layerGroup();
  // Dim everything outside: a sheet over the whole map with the region cut out of it.
  const v = CITY.view.max, sheet = [[v[0][0] - 5, v[0][1] - 5], [v[0][0] - 5, v[1][1] + 5], [v[1][0] + 5, v[1][1] + 5], [v[1][0] + 5, v[0][1] - 5]];
  const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
  focusLayer.addLayer(L.polygon([sheet].concat(polys.map(p => p[0].map(ll))), {pane: 'mask', interactive: false, className: 'focus-dim'}));
  focusLayer.addLayer(L.geoJSON(f, {pane: 'focus', interactive: false, style: () => ({className: 'focus-line'})}));
  // Every municipality in it, biggest first so they win the label declutter.
  const size = g => { const b = L.geoJSON(g).getBounds(); return (b.getEast() - b.getWest()) * (b.getNorth() - b.getSouth()); };
  const towns = data.outer.features.filter(t => t.properties.region === key && !t.properties.rest);
  towns.slice().sort((a, b) => size(b) - size(a)).forEach(t => focusLayer.addLayer(label(esc(t.properties.name), 'lbl-focus', ll(t.properties.lp))));
  focusLayer.addTo(map);
  // The list in the panel: tap a name to go there.
  const sorted = towns.slice().sort((a, b) => a.properties.name.localeCompare(b.properties.name));
  document.getElementById('focusCount').textContent = fill(CITY.focus.count, {n: sorted.length, name: regionName(key)});
  list.innerHTML = '';
  sorted.forEach(t => {
    const b = document.createElement('button'); b.type = 'button';
    b.innerHTML = esc(t.properties.name) + (t.properties.drive != null ? '<span>' + t.properties.drive + ' min</span>' : '');
    b.title = t.properties.drive != null ? 'About ' + t.properties.drive + ' min to ' + CITY.drive.hubName + ' with no traffic' : '';
    b.addEventListener('click', () => {
      const p = PLACES.find(x => x.f === t);
      if (matchMedia('(max-width:760px)').matches) panel.classList.add('collapsed');
      if (p) goPlace(p);
    });
    list.appendChild(b);
  });
  list.hidden = false; res.hidden = false;
  if (move){
    frame(L.geoJSON(f).getBounds());
    // On a phone, clear the way: fold the panel (the picker stays) and close the card.
    if (matchMedia('(max-width:760px)').matches){ panel.classList.add('collapsed'); closeHere(); }
  }
  queueDeclutter(); queueHash();
}
document.querySelectorAll('[data-scope]').forEach(b => b.addEventListener('click', () => { if (b.dataset.scope !== scope){ setScope(b.dataset.scope, true); logEvent('scope', {id: b.dataset.scope}); } }));

/* ---------- Focus on one place (city view) ----------
   Tap a neighbourhood's or area's name on the map, or "Focus on" on the card, and everything outside the
   place dims. Two sheets with the place cut out do it: a strong one under the trains and routes (fills, streets,
   boundaries), a lighter one over them, so a line that passes through stays full inside and half-faded outside,
   and you can follow it to where it ends. Lines that don't pass through fade right out; points and labels
   outside fade (names of places and stations less, so you can read where a route goes). The panel lists the
   lines, main streets and landmarks in or through the place. Tap outside it, press Escape or Exit to leave.
   Kept in links as focus=<layer id>:<name>. */
var placeF = null, pfLayer = null, pfBox = null, pfMemo = new WeakMap();
const PF_KINDS = ['units', 'fill'];
const pfLayers = () => LAYERS.filter(it => PF_KINDS.includes(it.kind)).sort((a, b) => (a.kind === 'units' ? 0 : a.size === 'major' ? 2 : 1) - (b.kind === 'units' ? 0 : b.size === 'major' ? 2 : 1));
const pfFeature = (id, name) => { const fc = data.layers[id]; return fc ? fc.features.find(f => f.properties.name === name) : null; };
function placeFromLink(v){
  if (!v || !v.includes(':')) return null;
  const i = v.indexOf(':'), id = v.slice(0, i), name = v.slice(i + 1);
  return pfLayers().some(it => it.id === id) && pfFeature(id, name) ? [id, name] : null;
}
// What a place's layer calls one of its own (Neighbourhood, Former city, Side of the city).
const pfNoun = it => it.kind === 'units' ? CITY.units.singular : (it.place || it.name);
function tapToFocus(lb, id, f){
  lb.on('add', () => {
    const el = lb.getElement(); if (!el || el._pf) return;
    el._pf = true; el.classList.add('lbl-tap'); el.title = 'Focus on ' + f.properties.name;
    L.DomEvent.on(el, 'click', ev => {
      L.DomEvent.stop(ev);
      if (map.dragging && map.dragging.moved()) return;
      setPlaceFocus(id, f.properties.name, true);
      if (placeF) logEvent('focus', {layer: id, via: 'map'});
    });
  });
}
// A tap on the map: outside the focused place it only leaves focus (no card); otherwise the card as usual.
function tapMap(e){
  if (placeF && !inPlace(e.latlng.lng, e.latlng.lat)){
    if (!swallowTap){ swallowTap = true; setPlaceFocus(null, null, false); setTimeout(() => { swallowTap = false; }); }
    return;
  }
  // A tap on a shape reaches here twice (the shape, then the map): count the card once.
  const prev = lastInspect && lastInspect[0];
  inspect(e.latlng);
  if (lastInspect && lastInspect[0].equals(e.latlng) && !(prev && prev.equals(e.latlng))) logEvent('card', {via: 'tap'});
}
function inPlace(x, y){
  const b = placeF.bb;
  return x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3] && contains(placeF.f.geometry, x, y);
}
// Does a line (any coordinates: LineString or MultiLineString) pass through the place? A vertex inside, or a
// segment crossing its edge, counts; so does running along it, as a boundary street does.
function crosses(a, b, c, d){
  const o = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  return o(a, b, c) !== o(a, b, d) && o(c, d, a) !== o(c, d, b);
}
function lineMeets(geom){
  const b = placeF.bb, parts = geom.type === 'LineString' ? [geom.coordinates] : geom.type === 'MultiLineString' ? geom.coordinates : [];
  for (const c of parts) for (let i = 0; i < c.length; i++){
    const p = c[i];
    if (p[0] >= b[0] && p[0] <= b[2] && p[1] >= b[1] && p[1] <= b[3] && contains(placeF.f.geometry, p[0], p[1])) return true;
    if (!i) continue;
    const q = c[i - 1];
    if (Math.max(p[0], q[0]) < b[0] || Math.min(p[0], q[0]) > b[2] || Math.max(p[1], q[1]) < b[1] || Math.min(p[1], q[1]) > b[3]) continue;
    for (const r of placeF.rings) for (let k = 1; k < r.length; k++) if (crosses(q, p, r[k - 1], r[k])) return true;
  }
  return false;
}
// The routes (indices into transit.json) with a stop inside the place.
function placeRoutes(){
  if (!placeF.ri && data.transit){ placeF.ri = new Set(); data.transit.stops.forEach(s => { if (inPlace(s[0], s[1])) s[3].forEach(i => placeF.ri.add(i)); }); }
  return placeF.ri || new Set();
}
const featMeets = f => { if (!pfMemo.has(f)) pfMemo.set(f, lineMeets(f.geometry)); return pfMemo.get(f); };
// Sort one map layer into in / out as it joins the map.
const PF_LINE_PANES = ['rail', 'transit'], PF_PT_PANES = ['pts', 'stlbl', 'tooltipPane'];
function pfSort(l){
  if (!placeF || l === pfLayer || !l.options) return;
  const pane = l.options.pane || (l instanceof L.Tooltip ? 'tooltipPane' : l instanceof L.Marker ? 'markerPane' : 'overlayPane');
  const el = l._path || l._icon || (l.getElement && l.getElement());
  if (!el || /hover-tip/.test(l.options.className || '')) return;
  let cls = null;
  const f = l.feature || l.options.feat, picked_ = / (pick|focus)\b/.test(l.options.className || '') || (l._icon && l._icon.querySelector('.pick, .focus'));
  if (l instanceof L.Polyline && !(l instanceof L.Polygon)){
    if (!PF_LINE_PANES.includes(pane)) return;
    if (!picked_ && !(f ? featMeets(f) : lineMeets({type: 'LineString', coordinates: l.getLatLngs().flat(Infinity).map(p => [p.lng, p.lat])}))) cls = 'fz-off';
  } else if (l.getLatLng && PF_PT_PANES.includes(pane)){
    const p = l.getLatLng(); if (!p) return;
    if (f && !picked_ && !featMeets(f)) cls = 'fz-off';         // a route's number badge: hidden if the route doesn't pass through
    else if (l.options.stopOf && !picked_ && !inPlace(p.lng, p.lat) && !l.options.stopOf.some(i => placeRoutes().has(i))) cls = 'fz-off';   // a stop no route through the place serves
    else if (!inPlace(p.lng, p.lat)) cls = 'fz-out';
  } else return;
  el.classList.remove('fz-off', 'fz-out');
  if (cls) el.classList.add(cls);
}
map.on('layeradd', e => { if (placeF) pfSort(e.layer); });
function setPlaceFocus(id, name, move){
  const f = id ? pfFeature(id, name) : null;
  const same = f && placeF && placeF.id === id && placeF.name === name;
  if (pfLayer){ map.removeLayer(pfLayer); pfLayer = null; }
  map.getContainer().querySelectorAll('.fz-off, .fz-out').forEach(n => n.classList.remove('fz-off', 'fz-out'));
  placeF = null; pfMemo = new WeakMap();
  if (!f || (same && move)){
    map.getContainer().classList.remove('pfocus');
    drawPlaceBox();
    redrawCard();
    queueDeclutter(); queueHash(); return;
  }
  if (scope !== 'inner') setScope('inner', false);
  const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
  const rings = polys.flat(), xs = rings.flat().map(p => p[0]), ys = rings.flat().map(p => p[1]);
  placeF = {id, name, f, rings, bb: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)], it: LAYERS.find(it => it.id === id)};
  map.getContainer().classList.add('pfocus');
  pfLayer = L.layerGroup();
  const v = CITY.view.max, sheet = [[v[0][0] - 5, v[0][1] - 5], [v[0][0] - 5, v[1][1] + 5], [v[1][0] + 5, v[1][1] + 5], [v[1][0] + 5, v[0][1] - 5]];
  const holes = polys.map(p => p[0].map(ll));
  pfLayer.addLayer(L.polygon([sheet].concat(holes), {pane: 'pfdim', interactive: false, className: 'pf-dim'}));
  pfLayer.addLayer(L.polygon([sheet].concat(holes), {pane: 'pfdim2', interactive: false, className: 'pf-dim2'}));
  pfLayer.addLayer(L.geoJSON(f, {pane: 'pfline', interactive: false, style: () => ({className: 'pf-line'})}));
  pfLayer.addTo(map);
  map.eachLayer(pfSort);
  drawPlaceBox();
  if (move){
    frame(L.geoJSON(f).getBounds());
    // On a phone, clear the way to the map; the panel keeps a one-line reminder with Exit.
    if (!wide()){ panel.classList.add('collapsed'); closeHere(); }
  }
  redrawCard();
  queueDeclutter(); queueHash();
}
// The card's "Focus on" chips: the unit, then the areas it sits in.
function focusChips(hits){
  const ls = pfLayers().filter(it => hits[it.id]);
  if (!ls.length) return '';
  return '<div class="pfgo"><small>Focus on</small>' + ls.map(it => {
    const n = hits[it.id].properties.name, on = placeF && placeF.id === it.id && placeF.name === n;
    return '<button type="button" data-pf="' + esc(it.id + ':' + n) + '" aria-pressed="' + !!on + '" title="' + esc(pfNoun(it)) + '">' + esc(n) + (on ? ' ×' : '') + '</button>';
  }).join('') + '</div>';
}
/* The panel box: what's in or passes through the place, from the data (whichever layers are on).
   Rapid transit and trains by line; streetcars and buses with a stop inside, as chips that draw the route;
   main streets in or along it; landmarks and institutions inside. */
function drawPlaceBox(){
  if (!pfBox){
    pfBox = document.createElement('div'); pfBox.className = 'pfbox'; pfBox.id = 'pfBox'; pfBox.hidden = true;
    document.querySelector('.scope').after(pfBox);
  }
  if (!placeF){ pfBox.hidden = true; pfBox.innerHTML = ''; return; }
  const rows = [], names = a => [...new Set(a)];
  const lineRow = (it, fc, cls) => {
    if (!fc) return;
    const hitL = fc.features.filter(f => /Line/.test(f.geometry.type) && featMeets(f));
    if (hitL.length) rows.push([it.name, '<span class="pf-lines">' + names(hitL.map(f => f.properties.name)).map(n => '<span' + (cls ? ' class="' + cls + '"' : '') + '>' + esc(n) + '</span>').join('') + '</span>']);
  };
  LAYERS.filter(it => it.kind === 'metro').forEach(it => lineRow(it, loaded[[].concat(it.files)[0]]));
  LAYERS.filter(it => it.kind === 'rail').forEach(it => lineRow(it, loaded[[].concat(it.files)[0]]));
  const T = data.transit;
  if (TR && T){
    const rs = [...placeRoutes()].map(i => T.routes[i]).sort((a, b) => String(a.r).localeCompare(String(b.r), undefined, {numeric: true}));
    const chip = (r, night) => '<button type="button" class="rt-chip ' + r.m + routeCls(r, night) + '" data-route="' + esc(r.r) + '" aria-pressed="' + picked.has(r.r) + '" title="' + routeTip(r) + '">' + esc(r.r) + '</button>';
    TR.rows.forEach(([mode, label]) => { const x = rs.filter(r => r.m === mode && r.day); if (x.length) rows.push([label, '<span class="rt-chips">' + x.map(r => chip(r)).join('') + '</span>']); });
    const night = rs.filter(r => r.f.includes('night'));
    if (night.length) rows.push([TR.night, '<span class="rt-chips">' + night.map(r => chip(r, true)).join('') + '</span>']);
  }
  LAYERS.filter(it => it.kind === 'construction').forEach(it => lineRow(it, loaded[it.file], 'uc'));
  LAYERS.filter(it => it.kind === 'streets' && !it.under).forEach(it => {
    const fc = loaded[it.file]; if (!fc) return;
    const st = fc.features.filter(featMeets).sort((a, b) => a.properties.name.localeCompare(b.properties.name));
    const nm = names(st.map(f => f.properties.name)), cap = 14;
    if (nm.length) rows.push([it.name, esc(nm.slice(0, cap).join(', ')) + (nm.length > cap ? ' <span class="more">and ' + (nm.length - cap) + ' more</span>' : '')]);
  });
  // Points inside: landmarks, then each institution layer, then skyscrapers (counted, tallest named).
  const ptsIn = fc => fc ? fc.features.filter(f => f.geometry.type === 'Point' && inPlace(f.geometry.coordinates[0], f.geometry.coordinates[1])) : [];
  const btn = f => '<button type="button" data-pt="' + f.geometry.coordinates.join(',') + '" data-name="' + esc(f.properties.name) + '">' + esc(f.properties.name) + (f.properties.sub ? ' <small>' + esc(f.properties.sub) + '</small>' : '') + '</button>';
  LAYERS.filter(it => it.kind === 'landmarks').forEach(it => { const p = ptsIn(loaded[it.file]); if (p.length) rows.push([it.name, '<span class="flist">' + p.map(btn).join('') + '</span>']); });
  LAYERS.filter(it => it.kind === 'places').forEach(it => (it.cats || [[it.cat, it.name]]).forEach(([c, label]) => {   // a row per category
    const p = ptsIn(loaded[it.file]).filter(f => !c || featCats(f.properties).includes(c)); if (p.length) rows.push([label, '<span class="flist">' + p.map(btn).join('') + '</span>']); }));
  LAYERS.filter(it => it.kind === 'towers').forEach(it => {
    const p = ptsIn(loaded[it.file]).sort((a, b) => b.properties.h - a.properties.h);
    if (p.length) rows.push([it.name, p.length + (p.length > 1 ? ' · tallest ' : ' · ') + btn(p[0]).replace('<button', '<button class="inline"')]);
  });
  pfBox.hidden = false;
  pfBox.innerHTML = '<div class="pf-head"><div><small>Focused on · ' + esc(pfNoun(placeF.it)) + '</small><b>' + esc(placeF.name) + '</b></div>' +
    '<button type="button" id="pfExit">Exit focus</button></div>' +
    '<div class="pf-inv">' + (rows.length ? '<dl>' + rows.map(([k, v]) => '<dt>' + esc(k) + '</dt><dd>' + v + '</dd>').join('') + '</dl>' : '') +
    '<p>' + esc(TR && T ? 'Lines and routes that pass through, and streets in or along it. Routes have a stop inside. Tap a number to draw it.' : 'Lines that pass through, and streets in or along it.') + '</p></div>';
  pfBox.querySelector('#pfExit').onclick = () => setPlaceFocus(null, null, true);
  pfBox.querySelectorAll('[data-route]').forEach(b => b.addEventListener('click', () => { pickRoute(b.dataset.route, !picked.has(b.dataset.route)); b.setAttribute('aria-pressed', String(picked.has(b.dataset.route))); }));
  pfBox.querySelectorAll('[data-pt]').forEach(b => b.addEventListener('click', () => {
    const [x, y] = b.dataset.pt.split(',').map(Number);
    if (!wide()) panel.classList.add('collapsed');
    goTo(L.latLng(y, x), b.dataset.name, false);
  }));
}



/* ---------- Shareable links: the view lives in the address bar's #fragment ----------
   #map=zoom/lat/lng&pin=lat,lng&name=…&view=region&layers=a,b&lens=commute&hub=gct&fit=cost:lower+middle,union:30
   Anything left out means the starting setting, so old links keep working as defaults change.
   Layers are named by their short ids in city.json; renaming a layer's label doesn't break links.
   The fragment never reaches a server, and replaceState keeps the Back button clean. */
var linkReady = false, hashTimer = 0, lastHash = '';   // var: the panel's handlers can reach these before this line runs
const SHARE_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 10V2.5M5 5.2 8 2.2l3 3M4.5 7.5H3.5v6h9v-6h-1" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const enc = v => encodeURIComponent(v).replace(/%2C/g, ',').replace(/%2F/g, '/').replace(/%3A/g, ':').replace(/%2B/g, '+');
const SUBS = LAYERS.filter(it => it.sub).map(it => it.sub);
// Start keeping the address bar in step at the next touch, click, key or scroll, so a plain visit
// (or one just reset) stays a plain URL until someone actually changes something. Set after this
// event's own handlers, so the gesture that armed it doesn't count.
function armLink(){
  const ev = ['pointerdown', 'keydown', 'wheel'];
  const start = () => { ev.forEach(e => removeEventListener(e, start, true)); linkReady = true; };
  setTimeout(() => ev.forEach(e => addEventListener(e, start, true)), 1200);
}
function queueHash(){ if (typeof checkPreset === 'function') checkPreset(); if (linkReady){ clearTimeout(hashTimer); hashTimer = setTimeout(writeHash, 250); } }
function linkState(){
  const c = map.getCenter(), z = map.getZoom();
  const parts = [['map', (Math.round(z * 4) / 4) + '/' + c.lat.toFixed(5) + '/' + c.lng.toFixed(5)]];
  if (pin && !pinIsMe){ const p = pin.getLatLng(); parts.push(['pin', p.lat.toFixed(5) + ',' + p.lng.toFixed(5)]); if (pinName) parts.push(['name', pinName]); }
  if (CHG && chgStages.size < Object.keys(CHG.stages).length) parts.push(['chg', [...chgStages].join('+')]);
  if (PARK && state[PARK.id] && pkWant.size) parts.push(['park', Object.keys(PARK.amenities).filter(k => pkWant.has(k)).join('+')]);
  if (BIKE && [...bkClasses].sort().join() !== BIKE_DEFAULT.slice().sort().join()) parts.push(['bike', Object.keys(BIKE.classes).filter(k => bkClasses.has(k)).join('+')]);
  if (cmp && cmp.b){ const p = cmp.b[0]; parts.push(['pin2', p.lat.toFixed(5) + ',' + p.lng.toFixed(5)]); if (cmp.b[1]) parts.push(['name2', cmp.b[1]]); }
  if (scope === 'outer') parts.push(['view', 'region']);
  if (focusKey) parts.push(['focus', focusKey]);
  if (placeF) parts.push(['focus', placeF.id + ':' + placeF.name]);
  const on = LAYERS.filter(it => state[it.id]).map(it => it.id)
    .concat(SUBS.filter(s => document.getElementById(s.id).checked).map(s => s.id));
  const dflt = LAYERS.filter(it => it.on).map(it => it.id).concat(SUBS.filter(s => s.on).map(s => s.id));
  if (on.join() !== dflt.join()) parts.push(['layers', on.length ? on.join(',') : 'none']);
  if (lens !== FIRST_LENS || (LENSES[lens].pick && pick[lens] !== LENSES[lens].pick[0][0])) parts.push(['lens', lens + (LENSES[lens].pick ? ':' + pick[lens] : '')]);
  if (hubLens && hubLens.hub !== hubLens.hubs[0].id) parts.push(['hub', hubLens.hub]);
  const fit = FILTERS.map(f => f.max ? (filt[f.lens] ? f.lens + ':' + filt[f.lens] : '') : (filt[f.lens].size ? f.lens + ':' + [...filt[f.lens]].join('+') : '')).filter(Boolean);
  if (fit.length) parts.push(['fit', fit.join(',')]);
  const brd = BOARDS.filter(it => state[it.id] && boardPick[it.id] !== it.boards[0][0]).map(it => it.id + ':' + boardPick[it.id]);
  if (brd.length) parts.push(['board', brd.join(',')]);
  if (BUSES && state[BUSES.id] && busKey() !== (BUSES.default === 'all' ? 'all' : BUS_DEFAULT.join('+'))) parts.push(['bus', busKey()]);
  if (picked.size) parts.push(['routes', [...picked].join(',')]);
  const pgs = Object.entries(placePick).filter(([id, g]) => g !== 'all' && state[id]).map(([id, g]) => id + ':' + g);
  if (pgs.length) parts.push(['pick', pgs.join(',')]);
  const pcs = LAYERS.filter(it => it.cats && catPick[it.id] && state[it.id]).map(it => it.id + ':' + placeCats(it).filter(c => catPick[it.id].has(c)).join('+'));
  if (pcs.length) parts.push(['cats', pcs.join(',')]);
  { // party= only when the shading isn't what the layers alone would give (the highest level on, or none)
    const onP = Object.keys(PARTY).filter(x => state[x]).sort((a, b) => prank(a) - prank(b));
    if (onP.length && shade !== onP[onP.length - 1]) parts.push(['party', shade || 'none']); }
  if (presetOn && !presetCustom) parts.push(['preset', presetOn]);
  return parts.map(([k, v]) => k + '=' + enc(v)).join('&');
}
function writeHash(){
  const h = '#' + linkState();
  if (h === location.hash) return;
  lastHash = h;
  try { history.replaceState(null, '', h); } catch (e) {}
}
function readHash(h){
  const out = {};
  h.replace(/^#/, '').split('&').forEach(kv => { const i = kv.indexOf('='); if (i > 0) { try { out[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1)); } catch (e) {} } });
  return out;
}
// Put the map into the state a link describes. Unknown ids and malformed parts are skipped.
function applyHash(h){
  const o = readHash(h);
  if (!['map', 'pin', 'view', 'layers', 'lens', 'hub', 'fit', 'focus', 'board', 'bus', 'routes', 'chg', 'preset', 'pick', 'party', 'cats'].some(k => k in o)) return false;
  // Links made before layers were merged name the old one-category layers ("mosques"): each turns on the
  // merged layer with that category picked (its "replaces" map).
  const merged = {}, oldIds = {}, oldPicks = [];   // a replaces value "@group" picks that group instead
  LAYERS.forEach(it => Object.entries(it.replaces || {}).forEach(([old, c]) => { oldIds[old] = [it.id, c]; }));
  const newId = id => (oldIds[id] || [id])[0];
  // A bare preset= link (no layers of its own) sets up that view; otherwise the link wins and the view is noted.
  if (o.preset && presetById(o.preset) && !o.layers){ applyPreset(o.preset); if (!o.map && !o.pin) return true; }
  const num = s => s.split(/[,/]/).map(Number);
  // focus= is a county or region (regional view), or "layer:name" for one place in the city.
  const pfo = placeFromLink(o.focus);
  setScope(!pfo && (o.view === 'region' || regionFeature(o.focus)) ? 'outer' : 'inner', false);
  setFocus(regionFeature(o.focus) ? o.focus : null, false);
  setPlaceFocus(pfo ? pfo[0] : null, pfo ? pfo[1] : null, false);
  if (o.layers){
    const want = new Set(o.layers === 'none' ? [] : o.layers.split(','));
    [...want].forEach(id => { if (oldIds[id]){ const [nid, c] = oldIds[id]; want.add(nid); if (c[0] === '@') oldPicks.push([nid, c.slice(1)]); else (merged[nid] = merged[nid] || []).push(c); } });
    // Area fills first, then the lens: switching the lens on turns fills off, so it must come last to win.
    LAYERS.slice().sort((a, b) => (a.kind === 'lens') - (b.kind === 'lens')).forEach(it => {
      const cb = document.getElementById('lyr-' + it.id), w = want.has(it.id);
      if (cb.checked !== w){ cb.checked = w; setLayer(it.id, w); }
    });
    SUBS.forEach(s => { document.getElementById(s.id).checked = want.has(s.id); });
    syncStnNames();
  }
  if (o.layers || o.party) partyFromLink(o.party);
  (o.board || '').split(',').forEach(part => { const [id, b] = part.split(':'); if (b) setBoard(id, b); });
  if (o.bus) setBusFams(o.bus.split('+'));
  Object.keys(placePick).forEach(id => setPlacePick(id, 'all'));
  oldPicks.forEach(([id, g]) => setPlacePick(id, g));
  if (o.pick) o.pick.split(',').forEach(x => { const [id, g] = x.split(':'); if (id && g) setPlacePick(newId(id), g); });
  LAYERS.filter(it => it.cats).forEach(it => setPlaceCats(it.id, []));
  if (o.cats) o.cats.split(',').forEach(x => { const [id, cs] = x.split(':'); if (id && cs) merged[id] = cs.split('+'); });
  Object.entries(merged).forEach(([id, cs]) => setPlaceCats(id, cs));
  if (CHG){ const want = o.chg ? o.chg.split('+').filter(k => k in CHG.stages) : Object.keys(CHG.stages);
    Object.keys(CHG.stages).forEach(k => { if (want.includes(k) !== chgStages.has(k)) { if (want.includes(k)) chgStages.add(k); else chgStages.delete(k); } });
    if (!chgStages.size) Object.keys(CHG.stages).forEach(k => chgStages.add(k));
    document.querySelectorAll('[data-chg]').forEach(b => b.setAttribute('aria-pressed', String(chgStages.has(b.dataset.chg))));
    if (layers[CHG.id] && layers[CHG.id]._draw) layers[CHG.id]._draw(); }
  if (BIKE) setBikeClasses(o.bike ? o.bike.split('+') : BIKE_DEFAULT);
  if (PARK) setParkWant(o.park ? o.park.split('+') : []);
  picked.clear(); (o.routes || '').split(',').filter(Boolean).forEach(r => picked.add(r));
  if (TR && (picked.size || pickLayer.getLayers().length)) ensureRoutes().then(drawPicks);
  if (o.hub && hubLens) setHub(o.hub, false);
  const [lk, lp] = (o.lens || '').split(':');
  if (lk && LENSES[lk] && document.querySelector('[data-lens="' + lk + '"]')){ if (lp) setPick(lk, lp); setLens(lk); }
  if (o.fit){
    clearFilters();
    o.fit.split(',').forEach(part => {
      const [k, v] = part.split(':'), f = FILTERS.find(x => x.lens === k);
      if (!f || v == null || !document.querySelector('[data-f="' + k + '"]')) return;
      if (f.max){ if (f.options.some(([ov]) => +ov === +v)) filt[k] = +v; }
      else v.split('+').forEach(t => { if (f.options.some(([ov]) => String(ov) === t)) filt[k].add(t); });
    });
    applyFilter();
  }
  const m = o.map ? num(o.map) : null, ok = a => a && a.every(Number.isFinite);
  const p = o.pin ? num(o.pin) : null;
  if (ok(m) && m.length === 3) map.setView([m[1], m[2]], m[0], {animate: false});
  const p2 = o.pin2 ? num(o.pin2) : null;
  if (cmp || pinB) endCompare(1);
  if (ok(p) && p.length === 2){
    const at = L.latLng(p[0], p[1]);
    if (ok(m)) inspect(at, o.name || undefined);
    else goTo(at, o.name || '', false);
    // A shared comparison: the second place, and a view that holds both when the link gives none.
    if (ok(p2) && p2.length === 2 && lastInspect){
      cmp = {a: lastInspect.slice(), b: null};
      inspect(L.latLng(p2[0], p2[1]), o.name2 || undefined);
      if (!ok(m)) frame(L.latLngBounds([at, L.latLng(p2[0], p2[1])]).pad(.3));
    }
  } else closeHere();
  if (o.preset && presetById(o.preset)){ presetOn = o.preset; presetSig = presetState(); presetCustom = false; drawPresets(); }
  else if (o.layers && presetOn){ presetOn = null; presetCustom = false; drawPresets(); }
  if (!ok(m) && !(ok(p) && p.length === 2)) frame(placeF ? L.geoJSON(placeF.f).getBounds() : scope === 'inner' ? CITY_BOUNDS : focusKey ? L.geoJSON(regionFeature(focusKey)).getBounds() : REGION_VIEW);
  return true;
}
// Share: the phone's share sheet where there is one, otherwise copy the link.
async function share(e){
  logEvent('share', {from: e && e.currentTarget && e.currentTarget.id === 'shareView' ? 'panel' : 'card'});
  writeHash();
  const url = location.href;
  const title = document.title + (pin && pinName ? ' · ' + pinName : '');
  if (navigator.share && matchMedia('(pointer:coarse)').matches){
    try { await navigator.share({title, url}); return; } catch (err){ if (err && err.name === 'AbortError') return; }
  }
  let copied = false;
  try { await navigator.clipboard.writeText(url); copied = true; } catch (err) {}
  if (!copied){ window.prompt('Copy this link:', url); return; }
  flash('Link copied');
}
function flash(msg){
  let t = document.getElementById('toast');
  if (!t){ t = document.createElement('div'); t.id = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('on');
  clearTimeout(flash._t); flash._t = setTimeout(() => t.classList.remove('on'), 1800);
}
document.getElementById('shareView').addEventListener('click', share);
map.on('moveend', queueHash);
// A link pasted into the same tab (only the #fragment changes) re-applies without a reload.
window.addEventListener('hashchange', () => { if (location.hash !== lastHash){ linkReady = false; applyHash(location.hash); linkReady = true; } });


/* ---------- Use my location (phones) ----------
   A button in the search bar asks the phone for its position once, then pins it and opens the card there, as a
   tap on the map would. Every lookup runs in the browser: the position never leaves the phone, and it's
   kept out of shared links. A spot beyond the map's area gets a note instead. For demos and testing from
   elsewhere, ?at=lat,lng in the address pretends the phone is there (and shows the button on any device). */
const FAKE_AT = (() => { const m = /[?&]at=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/.exec(location.search); return m ? [+m[1], +m[2]] : null; })();
// The button sits in the search bar, beside Find, so it never covers the map or the card.
if ((navigator.geolocation && matchMedia('(pointer:coarse)').matches) || FAKE_AT){
  const b = document.createElement('button');
  b.type = 'button'; b.id = 'locate'; b.title = 'Use my location'; b.setAttribute('aria-label', 'Use my location');
  b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.6" fill="currentColor"/><circle cx="12" cy="12" r="7.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 1.5v3.5M12 19v3.5M1.5 12H5M19 12h3.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  b.addEventListener('click', locateMe);
  document.getElementById('go').before(b);
}
function locateMe(){
  const b = document.getElementById('locate');
  if (!b || b.classList.contains('busy')) return;
  b.classList.add('busy');
  const done = () => b.classList.remove('busy');
  const got = (lat, lng, acc) => {
    done();
    if (!FAKE_AT) logEvent('locate', {result: 'found'});   // never anything derived from the position
    const at = L.latLng(lat, lng);
    const inCity = data.footprint && hit(data.footprint, lng, lat), inRegion = inCity || (data.outer && hit(data.outer, lng, lat));
    if (!inRegion){ flash(CITY.locateOutside || 'You’re outside this map’s area. Search an address instead.'); return; }
    if (placeF && !inPlace(lng, lat)) setPlaceFocus(null, null, false);
    if (!wide()) panel.classList.add('collapsed');
    meNext = true;
    goTo(at, '', false, 15);
    if (meRing){ map.removeLayer(meRing); meRing = null; }
    if (acc > 25) meRing = L.circle(at, {radius: acc, pane: 'pin', interactive: false, className: 'me-ring'}).addTo(map);
    if (acc > 1000) flash('Your location is approximate (within about ' + dist(acc) + ')');
  };
  if (FAKE_AT){ setTimeout(() => got(FAKE_AT[0], FAKE_AT[1], 15), 300); return; }
  navigator.geolocation.getCurrentPosition(p => got(p.coords.latitude, p.coords.longitude, p.coords.accuracy || 0), err => {
    done();
    logEvent('locate', {result: err.code === 1 ? 'denied' : 'failed'});
    flash(err.code === 1 ? 'Location is off for this site. Allow it in your browser settings to use this.' : 'Couldn’t find your location. Try again, or search an address.');
  }, {enableHighAccuracy: true, timeout: 15000, maximumAge: 30000});
}


/* ---------- Save the map as an image (all in the browser) ----------
   The map is drawn from the site's own shapes, with no tiles from other sites, so html-to-image (loaded
   only when first used) can turn it into a picture. The map is briefly redrawn in a frame of the chosen
   shape (wide 4K, or square, portrait or story for Instagram) that covers what's on screen, and stamped
   with the data credits the licences ask for. Focused on a place, the frame fits the place and its name
   goes top left as a title. The panels, the pin and the controls are left out; "Without labels" also drops every name. */
const IMG_LIB = 'https://cdn.jsdelivr.net/npm/html-to-image@1.11.13/dist/html-to-image.js';
let imgLib = null;
const loadImgLib = () => imgLib || (imgLib = new Promise((res, rej) => {
  const sc = document.createElement('script'); sc.src = IMG_LIB;
  sc.onload = () => window.htmlToImage ? res(window.htmlToImage) : rej(new Error('missing'));
  sc.onerror = () => { imgLib = null; rej(new Error('load')); };
  document.head.appendChild(sc);
}));
const imgBtn = document.getElementById('saveImg'), imgMenu = document.getElementById('imgMenu');
function imgMenuOpen(on){ imgMenu.hidden = !on; imgBtn.setAttribute('aria-expanded', String(on)); if (on) loadImgLib().catch(() => {}); }
imgBtn.addEventListener('click', e => { e.stopPropagation(); imgMenuOpen(imgMenu.hidden); });
imgMenu.querySelectorAll('[data-img]').forEach(b => b.addEventListener('click', () => saveImage(b.dataset.img === 'labels')));
/* Shapes: wide for screens and slides; square, portrait (4:5) and story (9:16) for Instagram, which shows
   1080 px wide, so those are made at twice that. The choice is remembered in this browser. */
const SHAPES = {wide: [3840, 2160, ''], square: [2160, 2160, '-square'], portrait: [2160, 2700, '-portrait'], story: [2160, 3840, '-story']};
let imgShape = (() => { try { const v = localStorage.getItem('imgShape'); if (SHAPES[v]) return v; } catch (e) {} return matchMedia('(pointer:coarse)').matches ? 'portrait' : 'wide'; })();
function setShape(k){
  imgShape = k;
  try { localStorage.setItem('imgShape', k); } catch (e) {}
  imgMenu.querySelectorAll('[data-shape]').forEach(b => b.setAttribute('aria-checked', String(b.dataset.shape === k)));
  const [w, h] = SHAPES[k];
  document.getElementById('imgSize').textContent = 'Just the map, without the panels. ' + w + ' × ' + h + ' PNG' + (k === 'wide' ? ' (4K).' : ', sized for Instagram.');
}
imgMenu.querySelectorAll('[data-shape]').forEach(b => b.addEventListener('click', () => setShape(b.dataset.shape)));
setShape(imgShape);
document.addEventListener('click', e => { if (!imgMenu.hidden && !imgMenu.contains(e.target)) imgMenuOpen(false); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !imgMenu.hidden){ imgMenuOpen(false); imgBtn.focus(); } });
// html-to-image copies each SVG whole without the page's stylesheet, and the map's shapes take their
// colours from CSS classes. So, for the moment of capture, the computed look is written onto each shape.
const SVG_PROPS = ['fill', 'fill-opacity', 'fill-rule', 'stroke', 'stroke-width', 'stroke-opacity', 'stroke-dasharray',
  'stroke-linecap', 'stroke-linejoin', 'opacity', 'display', 'visibility', 'paint-order'];
function inlineSvgStyles(root){
  const saved = [];
  root.querySelectorAll('svg *').forEach(n => {
    const cs = getComputedStyle(n);
    saved.push([n, n.getAttribute('style')]);
    n.setAttribute('style', SVG_PROPS.map(k => k + ':' + cs.getPropertyValue(k)).join(';'));
  });
  return () => saved.forEach(([n, v]) => { if (v == null) n.removeAttribute('style'); else n.setAttribute('style', v); });
}
const frames = n => new Promise(r => { const step = k => k ? requestAnimationFrame(() => step(k - 1)) : r(); step(n); });
let saving = false;
async function saveImage(labels){
  if (saving) return; saving = true;
  logEvent('image', {shape: imgShape, labels: !!labels});
  imgMenuOpen(false);
  const [W, H, suffix] = SHAPES[imgShape], el = map.getContainer(), busy = document.getElementById('busy');
  const center = map.getCenter(), zoom = map.getZoom(), before = el.getAttribute('style') || '';
  // Wide: a 16:9 frame at least as big as the screen's map, so the picture shows what's on screen (and a bit more
  // on the short side). Instagram shapes: a 1080-px-wide frame drawn at twice the size, so names stay readable
  // when the post is seen on a phone.
  const cw = imgShape === 'wide' ? Math.round(Math.max(el.clientWidth, el.clientHeight * W / H)) : W / 2, ch = Math.round(cw * H / W);
  const k = cw / W;   // frame pixels per image pixel
  busy.firstElementChild.textContent = 'Making your image…'; busy.hidden = false;
  let canvas = null, restoreSvg = null;
  try {
    const lib = await loadImgLib();
    el.style.right = 'auto'; el.style.bottom = 'auto'; el.style.width = cw + 'px'; el.style.height = ch + 'px';
    map.invalidateSize({pan: false});
    // Focused on a place: fit it in the frame, clear of the title (top left) and the credits (bottom right).
    if (placeF) map.fitBounds(L.geoJSON(placeF.f).getBounds(), {animate: false, reset: true, maxZoom: 16,
      paddingTopLeft: [70 * k, (titleH(W) + 90) * k], paddingBottomRight: [70 * k, 220 * k]});
    else map.setView(center, zoom, {animate: false, reset: true});   // reset: redraw every shape for the new frame
    await new Promise(r => setTimeout(r, 400)); declutter(); await frames(2);
    const has = (n, c) => n.classList && n.classList.contains(c);
    const skip = n => has(n, 'leaflet-control-container') || has(n, 'leaflet-pin-pane') || has(n, 'hover-tip') ||
      (!labels && (has(n, 'leaflet-tooltip-pane') || has(n, 'leaflet-stlbl-pane') || has(n, 'shield') || has(n, 'rt-b') || has(n, 'sub-b') ||
        (n.tagName === 'B' && n.parentElement && has(n.parentElement, 'lm'))));
    restoreSvg = inlineSvgStyles(el);
    canvas = await lib.toCanvas(el, {width: cw, height: ch, canvasWidth: W, canvasHeight: H, pixelRatio: 1,
      backgroundColor: getComputedStyle(el).backgroundColor, filter: n => !skip(n)});
    if (placeF) stampTitle(canvas, placeF.name, pfNoun(placeF.it) + ' · ' + document.title);
    stampCredits(canvas);
  } catch (err){
    console.error(err);
  } finally {
    if (restoreSvg) restoreSvg();
    el.setAttribute('style', before);
    map.invalidateSize({pan: false}); map.setView(center, zoom, {animate: false, reset: true});   // reset: redraw every shape for the new frame
    busy.hidden = true; saving = false;
  }
  if (!canvas){ flash('The image couldn’t be made. Check your connection and try again.'); return; }
  canvas.toBlob(async blob => {
    if (!blob){ flash('The image couldn’t be made.'); return; }
    const what = placeF ? placeF.name : pin && pinName ? pinName : '';
    const name = slug(document.title) + (what ? '-' + slug(what) : '') + suffix + (labels ? '' : '-no-labels') + '.png';
    const file = new File([blob], name, {type: 'image/png'});
    if (matchMedia('(pointer:coarse)').matches && navigator.canShare && navigator.canShare({files: [file]})){
      try { await navigator.share({files: [file], title: document.title}); return; } catch (e){ if (e && e.name === 'AbortError') return; }
    }
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    flash('Image saved');
  }, 'image/png');
}
// Bottom-right: the map's name and address, then the data credits (the licences ask for them wherever the map
// goes), wrapped to fit the narrower Instagram shapes.
function stampCredits(canvas){
  const ctx = canvas.getContext('2d'), cs = getComputedStyle(document.documentElement);
  const ink = cs.getPropertyValue('--ink').trim() || '#23262B', bg = cs.getPropertyValue('--panel').trim() || '#fff';
  const font = cs.getPropertyValue('--font').trim() || 'sans-serif';
  const credit = (() => { const d = document.createElement('div'); d.innerHTML = CITY.attribution; return d.textContent.replace(/\s+/g, ' ').trim(); })();
  const title = document.title + ' · ' + location.host + location.pathname.replace(/\/$/, '');
  const pad = 22, x = canvas.width - 36, y = canvas.height - 36, maxW = Math.min(canvas.width - 200, 2600);
  ctx.font = '400 24px ' + font;
  const lines = [];
  credit.split(' ').forEach(w => { const l = lines.length ? lines[lines.length - 1] + ' ' + w : w;
    if (lines.length && ctx.measureText(l).width <= maxW) lines[lines.length - 1] = l; else lines.push(w); });
  const w2 = Math.max(...lines.map(l => ctx.measureText(l).width));
  ctx.font = '700 30px ' + font; const w1 = ctx.measureText(title).width;
  const bw = Math.max(w1, w2) + pad * 2, bh = 30 + lines.length * 31 + 11 + pad * 2;
  ctx.globalAlpha = .88; ctx.fillStyle = bg;
  ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x - bw, y - bh, bw, bh, 14); else ctx.rect(x - bw, y - bh, bw, bh); ctx.fill();
  ctx.globalAlpha = 1; ctx.fillStyle = ink; ctx.textAlign = 'right'; ctx.textBaseline = 'alphabetic';
  ctx.fillText(title, x - pad, y - bh + pad + 28);
  ctx.font = '400 24px ' + font; ctx.globalAlpha = .75;
  lines.forEach((l, i) => ctx.fillText(l, x - pad, y - pad - (lines.length - 1 - i) * 31));
  ctx.globalAlpha = 1;
}
// Top-left, when focused on a place: its name, big, and what it is, for a poster or a post.
const titleH = W => Math.round(W / 2160 * 210);
function stampTitle(canvas, name, sub){
  const ctx = canvas.getContext('2d'), cs = getComputedStyle(document.documentElement);
  const ink = cs.getPropertyValue('--ink').trim() || '#23262B', ink2 = cs.getPropertyValue('--ink-2').trim() || '#5D6168', bg = cs.getPropertyValue('--panel').trim() || '#fff';
  const font = cs.getPropertyValue('--font').trim() || 'sans-serif';
  const s = canvas.width / 2160, pad = 34 * s, x = 48 * s, y = 48 * s, maxW = canvas.width - 2 * x - 2 * pad;
  let big = 84 * s;
  ctx.font = '800 ' + big + 'px ' + font;
  while (ctx.measureText(name).width > maxW && big > 40 * s){ big -= 4 * s; ctx.font = '800 ' + big + 'px ' + font; }
  const w1 = Math.min(ctx.measureText(name).width, maxW);
  const small = 34 * s; ctx.font = '500 ' + small + 'px ' + font; const w2 = Math.min(ctx.measureText(sub).width, maxW);
  const bw = Math.max(w1, w2) + pad * 2, bh = big + small + 22 * s + pad * 2;
  ctx.globalAlpha = .92; ctx.fillStyle = bg;
  ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x, y, bw, bh, 22 * s); else ctx.rect(x, y, bw, bh); ctx.fill();
  ctx.globalAlpha = 1; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = ink; ctx.font = '800 ' + big + 'px ' + font; ctx.fillText(name, x + pad, y + pad + big * .82, maxW);
  ctx.fillStyle = ink2; ctx.font = '500 ' + small + 'px ' + font; ctx.fillText(sub, x + pad, y + pad + big + 14 * s + small * .82, maxW);
}

/* ---------- load ---------- */
renderEmpty('Loading map data…');
const files = ['base', 'regions'].concat(CITY.maskWater ? [CITY.maskWater] : []);
const REP_FILES = ((CITY.card.reps && CITY.card.reps.offices) || []).map(o => o.file).filter(Boolean);
data.repAreas = {};
// Files of layers marked "lazy" (bus route shapes) load the first time they're needed.
LAYERS.filter(it => !it.lazy).forEach(it => [].concat(it.file || it.files || []).forEach(f => { if (!files.includes(f)) files.push(f); }));
const loaded = {};
// Files of layers marked "optional" (e.g. daily closures not fetched yet) load as empty instead of failing the map.
const OPTIONAL = new Set(LAYERS.filter(it => it.optional).flatMap(it => [].concat(it.file || it.files || [])).concat(CITY.maskWater ? [CITY.maskWater] : []));
Promise.all(files.map(f => get(f).catch(e => { if (OPTIONAL.has(f)) return {type:'FeatureCollection', features:[]}; throw e; }).then(d => { loaded[f] = d; }))
  .concat([get(CITY.lens.file).then(d => { data.profiles = d; }), get(CITY.card.reps.file).then(d => { data.reps = d; }).catch(() => { data.reps = null; }),
    CITY.regionPlaces ? get(CITY.regionPlaces.file).then(d => { data.regionPlaces = d; }).catch(() => { data.regionPlaces = null; }) : null,
    CITY.card.nearby ? get(CITY.card.nearby.file).then(d => { data.nearby = d; }).catch(() => { data.nearby = null; }) : null,
    ...REP_FILES.map(f => get(f).then(d => { data.repAreas[f] = d; }).catch(() => { data.repAreas[f] = null; })),
    CITY.drive ? get('drive_grid.json').then(d => { data.driveGrid = d; }).catch(() => { data.driveGrid = null; }) : null,
    CITY.focus ? get('region_areas').then(d => { data.regionAreas = d; }).catch(() => { data.regionAreas = null; }) : null]))
.then(() => {
  const base = loaded.base, src = it => it.file ? loaded[it.file] : it.files.map(f => loaded[f]);
  LAYERS.filter(it => AREA_KINDS.includes(it.kind) || it.kind === 'boards').forEach(it => { data.layers[it.id] = loaded[it.file]; });
  Object.assign(data, {footprint: data.layers[CITY.footprint], units: UNITS && loaded[UNITS.file],
    knownas: byKind('knownas') && loaded[byKind('knownas').file], landmarks: byKind('landmarks') && loaded[byKind('landmarks').file],
    outer: {type:'FeatureCollection', features: base.features.filter(f => f.properties.kind === 'neighbour')}});
  // An annex counts as inside the city view (footprint), though no city layer covers it.
  const annex = base.features.filter(f => f.properties.kind === 'annex');
  if (annex.length && data.footprint) data.footprint = {type: 'FeatureCollection', features: data.footprint.features.concat(annex)};
  buildBase(base, loaded.regions);
  indexPlaces(base);
  buildFocusUI();
  // City-only mode: cover every other municipality and the land beyond the region (water stays visible).
  mask = L.geoJSON({type:'FeatureCollection', features: base.features.filter(f => f.properties.kind !== 'city' && f.properties.kind !== 'annex')},
    {pane:'mask', interactive:false, style: f => ({className: f.properties.water ? 'mask-water' : 'mask'})});
  // Lakes beyond the city (optional CITY.maskWater file): painted water on the mask, so layers that reach past the
  // city (districts across a region) don't show through the gaps the mask leaves for water.
  if (CITY.maskWater && loaded[CITY.maskWater]) mask.addData(loaded[CITY.maskWater]);
  // A lens with no figures in this build's data (e.g. transit times not fetched yet) is hidden, with its filter row.
  CITY.lens.lenses.filter(L_ => L_.optional).forEach(L_ => {
    if (!Object.values(data.profiles).some(d => d[L_.minutes || L_.field || L_.key] != null)) document.querySelectorAll('[data-lens="' + L_.id + '"], .frow:has([data-f="' + L_.id + '"])').forEach(e => e.remove());
  });
  ORDER.forEach(it => { layers[it.id] = KINDS[it.kind](it, it.kind === 'lens' ? [data.units, data.profiles] : it.kind === 'suburbs' ? base : src(it)); });
  drawDriveLegend();
  ORDER.forEach(it => { if (state[it.id]) layers[it.id].addTo(map); });
  syncStnNames();
  zoomClasses();
  if (!applyHash(location.hash)){
    setScope('inner', false);
    frame(CITY_BOUNDS);
    inspect(L.latLng(CITY.example.at), CITY.example.name);
  }
  lastHash = location.hash;
  if (location.hash) linkReady = true; else armLink();
  eventPresets();
  drawPresets();
  tourInvite();
  eventBanner();
  window.cityMapReady = true;
  // Stops and the route list: fetched after the map is up, then stops are drawn and the open card redrawn.
  if (TR) get(TR.file).then(d => {
    data.transit = d;
    drawStops(); drawBusBox(); if (placeF) drawPlaceBox();
    redrawCard();
  }).catch(() => { data.transit = null; });
  // Bike share stations: fetched after the map is up for the Transit nearby row (TR.bikeshare).
  if (TR && TR.bikeshare && DOCK) ensureDocks().then(d => { if (d) redrawCard(); });
  // What's changing: fetched after the map is up for the card's Changing nearby section.
  if (CC && CHG) ensureChanges().then(() => redrawCard());
  // Attendance areas are big: fetched after the map is up, then the open card is redrawn with them.
  if (CITY.card.schools) get(CITY.card.schools.file).then(d => {
    data.schools = d;
    redrawCard();
  }).catch(() => { data.schools = null; });
  // Pickup row (collection or sweeping days): fetched after the map is up, then the open card is redrawn.
  if (PU) get(PU.file).then(d => { data.pickup = d; redrawCard(); }).catch(() => { data.pickup = null; });
  // Where to vote: only fetched while the polls haven't closed.
  if (voteLive()) get(VOTE.file).then(d => {
    // A sites table (New York: one row per poll site, areas pointing at it by index): expand to the area's own
    // n/a/x/y (election day, s) and en/ea/ex/ey (its assigned early voting site, e).
    if (d.sites) d.features.forEach(f => {
      const p = f.properties, S = i => d.sites[i] || [];
      if (p.s != null){ const [n, a, x, y] = S(p.s); Object.assign(p, {n, a}, x != null ? {x, y} : {}); }
      if (p.e != null){ const [n, a, x, y] = S(p.e); Object.assign(p, {en: n, ea: a}, x != null ? {ex: x, ey: y} : {}); }
    });
    data.voting = d;
    redrawCard();
  }).catch(() => { data.voting = null; });
}).catch(err => { renderEmpty('The map data didn’t load (' + err.message + '). Reload the page to try again.'); });
})();
