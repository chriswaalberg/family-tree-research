#!/usr/bin/env python3
"""make_viewer_data.py — builds data.json (format v2) for the family-tree viewer from a GEDCOM file.

Only a GEDCOM is required. Optional:
  --csv        certainty per child-parent relation (see DATA-FORMAT.md, "Certainty CSV")
  --regions    region table as JSON: {"regios": {code: {"naam": ..., "kleur": "#hex"}}, "plaatsen": {place: code}}
  --stories    the user's own stories per person as JSON (see DATA-FORMAT.md, "Stories")
  --zeitgeist  life and times per place (daily life, events, old images) as JSON (see DATA-FORMAT.md, "Zeitgeist")
  --media-dir  copy photos and documents (GEDCOM OBJE/FILE) into this folder as media/<name>,
               so they can be published next to index.html

Examples:
  python3 make_viewer_data.py tree.ged data.json
  python3 make_viewer_data.py tree.ged data.json --start @I12@:Femke --start "Thomas de Vries" --lang nl
  python3 make_viewer_data.py tree.ged data.json --csv relations.csv --regions regions.json --title "The De Vries family"

Without --start the script picks the person with the most known ancestors.
Living people (no death, born less than 100 years ago, or estimated so via parents/children) get
"levend": true. All their data is kept and shown; --hide-living leaves out their dates and places.
Dutch option names (--taal, --titel, --verhalen, --tijdgeest, --regios, --media-map, ...) still work.
Standard library only; Python 3.8+.
"""
import argparse, csv, datetime, json, os, re, shutil, sys, unicodedata

# ---------------------------------------------------------------- read GEDCOM
def read_text(path):
    raw = open(path, "rb").read()
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if raw.startswith(bom):
            return raw.decode(enc)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # ANSEL or Windows-1252: not a perfect ANSEL conversion, but readable for ordinary letters
        return raw.decode("cp1252", errors="replace")

LINE = re.compile(r"^\s*(\d+)\s+(@[^@]+@\s+)?(\S+)(?:\s(.*))?$")

def parse_gedcom(text):
    """Builds a tree of lines: each node {x: xref, t: tag, v: value, c: children}."""
    root = {"c": []}
    stack = [(-1, root)]
    for raw in text.splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        lvl, xref, tag, val = int(m.group(1)), (m.group(2) or "").strip(), m.group(3).upper(), m.group(4) or ""
        while stack[-1][0] >= lvl:
            stack.pop()
        parent = stack[-1][1]
        if tag in ("CONC", "CONT") and parent is not root:
            parent["v"] += ("\n" if tag == "CONT" else "") + val
            continue
        node = {"x": xref, "t": tag, "v": val, "c": []}
        parent["c"].append(node)
        stack.append((lvl, node))
    return root["c"]

def sub(node, tag):
    for c in node["c"]:
        if c["t"] == tag:
            return c
    return None

def subs(node, tag):
    return [c for c in node["c"] if c["t"] == tag]

YEAR = re.compile(r"(\d{3,4})(?!.*\d{3,4})")
def year_of(date):
    if not date:
        return None
    m = YEAR.search(date)
    return int(m.group(1)) if m else None

def event(node, tags):
    """Date and place, each from the first event that has it:
    BIRT with only a date + BAPM with date and place gives the BIRT date and the BAPM place."""
    date = plac = ""
    for tag in tags:
        for e in subs(node, tag):
            d, p = sub(e, "DATE"), sub(e, "PLAC")
            if not date and d and d["v"].strip():
                date = d["v"].strip()
            if not plac and p and p["v"].strip():
                plac = p["v"].strip()
    return date, plac

def name_parts(indi):
    n = sub(indi, "NAME")
    full = n["v"] if n else ""
    given = (sub(n, "GIVN") or {}).get("v", "") if n else ""
    surn = (sub(n, "SURN") or {}).get("v", "") if n else ""
    m = re.match(r"^(.*?)/(.*?)/(.*)$", full)
    if m:
        given = given or m.group(1).strip()
        surn = surn or m.group(2).strip()
        suffix = m.group(3).strip()
    else:
        given = given or full.strip()
        suffix = ""
    display = " ".join(" ".join(x for x in (given, surn, suffix) if x).split()) or "?"
    return display, given, surn

# ---------------------------------------------------------------- regions
COUNTRIES = {  # code: (names as they appear in place names, nl label, en label, colour)
    "NL": (["nederland", "netherlands", "the netherlands", "holland", "niederlande"], "Nederland", "Netherlands", "#e07a2f"),
    "BE": (["belgie", "belgium", "belgique", "belgien"], "België", "Belgium", "#c9a227"),
    "DE": (["duitsland", "germany", "deutschland", "allemagne", "preussen", "pruisen", "prussia"], "Duitsland", "Germany", "#5a9a6e"),
    "SE": (["zweden", "sweden", "sverige", "schweden"], "Zweden", "Sweden", "#1f9bb5"),
    "NO": (["noorwegen", "norway", "norge"], "Noorwegen", "Norway", "#3b6ea5"),
    "DK": (["denemarken", "denmark", "danmark"], "Denemarken", "Denmark", "#b0486a"),
    "FR": (["frankrijk", "france", "frankreich"], "Frankrijk", "France", "#7a5195"),
    "GB": (["engeland", "england", "united kingdom", "uk", "scotland", "schotland", "wales", "great britain"], "Verenigd Koninkrijk", "United Kingdom", "#9a8fb8"),
    "US": (["verenigde staten", "united states", "usa", "united states of america"], "Verenigde Staten", "United States", "#8d7f6e"),
    "ID": (["indonesie", "indonesia", "nederlands-indie", "dutch east indies", "nederlandsch-indie"], "Indonesië", "Indonesia", "#d97a9a"),
}

def norm(s):
    return " ".join(unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower().replace(".", " ").split())

def region_of(place, table):
    """table: {normalised place: code}. First the whole place, then each part, then the country."""
    if not place:
        return None
    n = norm(place)
    if n in table:
        return table[n]
    parts = [p.strip() for p in n.split(",") if p.strip()]
    for p in parts:
        if p in table:
            return table[p]
    for p in reversed(parts):
        for code, (names, *_rest) in COUNTRIES.items():
            if p in names:
                return code
    return None

# ---------------------------------------------------------------- certainty (CSV)
STATUS = {"zeker": "zeker", "certain": "zeker", "waarschijnlijk": "waarschijnlijk", "probable": "waarschijnlijk", "likely": "waarschijnlijk",
          "mogelijk": "mogelijk", "possible": "mogelijk", "onbekend": "onbekend", "unknown": "onbekend", "fout": "fout", "error": "fout",
          "wrong": "fout", "niet gecheckt": "niet gecheckt", "not checked": "niet gecheckt"}
# relation type (CSV column type/soort): the viewer uses the Dutch values internally
REL_TYPE = {"raised": "aangenomen", "accepted": "aangenomen", "raised as own": "aangenomen", "social": "aangenomen",
            "adopted": "adoptie", "adoption": "adoptie", "foster": "pleeg", "biological": "biologisch"}

def norm_status(s):
    s = (s or "").strip().lower()
    for k, v in STATUS.items():
        if s == k or s.startswith(k):
            return v
    return "niet gecheckt"

def col(row, *names):
    for n in names:
        for k in row:
            if k and k.strip().lower() == n:
                return (row[k] or "").strip()
    return ""

# ---------------------------------------------------------------- media (OBJE)
SOORT_GED = {"photo": "foto", "foto": "foto", "document": "document", "scan": "scan", "certificate": "scan",
             "akte": "scan", "book": "document", "card": "document", "newspaper": "document"}

def media_of(indi, objs):
    """All OBJE under a person (also under events), inline or as a reference @O1@."""
    out, stack = [], list(indi["c"])
    while stack:
        n = stack.pop(0)
        if n["t"] == "OBJE":
            o = objs.get(n["v"].strip()) if n["v"].strip().startswith("@") else n
            if o:
                titl = (sub(o, "TITL") or {}).get("v", "")
                for f in subs(o, "FILE"):
                    path = f["v"].strip()
                    if not path:
                        continue
                    t = titl or (sub(f, "TITL") or {}).get("v", "")
                    typ = (sub(sub(f, "FORM") or {"c": []}, "TYPE") or sub(f, "TYPE") or sub(o, "TYPE") or {}).get("v", "")
                    m = {"bestand": path}
                    if t: m["titel"] = t.strip()
                    srt = SOORT_GED.get(typ.strip().lower())
                    if srt: m["soort"] = srt
                    if m not in out: out.append(m)
            continue
        stack.extend(n["c"])
    return out

def veilige_naam(naam, gebruikt):
    base, ext = os.path.splitext(os.path.basename(naam))
    base = unicodedata.normalize("NFD", base).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-.")[:80] or "bestand"
    ext = re.sub(r"[^A-Za-z0-9.]", "", ext.lower())
    kand, k = base + ext, 2
    while kand in gebruikt:
        kand, k = f"{base}-{k}{ext}", k + 1
    gebruikt.add(kand)
    return kand

def kopieer_media(pad, doel, gebruikt, max_px):
    """Copies one file; photos are shrunk (and converted to JPEG if needed) when Pillow is available."""
    ext = os.path.splitext(pad)[1].lower()
    if max_px and ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"):
        try:
            from PIL import Image
            im = Image.open(pad)
            im.load()
            groot = max(im.size) > max_px or os.path.getsize(pad) > 1_500_000 or ext in (".tif", ".tiff", ".bmp")
            if groot:
                im.thumbnail((max_px, max_px))
                alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
                if alpha:  # screenshots often have an alpha channel without real transparency
                    try:
                        alpha = im.convert("RGBA").getchannel("A").getextrema()[0] < 255
                    except Exception:
                        pass
                if alpha and ext == ".png":
                    naam = veilige_naam(pad, gebruikt)
                    im.save(os.path.join(doel, naam), optimize=True)
                else:
                    naam = veilige_naam(os.path.splitext(pad)[0] + ".jpg", gebruikt)
                    im.convert("RGB").save(os.path.join(doel, naam), "JPEG", quality=85, optimize=True)
                return naam
        except Exception:
            pass  # no Pillow or unreadable image: just copy
    naam = veilige_naam(pad, gebruikt)
    shutil.copy2(pad, os.path.join(doel, naam))
    return naam

# ---------------------------------------------------------------- main
# kind of image ("soort"): the viewer shows "A drawing from that time" etc.; English names are stored in Dutch
IMG_KIND = {"photo": "foto", "drawing": "tekening", "print": "prent", "painting": "schilderij",
            "map": "kaart", "coin": "munt", "poster": "affiche",
            "newspaper": "krant", "clipping": "krant", "krantenknipsel": "krant"}


def img_kinds(images):
    for b in images if isinstance(images, list) else []:
        if isinstance(b, dict):
            k = b.get("soort") or b.get("type")  # never "kind": that is the children flag
            if isinstance(k, str) and k.strip():
                b["soort"] = IMG_KIND.get(k.strip().lower(), k.strip().lower())
                if b.get("type") == k: del b["type"]
            if "paragraph" in b and "alinea" not in b:  # story images: after which paragraph (1-based)
                b["alinea"] = b.pop("paragraph")
            for k in ("standing_since", "built"):  # a building that already stood then: year it was built
                if k in b and "stond_er_al" not in b:
                    b["stond_er_al"] = b.pop(k)
    return images


# ---------------------------------------------------------------- where someone lived, and when
WOON_MARGIN = 5  # years a dated place counts before and after its record (never across a record from another place, never outside the life)
WOON_TAGS = ("BIRT", "CHR", "BAPM", "RESI", "CENS", "OCCU", "EDUC", "EMIG", "IMMI", "NATU", "EVEN", "DEAT")


def place_key(plac):
    return norm((plac or "").split(",")[0])


def dated_places(node, tags):
    """(year, place) for every event with both a year and a place (RESI may use ADDR/CITY instead of PLAC)."""
    out = []
    for e in node["c"]:
        if e["t"] not in tags: continue
        y = year_of((sub(e, "DATE") or {}).get("v", ""))
        pl = (sub(e, "PLAC") or {}).get("v", "").strip()
        if not pl:
            ad = sub(e, "ADDR")
            pl = ((sub(ad, "CITY") or {}).get("v", "") if ad else "").strip()
        if y and pl: out.append((y, pl))
    return out


def residence_spans(points, by, dy):
    """Dated places -> [[place, from, to], ...]: consecutive records in one place form one period,
    widened by WOON_MARGIN but never past the midpoint to a record elsewhere, never before birth or after death."""
    pts = sorted(set(points))
    runs = []
    for y, pl in pts:
        if runs and runs[-1][0] == place_key(pl): runs[-1][3] = y
        else: runs.append([place_key(pl), pl, y, y])
    out = []
    for k, (key, pl, a, b) in enumerate(runs):
        lo, hi = a - WOON_MARGIN, b + WOON_MARGIN
        if k: lo = max(lo, (runs[k - 1][3] + a + 1) // 2)
        if k + 1 < len(runs): hi = min(hi, (b + runs[k + 1][2]) // 2)
        if by: lo = max(lo, by)
        if dy: hi = min(hi, dy)
        if hi >= lo: out.append([pl, lo, hi])
    return out


# ---------------------------------------------------------------- abroad ("weg")
# countries people often emigrated to; only used to recognise a stay abroad (COUNTRIES above also count)
ABROAD_COUNTRIES = {
    "AU": ["australie", "australia", "australien"], "CA": ["canada"], "NZ": ["nieuw-zeeland", "new zealand"],
    "ZA": ["zuid-afrika", "south africa"], "SR": ["suriname"], "CW": ["curacao", "nederlandse antillen", "netherlands antilles"],
    "AR": ["argentinie", "argentina"], "BR": ["brazilie", "brazil"], "CL": ["chili", "chile"],
}
EMIG_TYPE = re.compile(r"emigr|landverhuiz", re.I)


def country_key(plac):
    """Country code of a place (or its last part when unknown); None for a place without a recognisable country ("Amsterdam")."""
    parts = [x.strip() for x in norm(plac).split(",") if x.strip()]
    if not parts: return None
    for code, (names, *_r) in COUNTRIES.items():
        if parts[-1] in names: return code
    for code, names in ABROAD_COUNTRIES.items():
        if parts[-1] in names: return code
    return parts[-1].upper() if len(parts) > 1 else None


def first_year(date):
    """Earliest possible year: AFT 1952 -> 1952, BET 1950 AND 1955 -> 1950, ABT/BEF -> the year given."""
    ys = [int(y) for y in re.findall(r"(?<!\d)(\d{3,4})(?!\d)", date or "")]
    return min(ys) if ys else None


def abroad_spans(r, p, people, fams, home):
    """[[from, to, land], ...]: from = the earliest year of an EMIG, IMMI abroad, EVEN of type emigration or RESI abroad;
    to = the first later dated fact in the home country (RESI, OCCU or another event with a place, marriage, child, IMMI back,
    death); none: the year of death (null when unknown)."""
    if not home: return []
    abroad = lambda pl: (lambda k: k is not None and k != home)(country_key(pl))
    starts, homef = [], []
    for e in r["c"]:
        d = (sub(e, "DATE") or {}).get("v", "")
        pl = (sub(e, "PLAC") or {}).get("v", "").strip()
        typ = (sub(e, "TYPE") or {}).get("v", "")
        y = first_year(d)
        if not y: continue
        if e["t"] == "EMIG" or (e["t"] == "EVEN" and EMIG_TYPE.search(typ)) or (e["t"] in ("IMMI", "RESI") and pl and abroad(pl)):
            starts.append((y, country_key(pl) if pl and abroad(pl) else None))
        elif pl and not abroad(pl) and e["t"] not in ("BIRT", "CHR", "BAPM", "BURI", "CREM"):
            homef.append(year_of(d))
    for c in subs(r, "FAMS"):
        fam = fams.get(c["v"])
        for e in (subs(fam, "MARR") + subs(fam, "RESI")) if fam else []:
            y = year_of((sub(e, "DATE") or {}).get("v", "")); pl = (sub(e, "PLAC") or {}).get("v", "")
            if y and pl and not abroad(pl): homef.append(y)
    for j in p["ch"]:
        q = people[j]
        if q.get("by") and q.get("bplac") and not abroad(q["bplac"]): homef.append(q["by"])
    if p.get("dy") and p.get("dplac") and not abroad(p["dplac"]): homef.append(p["dy"])
    homef = sorted(y for y in homef if y)
    out = []
    for y, land in sorted(starts, key=lambda t: t[0]):
        if out and (out[-1][1] is None or y < out[-1][1]):
            if land and out[-1][2] == "?": out[-1][2] = land
            continue
        tot = next((h for h in homef if h > y), p.get("dy"))
        out.append([y, tot, land or next((l for yy, l in starts if l and yy >= y), "?")])
    return out


def story_image_warnings(p, images):
    """Story images should fit a moment in the story: a dating within (birth - 10) to (death + 10)
    and an existing paragraph ("alinea"). Only warnings; the data is written anyway."""
    text = p.get("verhaal")
    texts = text.values() if isinstance(text, dict) else [text]
    n_par = max((len([x for x in re.split(r"\n\s*\n", t) if x.strip()]) for t in texts if isinstance(t, str)), default=0)
    by, dy = p.get("by"), p.get("dy")
    lo = by - 10 if by else None
    hi = dy + 10 if dy else (datetime.date.today().year if p.get("levend") else (by + 110 if by else None))
    out = []
    for b in images if isinstance(images, list) else []:
        if not isinstance(b, dict): continue
        name = b.get("bestand") or b.get("file") or b.get("titel") or "?"
        if isinstance(name, dict): name = next(iter(name.values()), "?")
        d = b.get("datering") or b.get("dating") or b.get("date")
        ys = [int(y) for y in re.findall(r"(?<!\d)(\d{3,4})(?!\d)", str(d))] if d else []
        built = b.get("stond_er_al")
        if built is not None:  # a building that still stood the same way: the dating may be later, but it must have been built in their lifetime or before
            by_ = year_of(str(built))
            if by_ is None: out.append(f"{name}: \"stond_er_al\": {built} is not a year")
            elif hi is not None and by_ > hi: out.append(f"{name}: \"stond_er_al\": {built} is after {hi} (death + 10)")
        elif ys and lo is not None and hi is not None and (max(ys) < lo or min(ys) > hi):
            out.append(f"{name}: dating {d} is outside {lo}-{hi} (birth - 10 to death + 10; for a building that already stood then, add \"stond_er_al\": <year built>)")
        al = b.get("alinea")
        if al is None:
            out.append(f"{name}: no \"alinea\" (which paragraph does it belong to?)")
        else:
            try: ok = 1 <= int(al) <= n_par
            except (TypeError, ValueError): ok = False
            if not ok: out.append(f"{name}: \"alinea\": {al} does not exist (the story has {n_par} paragraph(s))")
    for w in out:
        print(f"  warning, story image of {p['n']}: {w}", file=sys.stderr)
    return len(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gedcom")
    ap.add_argument("uit", nargs="?", default="data.json", metavar="output")
    ap.add_argument("--csv", help="relation certainty CSV (optional)")
    ap.add_argument("--regions", "--regios", dest="regios", help="region table as JSON (optional)")
    ap.add_argument("--start", action="append", default=[], help="start person: GEDCOM id (@I1@) or name, optionally with :label")
    ap.add_argument("--lineage-start", "--stamlijn-start", dest="stamlijn_start", help="different start person for the Line view (id or name)")
    ap.add_argument("--title", "--titel", dest="titel")
    ap.add_argument("--family-name", "--familienaam", dest="familienaam")
    ap.add_argument("--lang", "--taal", dest="taal", choices=["en", "nl"], default="en", help="viewer language (default en)")
    ap.add_argument("--show-living", "--levenden-tonen", dest="levenden_tonen", action="store_true", help="(default; kept for old commands)")
    ap.add_argument("--hide-living", "--levenden-verbergen", dest="levenden_verbergen", action="store_true", help="leave out dates and places of living people")
    ap.add_argument("--zeitgeist", "--tijdgeest", dest="tijdgeest", help="life and times per place as JSON (optional, for the Story view)")
    ap.add_argument("--stories", "--verhalen", dest="verhalen", help="own stories per person as JSON (optional, for the Story view)")
    ap.add_argument("--living-years", "--levend-grens", dest="levend_grens", type=int, default=100, help="years (default 100)")
    ap.add_argument("--media-dir", "--media-map", dest="media_map", help="copy local photos/documents into this folder (as media/<name>)")
    ap.add_argument("--media-max", type=int, default=2000,
                    help="shrink photos to at most this many pixels (longest side) if Pillow is available; 0 = don't")
    ap.add_argument("--media-base", "--media-basis", dest="media_basis", help="folder where relative file paths in the GEDCOM start "
                                         "(default: the GEDCOM's folder, then the folder above)")
    a = ap.parse_args()

    recs = parse_gedcom(read_text(a.gedcom))
    indis = [r for r in recs if r["t"] == "INDI" and r["x"]]
    fams = {r["x"]: r for r in recs if r["t"] == "FAM" and r["x"]}
    objs = {r["x"]: r for r in recs if r["t"] == "OBJE" and r["x"]}
    idx = {r["x"]: i for i, r in enumerate(indis)}
    if not indis:
        sys.exit("No people (INDI) found in " + a.gedcom)

    people = []
    for r in indis:
        n, g, s = name_parts(r)
        bdate, bplac = event(r, ("BIRT", "CHR", "BAPM"))
        ddate, dplac = event(r, ("DEAT", "BURI", "CREM"))
        sex = (sub(r, "SEX") or {}).get("v", "").strip().upper()[:1]
        p = {"id": r["x"].strip("@"), "n": n, "g": g, "s": s}
        if sex in ("M", "F"):
            p["x"] = sex
        for k, v in (("bdate", bdate), ("bplac", bplac), ("ddate", ddate), ("dplac", dplac)):
            if v:
                p[k] = v
        if year_of(bdate): p["by"] = year_of(bdate)
        if year_of(ddate): p["dy"] = year_of(ddate)
        jobs = [c["v"].strip() for c in subs(r, "OCCU") if c["v"].strip()]  # occupations, literally, in GEDCOM order
        if jobs: p["beroep"] = jobs
        p["_dead"] = bool(sub(r, "DEAT") or sub(r, "BURI") or sub(r, "CREM"))
        p["f"] = p["m"] = -1
        p["ch"], p["sp"] = [], []
        famc = [c["v"] for c in subs(r, "FAMC")]
        for fx in famc:
            fam = fams.get(fx)
            if not fam:
                continue
            h, w = sub(fam, "HUSB"), sub(fam, "WIFE")
            p["f"] = idx.get(h["v"], -1) if h else -1
            p["m"] = idx.get(w["v"], -1) if w else -1
            break
        md = media_of(r, objs)
        if md:
            p["media"] = md
        people.append(p)
    for i, r in enumerate(indis):
        for c in subs(r, "FAMS"):
            fam = fams.get(c["v"])
            if not fam:
                continue
            for k in ("HUSB", "WIFE"):
                o = sub(fam, k)
                j = idx.get(o["v"]) if o else None
                if j is not None and j != i and j not in people[i]["sp"]:
                    people[i]["sp"].append(j)
            for ch in subs(fam, "CHIL"):
                j = idx.get(ch["v"])
                if j is not None and j not in people[i]["ch"]:
                    people[i]["ch"].append(j)

    # ---- where and when someone lived ("woon"): own events, marriages and the births of their children
    for i, r in enumerate(indis):
        p = people[i]
        pts = dated_places(r, WOON_TAGS)
        if p.get("by") and p.get("bplac"): pts.append((p["by"], p["bplac"]))
        if p.get("dy") and p.get("dplac"): pts.append((p["dy"], p["dplac"]))
        for c in subs(r, "FAMS"):
            fam = fams.get(c["v"])
            if fam: pts += dated_places(fam, ("MARR", "MARB", "MARL", "ENGA", "DIV", "RESI", "CENS", "EVEN"))
        for j in p["ch"]:
            q = people[j]
            if q.get("by") and q.get("bplac"): pts.append((q["by"], q["bplac"]))
        w = residence_spans(pts, p.get("by"), p.get("dy"))
        # abroad: periods in another country, and that country as a 4th element on "woon" periods abroad
        # home country: the country with the most dated facts (ties: the birth country), so an immigrant's new country is home
        cnt = {}
        for y, pl in pts:
            k = country_key(pl)
            if k: cnt[k] = cnt.get(k, 0) + 1
        bk = country_key(p.get("bplac"))
        home = max(cnt, key=lambda k: (cnt[k], k == bk)) if cnt else bk
        weg = abroad_spans(r, p, people, fams, home)
        if weg: p["weg"] = weg
        for x in w:
            k = country_key(x[0])
            if home and k and k != home: x.append(k)
        if w: p["woon"] = w

    # ---- media: copy local files (only with --media-dir)
    for p in people:  # original GEDCOM path -> published path (for "scan" on story images)
        p["_media_orig"] = {m["bestand"]: m["bestand"] for m in p.get("media", [])}
    n_media = sum(len(p.get("media", [])) for p in people)
    n_kop = n_mis = 0
    if a.media_map:
        os.makedirs(a.media_map, exist_ok=True)
        gdir = os.path.dirname(os.path.abspath(a.gedcom))
        bases = [a.media_basis] if a.media_basis else [gdir, os.path.dirname(gdir)]
        gebruikt, gekopieerd = set(), {}  # existing copies are overwritten
        for p in people:
            houden = []
            for m in p.get("media", []):
                b = m["bestand"]
                if re.match(r"^(https?:|data:)", b):
                    houden.append(m); continue
                pad = next((os.path.join(d, b) for d in ([""] if os.path.isabs(b) else bases)
                            if os.path.isfile(os.path.join(d, b))), None)
                if not pad:
                    n_mis += 1
                    print(f"  media not found, skipped: {b} ({p['n']})"); continue
                if pad not in gekopieerd:
                    gekopieerd[pad] = kopieer_media(pad, a.media_map, gebruikt, a.media_max)
                    groot = os.path.getsize(os.path.join(a.media_map, gekopieerd[pad]))
                    if groot > 5_000_000:
                        print(f"  note: large file ({groot//1_000_000} MB): {b}")
                p["_media_orig"][b] = "media/" + gekopieerd[pad]
                m = dict(m, bestand="media/" + gekopieerd[pad]); n_kop += 1
                houden.append(m)
            if houden: p["media"] = houden
            else: p.pop("media", None)
        print(f"media: {len(gekopieerd)} files to {a.media_map} ({n_kop} links, {n_mis} not found)")
    elif n_media:
        print(f"media: {n_media} links (paths unchanged; use --media-dir to publish them)")

    # ---- certainty
    for p in people:
        c = {}
        if p["f"] >= 0: c["f"] = ["niet gecheckt", "", ""]
        if p["m"] >= 0: c["m"] = ["niet gecheckt", "", ""]
        if c: p["c"] = c
    if a.csv:
        by_name = {}
        for i, p in enumerate(people):
            by_name.setdefault(norm(p["n"]), []).append(i)
        def find(v):
            v = (v or "").strip()
            if not v: return None
            k = v if v.startswith("@") else "@" + v.strip("@") + "@"
            if k in idx: return idx[k]
            m = re.match(r"^(.*?)\s*\((\d{3,4})\)\s*$", v)
            name, yr = (m.group(1), int(m.group(2))) if m else (v, None)
            cands = by_name.get(norm(name), [])
            if yr: cands = [i for i in cands if people[i].get("by") == yr] or cands
            return cands[0] if len(cands) == 1 else None
        n_ok = n_bad = 0
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            # Only detect the delimiter (from the header). csv.Sniffer guesses the apostrophe in names like
            # Johannes 'John' as quote character and then cuts notes off at the first comma.
            header = fh.readline(); fh.seek(0)
            delim = max(",;\t", key=header.count)
            for row in csv.DictReader(fh, delimiter=delim, quotechar='"'):
                ci = find(col(row, "kind_id", "child_id", "kind", "child"))
                pi = find(col(row, "ouder_id", "parent_id", "ouder", "parent"))
                if ci is None or pi is None:
                    n_bad += 1; continue
                role = "f" if people[ci]["f"] == pi else "m" if people[ci]["m"] == pi else None
                if role is None:
                    n_bad += 1; continue
                people[ci].setdefault("c", {})[role] = [norm_status(col(row, "status", "zekerheid", "certainty")),
                                                        col(row, "bron", "source"), col(row, "opmerking", "opm", "note", "notes")]
                soort = (col(row, "soort", "relatie", "relation", "type", "kind") or "").strip().lower()
                soort = REL_TYPE.get(soort, soort)
                if soort and soort not in ("biologisch", "biological"):
                    people[ci]["c"][role].append(soort)
                n_ok += 1
        print(f"CSV: {n_ok} relations read, {n_bad} rows skipped (person not found or not a parent-child relation)")

    # ---- regions
    regios, table = {}, {}
    if a.regios:
        rt = json.load(open(a.regios, encoding="utf-8"))
        regios.update(rt.get("regios", {}))
        table = {norm(k): v for k, v in rt.get("plaatsen", {}).items()}
    for p in people:
        r = region_of(p.get("bplac"), table) or region_of(p.get("dplac"), table)  # no birth place: use place of death
        if r:
            p["r"] = r
            if r not in regios and r in COUNTRIES:
                _, nl, en, kleur = COUNTRIES[r]
                regios[r] = {"naam": {"nl": nl, "en": en}, "kleur": kleur}
    used = {p["r"] for p in people if p.get("r")}
    regios = {k: v for k, v in regios.items() if k in used}

    # ---- living
    cutoff = datetime.date.today().year - a.levend_grens
    def est_year(i, seen=()):
        p = people[i]
        if p.get("by"): return p["by"]
        ys = [people[q]["by"] + 27 for q in (p["f"], p["m"]) if q >= 0 and people[q].get("by")]
        ys += [people[c]["by"] - 30 for c in p["ch"] if people[c].get("by")]
        ys += [people[s]["by"] for s in p["sp"] if people[s].get("by")]
        return max(ys) if ys else None
    surn0 = [p.get("s", "") for p in people]
    n_lev = 0
    for i, p in enumerate(people):
        dead = p.pop("_dead") or p.get("ddate") or p.get("dy")
        y = est_year(i)
        if not dead and y is not None and y >= cutoff:
            p["levend"] = True; n_lev += 1
            if a.levenden_verbergen:
                for k in ("bdate", "bplac", "ddate", "dplac", "by", "dy", "r", "media", "beroep", "woon", "weg"):
                    p.pop(k, None)

    # ---- start people
    def anc_count(i):
        seen, st = set(), [i]
        while st:
            j = st.pop()
            for q in (people[j]["f"], people[j]["m"]):
                if q >= 0 and q not in seen: seen.add(q); st.append(q)
        return len(seen)
    def resolve(v):
        v = v.strip()
        k = v if v.startswith("@") else "@" + v.strip("@") + "@"
        if k in idx: return idx[k]
        c = [i for i, p in enumerate(people) if norm(p["n"]) == norm(v)]
        if len(c) == 1: return c[0]
        sys.exit(f"Start person not found (or not unique): {v}")
    starts = []
    for s in a.start:
        who, label = (s.rsplit(":", 1) + [""])[:2] if ":" in s else (s, "")
        i = resolve(who)
        starts.append({"persoon": i, **({"label": label} if label else {})})
    if not starts:
        best = max(range(len(people)), key=lambda i: (anc_count(i), people[i].get("by") or 0))
        starts = [{"persoon": best}]

    # ---- own stories (Story view)
    if a.verhalen:
        with open(a.verhalen, encoding="utf-8") as fh:
            vh = json.load(fh)
        n_vh = 0
        for key, val in vh.items():
            if key.startswith("_"): continue
            k = key if key.startswith("@") else "@" + key.strip("@") + "@"
            if k in idx: i = idx[k]
            else:
                c = [j for j, p in enumerate(people) if norm(p["n"]) == norm(key)]
                if len(c) != 1:
                    print(f"Story skipped, person not found (or not unique): {key}", file=sys.stderr); continue
                i = c[0]
            if isinstance(val, dict) and ("tekst" in val or "text" in val):
                people[i]["verhaal"] = val.get("tekst", val.get("text"))
                src = val.get("bronnen") or val.get("sources")
                img = val.get("beelden") or val.get("images")
                if src: people[i]["verhaal_bronnen"] = src
                if img: people[i]["verhaal_beelden"] = img_kinds(img)
            else:
                people[i]["verhaal"] = val
            n_vh += 1
        # "scan" on a story image: the full scan of a clipping, as in the GEDCOM OBJE -> the same published path as that media
        for p in people:
            for b in p.get("verhaal_beelden") or []:
                if not isinstance(b, dict) or not b.get("scan"): continue
                orig, sc = p.get("_media_orig", {}), str(b["scan"]).strip()
                hit = orig.get(sc) or next((v for k, v in orig.items() if v == sc or os.path.basename(k) == os.path.basename(sc)), None)
                if hit: b["scan"] = hit
                else: print(f"  warning, story image of {p['n']}: \"scan\": {sc} is not one of this person's photos/documents (OBJE)", file=sys.stderr)
        n_warn = sum(story_image_warnings(p, p["verhaal_beelden"]) for p in people if p.get("verhaal_beelden"))
        print(f"Stories: {n_vh} read" + (f", {n_warn} warning(s) about story images (see above)" if n_warn else ""))

    for p in people: p.pop("_media_orig", None)
    fam = a.familienaam or surn0[starts[0]["persoon"]] or ""
    out = {"versie": 2, "taal": a.taal}
    if a.titel: out["titel"] = a.titel
    if fam: out["familienaam"] = fam
    out["startpersonen"] = starts
    if a.stamlijn_start: out["startpersoon_per_weergave"] = {"stamlijn": resolve(a.stamlijn_start)}
    if not a.levenden_verbergen: out["levenden_tonen"] = True
    if regios: out["regios"] = regios
    if table: out["plaatsen"] = {k: v for k, v in sorted(table.items())}
    for p in people:
        for k in ("ch", "sp"):
            if not p[k]: del p[k]
        if p.get("g") == "": del p["g"]
        if p.get("s") == "": del p["s"]
    if a.tijdgeest:
        with open(a.tijdgeest, encoding="utf-8") as fh:
            out["tijdgeest"] = json.load(fh)
        tg = out["tijdgeest"]
        for pl in tg.get("plaatsen", []):
            if pl.get("beelden"): pl["beelden"] = img_kinds(pl["beelden"])
        print(f"Zeitgeist: {len(tg.get('plaatsen', []))} place(s), "
              f"{sum(len(x.get('beelden', [])) for x in tg.get('plaatsen', []))} images")
    out["personen"] = people
    with open(a.uit, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"{a.uit}: {len(people)} people, {len(fams)} families, {n_lev} living"
          f"{' (details hidden)' if n_lev and a.levenden_verbergen else ''}, "
          f"start person: {people[starts[0]['persoon']]['n']}, regions: {', '.join(sorted(used)) or 'none'}")

if __name__ == "__main__":
    main()
