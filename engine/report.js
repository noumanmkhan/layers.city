// "Report an issue" link for a place card: opens the place-report issue form
// (.github/ISSUE_TEMPLATE/place-report.yml) with the place, city and page filled in.
// Field names must match the form's ids. Issues are public; the form says so.
// The one approved link from the site's pages to GitHub (see CLAUDE.md).
// No city names here: the page passes its own city and URL.
var REPORT_FORM = 'https://github.com/noumanmkhan/layers.city/issues/new';

function reportUrl(place, city, pageUrl) {
  var p = place || {};
  var q = {
    template: 'place-report.yml',
    title: 'Place report: ' + (p.name || ''),
    place_id: p.id || p.osm || '',
    place_name: p.name || '',
    city: city || '',
    page_url: pageUrl || (typeof location !== 'undefined' ? location.href : '')
  };
  return REPORT_FORM + '?' + Object.keys(q).filter(function (k) { return q[k]; })
    .map(function (k) { return k + '=' + encodeURIComponent(q[k]); }).join('&');
}

if (typeof module !== 'undefined') module.exports = { reportUrl: reportUrl };
