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
 *
 * San Francisco: Muni's trip updates from 511.org (about 1 MB, every Muni bus, train, streetcar and cable car),
 * which needs a key (the FIVE11_KEY secret, which deploy.yml copies to the Pages project; it stays here, never in
 * an answer) and allows 60 requests an hour per key. So its feed is cached for 60 s, and the last good copy is
 * kept for 15 minutes: when 511 says no (too many requests, or down), the answer is built from that copy, whose
 * times are still clock times, and says how old it is in asof. 511 writes stop ids as the rider-facing stop code
 * (1 + the GTFS stop_id: stop 5417 is 15417), so "idPrefix" maps the page's ids to the feed's and back.
 *
 * New York: the subway's trip updates come one feed per group of lines (A C E, B D F M, …; no key). The page sends
 * the rapid lines at the platforms asked for (&lines=A,C), and only those lines' feeds are read ("rapid" is then a
 * map of feeds and "lineFeed" says which feed carries each line; with no lines given, all are read). The buses'
 * live times need an MTA Bus Time key, which isn't set up: "main" is empty and bus stops get no live times.
 */
const FEEDS = {
  toronto: { main: 'https://gtfsrt.ttc.ca/trips/update?format=binary', rapid: 'https://gtfsrt.ttc.ca/trips/subway?format=binary' },
  nyc: {
    main: null,
    rapid: Object.fromEntries(['ace', 'bdfm', 'g', 'jz', 'nqrw', 'l', 'si', ''].map(k => [k || '1234567',
      'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs' + (k ? '-' + k : '')])),
    lineFeed: { 1: '1234567', 2: '1234567', 3: '1234567', 4: '1234567', 5: '1234567', 6: '1234567', 7: '1234567',
      '5X': '1234567', '6X': '1234567', '7X': '1234567', GS: '1234567', S: '1234567', A: 'ace', C: 'ace', E: 'ace',
      H: 'ace', FS: 'ace', B: 'bdfm', D: 'bdfm', F: 'bdfm', FX: 'bdfm', M: 'bdfm', G: 'g', J: 'jz', Z: 'jz',
      N: 'nqrw', Q: 'nqrw', R: 'nqrw', W: 'nqrw', L: 'l', SI: 'si', SIR: 'si' },
  },
  sf: { main: env => env.FIVE11_KEY && `https://api.511.org/transit/tripupdates?api_key=${encodeURIComponent(env.FIVE11_KEY)}&agency=SF`,
        ttl: 60, keep: 900, idPrefix: '1' },
};
const FEED_TTL = 20;      // seconds a feed is cached at the edge, unless it sets its own ttl
const MAX_STOPS = 24;
const AHEAD = 90 * 60;    // keep arrivals up to 90 minutes out
const PER_STOP = 30;

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const city = url.searchParams.get('city') || 'toronto';
  const feeds = FEEDS[city];
  const stops = [...new Set((url.searchParams.get('stops') || '').split(',').map(s => s.trim()).filter(s => /^[\w.-]{1,32}$/.test(s)))].slice(0, MAX_STOPS);
  if (!feeds || !stops.length) return json({ error: 'Give a known city and one or more stop ids.' }, 400, 60);
  const rapid = url.searchParams.get('rapid') === '1' && !!feeds.rapid;

  // A city with a feed per group of rapid lines: only the feeds for the lines asked for (all when none are named).
  const lines = [...new Set((url.searchParams.get('lines') || '').split(',').map(s => s.trim()).filter(s => /^\w{1,8}$/.test(s)))].sort();
  const rapidFeeds = !rapid ? [] : typeof feeds.rapid === 'object' && feeds.rapid
    ? [...new Set(lines.length && feeds.lineFeed && lines.every(l => feeds.lineFeed[l]) ? lines.map(l => feeds.lineFeed[l]) : Object.keys(feeds.rapid))]
    : ['rapid'];
  // The same question within 15 s gets the same answer from the edge cache, without reading the feed again.
  const key = new Request(`${url.origin}/api/arrivals?city=${city}&stops=${[...stops].sort().join(',')}${rapid ? '&rapid=1&f=' + rapidFeeds.join(',') : ''}`);
  const cache = caches.default;
  const hit = await cache.match(key);
  if (hit) return hit;

  const ttl = feeds.ttl || FEED_TTL;
  // A feed's last good copy, for a feed that sets "keep" (seconds), under a key of its own that names no secret.
  const keepKey = which => new Request(`${url.origin}/api/arrivals/__feed/${city}/${which}`);
  const get = async which => {
    const src = which === 'main' || which === 'rapid' ? feeds[which] : feeds.rapid[which];
    const u = typeof src === 'function' ? src(env || {}) : src;
    try {
      if (!u) throw new Error('no feed address');
      const r = await fetch(u, { cf: { cacheTtlByStatus: { '200-299': ttl, '400-599': 60 }, cacheEverything: true }, headers: { 'User-Agent': 'Layers.City (go@layers.city)' } });
      if (!r.ok) throw new Error('feed ' + r.status);
      const buf = await r.arrayBuffer();
      if (feeds.keep && r.headers.get('cf-cache-status') !== 'HIT')
        await cache.put(keepKey(which), new Response(buf, { headers: { 'Cache-Control': `public, max-age=${feeds.keep}` } }));
      return new Uint8Array(buf);
    } catch (e) {
      const old = feeds.keep && await cache.match(keepKey(which));
      if (old) return new Uint8Array(await old.arrayBuffer());
      throw e;
    }
  };
  const now = Math.floor(Date.now() / 1000);
  // The feed's own stop ids for the ones asked for (511: 1 + the stop_id), and back again.
  const pre = feeds.idPrefix || '';
  const feedIds = stops.map(s => pre + s);
  const bufs = await Promise.allSettled([feeds.main ? get('main') : Promise.reject('no main feed'), ...rapidFeeds.map(get)]);
  if (bufs.every(b => b.status === 'rejected')) return json({ error: 'The live feed is not responding right now.' }, 503, 10);
  const out = { asof: 0, stops: Object.fromEntries(stops.map(s => [s, []])) };
  for (const b of bufs) {
    if (b.status !== 'fulfilled') continue;
    const o = scan(b.value, feedIds, now);
    out.asof = Math.max(out.asof, o.asof);
    stops.forEach((s, i) => out.stops[s].push(...o.stops[feedIds[i]]));
  }
  for (const k of Object.keys(out.stops)) out.stops[k] = out.stops[k].sort((a, b) => a[2] - b[2]).slice(0, PER_STOP);
  const res = json({ now, asof: out.asof, stops: out.stops }, 200, Math.min(15, ttl));
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
