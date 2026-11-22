#!/usr/bin/env python3
"""make_viewer_data.py — builds data.json (format v2) for the family-tree viewer from a GEDCOM file.

Only a GEDCOM is required. Optional:
  --csv        certainty per child-parent relation (see DATA-FORMAT.md, "Certainty CSV")
  --regions    region table as JSON: {"regios": {code: {"naam": ..., "kleur": "#hex"}}, "plaatsen": {place: code}}
  --stories    the user's own stories per person as JSON (see DATA-FORMAT.md, "Stories")
  --zeitgeist  life and times per place (daily life, events, old images) as JSON (see DATA-FORMAT.md, "Zeitgeist")
  --coords     coordinates per place as JSON, from geocode_places.py (for the maps in Story and Cards)
  --media-dir  copy photos and documents (GEDCOM OBJE/FILE) into this folder as media/<name>,
               so they can be published next to index.html

Examples:
  python3 make_viewer_data.py tree.ged data.json
  python3 make_viewer_data.py tree.ged data.json --start @I12@:Femke --start "Thomas de Vries" --lang nl
  python3 make_viewer_data.py tree.ged data.json --csv relations.csv --regions regions.json --title "The De Vries family"

All of this can live in one settings file, so the command stays short and every tool builds the same data.json:
  python3 make_viewer_data.py --config family-tree.json
  python3 make_viewer_data.py            (no GEDCOM given: uses family-tree.json or stamboom.json in this folder)
Keys in English or Dutch; paths are relative to the settings file's folder; options on the command line win.
Format: references/viewer.md, "One settings file".

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

def aka_names(indi, display, given, surn):
    """Other names someone was known by: a NICK under any NAME, and every NAME after the first (aka, married name, …).
    Same surname: only the first names ("Jopie"); another surname: the whole name."""
    out = []
    for k, nm in enumerate(subs(indi, "NAME")):
        out += [c["v"].strip() for c in subs(nm, "NICK") if c["v"].strip()]
        if k == 0:
            continue
        full = nm["v"] or ""
        m = re.match(r"^(.*?)/(.*?)/(.*)$", full)
        g2 = ((sub(nm, "GIVN") or {}).get("v", "") or (m.group(1) if m else full)).strip()
        s2 = ((sub(nm, "SURN") or {}).get("v", "") or (m.group(2) if m else "")).strip()
        v = " ".join((g2 if not s2 or s2 == surn else g2 + " " + s2).split())
        if v:
            out.append(v)
    seen, res = {display.lower(), given.lower()}, []
    for v in out:
        if v.lower() not in seen:
            seen.add(v.lower()); res.append(v)
    return res

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
WHY_MIN = 25  # a certain/probable/possible link with a shorter reason gets a warning
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
                    prim = (sub(n, "_PRIM") or sub(o, "_PRIM") or {}).get("v", "").strip().upper()
                    if prim in ("Y", "YES", "1"): m["portret"] = True  # the main photo (Ancestry, FTM, RootsMagic; media.csv "portrait")
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
            if "card" in b and "kaart" not in b:  # ... and after which card of the card version (1-based)
                b["kaart"] = b.pop("card")
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


# what happened at a place, for the sentence before a map ("woon_feiten"): GEDCOM tag -> stored kind (Dutch, like the other values)
FACT_KIND = {"CHR": "doop", "BAPM": "doop", "RESI": "woonde", "CENS": "volkstelling", "OCCU": "beroep", "EDUC": "school",
             "EMIG": "emigratie", "IMMI": "immigratie", "NATU": "naturalisatie", "EVEN": "gebeurtenis",
             "MARR": "huwelijk", "MARB": "ondertrouw", "MARL": "ondertrouw", "ENGA": "verloving", "DIV": "scheiding"}


def placed_facts(node, tags):
    """[year, place, kind, extra] for dated events with a place (extra: the occupation, or the type of an EVEN)."""
    out = []
    for e in node["c"]:
        if e["t"] not in tags or e["t"] not in FACT_KIND: continue
        y = year_of((sub(e, "DATE") or {}).get("v", ""))
        pl = (sub(e, "PLAC") or {}).get("v", "").strip()
        if not pl:
            ad = sub(e, "ADDR")
            pl = ((sub(ad, "CITY") or {}).get("v", "") if ad else "").strip()
        if not (y and pl): continue
        x = e["v"].strip() if e["t"] == "OCCU" else (sub(e, "TYPE") or {}).get("v", "").strip() if e["t"] == "EVEN" else ""
        out.append([y, pl, FACT_KIND[e["t"]]] + ([x] if x else []))
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


# A story that leans on a newspaper should show the clipping: a link to Delpher or Trove in its sources,
# or a newspaper's name in a source's label
NEWS_LINK = re.compile(r"resolver\.kb\.nl|delpher\.nl|trove\.nla\.gov\.au|newspapers\.com|chroniclingamerica", re.I)
NEWS_NAME = re.compile(r"\b(\w*(courant|krant|dagblad|nieuwsblad|handelsblad|weekblad|telegraaf|tidning|zeitung)\w*"
                       r"|\w*(residentie|maas|nieuws|dorps|stads|amstel|zaan|gooi|eem|graafschap|grens|lands?)bode|newspaper|gazette|herald|tribune|chronicle|advertiser|weekly)\b", re.I)
NEWS_TITLE = re.compile(r"\b(De Tijd|Het Vaderland|Het Volk|The Times)\b")  # titles that are plain words in lower case


def map_town(pl):
    """The town in a place name, as the viewer's mapName: with four or more parts the third from the end (a street in a town)."""
    a = [x.strip() for x in str(pl or "").split(",") if x.strip()]
    return re.sub(r"\s*\(.*?\)\s*", " ", a[len(a) - 3 if len(a) >= 4 else 0] if a else "").strip()


def story_map_warnings(p, coords):
    """Places of someone with an own story that may get a map (birth, homes, death, story places without "alinea")
    but are named nowhere in the story text: the viewer then puts a short template sentence before that map."""
    txt = p.get("verhaal")
    txt = " ".join(txt.values()) if isinstance(txt, dict) else " ".join(txt) if isinstance(txt, list) else str(txt or "")
    t = norm(txt)
    pls = [p.get("bplac")] + [w[0] for w in p.get("woon") or []] + [p.get("dplac")] \
        + [x["plaats"] for x in p.get("verhaal_plekken") or [] if x.get("alinea") is None]
    miss = []
    for pl in pls:
        if not pl or pl not in coords: continue
        tw = map_town(pl)
        if tw and norm(tw) not in t and tw not in miss: miss.append(tw)
    if not miss: return 0
    print(f"  note, story of {p['n']}: map place(s) not named in the story: {', '.join(miss)}", file=sys.stderr)
    return 1


def story_clipping_warnings(p):
    """A story citing a newspaper (Delpher/Trove link or a paper's name in a source) without a "krant" image."""
    src = p.get("verhaal_bronnen")
    if not src: return 0
    if any(isinstance(b, dict) and str(b.get("soort") or "").lower() == "krant" for b in p.get("verhaal_beelden") or []):
        return 0
    hits = []
    for s in src if isinstance(src, list) else [src]:
        label, url = (s[0] if s else "", s[1] if len(s) > 1 else "") if isinstance(s, (list, tuple)) else \
                     ((s.get("label") or s.get("titel") or s.get("title") or "", s.get("url") or "") if isinstance(s, dict) else (str(s), ""))
        label = next(iter(label.values()), "") if isinstance(label, dict) else str(label)
        m = NEWS_LINK.search(str(url)) or NEWS_LINK.search(label) or NEWS_NAME.search(label) or NEWS_TITLE.search(label)
        if m: hits.append(label.strip() or str(url))
    if not hits: return 0
    print(f"  warning, story of {p['n']}: this story cites a newspaper without a clipping ({hits[0][:70]}"
          + (f" and {len(hits) - 1} more" if len(hits) > 1 else "") + "): add the clipping the text leans on as a story image"
          " with \"soort\": \"krant\" (scripts/delpher.py cuts it), and put other finds in media.csv as documents", file=sys.stderr)
    return 1


CARD_MAX = 250       # characters per card (aim for ~200)
PARA_LONG = 350      # a story paragraph this long, without a card version: suggest one
FIRST_CARD_TIME = re.compile(
    r"\b(1[5-9]\d\d|20\d\d)\b"                                              # a year
    r"|\b\d{1,3}\s*(jaar|years?)\b|\b\d{1,2}-?jarige?\b|\b\w+jarige\b"           # "16 jaar", "16-jarige", "zestienjarige"
    r"|\bop (zijn|haar|z'n) \w+(de|ste|e)\b|\btoen (hij|zij|ze) \w+( jaar)?( oud)? was\b"
    r"|\bat (the age of )?\d{1,2}\b|\baged \w+\b|\bwhen (he|she) was (?!born)\w+\b", re.I)


def split_paras(t):
    return [x.strip() for x in re.split(r"\n\s*\n", t) if x.strip()] if isinstance(t, str) else []


def story_card_warnings(p):
    """The card version of a story ("verhaal_kaarten"): short cards, a hook first, the same number in every language,
    every image on an existing card. Without a card version: a hint when a paragraph is long. Only warnings."""
    out, cards, text = [], p.get("verhaal_kaarten"), p.get("verhaal")
    if cards:
        per = {k: split_paras(v) for k, v in (cards.items() if isinstance(cards, dict) else [("", cards)])}
        if len({len(v) for v in per.values()}) > 1:
            out.append("cards: not the same number in each language (" + ", ".join(f"{k} {len(v)}" for k, v in per.items()) + ")")
        for lang, cs in per.items():
            tag = f" ({lang})" if lang else ""
            for j, c in enumerate(cs, 1):
                if len(c) > CARD_MAX: out.append(f"card {j}{tag} has {len(c)} characters (max. {CARD_MAX}, aim for ~200)")
            m = FIRST_CARD_TIME.search(cs[0]) if cs else None
            if m:
                ys = [int(y) for y in re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", cs[0])]
                moves = any(y != p.get("by") for y in ys) or not ys
                out.append(f"card 1{tag} has a year or age (\"{m.group(0)}\"); make it a hook without one"
                           + (": the viewer places cards by year, so the whole series moves to that moment" if moves else ""))
        n = max((len(v) for v in per.values()), default=0)
        for b in p.get("verhaal_beelden") or []:
            if not isinstance(b, dict): continue
            name = b.get("bestand") or "?"
            k = b.get("kaart")
            if k is None: out.append(f"image {name}: no \"kaart\" (after which card does it belong?)")
            else:
                try: ok = 1 <= int(k) <= n
                except (TypeError, ValueError): ok = False
                if not ok: out.append(f"image {name}: \"kaart\": {k} does not exist (the story has {n} card(s))")
    else:
        texts = text.values() if isinstance(text, dict) else [text]
        longest = max((len(x) for t in texts for x in split_paras(t)), default=0)
        if longest > PARA_LONG:
            out.append(f"no card version (\"kaarten\") and a paragraph of {longest} characters; consider writing cards")
    out += story_budget_warnings(p)
    for w in out:
        print(f"  warning, story of {p['n']}: {w}", file=sys.stderr)
    return len(out)


BUDGET_OWN = 12      # own cards (intro, story, separate images, farewell); zeitgeist and wars add ~2-5, aim for ~15 in all
PAPER = re.compile(r"^(krant|scan|document|kaart)$", re.I)


def story_budget_warnings(p):
    """Estimate the person's own cards in the Cards view, the way the viewer builds them: intro, one card per story card
    (or paragraph), the first ordinary image after a card goes under its text (text on the image), other images and
    clippings/scans/documents/maps are cards of their own, farewell. Zeitgeist and war cards come on top and depend on the
    trail, and so do runs of text cards: for exact numbers open the viewer with #kaartbudget (#cardbudget)."""
    cards, text = p.get("verhaal_kaarten"), p.get("verhaal")
    src = cards or text
    first = next(iter(src.values()), "") if isinstance(src, dict) else src
    paras = split_paras(first)
    if not paras: return []
    key = "kaart" if cards else "alinea"
    imgs = {}
    loose = 0
    for b in p.get("verhaal_beelden") or []:
        if not isinstance(b, dict) or not b.get("bestand"): continue
        try: n = int(b.get(key) if b.get(key) is not None else b.get("alinea"))
        except (TypeError, ValueError): loose += 1; continue
        imgs.setdefault(min(max(n, 1), len(paras)), []).append(b)
    seq = ["T"]  # intro
    for n in range(1, len(paras) + 1):
        bs = imgs.get(n, [])
        ordinary = [b for b in bs if not PAPER.match(str(b.get("soort") or "")) and not b.get("scan")]
        seq.append("I" if ordinary else "T")
        seq += ["I"] * (len(bs) - (1 if ordinary else 0))
    seq += ["I"] * loose + ["T"]  # farewell
    out = []
    if len(seq) > BUDGET_OWN:
        out.append(f"about {len(seq)} own cards in Cards (intro, {len(paras)} story cards, {len(seq) - len(paras) - 2} separate image card(s), farewell); "
                   f"with zeitgeist and wars that is more than ~15: merge or drop cards (aim: {BUDGET_OWN} or fewer)")
    return out


FRONT_YEAR = re.compile(r"(?:[\w.'’-]+\s+){0,3}?(1[5-9]\d\d|20\d\d)\b")  # a year at the front of a card dates it (same rule as the viewer)


def zeitgeist_card_warnings(pl, L):
    """A zeitgeist "leven" block: short cards (at most CARD_MAX characters), or a hint when a paragraph is long and there are no cards."""
    if not isinstance(L, dict): return 0
    name = pl.get("naam") or pl.get("id") or "?"
    if isinstance(name, dict): name = next(iter(name.values()), "?")
    title = L.get("titel") or f"{L.get('van', '?')}-{L.get('tot', '?')}"
    if isinstance(title, dict): title = next(iter(title.values()), "?")
    out, cards = [], L.get("kaarten")
    if cards:
        per = {k: split_paras(v) for k, v in (cards.items() if isinstance(cards, dict) else [("", cards)])}
        if len({len(v) for v in per.values()}) > 1:
            out.append("cards: not the same number in each language (" + ", ".join(f"{k} {len(v)}" for k, v in per.items()) + ")")
        for lang, cs in per.items():
            for j, c in enumerate(cs, 1):
                if len(c) > CARD_MAX: out.append(f"card {j}{f' ({lang})' if lang else ''} has {len(c)} characters (max. {CARD_MAX}, aim for ~200)")
                m = FRONT_YEAR.match(c.strip())
                van, tot = L.get("van"), L.get("tot")
                if m and isinstance(van, int) and isinstance(tot, int) and not (van <= int(m.group(1)) <= tot):
                    out.append(f"card {j}{f' ({lang})' if lang else ''} starts with {m.group(1)}, outside this block ({van}-{tot}); "
                               "Cards only show it to people alive then")
    else:
        t = L.get("tekst") or L.get("text")
        longest = max((len(x) for v in (t.values() if isinstance(t, dict) else [t]) for x in split_paras(v)), default=0)
        if longest > PARA_LONG:
            out.append(f"no card version (\"kaarten\") and a paragraph of {longest} characters; consider writing cards")
    for w in out:
        print(f"  warning, zeitgeist {name}, \"{title}\": {w}", file=sys.stderr)
    return len(out)


def story_places(lst):
    """"plekken"/"places" of a story: [{"plaats": "Ahuys", "alinea": 1, "kaart": 1}] or plain strings -> Dutch keys."""
    out = []
    for pl in lst or []:
        if isinstance(pl, str): pl = {"plaats": pl}
        if not isinstance(pl, dict): continue
        e = {"plaats": pl.get("plaats") or pl.get("place")}
        for nl, en in (("alinea", "paragraph"), ("kaart", "card"), ("jaar", "year"), ("bijschrift", "caption")):
            v = pl.get(nl, pl.get(en))
            if v is not None: e[nl] = v
        if e["plaats"]: out.append(e)
    return out


def coords_for(people, cf):
    """{place: [lat, lon, precision]} for every place a person or story uses; warns about places without coordinates."""
    by_norm = {norm(k): v for k, v in cf.items() if not k.startswith("_") and isinstance(v, dict)}
    used = []
    for p in people:
        for pl in [p.get("bplac"), p.get("dplac")] + [w[0] for w in p.get("woon") or []] + [x["plaats"] for x in p.get("verhaal_plekken") or []]:
            if pl and pl not in used: used.append(pl)
    out, missing, vague = {}, [], 0
    used = [pl for pl in used if not re.match(r"^(ndg|onbekend|unknown|\?+|-+|n/?a|nvt)$", pl.strip(), re.I)]  # not a place
    for pl in used:
        e = cf.get(pl) if isinstance(cf.get(pl), dict) else by_norm.get(norm(pl))
        if not e and "," not in pl:  # a short name in a story ("Amersfoort"): the one place in the file that starts with it
            hit = [v for k, v in by_norm.items() if k.split(",")[0].strip() == norm(pl)]
            if len(hit) == 1: e = hit[0]
        prec = e and (e.get("precisie") or PREC_EN.get(str(e.get("precision", "")).lower(), e.get("precision")))
        if not e or e.get("lat") is None or e.get("lon") is None or prec in (None, "onbekend", "unknown"):
            missing.append(pl); continue
        prec = prec if prec in ("plaats", "regio", "land") else "plaats"
        if prec != "plaats": vague += 1
        out[pl] = [round(float(e["lat"]), 4), round(float(e["lon"]), 4), prec]
    print(f"Coordinates: {len(out)} of {len(used)} place(s)" + (f", {vague} only region/country (no pin)" if vague else ""))
    if missing:
        print(f"  warning, {len(missing)} place(s) without coordinates (run geocode_places.py, or add them by hand): "
              + "; ".join(missing[:15]) + (" ..." if len(missing) > 15 else ""), file=sys.stderr)
    return out


# ---------------------------------------------------------------- base map (Natural Earth) for the maps
GEO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geo", "natural-earth.json")
MAP_FINE_MAX_KM = 320   # maps up to this width use the detailed (10m) coastlines; wider maps the coarse (50m) ones
MAP_DETAIL_KM = 120     # width of the detail map around one place (keep equal to MAP_DETAIL_KM in the viewer)
MAP_CELL = 1            # detailed coastlines are cut into cells of this many degrees


def geo_decode(r):
    out, x, y = [], 0, 0
    for i in range(0, len(r) - 1, 2):
        x += r[i]; y += r[i + 1]; out.append((x, y))
    return out


def geo_encode(pts):
    out, px, py = [], 0, 0
    for i, (x, y) in enumerate(pts):
        if i and x == px and y == py: continue
        out += [x - px, y - py] if i else [x, y]; px, py = x, y
    return out


def clip_poly(pts, x0, y0, x1, y1):
    """Sutherland-Hodgman: a polygon cut to a rectangle (for the fill; the edges of the cut are never stroked)."""
    def cut(pts, inside, inter):
        out = []
        for i, b in enumerate(pts):
            a = pts[i - 1]
            if inside(b):
                if not inside(a): out.append(inter(a, b))
                out.append(b)
            elif inside(a): out.append(inter(a, b))
        return out
    def ix(xc):
        return lambda a, b: (xc, round(a[1] + (b[1] - a[1]) * (xc - a[0]) / (b[0] - a[0])))
    def iy(yc):
        return lambda a, b: (round(a[0] + (b[0] - a[0]) * (yc - a[1]) / (b[1] - a[1])), yc)
    for inside, inter in ((lambda p: p[0] >= x0, ix(x0)), (lambda p: p[0] <= x1, ix(x1)),
                          (lambda p: p[1] >= y0, iy(y0)), (lambda p: p[1] <= y1, iy(y1))):
        pts = cut(pts, inside, inter)
        if not pts: return []
    return pts


def clip_line(pts, x0, y0, x1, y1):
    """A line (coast, border) cut to a rectangle: the pieces inside (Liang-Barsky per segment)."""
    out, cur = [], []
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]; t0, t1 = 0.0, 1.0; ok = True
        for pp, qq in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
            if pp == 0:
                if qq < 0: ok = False; break
            else:
                t = qq / pp
                if pp < 0: t0 = max(t0, t)
                else: t1 = min(t1, t)
        if not ok or t0 > t1:
            if len(cur) > 1: out.append(cur)
            cur = []; continue
        pa = (round(a[0] + dx * t0), round(a[1] + dy * t0)); pb = (round(a[0] + dx * t1), round(a[1] + dy * t1))
        if not cur or cur[-1] != pa:
            if len(cur) > 1: out.append(cur)
            cur = [pa]
        cur.append(pb)
        if t1 < 1:
            out.append(cur); cur = []
    if len(cur) > 1: out.append(cur)
    return out


def map_window(lat, lon, km):
    """lon/lat box of a map km wide around a point (square, with 30% to spare)."""
    import math
    dlat = km / 111.32 / 2 * 1.3
    dlon = dlat / max(.15, math.cos(math.radians(lat)))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def base_map(people, coords):
    """The coastlines, lakes and borders the maps need: the detailed ones cut into cells around the places, the coarse world whole."""
    import math
    try:
        with open(GEO_FILE, encoding="utf-8") as fh: geo = json.load(fh)
    except OSError:
        print(f"  warning, no base map ({GEO_FILE} missing): the maps are left out", file=sys.stderr); return None
    pin = {k: v for k, v in coords.items() if v[2] == "plaats"}
    boxes = [map_window(v[0], v[1], MAP_DETAIL_KM) for v in pin.values()]
    # Story: one map per person with all their places; when that fits the detailed width, its whole window is needed
    for p in people:
        pts = [pin[x] for x in [p.get("bplac"), p.get("dplac")] + [w[0] for w in p.get("woon") or []]
               + [x["plaats"] for x in p.get("verhaal_plekken") or []] if x in pin]
        if len(pts) < 2: continue
        la0, la1 = min(q[0] for q in pts), max(q[0] for q in pts); lo0, lo1 = min(q[1] for q in pts), max(q[1] for q in pts)
        span = max((la1 - la0) * 111.32, (lo1 - lo0) * 111.32 * math.cos(math.radians((la0 + la1) / 2)))
        if span * 1.4 <= MAP_FINE_MAX_KM:
            boxes.append(map_window((la0 + la1) / 2, (lo0 + lo1) / 2, max(MAP_DETAIL_KM, span * 1.4)))
    cells = set()
    for x0, y0, x1, y1 in boxes:
        for cx in range(math.floor(x0 / MAP_CELL), math.floor(x1 / MAP_CELL) + 1):
            for cy in range(math.floor(y0 / MAP_CELL), math.floor(y1 / MAP_CELL) + 1):
                cells.add((cx, cy))
    F = geo["fijn"]; q = F["q"]; c = MAP_CELL * q
    def prep(lst):
        out = []
        for r in lst:
            pts = geo_decode(r); xs = [t[0] for t in pts]; ys = [t[1] for t in pts]
            out.append((min(xs), min(ys), max(xs), max(ys), pts))
        return out
    land, lakes, bord = prep(F["land"]), prep(F["meren"]), prep(F["grenzen"])
    rivers = [(a, b, c2, d, pts, r[0]) for r, (a, b, c2, d, pts) in zip(F.get("rivieren", []), prep([r[1:] for r in F.get("rivieren", [])]))]
    fine = {}
    for cx, cy in sorted(cells):
        x0, y0, x1, y1 = cx * c, cy * c, (cx + 1) * c, (cy + 1) * c
        cell = {}
        for key, src, poly in (("l", land, True), ("m", lakes, True), ("g", bord, False)):
            for a0, b0, a1, b1, pts in src:
                if a1 < x0 or a0 > x1 or b1 < y0 or b0 > y1: continue
                if poly:
                    if a0 >= x0 and a1 <= x1 and b0 >= y0 and b1 <= y1:
                        cell.setdefault(key, []).append(geo_encode(pts))
                        cell.setdefault(key + "k", []).append(geo_encode(pts + pts[:1]))
                        continue
                    cp = clip_poly(pts, x0, y0, x1, y1)
                    if len(cp) >= 3: cell.setdefault(key, []).append(geo_encode(cp))
                    for ln in clip_line(pts + pts[:1], x0, y0, x1, y1): cell.setdefault(key + "k", []).append(geo_encode(ln))
                else:
                    for ln in clip_line(pts, x0, y0, x1, y1): cell.setdefault(key, []).append(geo_encode(ln))
        # rivers: [scalerank, x0, y0, dx1, ...] per piece inside the cell
        for a0, b0, a1, b1, pts, rank in rivers:
            if a1 < x0 or a0 > x1 or b1 < y0 or b0 > y1: continue
            for ln in clip_line(pts, x0, y0, x1, y1): cell.setdefault("r", []).append([rank] + geo_encode(ln))
        fine[f"{cx},{cy}"] = cell  # an empty cell = sea (the viewer then knows the cell is included)
    # coarse rivers (for route maps) only near the places: lines that reach within ~2,500 km of a pinned place
    grof = dict(geo["grof"])
    if grof.get("rivieren"):
        qg = grof["q"]; far = [map_window(v[0], v[1], 5000) for v in pin.values()]
        def near(r):
            pts = geo_decode(r[1:]); xs = [t[0] / qg for t in pts]; ys = [t[1] / qg for t in pts]
            return any(min(xs) <= bx1 and max(xs) >= bx0 and min(ys) <= by1 and max(ys) >= by0 for bx0, by0, bx1, by1 in far)
        grof["rivieren"] = [r for r in grof["rivieren"] if near(r)]
    out = {"bron": "Natural Earth", "fijn_max_km": MAP_FINE_MAX_KM, "cel": MAP_CELL,
           "fijn": {"q": q, "cellen": fine}, "grof": grof}
    size = len(json.dumps(out, separators=(",", ":"))) // 1024
    print(f"Base map: {len(fine)} detailed cell(s) around the places, coarse world map; {size} kB")
    return out


PREC_EN = {"place": "plaats", "town": "plaats", "region": "regio", "country": "land", "unknown": "onbekend"}


# ---------------------------------------------------------------- settings file (--config)
CONFIG_NAMES = ("family-tree.json", "stamboom.json")  # looked for in the current folder when no GEDCOM is given
CONFIG_KEYS = {  # key in the settings file (English or Dutch) -> argparse dest
    "gedcom": "gedcom", "ged": "gedcom", "output": "uit", "uit": "uit",
    "csv": "csv", "regions": "regios", "regios": "regios", "start": "start",
    "lineage_start": "stamlijn_start", "stamlijn_start": "stamlijn_start",
    "title": "titel", "titel": "titel", "family_name": "familienaam", "familienaam": "familienaam",
    "lang": "taal", "taal": "taal", "hide_living": "levenden_verbergen", "levenden_verbergen": "levenden_verbergen",
    "zeitgeist": "tijdgeest", "tijdgeest": "tijdgeest", "stories": "verhalen", "verhalen": "verhalen",
    "updated": "bijgewerkt", "bijgewerkt": "bijgewerkt", "living_years": "levend_grens", "levend_grens": "levend_grens",
    "coords": "coordinaten", "coordinaten": "coordinaten", "media_dir": "media_map", "media_map": "media_map",
    "media_max": "media_max", "media_base": "media_basis", "media_basis": "media_basis",
}
CONFIG_PATHS = {"gedcom", "uit", "csv", "regios", "tijdgeest", "verhalen", "coordinaten", "media_map", "media_basis"}
CONFIG_IGNORED = ("publish", "publiceren")  # from 0.9.52 (publishing was taken out again): ignored, so old files keep working


def find_config(folder="."):
    for n in CONFIG_NAMES:
        if os.path.isfile(os.path.join(folder, n)):
            return os.path.join(folder, n)
    return None


def load_config(path):
    """Read a settings file -> options as argparse dests. Paths become absolute."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            raw = json.load(fh)
    except (OSError, ValueError) as e:
        sys.exit(f"Settings file {path}: {e}")
    if not isinstance(raw, dict):
        sys.exit(f"Settings file {path}: expected an object {{...}}")
    base = os.path.dirname(os.path.abspath(path))
    opts, bad = {}, []
    for k, v in raw.items():
        key = k.strip().lower().replace("-", "_").replace(" ", "_")
        if key.startswith("_"):
            continue  # "_note": "..." is a comment
        if key in CONFIG_IGNORED:
            continue
        dest = CONFIG_KEYS.get(key)
        if not dest:
            bad.append(k); continue
        if v is None or v == "" or v == []:
            continue
        if dest in CONFIG_PATHS:
            v = os.path.join(base, os.path.expanduser(str(v)))
        elif dest == "start":
            v = [v] if isinstance(v, (str, dict)) else list(v)
            out = []
            for s in v:
                if isinstance(s, dict):
                    who = s.get("id") or s.get("person") or s.get("persoon") or s.get("name") or s.get("naam")
                    if not who: sys.exit(f"Settings file {path}: start entry without id: {s}")
                    lab = s.get("label") or ""
                    out.append(f"{who}:{lab}" if lab else str(who))
                else:
                    out.append(str(s))
            v = out
        elif dest == "taal" and v not in ("en", "nl"):
            sys.exit(f"Settings file {path}: \"{k}\" must be \"en\" or \"nl\", got {v!r}")
        elif dest in ("levend_grens", "media_max"):
            v = int(v)
        elif dest == "levenden_verbergen":
            v = bool(v)
        opts[dest] = v
    if bad:
        sys.exit(f"Settings file {path}: unknown key(s) {', '.join(bad)} (known: {', '.join(sorted(CONFIG_KEYS))})")
    opts.setdefault("uit", os.path.join(base, "data.json"))  # next to the settings file, not in whatever folder you're in
    return opts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gedcom", nargs="?", help="the GEDCOM (may come from the settings file instead)")
    ap.add_argument("uit", nargs="?", default=None, metavar="output", help="data.json to write (default data.json)")
    ap.add_argument("--config", "--instellingen", dest="config",
                    help="settings file with the GEDCOM, output, paths and options (keys in English or Dutch; "
                         "paths relative to its folder; command-line options win)")
    ap.add_argument("--csv", help="relation certainty CSV (optional)")
    ap.add_argument("--regions", "--regios", dest="regios", help="region table as JSON (optional)")
    ap.add_argument("--start", action="append", default=None, help="start person: GEDCOM id (@I1@) or name, optionally with :label")
    ap.add_argument("--lineage-start", "--stamlijn-start", dest="stamlijn_start", help="different start person for the Line view (id or name)")
    ap.add_argument("--title", "--titel", dest="titel")
    ap.add_argument("--family-name", "--familienaam", dest="familienaam")
    ap.add_argument("--lang", "--taal", dest="taal", choices=["en", "nl"], default="en", help="viewer language (default en)")
    ap.add_argument("--show-living", "--levenden-tonen", dest="levenden_tonen", action="store_true", help="(default; kept for old commands)")
    ap.add_argument("--hide-living", "--levenden-verbergen", dest="levenden_verbergen", action="store_true", help="leave out dates and places of living people")
    ap.add_argument("--zeitgeist", "--tijdgeest", dest="tijdgeest", help="life and times per place as JSON (optional, for the Story view)")
    ap.add_argument("--stories", "--verhalen", dest="verhalen", help="own stories per person as JSON (optional, for the Story view)")
    ap.add_argument("--updated", "--bijgewerkt", dest="bijgewerkt", help="'last updated' moment shown in the viewer's footer, "
                    "YYYY-MM-DD or YYYY-MM-DDTHH:MM (default: now; 'none' leaves it out)")
    ap.add_argument("--living-years", "--levend-grens", dest="levend_grens", type=int, default=100, help="years (default 100)")
    ap.add_argument("--coords", "--coordinaten", dest="coordinaten", help="coordinates per place as JSON, from geocode_places.py (optional, for the maps)")
    ap.add_argument("--media-dir", "--media-map", dest="media_map", help="copy local photos/documents into this folder (as media/<name>)")
    ap.add_argument("--media-max", type=int, default=2000,
                    help="shrink photos to at most this many pixels (longest side) if Pillow is available; 0 = don't")
    ap.add_argument("--media-base", "--media-basis", dest="media_basis", help="folder where relative file paths in the GEDCOM start "
                                         "(default: the GEDCOM's folder, then the folder above)")
    a = ap.parse_args()
    cfg = a.config
    if not cfg and not a.gedcom:
        cfg = find_config()
        if not cfg:
            ap.error(f"give a GEDCOM file, or --config, or put {' or '.join(CONFIG_NAMES)} in this folder")
    cfg_start = None
    if cfg:
        # with a settings file, one loose .json argument is the output, not the GEDCOM
        out_only = a.gedcom if a.gedcom and a.uit is None and a.gedcom.lower().endswith(".json") else None
        opts = load_config(cfg)
        cfg_start = opts.pop("start", None)
        ap.set_defaults(**opts)
        a = ap.parse_args()  # again, so the command line wins over the settings file
        if out_only:
            a.gedcom, a.uit = opts.get("gedcom"), out_only
        print(f"Settings: {cfg}")
        if not a.gedcom:
            sys.exit(f"Settings file {cfg}: no \"gedcom\" given")
    if a.start is None:
        a.start = cfg_start or []
    if a.uit is None:
        a.uit = "data.json"

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
        aka = aka_names(r, n, g, s)
        if aka: p["aka"] = aka
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
        # the same facts with what they were, so the map of a place can say why the person was there (not birth or death: the viewer has those)
        wf = [x for x in placed_facts(r, WOON_TAGS) if not (x[2] == "doop" and place_key(x[1]) == place_key(p.get("bplac")))]
        if p.get("by") and p.get("bplac"): pts.append((p["by"], p["bplac"]))
        if p.get("dy") and p.get("dplac"): pts.append((p["dy"], p["dplac"]))
        for c in subs(r, "FAMS"):
            fam = fams.get(c["v"])
            if fam:
                pts += dated_places(fam, ("MARR", "MARB", "MARL", "ENGA", "DIV", "RESI", "CENS", "EVEN"))
                h, w2 = sub(fam, "HUSB"), sub(fam, "WIFE")
                sp = [idx.get(o["v"]) for o in (h, w2) if o and idx.get(o["v"]) not in (None, i)]
                wf += [x + ([] if len(x) > 3 else [""]) + ([sp[0]] if sp and x[2] in ("huwelijk", "ondertrouw", "verloving", "scheiding") else [])
                       for x in placed_facts(fam, ("MARR", "MARB", "MARL", "ENGA", "DIV", "RESI", "CENS", "EVEN"))]
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
        # without duplicates, in GEDCOM order within a year and kind (a set here made the order differ per run)
        if wf: p["woon_feiten"] = sorted([list(x) for x in dict.fromkeys(tuple(x) for x in wf)], key=lambda x: (x[0], x[2]))

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
                # the note says *why* the status holds; "why"/"waarom" is an alias that wins over "note"
                people[ci].setdefault("c", {})[role] = [norm_status(col(row, "status", "zekerheid", "certainty")),
                                                        col(row, "bron", "source"),
                                                        col(row, "waarom", "why") or col(row, "opmerking", "opm", "note", "notes")]
                soort = (col(row, "soort", "relatie", "relation", "type", "kind") or "").strip().lower()
                soort = REL_TYPE.get(soort, soort)
                if soort and soort not in ("biologisch", "biological"):
                    people[ci]["c"][role].append(soort)
                n_ok += 1
        print(f"CSV: {n_ok} relations read, {n_bad} rows skipped (person not found or not a parent-child relation)")
        # every certain/probable/possible link needs a source and one plain sentence why (the viewer shows it as "Why certain:")
        weak = []
        for p in people:
            for role, c in (p.get("c") or {}).items():
                if c[0] not in ("zeker", "waarschijnlijk", "mogelijk"): continue
                miss = [w for w, bad in (("no source", not (c[1] or "").strip()),
                                         ("no reason" if not (c[2] or "").strip() else f"short reason ({len(c[2].strip())} chars)",
                                          len((c[2] or "").strip()) < WHY_MIN)) if bad]
                if miss:
                    par = people[p["f" if role == "f" else "m"]]["n"]
                    weak.append(f"{p['n']} → {par} ({c[0]}): {', '.join(miss)}")
        if weak:
            print(f"  warning: {len(weak)} certain/probable/possible link(s) without a source or with a reason under {WHY_MIN} characters"
                  f" (say in one sentence which record, place and year, who is named as parent; for probable/possible also what is missing):",
                  file=sys.stderr)
            for w in weak[:5]: print(f"    {w}", file=sys.stderr)
            if len(weak) > 5: print(f"    … and {len(weak) - 5} more", file=sys.stderr)

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
                for k in ("bdate", "bplac", "ddate", "dplac", "by", "dy", "r", "media", "beroep", "woon", "woon_feiten", "weg"):
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
                crd = val.get("kaarten") or val.get("cards")  # short version for Cards (blank line = new card)
                if crd: people[i]["verhaal_kaarten"] = crd
                plk = story_places(val.get("plekken") or val.get("places"))  # places the story points at (for its map)
                if plk: people[i]["verhaal_plekken"] = plk
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
        n_warn += sum(story_clipping_warnings(p) for p in people if p.get("verhaal"))
        n_cw = sum(story_card_warnings(p) for p in people if p.get("verhaal"))
        n_kv = sum(1 for p in people if p.get("verhaal_kaarten"))
        print(f"Stories: {n_vh} read, {n_kv} with cards" + (f", {n_warn} warning(s) about story images" if n_warn else "")
              + (f", {n_cw} warning(s) about cards" if n_cw else "") + (" (see above)" if n_warn or n_cw else ""))
        if n_vh: print("  Card budget per person (exact, with zeitgeist): open the viewer with #kaartbudget (or #cardbudget) at the end of the address")

    for p in people: p.pop("_media_orig", None)
    fam = a.familienaam or surn0[starts[0]["persoon"]] or ""
    out = {"versie": 2, "taal": a.taal}
    upd = a.bijgewerkt or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
    if upd.lower() not in ("none", "geen"):
        upd = upd.replace(" ", "T")
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M"):
            try: datetime.datetime.strptime(upd, fmt); break
            except ValueError: pass
        else: sys.exit(f"--updated: expected a date like 2026-11-22 or 2026-11-22T14:35, got {upd!r}")
        out["bijgewerkt"] = upd
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
        n_tw = 0
        for pl in tg.get("plaatsen", []):
            if pl.get("beelden"): pl["beelden"] = img_kinds(pl["beelden"])
            for L in pl.get("leven") or []:
                if isinstance(L, dict) and "cards" in L and "kaarten" not in L: L["kaarten"] = L.pop("cards")
                n_tw += zeitgeist_card_warnings(pl, L)
        for ev in [e for pl in tg.get("plaatsen", []) for e in pl.get("gebeurtenissen") or []] + list((tg.get("algemeen") or {}).get("gebeurtenissen") or []):
            if isinstance(ev, dict) and "weight" in ev and "gewicht" not in ev: ev["gewicht"] = ev.pop("weight")  # importance in Cards
            if isinstance(ev, dict) and "gewicht" in ev and not isinstance(ev["gewicht"], (int, float)):
                print(f"  warning, zeitgeist event {ev.get('jaar', '?')}: \"gewicht\": {ev['gewicht']} is not a number", file=sys.stderr)
        n_tk = sum(1 for pl in tg.get("plaatsen", []) for L in pl.get("leven") or [] if isinstance(L, dict) and L.get("kaarten"))
        print(f"Zeitgeist: {len(tg.get('plaatsen', []))} place(s), "
              f"{sum(len(x.get('beelden', [])) for x in tg.get('plaatsen', []))} images, {n_tk} life block(s) with cards"
              + (f", {n_tw} warning(s) about cards (see above)" if n_tw else ""))
    if a.coordinaten:
        with open(a.coordinaten, encoding="utf-8") as fh:
            out["coordinaten"] = coords_for(people, json.load(fh))
        if out["coordinaten"]:
            lk = base_map(people, out["coordinaten"])
            if lk: out["landkaart"] = lk
            n_mw = sum(story_map_warnings(p, out["coordinaten"]) for p in people if p.get("verhaal"))
            if n_mw: print(f"  {n_mw} stor{'y' if n_mw == 1 else 'ies'} with map places the text doesn't name: the viewer adds a short sentence"
                           " before those maps; name the place in the story (or give it \"alinea\" in \"plekken\") to place the map yourself")
    out["personen"] = people
    with open(a.uit, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"{a.uit}: {len(people)} people, {len(fams)} families, {n_lev} living"
          f"{' (details hidden)' if n_lev and a.levenden_verbergen else ''}, "
          f"start person: {people[starts[0]['persoon']]['n']}, regions: {', '.join(sorted(used)) or 'none'}")

if __name__ == "__main__":
    main()
