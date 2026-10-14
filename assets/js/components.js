/*!
 * Reflex Divine — UI components (vanilla JS, no dependencies)
 * Replaces jQuery, Elementor frontend, ElementsKit nav/funfact/masonry,
 * Magnific Popup, jquery.sticky, Lottie and Jeg Elementor Kit post pagination.
 */
(function (window, document) {
  'use strict';

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var RD = window.RD = window.RD || {};

  /* Off-canvas navigation (ElementsKit nav-menu replacement) */
  RD.nav = function () {
    var nav = document.querySelector('[data-offcanvas]');
    var toggle = document.querySelector('[data-nav-toggle]');
    var backdrop = document.querySelector('.nav-backdrop');
    if (!nav || !toggle) return;
    var lastFocus = toggle;

    function open() {
      lastFocus = toggle;
      nav.classList.add('is-open');
      document.body.classList.add('nav-open');
      toggle.setAttribute('aria-expanded', 'true');
      if (backdrop) backdrop.hidden = false;
      var first = nav.querySelector('a, button');
      if (first) first.focus();
    }
    function close() {
      nav.classList.remove('is-open');
      document.body.classList.remove('nav-open');
      toggle.setAttribute('aria-expanded', 'false');
      if (backdrop) backdrop.hidden = true;
      if (lastFocus) lastFocus.focus();
    }
    toggle.addEventListener('click', open);
    document.querySelectorAll('[data-nav-close]').forEach(function (el) { el.addEventListener('click', close); });
    document.addEventListener('keydown', function (e) {
      if (!nav.classList.contains('is-open')) return;
      if (e.key === 'Escape') close();
      if (e.key === 'Tab') { // keep focus inside the panel
        var f = nav.querySelectorAll('a, button');
        var a = f[0], z = f[f.length - 1];
        if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
        else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
      }
    });
    window.matchMedia('(min-width: 1200px)').addEventListener('change', function (m) { if (m.matches) close(); });
  };

  /* Scroll-triggered entrance animations (Elementor "Entrance Animation") */
  RD.animate = function () {
    var els = document.querySelectorAll('[data-animate]');
    if (!('IntersectionObserver' in window) || reduceMotion) {
      els.forEach(function (el) { el.classList.add('is-visible'); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add('is-visible'); io.unobserve(en.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    els.forEach(function (el) { io.observe(el); });
  };

  /* Animated counters (ElementsKit funfact) */
  RD.counters = function () {
    var els = document.querySelectorAll('[data-count-to]');
    if (!els.length) return;
    function run(el) {
      var to = parseInt(el.getAttribute('data-count-to'), 10) || 0;
      if (reduceMotion) { el.textContent = to.toLocaleString('en-US'); return; }
      var start = null, dur = 2000;
      function step(ts) {
        if (!start) start = ts;
        var p = Math.min((ts - start) / dur, 1);
        el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))).toLocaleString('en-US');
        if (p < 1) window.requestAnimationFrame(step);
      }
      el.textContent = '0';
      window.requestAnimationFrame(step);
    }
    if (!('IntersectionObserver' in window)) return; // numbers are already in the HTML
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { run(en.target); io.unobserve(en.target); } });
    }, { threshold: 0.5 });
    els.forEach(function (el) { io.observe(el); });
  };

  /* Carousel with buttons + autoplay (Trustindex slider replacement) */
  RD.carousel = function () {
    document.querySelectorAll('[data-carousel]').forEach(function (root) {
      var track = root.querySelector('[data-carousel-track]');
      var prev = root.querySelector('[data-carousel-prev]');
      var next = root.querySelector('[data-carousel-next]');
      if (!track) return;
      function stepSize() {
        var item = track.querySelector('[data-slide]');
        return item ? item.getBoundingClientRect().width + 16 : track.clientWidth;
      }
      function go(dir) {
        var max = track.scrollWidth - track.clientWidth - 2;
        if (dir > 0 && track.scrollLeft >= max) track.scrollTo({ left: 0 });
        else if (dir < 0 && track.scrollLeft <= 0) track.scrollTo({ left: max });
        else track.scrollBy({ left: dir * stepSize() });
      }
      if (prev) prev.addEventListener('click', function () { go(-1); });
      if (next) next.addEventListener('click', function () { go(1); });
      var delay = parseInt(root.getAttribute('data-autoplay'), 10);
      if (delay && !reduceMotion) {
        var timer = null;
        var start = function () { stop(); timer = window.setInterval(function () { go(1); }, delay); };
        var stop = function () { if (timer) window.clearInterval(timer); timer = null; };
        root.addEventListener('mouseenter', stop);
        root.addEventListener('mouseleave', start);
        root.addEventListener('focusin', stop);
        root.addEventListener('focusout', start);
        document.addEventListener('visibilitychange', function () { document.hidden ? stop() : start(); });
        start();
      }
    });
  };

  /* Lightbox (Elementor lightbox / Magnific Popup replacement) */
  RD.lightbox = function () {
    var links = Array.prototype.slice.call(document.querySelectorAll('[data-lightbox]'));
    if (!links.length) return;
    var icons = (document.querySelector('link[href$="main.css"]').getAttribute('href') || '').replace('assets/css/main.css', '') + 'assets/icons/icons.svg';
    function ic(n) { return '<svg class="icon" aria-hidden="true"><use href="' + icons + '#i-' + n + '"></use></svg>'; }
    var box = document.createElement('div');
    box.className = 'lightbox';
    box.hidden = true;
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', 'Image viewer');
    box.innerHTML = '<img class="lightbox__img" alt="">' +
      '<button type="button" class="lightbox__btn lightbox__close" aria-label="Close">' + ic('close') + '</button>' +
      '<button type="button" class="lightbox__btn lightbox__prev" aria-label="Previous image">' + ic('chevron-left') + '</button>' +
      '<button type="button" class="lightbox__btn lightbox__next" aria-label="Next image">' + ic('chevron-right') + '</button>' +
      '<p class="lightbox__count" aria-live="polite"></p>';
    document.body.appendChild(box);
    var img = box.querySelector('.lightbox__img');
    var count = box.querySelector('.lightbox__count');
    var idx = 0, opener = null, touchX = null;

    function show(i) {
      idx = (i + links.length) % links.length;
      var a = links[idx];
      var thumb = a.querySelector('img');
      img.src = a.getAttribute('href');
      img.alt = thumb ? thumb.alt : '';
      count.textContent = (idx + 1) + ' / ' + links.length;
    }
    function open(i) { opener = document.activeElement; show(i); box.hidden = false; document.body.style.overflow = 'hidden'; box.querySelector('.lightbox__close').focus(); }
    function close() { box.hidden = true; document.body.style.overflow = ''; img.removeAttribute('src'); if (opener) opener.focus(); }

    links.forEach(function (a, i) {
      a.addEventListener('click', function (e) { e.preventDefault(); open(i); });
    });
    box.querySelector('.lightbox__close').addEventListener('click', close);
    box.querySelector('.lightbox__prev').addEventListener('click', function () { show(idx - 1); });
    box.querySelector('.lightbox__next').addEventListener('click', function () { show(idx + 1); });
    box.addEventListener('click', function (e) { if (e.target === box) close(); });
    box.addEventListener('touchstart', function (e) { touchX = e.touches[0].clientX; }, { passive: true });
    box.addEventListener('touchend', function (e) {
      if (touchX === null) return;
      var dx = e.changedTouches[0].clientX - touchX;
      if (Math.abs(dx) > 40) show(idx + (dx < 0 ? 1 : -1));
      touchX = null;
    });
    document.addEventListener('keydown', function (e) {
      if (box.hidden) return;
      if (e.key === 'Escape') close();
      if (e.key === 'ArrowLeft') show(idx - 1);
      if (e.key === 'ArrowRight') show(idx + 1);
      if (e.key === 'Tab') { // trap focus among the buttons
        var b = box.querySelectorAll('button');
        if (e.shiftKey && document.activeElement === b[0]) { e.preventDefault(); b[b.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === b[b.length - 1]) { e.preventDefault(); b[0].focus(); }
      }
    });
  };

  /* Client-side pagination (Jeg Kit post block "next/prev" replacement).
     All posts are in the HTML (crawlable); JS only shows one page at a time. */
  RD.paginate = function () {
    var grid = document.querySelector('[data-paginate]');
    var pager = document.querySelector('[data-pager]');
    if (!grid || !pager) return;
    var per = parseInt(grid.getAttribute('data-paginate'), 10) || 15;
    var items = grid.querySelectorAll('[data-post]');
    var pages = Math.ceil(items.length / per);
    if (pages < 2) return;
    var prev = pager.querySelector('[data-pager-prev]');
    var next = pager.querySelector('[data-pager-next]');
    var status = pager.querySelector('[data-pager-status]');
    var page = 1;
    var m = /[?&]page=(\d+)/.exec(window.location.search);
    if (m) page = Math.min(Math.max(parseInt(m[1], 10), 1), pages);

    function render(scroll) {
      items.forEach(function (el, i) { el.hidden = i < (page - 1) * per || i >= page * per; });
      prev.disabled = page === 1;
      next.disabled = page === pages;
      status.textContent = 'Page ' + page + ' of ' + pages;
      var url = new URL(window.location.href);
      if (page > 1) url.searchParams.set('page', page); else url.searchParams.delete('page');
      window.history.replaceState(null, '', url);
      if (scroll) grid.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
    }
    prev.addEventListener('click', function () { if (page > 1) { page--; render(true); } });
    next.addEventListener('click', function () { if (page < pages) { page++; render(true); } });
    pager.hidden = false;
    render(false);
  };

  /* Language switcher (GTranslate replacement — uses Google Website Translator on demand) */
  RD.translate = function () {
    var root = document.querySelector('[data-lang-switcher]');
    if (!root) return;
    var toggle = root.querySelector('[data-lang-toggle]');
    var menu = root.querySelector('[role="menu"]');
    var current = root.querySelector('[data-lang-current]');
    var m = /(?:^|;\s*)googtrans=\/en\/(\w+)/.exec(document.cookie);
    var lang = m ? m[1] : 'en';

    function mark() {
      current.textContent = lang.toUpperCase();
      menu.querySelectorAll('[data-lang]').forEach(function (b) { b.setAttribute('aria-current', String(b.getAttribute('data-lang') === lang)); });
    }
    function setCookie(v) {
      var exp = v ? '' : '; expires=Thu, 01 Jan 1970 00:00:00 GMT';
      var val = v ? '/en/' + v : '';
      document.cookie = 'googtrans=' + val + '; path=/' + exp;
      var host = window.location.hostname;
      if (host.indexOf('.') > 0) document.cookie = 'googtrans=' + val + '; path=/; domain=.' + host.replace(/^www\./, '') + exp;
    }
    function loadGoogle() {
      if (window.google && window.google.translate) return;
      window.rdTranslateInit = function () {
        new window.google.translate.TranslateElement({ pageLanguage: 'en', includedLanguages: 'en,fr,hi,ta', autoDisplay: false }, 'google_translate_element');
      };
      var s = document.createElement('script');
      s.src = 'https://translate.google.com/translate_a/element.js?cb=rdTranslateInit';
      s.async = true;
      document.body.appendChild(s);
    }
    function setOpen(o) { menu.hidden = !o; toggle.setAttribute('aria-expanded', String(o)); }

    toggle.addEventListener('click', function () { setOpen(menu.hidden); });
    document.addEventListener('click', function (e) { if (!root.contains(e.target)) setOpen(false); });
    root.addEventListener('keydown', function (e) { if (e.key === 'Escape') { setOpen(false); toggle.focus(); } });
    menu.addEventListener('click', function (e) {
      var b = e.target.closest('[data-lang]');
      if (!b) return;
      var v = b.getAttribute('data-lang');
      setOpen(false);
      if (v === lang) return;
      setCookie(v === 'en' ? '' : v);
      window.location.reload();
    });
    mark();
    if (lang !== 'en') loadGoogle(); // only contacts Google when a translation was chosen
  };
})(window, document);
