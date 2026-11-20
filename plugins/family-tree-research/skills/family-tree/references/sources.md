# Sources: where to look for what?

Try yourself first (WebFetch/WebSearch, or the browser if available). If a site doesn't work (blocked, login, paywall), don't try to get in through workarounds. Ask the user specifically for a screenshot (see research.md). Note in the progress file which sites work and which don't, so you don't retry every session.

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
