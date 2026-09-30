// "Just Australia?" — suggest a country filter on News and the Calendar.
//
// The guess comes from the browser's own timezone (tz-country.js, generated
// by util/make_tz_countries.py), falling back to a region in the reader's
// language setting (en-AU, pt-BR). Nothing leaves the browser: no IP lookup,
// no location prompt. It's a suggestion, never an automatic filter, because
// it's wrong for anyone travelling, on a VPN or with a UTC clock.
//
// Shown only when the page's filter is on "all", the guessed country has
// something on the page right now, and the reader hasn't dismissed it. Any
// filter change hides it for the rest of the visit.
(function () {
  var STORE_KEY = 'dod-country-suggest-dismissed';

  function guessCountry() {
    try {
      var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      var table = window.DOD_TZ_COUNTRY || {};
      if (tz && table[tz]) return table[tz];
    } catch (e) { /* fall through to language */ }
    var langs = navigator.languages || [navigator.language || ''];
    for (var i = 0; i < langs.length; i++) {
      var m = /^[a-z]{2,3}-([A-Z]{2})\b/.exec(langs[i] || '');
      if (m) return m[1];
    }
    return null;
  }

  function dismissed(code) {
    try { return localStorage.getItem(STORE_KEY) === code; } catch (e) { return false; }
  }
  function rememberDismissal(code) {
    try { localStorage.setItem(STORE_KEY, code); } catch (e) { /* private mode: dismiss for this visit only */ }
  }

  // opts: select (the page's country <select>), slot (an empty element to
  // render into), count(code) -> items that country has on the page, and
  // noun ('item'/'event'). Applying just sets the select and fires its own
  // change event, so the page's filter code (URL, subscribe button) runs
  // exactly as if the reader had picked the country themselves.
  window.DODCountrySuggest = function (opts) {
    var select = opts.select, slot = opts.slot;
    if (!select || !slot || select.value !== 'all') return;
    var code = guessCountry();
    if (!code || dismissed(code)) return;
    var option = Array.prototype.find.call(select.options, function (o) { return o.value === code; });
    if (!option) return;
    var n = opts.count(code);
    if (!n) return;

    var label = option.textContent.trim();
    slot.innerHTML = '';
    var text = document.createElement('span');
    text.className = 'country-suggest-text';
    text.textContent = 'Showing every country.';
    var apply = document.createElement('button');
    apply.type = 'button';
    apply.className = 'country-suggest-apply';
    apply.textContent = 'Just ' + label + '? (' + n + ' ' + opts.noun + (n === 1 ? '' : 's') + ')';
    apply.title = 'Suggested from your device’s time zone. Nothing is sent anywhere.';
    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'country-suggest-dismiss';
    close.setAttribute('aria-label', 'Dismiss suggestion');
    close.textContent = '✕';
    slot.appendChild(text);
    slot.appendChild(apply);
    slot.appendChild(close);
    slot.hidden = false;

    function hide() { slot.hidden = true; }
    apply.addEventListener('click', function () {
      hide();
      select.value = code;
      select.dispatchEvent(new Event('change'));
    });
    close.addEventListener('click', function () { rememberDismissal(code); hide(); });
    select.addEventListener('change', hide);
  };
})();
