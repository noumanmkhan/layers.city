/* Along the way: find likely transit routes between two points, in the browser.
   No timetables: each ride costs its distance at the mode's typical speed, each boarding costs half the route's
   usual gap between vehicles plus a small penalty, and walking joins nearby stops. Round-based like RAPTOR
   (round k = k rides). Alternatives come from searching again with the main route's lines left out.
   Shared by the page and by tests (node). The engine names no city. */
(function (root) {
  var SPEED = { bus: 300, tram: 220, subway: 530, lrt: 380, go: 700, rail: 900 };  // metres a minute, stops included
  var WALK = 75;            // metres a minute, after the 1.3 detour below
  var DETOUR = 1.3;         // street distance / straight-line distance
  var ACCESS = 1000;        // furthest walk to the first stop / from the last (m, straight line)
  var XFER = 250;           // furthest walk between stops to change (m)
  var BOARD = 2;            // minutes added for every boarding (getting on is a hassle)
  var MAXWAIT = 10, MINWAIT = 1;
  var ROUNDS = 4;

  // opts.skip: modes to leave out, e.g. ['go', 'rail'] for local transit only.
  function Router(g, opts) {
    this.g = g;
    var skip = this.skip = {}, sm = (opts && opts.skip) || [];
    Object.keys(g.routes).forEach(function (rid) { if (sm.indexOf(g.routes[rid][2]) >= 0) skip[rid] = 1; });
    var lat0 = 0; g.stops.forEach(function (s) { lat0 += s[1]; }); lat0 /= g.stops.length;
    this.kx = 111320 * Math.cos(lat0 * Math.PI / 180); this.ky = 110540;
    var xy = this.xy = g.stops.map(function (s) { return [s[0] * this.kx, s[1] * this.ky]; }, this);
    // grid of stops, 250 m cells
    var C = this.C = 250, grid = this.grid = {};
    xy.forEach(function (p, i) { var k = Math.floor(p[0] / C) + ',' + Math.floor(p[1] / C); (grid[k] = grid[k] || []).push(i); });
    // patterns serving each stop: [pattern index, position]
    var sp = this.sp = g.stops.map(function () { return []; });
    g.patterns.forEach(function (p, pi) { p[2].forEach(function (s, j) { sp[s].push(pi, j); }); });
    // walking transfers, built lazily
    this.near = {};
  }
  Router.prototype.within = function (x, y, r) {
    var C = this.C, out = [], xy = this.xy, g = this.grid;
    for (var i = Math.floor((x - r) / C); i <= Math.floor((x + r) / C); i++)
      for (var j = Math.floor((y - r) / C); j <= Math.floor((y + r) / C); j++) {
        var c = g[i + ',' + j]; if (!c) continue;
        for (var n = 0; n < c.length; n++) {
          var p = xy[c[n]], d = Math.hypot(p[0] - x, p[1] - y);
          if (d <= r) out.push([c[n], d]);
        }
      }
    return out;
  };
  Router.prototype.nearStops = function (s) {
    if (!this.near[s]) { var p = this.xy[s]; this.near[s] = this.within(p[0], p[1], XFER).filter(function (q) { return q[0] !== s; }); }
    return this.near[s];
  };
  Router.prototype.wait = function (rid) {
    var h = this.g.routes[rid][3];
    return h ? Math.max(MINWAIT, Math.min(MAXWAIT, h / 2)) : MAXWAIT;
  };
  Router.prototype.speed = function (rid) {
    var r = this.g.routes[rid], m = r[2];
    if (m === 'bus' && /^9\d\d$/.test(r[0])) return 400;   // express buses
    return SPEED[m] || 300;
  };
  function walkMin(d) { return d * DETOUR / WALK; }

  // One search. a, b: [lng, lat]. ban: object of route ids to leave out.
  Router.prototype.search = function (a, b, ban) {
    ban = Object.assign({}, this.skip, ban || {});
    var g = this.g, n = g.stops.length, self = this;
    var ax = a[0] * this.kx, ay = a[1] * this.ky, bx = b[0] * this.kx, by = b[1] * this.ky;
    var direct = Math.hypot(ax - bx, ay - by);
    var egress = {}; this.within(bx, by, ACCESS).forEach(function (q) { egress[q[0]] = walkMin(q[1]); });
    var best = new Float64Array(n).fill(Infinity);      // best over all rounds (for pruning)
    var labels = [], parents = [];
    var L0 = new Float64Array(n).fill(Infinity), P0 = new Array(n), marked = [];
    this.within(ax, ay, ACCESS).forEach(function (q) { var t = walkMin(q[1]); L0[q[0]] = t; best[q[0]] = t; P0[q[0]] = { walk: true, d: q[1] }; marked.push(q[0]); });
    labels.push(L0); parents.push(P0);
    var target = direct < 2500 ? walkMin(direct) : Infinity, targetEnd = { walk: true };
    var ends = [];
    function checkEnd(k, L) {
      for (var s in egress) { var t = L[s] + egress[s]; if (t < target) { target = t; } if (isFinite(L[s])) ends.push([t, k, +s]); }
    }
    for (var k = 1; k <= ROUNDS && marked.length; k++) {
      var prev = labels[k - 1], L = new Float64Array(n).fill(Infinity), P = new Array(n);
      // patterns to scan, from the earliest marked position
      var scan = {};
      marked.forEach(function (s) { var a2 = self.sp[s]; for (var i = 0; i < a2.length; i += 2) { var pi = a2[i], j = a2[i + 1]; if (ban[g.patterns[pi][0]]) continue; if (scan[pi] === undefined || j < scan[pi]) scan[pi] = j; } });
      var improved = [];
      for (var pk in scan) {
        var pi = +pk, pat = g.patterns[pi], rid = pat[0], seq = pat[2], dist = pat[3];
        var v = this.speed(rid), w = this.wait(rid) + BOARD;
        var on = -1, onCost = Infinity;
        for (var j = scan[pi]; j < seq.length; j++) {
          var s = seq[j];
          if (on >= 0) {
            var t = onCost + (dist[j] - dist[on]) / v;
            if (t < L[s] && t < best[s] && t < target) { L[s] = t; best[s] = t; P[s] = { pat: pi, from: on, to: j, prev: k - 1 }; improved.push(s); }
          }
          var c = prev[s] + w;
          if (c < Infinity && (on < 0 || c < onCost + (dist[j] - dist[on]) / v)) { on = j; onCost = c; }
        }
      }
      // walk to nearby stops to change
      var walked = [];
      improved.forEach(function (s) {
        self.nearStops(s).forEach(function (q) {
          var t = L[s] + walkMin(q[1]);
          if (t < L[q[0]] && t < best[q[0]] && t < target) { L[q[0]] = t; best[q[0]] = t; P[q[0]] = { xfer: s, d: q[1] }; walked.push(q[0]); }
        });
      });
      labels.push(L); parents.push(P);
      checkEnd(k, L);
      marked = improved.concat(walked);
    }
    // the best end, then walk back through the parents
    ends.sort(function (x, y) { return x[0] - y[0]; });
    var walkOnly = direct < 2500 ? walkMin(direct) : Infinity;
    if (!ends.length || walkOnly <= ends[0][0]) return isFinite(walkOnly) ? { min: walkOnly, legs: [{ walk: true, m: direct * DETOUR, min: walkOnly }] } : null;
    var e = ends[0], legs = [], s = e[2], kk = e[1];
    legs.push({ walk: true, end: true, from: s, min: egress[s] });
    while (kk > 0) {
      var p = parents[kk][s];
      if (p.xfer !== undefined) { legs.push({ walk: true, from: p.xfer, to: s, min: walkMin(p.d) }); s = p.xfer; p = parents[kk][s]; }
      var pat = g.patterns[p.pat];
      legs.push({ route: pat[0], pat: p.pat, k: pat[1], from: p.from, to: p.to, stops: pat[2].slice(p.from, p.to + 1), wait: this.wait(pat[0]),
                  min: (pat[3][p.to] - pat[3][p.from]) / this.speed(pat[0]) });
      s = pat[2][p.from]; kk = p.prev;
    }
    legs.push({ walk: true, start: true, to: s, min: labels[0][s] });
    legs.reverse();
    return { min: e[0], legs: legs };
  };
  // Two routes are the same trip when their rides get on and off at the same places (504 or 503 along King):
  // the second's lines are kept on the first's legs as `also`.
  Router.prototype.same = function (x, y) {
    var a = x.legs.filter(function (l) { return l.route; }), b = y.legs.filter(function (l) { return l.route; }), self = this;
    if (a.length !== b.length) return false;
    function close(s, t) { var p = self.xy[s], q = self.xy[t]; return Math.hypot(p[0] - q[0], p[1] - q[1]) < 300; }
    for (var i = 0; i < a.length; i++)
      if (!close(a[i].stops[0], b[i].stops[0]) || !close(a[i].stops[a[i].stops.length - 1], b[i].stops[b[i].stops.length - 1])) return false;
    return true;
  };
  function sig(r) { return r.legs.filter(function (l) { return l.route; }).map(function (l) { return l.route; }).join('>'); }
  Router.prototype.sig = sig;

  // Up to `max` different routes, each within `slack` minutes (or 35%) of the quickest.
  Router.prototype.options = function (a, b, max) {
    max = max || 3;
    var first = this.search(a, b);
    if (!first) return [];
    var out = [first], seen = {}; seen[sig(first)] = 1;
    var limit = first.min + Math.max(12, first.min * 0.35);
    var queue = [{}], tried = {};
    while (queue.length && out.length < max + 3) {
      var ban = queue.shift();
      var base = this.search(a, b, ban);
      if (!base) continue;
      var lines = base.legs.filter(function (l) { return l.route; }).map(function (l) { return l.route; });
      for (var i = 0; i < lines.length; i++) {
        var b2 = Object.assign({}, ban); b2[lines[i]] = 1;
        var key = Object.keys(b2).sort().join(',');
        if (tried[key]) continue; tried[key] = 1;
        var r = this.search(a, b, b2);
        if (!r || r.min > limit) continue;
        var sg = sig(r);
        if (!seen[sg]) {
          seen[sg] = 1;
          var dup = null, self2 = this;
          for (var o = 0; o < out.length; o++) if (this.same(out[o], r)) { dup = out[o]; break; }
          if (dup) {
            var da = dup.legs.filter(function (l) { return l.route; }), ra = r.legs.filter(function (l) { return l.route; });
            da.forEach(function (l, li) { if (ra[li].route !== l.route && self2.g.routes[ra[li].route][2] === self2.g.routes[l.route][2]) { l.also = l.also || []; if (l.also.indexOf(ra[li].route) < 0) l.also.push(ra[li].route); } });
          } else out.push(r);
        }
        if (Object.keys(b2).length < 2) queue.push(b2);
      }
    }
    out.sort(function (x, y) { return x.min - y.min; });
    return out.slice(0, max);
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = Router; else root.AlongRouter = Router;
})(this);
