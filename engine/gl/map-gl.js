/* Layers.City map engine, MapLibre GL prototype (dev only).

   Draws a city's default map on the GPU with MapLibre GL JS, from the same city.json and data/ files as the Leaflet
   engine (engine/map.js), to compare how smoothly each zooms on a phone. Only the default layers and a few toggles are
   here; the panel, card, lenses, search and the rest stay on the Leaflet map until a full port.

   Colours and line widths are not copied into this file: each style is read from the engine's own CSS (template.html
   and the city's city.css) by asking the browser to style a hidden SVG path or label with the Leaflet class names
   (resolve() below). Light and dark themes, and any city's colours, therefore come along for free, and a theme switch
   only repaints.

   Zoom: MapLibre's zoom is one less than Leaflet's for the same scale (512 px tiles), so Leaflet's "from zoom 13" is
   GL 12 here (LZ() converts). */
(() => {
const DATA = '../data/';
const LZ = z => z - 1;
const ll = p => [p[1], p[0]];
const get = f => fetch(DATA + (f.includes('.') ? f : f + '.geojson')).then(r => { if (!r.ok) throw new Error(f); return r.json(); });
const LAYERS = CITY.groups.flatMap(([, items]) => items);
const byId = id => LAYERS.find(it => it.id === id);
const byKind = k => LAYERS.find(it => it.kind === k);
const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/* ---------- styles from the engine's CSS ---------- */
const probe = document.createElement('div');
probe.className = 'gl-probe';
probe.setAttribute('aria-hidden', 'true');
probe.innerHTML = '<svg width="1" height="1"><path d="M0 0"/></svg><div class="leaflet-tooltip lbl"></div>';
document.getElementById('map').appendChild(probe);
const probePath = probe.querySelector('path'), probeLbl = probe.querySelector('div');
const cvs = document.createElement('canvas'); cvs.width = cvs.height = 1;
const cctx = cvs.getContext('2d', {willReadFrequently: true});
/* Any CSS colour (including color-mix(), which comes back as color(srgb …)) as rgba() MapLibre can read. */
function colour(v){
  if (!v || v === 'none' || v === 'transparent') return null;
  if (/^rgba?\(/.test(v)) return v;
  cctx.clearRect(0, 0, 1, 1); cctx.fillStyle = '#000'; cctx.fillStyle = v; cctx.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = cctx.getImageData(0, 0, 1, 1).data;
  return 'rgba(' + r + ',' + g + ',' + b + ',' + (a / 255).toFixed(3) + ')';
}
function path(cls){
  probePath.setAttribute('class', cls);
  const s = getComputedStyle(probePath);
  return {fill: colour(s.fill), fillOpacity: +s.fillOpacity, stroke: colour(s.stroke), strokeOpacity: +s.strokeOpacity,
    width: parseFloat(s.strokeWidth) || 0, dash: s.strokeDasharray && s.strokeDasharray !== 'none' ? s.strokeDasharray.split(/[ ,]+/).map(parseFloat) : null,
    opacity: +s.opacity};
}
function text(cls){
  probeLbl.className = 'leaflet-tooltip lbl ' + cls;
  const s = getComputedStyle(probeLbl), w = +s.fontWeight, it = s.fontStyle === 'italic';
  const face = w >= 700 ? 'Bold' : w >= 600 ? 'SemiBold' : w >= 500 ? 'Medium' : 'Regular';
  const font = 'Inter ' + (it ? (w >= 600 ? 'SemiBold' : 'Medium') + ' Italic' : face);
  const halo = (s.textShadow.match(/(rgba?\([^)]*\)|#[0-9a-f]+)/i) || [])[1];
  return {font, size: parseFloat(s.fontSize), color: colour(s.color), halo: halo ? colour(halo) : null,
    upper: s.textTransform === 'uppercase', spacing: parseFloat(s.letterSpacing) / parseFloat(s.fontSize) || 0};
}
const cssVar = n => colour(getComputedStyle(document.documentElement).getPropertyValue(n).trim());

/* ---------- map ---------- */
const CITY_BOUNDS = [ll(CITY.view.city[0]), ll(CITY.view.city[1])];
const wide = () => !matchMedia('(max-width:760px)').matches;
const map = new maplibregl.Map({
  container: 'map',
  style: {version: 8, glyphs: '/glyphs/{fontstack}/{range}.pbf', sources: {}, layers: [{id: 'water', type: 'background', paint: {'background-color': '#CFE7F7'}}]},
  bounds: CITY_BOUNDS, fitBoundsOptions: {padding: wide() ? {top: 20, bottom: 20, left: 300, right: 40} : {top: 190, bottom: 40, left: 10, right: 10}},
  minZoom: LZ(8.5), maxZoom: LZ(17), maxBounds: [ll(CITY.view.max[0]), ll(CITY.view.max[1])],
  attributionControl: {compact: true, customAttribution: CITY.attribution},
  dragRotate: false, pitchWithRotate: false, touchPitch: false,
});
map.touchZoomRotate.disableRotation();
map.addControl(new maplibregl.NavigationControl({showCompass: false}), 'bottom-right');
window.glMap = map;

/* Each style function returns {layerId: {paint/layout overrides}}; restyle() re-runs them after a theme change. */
const stylers = [];
function addLayer(def, styler){
  map.addLayer(def);
  if (styler){ stylers.push([def.id, styler]); apply(def.id, styler()); }
}
function apply(id, st){
  Object.entries(st.paint || {}).forEach(([k, v]) => map.setPaintProperty(id, k, v));
  Object.entries(st.layout || {}).forEach(([k, v]) => map.setLayoutProperty(id, k, v));
}
const dataStylers = [];   // per-feature colours baked into the data (fill slugs): re-run on theme change
function restyle(){
  map.setPaintProperty('water', 'background-color', cssVar('--water'));
  stylers.forEach(([id, f]) => apply(id, f()));
  dataStylers.forEach(f => f());
}
// A Leaflet weight that steps with zoom ([[leafletZoom, width]…], first entry from the start) as a GL expression.
const steps = (pairs, k = 1) => ['step', ['zoom'], pairs[0][1] * k, ...pairs.slice(1).flatMap(([z, w]) => [LZ(z), w * k])];
const textLayout = (t, extra) => Object.assign({'text-font': [t.font], 'text-size': t.size, 'text-letter-spacing': t.spacing, 'text-transform': t.upper ? 'uppercase' : 'none'}, extra || {});
const textPaint = t => ({'text-color': t.color, 'text-halo-color': t.halo || 'rgba(0,0,0,0)', 'text-halo-width': t.halo ? 1.6 : 0, 'text-halo-blur': .4});

/* Icons: the engine's SVG glyphs drawn into the GPU sprite (a ringed disc per landmark category). */
const GLYPH = {
  sports: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 2.2a7.8 7.8 0 0 1 7.2 4.8H4.8A7.8 7.8 0 0 1 12 4.2zM4.8 15h14.4a7.8 7.8 0 0 1-14.4 0z"/>',
  park: '<path d="M12 2 6.5 9.5h3L5 16h6v6h2v-6h6l-4.5-6.5h3z"/>',
  music: '<path d="M20 2 8 4.3v11.1A3.5 3.5 0 1 0 10 18.5V9.2l8-1.5v5.7a3.5 3.5 0 1 0 2 3.1z"/>',
  civic: '<path d="M12 1.5 2 6.5V9h20V6.5zM4 10.5v7h3v-7zm6.5 0v7h3v-7zm6.5 0v7h3v-7zM2 19v2.5h20V19z"/>',
  campus: '<path d="M12 3 1 9l11 6 9-4.9V16h2V9zM5 13.2V17l7 4 7-4v-3.8L12 17z"/>',
  culture: '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
  airport: '<path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/>',
};
const PR = Math.min(3, Math.ceil(devicePixelRatio || 1));
function loadImg(svgText){
  return new Promise(res => { const im = new Image(); im.onload = () => res(im); im.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgText); });
}
async function landmarkIcons(cats){
  const panel = cssVar('--panel');
  for (const c of cats){
    const ring = cssVar('--lm-' + c) || cssVar('--ink');
    const s = 26, svgText = '<svg xmlns="http://www.w3.org/2000/svg" width="' + s * PR + '" height="' + s * PR + '" viewBox="0 0 26 26">' +
      '<circle cx="13" cy="13" r="11.5" fill="' + panel + '" stroke="' + ring + '" stroke-width="1.6"/>' +
      '<g transform="translate(6.5 6.5) scale(.54)" fill="' + ring + '">' + (GLYPH[c] || GLYPH.culture) + '</g></svg>';
    const im = await loadImg(svgText);
    const id = 'lm-' + c;
    if (map.hasImage(id)) map.updateImage(id, im); else map.addImage(id, im, {pixelRatio: PR});
  }
}
// A highway shield: a rounded box the text stretches (icon-text-fit), in the shield's colours.
async function shieldIcon(id, bg, ring){
  const w = 20, h = 18, svgText = '<svg xmlns="http://www.w3.org/2000/svg" width="' + w * PR + '" height="' + h * PR + '" viewBox="0 0 ' + w + ' ' + h + '">' +
    '<rect x="1" y="1" width="' + (w - 2) + '" height="' + (h - 2) + '" rx="4.5" fill="' + bg + '"' + (ring ? ' stroke="' + ring + '" stroke-width="1.5"' : '') + '/></svg>';
  const im = await loadImg(svgText);
  const opts = {pixelRatio: PR, stretchX: [[6 * PR, 14 * PR]], stretchY: [[6 * PR, 12 * PR]], content: [4 * PR, 2 * PR, 16 * PR, 16 * PR]};
  if (map.hasImage(id)) map.removeImage(id);
  map.addImage(id, im, opts);
}

/* ---------- layers ---------- */
const toggles = {};   // config id -> [GL layer ids]
const own = (cfgId, ids) => { toggles[cfgId] = (toggles[cfgId] || []).concat(ids); };

function buildBase(base, regions){
  map.addSource('base', {type: 'geojson', data: base});
  const kinds = {far: 'outside', out: 'neighbour', city: 'city', annex: 'annex'};
  Object.entries(kinds).forEach(([k, kind]) => {
    const cls = 'base-' + k;
    addLayer({id: 'base-fill-' + k, type: 'fill', source: 'base', filter: ['==', ['get', 'kind'], kind]},
      () => { const s = path(cls); return {paint: {'fill-color': s.fill || 'rgba(0,0,0,0)', 'fill-opacity': s.fillOpacity}}; });
    addLayer({id: 'base-line-' + k, type: 'line', source: 'base', filter: ['==', ['get', 'kind'], kind], layout: {'line-join': 'round'}},
      () => { const s = path(cls); return {paint: {'line-color': s.stroke || 'rgba(0,0,0,0)', 'line-width': s.stroke ? s.width : 0}}; });
  });
  // Municipality labels (from Leaflet zoom 10; minor ones from 12) and region names (below 10).
  const munis = {type: 'FeatureCollection', features: base.features.filter(f => f.properties.kind === 'neighbour' && f.properties.lp)
    .map(f => ({type: 'Feature', properties: {name: f.properties.name, minor: !!f.properties.minor}, geometry: {type: 'Point', coordinates: f.properties.lp}}))};
  map.addSource('munis', {type: 'geojson', data: munis});
  map.addSource('regions', {type: 'geojson', data: regions});
  const water = {type: 'FeatureCollection', features: (CITY.water || []).map(w => ({type: 'Feature', properties: {name: w.name, cls: w.cls || '', rot: +w.rotate || 0}, geometry: {type: 'Point', coordinates: ll(w.at)}}))};
  map.addSource('waterlbl', {type: 'geojson', data: water});
}

function polyFill(it, fc, colourOf){
  const src = 'f-' + it.id;
  const bake = () => { fc.features.forEach(f => { f.properties._c = colourOf(f); }); if (map.getSource(src)) map.getSource(src).setData(fc); };
  bake(); dataStylers.push(bake);
  map.addSource(src, {type: 'geojson', data: fc});
  const major = it.size === 'major', cls = major ? 'fill-major' : 'fill-minor';
  addLayer({id: src + '-fill', type: 'fill', source: src, layout: {visibility: 'none'}}, () => ({paint: {'fill-color': ['get', '_c'], 'fill-opacity': path(cls).fillOpacity}}));
  addLayer({id: src + '-line', type: 'line', source: src, layout: {visibility: 'none'}}, () => { const s = path(cls); return {paint: {'line-color': s.stroke, 'line-width': s.width}}; });
  own(it.id, [src + '-fill', src + '-line']);
}

function outline(it, fc, cls){
  const src = 'o-' + it.id;
  map.addSource(src, {type: 'geojson', data: fc});
  addLayer({id: src, type: 'line', source: src, layout: {visibility: it.on ? 'visible' : 'none', 'line-join': 'round'}},
    () => { const s = path(cls); return {paint: {'line-color': s.stroke, 'line-width': s.width, 'line-opacity': s.strokeOpacity}}; });
  own(it.id, [src]);
}

function streets(it, fc){
  const src = 's-' + it.id;
  map.addSource(src, {type: 'geojson', data: fc});
  const W = [[0, [2, 1]], [11, [3, 1.6]], [12, [4.2, 2.6]], [13, [6, 4]], [14, [8, 5.6]]];
  const k = ['match', ['get', 'cls'], 'major', 1, 'coll', .55, .75];
  const width = i => ['step', ['zoom'], ['*', k, W[0][1][i]], ...W.slice(1).flatMap(([z, w]) => [LZ(z), ['*', k, w[i]]])];
  // Minor arterials from Leaflet zoom 12, collectors from 13 (template.html).
  const vis = ['any', ['==', ['get', 'cls'], 'major'], ['all', ['==', ['get', 'cls'], 'minor'], ['>=', ['zoom'], LZ(12)]], ['all', ['==', ['get', 'cls'], 'coll'], ['>=', ['zoom'], LZ(13)]]];
  const v = it.on ? 'visible' : 'none';
  addLayer({id: src + '-case', type: 'line', source: src, filter: vis, layout: {visibility: v, 'line-cap': 'round', 'line-join': 'round'}},
    () => ({paint: {'line-color': path('st-case').stroke, 'line-width': width(0)}}));
  addLayer({id: src + '-core', type: 'line', source: src, filter: vis, layout: {visibility: v, 'line-cap': 'round', 'line-join': 'round'}},
    () => ({paint: {'line-color': path('st-core').stroke, 'line-width': width(1)}}));
  own(it.id, [src + '-case', src + '-core']);
  return src;
}
// Street names along the line, laid out and kept apart by MapLibre's own placement (the Leaflet engine does it by hand).
function streetNames(it, src){
  const sz = it.yieldLabels ? 10 : 11.5;
  addLayer({id: src + '-name', type: 'symbol', source: src, minzoom: LZ(it.labelZoom || 12),
    filter: ['all', ['has', 'name'], ['any', ['!=', ['get', 'cls'], 'minor'], ['>=', ['zoom'], LZ(13)]]],
    layout: {visibility: it.on ? 'visible' : 'none', 'symbol-placement': 'line', 'symbol-spacing': 340, 'text-field': ['get', 'name'],
      'text-font': [it.yieldLabels ? 'Inter Medium' : 'Inter SemiBold'], 'text-size': ['match', ['get', 'cls'], 'major', 11.5, 'minor', 10.5, sz],
      'text-max-angle': 30, 'text-padding': 4, 'symbol-sort-key': ['-', 0, ['coalesce', ['get', 'len'], 0]], 'text-rotation-alignment': 'map', 'text-pitch-alignment': 'viewport'}},
    () => ({paint: {'text-color': cssVar('--ink'), 'text-halo-color': cssVar('--city'), 'text-halo-width': 1.6}}));
  own(it.id, [src + '-name']);
}

function highways(it, [fc, outer, shields]){
  map.addSource('hwy', {type: 'geojson', data: fc});
  map.addSource('hwy-out', {type: 'geojson', data: outer});
  const W = [[0, [5, 2.4]], [11, [7, 3.6]], [13, [10, 5.5]]];
  const wd = i => steps(W.map(([z, w]) => [z, w[i]]));
  const ids = [];
  [['hwy-out', 'outer', null], ['hwy', 'in', ['!', ['to-boolean', ['get', 'over']]]]].forEach(([src, tag, filter]) => {
    const f = filter ? {filter} : {};
    addLayer(Object.assign({id: src + '-case', type: 'line', source: src, layout: {'line-cap': 'round', 'line-join': 'round'}}, f),
      () => ({paint: {'line-color': path('hwy-case').stroke, 'line-width': wd(0)}}));
    addLayer(Object.assign({id: src + '-core', type: 'line', source: src, layout: {'line-cap': 'round', 'line-join': 'round'}}, f),
      () => ({paint: {'line-color': tag === 'in' ? ['match', ['get', 'kind'], 'city', path('hwy-core city').stroke, path('hwy-core').stroke] : path('hwy-core outer').stroke, 'line-width': wd(1)}}));
    ids.push(src + '-case', src + '-core');
  });
  own(it.id, ids);
  // Shields: one per city highway (more where "repeat" asks), GTA shields from the region file.
  const pts = [];
  fc.features.forEach(f => {
    const parts = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.coordinates;
    const longest = parts.reduce((a, b) => b.length > a.length ? b : a);
    ((it.repeat || {})[f.properties.route] || [.5]).forEach((t, i) => pts.push({type: 'Feature', geometry: {type: 'Point', coordinates: longest[Math.floor((longest.length - 1) * t)]},
      properties: {t: (it.shields || {})[f.properties.route] || f.properties.route, s: f.properties.kind === 'city' ? 'sh-city' : 'sh', minor: !!i}}));
  });
  shields.features.forEach(f => pts.push({type: 'Feature', geometry: f.geometry, properties: {t: f.properties.toll ? it.tollShield : f.properties.route, s: f.properties.toll ? 'sh-toll' : 'sh', outer: true}}));
  map.addSource('shields', {type: 'geojson', data: {type: 'FeatureCollection', features: pts}});
  addLayer({id: 'shields', type: 'symbol', source: 'shields', minzoom: LZ(10) - .5,
    filter: ['any', ['!', ['get', 'minor']], ['>=', ['zoom'], LZ(12)]],
    layout: {'icon-image': ['get', 's'], 'icon-text-fit': 'both', 'text-field': ['get', 't'], 'text-font': ['Inter Bold'], 'text-size': 11, 'symbol-sort-key': 1, 'text-padding': 2}},
    () => ({paint: {'text-color': ['match', ['get', 's'], 'sh', cssVar('--shield-ink'), '#ffffff']}}));
  own(it.id, ['shields']);
}

function rail(it, [lines, stns, inner]){
  map.addSource('rail', {type: 'geojson', data: inner || lines});
  const gap = ['step', ['zoom'], 0, LZ(11), 2, LZ(12), 3, LZ(13), 4];
  addLayer({id: 'rail', type: 'line', source: 'rail', layout: {'line-cap': 'round', 'line-join': 'round'},
    paint: {'line-color': ['get', 'color'], 'line-width': steps([[0, 2.2], [11, 3], [13, 3.5]]),
      'line-offset': ['step', ['zoom'], 0, LZ(11), ['*', ['get', 'offset'], 2], LZ(12), ['*', ['get', 'offset'], 3], LZ(13), ['*', ['get', 'offset'], 4]]}});
  const ends = lines.features.map(f => f.geometry.coordinates[f.geometry.coordinates.length - 1]);
  stns.features.forEach(f => { const c = f.geometry.coordinates; f.properties.end = ends.some(e => Math.abs(e[0] - c[0]) < .01 && Math.abs(e[1] - c[1]) < .008); });
  map.addSource('go-stn', {type: 'geojson', data: stns});
  // Ends and hubs always; the rest from Leaflet zoom 12 (template.html).
  const vis = ['any', ['get', 'hub'], ['get', 'end'], ['>=', ['zoom'], LZ(12)]];
  addLayer({id: 'go-stn', type: 'circle', source: 'go-stn', filter: vis,
    paint: {'circle-radius': ['case', ['get', 'hub'], 6, ['get', 'end'], 4.5, 3.5]}},
    () => { const s = path('go-stn'); return {paint: {'circle-color': s.fill, 'circle-stroke-color': s.stroke, 'circle-stroke-width': ['case', ['get', 'hub'], 2.6, s.width]}}; });
  addLayer({id: 'go-stn-name', type: 'symbol', source: 'go-stn', filter: vis,
    layout: {'text-field': ['get', 'name'], 'text-anchor': 'left', 'text-offset': [.7, 0], 'symbol-sort-key': ['case', ['any', ['get', 'end'], ['get', 'hub']], 3, 6]}},
    () => { const t = text('lbl-go'); return {layout: textLayout(t), paint: textPaint(t)}; });
  own(it.id, ['rail', 'go-stn', 'go-stn-name']);
}

function metro(it, [lines, stns]){
  const colours = () => { lines.features.forEach(f => { f.properties._c = path('sub-line l' + f.properties.line).stroke || f.properties.color; }); };
  colours();
  map.addSource('metro', {type: 'geojson', data: lines});
  dataStylers.push(() => { colours(); map.getSource('metro').setData(lines); });
  addLayer({id: 'metro', type: 'line', source: 'metro', layout: {'line-cap': 'round', 'line-join': 'round'},
    paint: {'line-color': ['get', '_c'], 'line-width': steps([[0, 3], [11, 4.5], [13, 6]])}});
  stns.features.forEach(f => { f.properties.x = f.properties.lines.length > 1; });
  map.addSource('stn', {type: 'geojson', data: stns});
  addLayer({id: 'stn', type: 'circle', source: 'stn', minzoom: LZ(13),
    paint: {'circle-radius': ['case', ['any', ['get', 'x'], ['get', 'terminus']], 5, 3.5]}},
    () => { const s = path('stn'); return {paint: {'circle-color': s.fill, 'circle-stroke-color': s.stroke, 'circle-stroke-width': ['case', ['get', 'terminus'], 2.6, ['get', 'x'], 2.2, s.width]}}; });
  addLayer({id: 'stn-name', type: 'symbol', source: 'stn', minzoom: LZ(13),
    layout: {'text-field': ['get', 'name'], 'text-anchor': 'left', 'text-offset': [.7, 0], 'symbol-sort-key': ['case', ['get', 'terminus'], 2, 5]}},
    () => { const t = text('lbl-stn'); return {layout: textLayout(t), paint: textPaint(t)}; });
  own(it.id, ['metro', 'stn', 'stn-name']);
}

function landmarks(it, fc){
  map.addSource('lm', {type: 'geojson', data: fc});
  // Tier 1 from Leaflet zoom 11 (names from 13), tier 2 from 13 (names from 14).
  addLayer({id: 'lm', type: 'symbol', source: 'lm', filter: ['any', ['==', ['get', 'tier'], 1], ['>=', ['zoom'], LZ(13)]],
    layout: {'icon-image': ['concat', 'lm-', ['get', 'cat']], 'icon-allow-overlap': false, 'symbol-sort-key': ['get', 'tier'],
      'text-field': ['step', ['zoom'], '', LZ(13), ['case', ['==', ['get', 'tier'], 1], ['get', 'name'], ''], LZ(14), ['get', 'name']],
      'text-font': ['Inter Bold'], 'text-size': 11.5, 'text-anchor': 'left', 'text-offset': [1.2, 0], 'text-optional': true}, minzoom: LZ(11)},
    () => ({paint: {'text-color': cssVar('--ink'), 'text-halo-color': cssVar('--city'), 'text-halo-width': 1.8}}));
  own(it.id, ['lm']);
}

function labels(units){
  // Neighbourhood names (Leaflet zoom 13+), at each unit's label point.
  const pts = {type: 'FeatureCollection', features: units.features.filter(f => f.properties.lp).map(f => ({type: 'Feature', properties: {name: f.properties.name}, geometry: {type: 'Point', coordinates: f.properties.lp}}))};
  map.addSource('nbhd-lbl', {type: 'geojson', data: pts});
  addLayer({id: 'nbhd-lbl', type: 'symbol', source: 'nbhd-lbl', minzoom: LZ(13),
    layout: {'text-field': ['get', 'name'], 'text-max-width': 9, 'symbol-sort-key': 20, 'text-line-height': 1.15}},
    () => { const t = text('lbl-nbhd'); return {layout: textLayout(t), paint: textPaint(t)}; });
  own(UNITS.id, ['nbhd-lbl']);
  addLayer({id: 'muni-lbl', type: 'symbol', source: 'munis', minzoom: LZ(10), filter: ['any', ['!', ['get', 'minor']], ['>=', ['zoom'], LZ(12)]],
    layout: {'text-field': ['get', 'name'], 'symbol-sort-key': 30}},
    () => { const t = text('lbl-muni'); return {layout: textLayout(t), paint: textPaint(t)}; });
  // Region names belong to the regional view (Leaflet hides them in the city view, .mode-inner).
  addLayer({id: 'region-lbl', type: 'symbol', source: 'regions', maxzoom: LZ(10), layout: {visibility: 'none', 'text-field': ['get', 'name'], 'symbol-sort-key': 30}},
    () => { const t = text('lbl-region'); return {layout: textLayout(t), paint: textPaint(t)}; });
  addLayer({id: 'water-lbl', type: 'symbol', source: 'waterlbl',
    filter: ['any', ['all', ['==', ['get', 'cls'], 'lake-near'], ['>=', ['zoom'], LZ(10)]], ['all', ['==', ['get', 'cls'], 'lake-far'], ['<', ['zoom'], LZ(10)]], ['!', ['in', ['get', 'cls'], ['literal', ['lake-near', 'lake-far']]]]],
    layout: {'text-field': ['get', 'name'], 'text-rotate': ['get', 'rot'], 'symbol-sort-key': 40, 'text-allow-overlap': true}},
    () => { const t = text('lbl-lake'); return {layout: textLayout(t), paint: {'text-color': t.color}}; });
}

/* ---------- panel ---------- */
const PANEL_IDS = ['nbhd', 'landmarks', 'subway', 'go', 'hwy', 'streets', 'coll', 'boroughs', 'areas', 'wards', 'fed'];
function panel(){
  const box = document.getElementById('gl-layers');
  LAYERS.filter(it => toggles[it.id] && (PANEL_IDS.includes(it.id) || it.kind === 'units')).forEach(it => {
    const row = document.createElement('label');
    row.innerHTML = '<input type="checkbox"' + (it.on ? ' checked' : '') + '> ' + it.name;
    row.querySelector('input').addEventListener('change', e => toggles[it.id].forEach(id => map.setLayoutProperty(id, 'visibility', e.target.checked ? 'visible' : 'none')));
    box.appendChild(row);
  });
}

/* "What's here", reduced to the neighbourhood's name: point-in-polygon on the loaded units. */
function inRing(x, y, r){ let ins = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++){ const xi = r[i][0], yi = r[i][1], xj = r[j][0], yj = r[j][1]; if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) ins = !ins; } return ins; }
const inPoly = (x, y, c) => inRing(x, y, c[0]) && !c.slice(1).some(h => inRing(x, y, h));
const contains = (g, x, y) => g.type === 'Polygon' ? inPoly(x, y, g.coordinates) : g.type === 'MultiPolygon' ? g.coordinates.some(c => inPoly(x, y, c)) : false;
let pin = null;

/* ---------- load ---------- */
const UNITS = byKind('units');
const want = ['base', 'regions', UNITS.file, 'neighbourhoods'];
const need = ['subway', 'go', 'hwy', 'streets', 'coll', 'landmarks', 'boroughs', 'areas', 'wards', 'fed'].map(byId).filter(Boolean);
need.forEach(it => [].concat(it.file || it.files || []).forEach(f => { if (!want.includes(f)) want.push(f); }));
const loaded = {};
const ready = new Promise(r => map.on('load', r));
Promise.all(want.map(f => get(f).then(d => { loaded[f] = d; }).catch(() => { loaded[f] = null; }))).then(() => ready).then(async () => {
  map.setPaintProperty('water', 'background-color', cssVar('--water'));
  const src = it => it.file ? loaded[it.file] : it.files.map(f => loaded[f]);
  buildBase(loaded.base, loaded.regions);
  // Order follows the Leaflet panes: fills, streets, neighbourhood lines, civic, highways, rail, mask, transit, points, labels.
  [byId('boroughs'), byId('areas')].filter(Boolean).forEach(it => {
    const cls = it.size === 'major' ? 'fill-major ' : 'fill-minor ';
    polyFill(it, src(it), f => path(cls + slug(f.properties.name)).fill);
  });
  const coll = byId('coll'), st = byId('streets');
  const collSrc = coll && streets(coll, src(coll)), stSrc = st && streets(st, src(st));
  outline(UNITS, src(UNITS), 'nbhd');
  [['wards', 'ward'], ['prov', 'prov'], ['fed', 'fed']].forEach(([id, cls]) => { const it = byId(id); if (it && src(it)) outline(Object.assign({}, it, {on: false}), src(it), cls); });
  const hw = byId('hwy'); if (hw) highways(hw, src(hw));
  const go = byId('go'); if (go) rail(go, src(go));
  // City-only view: cover every other municipality and the land beyond the region.
  map.addSource('mask', {type: 'geojson', data: {type: 'FeatureCollection', features: loaded.base.features.filter(f => f.properties.kind !== 'city' && f.properties.kind !== 'annex')}});
  addLayer({id: 'mask', type: 'fill', source: 'mask'}, () => { const m = path('mask'), w = path('mask-water');
    return {paint: {'fill-color': ['case', ['to-boolean', ['get', 'water']], w.fill, m.fill], 'fill-opacity': ['case', ['to-boolean', ['get', 'water']], w.fillOpacity, m.fillOpacity]}}; });
  addLayer({id: 'mask-line', type: 'line', source: 'mask'}, () => ({paint: {'line-color': path('mask').stroke, 'line-width': 1}}));
  const sub = byId('subway'); if (sub) metro(sub, src(sub));
  const lm = byId('landmarks');
  if (lm){ await landmarkIcons([...new Set(src(lm).features.map(f => f.properties.cat))]); landmarks(lm, src(lm)); }
  await shieldIcon('sh', cssVar('--shield')); await shieldIcon('sh-city', cssVar('--shield-city'), '#fff'); await shieldIcon('sh-toll', cssVar('--shield-toll'), '#fff');
  // The mask hides region highways in the city view (Leaflet hides the outer ones by CSS).
  map.setLayoutProperty('hwy-out-case', 'visibility', 'none'); map.setLayoutProperty('hwy-out-core', 'visibility', 'none');
  map.setFilter('shields', ['all', ['!', ['to-boolean', ['get', 'outer']]], ['any', ['!', ['get', 'minor']], ['>=', ['zoom'], LZ(12)]]]);
  labels(src(UNITS));
  if (stSrc) streetNames(st, stSrc);
  if (collSrc) streetNames(coll, collSrc);
  // Label priority: MapLibre places the topmost layer's labels first, so stack them as the Leaflet engine's
  // declutter ranks them (LABEL_PRIORITY in map.js): street names yield to everything, landmarks win.
  ['s-coll-name', 's-streets-name', 'nbhd-lbl', 'muni-lbl', 'water-lbl', 'go-stn', 'go-stn-name', 'stn', 'stn-name', 'shields', 'lm']
    .filter(id => map.getLayer(id)).forEach(id => map.moveLayer(id));
  panel();
  // Tap: drop a pin and name the neighbourhood.
  map.on('click', e => {
    const {lng, lat} = e.lngLat, f = src(UNITS).features.find(f => contains(f.geometry, lng, lat));
    const el = document.getElementById('gl-here');
    el.textContent = f ? f.properties.name : 'Outside ' + CITY.heading;
    el.hidden = false;
    if (!pin){ const d = document.createElement('span'); d.className = 'pin'; pin = new maplibregl.Marker({element: d}); }
    pin.setLngLat(e.lngLat).addTo(map);
  });
  // Attribution starts folded on phones (the "i" opens it), as Leaflet's line is short.
  document.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show');
  window.glReady = true;
});

/* Theme: follow the saved choice or the system, and repaint on change. */
const mq = matchMedia('(prefers-color-scheme: dark)');
mq.addEventListener('change', () => { if (window.glReady) restyle(); });
document.getElementById('gl-theme').addEventListener('click', () => {
  const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' : mq.matches;
  document.documentElement.dataset.theme = dark ? 'light' : 'dark';
  try { localStorage.setItem('theme', document.documentElement.dataset.theme); } catch (e) {}
  if (window.glReady) restyle();
});
})();
