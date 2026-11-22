#!/usr/bin/env python3
"""Delpher (Dutch historic newspapers, KB) helper: search, read, and cut clippings.

Delpher can be searched without a key through the KB's SRU service. This script wraps it:

  search  <CQL query>              list articles: date, paper, title, page, urn
  text    <urn>                    the OCR text of an article
  locate  <urn> <words>            find the words on the article's page and write a WIDE crop with a
                                   ruler in page coordinates (pixels of the full scan). Look at it at
                                   true size, read the clipping's edges off the ruler, then:
  cut     <urn> <x0,y0,x1,y1>      cut exactly that box from the page scan (at least --min-width px wide)

<urn> may be an article urn (MMKB04:000139340:mpeg21:a0065), a page urn (...:p011), or a resolver or
Delpher link containing one. Cutting automatically between the separator lines proved unreliable, so
the edges are chosen by looking at the ruler crop, on purpose.

Examples:
  python3 -I delpher.py search '"Restaurant Royal" AND Kneuterdijk' --from 1910 --to 1920
  python3 -I delpher.py text MMKB04:000139340:mpeg21:a0065
  python3 -I delpher.py locate MMKB04:000139340:mpeg21:a0065 "Restaurant Royal" --out /tmp/look.jpg
  python3 -I delpher.py cut MMKB04:000139340:mpeg21:a0065 250,2880,905,3130 --out clipping.jpg --check

Standard library + Pillow. JPEG 2000 scans: Pillow if it can read them, else macOS `sips`.
Old newspapers are usually public domain; check Delpher's terms for the paper.
"""
import argparse
import collections
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


_LIVE = []


def live(kind, **fields):
    """Tell a running Workshop (live.py serve) what happens. Does nothing when none is running."""
    try:
        if not _LIVE:
            import importlib.util
            spec = importlib.util.spec_from_file_location("ftr_live", os.path.join(os.path.dirname(os.path.abspath(__file__)), "live.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _LIVE.append(mod.emit)
        _LIVE[0](kind, **fields)
    except Exception:
        pass

SRU = ("https://jsru.kb.nl/sru/sru?version=1.2&operation=searchRetrieve&x-collection=DDD_artikel"
       "&recordSchema=ddd&maximumRecords={n}&startRecord={start}&query={q}")
RESOLVER = "http://resolver.kb.nl/resolve?urn="
UA = "family-tree-research (genealogy plugin; https://github.com/chriswaalberg/family-tree-research)"
NS = {"srw": "http://www.loc.gov/zing/srw/", "dc": "http://purl.org/dc/elements/1.1/", "ddd": "http://www.kb.nl/ddd"}
URN = re.compile(r"([A-Za-z]+\d*:[\w.]+:mpeg21)(?::([ap]\d{3,5}))?")

CROP_W, CROP_H = 1400, 1000    # default size of the locate crop, in page pixels (true size: about one screen)
MARGIN = 70                    # ruler margin around the crop, in output pixels
MIN_WIDTH = 1000               # a clipping must stay readable on a phone at full width


def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def cache_dir(a):
    d = a.cache or os.path.join(tempfile.gettempdir(), "delpher-cache")
    os.makedirs(d, exist_ok=True)
    return d


def cached(a, name, url):
    p = os.path.join(cache_dir(a), name.replace(":", "_"))
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        data = fetch(url)
        with open(p + ".part", "wb") as fh: fh.write(data)
        os.replace(p + ".part", p)
    return p


def parse_urn(s):
    """-> (issue urn, 'a...' or 'p...' or None)"""
    m = URN.search(urllib.parse.unquote(s))
    if not m: sys.exit(f"No Delpher urn found in: {s}")
    return m.group(1), m.group(2)


def sru(query, n=20, start=1):
    root = ET.fromstring(fetch(SRU.format(n=n, start=start, q=urllib.parse.quote(query))))
    total = int(root.findtext("srw:numberOfRecords", "0", NS) or 0)
    out = []
    for rec in root.iterfind(".//srw:recordData", NS):
        g = lambda t: (rec.findtext(t, "", NS) or "").strip()
        out.append({"date": g("dc:date")[:10].replace("/", "-"), "paper": g("ddd:papertitle"), "title": g("dc:title"),
                    "page": g("ddd:page"), "pageurl": g("ddd:pageurl"), "urn": g("ddd:metadataKey")})
    return total, out


def page_of(a, issue, part):
    """The page (p...) of an article: from SRU, else the page named most often on the Delpher article page."""
    if a.page: return a.page if a.page.startswith("p") else "p" + a.page
    if part and part.startswith("p"): return part
    if not part: sys.exit("Give an article urn (...:a0065) or a page urn (...:p011), not only the newspaper issue.")
    try:
        _, recs = sru(f'metadataKey="{issue}:{part}"', n=1)
        if recs and recs[0]["pageurl"]:
            return recs[0]["pageurl"].rsplit(":", 1)[1]
    except Exception as e:
        print(f"  (SRU lookup of the page failed: {e}; reading the article page instead)", file=sys.stderr)
    html = fetch(RESOLVER + f"{issue}:{part}").decode("utf-8", "replace")
    pages = collections.Counter(re.findall(re.escape(issue) + r":(p\d{3,5})\b", html))
    if not pages: sys.exit("Could not find the page of this article; pass it with --page p011.")
    return pages.most_common(1)[0][0]


def open_scan(a, issue, page):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    jp2 = cached(a, f"{issue}:{page}.jp2", RESOLVER + f"{issue}:{page}:image")
    try:
        im = Image.open(jp2); im.load(); return im.convert("RGB")
    except Exception:
        jpg = jp2[:-4] + ".jpg"
        if not os.path.exists(jpg):
            if not shutil.which("sips"): sys.exit("Pillow cannot read JPEG 2000 here and `sips` (macOS) is missing.")
            subprocess.run(["sips", "-s", "format", "jpeg", jp2, "--out", jpg], check=True, capture_output=True)
        return Image.open(jpg).convert("RGB")


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def alto_lines(a, issue, page):
    root = ET.parse(cached(a, f"{issue}:{page}.alto.xml", RESOLVER + f"{issue}:{page}:alto")).getroot()
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    pg = root.find(f".//{ns}Page")
    size = (int(float(pg.get("WIDTH"))), int(float(pg.get("HEIGHT")))) if pg is not None and pg.get("WIDTH") else None
    lines = []
    for tl in root.iter(f"{ns}TextLine"):
        words = [s.get("SUBS_CONTENT") if s.get("SUBS_TYPE") == "HypPart1" else s.get("CONTENT", "")
                 for s in tl.iter(f"{ns}String") if s.get("SUBS_TYPE") != "HypPart2"]
        x, y, w, h = [int(float(tl.get(k, 0))) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")]
        lines.append({"text": " ".join(w_ for w_ in words if w_), "box": (x, y, x + w, y + h)})
    return lines, size


def ruler_image(im, box, zoom, marks=(), grid=True, cut=None):
    """The crop `box` of `im` (page pixels), scaled by zoom, in a white margin with a ruler in page coordinates.
    Every number sits centred on its tick (read the line, not the side of the number); `grid` adds faint lines every
    100 px, with their numbers on the print too (read positions off those numbers, never off the image's own pixels: the image
    has a margin, so its pixels are about MARGIN px off). `marks` (page boxes) are red bars in the top and left margins.
    `cut` (a page box): everything outside it is veiled and it gets a thin red outline, so you see exactly what a cut takes."""
    from PIL import Image, ImageDraw, ImageFont
    x0, y0, x1, y1 = box
    crop = im.crop(box)
    if zoom != 1: crop = crop.resize((max(1, round(crop.width * zoom)), max(1, round(crop.height * zoom))), Image.LANCZOS)
    W, H = crop.width + 2 * MARGIN, crop.height + 2 * MARGIN
    out = Image.new("RGB", (W, H), "white"); out.paste(crop, (MARGIN, MARGIN))
    d = ImageDraw.Draw(out)
    try: font = ImageFont.load_default(size=16)
    except TypeError: font = ImageFont.load_default()
    step = 10 if zoom >= 0.6 else 50
    sx = lambda x: MARGIN + (x - x0) * zoom
    sy = lambda y: MARGIN + (y - y0) * zoom

    def label(cx, cy, txt):  # centred on (cx, cy): the number sits exactly on its tick
        l, t, r, b = d.textbbox((0, 0), txt, font=font)
        d.text((cx - (r - l) / 2 - l, cy - (b - t) / 2 - t), txt, fill="black", font=font)

    if grid:  # faint lines every 100 page pixels over the print, to read edges against
        over = Image.new("RGBA", out.size, (0, 0, 0, 0)); g = ImageDraw.Draw(over)
        for x in range((x0 // 100 + 1) * 100, x1, 100): g.line([(sx(x), MARGIN), (sx(x), H - MARGIN)], fill=(0, 120, 255, 90))
        for y in range((y0 // 100 + 1) * 100, y1, 100): g.line([(MARGIN, sy(y)), (W - MARGIN, sy(y))], fill=(0, 120, 255, 90))
        out.paste(Image.alpha_composite(out.convert("RGBA"), over).convert("RGB")); d = ImageDraw.Draw(out)
        try: small = ImageFont.load_default(size=13)
        except TypeError: small = font
        def tag(cx, cy, txt):  # a small number on the print, on a white chip
            l, t_, r, b = d.textbbox((0, 0), txt, font=small); w, h = r - l, b - t_
            d.rectangle([cx - w / 2 - 3, cy - h / 2 - 2, cx + w / 2 + 3, cy + h / 2 + 2], fill=(255, 255, 255))
            d.text((cx - w / 2 - l, cy - h / 2 - t_), txt, fill=(0, 90, 200), font=small)
        for x in range((x0 // 100 + 1) * 100, x1, 100): tag(sx(x), MARGIN + 10, str(x))
        for y in range((y0 // 100 + 1) * 100, y1, 100): tag(MARGIN + 18, sy(y), str(y))
    for x in range((x0 // step + 1) * step, x1, step):
        L = 22 if x % 100 == 0 else 12 if x % 50 == 0 else 6
        d.line([(sx(x), MARGIN), (sx(x), MARGIN - L)], fill="black")
        d.line([(sx(x), H - MARGIN), (sx(x), H - MARGIN + L)], fill="black")
        if x % 100 == 0:
            label(sx(x), 20, str(x)); label(sx(x), H - 20, str(x))
    for y in range((y0 // step + 1) * step, y1, step):
        L = 22 if y % 100 == 0 else 12 if y % 50 == 0 else 6
        d.line([(MARGIN, sy(y)), (MARGIN - L, sy(y))], fill="black")
        d.line([(W - MARGIN, sy(y)), (W - MARGIN + L, sy(y))], fill="black")
        if y % 100 == 0:
            label(MARGIN - 45, sy(y), str(y)); label(W - MARGIN + 45, sy(y), str(y))
    if cut:
        cx0, cy0, cx1, cy1 = sx(cut[0]), sy(cut[1]), sx(cut[2]), sy(cut[3])
        veil = Image.new("RGBA", out.size, (0, 0, 0, 0)); v = ImageDraw.Draw(veil)
        for r in ([MARGIN, MARGIN, W - MARGIN, cy0], [MARGIN, cy1, W - MARGIN, H - MARGIN], [MARGIN, cy0, cx0, cy1], [cx1, cy0, W - MARGIN, cy1]):
            if r[2] > r[0] and r[3] > r[1]: v.rectangle(r, fill=(255, 255, 255, 170))
        out.paste(Image.alpha_composite(out.convert("RGBA"), veil).convert("RGB")); d = ImageDraw.Draw(out)
        d.rectangle([cx0, cy0, cx1, cy1], outline="red", width=2)
    for (mx0, my0, mx1, my1) in marks:
        d.line([(sx(max(mx0, x0)), MARGIN - 4), (sx(min(mx1, x1)), MARGIN - 4)], fill="red", width=4)
        d.line([(MARGIN - 4, sy(max(my0, y0))), (MARGIN - 4, sy(min(my1, y1)))], fill="red", width=4)
    d.rectangle([MARGIN - 1, MARGIN - 1, W - MARGIN, H - MARGIN], outline="gray")
    return out


def cmd_search(a):
    q = a.query
    if a.van or a.tot:
        q = f'({q}) AND date within "{a.van or 1600}-01-01 {a.tot or 2100}-12-31"'
    total, recs = sru(q, n=a.max, start=a.start)
    live("result", source="Delpher", q=a.query, n=total)
    print(f"{total} article(s) for: {q}" + (f"  (showing {a.start}-{a.start + len(recs) - 1})" if recs else ""))
    for r in recs:
        print(f"{r['date']}  {r['paper'][:40]:<40}  p.{r['page']:<3} {r['title'][:60]}\n            {r['urn']}")


def cmd_text(a):
    issue, part = parse_urn(a.urn)
    if not part or not part.startswith("a"): sys.exit("text needs an article urn (...:a0065).")
    root = ET.fromstring(fetch(RESOLVER + f"{issue}:{part}:ocr"))
    paras = [" ".join(e.itertext()).strip() for e in root]
    print("\n\n".join(p for p in paras if p))
    print(f"\nSource: {RESOLVER}{issue}:{part}")


def cmd_locate(a):
    issue, part = parse_urn(a.urn)
    page = page_of(a, issue, part)
    lines, size = alto_lines(a, issue, page)
    q = norm(a.words)
    hits = [l for l in lines if q and q in norm(l["text"])]
    if not hits:
        sys.exit(f"\"{a.words}\" not found on {issue}:{page} (the OCR may misspell it: try one word, or another page with --page).")
    print(f"Page {issue}:{page}" + (f", {size[0]} x {size[1]} px" if size else "") + f": {len(hits)} line(s) with \"{a.words}\"")
    for j, l in enumerate(hits, 1):
        print(f"  {j}. box {','.join(map(str, l['box']))}  {l['text'][:90]}")
    h = hits[min(max(a.hit, 1), len(hits)) - 1]
    im = open_scan(a, issue, page)
    W, H = im.size
    cx, cy = ((h["box"][0] + h["box"][2]) // 2, (h["box"][1] + h["box"][3]) // 2)
    if a.at:
        cx, cy = [int(v) for v in a.at.split(",")]
    x0 = max(0, min(W - a.width, cx - a.width // 2)); y0 = max(0, min(H - a.height, cy - a.height // 2))
    box = (x0, y0, min(W, x0 + a.width), min(H, y0 + a.height))
    out = a.out or os.path.join(cache_dir(a), f"locate-{issue}-{page}.jpg".replace(":", "_"))
    ruler_image(im, box, a.zoom, [h["box"]], grid=not a.no_grid).save(out, quality=90)
    print(f"Wide crop around hit {a.hit} (page box {','.join(map(str, box))}, zoom {a.zoom}), ruler in page pixels:\n  {out}")
    print("Look at it at true size and read the clipping's edges (heading to last relevant line, column rules) off the ruler's\n"
          f"NUMBERS (also on the print, every 100 px), not off the image's own pixel positions: the image has a {MARGIN} px margin.\n"
          f"Move or widen the view with --at x,y / --width / --height / --zoom 0.5. Then:\n"
          f"  delpher.py cut {issue}:{part or page} x0,y0,x1,y1 --out <file.jpg> --check")


def cmd_cut(a):
    issue, part = parse_urn(a.urn)
    page = page_of(a, issue, part)
    try: x0, y0, x1, y1 = [int(v) for v in a.box.split(",")]
    except ValueError: sys.exit("The box is x0,y0,x1,y1 in page pixels, e.g. 300,2450,920,2800")
    im = open_scan(a, issue, page)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(im.width, x1), min(im.height, y1)
    if x1 <= x0 or y1 <= y0: sys.exit("Empty box.")
    from PIL import Image
    c = im.crop((x0, y0, x1, y1))
    if c.width < a.min_width:
        c = c.resize((a.min_width, round(c.height * a.min_width / c.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    c.save(a.out, quality=92)
    print(f"Clipping {c.width} x {c.height} px -> {a.out}\n  source: {RESOLVER}{issue}:{part or page}"
          f"   (whole page: {RESOLVER}{issue}:{page}:image)")
    if a.check:
        chk = os.path.splitext(a.out)[0] + "-check.jpg"
        pad = 60
        ruler_image(im, (max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)), 1,
                    [(x0, y0, x1, y1)], cut=(x0, y0, x1, y1)).save(chk, quality=85)
        print(f"  check (the box in red, the {pad} px around it veiled: only the clear part is cut; don't publish this one): {chk}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n\n", 1)[1])
    ap.add_argument("--cache", help="folder for downloaded scans and ALTO files (default: system temp/delpher-cache)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("search", aliases=["zoek"], help="search articles (CQL, e.g. '\"Jan Smit\" AND Leiden')")
    s.add_argument("query"); s.add_argument("--max", type=int, default=20); s.add_argument("--start", type=int, default=1)
    s.add_argument("--from", "--van", dest="van", type=int); s.add_argument("--to", "--tot", dest="tot", type=int)
    s.set_defaults(f=cmd_search)
    t = sp.add_parser("text", aliases=["tekst"], help="OCR text of an article")
    t.add_argument("urn"); t.set_defaults(f=cmd_text)
    for name, alias, fn in (("locate", "vind", cmd_locate), ("cut", "knip", cmd_cut)):
        c = sp.add_parser(name, aliases=[alias], help="wide crop with a ruler" if name == "locate" else "cut the clipping")
        c.add_argument("urn")
        c.add_argument("--page", "--pagina", help="page (p011) when the lookup fails or the article runs over pages")
        c.set_defaults(f=fn)
        if name == "locate":
            c.add_argument("words", help="word(s) on one line of the article, e.g. a name")
            c.add_argument("--hit", type=int, default=1, help="which matching line to centre on (default 1)")
            c.add_argument("--at", help="centre the crop on x,y (page pixels) instead of the hit")
            c.add_argument("--width", type=int, default=CROP_W); c.add_argument("--height", type=int, default=CROP_H)
            c.add_argument("--zoom", type=float, default=1.0, help="scale of the crop (1 = true size; 0.5 for an overview)")
            c.add_argument("--out", help="output jpg (default: in the cache folder)")
            c.add_argument("--no-grid", action="store_true", help="no faint 100 px grid over the print")
        else:
            c.add_argument("box", help="x0,y0,x1,y1 in page pixels, read off the locate ruler")
            c.add_argument("--out", required=True); c.add_argument("--min-width", type=int, default=MIN_WIDTH)
            c.add_argument("--check", action="store_true", help="also write a ruler image of the box with some margin")
    a = ap.parse_args()
    kind = {"cmd_search": "search", "cmd_text": "read"}.get(a.f.__name__, "clip")
    live(kind, source="Delpher", q=getattr(a, "query", None) or getattr(a, "words", None) or getattr(a, "urn", None))
    a.f(a)


if __name__ == "__main__":
    main()
