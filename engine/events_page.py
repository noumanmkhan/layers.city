"""Events page: everything on a city's events listing for the next 30 days, at /<city>/events/.

Usage:  python3 engine/events_page.py <city>        (by hand, after the page's words or chrome change)
Reads:  cities/<city>/events_page.json             the page's words and its listing's file name
        docs/<city>/data/city.json, neighbourhoods.geojson   the city's name, locale and outline (for the card image)
Writes: docs/<city>/events/index.html, card.png

The listing itself (docs/<city>/events/<file>, Toronto: fetch_happening.py, daily) is read by the page in the
browser, so the page never goes stale between builds: sections are worked out from the visitor's clock in the
city's time zone. Today, then this weekend, then the next seven days, then the rest of the window. Filters
(free only, category, neighbourhood) live in the address (?free=1&cat=…&hood=…) so a filtered view can be
bookmarked. "Near me" asks the browser for a position once and sorts by straight-line distance; the position
is kept in a variable on the page only: never stored, sent, put in the address or counted.

The rules are the venues pages': facts only. An event is a title, its times, its place and a link to its own
page at the source; no descriptions, images or prices.
Needs: pip install pillow fonttools brotli
"""
import html, io, json, math, os, sys
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont
from theme import SCRIPT as THEME_SCRIPT, css as theme_css

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DOCS = os.path.join(ROOT, 'docs')
SITE = 'https://layers.city'
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: events_page.py <city>')
D = os.path.join(DOCS, city, 'data')
OUT = os.path.join(DOCS, city, 'events')
cfg = json.load(open(os.path.join(D, 'city.json')))
P = json.load(open(os.path.join(ROOT, 'cities', city, 'events_page.json')))
W = P['words']
CITY = cfg.get('heading') or cfg['title'].split(' · ')[0]
CA = cfg.get('search', {}).get('country') == 'ca'
BRAND = '-ca' if CA else ''
INDEX = f'{SITE}/{city}/events/'
esc = lambda s: html.escape(str(s), quote=True)


# ---- the card image: the city's outline and the page's name, as the venues card ------------------------------
def font(weight, size):
    f = TTFont(os.path.join(DOCS, 'fonts', f'archivo-latin-{weight}-normal.woff2')); f.flavor = None
    b = io.BytesIO(); f.save(b); b.seek(0)
    return ImageFont.truetype(b, size)


def card_image(path):
    RED, INK, INK2, PAPER, LAND, EDGE = '#C8102E', '#1A1414', '#5C5251', '#FBF6F5', '#EDE4E2', '#D6C9C6'
    rings = []
    for f in json.load(open(os.path.join(D, 'neighbourhoods.geojson')))['features']:
        g = f['geometry']
        rings += [p[0] for p in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']])]
    xs = [c[0] for r in rings for c in r]; ys = [c[1] for r in rings for c in r]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    kx = math.cos(math.radians((miny + maxy) / 2))
    box = (660, 40, 1160, 590)
    sc = min((box[2] - box[0]) / ((maxx - minx) * kx), (box[3] - box[1]) / (maxy - miny))
    ox = box[0] + ((box[2] - box[0]) - (maxx - minx) * kx * sc) / 2
    oy = box[1] + ((box[3] - box[1]) - (maxy - miny) * sc) / 2
    S = 2
    im = Image.new('RGB', (1200 * S, 630 * S), PAPER); d = ImageDraw.Draw(im)
    for r in rings:
        d.polygon([((ox + (x - minx) * kx * sc) * S, (oy + (maxy - y) * sc) * S) for x, y in r], fill=LAND, outline=EDGE, width=S)
    im = im.resize((1200, 630), Image.LANCZOS); d = ImageDraw.Draw(im)
    brand, big, sub = font(800, 34), font(800, 72), font(700, 34)
    d.text((72, 64), 'Layers', font=brand, fill=INK)
    d.text((72 + d.textlength('Layers', font=brand), 64), '.City', font=brand, fill=RED)
    words, lines = W['title'].split(), ['']
    for w in words:
        t = (lines[-1] + ' ' + w).strip()
        if d.textlength(t, font=big) <= 540 or not lines[-1]: lines[-1] = t
        else: lines.append(w)
    y = 315 - len(lines) * 72 * 1.08 / 2
    for ln in lines:
        d.text((72, y), ln, font=big, fill=INK); y += 72 * 1.08
    d.text((72, y + 18), W['card'], font=sub, fill=INK2)
    im.convert('P', palette=Image.ADAPTIVE, colors=48).save(path, optimize=True)


# ---- page chrome, in the venues pages' style (engine/venues.py) -------------------------------------------------
CSS = """@font-face{font-family:'Archivo';font-weight:800;font-display:swap;src:url(/fonts/archivo-latin-800-normal.woff2) format('woff2')}
@font-face{font-family:'Archivo';font-weight:700;font-display:swap;src:url(/fonts/archivo-latin-700-normal.woff2) format('woff2')}
@font-face{font-family:'IBM Plex Sans';font-weight:400;font-display:swap;src:url(/fonts/ibm-plex-sans-latin-400-normal.woff2) format('woff2')}
@font-face{font-family:'IBM Plex Sans';font-weight:500;font-display:swap;src:url(/fonts/ibm-plex-sans-latin-500-normal.woff2) format('woff2')}
:root{--bg:#F7F4F3;--card:#FFFFFF;--ink:#1A1414;--ink-2:#463D3C;--ink-3:#5C5251;--muted:#7A6E6C;--rule:#D8CFCD;--accent:#C8102E;--soft:rgba(200,16,46,.08);
--go:#1E6B47;--display:'Archivo',system-ui,sans-serif;--body:'IBM Plex Sans',system-ui,sans-serif}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);font-size:17px;line-height:1.55}
a{color:var(--accent)}
.wrap{max-width:860px;margin:0 auto;padding:0 20px}
header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:22px 0}
.brand{display:flex;align-items:center;gap:10px;color:var(--ink);text-decoration:none;font-family:var(--display);font-weight:800;font-size:20px}
.brand b{color:var(--accent);font-weight:700}.brand svg{width:26px;height:auto}
.crumbs{font-size:14px;color:var(--ink-3)}.crumbs a{color:var(--ink-2)}
h1{font-family:var(--display);font-weight:800;font-size:clamp(34px,6.5vw,56px);line-height:1.02;letter-spacing:-.02em;margin:22px 0 10px}
.kind{margin:0;color:var(--ink-2);font-size:18px}
.stamp{font-size:14px;color:var(--ink-3);margin:8px 0 0}
.brand:focus-visible,button:focus-visible,select:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid var(--ink);outline-offset:3px}
section{background:var(--card);border:1.5px solid var(--rule);border-radius:14px;padding:22px 24px;margin:20px 0}
h2{font-family:var(--display);font-weight:700;font-size:22px;margin:0 0 4px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
h2 .n{font-family:var(--body);font-weight:400;font-size:15px;color:var(--ink-3)}
.days{margin:0 0 8px;font-size:14px;color:var(--ink-3)}
ul.events{list-style:none;margin:0;padding:0}
ul.events li{display:flex;flex-wrap:wrap;gap:2px 14px;align-items:baseline;padding:11px 0;border-top:1px solid var(--rule)}
ul.events li:first-child{border-top:0}
ul.events time{flex:0 0 150px;color:var(--ink-2);font-size:15px}ul.events time b{display:block;color:var(--ink);font-weight:500}
ul.events .ev{flex:1 1 300px;min-width:0}
ul.events .t{font-weight:500;color:var(--ink);text-decoration:none}ul.events .t:hover{color:var(--accent);text-decoration:underline}
ul.events .where{display:block;color:var(--ink-3);font-size:15px}
ul.events .more{display:block;color:var(--ink-3);font-size:14px}
ul.events .acts{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center;margin-top:3px;font-size:14px}
.tag{display:inline-block;padding:1px 9px;border-radius:999px;font-size:13px;background:var(--soft);color:var(--ink)}
.tag.free{background:var(--go);color:#fff;font-weight:500}
.maplink{display:inline-flex;align-items:center;gap:4px;color:var(--accent);text-decoration:none}.maplink:hover{text-decoration:underline}.maplink svg{width:11px;height:14px}
.away{color:var(--ink-2);font-weight:500}.src{color:var(--ink-3)}
.empty{color:var(--ink-3);margin:6px 0 0}
.showall{font:inherit;font-size:15px;margin:12px 0 0;min-height:40px;padding:0 16px;border-radius:999px;border:1.5px solid var(--rule);background:var(--card);color:var(--ink);cursor:pointer}
.controls{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin:22px 0 6px;font-size:15px}
.controls label{display:inline-flex;align-items:center;gap:8px;color:var(--ink-2)}
.controls select{font:inherit;min-height:40px;max-width:100%;padding:6px 10px;border:1.5px solid var(--rule);border-radius:8px;background:var(--card);color:var(--ink)}
.controls .check input{width:18px;height:18px;margin:0;accent-color:var(--accent)}
.near{display:inline-flex;align-items:center;gap:8px;font:500 15px/1 var(--body);min-height:40px;padding:0 16px 0 13px;border-radius:999px;border:0;background:var(--accent);color:#fff;cursor:pointer}
.near svg{width:14px;height:17px}.near[aria-pressed="true"]{background:var(--ink);color:var(--bg)}
.reset{font:inherit;font-size:15px;background:none;border:0;padding:0;color:var(--accent);text-decoration:underline;cursor:pointer}
.status{font-size:14px;color:var(--ink-3);margin:4px 0 0;min-height:1.5em}
footer{padding:28px 0 40px;font-size:14px;color:var(--ink-3)}footer a{color:var(--ink-2)}
[hidden]{display:none!important}
@media (max-width:560px){section{padding:16px}ul.events time{flex-basis:100%}ul.events time b{display:inline;margin-right:6px}h1{margin-top:12px}.controls label:not(.check){flex:1 1 100%;min-width:0}.controls select{flex:1;min-width:0;width:100%}}"""
CSS += theme_css(['.tag.free{color:#0E1A14}'])
PIN = ('<svg viewBox="18 6 84 108" aria-hidden="true"><path d="M60 112 C60 112 22 74 22 48 A38 38 0 0 1 98 48 C98 74 60 112 60 112 Z" fill="#C8102E"/>'
       '<polygon points="60,52 84,63 60,74 36,63" fill="#fff" fill-opacity=".42"/><polygon points="60,39 84,50 60,61 36,50" fill="#fff" fill-opacity=".72"/>'
       '<polygon points="60,20 90,34 60,48 30,34" fill="#fff"/>%s</svg>')
PIN %= ('<path transform="translate(51,24.5) scale(0.9)" d="M10 0 L11.6 3.2 L13.2 2.4 L12.6 6.6 L15.2 4.2 L15.8 5.8 '
        'L18.4 5.2 L17.4 8.2 L19.2 9.2 L14.6 12.8 L15.2 14.6 L10.6 14 L10.8 18.6 L9.2 18.6 L9.4 14 L4.8 14.6 L5.4 12.8 '
        'L0.8 9.2 L2.6 8.2 L1.6 5.2 L4.2 5.8 L4.8 4.2 L7.4 6.6 L6.8 2.4 L8.4 3.2 Z" fill="#C8102E"/>' if CA else '')
SMALL_PIN = ('<svg viewBox="18 6 84 108" aria-hidden="true"><path d="M60 112 C60 112 22 74 22 48 A38 38 0 0 1 98 48 C98 74 60 112 60 112 Z" '
             'fill="currentColor"/><circle cx="60" cy="48" r="14" fill="var(--card)"/></svg>')
NEAR_PIN = SMALL_PIN.replace('var(--card)', 'var(--accent)')

# What the script needs, as data: the listing, the map's address, and the words.
JS_CFG = {'file': P['file'], 'map': f'/{city}/', 'locale': cfg.get('locale', 'en-CA'), 'placeless': W['placeless'],
          'unit': 'mi' if cfg.get('units') == 'imperial' else 'km', 'pin': SMALL_PIN, 'srcs': W.get('sources', {})}

SCRIPT = """<script>
(()=>{const C=__CFG__,$=id=>document.getElementById(id),esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]);
const freeEl=$('free'),catEl=$('cat'),hoodEl=$('hood'),nearEl=$('near'),statusEl=$('status'),out=$('sections');
let D=null,me=null;const shown={};   // me: the visitor's position, kept here only, never stored or sent
// City-time clock: "YYYY-MM-DDTHH:MM".
const cityNow=tz=>new Date().toLocaleString('sv-SE',{timeZone:tz}).replace(' ','T').slice(0,16);
const dayAdd=(d,n)=>{const t=new Date(Date.UTC(+d.slice(0,4),+d.slice(5,7)-1,+d.slice(8,10)+n));return t.toISOString().slice(0,10)};
const wd=d=>new Date(Date.UTC(+d.slice(0,4),+d.slice(5,7)-1,+d.slice(8,10))).getUTCDay();
const dateFmt=(d,o)=>new Date(Date.UTC(+d.slice(0,4),+d.slice(5,7)-1,+d.slice(8,10),12)).toLocaleDateString(C.locale,Object.assign({timeZone:'UTC'},o));
const clock=s=>new Date(2000,0,1,+s.slice(11,13),+s.slice(14,16)).toLocaleTimeString(C.locale,{hour:'numeric',minute:s.slice(14,16)==='00'?undefined:'2-digit'});
// An occurrence that hasn't ended: all day from today on; timed with an end after now, or started under two hours ago.
function live(t,now){const[s,e]=t;if(s.length===10)return s>=now.slice(0,10);if(e)return e>now;
  const d=new Date(+s.slice(0,4),+s.slice(5,7)-1,+s.slice(8,10),+s.slice(11,13)+2,+s.slice(14,16));return d.toLocaleString('sv-SE').replace(' ','T').slice(0,16)>now}
function km(a,b){const r=Math.PI/180,x=(b[1]-a[1])*r*Math.cos((a[0]+b[0])/2*r),y=(b[0]-a[0])*r;return Math.sqrt(x*x+y*y)*6371}
function away(k){if(C.unit==='mi'){const m=k/1.609344;return(m<.1?'under 0.1':m<10?m.toFixed(1):Math.round(m))+' mi away'}
  return k<1?Math.max(100,Math.round(k*10)*100)+' m away':(k<10?k.toFixed(1):Math.round(k))+' km away'}
function sections(now){const today=now.slice(0,10),wk=[],end=D.to;
  for(let i=1;i<=6;i++){const d=dayAdd(today,i);if(wd(d)===6||wd(d)===0)wk.push(d)}
  if(wd(today)===6)wk.splice(0,wk.length,dayAdd(today,1));         // Saturday: the weekend's other day
  const next=[];for(let i=1;i<=7;i++){const d=dayAdd(today,i);if(!wk.includes(d))next.push(d)}
  const later=[];for(let d=dayAdd(today,8);d<=end;d=dayAdd(d,1))later.push(d);
  return[{id:'today',title:'Today',days:[today]},{id:'weekend',title:'This weekend',days:wk},{id:'week',title:'Next 7 days',days:next},{id:'later',title:'Later this month',days:later,cap:10}].filter(s=>s.days.length)}
function span(days){if(days.length===1)return dateFmt(days[0],{weekday:'long',month:'long',day:'numeric'});
  return dateFmt(days[0],{weekday:'short',month:'short',day:'numeric'})+' to '+dateFmt(days[days.length-1],{weekday:'short',month:'short',day:'numeric'})}
// The day is left out in a one-day section (Today): its heading says it.
function when(t,today,one){const[s,e]=t,d=s.slice(0,10);
  const day=one?'':'<b>'+esc(d===today?'Today':d===dayAdd(today,1)?'Tomorrow':dateFmt(d,{weekday:'short',month:'short',day:'numeric'}))+'</b>';
  return day+(s.length===10?'All day':esc(clock(s)+(e&&e.slice(0,10)===d?'–'+clock(e):'')))}
function row(e,t,rest,today,one){
  const where=e.lat==null?[e.venue,C.placeless]:[e.venue,e.hood],src=C.srcs[e.src];
  const more=rest.length?'<span class="more">'+(rest.length===1?'Also '+esc(dateFmt(rest[0][0].slice(0,10),{weekday:'short',month:'short',day:'numeric'})):esc('+ '+rest.length+' more dates to '+dateFmt(rest[rest.length-1][0].slice(0,10),{month:'short',day:'numeric'})))+'</span>':'';
  const map=e.lat==null?'':'<a class="maplink" href="'+esc(C.map+'#map=17/'+e.lat+'/'+e.lng+'&pin='+e.lat+','+e.lng+'&name='+encodeURIComponent(e.venue||e.title))+'">'+C.pin+'Show on map</a>';
  return'<li><time>'+when(t,today,one)+'</time><div class="ev"><a class="t" href="'+esc(e.url)+'" target="_blank" rel="noopener">'+esc(e.title)+'</a>'+
    '<span class="where">'+esc(where.filter(Boolean).filter((v,i,a)=>a.indexOf(v)===i).join(' · '))+'</span>'+more+
    '<span class="acts">'+(e.free?'<span class="tag free">Free</span>':'')+(src?'<span class="src">'+esc(src)+'</span>':'')+(e.category?'<span class="tag">'+esc(e.category)+'</span>':'')+
    (me&&e.lat!=null?'<span class="away">'+esc(away(km(me,[e.lat,e.lng])))+'</span>':'')+map+'</span></div></li>'}
function render(){if(!D)return;const now=cityNow(D.tz),today=now.slice(0,10),f=freeEl.checked,cat=catEl.value,hood=hoodEl.value;
  const keep=D.events.filter(e=>(!f||e.free===true)&&(!cat||e.category===cat)&&(!hood||(hood==='-'?e.lat==null:e.hood===hood)))
    .map(e=>[e,e.times.filter(t=>live(t,now))]).filter(a=>a[1].length);
  const dist=e=>me&&e.lat!=null?km(me,[e.lat,e.lng]):1e9;
  const key=s=>s.length===10?s+'T99':s;     // by start time, all-day ones after that day's timed ones
  out.innerHTML=sections(now).map(s=>{const set=new Set(s.days);
    const rows=keep.map(([e,ts])=>{const i=ts.findIndex(t=>set.has(t[0].slice(0,10)));return i<0?null:[e,ts[i],ts.slice(i+1)]}).filter(Boolean)
      .sort((a,b)=>(dist(a[0])-dist(b[0]))||key(a[1][0]).localeCompare(key(b[1][0]))||a[0].title.localeCompare(b[0].title));
    const cap=shown[s.id]||s.cap||30,body=rows.slice(0,cap).map(r=>row(r[0],r[1],r[2],today,s.days.length===1)).join('');
    return'<section id="'+s.id+'" aria-labelledby="h-'+s.id+'"><h2 id="h-'+s.id+'">'+esc(s.title)+' <span class="n">'+rows.length.toLocaleString(C.locale)+(rows.length===1?' event':' events')+'</span></h2>'+
      '<p class="days">'+esc(span(s.days))+'</p>'+(rows.length?'<ul class="events">'+body+'</ul>':'<p class="empty">Nothing listed'+(f||cat||hood?' with these filters.':'.')+'</p>')+
      (rows.length>cap?'<button type="button" class="showall" data-s="'+s.id+'" data-n="'+rows.length+'">Show all '+rows.length.toLocaleString(C.locale)+'</button>':'')+'</section>'}).join('');
  const q=new URLSearchParams();if(f)q.set('free','1');if(cat)q.set('cat',cat);if(hood)q.set('hood',hood);
  try{history.replaceState(null,'',location.pathname+(q.toString()?'?'+q:''))}catch(e){}
  $('reset').hidden=!(f||cat||hood)}
out.addEventListener('click',ev=>{const b=ev.target.closest('.showall');if(b){shown[b.dataset.s]=+b.dataset.n;render()}});
[freeEl,catEl,hoodEl].forEach(el=>el.addEventListener('change',()=>{for(const k in shown)delete shown[k];render()}));
$('reset').addEventListener('click',()=>{freeEl.checked=false;catEl.value='';hoodEl.value='';render()});
nearEl.addEventListener('click',()=>{
  if(me){me=null;nearEl.setAttribute('aria-pressed','false');nearEl.lastChild.textContent='Near me';statusEl.textContent='';render();return}
  if(!navigator.geolocation){statusEl.textContent='This browser can’t share a location.';return}
  statusEl.textContent='Finding where you are…';
  navigator.geolocation.getCurrentPosition(p=>{me=[p.coords.latitude,p.coords.longitude];nearEl.setAttribute('aria-pressed','true');nearEl.lastChild.textContent='Sorted by distance';
    statusEl.textContent='Nearest first, straight-line distance. Your location stays in this browser: it isn’t saved or sent anywhere.';render()},
    ()=>{statusEl.textContent='Location not available, so the list stays in time order.'},{enableHighAccuracy:false,timeout:15000,maximumAge:300000})});
fetch(C.file).then(r=>r.json()).then(d=>{D=d;
  const cats={},hoods={};let none=0;d.events.forEach(e=>{if(e.category)cats[e.category]=1;if(e.hood)hoods[e.hood]=1;if(e.lat==null)none++});
  const opt=(v,t)=>'<option value="'+esc(v)+'">'+esc(t)+'</option>',srt=o=>Object.keys(o).sort((a,b)=>a.localeCompare(b,C.locale));
  catEl.insertAdjacentHTML('beforeend',srt(cats).map(c=>opt(c,c)).join(''));
  hoodEl.insertAdjacentHTML('beforeend',(none?opt('-',C.placeless):'')+srt(hoods).map(h=>opt(h,h)).join(''));
  const q=new URLSearchParams(location.search);freeEl.checked=q.get('free')==='1';
  if(q.get('cat')&&cats[q.get('cat')])catEl.value=q.get('cat');if(q.get('hood')&&(hoods[q.get('hood')]||q.get('hood')==='-'))hoodEl.value=q.get('hood');
  const a=d.asof;$('stamp').textContent='Listing as of '+dateFmt(a.slice(0,10),{month:'long',day:'numeric'})+', '+clock(a)+', refreshed every morning. Each event links to its own page at the source.';
  render()}).catch(()=>{out.innerHTML='<section><p class="empty">The listing didn’t load. Try again in a moment.</p></section>'});
})();
</script>"""

controls = f"""<div class="controls">
<button type="button" class="near" id="near" aria-pressed="false">{NEAR_PIN.replace('fill="currentColor"', 'fill="#fff"')}<span>Near me</span></button>
<label class="check"><input type="checkbox" id="free"> Free only</label>
<label>Category <select id="cat"><option value="">All</option></select></label>
<label>Neighbourhood <select id="hood"><option value="">All</option></select></label>
<button type="button" class="reset" id="reset" hidden>Clear filters</button>
</div>
<p class="status" id="status" aria-live="polite"></p>"""
body = (f'<h1>{esc(W["title"])}</h1><p class="kind">{esc(W["intro"])} {esc(W["listing"])}</p>'
        f'<p class="stamp" id="stamp"></p>{controls}'
        f'<div id="sections"><section><p class="empty">Loading the listing…</p></section></div>'
        f'<noscript><section><p class="empty">This page needs JavaScript to show the listing.</p></section></noscript>'
        + SCRIPT.replace('__CFG__', json.dumps(JS_CFG, ensure_ascii=False)))
crumbs = f'<a href="/{city}/">{esc(CITY)} map</a> › Events'

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
{THEME_SCRIPT}
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(W['title'])} · Layers.City</title>
<meta name="description" content="{esc(W['desc'])}">
<link rel="canonical" href="{INDEX}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Layers.City">
<meta property="og:url" content="{INDEX}">
<meta property="og:title" content="{esc(W['title'])}">
<meta property="og:description" content="{esc(W['desc'])}">
<meta property="og:image" content="{INDEX}card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="/apple-touch-icon{BRAND}.png">
<link rel="preload" href="{esc(P['file'])}" as="fetch" crossorigin>
<style>{CSS}</style>
<script src="/stats.js" defer></script>
</head>
<body>
<div class="wrap">
<header><a class="brand" href="/">{PIN}<span>Layers<b>.City</b></span></a>
<nav class="crumbs">{crumbs}</nav></header>
<main>
{body}
</main>
<footer>{esc(W['source'])}<br><a href="/attributions/">Attributions</a> · <a href="/privacy/">Privacy</a> · <a href="/terms/">Terms</a> · <a href="/">All maps</a></footer>
</div>
</body>
</html>
"""
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'index.html'), 'w').write(page)
card_image(os.path.join(OUT, 'card.png'))
print(f'{city}: /{city}/events/ written')
