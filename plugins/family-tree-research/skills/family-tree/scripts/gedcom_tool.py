#!/usr/bin/env python3
"""gedcom_tool.py — a small GEDCOM toolkit for the family-tree plugin.

Subcommands (Dutch names in brackets also work):
  new    (nieuw)       intake.json -> new GEDCOM (onboarding without an existing tree)
  add    (toevoegen)   GEDCOM + additions.json -> GEDCOM with new ancestors (+ optional CSV rows)
  check  (controleer)  GEDCOM -> Markdown report (counts, generations, gaps, odd dates)
  media                GEDCOM + media.csv -> GEDCOM with photos/documents per person (OBJE/FILE)
  rebuild (opbouwen)   original GEDCOM + rounds folder -> working GEDCOM, relations CSV, rejected register

Examples:
  python3 gedcom_tool.py new data/intake.json source/tree.ged
  python3 gedcom_tool.py add source/tree.ged data/additions.json source/tree.ged --csv data/relations.csv
  python3 gedcom_tool.py check source/tree.ged reports/check.md --start @I1@ --lang en
  python3 gedcom_tool.py media source/tree.ged data/media.csv source/tree.ged
  python3 gedcom_tool.py rebuild source/original.ged rounds source/tree.ged --csv data/relations.csv \
      --rejected reports/rejected.md --media data/media.csv

JSON keys may be English or Dutch (see references/gedcom-tool.md).
Standard library only; Python 3.8+.
"""
import argparse, csv, datetime, json, os, re, sys


_LIVE = []


def live(kind, **fields):
    """Tell this tree's Workshop (live.py serve) what happens (`_where` = a file of the tree). Does nothing without one."""
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

MONTHS = {
    "jan": "JAN", "januari": "JAN", "january": "JAN", "feb": "FEB", "februari": "FEB", "february": "FEB",
    "mrt": "MAR", "maart": "MAR", "mar": "MAR", "march": "MAR", "apr": "APR", "april": "APR",
    "mei": "MAY", "may": "MAY", "jun": "JUN", "juni": "JUN", "june": "JUN", "jul": "JUL", "juli": "JUL",
    "july": "JUL", "aug": "AUG", "augustus": "AUG", "august": "AUG", "sep": "SEP", "sept": "SEP",
    "september": "SEP", "okt": "OCT", "oct": "OCT", "oktober": "OCT", "october": "OCT", "nov": "NOV",
    "november": "NOV", "dec": "DEC", "december": "DEC",
}
MNUM = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def g(d, *keys, default=None):
    """First present key (English or Dutch alias)."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def gedcom_date(s):
    """Convert a loose date ('12-03-1901', 'ca. 1850', 'about 1850', 'March 1931', 'before 1900') to GEDCOM."""
    if not s:
        return ""
    t = str(s).strip().lower()
    pre = ""
    for words, code in ((("ca.", "ca ", "c. ", "c.", "circa", "ongeveer", "omstreeks", "about", "abt", "approx", "~"), "ABT "),
                        (("voor ", "vóór ", "before ", "bef "), "BEF "),
                        (("na ", "after ", "aft "), "AFT ")):
        for w in words:
            if t.startswith(w):
                pre, t = code, t[len(w):].strip()
                break
        if pre:
            break
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= mo <= 12:
            return f"{pre}{d} {MNUM[mo-1]} {y}"
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return f"{pre}{int(m.group(3))} {MNUM[int(m.group(2))-1]} {m.group(1)}"
    m = re.fullmatch(r"(\d{1,2})?\s*([a-zé]+)\.?\s+(\d{4})", t)
    if m and m.group(2) in MONTHS:
        day = f"{int(m.group(1))} " if m.group(1) else ""
        return f"{pre}{day}{MONTHS[m.group(2)]} {m.group(3)}"
    m = re.fullmatch(r"([a-zé]+)\.?\s+(\d{1,2}),?\s+(\d{4})", t)  # March 12, 1931
    if m and m.group(1) in MONTHS:
        return f"{pre}{int(m.group(2))} {MONTHS[m.group(1)]} {m.group(3)}"
    m = re.fullmatch(r"(\d{4})", t)
    if m:
        return f"{pre}{m.group(1)}"
    return f"{pre}{s}".strip() if pre else str(s).strip()


def year(s):
    m = re.search(r"(\d{4})", s or "")
    return int(m.group(1)) if m else None


def event(tag, ev, source=None):
    out = []
    if not ev:
        return out
    if isinstance(ev, str):
        ev = {"date": ev}
    d = gedcom_date(g(ev, "date", "datum"))
    p = (g(ev, "place", "plaats", default="") or "").strip()
    if not d and not p:
        return out
    out.append(f"1 {tag}")
    if d:
        out.append(f"2 DATE {d}")
    if p:
        out.append(f"2 PLAC {p}")
    src = g(ev, "source", "bron") or source
    if src:
        out.append(f"2 NOTE Source: {src}")
    return out


def person_lines(xref, p, famc=None, fams=()):
    gn = (g(p, "given_names", "given", "voornamen", default="") or "").strip()
    sn = (g(p, "surname", "achternaam", default="") or "").strip()
    r = [f"0 {xref} INDI", f"1 NAME {gn} /{sn}/".replace("  ", " ")]
    if gn:
        r.append(f"2 GIVN {gn}")
    if sn:
        r.append(f"2 SURN {sn}")
    sex = (g(p, "sex", "geslacht", default="") or "").upper()[:1]
    if sex in ("M", "F", "V", "W"):
        r.append(f"1 SEX {'M' if sex == 'M' else 'F'}")
    r += event("BIRT", g(p, "birth", "born", "geboren"))
    r += event("BAPM", g(p, "baptism", "gedoopt"))
    r += event("DEAT", g(p, "death", "died", "overleden"))
    r += event("BURI", g(p, "burial", "begraven"))
    occ = g(p, "occupation", "beroep")
    if occ:
        r.append(f"1 OCCU {occ}")
    src = g(p, "source", "sources", "bron")
    for b in ([src] if isinstance(src, str) else src or []):
        r.append(f"1 NOTE Source: {b}")
    notes = g(p, "notes", "notities")
    if notes:
        r.append(f"1 NOTE {notes}")
    if famc:
        r.append(f"1 FAMC {famc}")
    for f in fams:
        r.append(f"1 FAMS {f}")
    return r


def header(source="Family-tree plugin"):
    today = datetime.date.today()
    return ["0 HEAD", f"1 SOUR {source}", "1 GEDC", "2 VERS 5.5.1", "2 FORM LINEAGE-LINKED",
            "1 CHAR UTF-8", f"1 DATE {today.day} {MNUM[today.month-1]} {today.year}"]


# ---------------------------------------------------------------- new
def cmd_new(a):
    inp = json.load(open(a.intake, encoding="utf-8"))
    people = g(inp, "people", "personen", default=[])
    ids = {p["id"]: f"@I{i+1}@" for i, p in enumerate(people)}
    fams, famc, fams_of = {}, {}, {}

    def fam_for(f, m):
        k = (f or "", m or "")
        if k not in fams:
            fams[k] = {"x": f"@F{len(fams)+1}@", "children": [], "marr": None}
            for o in (f, m):
                if o:
                    fams_of.setdefault(o, []).append(fams[k]["x"])
        return fams[k]

    for p in people:
        f, m = g(p, "father", "vader"), g(p, "mother", "moeder")
        if f or m:
            fam = fam_for(f, m)
            fam["children"].append(p["id"])
            famc[p["id"]] = fam["x"]
    for h in g(inp, "marriages", "huwelijken", default=[]):
        fam_for(g(h, "husband", "man"), g(h, "wife", "vrouw"))["marr"] = h

    lines = header()
    for p in people:
        lines += person_lines(ids[p["id"]], p, famc.get(p["id"]), fams_of.get(p["id"], []))
    for (f, m), fam in fams.items():
        lines.append(f"0 {fam['x']} FAM")
        if f:
            lines.append(f"1 HUSB {ids[f]}")
        if m:
            lines.append(f"1 WIFE {ids[m]}")
        if fam["marr"]:
            lines += event("MARR", fam["marr"])
        for c in fam["children"]:
            lines.append(f"1 CHIL {ids[c]}")
    lines.append("0 TRLR")
    write(a.output, lines)
    print(f"{len(people)} people, {len(fams)} families -> {a.output}")
    print("id mapping (intake -> GEDCOM):", json.dumps({p["id"]: ids[p["id"]] for p in people}, ensure_ascii=False))


# ---------------------------------------------------------------- reading
def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return [l.rstrip("\r\n") for l in fh]


def write(path, lines):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, path)


def records(lines):
    """-> list of [xref, tag, [lines]] per level-0 record."""
    recs = []
    for l in lines:
        if l.startswith("0 "):
            m = re.match(r"0 (@[^@]+@) (\w+)", l)
            recs.append([m.group(1) if m else None, m.group(2) if m else l[2:].split(" ")[0], [l]])
        elif recs:
            recs[-1][2].append(l)
    return recs


def values(rec, tag, level=1):
    return [(l.split(" ", 2) + [""])[2].strip() for l in rec[2]
            if l.startswith(f"{level} {tag} ") or l == f"{level} {tag}"]


def tree(lines):
    recs = records(lines)
    indi = {r[0]: r for r in recs if r[1] == "INDI"}
    fam = {r[0]: r for r in recs if r[1] == "FAM"}
    return recs, indi, fam


def name(rec):
    n = values(rec, "NAME")
    return re.sub(r"\s+", " ", n[0].replace("/", "")).strip() if n else "(no name)"


def ev(rec, tags):
    """First date and place from the given events."""
    date = place = ""
    for tag in tags:
        inside = False
        for l in rec[2]:
            if l.startswith("1 "):
                inside = l.split(" ")[1] == tag
            elif inside and l.startswith("2 DATE ") and not date:
                date = l[7:].strip()
            elif inside and l.startswith("2 PLAC ") and not place:
                place = l[7:].strip()
    return date, place


def parents(xref, indi, fam):
    for f in values(indi[xref], "FAMC"):
        if f in fam:
            h = (values(fam[f], "HUSB") or [None])[0]
            w = (values(fam[f], "WIFE") or [None])[0]
            return f, (h if h in indi else None), (w if w in indi else None)
    return None, None, None


# ---------------------------------------------------------------- add
STATUS_DEFAULT = {"en": "certain", "nl": "zeker"}


def cmd_add(a):
    lines = read(a.gedcom)
    recs, indi, fam = tree(lines)
    add = json.load(open(a.additions, encoding="utf-8"))
    used, ref, new_indi = set(), {}, {}

    def free(prefix):
        n = 1
        while f"@{prefix}{n}@" in indi or f"@{prefix}{n}@" in fam or f"@{prefix}{n}@" in used:
            n += 1
        used.add(f"@{prefix}{n}@")
        return f"@{prefix}{n}@"

    for p in g(add, "new", "nieuw", default=[]):
        x = free("IN")
        ref[p["ref"]] = x
        new_indi[x] = {"p": p, "famc": None, "fams": []}

    def resolve(r):
        if r in ref:
            return ref[r]
        r2 = r if r.startswith("@") else f"@{r}@"
        if r2 in indi:
            return r2
        sys.exit(f"Unknown reference: {r}")

    csv_rows, new_fams, extra = [], [], {}
    for o in g(add, "parents", "ouders", default=[]):
        child = resolve(g(o, "child", "kind"))
        fa = resolve(g(o, "father", "vader")) if g(o, "father", "vader") else None
        mo = resolve(g(o, "mother", "moeder")) if g(o, "mother", "moeder") else None
        marr = g(o, "marriage", "huwelijk")
        src = g(o, "source", "bron")
        f = None
        if child in indi:
            f, cf, cm = parents(child, indi, fam)
            if f and ((fa and cf and cf != fa) or (mo and cm and cm != mo)):
                sys.exit(f"{child} already has different parents in {f}; resolve this first (see the questions report).")
        if f:
            for role, x in (("HUSB", fa), ("WIFE", mo)):
                if x and not values(fam[f], role):
                    extra.setdefault(f, []).append(f"1 {role} {x}")
                    link_fams(x, f, new_indi, extra)
            if marr:
                extra.setdefault(f, []).extend(event("MARR", marr, src))
        else:
            f = free("FN")
            r = [f"0 {f} FAM"]
            if fa:
                r.append(f"1 HUSB {fa}")
            if mo:
                r.append(f"1 WIFE {mo}")
            r += event("MARR", marr, src)
            r.append(f"1 CHIL {child}")
            new_fams.append(r)
            for x in (fa, mo):
                if x:
                    link_fams(x, f, new_indi, extra)
            if child in new_indi:
                new_indi[child]["famc"] = f
            else:
                extra.setdefault(child, []).append(f"1 FAMC {f}")
        for role, nl, x in (("father", "vader", fa), ("mother", "moeder", mo)):
            if x:
                csv_rows.append([child, x,
                                 g(o, f"status_{role}", f"status_{nl}", "status", default=STATUS_DEFAULT[a.lang]),
                                 g(o, f"source_{role}", f"bron_{nl}", "source", "bron", default=""),
                                 g(o, f"why_{role}", f"waarom_{nl}", "why", "waarom", "note", "opmerking", default=""),
                                 g(o, f"type_{role}", "type", "soort", default="")])

    out = []
    for r in recs:
        if r[1] == "TRLR":
            continue
        out += r[2] + extra.get(r[0], [])
    for x, d in new_indi.items():
        out += person_lines(x, d["p"], d["famc"], d["fams"])
    for r in new_fams:
        out += r
    out.append("0 TRLR")
    write(a.output, out)

    if a.csv and csv_rows:
        is_new = not os.path.exists(a.csv)
        with open(a.csv, "a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            if is_new:
                w.writerow(["child_id", "parent_id", "status", "source", "note", "type"] if a.lang == "en"
                           else ["kind_id", "ouder_id", "status", "bron", "opmerking", "soort"])
            w.writerows(csv_rows)
    print(f"{len(new_indi)} new people, {len(new_fams)} new families -> {a.output}")
    print("new ids:", json.dumps(ref, ensure_ascii=False))
    if a.csv:
        print(f"{len(csv_rows)} relations appended to {a.csv}")


def link_fams(x, f, new_indi, extra):
    if x in new_indi:
        if f not in new_indi[x]["fams"]:
            new_indi[x]["fams"].append(f)
    else:
        extra.setdefault(x, []).append(f"1 FAMS {f}")


# ---------------------------------------------------------------- check
T = {
    "en": {"title": "Family tree check", "file": "File", "people": "People", "families": "families",
           "sourced": "With a source (SOUR/NOTE Source)", "start": "Start person", "none": "No people found.",
           "per_gen": "Ancestors per generation", "cols": "| generation | expected | found | missing |",
           "total": "Unique ancestors: **{n}**, oldest generation: {g}.", "gaps": "Gaps (missing parents up to generation {g})",
           "gap": "- gen. {g}: {role} of **{name}** ({x}; {d} {p})", "father": "father", "mother": "mother",
           "nogaps": "- None.", "odd": "Worth a look", "noodd": "- Nothing unusual found.",
           "deathbefore": "- {n} ({x}): died ({d}) before born ({b})", "old": "- {n} ({x}): lived to {a}?",
           "parentage": "- {n} ({x}, {b}): {role} was {a}", "afterdeath": "- {n} ({x}, {b}): born after death of {role} ({d})",
           "dup": "- Possible duplicate: {n} ({y}): {xs}",
           "done": "Report -> {f} ({p} people, {a} ancestors, {g} gaps, {o} worth a look)"},
    "nl": {"title": "Controle stamboom", "file": "Bestand", "people": "Personen", "families": "gezinnen",
           "sourced": "Met bronvermelding (SOUR/NOTE Bron)", "start": "Startpersoon", "none": "Geen personen gevonden.",
           "per_gen": "Voorouders per generatie", "cols": "| generatie | verwacht | gevonden | ontbreekt |",
           "total": "Totaal unieke voorouders: **{n}**, oudste generatie: {g}.", "gaps": "Gaten (ontbrekende ouders t/m generatie {g})",
           "gap": "- gen. {g}: {role} van **{name}** ({x}; {d} {p})", "father": "vader", "mother": "moeder",
           "nogaps": "- Geen.", "odd": "Opvallend", "noodd": "- Niets opvallends gevonden.",
           "deathbefore": "- {n} ({x}): overleden ({d}) vóór geboren ({b})", "old": "- {n} ({x}): {a} jaar oud geworden?",
           "parentage": "- {n} ({x}, {b}): {role} was {a} jaar", "afterdeath": "- {n} ({x}, {b}): geboren na overlijden {role} ({d})",
           "dup": "- Mogelijk dubbel: {n} ({y}): {xs}",
           "done": "Rapport -> {f} ({p} personen, {a} voorouders, {g} gaten, {o} opvallend)"},
}


def cmd_check(a):
    t = T[a.lang]
    lines = read(a.gedcom)
    recs, indi, fam = tree(lines)
    start = a.start
    if start and not start.startswith("@"):
        start = f"@{start}@"
    if not start or start not in indi:
        def count(x, seen=None):
            seen = seen if seen is not None else set()
            _, f, m = parents(x, indi, fam)
            n = 0
            for o in (f, m):
                if o and o not in seen:
                    seen.add(o)
                    n += 1 + count(o, seen)
            return n
        start = max(indi, key=lambda x: count(x)) if indi else None

    def has_source(r):
        return any(l.startswith(("1 SOUR", "2 SOUR", "1 NOTE Bron", "2 NOTE Bron", "1 NOTE Source", "2 NOTE Source")) for l in r[2])

    out = [f"# {t['title']}", "", f"{t['file']}: `{os.path.basename(a.gedcom)}` · {datetime.date.today():%Y-%m-%d}", "",
           f"- {t['people']}: **{len(indi)}**, {t['families']}: **{len(fam)}**",
           f"- {t['sourced']}: {sum(1 for r in indi.values() if has_source(r))}"]
    if not start:
        out.append("\n" + t["none"])
        write(a.output, out)
        return
    out += [f"- {t['start']}: **{name(indi[start])}** ({start})", "", f"## {t['per_gen']}", "",
            t["cols"], "|---|---|---|---|"]
    gen, layer, gaps, seen = 1, [start], [], {start: 1}
    while layer and gen < 30:
        nxt = []
        for x in layer:
            _, f, m = parents(x, indi, fam)
            for role, o in (("father", f), ("mother", m)):
                if o:
                    if o not in seen:
                        seen[o] = gen + 1
                    nxt.append(o)
                elif gen <= a.gaps_to:
                    gaps.append((gen + 1, role, x))
        if not nxt:
            break
        gen += 1
        uniq = len(set(nxt))
        out.append(f"| {gen} | {2**(gen-1)} | {uniq} | {2**(gen-1)-uniq} |")
        layer = list(dict.fromkeys(nxt))
    out += ["", t["total"].format(n=len(seen) - 1, g=gen), "", f"## {t['gaps'].format(g=a.gaps_to + 1)}", ""]
    for gg, role, x in gaps[:200]:
        d, p = ev(indi[x], ("BIRT", "BAPM", "CHR"))
        out.append(t["gap"].format(g=gg, role=t[role], name=name(indi[x]), x=x, d=d or "?", p=p))
    if not gaps:
        out.append(t["nogaps"])

    out += ["", f"## {t['odd']}", ""]
    odd, warns = [], []

    def flag(x, line):
        odd.append(line)
        warns.append((x, line))
    for x, r in indi.items():
        by = year(ev(r, ("BIRT", "BAPM", "CHR"))[0])
        dy = year(ev(r, ("DEAT", "BURI", "CREM"))[0])
        if by and dy and dy < by:
            flag(x, t["deathbefore"].format(n=name(r), x=x, d=dy, b=by))
        if by and dy and dy - by > 105:
            flag(x, t["old"].format(n=name(r), x=x, a=dy - by))
        _, f, m = parents(x, indi, fam)
        for role, o, lo, hi in (("father", f, 16, 75), ("mother", m, 14, 50)):
            if o and by:
                oby = year(ev(indi[o], ("BIRT", "BAPM", "CHR"))[0])
                ody = year(ev(indi[o], ("DEAT", "BURI", "CREM"))[0])
                if oby and not (lo <= by - oby <= hi):
                    flag(x, t["parentage"].format(n=name(r), x=x, b=by, role=t[role], a=by - oby))
                if ody and by > ody + (1 if role == "father" else 0):
                    flag(x, t["afterdeath"].format(n=name(r), x=x, b=by, role=t[role], d=ody))
    names = {}
    for x, r in indi.items():
        k = (name(r).lower(), year(ev(r, ("BIRT", "BAPM", "CHR"))[0]))
        if k[1]:
            names.setdefault(k, []).append(x)
    for k, xs in names.items():
        if len(xs) > 1:
            odd.append(t["dup"].format(n=k[0], y=k[1], xs=", ".join(xs)))
    out += odd[:200] or [t["noodd"]]
    write(a.output, out)
    print(t["done"].format(f=a.output, p=len(indi), a=len(seen) - 1, g=len(gaps), o=len(odd)))
    live("check", _where=a.gedcom, people=len(indi), ancestors=len(seen) - 1, gaps=len(gaps), odd=len(odd), start=start.strip("@"))
    for x, line in warns[:40]:
        live("warn", _where=a.gedcom, person=x.strip("@"), text=re.sub(r"@[^@\s]+@,?\s*", "", re.sub(r"[*`_]", "", line)).replace("()", "").lstrip("- ").strip())


# ---------------------------------------------------------------- media
MEDIA_TYPE = {"foto": "photo", "photo": "photo", "scan": "document", "akte": "document", "certificate": "document",
              "record": "document", "document": "document"}


def cmd_media(a):
    """media.csv columns: person (GEDCOM id or name with optional (year)), file, title, type (photo/scan/document).
    Dutch column names (persoon, bestand, titel, soort) also work. Paths are relative to the tree folder
    (e.g. scans/1830 death.jpg or photos/grandma.jpg). Existing links (same FILE on the same person) are not duplicated."""
    lines = read(a.gedcom)
    recs, indi, fam = tree(lines)
    by_name = {}
    for x, r in indi.items():
        by_name.setdefault(re.sub(r"\s+", " ", name(r).lower()), []).append(x)

    def find(v):
        v = (v or "").strip()
        k = v if v.startswith("@") else "@" + v.strip("@") + "@"
        if k in indi:
            return k
        m = re.match(r"^(.*?)\s*\((\d{3,4})\)\s*$", v)
        nm, yr = (m.group(1), m.group(2)) if m else (v, None)
        c = by_name.get(re.sub(r"\s+", " ", nm.lower()), [])
        if yr:
            c = [x for x in c if yr in (ev(indi[x], ("BIRT", "BAPM", "CHR"))[0] or "")] or c
        return c[0] if len(c) == 1 else None

    with open(a.csv, newline="", encoding="utf-8-sig") as fh:
        head = fh.readline(); fh.seek(0)
        delim = max(",;\t", key=head.count)
        rows = list(csv.DictReader(fh, delimiter=delim))
    added, marked, failed, extra = 0, 0, [], {}
    for r in rows:
        row = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
        who = row.get("person") or row.get("persoon") or row.get("id")
        x = find(who)
        f = row.get("file") or row.get("bestand")
        if not x or not f:
            failed.append(f"{who} / {f}"); continue
        prim = (row.get("portrait") or row.get("portret") or "").lower() in ("y", "yes", "ja", "j", "1", "x", "true", "portrait", "portret")
        rec = indi[x][2]
        have = [l[7:].strip() for l in rec if l.startswith("2 FILE ")]
        if f in have:
            if prim:  # already linked: only mark it as the portrait (2 _PRIM Y under its OBJE)
                k = next(i for i, l in enumerate(rec) if l.startswith("2 FILE ") and l[7:].strip() == f)
                j = max(i for i in range(k) if rec[i].startswith("1 OBJE"))
                end = next((i for i in range(k + 1, len(rec)) if rec[i][:1] in "01"), len(rec))
                if not any(rec[i].startswith("2 _PRIM") for i in range(j, end)):
                    rec.insert(j + 1, "2 _PRIM Y"); marked += 1
            continue
        if f in [e[0] for e in extra.get(x, [])]:
            continue
        extra.setdefault(x, []).append((f, row.get("title") or row.get("titel") or "", row.get("type") or row.get("soort") or "", prim))
    for x, items in extra.items():
        rec = indi[x][2]
        for f, title, kind, prim in items:
            ext = os.path.splitext(f)[1].lstrip(".").lower() or "jpg"
            rec += ["1 OBJE"] + (["2 _PRIM Y"] if prim else []) + [f"2 FILE {f}", f"3 FORM {ext}"]
            typ = MEDIA_TYPE.get(kind.lower())
            if typ:
                rec.append(f"4 TYPE {typ}")
            if title:
                rec.append(f"2 TITL {title}")
            added += 1
    write(a.output, [l for r in recs for l in r[2]])
    print(f"media: {added} links added for {len(extra)} people" + (f", {marked} existing photo(s) marked as portrait" if marked else "") + f" -> {a.output}")
    for f in failed:
        print("  not linked (person not found/not unique, or no file):", f)


# ---------------------------------------------------------------- rebuild
# The original GEDCOM is never changed. Every research round is one JSON file in a rounds folder; `rebuild`
# applies all rounds to the original, in order, and writes the working version, the relations CSV and the
# register of rejected links. Same input -> byte-for-byte the same output.

class RoundError(Exception):
    pass


RB = {
    "en": {"not_checked": "not checked", "certain": "certain",
           "was": "Earlier value: {v} (changed in round {n})",
           "dropped_link": "Removed as parent in round {n}: {p} ({x}). Reason: {r}",
           "merged": "Merged in round {n} with {x} ({p}){r}",
           "merged_other": "Other value from the merged record {x}: {v}",
           "dropped_event": "Removed in round {n}: {v}. Reason: {r}",
           "built": "Rebuilt by Family Tree Research from {o} + {k} round(s), last: {last}",
           "round_src": "Research round {n}", "back": " — added again in round {n}: {w}",
           "rej_title": "Rejected links", "rej_intro": "Made by `gedcom_tool.py rebuild` from the rounds: don't edit by hand. "
           "**Read this before adding a parent.** Something listed here only goes back in with a new source that refutes the reason.",
           "rej_cols": "| Child | Rejected parent | Where it came from | Why | Source | Round |",
           "rej_people": "Removed people", "rej_pcols": "| Person | Where it came from | Why | Source | Round |",
           "rej_events": "Removed events", "rej_ecols": "| Person | Event | Why | Source | Round |",
           "none": "- None yet."},
    "nl": {"not_checked": "niet gecheckt", "certain": "zeker",
           "was": "Eerdere waarde: {v} (gewijzigd in ronde {n})",
           "dropped_link": "In ronde {n} weggehaald als ouder: {p} ({x}). Reden: {r}",
           "merged": "In ronde {n} samengevoegd met {x} ({p}){r}",
           "merged_other": "Andere waarde uit het samengevoegde record {x}: {v}",
           "dropped_event": "Weggehaald in ronde {n}: {v}. Reden: {r}",
           "built": "Opnieuw opgebouwd door Family Tree Research uit {o} + {k} ronde(s), laatste: {last}",
           "round_src": "Onderzoeksronde {n}", "back": " — weer toegevoegd in ronde {n}: {w}",
           "rej_title": "Afgewezen koppelingen", "rej_intro": "Gemaakt door `gedcom_tool.py rebuild` uit de rondes: niet met de hand bewerken. "
           "**Lees dit vóór je een ouder toevoegt.** Wat hier staat gaat er alleen weer in met een nieuwe bron die de reden weerlegt.",
           "rej_cols": "| Kind | Afgewezen ouder | Waar het vandaan kwam | Waarom | Bron | Ronde |",
           "rej_people": "Weggehaalde personen", "rej_pcols": "| Persoon | Waar het vandaan kwam | Waarom | Bron | Ronde |",
           "rej_events": "Weggehaalde gebeurtenissen", "rej_ecols": "| Persoon | Gebeurtenis | Waarom | Bron | Ronde |",
           "none": "- Nog geen."},
}

def live_step(op, s, msg):
    """One round step, short, for the Workshop (live.py): what it is, about whom, and the words that matter."""
    out = {"op": op}
    pid = g(s, "person", "persoon", "child", "kind", "keep", "houd")
    if pid:
        out["person"] = str(pid).strip("@")
    m = re.search(r" for (.+?)(?: \(\d{4}\))?$", str(msg))
    if m:
        out["name"] = m.group(1)
    if op == "note":
        out["text"] = str(g(s, "text", "tekst", "note", "notitie", default=""))[:320]
    elif op in ("event", "drop_event"):
        for k, keys in (("type", ("type", "soort")), ("date", ("date", "datum")), ("place", ("place", "plaats")),
                        ("text", ("note", "notitie", "reason", "reden", "description", "beschrijving"))):
            v = g(s, *keys)
            if v:
                out[k] = str(v)[:200]
    elif op == "aka":
        out["text"] = str(g(s, "name", "naam", default=""))[:80]
    elif op == "places":
        out["n"] = len(g(s, "map", "kaart", "plaatsen", default={}) or {})
    return out


# step names (English, Dutch) -> canonical
OPS = {"add": "add", "new": "add", "nieuw": "add", "person": "add", "persoon": "add",
       "parents": "parents", "ouders": "parents",
       "status": "status", "zekerheid": "status",
       "event": "event", "gebeurtenis": "event",
       "occupation": "occupation", "beroep": "occupation",
       "note": "note", "notitie": "note",
       "aka": "aka", "roepnaam": "aka", "bijnaam": "aka", "alias": "aka",
       "name": "name", "naam": "name",
       "drop_link": "drop_link", "koppeling_weg": "drop_link",
       "merge": "merge", "samenvoegen": "merge",
       "drop_event": "drop_event", "gebeurtenis_weg": "drop_event",
       "drop_person": "drop_person", "persoon_weg": "drop_person",
       "places": "places", "plaatsen": "places",
       "lines": "lines", "regels": "lines"}

EVENT_TAGS = {
    "birth": "BIRT", "born": "BIRT", "geboorte": "BIRT", "geboren": "BIRT",
    "baptism": "BAPM", "doop": "BAPM", "gedoopt": "BAPM", "christening": "CHR",
    "death": "DEAT", "died": "DEAT", "overlijden": "DEAT", "overleden": "DEAT",
    "burial": "BURI", "begrafenis": "BURI", "begraven": "BURI", "cremation": "CREM", "crematie": "CREM",
    "marriage": "MARR", "huwelijk": "MARR", "banns": "MARB", "ondertrouw": "MARB",
    "divorce": "DIV", "scheiding": "DIV",
    "residence": "RESI", "woonplaats": "RESI", "woont": "RESI", "wonen": "RESI",
    "emigration": "EMIG", "emigratie": "EMIG", "immigration": "IMMI", "immigratie": "IMMI",
    "census": "CENS", "volkstelling": "CENS", "confirmation": "CONF", "belijdenis": "CONF",
    "probate": "PROB", "will": "WILL", "testament": "WILL", "graduation": "GRAD", "naturalisation": "NATU",
    "naturalization": "NATU", "naturalisatie": "NATU",
}
GEDCOM_EVENTS = set(EVENT_TAGS.values()) | {"ADOP", "BARM", "BASM", "BLES", "CHRA", "FCOM", "ORDN", "RETI",
                                            "ENGA", "MARC", "MARL", "MARS", "ANUL", "DIVF", "EVEN", "FACT"}
SINGLE = {"BIRT", "BAPM", "CHR", "DEAT", "BURI", "CREM", "MARR", "DIV"}
FAM_EVENTS = {"MARR", "MARB", "DIV", "ENGA", "MARC", "MARL", "MARS", "ANUL", "DIVF"}
SKIP_ON_MERGE = {"SEX", "CHAN", "RIN", "_UID", "RFN", "AFN", "FAMS", "FAMC", "NAME"}
PEDI = {"adopted": "adopted", "adoptie": "adopted", "foster": "foster", "pleeg": "foster"}
URL_RE = re.compile(r"https?://\S+")


def lvl(l):
    try:
        return int(l.split(" ", 1)[0])
    except ValueError:
        return 99


def tag_of(l):
    p = l.split(" ")
    return p[1] if len(p) > 1 else ""


def blocks(r, tag=None):
    """(start, end) of the level-1 blocks in a record's lines, optionally only those with this tag."""
    out = []
    for k in range(1, len(r)):
        if lvl(r[k]) == 1 and (tag is None or tag_of(r[k]) == tag):
            e = k + 1
            while e < len(r) and lvl(r[e]) > 1:
                e += 1
            out.append((k, e))
    return out


def sub_value(blk, tag, level=2):
    for l in blk[1:]:
        if lvl(l) == level and tag_of(l) == tag:
            return l.split(" ", 2)[2].strip() if len(l.split(" ", 2)) > 2 else ""
    return ""


def text_lines(level, tag, text):
    """A text value as one GEDCOM line plus CONT lines for line breaks."""
    parts = str(text).split("\n")
    return [f"{level} {tag} {parts[0]}".rstrip()] + [f"{level+1} CONT {p}".rstrip() for p in parts[1:]]


def norm_name(s):
    return re.sub(r"\s+", " ", (s or "").replace("/", " ")).strip().lower()


def norm_place(s):
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


class Rebuild:
    def __init__(self, lines, lang):
        self.lang, self.t = lang, RB[lang]
        recs = records(lines)
        self.trailer = [r for r in recs if r[1] == "TRLR"]
        self.recs = [r for r in recs if r[1] != "TRLR"]
        self.idx = {r[0]: r for r in self.recs if r[0]}
        self.ever = set(self.idx)  # every id that ever existed, so a fixed id is never reused
        self.alias = {}            # dropped/merged id -> kept id
        self.rel = {}              # (child, parent) -> [status, source, note, type]
        self.rejected, self.gone_people, self.gone_events = [], [], []
        self.places = {}
        self.n = 0                 # current round number
        self.refs = {}             # ref -> id within the current round
        self.round_src = None
        self.n_fam = 0
        self.log = []

    # --- records
    def add_rec(self, x, tag, body):
        if x in self.idx:
            raise RoundError(f"id {x} already exists")
        r = [x, tag, [f"0 {x} {tag}"] + body]
        self.recs.append(r)
        self.idx[x] = r
        self.ever.add(x)
        return r[2]

    def delete(self, x):
        r = self.idx.pop(x)
        self.recs.remove(r)

    def L(self, x):
        return self.idx[x][2]

    def kind(self, x):
        return self.idx[x][1] if x in self.idx else None

    def name(self, x):
        return name(self.idx[x]) if x in self.idx else x

    def label(self, x):
        d = ev(self.idx[x], ("BIRT", "BAPM", "CHR"))[0] if x in self.idx else ""
        y = year(d)
        return f"{self.name(x)}" + (f" ({y})" if y else "")

    def resolve(self, v, what="person", required=True):
        if v in (None, ""):
            if required:
                raise RoundError(f"missing {what}")
            return None
        v = str(v).strip()
        x = self.refs.get(v) or (v if v.startswith("@") else f"@{v.strip('@')}@")
        while x in self.alias:
            x = self.alias[x]
        want = "FAM" if what == "family" else "INDI"
        if self.kind(x) != want:
            raise RoundError(f"unknown {what} '{v}'")
        return x

    def refs_in_fam(self, f, tag):
        return [l.split(" ", 2)[2].strip() for l in self.L(f)[1:] if lvl(l) == 1 and tag_of(l) == tag]

    def fams_of(self, x, tag):
        return [l.split(" ", 2)[2].strip() for l in self.L(x)[1:] if lvl(l) == 1 and tag_of(l) == tag]

    def drop_line(self, x, tag, ref):
        r = self.L(x)
        r[:] = [l for l in r if not (lvl(l) == 1 and tag_of(l) == tag and l.split(" ", 2)[2:] == [ref])]

    def fixed_id(self, s, kind, *keys):
        """Optional fixed id from a step ("@I90012@" or "I90012"); refuses one that exists or existed."""
        v = g(s, *keys)
        if v in (None, ""):
            return None
        v = str(v).strip()
        x = f"@{v.strip('@')}@"
        if not re.fullmatch(r"@[A-Za-z0-9_]+@", x):
            raise RoundError(f"{keys[0]} '{v}' is not a valid id (letters, digits and _ only, like @{kind}90012@)")
        if x in self.ever or x in self.alias:
            raise RoundError(f"{keys[0]} {x} already exists (in the original or an earlier round)")
        return x

    def new_fam(self, husb=None, wife=None, children=(), fid=None):
        if fid:
            f = fid
        else:
            self.n_fam += 1
            f = f"@F{self.n}_{self.n_fam}@"
        body = ([f"1 HUSB {husb}"] if husb else []) + ([f"1 WIFE {wife}"] if wife else []) + [f"1 CHIL {c}" for c in children]
        self.add_rec(f, "FAM", body)
        for p in (husb, wife):
            if p:
                self.L(p).append(f"1 FAMS {f}")
        for c in children:
            self.L(c).append(f"1 FAMC {f}")
        return f

    def couple_fam(self, a, b, create=True, fid=None):
        """Family with exactly these spouses (either may be None), else a new one (with fixed id fid if given)."""
        for f in self.fams_of(a or b, "FAMS"):
            sp = set(self.refs_in_fam(f, "HUSB") + self.refs_in_fam(f, "WIFE"))
            if sp == {p for p in (a, b) if p}:
                if fid:
                    raise RoundError(f"family_id {fid}: this couple already has a family, {f}")
                return f
        if not create:
            return None
        h, w = a, b
        if (a and self.sex(a) == "F") or (b and self.sex(b) == "M"):
            h, w = b, a
        return self.new_fam(h, w, fid=fid)

    def sex(self, x):
        s = values(self.idx[x], "SEX")
        return s[0][:1].upper() if s else ""

    # --- sources
    def cite(self, src, level):
        """Citation lines for a source: a string (text with optional link), {text, url} or a list of those."""
        if not src:
            return []
        if isinstance(src, list):
            return [l for s in src for l in self.cite(s, level)]
        if isinstance(src, dict):
            text = g(src, "text", "tekst", "title", "titel", default="")
            url = g(src, "url", "link", default="")
        else:
            text, url = str(src), ""
            m = URL_RE.search(text)
            if m:
                url = m.group(0).rstrip(".,;)")
                text = (text[:m.start()] + text[m.start() + len(url):]).strip(" ,;:-–(").strip()
        if not self.round_src:
            self.round_src = f"@S{self.n}_R@"
            self.add_rec(self.round_src, "SOUR", text_lines(1, "TITL", self.round_title))
        out = [f"{level} SOUR {self.round_src}"]
        out += text_lines(level + 1, "PAGE", text or url)
        if url:
            out += [f"{level+1} DATA", f"{level+2} WWW {url}"]
        return out

    @staticmethod
    def src_text(src):
        if not src:
            return ""
        if isinstance(src, list):
            return "; ".join(Rebuild.src_text(s) for s in src)
        if isinstance(src, dict):
            return " ".join(x for x in (g(src, "text", "tekst", "title", "titel", default=""), g(src, "url", "link", default="")) if x)
        return str(src)

    # --- building blocks
    def event_block(self, tag, e, src):
        """New level-1 event block from {date, place, note, type, source}."""
        if isinstance(e, str):
            e = {"date": e}
        t = g(e, "type", "soort", "kind")
        desc = g(e, "description", "omschrijving") if tag == "EVEN" else None
        out = [f"1 {tag} {desc}" if desc else f"1 {tag}"]
        if tag == "EVEN" and t:
            out.append(f"2 TYPE {t}")
        d = gedcom_date(g(e, "date", "datum"))
        p = g(e, "place", "plaats")
        if d:
            out.append(f"2 DATE {d}")
        if p:
            out.append(f"2 PLAC {p}")
        if g(e, "age", "leeftijd"):
            out.append(f"2 AGE {g(e, 'age', 'leeftijd')}")
        if g(e, "note", "notitie"):
            out += text_lines(2, "NOTE", g(e, "note", "notitie"))
        out += self.cite(g(e, "source", "bron") or src, 2)
        return out

    def insert_event(self, x, blk):
        r = self.L(x)
        pos = len(r)
        for k in range(1, len(r)):
            if lvl(r[k]) == 1 and tag_of(r[k]) in ("SOUR", "OBJE", "NOTE", "_WLNK", "FAMS", "FAMC", "CHIL", "CHAN"):
                pos = k
                break
        r[pos:pos] = blk

    def person_body(self, p, src):
        gn = (g(p, "given_names", "given", "voornamen", default="") or "").strip()
        sn = (g(p, "surname", "achternaam", default="") or "").strip()
        body = [f"1 NAME {gn} /{sn}/".replace("  ", " ")] + ([f"2 GIVN {gn}"] if gn else []) + ([f"2 SURN {sn}"] if sn else [])
        sex = (g(p, "sex", "geslacht", default="") or "").upper()[:1]
        if sex in ("M", "F", "V", "W"):
            body.append(f"1 SEX {'M' if sex == 'M' else 'F'}")
        for keys, tag in ((("birth", "born", "geboren", "geboorte"), "BIRT"), (("baptism", "gedoopt", "doop"), "BAPM"),
                          (("death", "died", "overleden", "overlijden"), "DEAT"), (("burial", "begraven"), "BURI")):
            e = g(p, *keys)
            if e:
                body += self.event_block(tag, e, None)
        occ = g(p, "occupation", "beroep")
        for o in ([occ] if isinstance(occ, str) else occ or []):
            body.append(f"1 OCCU {o}")
        aka = g(p, "aka", "roepnaam", "alias")
        for a in ([aka] if isinstance(aka, (str, dict)) else aka or []):
            body += self.aka_lines(a)
        if g(p, "notes", "note", "notities", "notitie"):
            body += text_lines(1, "NOTE", g(p, "notes", "note", "notities", "notitie"))
        body += self.cite(src, 1)
        return body

    @staticmethod
    def aka_lines(a):
        if isinstance(a, dict):
            gn = (g(a, "given_names", "given", "voornamen", default="") or "").strip()
            sn = (g(a, "surname", "achternaam", default="") or "").strip()
        else:
            m = re.match(r"^(.*?)\s*/(.*)/\s*$", a.strip())
            gn, sn = (m.group(1).strip(), m.group(2).strip()) if m else (a.strip(), "")
        return [f"1 NAME {gn} /{sn}/".replace("  ", " ")] + ([f"2 GIVN {gn}"] if gn else []) + \
               ([f"2 SURN {sn}"] if sn else []) + ["2 TYPE aka"]

    # --- the steps
    def op_add(self, s, src):
        ref = str(g(s, "ref", default="") or "").strip()
        k = len(self.refs) + 1
        key = re.sub(r"[^A-Za-z0-9_]", "_", ref) if ref else str(k)
        x = self.fixed_id(s, "I", "id") or f"@I{self.n}_{key}@"
        if ref in self.refs:
            raise RoundError(f"ref '{ref}' used twice in this round")
        self.add_rec(x, "INDI", self.person_body(s, src))
        self.refs[ref or str(k)] = x
        return f"new {self.label(x)} {x}"

    def check_rejected(self, child, parent, s):
        why = g(s, "despite", "ondanks")
        for r in self.rejected:
            if r["child"] != child:
                continue
            same = r["parent"] == parent or norm_name(r["pname"]) == norm_name(self.name(parent))
            if same and why:
                r["back"] = self.t["back"].format(n=self.n, w=why)
            elif same:
                raise RoundError(f"{self.label(parent)} was rejected as parent of {self.label(child)} in round {r['n']}: "
                                 f"{r['reason']}. Add \"despite\": \"<new source and why>\" only if a new source refutes that.")

    def op_parents(self, s, src):
        child = self.resolve(g(s, "child", "kind"))
        fa = self.resolve(g(s, "father", "vader"), required=False)
        mo = self.resolve(g(s, "mother", "moeder"), required=False)
        if not fa and not mo:
            raise RoundError("no father or mother")
        for p in (fa, mo):
            if p:
                self.check_rejected(child, p, s)
        fid = self.fixed_id(s, "F", "family_id", "gezin_id")
        fc = self.fams_of(child, "FAMC")
        f = None
        for c in fc:
            h, w = (self.refs_in_fam(c, "HUSB") or [None])[0], (self.refs_in_fam(c, "WIFE") or [None])[0]
            if (fa and h and h != fa) or (mo and w and w != mo):
                raise RoundError(f"{self.label(child)} already has other parents in {c} ({self.label(h) if h else '-'} / "
                                 f"{self.label(w) if w else '-'}); remove the wrong link first with drop_link")
            f = c
        if f and fid:
            raise RoundError(f"family_id {fid}: {self.label(child)} already has a family, {f}")
        if f:
            for role, x in (("HUSB", fa), ("WIFE", mo)):
                if x and not self.refs_in_fam(f, role):
                    self.L(f).append(f"1 {role} {x}")
                    self.L(x).append(f"1 FAMS {f}")
                    self.merge_dup_families(x)
                    f = self.alias.get(f, f)
        else:
            f = self.couple_fam(fa, mo, fid=fid)
            self.L(f).append(f"1 CHIL {child}")
            self.L(child).append(f"1 FAMC {f}")
        marr = g(s, "marriage", "huwelijk")
        if marr:
            self.set_event(f, "MARR", marr if isinstance(marr, dict) else {"date": marr}, src)
        typ = g(s, "type", "soort", default="")
        if PEDI.get(str(typ).lower()):
            r = self.L(child)
            k = next(i for i, l in enumerate(r) if l == f"1 FAMC {f}")
            if not (k + 1 < len(r) and r[k + 1].startswith("2 PEDI")):
                r.insert(k + 1, f"2 PEDI {PEDI[str(typ).lower()]}")
        c = self.cite(src, 1)
        if c and not any(l == c[1] for l in self.L(f)):
            self.L(f).extend(c)
        for role, nl, x in (("father", "vader", fa), ("mother", "moeder", mo)):
            if x:
                self.rel[(child, x)] = [
                    g(s, f"status_{role}", f"status_{nl}", "status", default=self.t["certain"]),
                    self.src_text(g(s, f"source_{role}", f"bron_{nl}") or src) or g(s, "despite", "ondanks", default=""),
                    g(s, f"why_{role}", f"waarom_{nl}", f"note_{role}", f"opmerking_{nl}", "why", "waarom", "note", "opmerking", default=""),
                    g(s, f"type_{role}", f"soort_{nl}", "type", "soort", default="")]
        return f"parents of {self.label(child)}: " + " + ".join(self.label(x) for x in (fa, mo) if x)

    def op_status(self, s, src):
        child = self.resolve(g(s, "child", "kind"))
        done = []
        for role, nl, keys in (("father", "vader", ("father", "vader")), ("mother", "moeder", ("mother", "moeder")),
                               ("", "", ("parent", "ouder"))):
            if not g(s, *keys):
                continue
            x = self.resolve(g(s, *keys))
            pre = [f"status_{role}", f"status_{nl}"] if role else []
            st = g(s, *(pre + ["status", "zekerheid"]))
            if not st:
                raise RoundError("missing status")
            old = self.rel.get((child, x)) or ["", "", "", ""]
            # a status step changes the certainty (and source/reason when given); it never drops the kind of link
            # (raised/adopted/foster): a round that only set "certain" once wiped an adoption
            self.rel[(child, x)] = [st,
                                    self.src_text(g(s, *([f"source_{role}", f"bron_{nl}"] if role else []), "source", "bron") or src),
                                    g(s, *([f"why_{role}", f"waarom_{nl}", f"note_{role}", f"opmerking_{nl}"] if role else []),
                                      "why", "waarom", "note", "opmerking", default=""),
                                    g(s, *([f"type_{role}", f"soort_{nl}"] if role else []), "type", "soort", default="")
                                    or (old[3] if len(old) > 3 else "")]
            done.append(f"{self.label(x)}: {st}")
        if not done:
            raise RoundError("no parent given (father, mother or parent)")
        return f"status for {self.label(child)}: " + ", ".join(done)

    def target(self, s):
        """Person or family a step is about."""
        if g(s, "family", "gezin"):
            return self.resolve(g(s, "family", "gezin"), "family")
        x = self.resolve(g(s, "person", "persoon"))
        if g(s, "partner"):
            return self.couple_fam(x, self.resolve(g(s, "partner")), fid=self.fixed_id(s, "F", "family_id", "gezin_id"))
        return x

    def set_event(self, x, tag, e, src, keep=False, separate=False):
        """Update the first event with this tag (single events) or add one. keep=True only fills empty fields."""
        r = self.L(x)
        bs = blocks(r, tag)
        if tag == "EVEN":
            t = g(e, "type", "soort")
            bs = [b for b in bs if sub_value(r[b[0]:b[1]], "TYPE") == t]
        if not bs or separate or tag not in SINGLE:
            self.insert_event(x, self.event_block(tag, e, src))
            return "added"
        s0, e0 = bs[0]
        blk = r[s0:e0]
        new = [blk[0]]
        rest = blk[1:]
        notes = []
        for key, sub, conv in ((("date", "datum"), "DATE", gedcom_date), (("place", "plaats"), "PLAC", lambda v: v)):
            v = g(e, *key)
            if not v:
                continue
            v = conv(v)
            old = sub_value(blk, sub)
            if old and keep:
                continue
            if old and old != v:
                notes.append(self.t["was"].format(v=old, n=self.n))
            rest = [l for l in rest if not (lvl(l) == 2 and tag_of(l) == sub)]
            new.append(f"2 {sub} {v}")
        # keep the original order: DATE, PLAC first, then the rest
        new += rest
        if g(e, "note", "notitie"):
            new += text_lines(2, "NOTE", g(e, "note", "notitie"))
        for n_ in notes:
            new.append(f"2 NOTE {n_}")
        new += self.cite(g(e, "source", "bron") or src, 2)
        r[s0:e0] = new
        return "updated"

    def op_event(self, s, src):
        kind = str(g(s, "type", "soort", "event", "gebeurtenis", default="") or "").strip()
        tag = EVENT_TAGS.get(kind.lower()) or (kind.upper() if kind.upper() in GEDCOM_EVENTS else "EVEN")
        if not kind:
            raise RoundError("missing type (birth, death, marriage, residence, …)")
        x = self.target(s)
        if tag in FAM_EVENTS and self.kind(x) != "FAM":
            raise RoundError(f"{kind} belongs to a couple: give person + partner, or family")
        e = dict(s)
        how = self.set_event(x, tag, e, src, keep=bool(g(s, "if_empty", "alleen_als_leeg", "only_if_missing")),
                             separate=bool(g(s, "separate", "apart")))
        return f"{tag} {how} for {self.label(x) if self.kind(x) == 'INDI' else x}"

    def op_occupation(self, s, src):
        x = self.resolve(g(s, "person", "persoon"))
        occ = g(s, "occupation", "beroep")
        if not occ:
            raise RoundError("missing occupation")
        r = self.L(x)
        bs = [b for b in blocks(r, "OCCU") if r[b[0]].split(" ", 2)[2:] == [occ]]
        if bs and not g(s, "date", "datum"):
            s0, e0 = bs[0]
            extra = []
            if g(s, "note", "notitie"):
                extra += text_lines(2, "NOTE", g(s, "note", "notitie"))
            extra += self.cite(src, 2)
            r[e0:e0] = extra
            return f"occupation {occ} confirmed for {self.label(x)}"
        blk = [f"1 OCCU {occ}"]
        d, p = gedcom_date(g(s, "date", "datum")), g(s, "place", "plaats")
        if d:
            blk.append(f"2 DATE {d}")
        if p:
            blk.append(f"2 PLAC {p}")
        if g(s, "note", "notitie"):
            blk += text_lines(2, "NOTE", g(s, "note", "notitie"))
        blk += self.cite(src, 2)
        self.insert_event(x, blk)
        return f"occupation {occ} for {self.label(x)}"

    def op_note(self, s, src):
        x = self.target(s)
        text = g(s, "text", "tekst", "note", "notitie")
        if not text:
            raise RoundError("missing text")
        self.L(x).extend(text_lines(1, "NOTE", text) + self.cite(src, 1))
        return f"note for {self.label(x) if self.kind(x) == 'INDI' else x}"

    def op_aka(self, s, src):
        x = self.resolve(g(s, "person", "persoon"))
        lines = self.aka_lines(g(s, "name", "naam") or s)
        r = self.L(x)
        if lines[0] in r or norm_name(lines[0][7:]) == norm_name(name(self.idx[x])):
            return f"aka already there for {self.label(x)}"
        if g(s, "note", "notitie"):
            lines += text_lines(2, "NOTE", g(s, "note", "notitie"))
        lines += self.cite(src, 2)
        b = blocks(r, "NAME")
        pos = b[-1][1] if b else 1
        r[pos:pos] = lines
        return f"aka {lines[0][7:]} for {self.label(x)}"

    def op_name(self, s, src):
        x = self.resolve(g(s, "person", "persoon"))
        r = self.L(x)
        b = blocks(r, "NAME")
        new = self.aka_lines(g(s, "name", "naam") or s)[:-1]  # without TYPE aka
        if not b:
            r[1:1] = new
            return f"name {new[0][7:]} for {x}"
        s0, e0 = b[0]
        old = r[s0][7:].strip()
        sub = [l for l in r[s0 + 1:e0] if not re.match(r"2 (GIVN|SURN) ", l)]
        repl = new + sub + self.cite(src, 2)
        if g(s, "keep_old", "oude_houden", default=True) and norm_name(old) != norm_name(new[0][7:]):
            repl += self.aka_lines(old)
        r[s0:e0] = repl
        return f"name {old} -> {new[0][7:]}"

    def op_drop_link(self, s, src):
        child = self.resolve(g(s, "child", "kind"))
        reason = g(s, "reason", "reden")
        if not reason:
            raise RoundError("a removed link needs a reason (reason/reden)")
        parents_ = [self.resolve(g(s, k)) for k in ("parent", "ouder", "father", "vader", "mother", "moeder") if g(s, k)]
        if not parents_:
            raise RoundError("no parent given (parent, father or mother)")
        for parent in parents_:
            fams = [f for f in self.fams_of(child, "FAMC")
                    if parent in self.refs_in_fam(f, "HUSB") + self.refs_in_fam(f, "WIFE")]
            if not fams:
                raise RoundError(f"{self.label(parent)} is not a parent of {self.label(child)}")
            f = fams[0]
            others = [c for c in self.refs_in_fam(f, "CHIL") if c != child]
            role = "HUSB" if parent in self.refs_in_fam(f, "HUSB") else "WIFE"
            couple = str(g(s, "couple", "paar", default="") or "").lower()
            real = bool(others) or any(blocks(self.L(f), t) for t in ("MARR", "MARB", "DIV", "ENGA"))
            split = couple in ("split", "splitsen") or (couple not in ("keep", "houden") and not real)
            if split and not others:
                self.drop_line(f, role, parent)
                self.drop_line(parent, "FAMS", f)
                if not (self.refs_in_fam(f, "HUSB") + self.refs_in_fam(f, "WIFE")):
                    self.drop_line(child, "FAMC", f)
                    self.delete(f)
            else:
                self.drop_line(f, "CHIL", child)
                self.drop_line(child, "FAMC", f)
                if split:
                    self.drop_line(f, role, parent)
                    self.drop_line(parent, "FAMS", f)
                other = [p for p in self.refs_in_fam(f, "HUSB") + self.refs_in_fam(f, "WIFE") if p != parent]
                if other:
                    nf = self.couple_fam(other[0], None)
                    self.L(nf).append(f"1 CHIL {child}")
                    self.L(child).append(f"1 FAMC {nf}")
            # split with other children: the parent leaves the family, so the link goes for all of them
            hit = [child] + (others if split else [])
            for c in hit:
                self.L(c).extend([f"1 NOTE {self.t['dropped_link'].format(n=self.n, p=self.label(parent), x=parent, r=reason)}"]
                                 + self.cite(src, 1))
                self.rejected.append({"child": c, "cname": self.label(c), "parent": parent, "pname": self.name(parent),
                                      "plabel": self.label(parent), "from": g(s, "from", "herkomst", "origin", default=""),
                                      "reason": reason, "source": self.src_text(src), "n": self.n})
                self.rel.pop((c, parent), None)
        return f"link removed: {self.label(child)} -/- " + ", ".join(self.label(p) for p in parents_)

    def merge_blocks(self, keep, drop, dropped_label):
        """Move drop's level-1 blocks to keep: names as aka, single events only when keep lacks them."""
        rk, rd = self.L(keep), self.L(drop)
        for s0, e0 in blocks(rd):
            blk = rd[s0:e0]
            t = tag_of(blk[0])
            if t == "NAME":
                v = blk[0][7:].strip()
                if all(norm_name(l[7:]) != norm_name(v) for l in rk if l.startswith("1 NAME ")):
                    nb = blocks(rk, "NAME")
                    pos = nb[-1][1] if nb else 1
                    rk[pos:pos] = self.aka_lines(v)
                continue
            if t in SKIP_ON_MERGE or t in ("HUSB", "WIFE", "CHIL"):
                continue
            if t in SINGLE and blocks(rk, t):
                k0, k1 = blocks(rk, t)[0]
                kb = rk[k0:k1]
                extra = []
                dv = " ".join(x for x in (sub_value(blk, "DATE"), sub_value(blk, "PLAC")) if x)
                kv = " ".join(x for x in (sub_value(kb, "DATE"), sub_value(kb, "PLAC")) if x)
                if dv and dv != kv:
                    extra.append(f"2 NOTE {self.t['merged_other'].format(x=drop, v=dv)}")
                # carry its sources over
                i = 1
                while i < len(blk):
                    if lvl(blk[i]) == 2 and tag_of(blk[i]) == "SOUR":
                        j = i + 1
                        while j < len(blk) and lvl(blk[j]) > 2:
                            j += 1
                        extra += blk[i:j]
                        i = j
                    else:
                        i += 1
                rk[k1:k1] = extra
                continue
            # skip exact duplicates
            txt = "\n".join(blk)
            if any("\n".join(rk[a:b]) == txt for a, b in blocks(rk, t)):
                continue
            rk.extend(blk)

    def op_merge(self, s, src):
        keep = self.resolve(g(s, "keep", "houd", "houden"))
        drop = self.resolve(g(s, "drop", "weg"))
        if keep == drop:
            raise RoundError("keep and drop are the same person")
        reason = g(s, "reason", "reden", default="")
        dl = self.label(drop)
        self.merge_blocks(keep, drop, dl)
        for tag in ("FAMS", "FAMC"):
            for f in self.fams_of(drop, tag):
                r = self.L(f)
                r[:] = [(l.rsplit(" ", 1)[0] + " " + keep) if lvl(l) == 1 and tag_of(l) in ("HUSB", "WIFE", "CHIL")
                        and l.endswith(" " + drop) else l for l in r]
                if f"1 {tag} {f}" not in self.L(keep):
                    self.L(keep).append(f"1 {tag} {f}")
        self.delete(drop)
        self.alias[drop] = keep
        self.L(keep).extend([f"1 NOTE {self.t['merged'].format(n=self.n, x=drop, p=dl, r=(': ' + reason) if reason else '')}"]
                            + self.cite(src, 1))
        self.merge_dup_families(keep)
        self.dedupe(keep)
        for (c, p) in list(self.rel):
            if drop in (c, p):
                v = self.rel.pop((c, p))
                self.rel.setdefault((keep if c == drop else c, keep if p == drop else p), v)
        return f"merged {dl} {drop} into {self.label(keep)} {keep}"

    def merge_dup_families(self, x):
        """Families of x with the same spouses become one (the first in the file stays)."""
        seen = {}
        for f in list(self.fams_of(x, "FAMS")):
            if f not in self.idx:
                continue
            k = (tuple(self.refs_in_fam(f, "HUSB")), tuple(self.refs_in_fam(f, "WIFE")))
            if k in seen:
                keep = seen[k]
                self.merge_blocks(keep, f, f)
                for c in self.refs_in_fam(f, "CHIL"):
                    if f"1 CHIL {c}" not in self.L(keep):
                        self.L(keep).append(f"1 CHIL {c}")
                    cr = self.L(c)
                    cr[:] = [f"1 FAMC {keep}" if l == f"1 FAMC {f}" else l for l in cr]
                    self.dedupe(c)
                for p in self.refs_in_fam(f, "HUSB") + self.refs_in_fam(f, "WIFE"):
                    self.drop_line(p, "FAMS", f)
                self.delete(f)
                self.alias[f] = keep
            else:
                seen[k] = f
        # a family where x is now twice the same child
        for f in self.fams_of(x, "FAMS") + self.fams_of(x, "FAMC"):
            if f in self.idx:
                self.dedupe(f)

    def dedupe(self, x):
        seen, out = set(), []
        for l in self.L(x):
            if lvl(l) == 1 and tag_of(l) in ("FAMS", "FAMC", "CHIL", "HUSB", "WIFE"):
                if l in seen:
                    continue
                seen.add(l)
            out.append(l)
        self.L(x)[:] = out

    def op_drop_event(self, s, src):
        x = self.target(s)
        kind = str(g(s, "type", "soort", "event", "gebeurtenis", default="") or "")
        tag = EVENT_TAGS.get(kind.lower()) or (kind.upper() if kind.upper() in GEDCOM_EVENTS else "EVEN")
        reason = g(s, "reason", "reden")
        if not reason:
            raise RoundError("a removed event needs a reason (reason/reden)")
        match = str(g(s, "match", "met", "date", "datum", default="") or "")
        r = self.L(x)
        gone = []
        for s0, e0 in reversed(blocks(r, tag)):
            blk = r[s0:e0]
            if tag == "EVEN" and sub_value(blk, "TYPE").lower() != kind.lower():
                continue
            if match and not any(match.lower() in l.lower() for l in blk):
                continue
            gone.insert(0, " ".join(x_ for x_ in (tag, sub_value(blk, "DATE"), sub_value(blk, "PLAC")) if x_))
            del r[s0:e0]
        if not gone:
            raise RoundError(f"no {tag} event" + (f" with '{match}'" if match else "") + f" for {self.label(x)}")
        for v in gone:
            r.extend([f"1 NOTE {self.t['dropped_event'].format(n=self.n, v=v, r=reason)}"] + self.cite(src, 1))
            self.gone_events.append({"who": self.label(x) if self.kind(x) == "INDI" else x, "x": x, "what": v,
                                     "reason": reason, "source": self.src_text(src), "n": self.n})
        return f"removed {', '.join(gone)} for {self.label(x) if self.kind(x) == 'INDI' else x}"

    def op_drop_person(self, s, src):
        x = self.resolve(g(s, "person", "persoon"))
        reason = g(s, "reason", "reden")
        if not reason:
            raise RoundError("a removed person needs a reason (reason/reden)")
        lab = self.label(x)
        for tag in ("FAMS", "FAMC"):
            for f in self.fams_of(x, tag):
                if f not in self.idx:
                    continue
                r = self.L(f)
                r[:] = [l for l in r if not (lvl(l) == 1 and tag_of(l) in ("HUSB", "WIFE", "CHIL") and l.endswith(" " + x))]
                members = self.refs_in_fam(f, "HUSB") + self.refs_in_fam(f, "WIFE") + self.refs_in_fam(f, "CHIL")
                if len(members) <= 1:
                    for m in members:
                        self.drop_line(m, "FAMS", f)
                        self.drop_line(m, "FAMC", f)
                    self.delete(f)
        self.delete(x)
        self.rel = {k: v for k, v in self.rel.items() if x not in k}
        self.gone_people.append({"who": f"{lab} {x}", "from": g(s, "from", "herkomst", "origin", default=""),
                                 "reason": reason, "source": self.src_text(src), "n": self.n})
        return f"removed {lab} {x}"

    def op_places(self, s, src):
        m = g(s, "map", "tabel", "places", "plaatsen", default={})
        if not isinstance(m, dict) or not m:
            raise RoundError("places needs a map: {\"old name\": \"Place, Province, Country\"}")
        for k, v in m.items():
            self.places[norm_place(k)] = v
        return f"{len(m)} place name(s) in the table"

    def op_lines(self, s, src):
        x = self.target(s)
        ls = g(s, "lines", "regels", default=[])
        if isinstance(ls, str):
            ls = ls.split("\n")
        for l in ls:
            if lvl(l) < 1 or lvl(l) == 99:
                raise RoundError(f"line must start with a level of 1 or more: {l!r}")
        if ls and lvl(ls[0]) != 1:
            raise RoundError("the first line must be level 1")
        self.L(x).extend(ls)
        return f"{len(ls)} line(s) for {self.label(x) if self.kind(x) == 'INDI' else x}"

    # --- one round
    def apply(self, n, path, data):
        self.n, self.refs, self.round_src, self.n_fam = n, {}, None, 0
        self.live_steps = []
        if isinstance(data, list):
            data = {"steps": data}
        title = g(data, "title", "titel", default="")
        date = g(data, "date", "datum", default="")
        self.round_title = f"{self.t['round_src'].format(n=n)}" + (f": {title}" if title else "") + (f" ({date})" if date else "")
        default_src = g(data, "source", "bron")
        steps = g(data, "steps", "stappen", default=[])
        for i, s in enumerate(steps, 1):
            op = OPS.get(str(g(s, "op", "do", "doe", default="")).strip().lower())
            if not op:
                raise SystemExit(f"{path}, step {i}: unknown op {g(s, 'op', 'do', 'doe')!r}. "
                                 f"Known: {', '.join(sorted(set(OPS)))}")
            try:
                msg = getattr(self, "op_" + op)(s, g(s, "source", "bron") or default_src)
            except RoundError as e:
                raise SystemExit(f"{path}, step {i} ({op}): {e}")
            self.log.append(f"  {n}.{i} {msg}")
            self.live_steps.append(live_step(op, s, msg))
        return len(steps)

    # --- end
    def finish_places(self):
        changed = 0
        for r in self.recs:
            ls = r[2]
            for k, l in enumerate(ls):
                if tag_of(l) == "PLAC":
                    p = l.split(" ", 2)
                    v = p[2] if len(p) > 2 else ""
                    nv = self.places.get(norm_place(v))
                    if nv and nv != v:
                        ls[k] = f"{p[0]} PLAC {nv}"
                        changed += 1
        rest = {}
        for r in self.recs:
            for l in r[2]:
                if tag_of(l) == "PLAC":
                    v = l.split(" ", 2)[2].strip() if len(l.split(" ", 2)) > 2 else ""
                    if v and v.count(",") < 2:
                        rest[v] = rest.get(v, 0) + 1
        return changed, rest

    def lines(self, header_note):
        out = []
        for r in self.recs:
            out += r[2]
            if r[1] == "HEAD" and header_note:
                out.append(f"1 NOTE {header_note}")
        return out + ["0 TRLR"]

    def relation_rows(self, base):
        rows = []
        for r in self.recs:
            if r[1] != "INDI":
                continue
            c = r[0]
            for f in self.fams_of(c, "FAMC"):
                if f not in self.idx:
                    continue
                for p in self.refs_in_fam(f, "HUSB") + self.refs_in_fam(f, "WIFE"):
                    if p not in self.idx:
                        continue
                    v = self.rel.get((c, p)) or base.get((c, p)) or [self.t["not_checked"], "", "", ""]
                    rows.append([c, p, self.name(c), self.name(p)] + [str(x or "") for x in v])
        return rows

    def write_rejected(self, path):
        t = self.t
        esc = lambda v: str(v or "–").replace("|", "\\|").replace("\n", " ")
        out = [f"# {t['rej_title']}", "", t["rej_intro"], "", t["rej_cols"], "|---|---|---|---|---|---|"]
        for r in self.rejected:
            out.append(f"| {esc(r['cname'])} {r['child']} | {esc(r['plabel'])} {r['parent']} | {esc(r['from'])} | "
                       f"{esc(r['reason'] + r.get('back', ''))} | {esc(r['source'])} | {r['n']} |")
        if not self.rejected:
            out = out[:-2] + [t["none"]]
        if self.gone_people:
            out += ["", f"## {t['rej_people']}", "", t["rej_pcols"], "|---|---|---|---|---|"]
            for r in self.gone_people:
                out.append(f"| {esc(r['who'])} | {esc(r['from'])} | {esc(r['reason'])} | {esc(r['source'])} | {r['n']} |")
        if self.gone_events:
            out += ["", f"## {t['rej_events']}", "", t["rej_ecols"], "|---|---|---|---|---|"]
            for r in self.gone_events:
                out.append(f"| {esc(r['who'])} {r['x']} | {esc(r['what'])} | {esc(r['reason'])} | {esc(r['source'])} | {r['n']} |")
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        write(path, out)


def round_files(folder):
    out = []
    for f in os.listdir(folder):
        m = re.match(r"^(\d+)[^/]*\.json$", f)
        if m:
            out.append((int(m.group(1)), os.path.join(folder, f)))
    out.sort()
    nums = [n for n, _ in out]
    dup = sorted({n for n in nums if nums.count(n) > 1})
    if dup:
        sys.exit(f"Round number used twice in {folder}: {dup}")
    return out


def read_base_csv(path):
    base = {}
    if not path:
        return base
    with open(path, newline="", encoding="utf-8-sig") as fh:
        head = fh.readline(); fh.seek(0)
        delim = max(",;\t", key=head.count)
        for row in csv.DictReader(fh, delimiter=delim, quotechar='"'):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            c = row.get("child_id") or row.get("kind_id")
            p = row.get("parent_id") or row.get("ouder_id")
            if c and p:
                base[(c, p)] = [row.get("status") or row.get("zekerheid", ""), row.get("source") or row.get("bron", ""),
                                row.get("why") or row.get("waarom") or row.get("note") or row.get("opmerking", ""), row.get("type") or row.get("soort", "")]
    return base


def cmd_rebuild(a):
    if os.path.abspath(a.original) == os.path.abspath(a.output):
        sys.exit("The output may not be the original: the original is never changed.")
    rb = Rebuild(read(a.original), a.lang)
    files = round_files(a.rounds) if os.path.isdir(a.rounds) else []
    if not os.path.isdir(a.rounds):
        print(f"(no rounds folder {a.rounds} yet: output = original)")
    total, title, steps_last, last_path = 0, "", [], ""
    for n, path in files:
        try:
            data = json.load(open(path, encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"{path}: not valid JSON ({e})")
        total += rb.apply(n, path, data)
        if isinstance(data, dict):
            title = data.get("title") or data.get("titel") or os.path.splitext(os.path.basename(path))[0]
        steps_last, last_path = rb.live_steps, path
    changed, rest = rb.finish_places()
    last = os.path.basename(files[-1][1]) if files else "-"
    note = rb.t["built"].format(o=os.path.basename(a.original), k=len(files), last=last) if files else ""
    write(a.output, rb.lines(note))
    if not a.quiet:
        print("\n".join(rb.log))
    n_indi = sum(1 for r in rb.recs if r[1] == "INDI")
    print(f"rebuild: {len(files)} round(s), {total} step(s) -> {a.output} ({n_indi} people)")
    live("rebuild", _where=a.output, rounds=len(files), steps=total, people=n_indi, title=title)
    if steps_last:
        live("steps", _where=a.output, round=os.path.basename(last_path), title=title, steps=steps_last[-400:])
    if rb.places:
        print(f"places: {changed} place name(s) changed")
    if a.places_report or rb.places:
        top = sorted(rest.items(), key=lambda kv: -kv[1])[:15]
        if top:
            print(f"places not yet as 'Place, Province, Country': {len(rest)} — most used: "
                  + "; ".join(f"{k} ({v})" for k, v in top))
    if a.csv:
        base = read_base_csv(a.base_csv)
        base = {(rb.alias.get(c, c), rb.alias.get(p, p)): v for (c, p), v in base.items()}
        rows = rb.relation_rows(base)
        head = (["child_id", "parent_id", "child_name", "parent_name", "status", "source", "note", "type"] if a.lang == "en"
                else ["kind_id", "ouder_id", "kind_naam", "ouder_naam", "status", "bron", "opmerking", "soort"])
        tmp = a.csv + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(head)
            w.writerows(rows)
        os.replace(tmp, a.csv)
        unused = [k for k in rb.rel if k not in {(r[0], r[1]) for r in rows}]
        print(f"relations: {len(rows)} -> {a.csv}" + (f" ({len(unused)} status(es) for links that are not in the tree)" if unused else ""))
        for c, p in unused[:10]:
            print(f"  not a parent-child link (any more): {c} / {p}")
    if a.rejected:
        rb.write_rejected(a.rejected)
        print(f"rejected: {len(rb.rejected)} link(s), {len(rb.gone_people)} person(s), {len(rb.gone_events)} event(s) -> {a.rejected}")
    if a.media:
        cmd_media(argparse.Namespace(gedcom=a.output, csv=a.media, output=a.output))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", aliases=["nieuw"])
    n.add_argument("intake"); n.add_argument("output")
    t = sub.add_parser("add", aliases=["toevoegen"])
    t.add_argument("gedcom"); t.add_argument("additions"); t.add_argument("output")
    t.add_argument("--csv", help="relations CSV to append rows to")
    t.add_argument("--lang", "--taal", dest="lang", choices=["en", "nl"], default="en",
                   help="default status word and CSV header for a new file (default en)")
    c = sub.add_parser("check", aliases=["controleer"])
    c.add_argument("gedcom"); c.add_argument("output")
    c.add_argument("--start", help="GEDCOM id of the start person")
    c.add_argument("--gaps-to", "--gaten-tot", dest="gaps_to", type=int, default=8, help="show gaps up to this generation (default 8)")
    c.add_argument("--lang", "--taal", dest="lang", choices=["en", "nl"], default="en", help="report language (default en)")
    md = sub.add_parser("media")
    md.add_argument("gedcom"); md.add_argument("csv"); md.add_argument("output")
    rb = sub.add_parser("rebuild", aliases=["opbouwen"])
    rb.add_argument("original", help="the original GEDCOM (never changed)")
    rb.add_argument("rounds", help="folder with the round files (001-....json, 002-....json, ...)")
    rb.add_argument("output", help="the working version to write (e.g. source/tree.ged)")
    rb.add_argument("--csv", help="relations CSV to (re)write: every parent-child link with status and source")
    rb.add_argument("--base-csv", "--basis-csv", dest="base_csv",
                    help="existing relations CSV (by id) to start from; statuses in the rounds win")
    rb.add_argument("--rejected", "--afgewezen", dest="rejected", help="Markdown register of rejected links to (re)write")
    rb.add_argument("--media", help="media.csv to link at the end (same as the media subcommand)")
    rb.add_argument("--places-report", "--plaatsen-rapport", dest="places_report", action="store_true",
                    help="list the place names that are not yet 'Place, Province, Country'")
    rb.add_argument("--quiet", "--stil", dest="quiet", action="store_true", help="don't print every step")
    rb.add_argument("--lang", "--taal", dest="lang", choices=["en", "nl"], default="en",
                    help="language of generated notes, CSV header and register (default en)")
    a = ap.parse_args()
    {"new": cmd_new, "nieuw": cmd_new, "add": cmd_add, "toevoegen": cmd_add,
     "check": cmd_check, "controleer": cmd_check, "media": cmd_media,
     "rebuild": cmd_rebuild, "opbouwen": cmd_rebuild}[a.cmd](a)


if __name__ == "__main__":
    main()
