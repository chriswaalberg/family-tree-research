#!/usr/bin/env python3
"""archives.py — search open archives without a browser.

Every source has its own subcommand (Dutch names in brackets also work):

  oa search <name>              Open Archives (openarchieven.nl): index of records from dozens of archives
     (oa zoek)                  e.g. "Jan Jansen 1820-1850", or "Hendrik Jansen & Geesje Smit" (both in one record)
  oa show <archive:id> ...      a record, readable: event, everyone with their role, the source
     (oa toon)
  oa scans <archive:id> ...     download the scans of a record (The Hague, Rotterdam, Utrecht, Amsterdam,
                                Noord-Holland, Brabant, ...)
  saa <uuid or link> ...        Amsterdam City Archives open data (OAI-PMH, CC0): record + scans of any of its
                                36 indexes (passports, police reports '40-'45, family cards, population registers, ...)
  transkribus search <terms>    full text of Amsterdam civil records (also after 1880), Transkribus Read&Search
     (transkribus zoek)
  transkribus page <doc/page>   text + scan of one page
     (transkribus pagina)
  schiedam search "<first last>"  SchiedamGEN (Schiedam, Kethel, Mathenesse, Nieuwland): people
     (schiedam zoek)
  schiedam person <id>          a person: family, parents, records         (schiedam persoon)
  schiedam deed <id>            one record (certificate)                   (schiedam akte)
  riksarkivet --name/--place/--text   Swedish National Archives open API: indexed births and marriages of
                                Skåne, Blekinge, Halland (DDSS) with godparents, and the archive catalogue
  leiden <terms>                Erfgoed Leiden: archive descriptions, a person index of church records before 1811
                                (baptisms of Katwijk and more) and scans (IIIF)

Examples:
  python3 -I archives.py oa search "Jansen" --place Haarlem --type "BS Huwelijk" --from 1850 --to 1900
  python3 -I archives.py oa show saa:98533447-e76a-56a3-e053-b784100ade19
  python3 -I archives.py oa scans nha:C645C5F8-2967-479C-90D4-0113873AA7E3 --out scans/
  python3 -I archives.py saa https://archief.amsterdam/indexen/deeds/98533447-e76a-56a3-e053-b784100ade19 --out scans/
  python3 -I archives.py transkribus search "Landtman Geel"
  python3 -I archives.py transkribus page 1234567/12 --out scans/
  python3 -I archives.py schiedam search "Jan Groen"
  python3 -I archives.py riksarkivet --name Hans --place Åhus --from 1750 --to 1753
  python3 -I archives.py leiden "Maartje Hijg" --scans 1 --out scans/
  python3 -I archives.py leiden "DTB Katwijk" --filter 0440

Read a scan in full yourself: the OCR/handwriting text of these services is messy and misses things.
Run network commands in the foreground. No logins, captchas or paywalls: those are for the user.
Standard library only; Python 3.8+.
"""
import argparse
import html
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "family-tree-research (genealogy plugin; https://github.com/chriswaalberg/family-tree-research)"
PAUSE = 1.2          # seconds between two requests to the same site
RETRIES = 5          # tries on 429/502/503/504 and timeouts
BACKOFF = 20         # seconds to wait after a 429, times the try number
TIMEOUT = 90
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

_last = {}


def fetch(url, data=None, headers=None, opener=None, timeout=TIMEOUT):
    """GET (or POST when data is given) with a polite pause per host and backoff on 429/5xx."""
    host = urllib.parse.urlsplit(url).netloc
    h = {"User-Agent": UA}
    h.update(headers or {})
    if isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    for k in range(1, RETRIES + 1):
        wait = PAUSE - (time.time() - _last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with (opener.open if opener else urllib.request.urlopen)(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and k < RETRIES:
                s = BACKOFF * k if e.code == 429 else 5 * k
                print(f"  ({host} answered {e.code}; waiting {s} s)", file=sys.stderr)
                time.sleep(s)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            if k < RETRIES:
                print(f"  ({host}: {getattr(e, 'reason', e)}; trying again)", file=sys.stderr)
                time.sleep(5 * k)
                continue
            raise


def fetch_json(url, body=None, headers=None):
    h = {"Accept": "application/json"}
    if body is not None:
        h["Content-Type"] = "application/json"
        body = json.dumps(body).encode()
    h.update(headers or {})
    return json.loads(fetch(url, data=body, headers=h))


def save(data, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def ext_of(data):
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return ".tif"
    if data[:4] == b"%PDF":
        return ".pdf"
    return ".bin"


def safe(s):
    return re.sub(r"[^\w.-]+", "_", s)[:80]


def flat(x):
    """Open Archives JSON wraps every value: {"a2a_Year": {"a2a_Year": "1864"}} -> "1864"."""
    while isinstance(x, dict) and len(x) == 1:
        x = next(iter(x.values()))
    return x


def as_list(x):
    return x if isinstance(x, list) else ([] if x is None else [x])


# ---------------------------------------------------------------- Open Archives

OA = "https://api.openarch.nl/1.0/records/"


def oa_split(ref):
    m = re.search(r"([a-z]{2,6})[:/]([0-9A-Za-z{}_-]+)", ref.replace("openarchieven.nl/", ""))
    if not m:
        sys.exit(f"Not an Open Archives record: {ref} (expected <archive>:<identifier>, e.g. saa:98533447-...)")
    return m.group(1), m.group(2).strip("{}")


def oa_record(ref, lang):
    code, ident = oa_split(ref)
    d = fetch_json(f"{OA}show.json?" + urllib.parse.urlencode({"archive": code, "identifier": ident, "lang": lang}))
    return code, ident, (d[0] if isinstance(d, list) else d)


def cmd_oa_search(a):
    q = {"name": a.name, "lang": a.lang, "number_show": a.n, "start": a.start}
    if a.frm or a.to:
        q["name"] += f" {a.frm or ''}-{a.to or ''}"
    for k, v in (("eventplace", a.place), ("sourcetype", a.type), ("archive", a.archive),
                 ("relationtype", a.role), ("country_code", a.country)):
        if v:
            q[k] = v
    if a.scans:
        q["only_results_with_scans"] = "true"
    r = fetch_json(OA + "search.json?" + urllib.parse.urlencode(q))["response"]
    docs = r.get("docs", [])
    print(f"## {q['name']}: {r['number_found']} found, showing {a.start + 1}-{a.start + len(docs)}")
    for d in docs:
        e = d.get("eventdate") or {}
        date = "-".join(str(e[k]) for k in ("year", "month", "day") if e.get(k)) or "????"
        print(f"{date:10} {d.get('eventtype', '')} | {d.get('personname', '')} ({d.get('relationtype', '')}) | "
              f"{', '.join(d.get('eventplace') or [])} | {d.get('sourcetype', '')} | {d['archive_code']}:{d['identifier']}")
    if r["number_found"] > a.start + len(docs):
        print(f"(more: add --start {a.start + len(docs)})")


def pname(p):
    pn = p.get("a2a_PersonName", {})
    keys = ("a2a_PersonNameFirstName", "a2a_PersonNamePatronym", "a2a_PersonNamePrefixLastName", "a2a_PersonNameLastName")
    return " ".join(str(flat(pn[k])) for k in keys if k in pn)


def short(v):
    if isinstance(v, dict):
        return " ".join(str(x) for x in (short(y) for y in v.values()) if x)
    return str(flat(v))


def remarks(x):
    """Source remarks come as one value or a list of {Key, a2a_Value}; keep the useful ones."""
    out = []
    for r in as_list(x):
        if isinstance(r, dict) and "Key" in r:
            v = flat(r.get("a2a_Value"))
            if v and not isinstance(v, dict) and r["Key"] not in ("Provenance", "filename"):
                out.append(f"{r['Key']}: {v}")
        elif r:
            out.append(short(r))
    return "; ".join(out)


def cmd_oa_show(a):
    for ref in a.records:
        try:
            code, ident, r = oa_record(ref, a.lang)
        except urllib.error.HTTPError as e:
            print(f"== {ref}: error {e.code}")
            continue
        ev = as_list(r.get("a2a_Event"))
        ev = ev[0] if ev else {}
        role = {flat(x.get("a2a_PersonKeyRef")): flat(x.get("a2a_RelationType")) for x in as_list(r.get("a2a_RelationEP"))}
        print(f"== {code}:{ident}  {flat(ev.get('a2a_EventType'))} {short(ev.get('a2a_EventDate', {}))} "
              f"{short(ev.get('a2a_EventPlace', {}))}")
        for p in as_list(r.get("a2a_Person")):
            extra = {k.replace("a2a_", ""): short(v) for k, v in p.items() if k not in ("pid", "a2a_PersonName")}
            print(f"   {role.get(p.get('pid'), '?')}: {pname(p)}" + (f"  {extra}" if extra else ""))
        s = r.get("a2a_Source", {})
        ref_ = {k.replace("a2a_", ""): short(v) for k, v in s.get("a2a_SourceReference", {}).items()}
        print(f"   source: {short(s.get('a2a_SourceType', ''))} | {ref_}")
        rem = remarks(s.get("a2a_SourceRemark"))
        if rem:
            print(f"   remark: {rem[:600]}")
        n = len(oa_scan_urls(r))
        print(f"   scans: {n}" + (f"  (download: archives.py oa scans {code}:{ident} --out <folder>)" if n else ""))
        print(f"   link: https://www.openarchieven.nl/{code}:{ident}")


def oa_scan_urls(r):
    """All scan links in a record, full size. They don't always sit in the same field (The Hague puts them
    elsewhere), so take every image-service link: memorix thumbnails -> 1920x1080, proxy thumb -> download.
    Viewer pages (/embed/) and 250x250 previews are copies of the same scan."""
    out = []
    for u in re.findall(r'https?://(?:proxy\.archieven\.nl/(?:download|thumb)/|images\.memorix\.nl/[^/"]+/thumb/)[^"\s]+', json.dumps(r)):
        if "/embed/" in u or "/250x250/" in u:
            continue
        u = u.replace("proxy.archieven.nl/thumb/", "proxy.archieven.nl/download/")
        u = re.sub(r"/thumb/\d+x\d+/", "/thumb/640x480/", u)
        out.append(u)
    return list(dict.fromkeys(out))


def big(u):
    """The scan URLs are thumbnails; ask for the biggest size the image service gives."""
    m = re.match(r"(https://images\.memorix\.nl/[^/]+/thumb/)\d+x\d+(/.*)", u)
    if m:
        return [m.group(1) + "1920x1080" + m.group(2), u]
    if u.endswith("/info.json"):           # a IIIF image service: ask for a big rendering
        b = u[:-len("info.json")]
        return [b + "full/2400,/0/default.jpg", b + "full/full/0/default.jpg", b + "full/max/0/default.jpg"]
    return [u]


def download(urls, path_base):
    """Try the URLs in order; save the first that gives an image. Returns the path or None."""
    for u in urls:
        try:
            data = fetch(u)
        except urllib.error.HTTPError as e:
            last = f"{e.code} {u}"
            continue
        if ext_of(data) == ".bin":
            last = f"not an image: {u}"
            continue
        return save(data, path_base + ext_of(data))
    print(f"   scan not available ({last}); some archives only show scans on their own site")
    return None


def cmd_oa_scans(a):
    for ref in a.records:
        code, ident, r = oa_record(ref, "en")
        urls = oa_scan_urls(r)
        print(f"== {code}:{ident}: {len(urls)} scan(s)")
        for i, u in enumerate(urls, 1):
            p = download(big(u), os.path.join(a.out, f"{code}_{safe(ident)}_{i}"))
            if p:
                print("   scan:", p)


# ---------------------------------------------------------------- Amsterdam City Archives, open data

SAA_OAI = "https://webservices.memorix.nl/a2a/a66155dd-f750-40be-9ddd-244d72248fa3"   # published on opendata.memorix.nl/organization/ams
A2A = {"a": "http://Mindbus.nl/A2A", "o": "http://www.openarchives.org/OAI/2.0/"}


def txt(el):
    return " ".join(t.strip() for t in el.itertext() if t.strip()) if el is not None else ""


def cmd_saa(a):
    for arg in a.records:
        m = UUID.search(arg)
        if not m:
            print(f"== {arg}: no uuid in it")
            continue
        uuid = m.group(0).lower()
        root = ET.fromstring(fetch(f"{SAA_OAI}?verb=GetRecord&metadataPrefix=oai_a2a&identifier={uuid}"))
        rec = root.find(".//a:A2A", A2A)
        if rec is None:
            print(f"== {uuid}: not found ({txt(root.find('.//o:error', A2A))})")
            continue
        src = rec.find("a:Source", A2A)
        print(f"== {uuid}\n   source: {txt(src.find('a:SourceType', A2A))} | {txt(src.find('a:SourceDate', A2A))} | "
              f"{txt(src.find('a:SourceReference', A2A))}")
        ev = rec.find("a:Event", A2A)
        if ev is not None:
            print(f"   event: {txt(ev)}")
        rel = {r.find("a:PersonKeyRef", A2A).text: txt(r.find("a:RelationType", A2A)) for r in rec.findall("a:RelationEP", A2A)}
        for p in rec.findall("a:Person", A2A):
            born = (txt(p.find("a:BirthDate", A2A)) + " " + txt(p.find("a:BirthPlace", A2A))).strip()
            extra = " | ".join(x for x in (born and "born " + born, txt(p.find("a:Profession", A2A)),
                                            txt(p.find("a:Residence", A2A))) if x)
            print(f"   {rel.get(p.get('pid'), '?')}: {txt(p.find('a:PersonName', A2A))}" + (f" | {extra}" if extra else ""))
        rem = txt(src.find("a:SourceRemark", A2A))
        if rem:
            print(f"   remark: {plain(rem)[:600]}")
        thumbs = re.findall(r"https://images\.memorix\.nl/ams/thumb/\d+x\d+/[0-9a-f-]+\.jpg", ET.tostring(rec, encoding="unicode"))
        for i, u in enumerate(dict.fromkeys(re.sub(r"/thumb/\d+x\d+/", "/thumb/640x480/", t) for t in thumbs), 1):
            if a.out:
                p = download(big(u), os.path.join(a.out, f"saa_{uuid}_{i}"))
                if p:
                    print("   scan:", p)
            else:
                print("   scan:", big(u)[0])
        print(f"   link: https://archief.amsterdam/indexen/deeds/{uuid}")


# ---------------------------------------------------------------- Transkribus (Amsterdam civil records)

TK = "https://api-read.transkribus.eu"
TK_COLL = 221825     # Stadsarchief Amsterdam: Burgerlijke Stand and more


def cmd_tk_search(a):
    d = fetch_json(TK + "/search", body={"term": a.terms, "collections": [a.collection], "offset": a.start, "limit": a.n})
    res = d.get("results", [])
    print(f"## {a.terms}: {d.get('total')} pages found, showing {a.start + 1}-{a.start + len(res)}")
    for r in res:
        sn = " | ".join("".join(f"**{x['string']}**" if x.get("isMatch") else x["string"] for x in s) for s in r.get("snippets", []))
        print(f"{r['id']}/{r['page']}\t{r.get('title', '')}\t{r.get('hierarchy', '')}\t{(r.get('dateFrom') or '')[:4]}\n   {sn[:500]}")
    if res:
        print("(read a page: archives.py transkribus page <doc/page> --out <folder>)")


def cmd_tk_page(a):
    for ref in a.pages:
        m = re.search(r"(\d+)\D+(\d+)", ref)
        if not m:
            print(f"== {ref}: expected <docId>/<page>")
            continue
        doc, nr = m.groups()
        d = json.loads(fetch(f"{TK}/documents/{doc}/pages/{nr}"))
        root = ET.fromstring(fetch(d["content"]))
        ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
        lines = []
        for tl in root.iter(ns + "TextLine"):
            u = tl.find(f"{ns}TextEquiv/{ns}Unicode")
            if u is not None and u.text:
                lines.append(u.text)
        pd = d.get("pageData", {})
        print(f"== {doc}/{nr}  {pd.get('extId', pd.get('title', ''))}  {pd.get('desc', '')}  ({len(lines)} lines)")
        if pd.get("backlink"):
            print("   link:", pd["backlink"])
        base = os.path.join(a.out, f"transkribus_{doc}_{nr}")
        save("\n".join(lines).encode(), base + ".txt")
        print("   text:", base + ".txt")
        if d.get("image") and not a.no_image:
            p = download(big(d["image"]), base)
            if p:
                print("   scan:", p)
        if a.print:
            print("\n".join("   | " + x for x in lines))


# ---------------------------------------------------------------- SchiedamGEN (form postbacks, no API)

SG = "https://sgen.schiedam.nl/default.aspx"


class Schiedam:
    """sgen.schiedam.nl has no API; this repeats what its buttons do (ASP.NET postbacks). Scans need a login: not here."""

    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(self, data=None):
        return fetch(SG, data=data, opener=self.op).decode("utf-8", "replace")

    @staticmethod
    def form(h):
        d = {}
        for m in re.finditer(r"<input[^>]*>", h):
            t = m.group(0)
            n, v, ty = (re.search(r'%s="([^"]*)"' % k, t) for k in ("name", "value", "type"))
            if n and (not ty or ty.group(1) in ("hidden", "text")):
                d[html.unescape(n.group(1))] = html.unescape(v.group(1)) if v else ""
        return d

    def post(self, upd):
        d = self.form(self.get())
        d.update(upd)
        return self.get(d)

    def button(self, name, arg):
        state = {"text": "", "value": "", "checked": False, "target": "", "navigateUrl": "", "commandName": "",
                 "commandArgument": arg, "autoPostBack": True, "selectedToggleStateIndex": 0,
                 "validationGroup": None, "readOnly": False, "primary": False, "enabled": True}
        return self.post({"__EVENTTARGET": name, "__EVENTARGUMENT": "", name + "_ClientState": json.dumps(state)})

    def search(self, q):
        cs = json.dumps({"enabled": True, "emptyMessage": "", "validationText": q, "valueAsString": q, "lastSetTextBoxValue": q})
        return self.post({"txtSearch": q, "txtSearch_ClientState": cs, "cmdSearch.x": "10", "cmdSearch.y": "10"})


def plain(h):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def sg_text(h):
    t = plain(h)
    for head in ("Nieuwe zoekopdracht", "Verfijn zoekresultaat"):
        if head in t:
            t = t.split(head, 1)[1]
    t = t.rsplit("Begint met Gelijk aan ", 1)[-1]
    return t.split("© Gemeentearchief")[0].replace(
        "Om de akten te kunnen downloaden en/of bekijken moet u eerst inloggen. ", "").strip()


def cmd_sg_search(a):
    if len(a.name.split()) < 2:
        print("SchiedamGEN needs a first name and a surname (a surname alone finds nothing).")
    h = Schiedam().search(a.name)
    m = re.search(r"([\d.]+ personen)", plain(h))
    print(f"## {a.name}: " + (m.group(1).replace("personen", "people") if m else "no results"))
    hits = re.findall(r'GetPersonDetails\((\d+)\).*?divItemBoxName">(.*?)</div>.*?divItemBoxSubtitle">(.*?)</div>', h, flags=re.S)
    for pid, name, sub in hits:
        print(f"{pid}\t{plain(name)}\t{plain(sub)}")
    if hits:
        print("(only the first page of results; narrow down with a fuller name. Next: archives.py schiedam person <id>)")


def cmd_sg_person(a):
    h = Schiedam().button("cmdPerson", a.id + ",0")
    print(sg_text(h))
    deeds = sorted(set(re.findall(r"GetCertificateDetails\((\d+)", h)))
    print("records:", " ".join(deeds) if deeds else "-", "  (archives.py schiedam deed <id>)")


def cmd_sg_deed(a):
    print(sg_text(Schiedam().button("cmdCertificate", a.id)))
    print(f"link: https://sgen.schiedam.nl/?type=CERT&id={a.id}  (the scan needs a login: ask the user)")


# ---------------------------------------------------------------- Riksarkivet (Sweden)

RA = "https://data.riksarkivet.se/api/records"   # terms: https://sok.riksarkivet.se/en/data-api/api/anvandarvillkor-api


def cmd_ra(a):
    if not (a.name or a.place or a.text):
        sys.exit("Give --name, --place and/or --text.")
    q = {k: v for k, v in {"name": a.name, "place": a.place, "text": a.text, "year_min": a.frm, "year_max": a.to,
                           "limit": a.n, "offset": a.start or None}.items() if v is not None}
    d = fetch_json(RA + "?" + urllib.parse.urlencode(q))
    items = d.get("items", [])
    print(f"## {d.get('totalHits')} found, showing {len(items)}")
    for it in items:
        link = it.get("_links", {}).get("self", "")
        if it.get("objectType") == "Register" and link:
            r = fetch_json(link)
            print(f"\n== {r.get('type')} {r.get('date')} {r.get('parish')} | {r.get('volume')} | {r.get('archive')}")
            for k, v in r.items():
                if k not in ("caption", "type", "date", "parish", "volume", "archive", "register", "createdBy", "_links"):
                    print(f"   {k}: {v}")
            print("   source:", link)
        else:
            print(f"\n== {it.get('objectType')} | {it.get('caption')} | {it.get('metadata', {}).get('date', '')} | "
                  f"{it.get('_links', {}).get('html', link)}")


# ---------------------------------------------------------------- Erfgoed Leiden

ELO = "https://data.erfgoedleiden.nl/search/records?lang=nl"


def cmd_leiden(a):
    d = fetch_json(ELO, body={"query": {"type": "FullTextQuery", "query": a.terms},
                              "pagination": {"page": a.page, "perPage": a.n}})
    rows = d.get("rows", [])
    print(f"## {a.terms}: {d.get('total')} found (page {a.page}, {len(rows)} rows)")
    for r in rows:
        parents = " / ".join(x.get("title", "") for x in r.get("data", {}).get("parents", []))
        desc = r.get("description") or ""
        if a.filter and a.filter.lower() not in (parents + " " + r.get("title", "") + " " + desc).lower():
            continue
        m = r.get("media") or {}
        n = m.get("total", len(m.get("rows", []))) if m else 0
        print(f"{r.get('id')} | {r.get('title', '')[:90]} | {parents[:80]} | scans: {n}")
        if desc.startswith("Persoonsvermelding"):       # person index: "Kind, Maartje, Hijg, Vader, Pieter, ..."
            print("   " + desc.split(":", 1)[1].strip()[:400])
        for x in (m.get("rows") or [])[:a.scans]:
            u = x.get("iiif")
            if not u:
                continue
            u = u.rstrip("/") + "/full/max/0/default.jpg"
            if a.out:
                p = download([u], os.path.join(a.out, f"leiden_{safe(x.get('name') or x.get('uuid') or r.get('id'))}"))
                if p:
                    print("   scan:", p)
            else:
                print("   scan:", u)


# ---------------------------------------------------------------- command line

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_subparsers(dest="source", required=True, metavar="source")

    def years(p):
        p.add_argument("--from", "--van", dest="frm", type=int, help="first year")
        p.add_argument("--to", "--tot", dest="to", type=int, help="last year")

    def out(p, required=True):
        p.add_argument("--out", "--uit", dest="out", required=required, help="folder for scans and text")

    # Open Archives
    oa = src.add_parser("oa", aliases=["openarchieven"], help="Open Archives (openarchieven.nl)")
    oas = oa.add_subparsers(dest="cmd", required=True, metavar="command")
    p = oas.add_parser("search", aliases=["zoek"], help="search by name")
    p.add_argument("name", help='e.g. "Jan Jansen", "Jan Jansen 1820-1850", "Hendrik Jansen & Geesje Smit"')
    years(p)
    p.add_argument("--place", "--plaats", dest="place", help="event place")
    p.add_argument("--type", "--soort", dest="type", help='source type, e.g. "BS Geboorte", "BS Huwelijk", "BS Overlijden", "DTB Dopen"')
    p.add_argument("--archive", "--archief", dest="archive", help="archive code, e.g. saa, nha, bhi, hua, ghn")
    p.add_argument("--role", "--rol", dest="role", help='role, e.g. "Bruidegom", "Vader"')
    p.add_argument("--country", "--land", dest="country", help="country code, e.g. nl, be, sr")
    p.add_argument("--scans", action="store_true", help="only records with scans")
    p.add_argument("--n", "--aantal", dest="n", type=int, default=50, help="results per page (max 100)")
    p.add_argument("--start", type=int, default=0, help="skip this many results (paging)")
    p.add_argument("--lang", "--taal", dest="lang", default="en", help="language of event/role names: en or nl")
    p.set_defaults(func=cmd_oa_search)
    p = oas.add_parser("show", aliases=["toon"], help="show records readably")
    p.add_argument("records", nargs="+", help="<archive>:<identifier> or an openarchieven.nl link")
    p.add_argument("--lang", "--taal", dest="lang", default="en")
    p.set_defaults(func=cmd_oa_show)
    p = oas.add_parser("scans", help="download the scans of records")
    p.add_argument("records", nargs="+")
    out(p)
    p.set_defaults(func=cmd_oa_scans)

    # Amsterdam City Archives open data
    p = src.add_parser("saa", aliases=["amsterdam"], help="Amsterdam City Archives open data: record + scans")
    p.add_argument("records", nargs="+", help="uuid, archief.amsterdam/indexen/deeds/<uuid> link or saa:<uuid>")
    out(p, required=False)
    p.set_defaults(func=cmd_saa)

    # Transkribus
    tk = src.add_parser("transkribus", help="Transkribus full text of Amsterdam civil records")
    tks = tk.add_subparsers(dest="cmd", required=True, metavar="command")
    p = tks.add_parser("search", aliases=["zoek"], help="full-text search")
    p.add_argument("terms", help='words that must be on the page, e.g. "Landtman Geel"')
    p.add_argument("--n", "--aantal", dest="n", type=int, default=30)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--collection", "--collectie", dest="collection", type=int, default=TK_COLL)
    p.set_defaults(func=cmd_tk_search)
    p = tks.add_parser("page", aliases=["pagina"], help="text + scan of pages")
    p.add_argument("pages", nargs="+", help="<docId>/<page> from the search results")
    out(p)
    p.add_argument("--print", action="store_true", help="also print the text")
    p.add_argument("--no-image", "--zonder-scan", dest="no_image", action="store_true", help="text only")
    p.set_defaults(func=cmd_tk_page)

    # SchiedamGEN
    sg = src.add_parser("schiedam", aliases=["schiedamgen"], help="SchiedamGEN (Schiedam and surroundings)")
    sgs = sg.add_subparsers(dest="cmd", required=True, metavar="command")
    p = sgs.add_parser("search", aliases=["zoek"], help="search people")
    p.add_argument("name", help='first name + surname, e.g. "Jan Groen"')
    p.set_defaults(func=cmd_sg_search)
    p = sgs.add_parser("person", aliases=["persoon"], help="one person")
    p.add_argument("id")
    p.set_defaults(func=cmd_sg_person)
    p = sgs.add_parser("deed", aliases=["akte"], help="one record")
    p.add_argument("id")
    p.set_defaults(func=cmd_sg_deed)

    # Riksarkivet
    p = src.add_parser("riksarkivet", aliases=["zweden", "sweden"], help="Swedish National Archives open API")
    p.add_argument("--name", "--naam", dest="name")
    p.add_argument("--place", "--plaats", dest="place", help="parish, e.g. Åhus")
    p.add_argument("--text", "--tekst", dest="text", help="free text (also finds the archive catalogue)")
    years(p)
    p.add_argument("--n", "--max", "--aantal", dest="n", type=int, default=30)
    p.add_argument("--start", type=int, default=0)
    p.set_defaults(func=cmd_ra)

    # Erfgoed Leiden
    p = src.add_parser("leiden", aliases=["erfgoedleiden"], help="Erfgoed Leiden archive descriptions and scans")
    p.add_argument("terms")
    p.add_argument("--filter", help="only rows whose title or path contains this (e.g. 0440 for Katwijk church books)")
    p.add_argument("--n", "--aantal", dest="n", type=int, default=100)
    p.add_argument("--page", "--pagina", dest="page", type=int, default=0)
    p.add_argument("--scans", type=int, default=0, help="per row, list (or with --out download) up to this many scans")
    out(p, required=False)
    p.set_defaults(func=cmd_leiden)

    a = ap.parse_args(argv)
    try:
        a.func(a)
    except urllib.error.HTTPError as e:
        sys.exit(f"{e.url}: HTTP {e.code}. If this keeps happening the site may be closed to scripts: ask the user.")
    except urllib.error.URLError as e:
        sys.exit(f"Network error: {e.reason}. No network here? (background tasks often have none)")


if __name__ == "__main__":
    main()
