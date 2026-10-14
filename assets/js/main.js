/*!
 * Reflex Divine — page bootstrap, contact form and site search.
 * Replaces Elementor Pro Forms (AJAX), WordPress search (?s=) and
 * Google Site Kit event tracking.
 */
(function (window, document) {
  'use strict';
  var RD = window.RD || {};

  function track(name, params) {
    if (typeof window.gtag === 'function') window.gtag('event', name, params || {});
  }

  /* ---------- Header state ---------- */
  function headerState() {
    var h = document.querySelector('[data-sticky-header]');
    if (!h) return;
    var onScroll = function () { h.classList.toggle('is-scrolled', window.scrollY > 10); };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ---------- Outbound / CTA tracking (Site Kit "content events" replacement) ---------- */
  function clickTracking() {
    document.addEventListener('click', function (e) {
      var a = e.target.closest('a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      if (a.hasAttribute('data-track')) track(a.getAttribute('data-track'), { link_url: href });
      else if (href.indexOf('tel:') === 0) track('phone_call', { link_url: href });
      else if (href.indexOf('mailto:') === 0) track('email_click', { link_url: href });
      else if (href.indexOf('https://wa.me') === 0) track('whatsapp_click', { link_url: href });
    });
  }

  /* ---------- Contact form ----------
     Posts to the form's action (integrations/contact-form/send-mail.php by default)
     or to data-endpoint (e.g. a Formspree / Web3Forms URL) if set.
     If no backend answers, the visitor is offered WhatsApp / e-mail fallbacks
     with the message pre-filled, so enquiries are never silently lost. */
  function contactForm() {
    var form = document.querySelector('[data-contact-form]');
    if (!form) return;
    var status = form.querySelector('[data-form-status]');
    var btn = form.querySelector('[type="submit"]');
    var endpoint = form.getAttribute('data-endpoint') || form.getAttribute('action');

    function setStatus(msg, ok, html) {
      status.className = 'form__status ' + (ok ? 'is-ok' : 'is-error');
      if (html) status.innerHTML = msg; else status.textContent = msg;
    }
    function validate() {
      var valid = true;
      form.querySelectorAll('input[required], input[pattern], input[type="email"]').forEach(function (f) {
        var ok = f.checkValidity();
        f.setAttribute('aria-invalid', String(!ok));
        if (!ok && valid) { f.focus(); valid = false; }
      });
      return valid;
    }
    function fallback(data) {
      var text = 'Hello%20Reflex%20Divine%2C%0A' + encodeURIComponent(data.get('message') || '') +
        '%0A%0A' + encodeURIComponent((data.get('name') || '') + ' · ' + (data.get('phone') || '') + ' · ' + (data.get('email') || ''));
      return 'We could not send your message right now. Please reach us on ' +
        '<a href="https://wa.me/918248826560?text=' + text + '" target="_blank" rel="noopener">WhatsApp</a> or ' +
        '<a href="mailto:reflexdivineba@gmail.com?subject=Website%20enquiry&amp;body=' + text + '">e-mail</a>, or call +91 8248826560.';
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!validate()) { setStatus('Please check the highlighted fields.', false); return; }
      var data = new FormData(form);
      if (data.get('company')) return; // honeypot
      btn.disabled = true;
      setStatus('Sending…', true);
      fetch(endpoint, { method: 'POST', body: data, headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, body: j }; }); })
        .then(function (res) {
          if (res.ok && res.body && res.body.ok !== false) {
            form.reset();
            setStatus('Thank you! Your message has been sent. We will contact you soon.', true);
            track('generate_lead', { form_name: 'contact' });
          } else if (res.body && res.body.error && res.body.field) {
            setStatus(res.body.error, false); // validation message from the server
          } else {
            setStatus(fallback(data), false, true);
          }
        })
        .catch(function () { setStatus(fallback(data), false, true); })
        .then(function () { btn.disabled = false; });
    });
    form.querySelectorAll('input').forEach(function (f) {
      f.addEventListener('input', function () { if (f.getAttribute('aria-invalid') === 'true' && f.checkValidity()) f.setAttribute('aria-invalid', 'false'); });
    });
  }

  /* ---------- Site search (replaces WordPress ?s=) ---------- */
  function search() {
    var list = document.querySelector('[data-search-results]');
    if (!list) return;
    var input = document.querySelector('[data-search-input]');
    var summary = document.querySelector('[data-search-summary]');
    var root = list.getAttribute('data-root') || '';
    var q = (new URLSearchParams(window.location.search).get('q') || '').trim();
    input.value = q;
    if (!q) { summary.textContent = 'Type a word such as “migraine”, “sleep” or “abhyanga”.'; return; }

    function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); }
    function norm(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
    function highlight(text, terms) {
      var out = esc(text);
      terms.forEach(function (t) {
        if (t.length < 2) return;
        out = out.replace(new RegExp('(' + t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'), '<mark>$1</mark>');
      });
      return out;
    }

    summary.textContent = 'Searching…';
    fetch(list.getAttribute('data-index'))
      .then(function (r) { return r.json(); })
      .then(function (items) {
        var terms = norm(q).split(/\s+/).filter(Boolean);
        var results = items.map(function (it) {
          var t = norm(it.t), d = norm(it.d), b = norm(it.b);
          var score = 0;
          for (var i = 0; i < terms.length; i++) {
            var term = terms[i];
            var hit = false;
            if (t.indexOf(term) > -1) { score += 10; hit = true; }
            if (d.indexOf(term) > -1) { score += 4; hit = true; }
            if (b.indexOf(term) > -1) { score += 1; hit = true; }
            if (!hit) return null; // all terms must match
          }
          return { it: it, score: score };
        }).filter(Boolean).sort(function (a, b) { return b.score - a.score; });

        summary.textContent = results.length + (results.length === 1 ? ' result' : ' results') + ' for “' + q + '”';
        list.innerHTML = results.map(function (r) {
          var it = r.it;
          var kind = it.k === 'article' ? 'Article' + (it.dt ? ' · ' + it.dt : '') : it.k === 'treatment' ? 'Treatment' : 'Page';
          return '<li><span class="kind">' + esc(kind) + '</span><h2><a href="' + root + it.u + '">' + highlight(it.t, terms) +
            '</a></h2><p>' + highlight(it.d, terms) + '</p></li>';
        }).join('');
        track('search', { search_term: q });
      })
      .catch(function () { summary.textContent = 'Search is unavailable right now. Please browse the blog instead.'; });
  }

  function year() {
    document.querySelectorAll('[data-year]').forEach(function (el) { el.textContent = new Date().getFullYear(); });
  }

  function init() {
    if (RD.nav) RD.nav();
    if (RD.animate) RD.animate();
    if (RD.counters) RD.counters();
    if (RD.carousel) RD.carousel();
    if (RD.lightbox) RD.lightbox();
    if (RD.paginate) RD.paginate();
    if (RD.translate) RD.translate();
    headerState();
    clickTracking();
    contactForm();
    search();
    year();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})(window, document);
