#!/usr/bin/env python3
"""make_geo.py — builds plugins/.../scripts/geo/natural-earth.json from Natural Earth GeoJSON (public domain).

Only for maintainers: the plugin ships the result. Download the GeoJSON files from
https://github.com/nvkelso/natural-earth-vector/tree/master/geojson into one folder, then:
  python3 -I tools/make_geo.py <folder> plugins/family-tree-research/skills/family-tree/scripts/geo/natural-earth.json

Layers: "fijn" (10m land, lakes with scalerank <= 6, land borders; simplified, for the detail maps) and
"grof" (50m land, lakes, land borders; for overviews, routes and the globe).
Rings are delta-encoded integers in units of 1/Q degree: [x0, y0, dx1, dy1, ...]. Standard library only.
"""
import json, os, sys

def rings(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon": return c
    if t == "MultiPolygon": return [r for p in c for r in p]
    if t == "LineString": return [c]
    if t == "MultiLineString": return c
    return []

def dp(pts, tol):
    """Douglas-Peucker, iterative."""
    if len(pts) < 3: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    st = [(0, len(pts) - 1)]
    while st:
        a, b = st.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1; L = (dx * dx + dy * dy) ** .5
        best, bi = -1, -1
        for i in range(a + 1, b):
            x, y = pts[i]
            d = abs(dy * (x - x1) - dx * (y - y1)) / L if L else ((x - x1) ** 2 + (y - y1) ** 2) ** .5
            if d > best: best, bi = d, i
        if best > tol:
            keep[bi] = True; st += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]

def enc(r, q):
    out, px, py = [], 0, 0
    for i, (x, y) in enumerate(r):
        X, Y = round(x * q), round(y * q)
        if i and X == px and Y == py: continue
        out += [X - px, Y - py] if i else [X, Y]; px, py = X, Y
    return out

def layer(path, tol, q, closed, keep=lambda p: True, minsize=0):
    feats = json.load(open(path, encoding="utf-8"))["features"]
    out = []
    for f in feats:
        if not keep(f["properties"]): continue
        for r in rings(f["geometry"]):
            if closed:
                xs = [p[0] for p in r]; ys = [p[1] for p in r]
                if max(xs) - min(xs) < minsize and max(ys) - min(ys) < minsize: continue
            s = dp([tuple(p[:2]) for p in r], tol)
            if len(s) >= (4 if closed else 2): out.append(enc(s, q))
    return out

def main():
    src, dst = sys.argv[1], sys.argv[2]
    P = lambda n: os.path.join(src, n + ".geojson")
    QF, QG = 1000, 100
    lakes = lambda p: (p.get("scalerank") or 9) <= 6
    noant = lambda p: True
    data = {
        "_uitleg": "Natural Earth (public domain, naturalearthdata.com), simplified by tools/make_geo.py. "
                   "Rings: delta-encoded integers in 1/q degree. fijn = 10m (detail maps), grof = 50m (overviews, routes, globe).",
        "fijn": {"q": QF, "land": layer(P("ne_10m_land"), .004, QF, True, minsize=.01),
                 "meren": layer(P("ne_10m_lakes"), .004, QF, True, lakes, minsize=.02),
                 "grenzen": layer(P("ne_10m_admin_0_boundary_lines_land"), .004, QF, False)},
        "grof": {"q": QG, "land": layer(P("ne_50m_land"), .04, QG, True, minsize=.15),
                 "meren": layer(P("ne_50m_lakes"), .04, QG, True, lakes, minsize=.3),
                 "grenzen": layer(P("ne_50m_admin_0_boundary_lines_land"), .04, QG, False)},
    }
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))
    for k in ("fijn", "grof"):
        print(k, {n: (len(v), sum(len(r) for r in v) // 2) for n, v in data[k].items() if n != "q"})
    print(dst, os.path.getsize(dst) // 1024, "kB")

if __name__ == "__main__":
    main()
