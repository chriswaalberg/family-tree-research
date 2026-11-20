#!/usr/bin/env python3
"""standalone_viewer.py — builds one standalone HTML file with the data inside (no data.json next to it).

Handy for emailing the family tree as a file, or when artifact publishing isn't available.

  python3 standalone_viewer.py viewer/index.html data/data.json family-tree.html
  python3 standalone_viewer.py viewer/index.html data/data.json family-tree.html --media viewer

With --media DIR, files with a path like "media/x.jpg" are read from DIR and baked into the file
(data: URL), so they also show in the standalone file: photos and documents of people, images with
own stories (verhaal_beelden) and zeitgeist images (tijdgeest). Mind the file size.
"""
import argparse, base64, json, mimetypes, os, re, sys

ZOEK = 'fetch("data.json").then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()})'

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("index"); ap.add_argument("data"); ap.add_argument("uit", metavar="output")
    ap.add_argument("--media", help="folder containing media/<name> (usually the viewer folder)")
    a = ap.parse_args()
    html = open(a.index, encoding="utf-8").read()
    data = json.load(open(a.data, encoding="utf-8"))
    if ZOEK not in html:
        sys.exit("Could not find where index.html loads data.json.")
    n_in = n_mis = 0
    if a.media:
        cache = {}
        def embed(lst):
            """Replace "media/..." paths in a list of items (dicts with "bestand", or plain strings)."""
            nonlocal n_in, n_mis
            for k, m in enumerate(lst or []):
                rel = m.get("bestand", "") if isinstance(m, dict) else m if isinstance(m, str) else ""
                if not rel.startswith("media/"):
                    continue
                pad = os.path.join(a.media, rel)
                if pad not in cache:
                    if not os.path.isfile(pad):
                        n_mis += 1; continue
                    mime = mimetypes.guess_type(pad)[0] or "application/octet-stream"
                    cache[pad] = f"data:{mime};base64," + base64.b64encode(open(pad, "rb").read()).decode()
                if isinstance(m, dict): m["bestand"] = cache[pad]
                else: lst[k] = cache[pad]
                n_in += 1
        for p in data.get("personen", []):
            embed(p.get("media"))
            embed(p.get("verhaal_beelden"))
        for pl in (data.get("tijdgeest") or {}).get("plaatsen", []):
            embed(pl.get("beelden"))
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace(ZOEK, "Promise.resolve(window.__STAMBOOM__)", 1)
    # the data goes after <meta charset>: a browser only looks for the charset in the first 1024 bytes
    tag = "<script>window.__STAMBOOM__=" + blob + ";</script>"
    m = re.search(r"<meta[^>]*charset[^>]*>", html, re.I)
    html = html[:m.end()] + "\n" + tag + html[m.end():] if m else html.replace("<head>", "<head>\n<meta charset=\"utf-8\">\n" + tag, 1)
    open(a.uit, "w", encoding="utf-8").write(html)
    extra = f", {n_in} media embedded" + (f", {n_mis} not found" if n_mis else "") if a.media else ""
    print(f"{a.uit}: {len(data.get('personen', []))} people{extra}, {len(html)//1024} kB")

if __name__ == "__main__":
    main()
