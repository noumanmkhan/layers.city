/* The layers.city Worker (Cloudflare Workers with static assets; replaces the Pages project, November 2026).
 *
 * docs/ is served as static assets (wrangler.jsonc): those requests never reach this code and cost nothing. Only
 * /api/* runs it (run_worker_first), and the one API is /api/arrivals, the live next-arrival times the Routes pages
 * and the iOS app read. Its handler stays in functions/api/arrivals.js, written as a Pages Function, so the Pages
 * project keeps serving it unchanged until the cutover.
 */
import { onRequestGet as arrivals } from '../functions/api/arrivals.js';

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    if (pathname === '/api/arrivals') {
      if (request.method !== 'GET' && request.method !== 'HEAD')
        return new Response('Only GET.', { status: 405, headers: { Allow: 'GET' } });
      return arrivals({ request, env, ctx });
    }
    if (pathname.startsWith('/api/')) return new Response('Not found.', { status: 404 });
    if (pathname.startsWith('/tiles/')) return tiles(request, env, ctx, pathname.slice(7));
    return env.ASSETS.fetch(request);
  },
};

/* /tiles/<path>: map tiles kept in the R2 bucket layers-city-tiles (binding TILES), such as toronto/buildings.pmtiles
 * (engine/tiles/buildings.sh). MapLibre's PMTiles protocol reads them by byte range, so each answer is the range
 * asked for (206), cached at Cloudflare's edge for a day so repeat views don't reach R2. */
async function tiles(request, env, ctx, key) {
  if (request.method !== 'GET' && request.method !== 'HEAD')
    return new Response('Only GET.', { status: 405, headers: { Allow: 'GET' } });
  if (!env.TILES || !/^[a-z0-9_-]+\/[a-z0-9_.-]+\.pmtiles$/.test(key)) return new Response('Not found.', { status: 404 });
  const range = request.headers.get('Range') || '';
  const cache = caches.default;
  const ck = new Request(new URL(request.url).origin + '/tiles/' + key + '?r=' + encodeURIComponent(range));
  const hit = await cache.match(ck);
  if (hit) return hit;
  const m = /^bytes=(\d+)-(\d*)$/.exec(range);
  const obj = await env.TILES.get(key, m ? { range: m[2] ? { offset: +m[1], length: +m[2] - +m[1] + 1 } : { offset: +m[1] } } : {});
  if (!obj) return new Response('Not found.', { status: 404 });
  const h = new Headers({ 'Content-Type': 'application/octet-stream', 'Accept-Ranges': 'bytes', ETag: obj.httpEtag,
    'Cache-Control': 'public, max-age=86400', 'Access-Control-Allow-Origin': '*' });
  let status = 200;
  if (m && obj.range) {
    const start = obj.range.offset, end = start + obj.range.length - 1;
    h.set('Content-Range', `bytes ${start}-${end}/${obj.size}`); h.set('Content-Length', String(obj.range.length)); status = 206;
  }
  const res = new Response(request.method === 'HEAD' ? null : obj.body, { status, headers: h });
  if (request.method === 'GET') ctx.waitUntil(cache.put(ck, res.clone()));
  return res;
}
