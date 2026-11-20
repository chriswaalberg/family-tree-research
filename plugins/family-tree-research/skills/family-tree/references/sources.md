# Sources: where to look for what?

## How to reach the archives

You usually have more than one way onto the internet. If one route doesn't work, **don't stop: try the next one yourself**, without waiting for the user to suggest it. A route can fail because a tool is missing or switched off (for example the Chrome extension disabled by the user's organisation, or no browser at all), not because the archive refuses you. Try them in this order:

1. **Fetch/search tools** (WebFetch, WebSearch, or whatever fetch tool you have). They don't need Chrome. Good for record pages, the Open Archives API and Wikipedia.
2. **A shell, if you have one** (Cowork's sandbox, Claude Code's terminal): call public APIs directly, e.g. `curl -s "https://api.openarchieven.nl/1.1/records/search.json?name=..."` or Python `urllib`. Its network can be different from the fetch tools', so a site that failed in one may work in the other. A cloud sandbox often only reaches domains on an allowed list; a blocked domain there says nothing about the archive itself.
3. **A browser**: the Chrome extension (Claude in Chrome), or the **browser built into the Claude desktop app** if you have one. The built-in browser runs on the user's own computer, separate from their Chrome, so it often works when Chrome is blocked by their organisation or a site is blocked from the cloud. It only works while the desktop app is open. Use a browser for sites that only work with JavaScript and for scan viewers (e.g. Riksarkivet).
4. **The user**: tell them exactly what to look up (archive, place, period, name) and ask for a screenshot or photo (see research.md).

**A blocked API is not a blocked site.** If an organisation's data API or one URL fails, that says nothing about its normal website. Before you conclude that a source is closed, open the **website itself** in a browser (the built-in one or Chrome) and try its own search, object pages and images. Example: the Rijksmuseum's data API (`data.rijksmuseum.nl`) can be blocked while rijksmuseum.nl works fine in the built-in browser, including the images. The other way round happens too: a site that won't load may have an open API. Only call a source unreachable after trying both, and say which ones you tried.

Tell the user in one short sentence which route you're switching to ("Chrome isn't available here, so I'll fetch the archive directly"). In the progress file, note per site which route works (e.g. "Open Archives: API via fetch works; Chrome blocked by organisation"; "Rijksmuseum: data API blocked, website in built-in browser works"), so a next session starts with the route that works.

Using another tool is fine. Getting around a site's own barrier is not: if a site asks for a **login, a payment or a captcha**, or clearly refuses automated access, don't try to get in another way. Ask the user.

**Sites with a login** (Ancestry, MyHeritage, ArkivDigital): if the user has an account, they can sign in themselves, once, in Chrome or in the built-in browser. The built-in browser keeps its own profile, so they stay signed in there. Never type their password yourself. Without an account: ask for a screenshot.

## Netherlands

| source | what | how |
|---|---|---|
| **Open Archieven** (openarchieven.nl, "Open Archives") | Millions of records from dozens of archives: civil registration (BS) births/marriages/deaths, church registers (DTB), population registers, notarial deeds | Free API, see below. First choice. |
| **WieWasWie** (wiewaswie.nl) | National index of civil and church records | Website; search by name, role, place, period. |
| **Archieven.nl** | Search portal of many regional archives, often with scans | Website. May be blocked; then via the user. |
| **Delpher** (delpher.nl) | Newspapers (family announcements, news) | Search name + place; useful after 1850. |
| **CBG** (cbg.nl) | Family announcements, personal record cards (died after 1938 and before 1994) | Record cards cost money: only mention them. |
| **Genealogie Online** | Other people's trees | Only as a lead, never as proof. |
| **FamilySearch** | Worldwide indexes and scans | Free account needed; often via the user. |

### Open Archives API

- Search: `https://api.openarchieven.nl/1.1/records/search.json?name=<name>&number_show=50&lang=en`
  - `name` may include a period: `Jan Jansen 1820-1850`.
  - **Two names joined with `&`** finds records in which both appear: `Hendrik Jansen %26 Geesje Smit` (URL-encode `&` as `%26`). Ideal for marriages and for someone's death record via the partner's name.
  - Filters: `eventplace`, `sourcetype` (e.g. `BS Huwelijk` = civil marriage, `BS Geboorte` = civil birth, `BS Overlijden` = civil death, `DTB Dopen` = church baptism), `relationtype`, `archive_code`, `country_code` (nl, be…), `start` (paging).
  - Per result: `personname`, `relationtype`, `eventtype`, `eventdate`, `eventplace`, `archive`, `url`.
- Opening a record: the `url` from the result (it lists everyone in the record with their roles: father, mother, bride, witness…). Use that URL as the source too.
- Max. 4 requests per second: take it easy, no tight loops.
- Coverage differs per region and period. Nothing found doesn't mean it doesn't exist. Then try WieWasWie and the regional archive.

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
- **Sweden**: Riksarkivet (free, scans and censuses) and ArkivDigital (paid, best scans). Household examination rolls (husförhörslängder) follow families year by year: ideal. Patronymics (-son/-dotter) until c. 1900. May be blocked; then via the user.
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

## Reading scans and old handwriting
When the user sends a photo or screenshot: read it yourself. Transcribe the relevant lines literally in `data/worklog.md` (uncertain letters in [square brackets]), translate where needed (Latin, Swedish, German, old Dutch) and name the source. Gothic script and Latin baptism registers are hard: say honestly what you can read with certainty and what you can't.
