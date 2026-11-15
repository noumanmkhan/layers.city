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
    return env.ASSETS.fetch(request);
  },
};
