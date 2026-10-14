#!/usr/bin/env python3
"""
Reflex Divine — WordPress (HTTrack mirror) -> standalone HTML/CSS/JS generator.

Reads the mirrored WordPress site in SRC (read-only) and writes a clean static
site into OUT. Hand-written files (assets/css, assets/js, assets/icons,
integrations/, docs/, README.md, tools/) are never touched.

Usage:
    python tools/build_site.py                 # SRC = parent of reflexdivineHTML
    python tools/build_site.py --src <mirror> --out <dir>

Requirements: Python 3.10+, beautifulsoup4, lxml, Pillow
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup, Comment, NavigableString
from PIL import Image

# --------------------------------------------------------------------------
# Site configuration (single source of truth for business data)
# --------------------------------------------------------------------------
SITE_URL = "https://reflexdivine.com"
SITE_NAME = "Reflex Divine"
BRAND = "Reflex Divine Bio-Acu Medical Care"
GA_IDS = ["G-36Q1P1MXMQ", "GT-M3LZ3NVF"]  # from Google Site Kit + manual gtag
PHONE_IN = "+91 8248826560"
PHONE_IN_TEL = "+918248826560"
PHONE_FR = "+33 631964486"
PHONE_FR_TEL = "+33631964486"
EMAIL = "reflexdivineba@gmail.com"
ADDR_IN = "Block - 1, No. 5, Viduthalai Nagar, Mudaliarpet, Pondicherry, India."
ADDR_FR = "22 Allée des greens, 95800 Courdimanche, France."
WA_HERO = "https://wa.me/919488670470"     # used by home "Book an Appointment"
WA_PACKAGES = "https://wa.me/918248826560"  # used by packages "Book Now"
# Social profiles: the WordPress site used generic placeholders. Update here.
SOCIAL = [
    ("Facebook", "facebook", "https://facebook.com/"),
    ("Instagram", "instagram", "https://instagram.com/"),
    ("YouTube", "youtube", "https://youtube.com/"),
]
NAV = [
    ("Home", ""), ("About Us", "about-us/"), ("Treatments", "treatments/"),
    ("Packages", "packages/"), ("Gallery", "gallery/"), ("Testimonials", "testimonials/"),
    ("Blog", "blog/"), ("Contact", "contact/"),
]
POSTS_PER_PAGE = 15  # matches the JetElementor post block on /blog/

# Hand-written paths that the build must never delete.
PRESERVE = {"assets", "tools", "integrations", "docs", "dist", "README.md"}
PRESERVE_ASSETS = {"css", "js", "icons"}

ROOT_DIR = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--src", default=str(ROOT_DIR.parent))
ap.add_argument("--out", default=str(ROOT_DIR))
args = ap.parse_args()
SRC = Path(args.src).resolve()
OUT = Path(args.out).resolve()

BUILD_DATE = dt.date.today().isoformat()
YEAR = dt.date.today().year


def log(*a):
    print(*a, flush=True)


# --------------------------------------------------------------------------
# Image pipeline: optimise + WebP + responsive widths
# --------------------------------------------------------------------------
WIDTHS = (480, 960, 1600)
_img_cache: dict[str, dict] = {}


def _src_path(ref: str) -> Path:
    ref = re.sub(r"^(\.\./)+", "", ref.split("?")[0])
    ref = ref.replace("%40", "@")
    return SRC / ref


def process_image(ref: str, max_w: int = 1600) -> dict:
    """Copy an upload into assets/images/uploads (optimised) and create WebP variants."""
    key = f"{ref}|{max_w}"
    if key in _img_cache:
        return _img_cache[key]
    sp = _src_path(ref)
    if not sp.exists():
        raise FileNotFoundError(f"missing image {ref}")
    rel = sp.relative_to(SRC).as_posix()
    rel = rel.replace("wp-content/uploads/", "assets/images/uploads/")
    dest = OUT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(sp)
    ow, oh = im.size
    ext = sp.suffix.lower()
    has_alpha = im.mode in ("RGBA", "LA", "P") and ("transparency" in im.info or im.mode != "P")
    w = min(ow, max_w)
    h = round(oh * w / ow)
    if ext == ".webp":
        # keep webp originals as the fallback too (all modern browsers)
        fb = dest
        if not fb.exists():
            im.resize((w, h), Image.LANCZOS).save(fb, "WEBP", quality=80, method=6) if w < ow else shutil.copy2(sp, fb)
    else:
        fb = dest
        if not fb.exists():
            if w < ow or ext in (".jpg", ".jpeg"):
                rim = im.resize((w, h), Image.LANCZOS) if w < ow else im
                if ext in (".jpg", ".jpeg"):
                    rim.convert("RGB").save(fb, "JPEG", quality=82, optimize=True, progressive=True)
                else:
                    rim.save(fb, optimize=True)
            else:
                shutil.copy2(sp, fb)
    variants = []
    for vw in WIDTHS:
        if vw >= w:
            continue
        vp = dest.with_name(f"{dest.stem}-{vw}w.webp")
        if not vp.exists():
            vh = round(oh * vw / ow)
            v = im.convert("RGBA" if has_alpha else "RGB").resize((vw, vh), Image.LANCZOS)
            v.save(vp, "WEBP", quality=78, method=6)
        variants.append((vp, vw))
    full_webp = dest.with_suffix(".webp") if ext != ".webp" else dest
    if ext != ".webp" and not full_webp.exists():
        im.convert("RGBA" if has_alpha else "RGB").resize((w, h), Image.LANCZOS).save(full_webp, "WEBP", quality=80, method=6)
    variants.append((full_webp, w))
    info = {
        "src": fb.relative_to(OUT).as_posix(),
        "webp": [(p.relative_to(OUT).as_posix(), vw) for p, vw in variants],
        "w": w, "h": h,
    }
    _img_cache[key] = info
    return info


def picture(ref: str, alt: str, R: str, cls: str = "", sizes: str = "100vw", max_w: int = 1600,
            lazy: bool = True, priority: bool = False, img_cls: str = "") -> str:
    info = process_image(ref, max_w)
    srcset = ", ".join(f"{R}{p} {w}w" for p, w in info["webp"])
    attrs = [f'src="{R}{info["src"]}"', f'alt="{html.escape(alt, quote=True)}"',
             f'width="{info["w"]}"', f'height="{info["h"]}"', 'decoding="async"']
    if priority:
        attrs.append('fetchpriority="high"')
    elif lazy:
        attrs.append('loading="lazy"')
    if img_cls:
        attrs.append(f'class="{img_cls}"')
    c = f' class="{cls}"' if cls else ""
    return (f'<picture{c}><source type="image/webp" srcset="{srcset}" sizes="{sizes}">'
            f'<img {" ".join(attrs)}></picture>')


def img_url(ref: str, max_w: int = 1600) -> str:
    """Absolute URL of the optimised fallback (for og:image etc.)."""
    return f"{SITE_URL}/{process_image(ref, max_w)['src']}"


def bg_image(ref: str, name: str, max_w: int = 1920) -> None:
    """Background images referenced from main.css -> assets/images/bg/<name>.{jpg|png,webp}."""
    sp = _src_path(ref)
    d = OUT / "assets/images/bg"
    d.mkdir(parents=True, exist_ok=True)
    im = Image.open(sp)
    ow, oh = im.size
    w = min(ow, max_w)
    rim = im.resize((w, round(oh * w / ow)), Image.LANCZOS) if w < ow else im
    alpha = sp.suffix.lower() == ".png"
    if alpha:
        rim.save(d / f"{name}.png", optimize=True)
        rim.convert("RGBA").save(d / f"{name}.webp", "WEBP", quality=80, method=6)
    else:
        rim.convert("RGB").save(d / f"{name}.jpg", "JPEG", quality=80, optimize=True, progressive=True)
        rim.convert("RGB").save(d / f"{name}.webp", "WEBP", quality=78, method=6)


# --------------------------------------------------------------------------
# Source parsing helpers
# --------------------------------------------------------------------------
def load(rel: str) -> BeautifulSoup:
    return BeautifulSoup((SRC / rel).read_text(encoding="utf-8"), "lxml")


def meta_of(soup: BeautifulSoup) -> dict:
    def m(**kw):
        t = soup.find("meta", attrs=kw)
        return t["content"].strip() if t and t.get("content") else ""
    schema = soup.select_one("script.yoast-schema-graph")
    return {
        "title": soup.title.get_text().strip() if soup.title else SITE_NAME,
        "description": m(name="description"),
        "robots": m(name="robots"),
        "og_title": m(property="og:title"),
        "og_type": m(property="og:type") or "website",
        "og_image": m(property="og:image"),
        "published": m(property="article:published_time"),
        "modified": m(property="article:modified_time"),
        "schema": json.loads(schema.string) if schema else None,
    }


def text_of(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip()


ALLOWED_TAGS = {"p", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "strong", "em", "b", "i",
                "a", "br", "img", "blockquote", "table", "thead", "tbody", "tr", "td", "th", "figure",
                "figcaption", "hr", "sup", "sub", "span"}


def clean_content(container, R: str, slugs: set[str]) -> str:
    """Sanitise WordPress post/page content into plain semantic HTML."""
    soup = BeautifulSoup(str(container), "lxml")
    root = soup.body.find() if soup.body else soup
    for t in root.find_all(["script", "style", "noscript", "iframe", "form", "svg"]):
        t.decompose()
    for c in root.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    # Elementor wraps text in nested <section>/<main>/<footer>; unwrap anything not allowed.
    for t in list(root.find_all(True)):
        if t.name not in ALLOWED_TAGS:
            t.unwrap()
    pictures: dict[str, str] = {}  # placeholder -> <picture> markup (inserted after serialising)
    for t in root.find_all(True):
        keep = {}
        if t.name == "a" and t.get("href"):
            keep["href"] = rewrite_href(t["href"], R, slugs)
            if keep["href"].startswith("http") and SITE_URL not in keep["href"]:
                keep["rel"] = "noopener"
                keep["target"] = "_blank"
        if t.name == "img":
            src = t.get("data-lazy-src") or t.get("src", "")
            alt = t.get("alt", "")
            token = f"@@PICTURE{len(pictures)}@@"
            pictures[token] = picture(src, alt, R, cls="content-img", sizes="(max-width: 860px) 100vw, 800px")
            t.replace_with(NavigableString(token))
            continue
        if t.name in ("td", "th") and t.get("colspan"):
            keep["colspan"] = t["colspan"]
        if t.name == "ol" and t.get("start"):
            keep["start"] = t["start"]
        t.attrs = keep
    # span without attributes is noise
    for t in root.find_all("span"):
        t.unwrap()
    # drop empty blocks (&nbsp; spacer paragraphs, empty headings)
    for t in list(root.find_all(["p", "h2", "h3", "h4", "h5", "h6", "li", "strong"])):
        if not t.get_text(strip=True).replace("\xa0", ""):
            t.decompose()
    # The WP editor split numbered steps into separate one-item <ol>s, so every step read "1.".
    # Continue the numbering across sibling one-item lists.
    n = 0
    for ol in root.find_all("ol"):
        if len(ol.find_all("li", recursive=False)) == 1:
            n += 1
            if n > 1:
                ol["start"] = str(n)
        else:
            n = 0
    out = root.decode_contents() if root.name in ("div", "body") else str(root)
    out = re.sub(r"\n\s*\n+", "\n", out).strip()
    for token, markup in pictures.items():
        out = out.replace(token, markup)
    return out


def rewrite_href(href: str, R: str, slugs: set[str]) -> str:
    """Rewrite HTTrack-style relative links (../slug/index.html) to clean relative URLs."""
    if href.startswith(("mailto:", "tel:", "#", "https://wa.me")):
        return href
    h = href.replace(SITE_URL + "/", "")
    if h.startswith(("http://", "https://")):
        return href
    h = re.sub(r"^(\.\./)+", "", h)
    h = re.sub(r"(^|/)index\.html", r"\1", h)
    if h.startswith("wp-content/uploads/"):
        return R + h.replace("wp-content/uploads/", "assets/images/uploads/")
    return R + h


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
def icon(name: str, R: str, cls: str = "icon") -> str:
    return f'<svg class="{cls}" aria-hidden="true" focusable="false"><use href="{R}assets/icons/icons.svg#i-{name}"></use></svg>'


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def head(*, R: str, path: str, title: str, description: str, og_type: str = "website",
         og_image: str = "", robots: str = "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1",
         schema=None, extra: str = "", published: str = "", modified: str = "", preload: str = "") -> str:
    canonical = f"{SITE_URL}/{path}"
    og_image = og_image or f"{SITE_URL}/assets/icons/og-default.png"
    art = ""
    if published:
        art += f'\n<meta property="article:published_time" content="{published}">'
    if modified:
        art += f'\n<meta property="article:modified_time" content="{modified}">'
    sch = ""
    if schema:
        sch = f'\n<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, separators=(",", ":"))}</script>'
    ga_main = GA_IDS[0]
    ga_cfg = "".join(f"gtag('config','{g}');" for g in GA_IDS)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>document.documentElement.className+=' js';setTimeout(function(){{if(!window.RD)document.documentElement.classList.remove('js')}},3000)</script>
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{canonical}">
<meta property="og:locale" content="en_US">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:image" content="{og_image}">{art}
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#BD1978">
<link rel="icon" href="{R}assets/icons/favicon-32x32.png" sizes="32x32">
<link rel="icon" href="{R}assets/icons/favicon-192x192.png" sizes="192x192">
<link rel="apple-touch-icon" href="{R}assets/icons/apple-touch-icon.png">
<link rel="preload" href="{R}assets/fonts/marcellus-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{R}assets/fonts/poppins-400-latin.woff2" as="font" type="font/woff2" crossorigin>{preload}
<link rel="stylesheet" href="{R}assets/css/main.css">
<link rel="stylesheet" href="{R}assets/css/responsive.css">{extra}{sch}
<script async src="https://www.googletagmanager.com/gtag/js?id={ga_main}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());{ga_cfg}</script>
</head>"""


def header(R: str, active: str) -> str:
    items = []
    for label, href in NAV:
        cur = ' aria-current="page"' if href == active else ""
        items.append(f'<li><a href="{R}{href}"{cur}>{label}</a></li>')
    social = "".join(
        f'<li><a href="{u}" target="_blank" rel="noopener" aria-label="{n}">{icon(i, R)}</a></li>' for n, i, u in SOCIAL)
    logo = picture("wp-content/uploads/2024/04/Asset-1-6k.png", "Reflex Divine logo", R, sizes="95px", max_w=480, lazy=False)
    logo_nav = picture("wp-content/uploads/2024/04/Asset-1-6k.png", "Reflex Divine logo", R, sizes="140px", max_w=480)
    return f"""
<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header" data-sticky-header>
  <div class="site-header__inner">
    <a class="brand" href="{R}" aria-label="Reflex Divine — Home">
      <span class="brand__logo">{logo}</span>
      <span class="brand__text"><span class="brand__name">Reflex Divine</span><span class="brand__tag">Bio Acu Medical Care</span></span>
    </a>
    <nav class="main-nav" id="main-nav" aria-label="Main navigation" data-offcanvas>
      <div class="main-nav__head">
        <a class="main-nav__logo" href="{R}">{logo_nav}</a>
        <button class="main-nav__close" type="button" data-nav-close aria-label="Close menu">{icon("close", R)}</button>
      </div>
      <ul class="main-nav__list">{"".join(items)}</ul>
    </nav>
    <a class="btn btn--solid header-phone" href="tel:{PHONE_IN_TEL}">{PHONE_IN}</a>
    <button class="nav-toggle" type="button" aria-controls="main-nav" aria-expanded="false" data-nav-toggle>
      {icon("menu", R)}<span class="sr-only">Open menu</span>
    </button>
  </div>
  <div class="nav-backdrop" data-nav-close hidden></div>
</header>
<ul class="floating-social" aria-label="Social media">{social}</ul>"""


def footer(R: str) -> str:
    logo = picture("wp-content/uploads/2024/04/Asset-1-6k.png", "Reflex Divine logo", R, sizes="140px", max_w=480)
    leaf6 = picture("wp-content/uploads/2024/04/elements-summer-sale-banner-NK5W2VA_leaf_6.png", "", R, cls="decor decor--footer-1", sizes="188px", max_w=400)
    leafs2 = picture("wp-content/uploads/2024/04/elements-summer-sale-banner-NK5W2VA_leafs_2.png", "", R, cls="decor decor--footer-2", sizes="76px", max_w=200)
    leafs = picture("wp-content/uploads/2024/04/elements-summer-sale-banner-NK5W2VA_leafs.png", "", R, cls="decor decor--footer-3", sizes="90px", max_w=200)
    social = "".join(
        f'<li><a href="{u}" target="_blank" rel="noopener" aria-label="{n}">{icon(i, R)}</a></li>' for n, i, u in SOCIAL)
    return f"""
<footer class="site-footer">
  <div class="footer-main">
    <div class="container footer-main__grid">
      <div class="footer-brand">
        <a href="{R}" class="footer-brand__logo" aria-label="Reflex Divine — Home">{logo}</a>
        <p class="footer-brand__name">Reflex Divine</p>
        <p class="footer-brand__tag">Bio Acu Medical Care</p>
      </div>
      <div class="footer-col">
        <p class="footer-col__title">{icon("pin", R)} India</p>
        <address>{ADDR_IN}</address>
      </div>
      <div class="footer-col">
        <p class="footer-col__title">{icon("pin", R)} France</p>
        <address>{ADDR_FR}</address>
      </div>
      <ul class="footer-contact">
        <li>{icon("phone", R)}<a href="tel:{PHONE_IN_TEL}">India : {PHONE_IN}</a></li>
        <li>{icon("phone", R)}<a href="tel:{PHONE_FR_TEL}">France : {PHONE_FR}</a></li>
        <li>{icon("at", R)}<a href="mailto:{EMAIL}">Email : {EMAIL}</a></li>
      </ul>
    </div>
    {leaf6}{leafs2}{leafs}
  </div>
  <div class="footer-bottom container">
    <ul class="footer-social" aria-label="Social media">{social}</ul>
    <p class="footer-copy">Copyright <span data-year>{YEAR}</span> &copy; {BRAND}.</p>
    <ul class="footer-legal"><li>Privacy Policy</li><li>Terms &amp; Conditions</li></ul>
  </div>
  <div class="footer-credit"><p>Website Designed by <a href="https://jayakumardeveloper.netlify.app/" target="_blank" rel="noopener">Jai❤️</a></p></div>
</footer>
<div class="lang-switcher" data-lang-switcher>
  <button type="button" class="lang-switcher__toggle" aria-haspopup="true" aria-expanded="false" data-lang-toggle>{icon("globe", R)}<span data-lang-current>EN</span></button>
  <ul class="lang-switcher__menu" role="menu" hidden>
    <li><button type="button" role="menuitem" data-lang="en">English</button></li>
    <li><button type="button" role="menuitem" data-lang="fr">Français</button></li>
    <li><button type="button" role="menuitem" data-lang="hi">हिन्दी</button></li>
    <li><button type="button" role="menuitem" data-lang="ta">தமிழ்</button></li>
  </ul>
</div>
<div id="google_translate_element" hidden></div>
<script src="{R}assets/js/components.js" defer></script>
<script src="{R}assets/js/main.js" defer></script>
</body>
</html>
"""


def banner(title: str, R: str, crumbs: bool = False, tag: str = "h1") -> str:
    bc = ""
    if crumbs:
        bc = (f'<nav class="breadcrumbs" aria-label="Breadcrumb"><ol><li><a href="{R}">Home</a></li>'
              f'<li aria-current="page">{esc(title)}</li></ol></nav>')
    return f'<section class="page-banner"><div class="container"><{tag} class="page-banner__title" data-animate="fade-up">{esc(title)}</{tag}>{bc}</div></section>'


def section_heading(sub: str, title: str, center: bool = True, sub_big: bool = False, tag="h2") -> str:
    c = " section-head--center" if center else ""
    s = " section-head__sub--big" if sub_big else ""
    return (f'<div class="section-head{c}" data-animate="fade-up"><p class="section-head__sub{s}">{sub}</p>'
            f'<{tag} class="section-head__title">{title}</{tag}></div>')


def write_page(path: str, content: str) -> None:
    dest = OUT / path / "index.html" if path and not path.endswith(".html") else OUT / (path or "index.html")
    if path == "":
        dest = OUT / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8", newline="\n")
    PAGES_WRITTEN.append(path)


PAGES_WRITTEN: list[str] = []


def schema_fix(schema: dict | None) -> dict | None:
    """Keep Yoast's graph but drop WordPress-only actions and point search at /search/."""
    if not schema:
        return None
    for node in schema.get("@graph", []):
        pa = node.get("potentialAction")
        if isinstance(pa, list):
            node["potentialAction"] = [a for a in pa if a.get("@type") != "CommentAction"]
            for a in node["potentialAction"]:
                if a.get("@type") == "SearchAction":
                    a["target"]["urlTemplate"] = f"{SITE_URL}/search/?q={{search_term_string}}"
            if not node["potentialAction"]:
                node.pop("potentialAction")
        elif isinstance(pa, dict) and pa.get("@type") == "SearchAction":
            pa["target"]["urlTemplate"] = f"{SITE_URL}/search/?q={{search_term_string}}"
        node.pop("commentCount", None)
        for k in ("url", "contentUrl", "thumbnailUrl"):
            if isinstance(node.get(k), str) and "/wp-content/uploads/" in node[k]:
                node[k] = node[k].replace("/wp-content/uploads/", "/assets/images/uploads/")
    return schema


# --------------------------------------------------------------------------
# Data extraction
# --------------------------------------------------------------------------
def discover() -> tuple[list[str], list[str]]:
    posts, pages = [], []
    for f in sorted(SRC.glob("*/index.html")):
        if f.parent.name.startswith(("wp-", "reflexdivineHTML", "page")):
            continue
        head_txt = f.read_text(encoding="utf-8", errors="ignore")[:400000]
        m = re.search(r'<body class="([^"]*)"', head_txt)
        cls = m.group(1) if m else ""
        if "single-post" in cls:
            posts.append(f.parent.name)
        elif "error404" in cls:
            continue
        else:
            pages.append(f.parent.name)
    return posts, pages


def excerpt(text: str, words: int = 18) -> str:
    w = text.split()
    return " ".join(w[:words]) + ("..." if len(w) > words else "")


def fmt_date(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def extract_posts(slugs: list[str]) -> list[dict]:
    out = []
    slugset = set(slugs)
    for slug in slugs:
        s = load(f"{slug}/index.html")
        meta = meta_of(s)
        title_el = s.select_one('[data-widget_type="jkit_post_title.default"] .post-title')
        body = s.select_one('[data-widget_type="theme-post-content.default"] .elementor-widget-container')
        fi = s.select_one('[data-widget_type="jkit_post_featured_image.default"] img')
        fi_src = (fi.get("data-lazy-src") or fi.get("src")) if fi else None
        # better alt text: listing used the post title as alt; fall back to that.
        cats = []
        if meta["schema"]:
            for n in meta["schema"]["@graph"]:
                if n.get("@type") == "Article":
                    cats = n.get("articleSection", [])
        out.append({
            "slug": slug,
            "title": text_of(title_el),
            "meta": meta,
            "body_el": body,
            "text": text_of(body),
            "image": re.sub(r"^(\.\./)+", "", fi_src) if fi_src else None,
            "image_alt": (fi.get("alt") or "") if fi else "",
            "categories": cats,
        })
    out.sort(key=lambda p: p["meta"]["published"], reverse=True)
    for p in out:
        p["slugs"] = slugset
    return out


# --------------------------------------------------------------------------
# Page builders
# --------------------------------------------------------------------------
TREATMENTS = [
    # slug, card title, short text, card image
    ("foot-reflexology", "Foot Reflexology", "Healing through foot pressure points for overall wellness.", "wp-content/uploads/2024/04/image-1.jpg"),
    ("varma-treatment", "Varma", "Ancient Indian technique using vital points to heal and rejuvenate.", "wp-content/uploads/2024/04/varmatreatmentsimg.webp"),
    ("electro-homeopathy", "Electro Homeopathy", "Natural remedies with electromagnetic properties for health.", "wp-content/uploads/2024/04/Cure-With-Therapy-Electro-Homeopathy-2-1.jpg"),
    ("ginger-therapy", "Ginger Therapy", "Therapeutic use of ginger for detox, pain relief, and vitality.", "wp-content/uploads/2024/04/14.Ginger-Therapy-1.jpg"),
    ("ayurvedic-abhyanga-therapy", "Ayurveda Abhyanga Therapy", "Traditional oil massage for detox and balance.", "wp-content/uploads/2024/04/images-4.jpg"),
    ("moxibustion-therapy", "Moxibustion Therapy", "Heat therapy using moxa for healing and energy flow.", "wp-content/uploads/2024/04/moxibustion-cones-moxa-treatment-points-top-needles.webp"),
    ("streaming-therapy", "Steaming Therapy", "Steam treatment to cleanse, detoxify, and revitalize.", "wp-content/uploads/2024/04/image16.jpg"),
    ("clx-nutraceutical-treatment", "CLX Nutraceutical Therapy", "Nutritional supplements boosting health and vitality.", "wp-content/uploads/2024/04/Picture1.png"),
]

REVIEWS = [
    ("Prajwala n.simha", "2024-04-29", "Had been here for foot reflexology! They are super friendly! Guide us properly ! Relaxing ! The place is clean Amazing experience! Definitely recommend this"),
    ("Padmavathi", "2024-04-13", "Best place for foot reflexology. Diagnosis is very good ."),
    ("Surensr SR", "2024-03-16", "Best Reflexology in Pondicherry. Good Treatment"),
    ("Ondra Hrdina", "2024-03-05", "Fantastic massages by professionals!"),
    ("Chaguila ANTOINE", "2024-02-07", "Le traitement en Reflexologie est super ! J’en suis à ma 2eme séance."),
    ("Saravanan Saravanan", "2023-09-25", "Good Experience"),
    ("Joseline Delaflore", "2023-08-16", "Très bon soin"),
    ("Camay V", "2023-08-13", "Good care. I recommend this center."),
]


def decor(name: str, R: str, cls: str, w: int = 200) -> str:
    return picture(f"wp-content/uploads/2024/04/{name}", "", R, cls=f"decor {cls}", sizes=f"{w}px", max_w=max(200, w * 2))


def build_home(posts_by_slug: dict) -> None:
    R = ""
    src = load("index.html")
    m = meta_of(src)
    home_cards = ["sole-searching-exploring-the-ancient-art-of-foot-reflexology",
                  "unlocking-wellness-the-power-of-foot-reflexology",
                  "from-toe-to-head-understanding-foot-reflexologys-healing-pathways"]
    blog_cards = "".join(post_card(posts_by_slug[s], R, home=True) for s in home_cards)

    def therapy_card(slug, title, text, delay):
        return f"""<div class="therapy-card" data-animate="fade-up" style="--delay:{delay}ms">
          <h3 class="therapy-card__title">{title}</h3>
          <p>{text}</p>
          <a class="link-arrow" href="{R}treatments/{slug}/">See Details {icon("arrow-right", R)}</a>
          {picture("wp-content/uploads/2024/04/elements-spa-logo-template-H9V6JEB.png", "", R, cls="therapy-card__mark", sizes="47px", max_w=200)}
        </div>"""

    def therapy_img(ref, alt, flowers=1):
        fl = "".join(decor("elements-summer-sale-banner-NK5W2VA_flower.png", R, f"decor--flower decor--flower-{i}", 82) for i in range(1, flowers + 1))
        return f'<div class="therapy-img" data-animate="zoom-in">{picture(ref, alt, R, sizes="(max-width: 767px) 100vw, 25vw", max_w=960)}{fl}</div>'

    stats = [
        ("EGVMGU_4.png", 10543, "+", "Satisfied Customers"),
        ("EGVMGU_5.png", 10, "+", "Well Trained Experts"),
        ("EGVMGU_6.png", 10, "+", "Popular Treatments"),
        ("EGVMGU_7.png", 15, "", "Years in Service"),
    ]
    stat_html = "".join(f"""<div class="stat" data-animate="fade-up" style="--delay:{i*120}ms">
        <span class="stat__icon">{picture("wp-content/uploads/2024/04/elements-50-spa-line-green-black-icons-" + f, "", R, sizes="68px", max_w=200)}</span>
        <p class="stat__num"><span data-count-to="{n}">{n:,}</span>{suf}</p>
        <p class="stat__label">{label}</p></div>""" for i, (f, n, suf, label) in enumerate(stats))

    content = head(
        R=R, path="", title=m["title"], description=m["description"], og_image=img_url("wp-content/uploads/2024/04/cropped-Asset-1-6k.png"),
        schema=home_schema(m["schema"]),
        preload=f'\n<link rel="preload" as="image" href="assets/images/bg/hero.webp" type="image/webp" fetchpriority="high">',
    ) + '\n<body class="page-home">' + header(R, "") + f"""
<main id="main">
  <section class="hero">
    <div class="hero__leaves" aria-hidden="true">
      {decor("elements-summer-sale-banner-NK5W2VA_leaf_2.png", R, "hero__leaf hero__leaf--1", 60)}
      {decor("elements-summer-sale-banner-NK5W2VA_leaf_2.png", R, "hero__leaf hero__leaf--2", 44)}
      {decor("elements-summer-sale-banner-NK5W2VA_leaf_2.png", R, "hero__leaf hero__leaf--3", 52)}
    </div>
    <div class="hero__inner">
      <div class="hero__box">
        <h1 class="hero__title" data-animate="fade-down" style="--delay:300ms">Welcome to Reflex Divinee</h1>
        <p data-animate="fade-up" style="--delay:400ms">Foot reflexology is a therapy based on the principle of ancient technique formulated by Sithar Thirumoolar that there are small and specific areas of innervation in the feet that correspond to specific muscle groups or organs of the body.</p>
        <div class="btn-row">
          <a class="btn" href="{WA_HERO}" target="_blank" rel="noopener" data-animate="fade-right" style="--delay:500ms" data-track="book_appointment">Book an Appointment</a>
          <a class="btn" href="{R}about-us/" data-animate="fade-left" style="--delay:500ms">Learn More</a>
        </div>
      </div>
    </div>
  </section>

  <section class="about-intro section">
    <div class="container two-col two-col--media-left">
      <div class="two-col__media" data-animate="fade-right">
        {picture("wp-content/uploads/2024/04/taking-pleasure-PY74FWE-1.jpg", "Relaxing foot reflexology session at Reflex Divine", R, sizes="(max-width: 767px) 100vw, 50vw", max_w=960)}
        {decor("elements-summer-sale-banner-NK5W2VA_leaf_2.png", R, "decor--about-leaf", 143)}
      </div>
      <div class="two-col__text" data-animate="fade-left">
        <p class="eyebrow">About Reflex Divinee</p>
        <h2>Who We Are</h2>
        <p>Here in Reflex Divine Bio-Acu Medical Care we heal people with various traditional therapies like Foot Reflexology, Varma, Electro Homeopathy, Ginger Therapy, Ayurveda Abhyanga Therapy, Moxibustion Therapy, Steaming Therapy, CLX Nutraceutical Therapy and much more Holistic Therapies.</p>
        <a class="btn" href="{R}about-us/">Know More</a>
      </div>
    </div>
    {decor("elements-summer-sale-banner-NK5W2VA_leafs.png", R, "decor--leafs-right", 90)}
    {decor("elements-summer-sale-banner-NK5W2VA_leafs_2.png", R, "decor--leafs-left", 76)}
  </section>

  <section class="doctor section section--cream">
    <div class="container two-col two-col--media-left">
      <div class="two-col__media doctor__media" data-animate="fade-right">
        {picture("wp-content/uploads/2025/06/dr-r-k-devapriyadharshini-bams.webp", "Dr. K. Devapriyadharshini, BAMS", R, sizes="(max-width: 767px) 100vw, 40vw", max_w=960)}
        {picture("wp-content/uploads/2024/04/Asset-1-6k.png", "", R, cls="doctor__badge", sizes="120px", max_w=480)}
      </div>
      <div class="two-col__text" data-animate="fade-left">
        <p class="eyebrow">at REFLEX DIVINE BIO ACU MEDICAL CARE</p>
        <h2>Foot Reflexology Treatment</h2>
        <p><strong>Treatment Offered:</strong><br><strong>Foot Reflexology</strong> – A deeply relaxing <strong>1-hour session</strong> that stimulates pressure points to improve circulation, relieve tension, and restore natural balance.</p>
        <p><strong>📍 Location:</strong><br><em>Prasanth Nivas</em>,<br>Near Aanavadhukal Temple, Railway Station Road, Mahe.</p>
        <p><strong>📞 Appointments:</strong><br>Call <a href="tel:+916380543415"><strong>+91 63805 43415</strong></a> to book.<br><em><strong>Note: Exclusively for Women • Treatment by Appointment Only</strong></em></p>
      </div>
    </div>
    {decor("elements-summer-sale-banner-NK5W2VA_leafs.png", R, "decor--leafs-right", 90)}
  </section>

  <section class="stats" aria-label="Reflex Divine in numbers">
    <div class="container stats__grid">{stat_html}</div>
  </section>

  <section class="therapies section">
    <div class="container">
      {section_heading("Our Therapies", "Our Most Popular Therapies")}
      <div class="therapy-grid">
        {therapy_img("wp-content/uploads/2024/04/image-1.jpg", "Foot reflexology treatment")}
        {therapy_card("foot-reflexology", "Foot Reflexology", "Healing through foot pressure points for overall wellness.", 0)}
        {therapy_img("wp-content/uploads/2024/04/varmatreatmentsimg.webp", "Varma treatment", 2)}
        {therapy_card("varma-treatment", "Varma", "Ancient Indian technique using vital points to heal and rejuvenate.", 100)}
        {therapy_card("electro-homeopathy", "Electro Homeopathy", "Natural remedies with electromagnetic properties for health.", 0)}
        {therapy_img("wp-content/uploads/2024/04/Picture1.png", "Electro homeopathy remedies", 0)}
        {therapy_card("ginger-therapy", "Ginger Therapy", "Therapeutic use of ginger for detox, pain relief, and vitality.", 100)}
        {therapy_img("wp-content/uploads/2024/04/14.Ginger-Therapy-1.jpg", "Ginger therapy", 0)}
      </div>
    </div>
  </section>

  <section class="reviews">
    <div class="container">
      <div class="section-head section-head--center" data-animate="fade-up">
        {picture("wp-content/uploads/2024/04/elements-spa-logo-template-H9V6JEB.png", "", R, cls="reviews__mark", sizes="47px", max_w=200)}
        <h2 class="section-head__title">What Our Client Says</h2>
      </div>
      {reviews_widget(R)}
    </div>
  </section>

  <section class="blog-teaser section">
    <div class="container">
      {section_heading("Our Blog", "Know more about foot relexology", sub_big=True)}
      <div class="post-grid post-grid--3">{blog_cards}</div>
      <p class="center"><a class="btn" href="{R}blog/">View More Blogs</a></p>
    </div>
  </section>

  <section class="cta section">
    <div class="container cta__inner">
      <h2 data-animate="fade-up">The Art Of Perfect Therapy</h2>
      <div class="cta__img" data-animate="zoom-in">{picture("wp-content/uploads/2024/04/11111111111-scaled.jpg", "Foot reflexology chart showing reflex points and corresponding body organs", R, sizes="(max-width: 767px) 100vw, 560px", max_w=1200)}</div>
      <a class="btn" href="{WA_HERO}" target="_blank" rel="noopener" data-track="book_appointment">Book An Appointment</a>
    </div>
  </section>
</main>""" + footer(R)
    write_page("", content)


def home_schema(schema):
    schema = schema_fix(schema)
    biz = {
        "@type": ["MedicalBusiness", "HealthAndBeautyBusiness"],
        "@id": f"{SITE_URL}/#business",
        "name": BRAND,
        "url": f"{SITE_URL}/",
        "logo": img_url("wp-content/uploads/2024/04/cropped-Asset-1-6k.png"),
        "image": img_url("wp-content/uploads/2024/04/taking-pleasure-PY74FWE-1.jpg"),
        "telephone": PHONE_IN_TEL,
        "email": EMAIL,
        "address": {"@type": "PostalAddress", "streetAddress": "Block - 1, No. 5, Viduthalai Nagar, Mudaliarpet",
                    "addressLocality": "Pondicherry", "addressCountry": "IN"},
        "priceRange": "₹500 - ₹1800",
        "aggregateRating": {"@type": "AggregateRating", "ratingValue": "5", "reviewCount": "67", "bestRating": "5"},
    }
    if schema:
        schema["@graph"].append(biz)
    return schema


def reviews_widget(R: str) -> str:
    stars = "".join(icon("star", R, "icon star") for _ in range(5))
    cards = []
    for name, date, text in REVIEWS:
        d = dt.date.fromisoformat(date)
        initials = "".join(w[0] for w in name.split()[:2]).upper()
        cards.append(f"""<li class="review-card" data-slide>
          <div class="review-card__head"><span class="review-card__avatar" aria-hidden="true">{initials}</span>
            <div><p class="review-card__name">{esc(name)}</p><p class="review-card__date">{d.day} {d.strftime('%B')} {d.year}</p></div>
            <span class="review-card__src" title="Posted on Google">{icon("google", R, "icon google")}</span></div>
          <div class="review-card__stars" role="img" aria-label="Rated 5 out of 5">{stars}</div>
          <p class="review-card__text">{esc(text)}</p></li>""")
    return f"""<div class="reviews-widget" data-carousel data-autoplay="6000">
      <div class="reviews-summary">
        <p class="reviews-summary__label">EXCELLENT</p>
        <div class="reviews-summary__stars" role="img" aria-label="5 out of 5 stars">{stars}</div>
        <p>Based on <strong>67 reviews</strong></p>
        <p class="reviews-summary__google">{icon("google", R, "icon google")} Google</p>
      </div>
      <div class="carousel">
        <button class="carousel__btn carousel__btn--prev" type="button" data-carousel-prev aria-label="Previous reviews">{icon("chevron-left", R)}</button>
        <ul class="carousel__track" data-carousel-track>{"".join(cards)}</ul>
        <button class="carousel__btn carousel__btn--next" type="button" data-carousel-next aria-label="Next reviews">{icon("chevron-right", R)}</button>
      </div>
    </div>"""


def post_card(p: dict, R: str, home: bool = False, idx: int = 0) -> str:
    img = picture(p["image"], p["image_alt"] or p["title"], R, sizes="(max-width: 767px) 100vw, (max-width: 1024px) 50vw, 380px", max_w=1600) if p["image"] else ""
    date = fmt_date(p["meta"]["published"])
    ex = excerpt(p["text"])
    url = f'{R}{p["slug"]}/'
    if home:
        return f"""<article class="post-card post-card--home" data-animate="fade-up">
      <a class="post-card__img" href="{url}" tabindex="-1" aria-hidden="true">{img}</a>
      <div class="post-card__body"><h3 class="post-card__title"><a href="{url}">{esc(p["title"])}</a></h3>
      <a class="btn btn--solid btn--sm" href="{url}">Read more<span class="sr-only">: {esc(p["title"])}</span></a></div></article>"""
    return f"""<article class="post-card" data-post data-index="{idx}">
      <a class="post-card__img" href="{url}" tabindex="-1" aria-hidden="true">{img}</a>
      <div class="post-card__body"><h3 class="post-card__title"><a href="{url}">{esc(p["title"])}</a></h3>
      <p class="post-card__date">{icon("calendar", R)}<time datetime="{p["meta"]["published"][:10]}">{date}</time></p>
      <p class="post-card__excerpt">{esc(ex)}</p></div></article>"""


def build_simple(slug: str, active: str, body_html_fn, banner_title: str | None = None, crumbs=False, R="../",
                 schema_override=None, body_class: str = "", extra_head: str = "") -> None:
    src = load(f"{slug}/index.html")
    m = meta_of(src)
    content = head(R=R, path=f"{slug}/", title=m["title"], description=m["description"],
                   og_image=img_url(re.sub(r"^(\.\./)+", "", m["og_image"])) if m["og_image"] and "uploads" in m["og_image"] else "",
                   schema=schema_override or schema_fix(m["schema"]), extra=extra_head) \
        + f'\n<body class="page-{body_class or slug.replace("/", "-")}">' + header(R, active) \
        + f'\n<main id="main">\n{banner(banner_title, R, crumbs) if banner_title else ""}\n{body_html_fn(src, R)}\n</main>' + footer(R)
    write_page(f"{slug}/", content)


def about_body(src, R):
    return f"""
  <section class="section">
    <div class="container two-col two-col--media-left">
      <div class="two-col__media" data-animate="fade-right">
        {picture("wp-content/uploads/2024/04/taking-pleasure-PY74FWE-1.jpg", "Holistic foot reflexology therapy", R, sizes="(max-width: 767px) 100vw, 50vw", max_w=960)}
        {decor("elements-summer-sale-banner-NK5W2VA_leaf_2.png", R, "decor--about-leaf", 143)}
      </div>
      <div class="two-col__text" data-animate="fade-left">
        <p class="eyebrow">About Reflex Divinee</p>
        <h2>Who We Are</h2>
        <p>Holistic medicine is a form of healing that considers the whole person — body, mind, spirit, and emotions — in the quest for optimal health and wellness. … A holistic practitioner may use all forms of health care, from conventional medication to alternative therapies, to treat a patient.</p>
      </div>
    </div>
    {decor("elements-summer-sale-banner-NK5W2VA_leafs.png", R, "decor--leafs-right", 90)}
  </section>
  <section class="section section--cream why-us">
    <div class="container narrow" data-animate="fade-up">
      <div class="section-head section-head--center"><p class="section-head__sub">Why Us</p><h2 class="section-head__title">Why Choose Reflex Divinee</h2></div>
      <p>Holistic medicine is a form of healing that considers the whole person — body, mind, spirit, and emotions — in the quest for optimal health and wellness. … A holistic practitioner may use all forms of health care, from conventional medication to alternative therapies, to treat a patient.</p>
      <p>People can achieve optimal health by gaining proper balance in life. … Holistic healing is beneficial for long-term health because it will not only help an existing problem but will help prevent other problems down the line. Treatments in holistic healing are designed to improve the body overall with a focus on health.</p>
      <p>Here in Reflex Divine Bio-Acu Medical Care we heal people with various traditional therapies like Foot Reflexology, Varma, Electro Homeopathy, Ginger Therapy, Ayurveda Abhyanga Therapy, Moxibustion Therapy, Steaming Therapy, CLX Nutraceutical Therapy and much more Holistic Therapies.</p>
    </div>
    {decor("elements-summer-sale-banner-NK5W2VA_leafs_2.png", R, "decor--leafs-left", 76)}
  </section>"""


def treatments_body(src, R):
    cards = "".join(f"""<article class="service-card" data-animate="fade-up" style="--delay:{(i % 3) * 100}ms">
        <a class="service-card__img" href="{slug}/" tabindex="-1" aria-hidden="true">{picture(img, title, R, sizes="(max-width: 767px) 100vw, (max-width: 1024px) 50vw, 380px", max_w=960)}</a>
        <div class="service-card__body"><h3>{title}</h3><p>{text}</p>
        <a class="link-arrow" href="{slug}/">View Details<span class="sr-only">: {title}</span> {icon("arrow-right", R)}</a></div></article>"""
                    for i, (slug, title, text, img) in enumerate(TREATMENTS))
    return f"""<section class="section"><div class="container">
      {section_heading("Our Services", "Our Most Popular Services")}
      <div class="service-grid">{cards}</div></div></section>"""


def build_treatment(slug: str, slugs: set[str]) -> None:
    R = "../../"
    src = load(f"treatments/{slug}/index.html")
    m = meta_of(src)
    h1 = text_of(src.select_one('[data-elementor-type="wp-page"] h1'))
    img = src.select_one('[data-elementor-type="wp-page"] [data-widget_type="image.default"] img')
    img_ref = re.sub(r"^(\.\./)+", "", img.get("data-lazy-src") or img["src"])
    body_el = src.select_one('[data-elementor-type="wp-page"] [data-widget_type="text-editor.default"] .elementor-widget-container')
    body = clean_content(body_el, R, slugs)
    if not body.lstrip().startswith("<"):
        body = f"<p>{body}</p>"
    others = "".join(f'<li><a href="{R}treatments/{s}/"{" aria-current=\"page\"" if s == slug else ""}>{t}</a></li>' for s, t, _, _ in TREATMENTS)
    content = head(R=R, path=f"treatments/{slug}/", title=m["title"], description=m["description"] or excerpt(text_of(body_el), 28),
                   og_image=img_url(img_ref), schema=schema_fix(m["schema"])) \
        + f'\n<body class="page-treatment">' + header(R, "treatments/") + f"""
<main id="main">
{banner(h1, R)}
<section class="section">
  <div class="container treatment">
    <div class="treatment__media" data-animate="fade-right">{picture(img_ref, h1, R, sizes="(max-width: 1024px) 100vw, 45vw", max_w=1200, lazy=False)}</div>
    <div class="treatment__text prose" data-animate="fade-left">{body}
      <p class="treatment__cta"><a class="btn btn--solid" href="{WA_PACKAGES}" target="_blank" rel="noopener" data-track="book_appointment">Book Now</a>
      <a class="btn" href="{R}packages/">View Packages</a></p>
    </div>
  </div>
</section>
<section class="section section--cream">
  <div class="container">
    <h2 class="h4 center">Other Treatments</h2>
    <ul class="treatment-links">{others}</ul>
  </div>
</section>
</main>""" + footer(R)
    write_page(f"treatments/{slug}/", content)


def packages_body(src, R):
    pk = [("Foot Reflexology", 700, "wp-content/uploads/2024/04/image-1.jpg"),
          ("Ginger Therapy", 500, "wp-content/uploads/2024/04/14.Ginger-Therapy-1.jpg"),
          ("Ayurveda Abhyanga Therapy", 1800, "wp-content/uploads/2024/04/varmatreatmentsimg.webp")]
    cards = "".join(f"""<article class="price-card" data-animate="fade-up" style="--delay:{i*120}ms">
      <figure class="price-card__img">{picture(img, t, R, sizes="(max-width: 767px) 100vw, 380px", max_w=960)}</figure>
      <h3 class="price-card__title">{t}</h3>
      <p class="price-card__from">starts from</p>
      <p class="price-card__price"><sup>₹</sup>{p}</p>
      <a class="btn btn--solid" href="{WA_PACKAGES}" target="_blank" rel="noopener" data-track="book_package">Book Now<span class="sr-only">: {t}</span></a>
    </article>""" for i, (t, p, img) in enumerate(pk))
    return f"""<section class="section"><div class="container">
      {section_heading("Packages", "Our Most Popular Packages")}
      <div class="price-grid">{cards}</div></div></section>"""


def gallery_body(src, R):
    links = src.select('[data-widget_type="gallery.default"] a[href]')
    items = []
    for i, a in enumerate(links):
        ref = re.sub(r"^(\.\./)+", "", a["href"])
        info = process_image(ref, 1600)
        alt = f"Reflex Divine gallery photo {i + 1}"
        items.append(f'<li><a href="{R}{info["src"]}" data-lightbox="gallery" data-index="{i}" aria-label="Open image {i + 1} of {len(links)}">'
                     f'{picture(ref, alt, R, sizes="(max-width: 767px) 50vw, 25vw", max_w=1600)}</a></li>')
    return f"""<section class="section"><div class="container">
      <ul class="gallery-grid" data-gallery>{"".join(items)}</ul></div></section>"""


def testimonials_body(src, R):
    vids = src.select('[data-widget_type="video.default"]')
    items = []
    for i, v in enumerate(vids):
        ref = re.sub(r"^(\.\./)+", "", v.find("video")["src"])
        dest = OUT / ref.replace("wp-content/uploads/", "assets/images/uploads/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC / ref, dest)
        rel = dest.relative_to(OUT).as_posix()
        items.append(f'<figure class="video-card" data-animate="fade-up"><video controls controlslist="nodownload" preload="metadata" playsinline src="{R}{rel}" aria-label="Client testimonial video {i + 1}"></video></figure>')
    return f"""<section class="section"><div class="container">
      <div class="video-grid">{"".join(items)}</div></div></section>"""


def contact_body(src, R):
    social = "".join(f'<li><a href="{u}" target="_blank" rel="noopener">{icon(i, R)}<span class="sr-only">{n}</span></a></li>' for n, i, u in SOCIAL)
    return f"""
<section class="section contact">
  <div class="container contact__grid">
    <div class="contact__info" data-animate="fade-right">
      <h2 class="h3">Get in Touch</h2>
      <p>Reach us by phone, email or WhatsApp, or send us a message using the form and we will get back to you.</p>
      <ul class="icon-list">
        <li>{icon("phone", R)}<span><strong>India:</strong> <a href="tel:{PHONE_IN_TEL}">{PHONE_IN}</a></span></li>
        <li>{icon("phone", R)}<span><strong>France:</strong> <a href="tel:{PHONE_FR_TEL}">{PHONE_FR}</a></span></li>
        <li>{icon("pin", R)}<span><strong>India:</strong> {ADDR_IN}</span></li>
        <li>{icon("pin", R)}<span><strong>France:</strong> {ADDR_FR}</span></li>
        <li>{icon("at", R)}<span><a href="mailto:{EMAIL}">{EMAIL}</a></span></li>
      </ul>
      <ul class="social-round">{social}</ul>
    </div>
    <div class="contact__form" data-animate="fade-left">
      <p class="eyebrow">Need Help? Send us a Message</p>
      <h2 class="h3">Send Us Your Message</h2>
      <form class="form" name="contact" method="post" action="{R}integrations/contact-form/send-mail.php" data-contact-form novalidate>
        <div class="form__hp" aria-hidden="true"><label>Leave this field empty<input type="text" name="company" tabindex="-1" autocomplete="off"></label></div>
        <div class="form__row">
          <label for="cf-name">Name</label>
          <input id="cf-name" name="name" type="text" placeholder="Name" autocomplete="name" maxlength="120">
        </div>
        <div class="form__row">
          <label for="cf-email">Email <span aria-hidden="true">*</span></label>
          <input id="cf-email" name="email" type="email" placeholder="Email" autocomplete="email" required maxlength="160">
        </div>
        <div class="form__row">
          <label for="cf-phone">Phone <span aria-hidden="true">*</span></label>
          <input id="cf-phone" name="phone" type="tel" placeholder="Phone" autocomplete="tel" required pattern="[0-9()#&+*=.\\s-]{{6,20}}" title="Only numbers and phone characters (#, -, *, etc) are accepted.">
        </div>
        <div class="form__row">
          <label for="cf-message">Message</label>
          <textarea id="cf-message" name="message" rows="5" placeholder="Message" maxlength="5000"></textarea>
        </div>
        <button class="btn btn--solid" type="submit">Send</button>
        <p class="form__status" role="status" aria-live="polite" data-form-status></p>
      </form>
    </div>
  </div>
</section>
<section class="map" aria-label="Map">
  <iframe title="Reflex Divine, Pondicherry on Google Maps" loading="lazy" referrerpolicy="no-referrer-when-downgrade"
    src="https://maps.google.com/maps?q=reflex%20divine%2C%20pondicherry&amp;t=m&amp;z=10&amp;output=embed&amp;iwloc=near"></iframe>
</section>"""


def build_blog(posts: list[dict]) -> None:
    R = "../"
    src = load("blog/index.html")
    m = meta_of(src)
    cards = "".join(post_card(p, R, idx=i) for i, p in enumerate(posts))
    body = f"""
{banner("Blog", R, crumbs=True)}
<section class="section"><div class="container">
  <form class="search-form search-form--inline" action="{R}search/" method="get" role="search">
    <label class="sr-only" for="blog-q">Search articles</label>
    <input id="blog-q" type="search" name="q" placeholder="Search articles…" autocomplete="off">
    <button class="btn btn--solid" type="submit">{icon("search", R)}<span class="sr-only">Search</span></button>
  </form>
  <div class="post-grid" data-paginate="{POSTS_PER_PAGE}">{cards}</div>
  <nav class="pager" aria-label="Blog pages" data-pager hidden>
    <button class="btn" type="button" data-pager-prev>Previous</button>
    <span class="pager__status" data-pager-status aria-live="polite"></span>
    <button class="btn" type="button" data-pager-next>Next</button>
  </nav>
</div></section>"""
    content = head(R=R, path="blog/", title=m["title"], description=m["description"] or "Articles on foot reflexology, Ayurveda and holistic therapies from Reflex Divine Bio-Acu Medical Care, Pondicherry.",
                   schema=schema_fix(m["schema"])) + '\n<body class="page-blog">' + header(R, "blog/") \
        + f'\n<main id="main">{body}\n</main>' + footer(R)
    write_page("blog/", content)


def build_post(p: dict, newer: dict | None, older: dict | None) -> None:
    R = "../"
    m = p["meta"]
    body = clean_content(p["body_el"], R, p["slugs"])
    url = f"{SITE_URL}/{p['slug']}/"
    share = [
        ("Facebook", "facebook", f"https://www.facebook.com/sharer/sharer.php?u={quote(url, safe='')}"),
        ("Twitter", "twitter", f"https://twitter.com/intent/tweet?url={quote(url, safe='')}&text={quote(p['title'], safe='')}"),
        ("LinkedIn", "linkedin", f"https://www.linkedin.com/sharing/share-offsite/?url={quote(url, safe='')}"),
        ("Telegram", "telegram", f"https://t.me/share/url?url={quote(url, safe='')}&text={quote(p['title'], safe='')}"),
        ("WhatsApp", "whatsapp", f"https://wa.me/?text={quote(p['title'] + ' ' + url, safe='')}"),
    ]
    share_html = "".join(f'<li><a href="{u}" target="_blank" rel="noopener" aria-label="Share on {n}">{icon(i, R)}</a></li>' for n, i, u in share)
    img = picture(p["image"], p["image_alt"] or p["title"], R, cls="post__featured", sizes="(max-width: 900px) 100vw, 860px", max_w=1600, lazy=False, priority=True) if p["image"] else ""
    nav = ""
    if newer or older:
        a = f'<a class="post-nav__prev" href="{R}{older["slug"]}/"><span>Previous article</span>{esc(older["title"])}</a>' if older else "<span></span>"
        b = f'<a class="post-nav__next" href="{R}{newer["slug"]}/"><span>Next article</span>{esc(newer["title"])}</a>' if newer else "<span></span>"
        nav = f'<nav class="post-nav" aria-label="More articles">{a}{b}</nav>'
    cats = "".join(f'<span class="post__cat">{esc(c)}</span>' for c in p["categories"])
    og = img_url(p["image"]) if p["image"] else ""
    content = head(R=R, path=f"{p['slug']}/", title=m["title"], description=m["description"] or excerpt(p["text"], 28),
                   og_type="article", og_image=og, schema=schema_fix(m["schema"]), published=m["published"], modified=m["modified"]) \
        + '\n<body class="page-post">' + header(R, "blog/") + f"""
<main id="main">
  <article class="post container narrow">
    <header class="post__header">
      <nav class="breadcrumbs" aria-label="Breadcrumb"><ol><li><a href="{R}">Home</a></li><li><a href="{R}blog/">Blog</a></li><li aria-current="page">{esc(p["title"])}</li></ol></nav>
      <h1 class="post__title">{esc(p["title"])}</h1>
      <p class="post__meta">{cats}<time datetime="{m["published"]}">{fmt_date(m["published"])}</time></p>
    </header>
    {img}
    <div class="post__content prose">{body}</div>
    <footer class="post__footer">
      <div class="share"><p class="share__title">Share This :</p><ul class="share__list">{share_html}</ul></div>
      <hr>
      <aside class="post-cta">
        <h2 class="h4">Have a question about this article?</h2>
        <p>Talk to our therapists — call <a href="tel:{PHONE_IN_TEL}">{PHONE_IN}</a> or message us on WhatsApp.</p>
        <p><a class="btn btn--solid" href="{WA_PACKAGES}" target="_blank" rel="noopener" data-track="book_appointment">Book an Appointment</a> <a class="btn" href="{R}contact/">Contact Us</a></p>
      </aside>
      {nav}
    </footer>
  </article>
</main>""" + footer(R)
    write_page(f"{p['slug']}/", content)


def build_search() -> None:
    R = "../"
    body = f"""
{banner("Search", R)}
<section class="section"><div class="container narrow">
  <form class="search-form" action="./" method="get" role="search" data-search-form>
    <label class="sr-only" for="q">Search the site</label>
    <input id="q" type="search" name="q" placeholder="Search treatments and articles…" autocomplete="off" data-search-input>
    <button class="btn btn--solid" type="submit">{icon("search", R)}<span class="sr-only">Search</span></button>
  </form>
  <p class="search-summary" role="status" aria-live="polite" data-search-summary></p>
  <ol class="search-results" data-search-results data-index="{R}assets/data/search-index.json" data-root="{R}"></ol>
</div></section>"""
    content = head(R=R, path="search/", title=f"Search | {SITE_NAME}", description="Search Reflex Divine treatments and articles.",
                   robots="noindex, follow") + '\n<body class="page-search">' + header(R, None) + f'\n<main id="main">{body}\n</main>' + footer(R)
    write_page("search/", content)


def build_404() -> None:
    # 404 is served from any depth, so it uses root-absolute URLs.
    R = "/"
    body = f"""
{banner("Page not found", R)}
<section class="section"><div class="container narrow center">
  <p>Sorry, the page you were looking for doesn’t exist or has moved.</p>
  <form class="search-form" action="/search/" method="get" role="search">
    <label class="sr-only" for="q404">Search the site</label>
    <input id="q404" type="search" name="q" placeholder="Search…">
    <button class="btn btn--solid" type="submit">{icon("search", R)}<span class="sr-only">Search</span></button>
  </form>
  <p><a class="btn" href="/">Back to Home</a> <a class="btn" href="/treatments/">Our Treatments</a> <a class="btn" href="/blog/">Read the Blog</a></p>
</div></section>"""
    content = head(R=R, path="404.html", title=f"Page not found | {SITE_NAME}", description="Page not found.", robots="noindex, follow") \
        + '\n<body class="page-404">' + header(R, None) + f'\n<main id="main">{body}\n</main>' + footer(R)
    (OUT / "404.html").write_text(content, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------
# SEO / server files
# --------------------------------------------------------------------------
def p_redirects() -> dict[str, str]:
    """Map WordPress ?p=<id> short links (HTTrack stubs) to clean slugs."""
    red = {}
    for f in SRC.glob("index*.html"):
        if f.name == "index.html":
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        a = re.search(r"Mirrored from https://reflexdivine\.com/\?p=(\d+)", t)
        b = re.search(r'URL=([^"]+?)index\.html"', t)
        if a and b:
            red[a.group(1)] = "/" + b.group(1)
    red.setdefault("62", "/")  # home page id (page-id-62)
    return dict(sorted(red.items(), key=lambda kv: int(kv[0])))


def write_server_files(posts: list[dict], sitemap_entries: list[tuple[str, str, str]]) -> None:
    red = p_redirects()
    # sitemap.xml
    urls = "\n".join(
        f"  <url><loc>{SITE_URL}/{loc}</loc><lastmod>{mod}</lastmod><priority>{pr}</priority></url>"
        for loc, mod, pr in sitemap_entries)
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n',
        encoding="utf-8", newline="\n")
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nDisallow: /search/\nDisallow: /integrations/\nDisallow: /tools/\nDisallow: /docs/\nDisallow: /dist/\n\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8", newline="\n")

    # Apache / LiteSpeed (.htaccess)
    p_rules = "\n".join(f"RewriteCond %{{QUERY_STRING}} (^|&)p={pid}(&|$)\nRewriteRule ^$ {dest}? [R=301,L]" for pid, dest in red.items())
    ht = f"""# Reflex Divine static site — generated by tools/build_site.py
Options -Indexes
DirectoryIndex index.html
ErrorDocument 404 /404.html
AddDefaultCharset utf-8

<IfModule mod_rewrite.c>
RewriteEngine On

# Force HTTPS and the bare domain
RewriteCond %{{HTTPS}} off [OR]
RewriteCond %{{HTTP_HOST}} ^www\\. [NC]
RewriteRule ^ https://reflexdivine.com%{{REQUEST_URI}} [R=301,L]

# WordPress short links (?p=ID) -> permalinks
{p_rules}

# WordPress search (?s=term) -> static search page
RewriteCond %{{QUERY_STRING}} (^|&)s=([^&]*)
RewriteRule ^$ /search/?q=%2 [R=301,L,NE]

# Old blog pagination and feeds
RewriteRule ^page/[0-9]+/?$ /blog/ [R=301,L]
RewriteRule ^(feed|comments/feed)/?$ /blog/ [R=301,L]
RewriteRule ^(.+)/feed/?$ /$1/ [R=301,L]
RewriteRule ^category/.*$ /blog/ [R=301,L]
RewriteRule ^author/.*$ /blog/ [R=301,L]

# Old media URLs -> new asset location
RewriteRule ^wp-content/uploads/(.*)$ /assets/images/uploads/$1 [R=301,L]

# WordPress endpoints that no longer exist
RewriteRule ^(wp-admin|wp-login\\.php|xmlrpc\\.php|wp-json|wp-includes|wp-content)(/.*)?$ - [G,L]

# Never serve build tooling, docs or the packaged ZIP
RewriteRule ^(tools|docs|dist)(/.*)?$ - [F,L]
</IfModule>

<IfModule mod_headers.c>
Header always set X-Content-Type-Options "nosniff"
Header always set Referrer-Policy "strict-origin-when-cross-origin"
Header always set X-Frame-Options "SAMEORIGIN"
Header always set Permissions-Policy "camera=(), microphone=(), geolocation=()"
Header always set Strict-Transport-Security "max-age=31536000"
<FilesMatch "\\.(css|js|woff2|webp|jpe?g|png|svg|mp4|ico)$">
Header set Cache-Control "public, max-age=31536000, immutable"
</FilesMatch>
<FilesMatch "\\.(html|xml|txt|json)$">
Header set Cache-Control "public, max-age=600"
</FilesMatch>
</IfModule>

<IfModule mod_deflate.c>
AddOutputFilterByType DEFLATE text/html text/css application/javascript application/json image/svg+xml text/xml application/xml text/plain
</IfModule>

<IfModule mod_mime.c>
AddType image/webp .webp
AddType font/woff2 .woff2
</IfModule>
"""
    (OUT / ".htaccess").write_text(ht, encoding="utf-8", newline="\n")

    # Netlify / Cloudflare Pages (_redirects)
    lines = ["# Generated by tools/build_site.py — Netlify / Cloudflare Pages redirects"]
    lines += [f"/  p={pid}  {dest}  301" for pid, dest in red.items()]
    lines += ["/  s=:q  /search/?q=:q  301",
              "/page/*  /blog/  301", "/feed  /blog/  301", "/feed/  /blog/  301",
              "/category/*  /blog/  301", "/author/*  /blog/  301",
              "/wp-content/uploads/*  /assets/images/uploads/:splat  301",
              "/wp-admin/*  /  301", "/wp-login.php  /  301", "/xmlrpc.php  /  410",
              "/tools/*  /404.html  404", "/docs/*  /404.html  404", "/dist/*  /404.html  404"]
    (OUT / "_redirects").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    # nginx snippet for reference
    ng = ["# nginx equivalent — include inside the server {} block", "error_page 404 /404.html;",
          "location ~ ^/(tools|docs|dist)/ { return 404; }",
          "location ^~ /wp-content/uploads/ { rewrite ^/wp-content/uploads/(.*)$ /assets/images/uploads/$1 permanent; }",
          "location ~ ^/page/[0-9]+/?$ { return 301 /blog/; }",
          "location = / {"]
    ng += [f"  if ($arg_p = {pid}) {{ return 301 {dest}; }}" for pid, dest in red.items()]
    ng += ["  if ($arg_s) { return 301 /search/?q=$arg_s; }", "  try_files /index.html =404;", "}"]
    (OUT / "integrations" / "server").mkdir(parents=True, exist_ok=True)
    (OUT / "integrations" / "server" / "nginx.conf").write_text("\n".join(ng) + "\n", encoding="utf-8", newline="\n")
    (OUT / "integrations" / "server" / "redirect-map.json").write_text(json.dumps(red, indent=2), encoding="utf-8", newline="\n")


def write_search_index(posts: list[dict]) -> None:
    items = [{"t": "Home", "u": "", "d": "Foot reflexology and holistic therapies in Pondicherry.", "k": "page"},
             {"t": "About Us", "u": "about-us/", "d": "Holistic healing and reflexology experts in Pondicherry.", "k": "page"},
             {"t": "Treatments", "u": "treatments/", "d": "All our reflexology, Ayurvedic and holistic treatments.", "k": "page"},
             {"t": "Packages", "u": "packages/", "d": "Foot Reflexology from ₹700, Ginger Therapy from ₹500, Ayurveda Abhyanga from ₹1800.", "k": "page"},
             {"t": "Gallery", "u": "gallery/", "d": "Photos from Reflex Divine.", "k": "page"},
             {"t": "Testimonials", "u": "testimonials/", "d": "Client video testimonials and Google reviews.", "k": "page"},
             {"t": "Contact", "u": "contact/", "d": "Phone, email, addresses in India and France, contact form.", "k": "page"}]
    for slug, title, text, _ in TREATMENTS:
        items.append({"t": title, "u": f"treatments/{slug}/", "d": text, "k": "treatment"})
    for p in posts:
        items.append({"t": p["title"], "u": f"{p['slug']}/", "d": excerpt(p["text"], 26),
                      "k": "article", "dt": p["meta"]["published"][:10], "b": " ".join(p["text"].split()[:400])})
    (OUT / "assets/data").mkdir(parents=True, exist_ok=True)
    (OUT / "assets/data/search-index.json").write_text(json.dumps(items, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def copy_static_assets() -> None:
    fonts = OUT / "assets/fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    gf = SRC / "wp-content/uploads/elementor/google-fonts/fonts"
    mapping = {
        "marcellus-latin.woff2": "marcellus-weo_ebrok8hqldviaf81vvok.woff2",
        "marcellus-latin-ext.woff2": "marcellus-weo_ebrok8hqldviaf81wpok7es.woff2",
        "poppins-300-latin.woff2": "poppins-pxibyp8kv8jhgfvrldz8z1xlfq.woff2",
        "poppins-400-latin.woff2": "poppins-pxieyp8kv8jhgfvrjjfecg.woff2",
        "poppins-400-latin-ext.woff2": "poppins-pxieyp8kv8jhgfvrjjnecmne.woff2",
        "poppins-400i-latin.woff2": "poppins-pxigyp8kv8jhgfvrjjluchta.woff2",
        "poppins-500-latin.woff2": "poppins-pxibyp8kv8jhgfvrlgt9z1xlfq.woff2",
        "poppins-600-latin.woff2": "poppins-pxibyp8kv8jhgfvrlej6z1xlfq.woff2",
        "poppins-700-latin.woff2": "poppins-pxibyp8kv8jhgfvrlcz7z1xlfq.woff2",
    }
    for new, old in mapping.items():
        shutil.copy2(gf / old, fonts / new)
    ic = OUT / "assets/icons"
    up = SRC / "wp-content/uploads/2024/04"
    shutil.copy2(up / "cropped-Asset-1-6k-32x32.png", ic / "favicon-32x32.png")
    shutil.copy2(up / "cropped-Asset-1-6k-192x192.png", ic / "favicon-192x192.png")
    shutil.copy2(up / "cropped-Asset-1-6k-180x180.png", ic / "apple-touch-icon.png")
    Image.open(up / "cropped-Asset-1-6k.png").save(ic / "og-default.png", optimize=True)
    # ICO for legacy /favicon.ico requests
    Image.open(up / "cropped-Asset-1-6k-192x192.png").save(OUT / "favicon.ico", sizes=[(32, 32), (48, 48)])
    # CSS background images
    bg_image("wp-content/uploads/2024/04/spa-salon-therapy-treatment-PZURJ69.jpg", "hero")
    bg_image("wp-content/uploads/2024/04/Untitled-design-8-1024x576-1.png", "hero-overlay", 1024)
    bg_image("wp-content/uploads/2024/04/spa-setting-PT7UYC2.jpg", "stats")
    bg_image("wp-content/uploads/2024/04/spa-salon-therapy-treatment-PZURJ69_2.jpg", "reviews")
    bg_image("wp-content/uploads/2024/04/dried-and-fresh-chamomile-flowers-and-leaves-on-PA55XK8.jpg", "banner")
    bg_image("wp-content/uploads/2024/04/bg-contact-3green@2x.png", "contact-green", 1200)


def clean_output() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.iterdir():
        if p.name in PRESERVE or p.name.startswith("."):
            if p.name == "assets":
                for a in p.iterdir():
                    if a.name not in PRESERVE_ASSETS:
                        shutil.rmtree(a) if a.is_dir() else a.unlink()
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    for f in (".htaccess",):
        if (OUT / f).exists():
            (OUT / f).unlink()


# --------------------------------------------------------------------------
def main() -> None:
    log(f"SRC={SRC}\nOUT={OUT}")
    if OUT == SRC:
        sys.exit("OUT must differ from SRC")
    clean_output()
    copy_static_assets()
    post_slugs, page_slugs = discover()
    log(f"posts={len(post_slugs)} pages={page_slugs}")
    all_slugs = set(post_slugs) | set(page_slugs)
    posts = extract_posts(post_slugs)
    by_slug = {p["slug"]: p for p in posts}

    build_home(by_slug)
    build_simple("about-us", "about-us/", about_body, "About Us")
    build_simple("treatments", "treatments/", treatments_body, "Treatments")
    for slug, *_ in TREATMENTS:
        build_treatment(slug, all_slugs)
    build_simple("packages", "packages/", packages_body, "Packages")
    build_simple("gallery", "gallery/", gallery_body, "Gallery")
    build_simple("testimonials", "testimonials/", testimonials_body, "Testimonials")
    build_simple("contact", "contact/", contact_body, "Contact Us")
    build_blog(posts)
    for i, p in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i + 1 < len(posts) else None
        build_post(p, newer, older)
    build_search()
    build_404()

    # sitemap entries
    def mod(rel):
        mm = meta_of(load(rel))
        return (mm["modified"] or BUILD_DATE)[:10]
    entries = [("", mod("index.html"), "1.0")]
    for s in ["about-us", "treatments", "packages", "gallery", "testimonials", "contact", "blog"]:
        entries.append((f"{s}/", mod(f"{s}/index.html"), "0.8"))
    for slug, *_ in TREATMENTS:
        entries.append((f"treatments/{slug}/", mod(f"treatments/{slug}/index.html"), "0.7"))
    for p in posts:
        entries.append((f"{p['slug']}/", (p["meta"]["modified"] or p["meta"]["published"])[:10], "0.6"))
    write_server_files(posts, entries)
    write_search_index(posts)
    n_img = sum(1 for _ in (OUT / "assets/images").rglob("*") if _.is_file())
    log(f"done: {len(PAGES_WRITTEN)} pages, {len(posts)} posts, {n_img} image files")


if __name__ == "__main__":
    main()
