# Reflex Divine — standalone static website

A WordPress-free rebuild of **https://reflexdivine.com** (Reflex Divine Bio-Acu Medical Care, Pondicherry) in plain **HTML5, CSS3 and vanilla JavaScript**.
It needs no database, PHP runtime (except the optional contact-form endpoint), CMS or build step to serve.

| | WordPress site | This site |
|---|---|---|
| CSS on the home page | 875 KB in 41 files + 13 KB inline | **38 KB in 2 files** |
| JavaScript on the home page | 656 KB in 30 files (jQuery, Elementor, …) | **21 KB in 2 files**, no jQuery |
| Home page HTML | 164 KB | 44 KB |
| Plugins / theme | 11 plugins + Hello Elementor + child theme | none |

Full details: [`docs/MIGRATION_REPORT.md`](docs/MIGRATION_REPORT.md) · [`docs/SEO_PERFORMANCE_REPORT.md`](docs/SEO_PERFORMANCE_REPORT.md)

---

## 1. Project structure

```text
reflexdivineHTML/
├── index.html                      Home
├── about-us/  treatments/  packages/  gallery/  testimonials/  contact/  blog/
├── treatments/<8 treatment pages>/
├── <61 blog-post slugs>/index.html  Posts keep their original WordPress URLs
├── search/                         Client-side site search (replaces ?s=)
├── 404.html
├── assets/
│   ├── css/main.css                Design tokens, layout, components, animations
│   ├── css/responsive.css          Breakpoints: 1366 / 1199 (menu) / 1024 / 767
│   ├── js/components.js            Nav, animations, counters, carousel, lightbox, pager, translate
│   ├── js/main.js                  Bootstrap, contact form, search, analytics events
│   ├── icons/icons.svg             SVG sprite (Font Awesome Free glyphs used by the old site)
│   ├── icons/favicon-*.png …
│   ├── fonts/                      Self-hosted Marcellus + Poppins (woff2)
│   ├── images/uploads/YYYY/MM/     Optimised originals + responsive WebP (480/960/1600w)
│   ├── images/bg/                  CSS background images (JPG/PNG + WebP)
│   └── data/search-index.json      Generated search index
├── integrations/
│   ├── contact-form/send-mail.php  Secure PHP mail endpoint (optional backend)
│   ├── contact-form/config.sample.php
│   └── server/nginx.conf, redirect-map.json
├── .htaccess                       Apache/LiteSpeed: redirects, security headers, caching
├── _redirects                      Netlify / Cloudflare Pages redirects
├── robots.txt  sitemap.xml  favicon.ico
├── docs/                           Reports (blocked from public access)
├── dist/reflexdivine-static-site.zip  Packaged copy of the whole project (don't upload)
└── tools/                          Generator + validator (blocked from public access)
```

All links are **relative**, so the site also works from a sub-folder. Pages use clean URLs (`/about-us/`), so preview it through a web server, not by double-clicking files.

## 2. Run locally

```bash
cd reflexdivineHTML
python -m http.server 8000
```

Open http://localhost:8000. (Any static server works, e.g. `npx serve`.) The contact form needs PHP or a form service (see §4), so on a plain static server it shows the WhatsApp / e-mail fallback.

## 3. Deploy

### A. Existing cPanel / Apache / LiteSpeed hosting (recommended — same host as today)
1. Back up the current WordPress install and database (keep it offline as an archive).
2. Upload the **contents** of `reflexdivineHTML/` to `public_html/`. Include `.htaccess` (hidden file).
3. Configure the contact form (§4, option 1).
4. Delete `tools/` and `docs/` from the server, or leave them: `.htaccess` returns 403 for both.
5. Run the post-launch checks in §6.

### B. Netlify / Cloudflare Pages / Vercel (static hosting)
* Publish directory: `reflexdivineHTML`, no build command.
* `_redirects` is picked up automatically by Netlify and Cloudflare Pages. For Vercel, convert the rules to `vercel.json`.
* PHP doesn't run there, so use contact-form option 2.

### C. nginx
Use `integrations/server/nginx.conf` inside your `server {}` block.

## 4. Contact form (needs a backend)

The form posts with `fetch()` and shows inline success or error messages. If no backend answers, visitors get pre-filled **WhatsApp** and **e-mail** links, so an enquiry is never silently lost.

**Option 1 — PHP endpoint (shared hosting).** Already wired up as the form `action`.
```bash
cp integrations/contact-form/config.sample.php integrations/contact-form/config.php
# edit 'to' and 'from'  (use an address on your own domain for 'from', e.g. no-reply@reflexdivine.com)
```
Alternatively, set the environment variables `RD_MAIL_TO` and `RD_MAIL_FROM`. `config.php` is denied to web visitors by `integrations/contact-form/.htaccess`. Never commit it to version control.
Built-in protections: POST only, same-origin check, honeypot, strict validation, header-injection safety, a per-IP rate limit (5 per hour, IPs stored only as hashes), and JSON responses.

**Option 2 — hosted form service (static hosts).** Create a form at Formspree, Web3Forms or Netlify Forms, then add the endpoint to the form in `tools/build_site.py` (`contact_body`), or directly in `contact/index.html`:
```html
<form ... data-contact-form data-endpoint="https://formspree.io/f/XXXXXXX">
```
`data-endpoint` takes priority over `action`.

## 5. Editing content

The site is plain HTML, so you can edit any page directly. For site-wide changes (header, footer, phone numbers, social links, Google Analytics IDs, navigation), it's faster to change the constants at the top of `tools/build_site.py` and regenerate:

```bash
pip install beautifulsoup4 lxml pillow
python tools/build_site.py      # reads the WordPress mirror in ../ and rewrites the site
python tools/validate_site.py   # broken links/assets, SEO tags, JSON-LD, sitemap
```

The generator only rewrites generated files. It never touches `assets/css`, `assets/js`, `assets/icons`, `integrations/`, `docs/`, `tools/` or this README.

**Adding a new blog post without WordPress:** copy any post folder, such as `the-ultimate-guide-to-foot-reflexology/`, to a new slug. Then edit the `<title>`, meta description, canonical, `og:*` tags, JSON-LD dates, `<h1>`, image and body. Finally, add the post to `blog/index.html` as a card, to `sitemap.xml`, and to `assets/data/search-index.json`.

## 6. Post-launch checklist

- [ ] `https://reflexdivine.com/?p=1342` redirects (301) to `/dr-k-devapriyadharshini-…/`
- [ ] `https://reflexdivine.com/?s=sleep` redirects to `/search/?q=sleep`
- [ ] `https://reflexdivine.com/wp-content/uploads/2024/04/image-1.jpg` redirects to `/assets/images/uploads/2024/04/image-1.jpg`
- [ ] `/wp-admin/` and `/xmlrpc.php` return 410
- [ ] Send a real contact-form message and confirm it arrives
- [ ] Google Search Console: submit `https://reflexdivine.com/sitemap.xml`, then watch Coverage for 404s
- [ ] Google Analytics Realtime shows visits (IDs `G-36Q1P1MXMQ`, `GT-M3LZ3NVF`)
- [ ] Replace the placeholder social links (`SOCIAL` in `tools/build_site.py`)

## 7. Browser support

Current Chrome, Edge, Firefox and Safari (desktop and iOS/Android). All content and navigation work without JavaScript. Only these need it: the contact form's inline status messages (without JS it does a plain POST), site search, blog pagination (without JS all posts are listed on one page), the carousel's buttons and autoplay, the lightbox, and translation. Animations respect `prefers-reduced-motion`.

## 8. Credits & licences

* Website designed by Daspal (original design, preserved).
* Fonts: Marcellus and Poppins, SIL Open Font License 1.1.
* Icons: Font Awesome Free 5, CC BY 4.0.
