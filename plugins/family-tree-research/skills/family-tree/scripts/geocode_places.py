#!/usr/bin/env python3
"""geocode_places.py — finds coordinates for the places in a GEDCOM, for the maps in the viewer.

Reads every place (PLAC) in the GEDCOM, plus the "plekken"/"places" of the stories file, and looks up the
ones that are not yet in the coordinates file with OpenStreetMap's Nominatim (1 request per second).
The file is a cache: places already in it are never looked up again, and your own corrections stay.

  python3 geocode_places.py tree.ged data/place-coords.json
  python3 geocode_places.py tree.ged data/place-coords.json --stories data/stories.json
  python3 geocode_places.py tree.ged data/place-coords.json --dry-run      (only list what is missing)

The coordinates file ({place as written in the GEDCOM: entry}):
  "Åhus, Skåne, Zweden": {"lat": 55.92, "lon": 14.30, "precisie": "plaats", "bron": "nominatim: Åhus, ..., Sweden"}
  precisie (precision): "plaats" (town or village), "regio" (province, county, state) or "land" (country).
  With "regio" or "land" the map says the exact spot is unknown instead of placing a pin.
  An entry whose "bron" does not start with "nominatim" counts as a manual correction and is never changed,
  not even with --refresh. "controleren": true = the result may be wrong (other country, a street or building, or a guess); check it.
  Not found: {"precisie": "onbekend", ...}; looked up again only with --retry.
English keys ("precision", "source", "check") are read too; the script writes the Dutch ones (as in data.json).

Dutch option names work too: --verhalen, --proefrun, --opnieuw, --vernieuwen.
Coordinates © OpenStreetMap contributors (ODbL). Standard library only; Python 3.8+.
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

URL = "https://nominatim.openstreetmap.org/search"
WAIT = 1.1  # seconds between requests (Nominatim: at most 1 per second)
PREC = {"plaats", "regio", "land", "onbekend"}
PREC_EN = {"place": "plaats", "town": "plaats", "region": "regio", "country": "land", "unknown": "onbekend"}
# Nominatim address types that are a region or a country rather than a town
# (a "municipality" is a town in many countries, e.g. Leiden: that stays a place)
REGION_TYPES = {"state", "province", "region", "county", "state_district", "archipelago"}
COUNTRY_TYPES = {"country", "continent"}
# a street, road or building for a place name is almost always wrong (Ameide -> a street in Rotterdam): accepted, but marked to check
NOT_A_TOWN_TYPES = {"road", "street", "highway", "building", "house", "house_number", "amenity", "shop", "office", "leisure",
                    "tourism", "railway", "aeroway", "man_made", "industrial", "retail", "commercial"}
NOT_A_PLACE = re.compile(r"^(ndg|onbekend|unknown|\?+|-+|n/?a|nvt)$", re.I)


def plugin_version():
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(here, "..", "..", "..", ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            return json.load(fh).get("version", "")
    except (OSError, ValueError):
        return ""


# the request names the plugin only, never the user or the people in the tree
UA = f"family-tree-research-plugin/{plugin_version() or 'dev'} (+https://github.com/chriswaalberg/family-tree-research)"


def read_text(path):
    raw = open(path, "rb").read()
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if raw.startswith(bom):
            return raw.decode(enc)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def gedcom_places(path):
    out, seen = [], set()
    for line in read_text(path).splitlines():
        m = re.match(r"^\s*\d+\s+PLAC\s+(.+?)\s*$", line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1)); out.append(m.group(1))
    return out


def story_places(path):
    """"plekken"/"places" of every story: [{"plaats": "Ahuys", ...}] or plain strings."""
    with open(path, encoding="utf-8") as fh:
        vh = json.load(fh)
    out = []
    for key, val in vh.items():
        if key.startswith("_") or not isinstance(val, dict): continue
        for pl in val.get("plekken") or val.get("places") or []:
            name = pl if isinstance(pl, str) else (pl.get("plaats") or pl.get("place") if isinstance(pl, dict) else None)
            if name and name not in out: out.append(name)
    return out


def norm(s):
    return " ".join(unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower().split())


def entry_get(e, *keys):
    for k in keys:
        if k in e: return e[k]
    return None


def is_manual(e):
    src = entry_get(e, "bron", "source")
    return not str(src or "").lower().startswith("nominatim")


def nominatim(q, last):
    """One request, at most one per second. Returns (list, time of this request)."""
    wait = WAIT - (time.monotonic() - last)
    if wait > 0: time.sleep(wait)
    url = URL + "?" + urllib.parse.urlencode({"q": q, "format": "jsonv2", "limit": 1, "addressdetails": 1, "accept-language": "en"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    t = time.monotonic()
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r), t


def precision_of(hit):
    t = (hit.get("addresstype") or hit.get("type") or "").lower()
    if t in COUNTRY_TYPES: return "land"
    if t in REGION_TYPES: return "regio"
    return "plaats"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gedcom")
    ap.add_argument("coords", help="coordinates file (JSON); created when missing, updated in place")
    ap.add_argument("--stories", "--verhalen", dest="verhalen", help="stories JSON: its \"plekken\"/\"places\" are looked up too")
    ap.add_argument("--dry-run", "--proefrun", dest="proefrun", action="store_true", help="only list the places that would be looked up")
    ap.add_argument("--retry", "--opnieuw", dest="opnieuw", action="store_true", help="look up places that were not found before again")
    ap.add_argument("--refresh", "--vernieuwen", dest="vernieuwen", action="store_true", help="look up all Nominatim entries again (manual ones stay)")
    a = ap.parse_args()

    places = gedcom_places(a.gedcom)
    if a.verhalen: places += [p for p in story_places(a.verhalen) if p not in places]
    data = {}
    if os.path.exists(a.coords):
        with open(a.coords, encoding="utf-8") as fh:
            data = json.load(fh)
    data.setdefault("_uitleg", "Coordinates per place, as written in the GEDCOM. precisie: plaats | regio | land | onbekend. "
                    "An entry whose bron does not start with 'nominatim' is a manual correction and is never changed by geocode_places.py. "
                    "controleren: true = check this one. Coordinates from Nominatim: © OpenStreetMap contributors (ODbL).")

    todo, skip = [], []
    for p in places:
        if NOT_A_PLACE.match(p.strip()): skip.append(p); continue
        e = data.get(p)
        if e is None: todo.append(p); continue
        if is_manual(e): continue
        prec = entry_get(e, "precisie", "precision")
        if a.vernieuwen or (a.opnieuw and prec in ("onbekend", "unknown")): todo.append(p)

    print(f"{len(places)} place(s), {len(todo)} to look up" + (f", {len(skip)} skipped (not a place: {', '.join(skip)})" if skip else ""))
    if a.proefrun:
        for p in todo: print("  " + p)
        return
    if not todo:
        print("Nothing to look up."); return
    print(f"About {round(len(todo) * WAIT * 1.5 / 60) or 1} minute(s). User-Agent: {UA}")

    last, ccache, n_ok, n_low, n_miss, n_chk = 0.0, {}, 0, 0, 0, 0

    def country_code(name, last):
        """The country code of the last part of a place ("Zweden" -> "se"), looked up once per name."""
        k = norm(name)
        if k in ccache: return ccache[k], last
        try:
            res, last = nominatim(name, last)
        except Exception as ex:
            print(f"  (country lookup failed for {name}: {ex})", file=sys.stderr); res = []
        cc = ((res[0].get("address") or {}).get("country_code") if res and precision_of(res[0]) == "land" else None)
        ccache[k] = cc
        return cc, last

    def save():
        tmp = a.coords + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, a.coords)

    try:
        for n, p in enumerate(todo, 1):
            parts = [x.strip() for x in p.split(",") if x.strip()]
            hit, used = None, 0
            # the whole name first, then without the first part (village unknown -> region or country)
            for drop in range(len(parts)):
                q = ", ".join(parts[drop:])
                try:
                    res, last = nominatim(q, last)
                except Exception as ex:
                    print(f"  {p}: request failed ({ex}); stopped, run again to continue", file=sys.stderr)
                    save(); sys.exit(1)
                if res: hit, used = res[0], drop; break
            if not hit:
                data[p] = {"precisie": "onbekend", "bron": "nominatim: not found"}
                n_miss += 1; print(f"  [{n}/{len(todo)}] {p}: not found"); continue
            prec = precision_of(hit)
            if used and prec == "plaats": prec = "regio"  # only a broader name was found
            e = {"lat": round(float(hit["lat"]), 4), "lon": round(float(hit["lon"]), 4), "precisie": prec,
                 "bron": "nominatim: " + hit.get("display_name", "")}
            # a check: is the result in the country the place name ends with?
            chk = []
            if len(parts) >= 2:
                cc, last = country_code(parts[-1], last)
                got = (hit.get("address") or {}).get("country_code")
                if cc and got and cc != got: chk.append(f"other country ({got})")
            elif prec == "plaats":
                chk.append("single name without country")
            if used: chk.append(f"only found as \"{', '.join(parts[used:])}\"")
            kind = {(hit.get("addresstype") or "").lower(), (hit.get("category") or "").lower(), (hit.get("type") or "").lower()}
            if kind & NOT_A_TOWN_TYPES: chk.append(f"found as a {hit.get('addresstype') or hit.get('category')}: {hit.get('name', '')}")
            if chk: e["controleren"] = True; n_chk += 1
            data[p] = e
            if prec == "plaats": n_ok += 1
            else: n_low += 1
            print(f"  [{n}/{len(todo)}] {p}: {prec} {e['lat']},{e['lon']}" + (f"  CHECK: {'; '.join(chk)}" if chk else ""))
            if n % 10 == 0: save()
    except KeyboardInterrupt:
        print("\nStopped; what was found so far is saved.")
    save()
    print(f"Done: {n_ok} town(s), {n_low} only region/country, {n_miss} not found, {n_chk} to check. Saved in {a.coords}")
    if n_chk or n_miss:
        print("Check the entries with \"controleren\": true or \"precisie\": \"onbekend\" by hand; change \"bron\" to e.g. \"manual\" "
              "(or \"hand\") so they are kept.")


if __name__ == "__main__":
    main()
