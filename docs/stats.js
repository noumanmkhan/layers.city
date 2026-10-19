/* Layers.City visit counts (Umami Cloud), shared by the maps hub and every city map.

   What's counted: page visits (path only), the referring site, country/region/city as Umami derives
   them from the connection (Umami says it stores no personal data and sets no cookies), device, browser,
   screen size, language,
   and which features get used, by name ("view: civic", "layer_on: tram", "image: portrait").

   What's never sent: anything after the # or the ? in the address (that's where pins, place names and
   the ?at= test spot live), search text, pin or location coordinates, place names, or any identifier
   for you. No cookies. The checks below enforce that even if a call elsewhere slips up:
   - the page address and referrer go out as origin + path only;
   - event data keeps only short ids (letters, digits, - and _), true/false, and a whole number under
     the key "step" (a tour step), so a coordinate can't pass as a number;
   - nothing loads off layers.city, with Global Privacy Control on, or after an opt-out on the privacy
     page (localStorage "umami.disabled"). Do Not Track is deliberately not honoured (October 19, 2026):
     the counts hold no personal data and no cookies, and honouring it hid every Chrome visitor who had
     it switched on.

   Leave ID empty to switch counting off everywhere. */
(function(){
  var ID = '26a83d6c-2032-4c93-94e5-4bba3bac7e70';
  var SRC = 'https://cloud.umami.is/script.js';
  var HOSTS = ['layers.city'];

  var queue = [], ready = false;
  // lcTrack(name, data): the engine's one way to count a feature. Calls before the tracker loads wait.
  window.lcTrack = function(name, data){
    if (!ID) return;
    if (ready && window.umami) window.umami.track(name, data);
    else if (queue.length < 20) queue.push([name, data]);
  };
  if (!ID || HOSTS.indexOf(location.hostname) < 0) return;
  if (navigator.globalPrivacyControl) return;
  try { if (localStorage.getItem('umami.disabled')) return; } catch (e) {}

  var ID_LIKE = /^[\w-]{1,40}$/;
  var bare = function(u){
    if (!u) return '';
    try { var x = new URL(u, location.href); return x.origin === location.origin ? x.pathname : x.origin + x.pathname; }
    catch (e) { return ''; }
  };
  window.lcBeforeSend = function(type, p){
    if (!p) return p;
    var out = {website: p.website, hostname: location.hostname, screen: p.screen, language: p.language,
      title: document.title, url: location.origin + location.pathname, referrer: bare(p.referrer)};
    if (p.name){
      if (!ID_LIKE.test(p.name)) return null;
      out.name = p.name;
      if (p.data && typeof p.data === 'object'){
        var d = {}, n = 0;
        for (var k in p.data){
          var v = p.data[k];
          if (!ID_LIKE.test(k)) continue;
          if (typeof v === 'boolean' || (k === 'step' && typeof v === 'number' && v % 1 === 0 && v >= 0 && v < 100) || (typeof v === 'string' && ID_LIKE.test(v))){ d[k] = v; n++; }
        }
        if (n) out.data = d;
      }
    }
    return out;
  };

  var s = document.createElement('script');
  s.defer = true; s.src = SRC;
  s.setAttribute('data-website-id', ID);
  s.setAttribute('data-domains', HOSTS.join(','));
  s.setAttribute('data-exclude-search', 'true');
  s.setAttribute('data-exclude-hash', 'true');
  s.setAttribute('data-before-send', 'lcBeforeSend');
  s.onload = function(){ ready = true; var q = queue; queue = []; q.forEach(function(a){ window.umami && window.umami.track(a[0], a[1]); }); };
  document.head.appendChild(s);
})();
