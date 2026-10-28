/* Live arrivals for the Routes page: GET /api/arrivals?city=toronto&stops=8344,2977[&rapid=1]
 *
 * A Cloudflare Pages Function (deployed with the site by deploy.yml; it serves only /api/*). It reads the city's
 * GTFS-realtime trip updates, which browsers can't fetch themselves (the agency's server sends no CORS header),
 * and returns the next arrivals at the stops asked for:
 *   {now, asof, stops: {"8344": [[route, direction, epoch seconds, live], ...]}}
 * live is 1 when a vehicle is already on that trip (a prediction), 0 when not (the agency's schedule for a trip
 * that hasn't started yet).
 *
 * The feed (Toronto: about 620 KB, refreshed every 20 to 30 s) is fetched through Cloudflare's cache for 20 s, so
 * the agency sees at most a few requests a minute from each Cloudflare location, however many people are looking.
 * It is scanned with a small hand-written protobuf reader that only looks at the fields used here, instead of a
 * full decoder (which takes 15 to 40 ms in V8 for this feed): it keeps the free plan's CPU budget.
 * rapid=1 (some of the stops are subway or LRT platforms) also reads the city's rapid-transit feed, when it has one
 * (Toronto: the subway, about 12 KB), and merges its arrivals in; the main feed is read too, since a light rail
 * line may be in either. Only the feeds needed are fetched.
 * No logging, no cookies, nothing about the visitor is kept: the request carries only stop ids.
 */
const FEEDS = {
  toronto: { main: 'https://gtfsrt.ttc.ca/trips/update?format=binary', rapid: 'https://gtfsrt.ttc.ca/trips/subway?format=binary' },
};
const FEED_TTL = 20;      // seconds the feed is cached at the edge
const MAX_STOPS = 24;
const AHEAD = 90 * 60;    // keep arrivals up to 90 minutes out
const PER_STOP = 30;

export async function onRequestGet({ request }) {
  const url = new URL(request.url);
  const city = url.searchParams.get('city') || 'toronto';
  const feeds = FEEDS[city];
  const stops = [...new Set((url.searchParams.get('stops') || '').split(',').map(s => s.trim()).filter(s => /^[\w.-]{1,32}$/.test(s)))].slice(0, MAX_STOPS);
  if (!feeds || !stops.length) return json({ error: 'Give a known city and one or more stop ids.' }, 400, 60);
  const rapid = url.searchParams.get('rapid') === '1' && !!feeds.rapid;

  // The same question within 15 s gets the same answer from the edge cache, without reading the feed again.
  const key = new Request(`${url.origin}/api/arrivals?city=${city}&stops=${[...stops].sort().join(',')}${rapid ? '&rapid=1' : ''}`);
  const cache = caches.default;
  const hit = await cache.match(key);
  if (hit) return hit;

  const get = async u => {
    const r = await fetch(u, { cf: { cacheTtl: FEED_TTL, cacheEverything: true }, headers: { 'User-Agent': 'Layers.City (go@layers.city)' } });
    if (!r.ok) throw new Error('feed ' + r.status);
    return new Uint8Array(await r.arrayBuffer());
  };
  const now = Math.floor(Date.now() / 1000);
  const bufs = await Promise.allSettled([get(feeds.main), rapid ? get(feeds.rapid) : Promise.reject('not asked')]);
  if (bufs.every(b => b.status === 'rejected')) return json({ error: 'The live feed is not responding right now.' }, 503, 10);
  const out = { asof: 0, stops: Object.fromEntries(stops.map(s => [s, []])) };
  for (const b of bufs) {
    if (b.status !== 'fulfilled') continue;
    const o = scan(b.value, stops, now);
    out.asof = Math.max(out.asof, o.asof);
    for (const s of stops) out.stops[s].push(...o.stops[s]);
  }
  for (const k of Object.keys(out.stops)) out.stops[k] = out.stops[k].sort((a, b) => a[2] - b[2]).slice(0, PER_STOP);
  const res = json({ now, asof: out.asof, stops: out.stops }, 200, 15);
  await cache.put(key, res.clone());
  return res;
}

function json(body, status, maxAge) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': `public, max-age=${maxAge}`,
      'Access-Control-Allow-Origin': '*' },
  });
}

/* ---- a minimal GTFS-realtime reader ----
 * FeedMessage: 1 header {3 timestamp}, 2 entity*.  FeedEntity: 3 trip_update.
 * TripUpdate: 1 trip {4 schedule_relationship, 5 route_id, 6 direction_id}, 2 stop_time_update*, 3 vehicle {1 id}.
 * StopTimeUpdate: 2 arrival {2 time}, 3 departure {2 time}, 4 stop_id, 5 schedule_relationship.
 * Every other field is skipped by its wire type. */
export function scan(b, stopIds, now) {
  const want = new Map(stopIds.map(s => [s, enc(s)]));
  const byLen = new Map();
  for (const [s, e] of want) { if (!byLen.has(e.length)) byLen.set(e.length, []); byLen.get(e.length).push([s, e]); }
  const stops = Object.fromEntries(stopIds.map(s => [s, []]));
  let asof = 0, p = 0;
  const n = b.length;

  function varint() {   // up to 53 bits, enough for epoch seconds and lengths
    let x = 0, mul = 1, c;
    do { c = b[p++]; x += (c & 0x7f) * mul; mul *= 128; } while (c & 0x80);
    return x;
  }
  function skip(wt) {
    if (wt === 0) { while (b[p++] & 0x80); }
    else if (wt === 1) p += 8;
    else if (wt === 2) { const l = varint(); p += l; }
    else if (wt === 5) p += 4;
    else throw new Error('wire type ' + wt);
  }
  function matchStop(start, len) {
    const cands = byLen.get(len);
    if (!cands) return null;
    outer: for (const [s, e] of cands) { for (let i = 0; i < len; i++) if (b[start + i] !== e[i]) continue outer; return s; }
    return null;
  }
  function eventTime(end) {   // StopTimeEvent: 2 time
    let t = 0;
    while (p < end) { const k = varint(), f = k >>> 3, wt = k & 7; if (f === 2 && wt === 0) t = varint(); else skip(wt); }
    return t;
  }
  function str(start, len) { let s = ''; for (let i = 0; i < len; i++) s += String.fromCharCode(b[start + i]); return s; }

  function tripUpdate(end) {
    let route = '', dir = 0, rel = 0, live = 0;
    const hits = [];
    while (p < end) {
      const k = varint(), f = k >>> 3, wt = k & 7;
      if (f === 1 && wt === 2) {   // trip
        const e = varint() + p;
        while (p < e) {
          const k2 = varint(), f2 = k2 >>> 3, w2 = k2 & 7;
          if (f2 === 5 && w2 === 2) { const l = varint(); route = str(p, l); p += l; }
          else if (f2 === 6 && w2 === 0) dir = varint();
          else if (f2 === 4 && w2 === 0) rel = varint();
          else skip(w2);
        }
      } else if (f === 2 && wt === 2) {   // stop_time_update
        const e = varint() + p;
        let stop = null, t = 0, skipped = false;
        while (p < e) {
          const k2 = varint(), f2 = k2 >>> 3, w2 = k2 & 7;
          if (f2 === 4 && w2 === 2) { const l = varint(); stop = matchStop(p, l); p += l; }
          else if ((f2 === 2 || f2 === 3) && w2 === 2) { const l = varint(), ee = p + l; const tt = eventTime(ee); p = ee; if (f2 === 2 || !t) t = tt || t; }
          else if (f2 === 5 && w2 === 0) skipped = varint() === 1;   // SKIPPED
          else skip(w2);
        }
        if (stop && t && !skipped) hits.push([stop, t]);
      } else if (f === 3 && wt === 2) {   // vehicle
        const e = varint() + p;
        while (p < e) { const k2 = varint(), f2 = k2 >>> 3, w2 = k2 & 7; if (f2 === 1 && w2 === 2) { const l = varint(); if (l) live = 1; p += l; } else skip(w2); }
      } else skip(wt);
    }
    if (rel === 3 || rel === 7) return;   // CANCELED, DELETED
    for (const [stop, t] of hits) if (t >= now - 60 && t <= now + AHEAD) stops[stop].push([route, dir, t, live]);
  }

  while (p < n) {
    const k = varint(), f = k >>> 3, wt = k & 7;
    if (f === 1 && wt === 2) {   // header
      const e = varint() + p;
      while (p < e) { const k2 = varint(), f2 = k2 >>> 3, w2 = k2 & 7; if (f2 === 3 && w2 === 0) asof = varint(); else skip(w2); }
    } else if (f === 2 && wt === 2) {   // entity
      const e = varint() + p;
      while (p < e) {
        const k2 = varint(), f2 = k2 >>> 3, w2 = k2 & 7;
        if (f2 === 3 && w2 === 2) { const ee = varint() + p; tripUpdate(ee); p = ee; } else skip(w2);
      }
    } else skip(wt);
  }
  return { asof, stops };
}

function enc(s) { const a = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) a[i] = s.charCodeAt(i); return a; }
