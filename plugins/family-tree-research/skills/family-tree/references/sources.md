# Sources: where to look for what?

## How to reach the archives

You usually have more than one way onto the internet. If one route doesn't work, **don't stop: try the next one yourself**, without waiting for the user to suggest it. A route can fail because a tool is missing or switched off (for example the Chrome extension disabled by the user's organisation, or no browser at all), not because the archive refuses you. Try them in this order:

1. **Fetch/search tools** (WebFetch, WebSearch, or whatever fetch tool you have). They don't need Chrome. Good for record pages, the Open Archives API and Wikipedia.
2. **A shell, if you have one** (Cowork's sandbox, Claude Code's terminal): use `scripts/archives.py` for the archives it knows (see "Searching archives with `scripts/archives.py`" below), or call public APIs directly, e.g. `curl -s "https://api.openarchieven.nl/1.1/records/search.json?name=..."` or Python `urllib`. Its network can be different from the fetch tools', so a site that failed in one may work in the other. A cloud sandbox often only reaches domains on an allowed list; a blocked domain there says nothing about the archive itself.
3. **A browser**: the Chrome extension (Claude in Chrome), or the **browser built into the Claude desktop app** if you have one. The built-in browser runs on the user's own computer, separate from their Chrome, so it often works when Chrome is blocked by their organisation or a site is blocked from the cloud. It only works while the desktop app is open. Use a browser for sites that only work with JavaScript and for scan viewers (e.g. Riksarkivet).
4. **The user**: tell them exactly what to look up (archive, place, period, name) and ask for a screenshot or photo (see research.md).

**A blocked API is not a blocked site.** If an organisation's data API or one URL fails, that says nothing about its normal website. Before you conclude that a source is closed, open the **website itself** in a browser (the built-in one or Chrome) and try its own search, object pages and images. Example: the Rijksmuseum's data API (`data.rijksmuseum.nl`) can be blocked while rijksmuseum.nl works fine in the built-in browser, including the images. The other way round happens too: a site that won't load may have an open API. Only call a source unreachable after trying both, and say which ones you tried.

Tell the user in one short sentence which route you're switching to ("Chrome isn't available here, so I'll fetch the archive directly"). In the progress file, note per site which route works (e.g. "Open Archives: API via fetch works; Chrome blocked by organisation"; "Rijksmuseum: data API blocked, website in built-in browser works"), so a next session starts with the route that works.

Using another tool is fine. Getting around a site's own barrier is not: if a site asks for a **login, a payment or a captcha**, or clearly refuses automated access, don't try to get in another way. Ask the user.

**Sites with a login** (Ancestry, MyHeritage, ArkivDigital): if the user has an account, they can sign in themselves, once, in Chrome or in the built-in browser. The built-in browser keeps its own profile, so they stay signed in there. Never type their password yourself. Without an account: ask for a screenshot.

## Netherlands

| source | what | how |
|---|---|---|
| **Open Archieven** (openarchieven.nl, "Open Archives") | Millions of records from dozens of archives: civil registration (BS) births/marriages/deaths, church registers (DTB), population registers, notarial deeds | Free API: `scripts/archives.py oa`, see below. First choice. |
| **Stadsarchief Amsterdam** (Amsterdam City Archives) | 36 open indexes (CC0) with scans: civil records, population registers, family cards, passport applications and police reports 1940–45, militia registers, notarial deeds, banns before 1811 | `scripts/archives.py saa` and `transkribus`, see below. |
| **SchiedamGEN** (sgen.schiedam.nl) | Schiedam, Kethel, Mathenesse, Nieuwland: births, marriages, deaths, divorces, recognitions | `scripts/archives.py schiedam`, see below. |
| **Erfgoed Leiden** (erfgoedleiden.nl) | Leiden region: archive descriptions, a person index of church records before 1811, scans (e.g. all Katwijk church books, archive 0440) | `scripts/archives.py leiden`, see below. |
| **WieWasWie** (wiewaswie.nl) | National index of civil and church records | Website; search by name, role, place, period. |
| **Archieven.nl** | Search portal of many regional archives, often with scans | Website. May be blocked; then via the user. |
| **Delpher** (delpher.nl) | Newspapers (family announcements, adverts, auctions, news) | Search name + place or address; useful after 1850. Works without a key via SRU: `scripts/delpher.py`, see below. |
| **CBG** (cbg.nl) | Family announcements, personal record cards (died after 1938 and before 1994) | Record cards cost money: only mention them. |
| **Genealogie Online** | Other people's trees | Only as a lead, never as proof. |
| **FamilySearch** | Worldwide indexes and scans | Free account needed; often via the user. |

### Searching archives with `scripts/archives.py`

One script with a subcommand per source, so you don't need a browser for these archives. Python standard library only; it waits politely between requests and slows down when a site says "too many requests". Run it in the foreground (background tasks often have no network) and use `--help` on any subcommand. Dutch names work too (`oa zoek`, `toon`, `schiedam persoon`/`akte`, `transkribus pagina`, `--van`/`--tot`, `--uit`).

| source | what's in it | command | known gaps |
|---|---|---|---|
| **Open Archives** | Index of dozens of archives: civil records, church registers, population registers | `archives.py oa search "Jan Jansen" [--from 1820 --to 1850] [--place] [--type "BS Huwelijk"] [--archive saa]`; `oa show <archive:id>` (everyone with their role, the source); `oa scans <archive:id> --out scans/` | Amsterdam births after c. 1880 (use Transkribus); Schiedam births after 1916 and marriages after c. 1945 (use SchiedamGEN); Katwijk aan Zee baptisms before 1714 (use Erfgoed Leiden); Maassluis is missing. Schiedam records rarely give an occupation |
| **Scans via Open Archives** | Scans that the archive itself passes on to Open Archives. Tested: **The Hague** (`hga`: births, marriages, deaths, population register, notarial), **Rotterdam** (`srt`: part of the civil records, population register, passenger lists), **Utrecht** (`hua`: baptisms, marriages, burials, population register, notarial; often a PDF), Amsterdam (`saa`), Noord-Holland (`nha`), Brabant (`bhi`) | `oa scans <archive:id> --out scans/` fetches every scan of a record at full size. By hand: the links are in `show.json` (not always in the same field); `proxy.archieven.nl/thumb/` → `/download/`, memorix `640x480` → `1920x1080`; the proxy redirects, so follow redirects (`curl -L`). `oa search --scans` only lists records with scans | Utrecht: no scans of the civil records. Rotterdam: not every record has a scan link. Gelders Archief, Groene Hart and Erfgoed Leiden gave no scan links in a sample: the user opens those on the archive's site |
| **Stadsarchief Amsterdam, open data** | All 36 public indexes, with scans | Find the record via `oa search … --archive saa`, then `archives.py saa <uuid or archief.amsterdam/indexen/deeds/… link> --out scans/` (record + scans through the archive's own OAI-PMH service) | Records with restricted access are not there. No name search at the service itself: search via Open Archives |
| **Transkribus, Stadsarchief Amsterdam** | Machine-read full text + scan of Amsterdam civil records, also after 1880 | `archives.py transkribus search "Landtman Geel"` (all words on one page; two surnames find a couple), then `transkribus page <doc/page> --out scans/` (text file + scan) | Not complete: births from c. 1924, marriages after 1940 and deaths after c. 1963 not seen |
| **SchiedamGEN** | Schiedam records, also beyond Open Archives' years: c. 121,000 births, 100,000 marriages, 165,000 deaths | `archives.py schiedam search "Jan Groen"` (first name + surname: a surname alone finds nothing), `schiedam person <id>`, `schiedam deed <id>` | Only the first page of hits. Scans need a login: the user downloads them. Link to a record: `https://sgen.schiedam.nl/?type=CERT&id=<id>` |
| **Riksarkivet** (Sweden), open API | Indexed birth and marriage registers of Skåne, Blekinge and Halland (DDSS; e.g. Åhus births 1706–1894), with godparents, the father's occupation and home, volume and page; plus the archive catalogue | `archives.py riksarkivet --name Hans --place Åhus --from 1750 --to 1753`, or `--text "Åhus kyrkoarkiv"` for the catalogue. No key; [terms of use](https://sok.riksarkivet.se/en/data-api/api/anvandarvillkor-api); only data older than 110 years | No deaths (the death register is only on the search site). Karlshamn not indexed. Church-book scans of e.g. Åhus give 403 |
| **Erfgoed Leiden** | Archive descriptions, a person index (e.g. baptisms before 1811 with child, parents, witnesses) and scans (IIIF) | `archives.py leiden "Maartje Hijg" --scans 1 --out scans/`; `leiden "DTB Katwijk" --filter 0440` for the Katwijk church books | The person index lists names without dates per person: open the record and its scan |

**Read every scan in full yourself.** The machine-read text (Transkribus, OCR) is messy: names come out misspelled, lines in the wrong order, words missing. Use the search text only to find the record; then read the whole scan, all of it (a witness, an occupation or a note in the margin is easy to miss) and transcribe what matters in `data/worklog.md`.

**Closed for scripts** (the user looks these up, or use another route above): the Riksarkivet search site (captcha; births and marriages go via its open API), Matricula scans, FamilySearch, gedbas, the website of the Haags Gemeentearchief (its scans do come through Open Archives), scans of the Utrecht civil records, the SchiedamGEN scans. Don't try to get around a login or captcha.

### Open Archives API by hand

- Search: `https://api.openarchieven.nl/1.1/records/search.json?name=<name>&number_show=50&lang=en`
  - `name` may include a period: `Jan Jansen 1820-1850`.
  - **Two names joined with `&`** finds records in which both appear: `Hendrik Jansen %26 Geesje Smit` (URL-encode `&` as `%26`). Ideal for marriages and for someone's death record via the partner's name.
  - Filters: `eventplace`, `sourcetype` (e.g. `BS Huwelijk` = civil marriage, `BS Geboorte` = civil birth, `BS Overlijden` = civil death, `DTB Dopen` = church baptism), `relationtype`, `archive_code`, `country_code` (nl, be…), `start` (paging).
  - Per result: `personname`, `relationtype`, `eventtype`, `eventdate`, `eventplace`, `archive`, `url`.
- Opening a record: the `url` from the result (it lists everyone in the record with their roles: father, mother, bride, witness…). Use that URL as the source too.
- Max. 4 requests per second: take it easy, no tight loops.
- Coverage differs per region and period. Nothing found doesn't mean it doesn't exist. Then try WieWasWie and the regional archive.

### Delpher (newspapers) via SRU

Delpher's website can be awkward for a script, but the KB's SRU service answers directly, without a key. `scripts/delpher.py` wraps it (`search`, `text`, `locate`, `cut`; run it with `--help`). By hand:

- Search: `https://jsru.kb.nl/sru/sru?version=1.2&operation=searchRetrieve&x-collection=DDD_artikel&recordSchema=ddd&maximumRecords=20&query=<CQL>`, e.g. `"F. Jansen" AND Leiden`, `Jansen AND "Breestraat 12"`, plus `AND date within "1910-01-01 1920-12-31"`. Each record has the date, paper title, page and `ddd:metadataKey` (the article urn, e.g. `MMKB04:000139340:mpeg21:a0065`).
- Text of an article: `http://resolver.kb.nl/resolve?urn=<article urn>:ocr`. The article itself (to cite): `http://resolver.kb.nl/resolve?urn=<article urn>`.
- Page of an article: `ddd:pageurl` in the SRU record (query `metadataKey="<article urn>"`), else the page named most often on the article's Delpher page. Pages are `p` + 3 to 5 digits.
- Page scan (JPEG 2000): `…resolve?urn=<issue urn>:pNNN:image`; word positions (ALTO, pixels of that scan): `…:pNNN:alto`.
- Names, addresses and business names find a lot (adverts, auctions, anniversaries), much more than the civil records say about occupations and shops. OCR misspells: also try one word, or the surname with the street.

### Dutch timeline
- From 1811: civil registration (Burgerlijke Stand, BS). Marriage and death records name the parents.
- Public after: births 100 years, marriages 75 years, deaths 50 years.
- Before 1811: church registers (DTB) per denomination (Dutch Reformed, Roman Catholic, Lutheran, Mennonite…). Patronymics common until ~1811.
- Population registers (c. 1850–1920): whole households with birth dates and places. Gold for completing families.

## Belgium
- **Search.arch.be** (State Archives): parish registers and civil registration, many with scans. Name search can be limited; browsing scans often goes via the user.
- Open Archives also has Belgian sources (`country_code=be`).
- Civil registration from 1796 (French period).

## Germany
- **Matricula** (data.matricula-online.eu): free scans of (mainly Catholic) church books, not searchable by name. Give the user the parish and period.
- **Archion**: Protestant church books, paid → via the user.
- FamilySearch has many German indexes.

## Scandinavia
- **Sweden**: Riksarkivet (free, scans and censuses; births and marriages of Skåne, Blekinge and Halland via its open API: `scripts/archives.py riksarkivet`, see above) and ArkivDigital (paid, best scans). Household examination rolls (husförhörslängder) follow families year by year: ideal. Patronymics (-son/-dotter) until c. 1900. May be blocked; then via the user.
- **Norway**: Digitalarkivet (free, well searchable, censuses 1801/1865/1875/1900/1910).
- **Denmark**: Danish Family Search (censuses), Arkivalieronline/Sa.dk (church books, scans).

## UK and Ireland
- FreeBMD (index of births/marriages/deaths 1837+), FreeREG (parish registers), FreeCEN (censuses). Free.
- GRO (General Register Office) indexes: free account; certificates cost money.
- Ireland: irishgenealogy.ie (civil and church records, free), National Archives of Ireland census 1901/1911.

## United States and Canada
- FamilySearch (free account), FindAGrave (graves, often with relatives), censuses 1850–1950 (free on FamilySearch; the 1950 census also on archives.gov).
- Canada: Library and Archives Canada (censuses), provincial vital records.

## Other
- Indonesia / Dutch East Indies: Open Archives and Delpher (East Indies newspapers); the CBG has an East Indies collection.
- Suriname/Dutch Caribbean: Open Archives (`country_code=sr`), Nationaal Archief (slave registers, emancipation registers 1863).

## Images

Search in this order (see "Finding images (generously)" in SKILL.md for targets, checks and processing). Use search terms per story and place: occupation, place, event, year, in the language of the country.

1. **Rijksmuseum** (Netherlands, also prints of other countries). Linked Art search API: `https://data.rijksmuseum.nl/search/collection?description=<term>&imageAvailable=true` (also `title=`, `creator=`, `type=`). Each hit is an object `https://id.rijksmuseum.nl/<id>`; fetch it with `Accept: application/ld+json` and read the licence there: `publicdomain/mark` or CC0 = free; `rightsstatements.org/vocab/InC` = copyright (skip, often there is no image online anyway). The image itself is on IIIF (`https://iiif.micr.io/<image-id>/full/1400,/0/default.jpg`); follow the object's link to its digital image to get the image id, which is not the object number.
2. **Wikimedia Commons** (everything, all countries). Search files: `https://commons.wikimedia.org/w/api.php?action=query&list=search&srnamespace=6&srsearch=<term>&format=json&srlimit=50`. Then per file `action=query&titles=File:<name>&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=1400&format=json` for licence (`LicenseShortName`), maker (`Artist`) and date (`DateTimeOriginal`). Only PD/CC0, or CC BY(-SA) with the maker's name.
3. **Dutch National Archives** (Nationaal Archief): the Anefo press photos (1945–1989) and the Van de Poll collection are CC0, many also on Commons ("Nationaal Archief", "Anefo", "Collectie Van de Poll").
4. **Regional image banks** (beeldbanken), e.g. Noord-Hollands Archief, Haags Gemeentearchief, Stadsarchief Amsterdam, Erfgoed Leiden, Zeeuws Archief. The licence differs per image: read it per item.
5. **Abroad**: national museums and libraries with open collections (e.g. Nationalmuseum and DigitaltMuseum in Sweden, Deutsche Digitale Bibliothek, Library of Congress, the British Library on Flickr Commons, Europeana as a portal), and Commons. Here too: read the licence per item.

**20th century**: national museums often have little that is free. Look for photographers who died more than 70 years ago (in the Netherlands e.g. Emmy Andriesse, d. 1953), government photo archives released as CC0 (Anefo, Van de Poll) and CC BY-SA collections on Commons (e.g. IISG).

**API blocked?** Then use the museum's website in the browser (see "A blocked API is not a blocked site" above): open a page on the museum's own site, run the search there with `fetch` on the same origin, and save the images as a blob download. One at a time, with about 2.5 seconds between requests; never in parallel. If a download doesn't reach the disk, fall back to a screenshot and crop it. Clean up temporary files and downloads afterwards. As everywhere: no logins, captchas or paywalls, and stop when a site says it doesn't want automated access.

## Reading scans and old handwriting
When the user sends a photo or screenshot: read it yourself. Transcribe the relevant lines literally in `data/worklog.md` (uncertain letters in [square brackets]), translate where needed (Latin, Swedish, German, old Dutch) and name the source. Gothic script and Latin baptism registers are hard: say honestly what you can read with certainty and what you can't.
