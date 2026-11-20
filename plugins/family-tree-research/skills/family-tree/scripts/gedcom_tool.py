#!/usr/bin/env python3
"""gedcom_tool.py — a small GEDCOM toolkit for the family-tree plugin.

Subcommands (Dutch names in brackets also work):
  new    (nieuw)       intake.json -> new GEDCOM (onboarding without an existing tree)
  add    (toevoegen)   GEDCOM + additions.json -> GEDCOM with new ancestors (+ optional CSV rows)
  check  (controleer)  GEDCOM -> Markdown report (counts, generations, gaps, odd dates)
  media                GEDCOM + media.csv -> GEDCOM with photos/documents per person (OBJE/FILE)

Examples:
  python3 gedcom_tool.py new data/intake.json source/tree.ged
  python3 gedcom_tool.py add source/tree.ged data/additions.json source/tree.ged --csv data/relations.csv
  python3 gedcom_tool.py check source/tree.ged reports/check.md --start @I1@ --lang en
  python3 gedcom_tool.py media source/tree.ged data/media.csv source/tree.ged

JSON keys may be English or Dutch (see references/gedcom-tool.md).
Standard library only; Python 3.8+.
"""
import argparse, csv, datetime, json, os, re, sys

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
    for words, code in ((("ca.", "ca ", "circa", "ongeveer", "omstreeks", "about", "abt", "approx", "~"), "ABT "),
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
    return [l.split(" ", 2)[2].strip() for l in rec[2]
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
                                 g(o, "note", "opmerking", default=""),
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
    odd = []
    for x, r in indi.items():
        by = year(ev(r, ("BIRT", "BAPM", "CHR"))[0])
        dy = year(ev(r, ("DEAT", "BURI", "CREM"))[0])
        if by and dy and dy < by:
            odd.append(t["deathbefore"].format(n=name(r), x=x, d=dy, b=by))
        if by and dy and dy - by > 105:
            odd.append(t["old"].format(n=name(r), x=x, a=dy - by))
        _, f, m = parents(x, indi, fam)
        for role, o, lo, hi in (("father", f, 16, 75), ("mother", m, 14, 50)):
            if o and by:
                oby = year(ev(indi[o], ("BIRT", "BAPM", "CHR"))[0])
                ody = year(ev(indi[o], ("DEAT", "BURI", "CREM"))[0])
                if oby and not (lo <= by - oby <= hi):
                    odd.append(t["parentage"].format(n=name(r), x=x, b=by, role=t[role], a=by - oby))
                if ody and by > ody + (1 if role == "father" else 0):
                    odd.append(t["afterdeath"].format(n=name(r), x=x, b=by, role=t[role], d=ody))
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
    added, failed, extra = 0, [], {}
    for r in rows:
        row = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
        who = row.get("person") or row.get("persoon") or row.get("id")
        x = find(who)
        f = row.get("file") or row.get("bestand")
        if not x or not f:
            failed.append(f"{who} / {f}"); continue
        have = [l[7:].strip() for l in indi[x][2] if l.startswith("2 FILE ")]
        if f in have or f in [e[0] for e in extra.get(x, [])]:
            continue
        extra.setdefault(x, []).append((f, row.get("title") or row.get("titel") or "", row.get("type") or row.get("soort") or ""))
    for x, items in extra.items():
        rec = indi[x][2]
        for f, title, kind in items:
            ext = os.path.splitext(f)[1].lstrip(".").lower() or "jpg"
            rec += ["1 OBJE", f"2 FILE {f}", f"3 FORM {ext}"]
            typ = MEDIA_TYPE.get(kind.lower())
            if typ:
                rec.append(f"4 TYPE {typ}")
            if title:
                rec.append(f"2 TITL {title}")
            added += 1
    write(a.output, [l for r in recs for l in r[2]])
    print(f"media: {added} links added for {len(extra)} people -> {a.output}")
    for f in failed:
        print("  not linked (person not found/not unique, or no file):", f)


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
    a = ap.parse_args()
    {"new": cmd_new, "nieuw": cmd_new, "add": cmd_add, "toevoegen": cmd_add,
     "check": cmd_check, "controleer": cmd_check, "media": cmd_media}[a.cmd](a)


if __name__ == "__main__":
    main()
