# Reflex Divine — SEO, Performance & QA Verification Report

Date: 14 Oct 2026 · Build: `tools/build_site.py` · Checks: `tools/validate_site.py`, browser tests in Chromium (desktop 1280–1440 px, mobile 375 px)

> **Scope note.** All measurements below were taken locally (no network throttling, local server). They show relative improvement. Re-run Lighthouse / PageSpeed Insights on the live domain after deployment for field numbers.

## 1. Automated validation (`python tools/validate_site.py`)

```
Checked 79 HTML pages, 77 sitemap URLs
0 errors, 0 warnings
```

What it checks on every page: every internal `href`, `src`, `srcset`, SVG `<use>` and form `action` resolves to a file; no leftover `wp-content`, `wp-includes`, `wp-json`, `elementor`, `xmlrpc` or shortcode text; no `index.html` links; exactly one `<h1>`; a `<title>`, meta description and absolute canonical; unique `id`s; `alt` on every `<img>` and `width`/`height` on content images; valid JSON-LD; every sitemap URL exists; every CSS `url()` exists. (The validator was proven to catch problems by injecting a broken link, a missing image and an image without alt into a copy of the site. All three were reported.)

## 2. SEO parity with the WordPress site

| Check | Result |
|---|---|
| URLs preserved | **77 / 77** content URLs identical (home, 7 pages, 8 treatments, 61 posts) |
| `<title>` | **77 / 77 identical** to Yoast output |
| Meta robots | **77 / 77 identical** (`index, follow, max-image-preview:large, …`); `/search/` and 404 are `noindex` |
| Meta description | **41 / 41** pages that had one are identical. **36 pages had none** on WordPress (28 posts + 8 treatments); they now get a description generated from the first 28 words of the content |
| Canonical | Absolute `https://reflexdivine.com/<path>/` on every page (the mirror had broken relative canonicals) |
| Open Graph / Twitter | `og:type/title/description/url/site_name/image`, `article:published_time/modified_time`, `twitter:card` on every page; images point to the optimised files |
| Structured data | Yoast graph preserved: `WebSite`, `WebPage`, `Article`, `Person`, `ImageObject`, `BreadcrumbList`. The `SearchAction` now targets `/search/?q=`; WordPress-only `CommentAction` removed. **Added** a `MedicalBusiness`/`HealthAndBeautyBusiness` node on the home page (name, address, phone, e-mail, price range, 5★ aggregate from 67 Google reviews) |
| Headings | One `<h1>` per page. **Posts gain a real H1** (WordPress used H2 for the post title). Header/footer brand text no longer uses heading tags |
| Image alt | 184 content images: 160 with descriptive alt text, 24 decorative images (leaves, flowers, logo marks) with `alt=""` on purpose |
| Internal links | All HTTrack `…/index.html` links rewritten to clean directory URLs; 0 broken |
| `sitemap.xml` | 77 URLs with `lastmod` from WordPress `article:modified_time` |
| `robots.txt` | Allows everything except `/search/`, `/integrations/`, `/tools/`, `/docs/`; declares the sitemap |
| Redirects | 77 `?p=ID` short links, `?s=` search, `/page/N/`, feeds, categories, authors, `/wp-content/uploads/*` → 301; WordPress admin endpoints → 410 (`.htaccess`, `_redirects`, nginx) |
| HTTPS / host | `.htaccess` forces `https://reflexdivine.com` (no `www`) |

## 3. Performance

### Page weight (bytes the browser must parse before rendering, not counting images)

| Page | WordPress CSS | Static CSS | WordPress JS | Static JS | WordPress HTML | Static HTML | DOM nodes WP → static |
|---|---|---|---|---|---|---|---|
| Home | 875 KB (41 files) + 13 KB inline | **38 KB (2)** | 656 KB (30 files) + 20 KB inline | **21 KB (2)** + 3 KB inline (analytics) | 164 KB | **44 KB** | 928 → 588 |
| Blog | 802 KB (30) | **38 KB (2)** | 364 KB (23) | **21 KB (2)** | 105 KB | 91 KB (all 61 cards, paginated in JS) | 520 → 982 |
| Post | 925 KB (31) | **38 KB (2)** | 398 KB (24) | **21 KB (2)** | 101 KB | **24 KB** | 482 → 291 |
| Contact | 827 KB (34) | **38 KB (2)** | 385 KB (24) | **21 KB (2)** | 94 KB | **16 KB** | 430 → 244 |

CSS and JS are not minified so they stay easy to maintain. Server gzip/brotli (enabled in `.htaccess`) cuts them by a further ~75%.

### Measured in the browser (home, local)
* **CLS: 0.000** (every image has `width`/`height`; fonts use `font-display: swap` and are preloaded)
* DOMContentLoaded ≈ 160 ms; 17 requests on first view (WordPress: 70+ local CSS/JS files, plus jQuery, Trustindex and Lottie)
* **No JavaScript errors** on Home, About, Treatments, a treatment page, Packages, Gallery, Testimonials, Contact, Blog, a post, Search, 404
* No horizontal overflow at 375 px

### Core Web Vitals measures applied
* **LCP:** the hero background is preloaded as WebP with `fetchpriority="high"`; post featured images use `fetchpriority="high"` and no lazy-loading; render-blocking CSS is down to 2 small files
* **INP:** no jQuery or Elementor runtime; about 21 KB of `defer`red vanilla JS; animations use IntersectionObserver
* **CLS:** explicit image dimensions, `aspect-ratio` containers, stable header
* Google Translate and Maps load only when needed (translator on language choice; map iframe `loading="lazy"`); Trustindex and Lottie are removed entirely

### Images
* Only the **79 uploads actually used** are shipped (WordPress kept 231 files, mostly auto-generated size variants).
* Each image gets an optimised fallback (≤ 1600 px, progressive JPEG q82 or optimised PNG) plus **WebP at 480 / 960 / full width**, served via `<picture>` with `srcset` and `sizes`.
* Full-size WebP total is **3.2 MB vs 15.1 MB** for the originals (–79%). Phones download the 480/960 px versions, which are much smaller still.
* The 4 testimonial videos (8.6 MB) are unchanged but use `preload="metadata"`, so nothing loads until a visitor presses play.
* Fonts: 9 self-hosted woff2 files (92 KB total; 2 preloaded), down from 40 font files plus icon fonts.

## 4. Functional tests (Chromium)

| Area | Test | Result |
|---|---|---|
| Header | Desktop nav, active state (`aria-current`), sticky overlap of hero | ✅ |
| Mobile menu | Opens full-height off-canvas panel; backdrop; body scroll lock; Esc / close button / backdrop close; focus trapped and returned to toggle | ✅ (bug found and fixed: `backdrop-filter` trapped the fixed panel inside the header) |
| Animations | Entrance animations fire on scroll; counters count to 10,543 / 10 / 10 / 15 | ✅ (`prefers-reduced-motion` handling and the 3-second no-JS fail-safe are implemented but were not separately tested) |
| Reviews carousel | Prev/next buttons wrap around; autoplay every 6 s, paused on hover/focus/hidden tab | ✅ |
| Gallery | Lightbox opens the right image; ←/→ keys, swipe, buttons; counter "4 / 8"; Esc closes and restores focus | ✅ |
| Blog | 61 posts, 15 per page, 5 pages; `?page=N` deep links; Next disabled on the last page | ✅ (without JS all 61 cards are in the HTML by design) |
| Search | "migraine" → 20 results ranked by title/description/body, highlighted; "abhyanga oil" → 4 results (all terms must match) | ✅ |
| Contact form | Empty submit flags email + phone, focuses the first invalid field; valid submit without a backend shows WhatsApp/e-mail fallback with the message pre-filled | ✅ front-end; **PHP endpoint not executed** (no PHP on the test server) — test after deployment |
| Videos | 4 testimonial videos play with native controls | ✅ |
| Post sharing | Facebook, X, LinkedIn, Telegram, WhatsApp share URLs encode title and canonical URL | ✅ |
| Language switcher | Menu opens/closes; choosing a language sets the `googtrans` cookie and loads Google's translator | ✅ wiring; translation itself depends on Google's service |
| 404 | `/404.html` uses root-absolute assets, so it renders at any depth | ✅ |

### Cross-browser
Uses only widely supported features: CSS Grid, `position: sticky`, `aspect-ratio`, `image-set()` (with a plain `url()` fallback first), `<picture>`/WebP, IntersectionObserver (falls back to showing content), `fetch`, `URLSearchParams`. Expected to work in current Chrome, Edge, Firefox, Safari 15.4+, and iOS/Android browsers. Automated testing ran in Chromium only. **Manually check Safari/iOS and Firefox after deployment.**

## 5. Known limitations / follow-ups

1. Contact form needs the PHP config or a form service (README §4) — **must be done before go-live**.
2. Google reviews are a static snapshot (8 reviews, "67 reviews"); refresh manually or re-embed Trustindex.
3. Add a cookie-consent banner (GA4 + EU visitors) and real Privacy/Terms pages.
4. Replace placeholder social URLs.
5. After launch: submit the sitemap in Search Console, monitor 404s for two weeks, and run PageSpeed Insights on the home page and one post.
