# Reflex Divine — WordPress → Static Migration Report

Prepared: 14 Oct 2026 · Source: HTTrack mirror of https://reflexdivine.com (captured 14 Oct 2026, 05:11–05:15 GMT) · Output: `reflexdivineHTML/`

## 1. What the source actually was

The folder delivered as "WordPress source" is a **crawled HTML mirror** (HTTrack 3.50), not a WordPress install. There are no PHP templates, `wp-config.php`, database dump, or theme/plugin PHP code. It contains:

| Item | Count | Notes |
|---|---|---|
| Rendered pages (`*/index.html`) | 77 | Home, 6 top-level pages, Treatments + 8 children, Blog, 61 posts |
| `?p=ID` redirect stubs (`index04cd.html`, …) | 76 | Used to build the 301 redirect map |
| `page/2…7/` | 6 | Crawled AJAX pagination of the home page (`?jkit-ajax-request`), not real content |
| `indexe2f2.html` | 1 | Same AJAX artifact |
| `giItT1WQy@!-/` | 1 | A crawled **404 page** (random URL), not content |
| `wp-json/` | 155 files | oEmbed/REST responses, not needed |
| `wp-content/uploads` | 42 MB | 231 images, 4 MP4 testimonials, Elementor CSS, local Google Fonts |
| `wp-content/plugins`, `wp-includes` | CSS/JS only | Compiled front-end assets of the plugins listed below |

Because only rendered output was available, everything was reverse-engineered from the HTML, the Elementor-generated CSS (`uploads/elementor/css/post-*.css`) and the Yoast JSON-LD. **The original files were only read, never modified.** The output is written to `reflexdivineHTML/`.

### Stack identified
* **WordPress** with **Hello Elementor** theme + child theme "Reflex Divinee" (`themes/divinee`, empty custom CSS)
* **Elementor 4.2.3** and **Elementor Pro 4.2.2** (header/footer/single-post theme builder, forms, sticky header, motion effects)
* Page builder add-ons: **ElementsKit Lite**, **Jeg Elementor Kit**, **JetEngine**, **Image Hover Effects Addon**
* **Yoast SEO Premium 23.3**, **Google Site Kit 1.186**, **GTranslate**, **WP Rocket 3.23**, **Trustindex** Google-reviews widget
* Elementor global kit (post 136): primary `#BD1978`, secondary `#FFFBEF`, text `#000`, accent `#A7C259`, link `#D9AB52`; headings *Marcellus*, body *Poppins 16/36px*; container 1170 px

### Templates / reusable components found
| WordPress component | Where | Static replacement |
|---|---|---|
| Elementor header template (#272): logo, "Reflex Divine / Bio Acu Medical Care", ElementsKit nav menu with off-canvas mobile menu, phone button, sticky | all pages | `header()` in generator → `.site-header`, `RD.nav` |
| Fixed social bar (header section d7d70f7) | all pages | `.floating-social` |
| Elementor footer template (#318): brand, India/France addresses, phones, e-mail, socials, copyright, legal, credit | all pages | `footer()` → `.site-footer` |
| Page title banner (chamomile background) | inner pages | `banner()` → `.page-banner` |
| Single-post template (#803): title, featured image, content, share buttons, comments | 61 posts | `build_post()` |
| Jeg "post block" with AJAX next/prev pagination | /blog/ | Static cards + `RD.paginate` |
| ElementsKit icon-box, fun-fact counters, pricing tables, blog-posts | home, treatments, packages | `.therapy-card`, `.stat` + `RD.counters`, `.price-card`, `.post-card` |
| Elementor gallery + lightbox | /gallery/ | `.gallery-grid` + `RD.lightbox` |
| Elementor video widgets | /testimonials/ | native `<video controls preload="metadata">` |
| Elementor Pro form | /contact/ | `<form data-contact-form>` + backend (see §4) |
| Google Maps widget | /contact/ | lazy-loaded `<iframe>` |
| Lottie "falling leaf" animation | home hero | CSS keyframes using the site's own leaf PNG (no Lottie library) |
| Entrance animations (fadeInUp/Down/Left/Right, rotateIn) | everywhere | `[data-animate]` + IntersectionObserver |
| Shortcodes | `[trustindex …]` reviews (rendered in a `<template>`) | Static review cards + `RD.carousel` |

No other shortcodes, widgets areas or sidebars were in use. No page had user comments (Yoast `commentCount: 0` everywhere).

---

## 2. Plugin migration (every plugin accounted for)

Legend — ✅ fully replaced client-side · 🟡 replaced, needs a service/config · ❌ removed (no front-end function)

| Plugin | What it did on this site | Status | Replacement |
|---|---|---|---|
| **Elementor** (free) | Layout engine for every page, entrance animations, image/heading/text/button/divider/video/gallery/maps/icon-list widgets, lightbox | ✅ | Semantic HTML + `main.css`/`responsive.css`; `RD.animate`, `RD.lightbox`; native `<video>`, `<iframe>` |
| **Elementor Pro** | Theme builder (header, footer, single post), sticky header, motion-effects backgrounds, **contact form**, social share | ✅ / 🟡 form | Shared header/footer generated into each page; `position: sticky`; CSS backgrounds (`background-attachment: fixed` for parallax); share links (Facebook, X/Twitter, LinkedIn, Telegram, WhatsApp). Form → §4 |
| **ElementsKit Lite** | Nav menu + off-canvas, icon boxes, fun-fact counters, pricing tables, blog posts, social icons, header-info, Lottie, masonry, icon font | ✅ | `RD.nav` (accessible: focus trap, Esc, aria-expanded), `RD.counters`, CSS components, SVG sprite instead of icon font, CSS leaf animation |
| **Jeg Elementor Kit** | Post title, featured image, post block with AJAX next/prev pagination, social share, comment form | ✅ | Static post template; all 61 posts rendered into `/blog/` and paginated client-side (15/page, `?page=N`, no-JS shows all) |
| **JetEngine** | Only its frontend CSS was enqueued; no listings/dynamic fields found in any page | ❌ | Nothing to migrate |
| **Image Hover Effects Addon** | Only CSS enqueued; no hover-effect widgets in any page | ❌ | Zoom-on-hover recreated in CSS for cards/gallery |
| **Yoast SEO Premium** | Titles, meta descriptions, robots, canonical, Open Graph/Twitter, JSON-LD schema graph, XML sitemap | ✅ | Per-page tags carried over verbatim; absolute canonicals restored; schema graph kept (WordPress-only `CommentAction` removed, `SearchAction` pointed to `/search/`); `sitemap.xml` + `robots.txt` generated |
| **Google Site Kit** | GA4 tags `GT-M3LZ3NVF` + `G-36Q1P1MXMQ`, CF7/content events | ✅ | Same gtag IDs in every page; events for phone, e-mail, WhatsApp, booking clicks, `generate_lead` (form), `search` |
| **GTranslate** | Floating EN/FR/HI/TA switcher (bottom-right) using Google translation | 🟡 | `RD.translate`: same 4 languages, same position; loads Google Website Translator **only after a visitor picks a language** (no third-party call otherwise). *If Google retires that endpoint, drop in GTranslate's hosted widget `https://cdn.gtranslate.net/widgets/latest/float.js` — it also works on static sites.* |
| **WP Rocket** | Page cache, CSS/JS minify, lazy-load, preload | ✅ | Not needed: pages are static; native `loading="lazy"`, `fetchpriority`, preloaded fonts + hero, responsive WebP, long-lived cache headers in `.htaccess` |
| **Trustindex (Google reviews widget)** | "EXCELLENT ★★★★★ based on 67 reviews" slider on home, loaded from `cdn.trustindex.io` | 🟡 | Static review cards (8 reviews captured on 14 Oct 2026) + accessible carousel. Reviewer photos replaced with initials (no Google-CDN hotlinking/tracking). **Reviews will not auto-update** — see §4 |
| WordPress core extras | jQuery + migrate, emoji script, `comment-reply`, `wp-embed`, oEmbed, REST API links, RSD/xmlrpc link | ❌ | Removed. Every `wp-*` URL now 301s or 410s via `.htaccess` |
| Hello Elementor theme + "divinee" child | Base reset styles; child theme had no custom CSS | ✅ | `main.css` base layer |

---

## 3. Feature-by-feature status

| Feature | Original | Static version | Status |
|---|---|---|---|
| Navigation (desktop + mobile off-canvas) | ElementsKit | `RD.nav` | ✅ Completed |
| Sticky header overlapping hero | Elementor Pro sticky | CSS `position: sticky` | ✅ |
| Hero, About, Doctor feature, counters, therapies, reviews, blog teaser, CTA | Elementor/EKit | HTML/CSS | ✅ |
| Entrance animations / falling-leaf Lottie | Elementor/Lottie | IntersectionObserver / CSS | ✅ (honours reduced motion) |
| Treatments index + 8 detail pages | Elementor pages | Generated pages; numbered lists fixed | ✅ |
| Packages / pricing + WhatsApp booking | EKit pricing | `.price-card`, same `wa.me` links | ✅ |
| Gallery + lightbox | Elementor gallery | Grid + keyboard/touch lightbox | ✅ |
| Video testimonials | Elementor video | Native video, `preload=metadata` | ✅ |
| Blog listing + pagination | Jeg post block (AJAX) | Static + client pagination | ✅ |
| 61 blog posts at original URLs | WordPress | Static pages, same slugs | ✅ |
| Social share on posts | Jeg (links were `#`, JS-driven) | Real share URLs | ✅ (works without JS now) |
| Site search (`?s=`) | WordPress search | `/search/` + JSON index (pages, treatments, posts, first 400 words) | ✅ |
| Google Maps | Elementor widget | Lazy iframe | ✅ |
| Analytics | Site Kit | gtag | ✅ |
| Language switcher | GTranslate | Google Website Translator on demand | 🟡 third-party dependent |
| **Contact form** | Elementor Pro (server-side) | Front-end + PHP endpoint or form service | 🟡 **Backend required** |
| **Google reviews auto-refresh** | Trustindex (live) | Static snapshot | 🟡 **Service required for live data** |
| **Blog comments** | WP comments (none ever posted) | Replaced by "Have a question?" CTA (call/WhatsApp/contact) | 🟡 Optional service |
| Content editing (CMS) | WP admin | Edit HTML or regenerate | 🟡 See §4 |

---

## 4. Features that need a backend service or API

| Need | Why it cannot be pure front-end | Implemented / recommended solution |
|---|---|---|
| **Contact form e-mail delivery** | Sending mail requires a server and secrets that must not live in browser JS | **Implemented:** `integrations/contact-form/send-mail.php` (POST-only, same-origin check, honeypot, validation, header-injection safe, hashed-IP rate limit, config outside code). **Alternative for static hosts:** Formspree / Web3Forms / Netlify Forms via `data-endpoint`. **Built-in fallback:** pre-filled WhatsApp + e-mail links if no backend responds |
| **Live Google reviews** | Google Places API keys must stay server-side; quota | Keep the static snapshot and refresh periodically, **or** re-embed the Trustindex hosted widget (`cdn.trustindex.io/loader.js?<widget-id>` — needs the widget ID from the Trustindex dashboard), **or** a small scheduled job/serverless function calling Places API and writing JSON |
| **Blog comments** (optional) | Storage + moderation | Giscus (GitHub), Disqus, or Cusdis; or leave the CTA as is (no comments existed) |
| **CMS-style editing** (optional) | Non-technical editing UI | Edit HTML directly; or adopt a Git-based CMS (Decap CMS / CloudCannon) with an SSG later; or keep `tools/build_site.py` as the site generator |
| **Translation** | Machine translation API | Google Website Translator (on demand) or GTranslate hosted widget. For SEO-indexable translations, publish human-translated `/fr/`, `/ta/` pages with `hreflang` |
| **Cookie consent** (recommended, not present before) | France audience + GA4 → GDPR/ePrivacy | Add a consent banner with Google Consent Mode v2 (e.g., a lightweight CMP) before launch in France |

---

## 5. URL preservation & redirects

* **All 77 content URLs are unchanged** (`/about-us/`, `/treatments/foot-reflexology/`, `/<post-slug>/`, …), including the odd legacy slugs `/970-2/` and `/is-refleffectivxology-ee-for-long-term-conditions-…/` (kept to avoid breaking inbound links; see recommendations).
* New URLs: `/search/` (noindex) and `/404.html`.
* 301 redirects generated in `.htaccess`, `_redirects` and `integrations/server/nginx.conf`:

| Old | New |
|---|---|
| `/?p=<id>` (77 WordPress post/page IDs, map in `integrations/server/redirect-map.json`) | matching permalink |
| `/?s=<term>` | `/search/?q=<term>` |
| `/page/<n>/` | `/blog/` |
| `/feed/`, `/<slug>/feed/`, `/category/*`, `/author/*` | `/blog/` or the post |
| `/wp-content/uploads/<path>` | `/assets/images/uploads/<path>` |
| `/wp-admin`, `/wp-login.php`, `/xmlrpc.php`, `/wp-json`, `/wp-includes`, other `/wp-content` | **410 Gone** |
| `http://`, `www.` | `https://reflexdivine.com` |

---

## 6. Fixes applied while converting (technical issues, not redesign)

1. **Posts had no `<h1>`** (title was an `<h2>`) → title is now the single `<h1>`; added breadcrumbs + publish date.
2. **Canonical/OG URLs were relative** in the mirror → restored to absolute `https://reflexdivine.com/...`.
3. **Numbered steps all showed "1."** on Electro Homeopathy and other pages (each step was its own `<ol>`) → numbering continues correctly.
4. **Contact page body was "Sed ut perspiciatis…" lorem ipsum** → replaced with one neutral sentence. *Please review the wording.*
5. **Header text used heading tags** (`<h2>Reflex Divine</h2>` in header and footer on every page) → plain text, so every page has a clean heading outline.
6. Home "See Details" links all pointed to `/treatments/` → now link to the specific treatment page.
7. **Accessibility:** skip link, landmark roles, `aria-current` in nav, labelled buttons, focus trap in menu/lightbox, visible focus rings, `prefers-reduced-motion`, form labels and `aria-invalid`, descriptive `alt` on the template images (home, about, treatments, packages) that had empty alt text, `lang="en"`.
8. Gallery images had no alt text → descriptive fallback alt added.
9. Removed a leaked bot-protection `EditURI` link (`recaptcha.cloud/?…server=103.244.113.74&ip=…`) that the host injected into every page head.
10. Footer social icons and post share buttons pointed to `#` → share buttons now work; footer socials use the configured profiles.

## 7. Content issues found but **not changed** (owner decision needed)

* **Social profile links are placeholders** (`https://facebook.com/`, `https://instagram.com/`, `https://youtube.com/`) on the original site. Update `SOCIAL` in `tools/build_site.py` and rebuild.
* **Privacy Policy / Terms & Conditions** in the footer linked to `#` (no pages exist). Shown as plain text until pages are written — recommended, especially with Google Analytics and EU visitors.
* Brand spelling varies: "Reflex Divine" vs "Reflex Divinee" (H1 "Welcome to Reflex Divinee", page titles). Kept as published.
* Typo in home heading "Know more about foot **relexology**". Kept as published.
* Slug typo `/is-refleffectivxology-ee-for-long-term-conditions-…/` and the auto slug `/970-2/`. Kept; if renamed later, add a 301.
* About page paragraphs contain "…" truncations (copied from a search snippet). Kept.
* Two different WhatsApp numbers are used (hero/CTA: +91 94886 70470; packages: +91 82488 26560) and a third phone (+91 63805 43415) in the Mahe women-only clinic block. Kept as published — please confirm.

## 8. Security notes

* No credentials, API keys, salts or database details exist in the output. The only identifiers are the public GA4 measurement IDs.
* The static site has **no admin login, no database, no PHP** (except the optional mail endpoint) — the WordPress attack surface (xmlrpc, wp-login, plugin CVEs) is gone.
* `.htaccess` adds `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`, HSTS; blocks `/tools` and `/docs`; directory listing off.
* Recommend a Content-Security-Policy once the final third-party list is settled (GA, Google Translate, Google Maps).
