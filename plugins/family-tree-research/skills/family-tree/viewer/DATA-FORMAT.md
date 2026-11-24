# data.json for the family-tree viewer (format v2)

The viewer (`index.html`) contains nothing about a specific family. Everything comes from `data.json`, which sits next to `index.html`. Build the file from a GEDCOM with `scripts/make_viewer_data.py`, or write it yourself.

```
python3 make_viewer_data.py tree.ged data.json                       # minimal
python3 make_viewer_data.py tree.ged data.json --start @I1@:Femke \
        --csv relations.csv --regions regions.json --title "The De Vries family" --lang en
```

> **Field names are Dutch.** The format was born in Dutch and the field names (`personen`, `taal`, `verhaal`, …) are kept stable for compatibility. This document explains every field in English. Values that are shown to readers (titles, stories, region names) can be plain text or `{"en": …, "nl": …}`.

## Top level

| Field | Type | Required | Meaning |
|---|---|---|---|
| `versie` | number | yes | Always `2`. Without it the viewer treats the file as the old format (v1). |
| `personen` | list | yes | All people (see below). References between people are **positions in this list** (0, 1, 2 …). |
| `taal` | `"en"` or `"nl"` | no | Language the viewer opens in. Default `"en"`. (`lang` also works.) Readers can switch with the EN/NL switch in the header; their choice is remembered per browser (localStorage). `?lang=en` or `?lang=nl` in the URL overrides both. |
| `titel` | text or `{"en": …, "nl": …}` | no | No longer shown. The title is always "Family tree of {start person}" / "Stamboom van {startpersoon}", because it depends on who you are looking at. Kept so older files still load. |
| `bijgewerkt` | `"YYYY-MM-DDTHH:MM"` or `"YYYY-MM-DD"` | no | When the tree was last updated. The viewer shows it small in the footer, under "Made with…": "Last updated: 22 November 2026, 2:35 pm" / "Laatst bijgewerkt: 22 november 2026, 14:35"; a date without a time shows without one. Missing or not valid: nothing is shown. `make_viewer_data.py` writes the moment of the build (local time); `--updated 2026-11-01` or `--updated 2026-11-01T09:00` sets another, `--updated none` leaves it out. (`updated` also works.) |
| `familienaam` | text | no | Family name. No longer shown (see `titel`). |
| `startpersonen` | list | no | Each item: `{"persoon": 0, "label": "Femke"}` (`label` optional, defaults to the first name). The first one is the start person when the viewer opens. The reader picks another start person by clicking the name in the title (it lists these start people and a search), or via "Make start person" in a person's details. The viewer remembers that choice per browser and per tree (localStorage, by GEDCOM `id`) and opens there next time, in every view; a link to a person (`#story/I4`) still wins. Without the list the viewer starts at person 0. |
| `startpersoon_per_weergave` | object | no | A different start person for one view, e.g. `{"stamlijn": 2}` (only until the reader picks a start person themselves). Views: `familie` (Family), `stamlijn` (Line), `verhaal` (Story), `tijdlijn` (Timeline), `waaier` (Fan), `kosmos` (Cosmos). |
| `levenden_tonen` | yes/no | no | Default (missing or `true`): the viewer shows everything. `false` hides dates and places of living people. |
| `regios` | object | no | Region codes: `{code: {"naam": …, "kleur": "#hex"}}` (`naam` = name, `kleur` = colour). `naam` can be text or `{"en": …, "nl": …}`. Use a country or country-region code (`NL`, `NL-ZH`, `BE-VAN`, `SE-M`). The viewer colours by **country of birth**: it takes the part before the hyphen (`NL-ZH` → `NL`). For well-known countries (NL, BE, DE, SE, NO, DK, FR, GB, US, ID) the viewer has its own names and colours; for other codes it uses `naam` and `kleur` from this table. |
| `plaatsen` | object | no | Place → region code, for people without `r`. Keys are compared without capitals and accents; first the whole place name, then each comma-separated part (`"Leiden, Zuid-Holland, Nederland"` → `leiden`, `zuid-holland`, `nederland`). |
| `tijdgeest` | object | no | Life and times per place (see "Zeitgeist" below). |
| `coordinaten` | object | no | Coordinates for the maps: `{place: [lat, lon, precision]}`, e.g. `"Åhus, Skåne, Zweden": [55.9235, 14.2955, "plaats"]`. Keys are the place names exactly as in `bplac`, `dplac`, `woon` and `verhaal_plekken`. Precision: `plaats` (town or village: a pin), `regio` (province, county, state) or `land` (country): then the map says the exact spot is unknown and shows no pin. Made by `make_viewer_data.py --coords` from the file of `geocode_places.py` (see "Coordinates" below); places without coordinates are left out. |
| `landkaart` | object | no | The base map for the maps, made by `make_viewer_data.py --coords` from Natural Earth (public domain, `scripts/geo/natural-earth.json`): `fijn` = detailed coastlines, lakes and land borders, cut into cells of `cel` degrees around the places (`{"x,y": {"l": land, "lk": coast, "m": lakes, "mk": lake shores, "g": borders, "r": rivers}}`; an empty cell is sea), `grof` = the whole world, coarse (`land`, `meren`, `grenzen`, and `rivieren` with scalerank ≤ 6 near the places), for overviews, routes and the globe. A river line starts with its Natural Earth scalerank: `[rank, x0, y0, dx1, …]`; rivers are drawn quietly (a soft bed with a thin line) on detail and route maps, without names. Rings are delta-encoded integers in 1/`q` degree. Maps up to `fijn_max_km` wide use `fijn`. Don't edit by hand. |

Without a region code the viewer also recognises the country from the last part of the birth or death place (`…, Sweden`). A place that matches nothing gets the "Unknown" colour. It never throws an error.

## Person

| Field | Type | Required | Meaning |
|---|---|---|---|
| `n` | text | yes | Full name. |
| `g` | text | no | Given names. The first one is shown on the cards. |
| `s` | text | no | Surname (including prefixes like "van", "de"). |
| `x` | `"M"` / `"F"` | no | Sex. |
| `f`, `m` | number | no | Position of father / mother, or `-1` if unknown. |
| `ch` | list of numbers | no | Children. |
| `sp` | list of numbers | no | Partners. |
| `bdate`, `bplac` | text | no | Birth (or baptism) date and place, as in the GEDCOM. |
| `ddate`, `dplac` | text | no | Death (or burial). |
| `by`, `dy` | number | no | Birth and death year (for the timeline and sorting). |
| `r` | text | no | Region code (key in `regios`). If missing, the viewer looks the place up in `plaatsen`. |
| `levend` | yes/no | no | Living person. Informational only; with `"levenden_tonen": false` the viewer shows the name with "Living", without dates and places. |
| `c` | object | no | Certainty of the relation to the parents: `{"f": [status, source, note], "m": [...]}`. The note is the reason the status holds: for `zeker`, `waarschijnlijk`, `mogelijk` and `fout` the person cards show it under a heading ("Why certain:" / "Waarom zeker:"), with the source as a link below; for the other statuses source and note are shown plainly. An optional fourth element gives the kind of relation: `"aangenomen"` (raised as their own child), `"adoptie"` (adoption) or `"pleeg"` (foster); default is biological. The viewer then shows e.g. "raised as their own child" and the Story view explains that this parent was not the biological parent. |
| `id` | text | no | Original GEDCOM id (e.g. `I12`), informational only. |
| `beroep` | list of text | no | Occupations, literally from the GEDCOM (`1 OCCU`), in GEDCOM order: `["timmerman", "bewaker"]`. Shown in the person's details and in the Story text: "He worked as timmerman, later bewaker." / "Hij was timmerman, later bewaker." Left out for living people with `--hide-living`. |
| `woon` | list | no | Where and when the person provably lived: `[["Rotterdam, Zuid-Holland, Nederland", 1859, 1864], ["Amsterdam, Noord-Holland, Nederland", 1874, 1911]]` (place, from, to). Made by `make_viewer_data.py` from every dated place: birth/baptism, `RESI` and other own events, marriages, the births of their children, death. Records in a row in the same place form one period, widened by 5 years but never past halfway to a record elsewhere, never before birth or after death. A 4th element marks a period abroad: `["Toronto, Ontario, Canada", 1958, 1963, "CA"]`. The zeitgeist uses it (see "Zeitgeist"). Left out for living people with `--hide-living`. |
| `bronnen` | list | no | The person's own sources, from the GEDCOM's `SOUR` citations on the person and on their events: `[["Netherlands, Death Index — Gemeentearchief Oegstgeest", "https://…"], ["Marriage Woubrugge 1813"]]` (text, optional link). Text = the source's title (not a round title from `rebuild`) and the citation's `PAGE`; link = `WWW`, else an Ancestry record link made from `_APID`. Duplicates left out. Shown in Story under the person block and on the person cards (one as "Source: …", more folded as "Sources (n)"). Left out for living people with `--hide-living`. |
| `woon_feiten` | list | no | What happened where, so a map can say why someone was there: `[[1794, "Rotterdam, Zuid-Holland, Nederland", "huwelijk", "", 20]]` (year, place, kind, extra, partner). Kinds: `doop`, `woonde` (RESI), `volkstelling`, `beroep` (extra = the occupation), `school`, `emigratie`, `immigratie`, `naturalisatie`, `gebeurtenis` (extra = the EVEN type), `huwelijk`, `ondertrouw`, `verloving`, `scheiding` (5th element: the partner's index in `personen`). A 6th element holds the GEDCOM date when it is not a plain date (`[2000, "Zwolle, Overijssel, Nederland", "woonde", "", null, "ABT 2000"]`; also `BEF`, `AFT`, `BET … AND …`, `FROM … TO …`), and for an event (`gebeurtenis`) or residence (`woonde`) whose date has a month (`MAY 1957`, so the map sentence of an event says "In May 1957 he was in … (sports day)" and a journey lists its places in date order; a residence sentence keeps only the year); the year is then the last year in it. The viewer turns it into words ("Around 2000 he lived in …", "From the 1970s he lived in … (until around 2000), where … were born"). Birth, death and the children's births are not repeated here (the viewer has them). Made by `make_viewer_data.py`; left out for living people with `--hide-living`. |
| `weg` | list | no | Periods abroad: `[[1952, 1978, "AU"]]` (from, to, country: a code like `AU`, or the last part of the place name). Made by `make_viewer_data.py`. From = the earliest possible year of an `EMIG`, an `IMMI` or `RESI` abroad, or an `EVEN` with `TYPE` Emigratie/Emigration (`AFT 1952` → 1952, `BET 1950 AND 1955` → 1950). To = the first later dated fact in the home country (a `RESI`, `OCCU` or other event with a place, a marriage, a child born there, an `IMMI` back, death); nothing: the year of death (`null` when unknown). The home country is the country with the most dated facts (a tie: the birth country), so for someone who emigrated for good and stayed, the new country is home. In those years the viewer shows no zeitgeist (life, events, images, national events) of the home country. Left out with `--hide-living`. |
| `media` | list | no | Photos and documents, see below. |
| `toegevoegd` | list | no | When this person came into the tree, for the **List** view: `[when, kind, text, order]`. `when` = `"2026-11-23"` or `"2026-11-23 14:35"`; `kind` = `"r"` (a research round: `text` is the round's title, `order` = round × 100000 + step, so steps of one day keep their order) or `"g"` (a date the family tree program wrote, e.g. MyHeritage `_CREA`). From GEDCOM `_CREA` (written by `gedcom_tool.py rebuild` for everyone a round added). Missing = in the original tree. |
| `gewijzigd` | list | no | The last change to this person, same shape as `toegevoegd`, with two more kinds: `"v"` (their own story, from `bijgewerkt`/`updated` in stories.json) and `"m"` (a photo or document, from the `added` column of media.csv; `text` = its title). The latest of: the last round step that named this person (GEDCOM `CHAN`, written by `rebuild`; `_UPD`/`CHAN` of other programs work too), their story, their media. |
| `verhaal`, `verhaal_bronnen`, `verhaal_beelden` | | no | Own story, see "Stories" below. |

### Other names (`aka`)

`aka`: list of other names the person was known by, e.g. `["Jopie"]`. Made by `make_viewer_data.py` from a `NICK` under any `NAME` and from every `NAME` after the first (`2 TYPE aka`, a married name, …); with the same surname only the first names are kept, with another surname the whole name. Search finds people by these names too, and the viewer shows them after the name: "Johanna Maria Elisabeth Jansen (Jopie)".

### Photos and documents (`media`)

A media item can carry `toegevoegd` (`"2026-11-24 09:15"`): when it was added (media.csv column `added`/`toegevoegd` → GEDCOM `2 _CREA` under the OBJE). It counts as a change of the person in the List view.

Each item: `{"bestand": "media/grandma-1950.jpg", "titel": "Grandma Riet, 1950", "soort": "foto"}` (`bestand` = file, `titel` = caption, `soort` = kind). Only `bestand` is required (a plain string also works).

- `bestand`: path next to `index.html` (e.g. `media/…`), an `https://` address or a `data:` URL.
- `titel`: caption. Without it the viewer shows the file name.
- `portret`: `true` for the person's portrait (made by `make_viewer_data.py` from `_PRIM Y` under the `OBJE`, which Ancestry, Family Tree Maker and RootsMagic also write, or from the `portrait` column of media.csv). The Story view shows the portrait as a polaroid at the top right of the person's block (above the name on phones), with `titel` as its caption; Cards uses it on the intro card. Without `portret` the first `foto` is the portrait. Other photos and documents stay small thumbnails.
- `soort`: `foto` (photo), `scan` or `document`. It decides how ▶ Swipe shows the item: only a `foto` becomes the portrait on a person's first card; a `scan`, `document` or item without `soort` is never used as a picture there, only as a small "view document" button that opens it large. Elsewhere `soort` is informational.

Images (`.jpg`, `.png`, `.gif`, `.webp`, …) appear as thumbnails in the detail panel; a click opens them large, with arrows to the next one. Other files (e.g. `.pdf`) appear as a link. For a living person with `"levenden_tonen": false` the viewer shows no media.

The script takes them from the GEDCOM: every `OBJE` under a person (also under an event, or as a reference to a separate `0 @O1@ OBJE` record), with `FILE` and `TITL`.

### Certainty statuses

| English | Dutch (stored) |
|---|---|
| `certain` | `zeker` |
| `probable` | `waarschijnlijk` |
| `possible` | `mogelijk` |
| `unknown` | `onbekend` |
| `error` / `wrong` | `fout` |
| `not checked` | `niet gecheckt` |

Both are accepted everywhere; the script stores the Dutch value and the viewer shows the label in the viewer language.

## Certainty CSV (optional, for the script)

Delimiter `,` `;` or tab. Column names may be English or Dutch:

| Column | Meaning |
|---|---|
| `child_id` / `kind_id` (or `child` / `kind`) | GEDCOM id (`@I3@` or `I3`), or a name with optional birth year: `Thomas de Vries (1984)` |
| `parent_id` / `ouder_id` (or `parent` / `ouder`) | same, for the father or mother |
| `status` / `certainty` / `zekerheid` | one of the statuses above |
| `source` / `bron` | free text; links become clickable |
| `note` / `notes` / `opmerking` (or `why` / `waarom`, which wins when both are there) | why the status holds, in one plain sentence: which record, place and year, who is named as parent; for probable/possible also what's missing. The script warns about certain/probable/possible links without a source or with a reason under 25 characters |
| `type` / `relation` / `soort` | optional: `biological` (default), `raised` (raised as their own child), `adopted`, `foster` — or the Dutch `biologisch`, `aangenomen`, `adoptie`, `pleeg` |

Relations not in the CSV, or all relations when there is no CSV, get `not checked`.

## Region table (optional, for the script)

```json
{
  "regios": {"NL-ZH": {"naam": {"en": "South Holland", "nl": "Zuid-Holland"}, "kleur": "#e07a2f"}},
  "plaatsen": {"Leiden": "NL-ZH", "Den Haag": "NL-ZH"}
}
```

Without a region table the script recognises a number of countries from the last part of the place name (Netherlands, Belgium, Germany, Sweden, Norway, Denmark, France, United Kingdom, United States, Indonesia — in English, Dutch and the local language) and colours per country. `examples/regions-basic.json` is a starting point.

## Copying media (script option)

`--media-dir viewer/media` copies all local files referenced in the GEDCOM into that folder under a safe name (photos larger than 2000 px or 1.5 MB are shrunk to JPEG if Pillow is available; `--media-max 0` turns that off), and writes `media/<name>` into data.json. Publish them as `media/<name>` next to index.html. Relative paths in the GEDCOM (e.g. `scans/record.jpg`) are looked up from the GEDCOM's folder and the folder above, or from `--media-base`. `https://` addresses are left as they are. Without `--media-dir` the paths go into data.json unchanged.

## Living people (rule in the script)

Someone counts as living if no death or burial is recorded and they were born less than 100 years ago. If the birth year is missing, the script estimates it from parents (+27), children (−30) or partners. The script writes all data; `--hide-living` leaves out dates and places of living people. Change the limit with `--living-years 110`.

## Minimal example

```json
{
  "versie": 2,
  "taal": "en",
  "familienaam": "de Vries",
  "startpersonen": [{"persoon": 0, "label": "Femke"}],
  "regios": {"NL": {"naam": {"en": "Netherlands", "nl": "Nederland"}, "kleur": "#e07a2f"}},
  "personen": [
    {"n": "Femke Johanna de Vries", "g": "Femke Johanna", "s": "de Vries", "x": "F", "f": 1, "m": 2, "levend": true,
     "c": {"f": ["zeker", "Birth certificate 2015", ""], "m": ["zeker", "Birth certificate 2015", ""]}},
    {"n": "Thomas de Vries", "g": "Thomas", "s": "de Vries", "x": "M", "f": 3, "m": 4, "sp": [2], "ch": [0], "levend": true},
    {"n": "Sanne", "g": "Sanne", "x": "F", "sp": [1], "ch": [0], "levend": true},
    {"n": "Pieter Johannes de Vries", "g": "Pieter Johannes", "s": "de Vries", "x": "M",
     "bdate": "3 JAN 1948", "bplac": "Den Helder, Noord-Holland, Nederland", "by": 1948,
     "ddate": "17 AUG 2019", "dy": 2019, "r": "NL", "sp": [4], "ch": [1]},
    {"n": "Anna Lindqvist", "g": "Anna", "s": "Lindqvist", "x": "F", "by": 1925, "sp": [3], "ch": [1]}
  ]
}
```

`examples/example-data.json` is a complete version with 7 people (start person, parents, grandparents), made with:

```
python3 make_viewer_data.py examples/example.ged examples/example-data.json \
  --csv examples/example-relations.csv --regions examples/regions-basic.json --start @I1@:Femke --start @I2@:Thomas
```

## Stories (`verhaal`, for the Story view)

The Story view takes the reader from the start person back in time, step by step. At every person the reader chooses father or mother; if only one parent is known, the story simply continues. The **richest trail** (gold star, and the "Follow the richest trail" button) adds up per step what is known about that person (dates, places, own story +8, sibling with a story +6), weighted by the certainty of the relation (certain 1 · probable 0.8 · possible 0.5 · not checked 0.45 · unknown 0.35 · error doesn't count). When certainty drops compared to the previous step, the story says so.

For most people the viewer writes a text from the data (birth, age at the child's birth, family, moves, death, zeitgeist). When someone has more to tell, give them their own story:

| Field | Type | Meaning |
|---|---|---|
| `verhaal` | text or `{"en": …, "nl": …}` | Replaces the template text. Blank line = new paragraph; `**bold**`, `*italic*` and `[text](https://…)` work. |
| `verhaal_kaarten` | text or `{"en": …, "nl": …}` | Optional short version for the Cards view (input key `kaarten` or `cards`). Blank line = new card. When present, Cards uses it instead of `verhaal`; the Story view always uses `verhaal`. Card 1 is a hook (no year or age): Cards always shows it right after the intro card. The other cards get a year like paragraphs do (first year in the card, else an age, else between their neighbours). Same number of cards in every language. |
| `verhaal_bronnen` | list | Sources: `[["title", "https://…"], …]`, shown under the story. |
| `verhaal_beelden` | list | Old images with the story: `[{"bestand": "media/verhalen/x.jpg", "titel": …, "maker": …, "datering": …, "bijschrift": …, "bron": ["title", "https://…"]}]` (`maker` = artist, `datering` = dating, `bijschrift` = caption, `bron` = source). Optional `soort` as with zeitgeist images (`foto`, `tekening`, …, `krant` for a newspaper clipping). Optional `alinea` (paragraph, 1-based): the image comes right after that paragraph, in the Story view between it and the next one and in Cards as the card after it. Without `alinea` the viewer places it after the paragraph that mentions the year from `datering` or a clear word from the title or caption, and otherwise spreads the images evenly over the story. Rule: every story image fits a moment in the story (same place, within ~15 years) and has an `alinea`; `make_viewer_data.py` warns (no error) when the year in `datering` lies outside (birth − 10) to (death + 10), or when `alinea` is missing or the paragraph doesn't exist. Optional `stond_er_al` (English input also: `built`, `standing_since`): the year a building in the image was built, for a later image of a building that still stood the same way in their time (a 1916 photo of a church from 1653), or for a later drawing of something that already existed then (a coat of arms). It turns the dating warning off; the script still warns if that year is after death + 10. Say it in the caption too. Optional `scan`: for a cropped clipping (`soort: "krant"`), the full scan as it hangs in the tree: the path from the GEDCOM `OBJE`/`FILE` (or media.csv), e.g. `"scan": "scans/1958-08-22 Weekly - … .jpg"`. `make_viewer_data.py` turns it into the same `media/<name>` that `--media-dir` makes for that file, and warns when it is not one of this person's media. The viewer then leaves that scan out of the document buttons in Story and Cards (the person sheet keeps it), and a tap on the clipping opens the clipping and then the full scan. Optional `kaart` (English input also: `card`; 1-based): after which card of `verhaal_kaarten` the image comes in Cards. Without `kaart` Cards falls back to `alinea`; `make_viewer_data.py` warns when a story has cards and an image has no `kaart` or one that doesn't exist. |

| `verhaal_plekken` | list | Places the story points at, for its map (input key `plekken` or `places`): `[{"plaats": "Ahuys", "alinea": 1, "kaart": 1}]` (`plaats` = place, `alinea` = paragraph, `kaart` = card of `verhaal_kaarten`, both 1-based like story images; optional `jaar` (year) and `bijschrift` (caption, text or `{"en": …, "nl": …}`)). Every map gets a sentence that says why: with a `bijschrift` that is the caption, under the map in Story and in Cards (the place to say what is uncertain: "Probably his birthplace."); without one, "Around {jaar} the story takes place in {place}", or without `jaar` "Part of the story takes place in {place}". Use it for a place the story mentions that is not a birth place or home in the tree (a port someone sailed from, a town abroad). Every `plaats` needs coordinates (see "Coordinates"). Plain strings work too: `"plekken": ["Ahuys"]`. |
| `verzamelkaart` | `false` | Only when a story turns the journey map off (input key `verzamelkaart` or `journey_map`, value `false`): Cards then shows one map per place abroad, as before. |

A sibling with their own story appears as "Remarkable relative" with the ancestor on the trail.

Give every story `"bijgewerkt": "2026-11-23 14:35"` (or `updated`) when you write or change it: the List view counts it as the person's last change.

With the script: `--stories stories.json`, keyed by GEDCOM id (`@I12@`) or full name. English keys (`text`, `cards`, `sources`, `images`) and Dutch keys (`tekst`, `kaarten`, `bronnen`, `beelden`) both work. `make_viewer_data.py` warns (no error) when cards differ in number per language, a card has more than 250 characters, card 1 has a year or age, an image has no or a wrong `kaart`, or a story without cards has a paragraph over 350 characters:

```json
{"@I12@": {"text": {"en": "…", "nl": "…"},
           "cards": {"en": "A hook without a year.\n\nIn 1781 …", "nl": "Een haak zonder jaartal.\n\nIn 1781 …"},
           "sources": [["Marriage record Katwijk 1781", "https://…"], ["Museum X", "https://…"]],
           "images": [
             {"bestand": "media/verhalen/katwijk-bomschuiten-1780.jpg", "soort": "prent",
              "titel": "Fishing boats on the beach at Katwijk", "maker": "…", "datering": "c. 1780",
              "bijschrift": {"en": "This is how the boats he sailed on were pulled onto the beach.", "nl": "Zo werden de schepen waarop hij voer het strand op getrokken."},
              "bron": ["Rijksmuseum", "https://id.rijksmuseum.nl/…"]},
             {"bestand": "media/verhalen/oude-kerk-katwijk.jpg", "soort": "tekening",
              "titel": "The Old Church at Katwijk aan Zee", "maker": "…", "datering": "1790",
              "bijschrift": {"en": "The church where he married in 1781.", "nl": "De kerk waar hij in 1781 trouwde."},
              "bron": ["Rijksmuseum", "https://id.rijksmuseum.nl/…"]},
             {"bestand": "media/verhalen/storm-1775.jpg", "soort": "prent",
              "titel": "Storm on the Dutch coast", "maker": "…", "datering": "1775",
              "bijschrift": {"en": "A storm like the one in which his brother drowned. This is Scheveningen, not Katwijk itself.", "nl": "Een storm zoals die waarin zijn broer verdronk. Dit is Scheveningen, niet Katwijk zelf."},
              "bron": ["Wikimedia Commons, public domain", "https://commons.wikimedia.org/wiki/File:…"], "alinea": 3, "kaart": 4},
             {"bestand": "media/verhalen/krant-1781-huwelijk.jpg", "soort": "krant", "alinea": 2, "kaart": 2,
              "titel": "Marriage announcement", "maker": "Leydse Courant", "datering": "5 May 1781",
              "bijschrift": {"en": "The announcement of his marriage (shortened: only the heading and his notice).", "nl": "De aankondiging van zijn huwelijk (ingekort: alleen de kop en zijn bericht)."},
              "bron": ["Delpher", "https://www.delpher.nl/…"]}]},
 "Pieter de Vries": "Short text without sources."}
```

## Zeitgeist (`tijdgeest`, for the Story view)

Optional top-level field. Per place it paints a picture of how people lived there. In the Story view it appears for everyone who lived in that place, but only for the years they provably lived there (`woon`, see above; not just birth or death place, never after death), and not in years abroad (`weg`). Someone born in Rotterdam in 1859 who lived in Amsterdam from about 1865 gets no Rotterdam images or events from 1883.

- **`leven`** (daily life): one or more paragraphs about daily life in a period. Shown with the first person on the trail whose time in that place (midpoint of the `woon` period) falls in that period, and not again after that. Optional `kaarten` (input also `cards`; text or `{"en": …, "nl": …}`, blank line = new card): the short version for Cards, each card with the block's heading; the Story view always shows `tekst`. Without `kaarten`, Cards makes one card per paragraph of `tekst`. Card 1 is a hook; then one picture of daily life per card, at most ~200 characters. A card that starts with a year (at most three words before it: "In 1881 …", "Around 1880 …", "On 14 May 1940 …") is only shown in Cards to someone whose life (birth − 10 to death) includes that year; "after/from/since 1880" (`na`, `vanaf`, `sinds`) means from then on, "until/before 1806" (`tot`, `voor`) up to then. A card without a year at the front is about the whole period and is always shown; a year further on in the card doesn't count. The script warns when a front year falls outside the block's `van`–`tot`. `make_viewer_data.py` warns when a card has more than 250 characters, or when a block without `kaarten` has a paragraph over 350 characters.
- **`beelden`** (images): old prints, drawings, paintings or photos. Per person the image closest in year to their life that hasn't been shown yet. Click = large.
- **`gebeurtenissen`** (events): local events with year and source. Shown for people who lived there then and were at least 6 years old, each once per story, at most 4 local ones per person. A national event from the same year as a local one is left out (no double "1944"). Cards show at most 3 of them per person: those with the highest optional `gewicht` (input also `weight`; a number, higher = more important, default 0) first, then events in their own place, then war years; the Story view shows all. An event within 5 years of a "lived through" card (a war) joins that card.
  - Optional `"links": [["title", "https://…"], …]` with `"links_label": "…"`: links shown under the event, e.g. to images you may not copy (copyright). Only link to pages where the image can actually be seen.
- **`algemeen.gebeurtenissen`** (general events): national events, at most 1 per person.

```json
{"tijdgeest": {
  "plaatsen": [{
    "id": "katwijk", "naam": "Katwijk", "match": ["katwijk"],
    "leven": [{"van": 1625, "tot": 1800, "titel": "Life in Katwijk aan Zee", "tekst": "… (blank line = new paragraph)",
               "kaarten": "A hook about daily life.\n\nOne picture per card, ~200 characters."}],
    "gebeurtenissen": [{"jaar": 1570, "tekst": "…", "bron": ["title", "https://…"]},
                       {"jaar": 1775, "van": 1771, "tot": 1780, "tekst": "In the 1770s …"}],
    "beelden": [
      {"bestand": "media/tijdgeest/katwijk-strand-1660.jpg", "van": 1620, "tot": 1720, "jaar": 1660, "soort": "schilderij",
       "titel": "Beach at Katwijk", "maker": "…", "datering": "c. 1650-1670",
       "bijschrift": "…", "bron": ["Rijksmuseum", "https://id.rijksmuseum.nl/…"]},
      {"bestand": "media/tijdgeest/katwijk-walvis-1598.jpg", "van": 1598, "tot": 1598, "jaar": 1598, "soort": "prent",
       "gebeurtenis": true, "titel": "Whale stranded near Katwijk, 1598", "maker": "…", "datering": "1598",
       "bijschrift": "…", "bron": ["Rijksmuseum", "https://id.rijksmuseum.nl/…"]},
      {"bestand": "media/tijdgeest/katwijk-sluis-1807.jpg", "van": 1790, "tot": 1830, "jaar": 1807, "soort": "tekening",
       "titel": "Laying the first stone of the sluice", "maker": "…", "datering": "1804",
       "bijschrift": "…", "bron": ["Rijksmuseum", "https://id.rijksmuseum.nl/…"]},
      {"bestand": "media/tijdgeest/katwijk-vissersvrouwen-1870.jpg", "van": 1850, "tot": 1900, "jaar": 1870, "soort": "prent",
       "titel": "Fishermen's wives waiting on the beach", "maker": "…", "datering": "c. 1870",
       "bijschrift": "…", "bron": ["Rijksmuseum", "https://id.rijksmuseum.nl/…"]},
      {"bestand": "media/tijdgeest/katwijk-school-1925.jpg", "van": 1910, "tot": 1940, "jaar": 1925, "soort": "foto",
       "kind": true, "titel": "Schoolchildren in Katwijk", "maker": "…", "datering": "1925",
       "bijschrift": "…", "bron": ["Wikimedia Commons, CC0", "https://commons.wikimedia.org/wiki/File:…"]}]
  }],
  "algemeen": {"naam": "Netherlands", "gebeurtenissen": [{"jaar": 1811, "tekst": "…", "bron": ["…", "https://…"]}]}
}}
```

Field names: `plaatsen` = places, `naam` = name, `van`/`tot` = from/to year, `jaar` = year, `titel` = title, `tekst` = text, `bron` = source, `algemeen` = general.

- Images are spread over the whole trail: each image goes to someone who lived in that place in the image's year (`jaar`, else the middle of `van`–`tot`) and whose mid-life is closest to it (first one per person, then at most two). Nobody on the trail lived there then: the image is not shown on that trail. Set `"gebeurtenis": true` on an image of a specific event (a sea battle, a stranded whale); it only appears for people alive at the time. Also set `"kind": true` on an image about children (children in a famine, at school): it only goes to someone on the trail who was younger than 16 at the time (at most two per person). If nobody on the trail was a child then, the image is not shown on that trail.
- `soort` on an image (kind): `foto`, `tekening`, `prent`, `schilderij`, `kaart`, `munt`, `affiche` or `krant` (newspaper clipping) (English also works in the input: photo, drawing, print, painting, map, coin, poster, newspaper; `make_viewer_data.py` stores the Dutch value). The Story view and Cards show it above the image: "A drawing from that time" / "Een tekening uit die tijd", "From the newspaper" / "Uit de krant"; without `soort`: "An image from that time". Not to be confused with `kind`, the flag for images about children. In Cards, `krant`, `scan`, `document` and `kaart` are shown whole (not cropped) on a paper colour with the caption below, for about 12 seconds; the card scrolls when the image is tall.
- `match`: text fragments that must occur in a place from `woon` (without capitals and accents). A data.json without `woon` (made by an older script) falls back to birth and death place for the whole life.
- Lifespan: birth year to death year; without a death year the viewer assumes 60 years.
- Texts can also be `{"en": …, "nl": …}`. Publish images as `media/tijdgeest/<name>` next to index.html. Only use images that are free to use (public domain or CC0), and credit artist and source.
- With the script: `--zeitgeist zeitgeist.json`.

## Coordinates (script input, for the maps)

`scripts/geocode_places.py tree.ged data/place-coords.json [--stories data/stories.json]` collects every place in the GEDCOM (and the `plekken` of the stories) and looks up the missing ones with OpenStreetMap's Nominatim, one per second. The file is a cache and can be edited by hand:

```json
{
  "Åhus, Skåne, Zweden": {"lat": 55.9235, "lon": 14.2955, "precisie": "plaats", "bron": "nominatim: Åhus, Kristianstads kommun, Skåne County, Sweden"},
  "Ahuys": {"lat": 55.9235, "lon": 14.2955, "precisie": "plaats", "bron": "manual: old spelling of Åhus"},
  "Australie": {"lat": -24.78, "lon": 134.76, "precisie": "land", "bron": "nominatim: Australia"}
}
```

- `precisie` (precision): `plaats`, `regio`, `land`, or `onbekend` (not found; looked up again only with `--retry`). English keys `precision`/`source` are read too.
- An entry whose `bron` (source) does not start with `nominatim` is a manual correction: the script never changes it, not even with `--refresh`.
- `"controleren": true` (check): the result lies in another country than the name ends with, the name had no country, only a broader name was found, or the hit is a street, road or building (Nominatim sometimes picks a street named after a village). Check these by hand.
- Names like `Ndg` or `unknown` are skipped. The request only names the plugin, never the user or the people in the tree. Coordinates from Nominatim: © OpenStreetMap contributors (ODbL).

`make_viewer_data.py --coords data/place-coords.json` puts the coordinates of the places that are used into `coordinaten`, and warns about places without coordinates. Names are matched exactly first, then without capitals and accents; a short name without a comma in a story ("Amersfoort") matches the one place that starts with it.

**What the viewer does with them.** One map at every moment a place is new on the trail (the people shown so far; the same place = the same core name, so Katwijk, Katwijk aan Zee and Katwijk aan de Rijn are one, Den Haag = 's-Gravenhage, a street in a town ("Rapenburg, Leiden, …": four or more parts) belongs to that town, or two spots within 1 km; neighbouring villages a few km apart each get their own map) or someone moves 300 km or more, in Story and in Cards alike, so a known place never comes back. The trail starts at the birthplace of the person before. **A map never stands without a sentence that names its place and says why.** Each map sits right after the paragraph (or card) that names its place (for a move abroad also the country; a story place's `alinea`/`kaart`). Otherwise the viewer writes a short sentence from the data and puts it right before the map, at the year of that moment: born there, married there (with whom), children born there ("In 1807 the family lived in Ameide, where Johanna was born."), lived, worked, went to school, left or arrived there (`woon_feiten`), died there, or "Around 1958 the story takes place in …" for a story place. Without an own story the birthplace map follows the birth text and the map of the place of death follows the death sentence. In Cards that sentence is the caption of every map card. `make_viewer_data.py` notes the stories whose map places the text doesn't name. Near: a detail map (120 km) with a small overview in a free corner; far: a route with the distance; over 5,000 km a globe turned to the middle of the two places. A map card counts as a card in the card budget but is not a text card (it breaks a run). **A journey in Cards:** three or more map moments in a row in one country abroad (a `woon` period with a country), at most 5 years apart, become one map card: numbered pins in time order, a dotted line from each to the next, a small overview, the sentence "From 1955 to 1959 he was in Australia, in these places:" and a list (place, year or month, what happened there: arrival, the occupation, the event type). It counts as one card. A story can turn it off with `"journey_map": false`. Story keeps one map per place. **The order maps are shown in:** a map shows the distance from where the person was before; when that place only gets its own map further on (a paragraph named a later place first), the distance is from the map shown just before it instead (the birthplace always stays). The numbers are in `const MAP` in index.html.

## Old format (v1)

Files without `versie` (with `root`, `eva` and region codes like `ZH`) keep working; the viewer converts them when loading.
