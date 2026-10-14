#!/usr/bin/env python3
"""
Static checks for the generated site:
  - every internal href/src/srcset resolves to a file
  - no leftover WordPress paths (wp-content, wp-includes, wp-json, index.html links, shortcodes)
  - one <h1>, <title>, meta description, canonical per page; unique ids; img alt present
  - sitemap URLs exist; JSON-LD parses
Usage: python tools/validate_site.py [site_dir]
Exit code 1 if any error is found.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent).resolve()
SITE = "https://reflexdivine.com"
SKIP_DIRS = {"tools", "docs", "integrations"}
errors, warnings = [], []


def resolve(page: Path, ref: str) -> Path | None:
    ref = unquote(ref.split("#")[0].split("?")[0])
    if not ref:
        return None
    base = ROOT if ref.startswith("/") else page.parent
    target = (base / ref.lstrip("/")).resolve()
    if ref.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target


pages = [p for p in ROOT.rglob("*.html") if not (set(p.relative_to(ROOT).parts) & SKIP_DIRS)]
titles, descs = Counter(), Counter()
for page in pages:
    rel = page.relative_to(ROOT).as_posix()
    raw = page.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "lxml")
    for bad in ("wp-content", "wp-includes", "wp-json", "elementor", "[vc_", "[/", "xmlrpc", "recaptcha.cloud"):
        if bad in raw and not (bad == "[/" and "[/\\]" in raw):
            if bad == "elementor" and "elementor" not in raw.lower().split("<body", 1)[-1]:
                continue
            errors.append(f"{rel}: leftover WordPress reference '{bad}'")
    if re.search(r'href="[^"]*index\.html"', raw) and rel != "404.html":
        errors.append(f"{rel}: link to index.html (should be clean URL)")
    h1 = soup.find_all("h1")
    if len(h1) != 1:
        errors.append(f"{rel}: {len(h1)} <h1> elements")
    t = soup.title.get_text(strip=True) if soup.title else ""
    d = soup.find("meta", attrs={"name": "description"})
    c = soup.find("link", rel="canonical")
    if not t:
        errors.append(f"{rel}: missing <title>")
    if not d or not d.get("content"):
        errors.append(f"{rel}: missing meta description")
    if not c or not c.get("href", "").startswith(SITE):
        errors.append(f"{rel}: missing/relative canonical")
    titles[t] += 1
    if d:
        descs[d.get("content")] += 1
    ids = Counter(e["id"] for e in soup.find_all(id=True))
    for i, n in ids.items():
        if n > 1:
            errors.append(f"{rel}: duplicate id '{i}'")
    for img in soup.find_all("img"):
        if img.get("alt") is None:
            errors.append(f"{rel}: <img> without alt: {img.get('src')}")
        if not img.get("width") and img.get("class") != ["lightbox__img"]:
            warnings.append(f"{rel}: <img> without width/height: {img.get('src')}")
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            json.loads(s.string)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{rel}: invalid JSON-LD ({e})")
    refs = []
    for tag, attr in (("a", "href"), ("link", "href"), ("img", "src"), ("script", "src"), ("video", "src"), ("source", "srcset"), ("use", "href"), ("form", "action")):
        for el in soup.find_all(tag):
            v = el.get(attr)
            if not v:
                continue
            if attr == "srcset":
                refs += [x.strip().split(" ")[0] for x in v.split(",")]
            else:
                refs.append(v)
    for ref in refs:
        u = urlparse(ref)
        if u.scheme in ("http", "https", "mailto", "tel", "data") or ref.startswith("#"):
            if ref.startswith(SITE):
                tgt = resolve(ROOT / "index.html", "/" + ref[len(SITE):].lstrip("/"))
                if tgt and not tgt.exists():
                    errors.append(f"{rel}: absolute site URL not found {ref}")
            continue
        tgt = resolve(page, ref)
        if tgt and not tgt.exists():
            errors.append(f"{rel}: broken reference {ref}")

for t, n in titles.items():
    if n > 1 and "Page not found" not in t:
        warnings.append(f"duplicate <title> x{n}: {t}")
for d, n in descs.items():
    if n > 1:
        warnings.append(f"duplicate meta description x{n}: {d[:70]}")

# sitemap
sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
for loc in locs:
    tgt = resolve(ROOT / "index.html", "/" + loc[len(SITE):].lstrip("/"))
    if tgt is None:
        tgt = ROOT / "index.html"
    if not tgt.exists():
        errors.append(f"sitemap: {loc} has no page")

# CSS url() references
for css in (ROOT / "assets/css").glob("*.css"):
    for ref in re.findall(r"url\(([^)]+)\)", css.read_text(encoding="utf-8")):
        ref = ref.strip("'\"")
        if ref.startswith("data:"):
            continue
        if not (css.parent / ref).resolve().exists():
            errors.append(f"{css.name}: missing {ref}")

print(f"Checked {len(pages)} HTML pages, {len(locs)} sitemap URLs")
for w in sorted(set(warnings)):
    print("WARN ", w)
for e in sorted(set(errors)):
    print("ERROR", e)
print(f"{len(set(errors))} errors, {len(set(warnings))} warnings")
sys.exit(1 if errors else 0)
