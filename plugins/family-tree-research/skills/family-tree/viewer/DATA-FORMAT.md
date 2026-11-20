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
| `familienaam` | text | no | Family name. No longer shown (see `titel`). |
| `startpersonen` | list | no | Each item: `{"persoon": 0, "label": "Femke"}` (`label` optional, defaults to the first name). The first one is the start person when the viewer opens. The reader picks another start person by clicking the name in the title (it lists these start people and a search), or via "Make start person" in a person's details. Without the list the viewer starts at person 0. |
| `startpersoon_per_weergave` | object | no | A different start person for one view, e.g. `{"stamlijn": 2}`. Views: `familie` (Family), `stamlijn` (Line), `verhaal` (Story), `tijdlijn` (Timeline), `waaier` (Fan), `kosmos` (Cosmos). |
| `levenden_tonen` | yes/no | no | Default (missing or `true`): the viewer shows everything. `false` hides dates and places of living people. |
| `regios` | object | no | Region codes: `{code: {"naam": …, "kleur": "#hex"}}` (`naam` = name, `kleur` = colour). `naam` can be text or `{"en": …, "nl": …}`. Use a country or country-region code (`NL`, `NL-ZH`, `BE-VAN`, `SE-M`). The viewer colours by **country of birth**: it takes the part before the hyphen (`NL-ZH` → `NL`). For well-known countries (NL, BE, DE, SE, NO, DK, FR, GB, US, ID) the viewer has its own names and colours; for other codes it uses `naam` and `kleur` from this table. |
| `plaatsen` | object | no | Place → region code, for people without `r`. Keys are compared without capitals and accents; first the whole place name, then each comma-separated part (`"Leiden, Zuid-Holland, Nederland"` → `leiden`, `zuid-holland`, `nederland`). |
| `tijdgeest` | object | no | Life and times per place (see "Zeitgeist" below). |

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
| `c` | object | no | Certainty of the relation to the parents: `{"f": [status, source, note], "m": [...]}`. An optional fourth element gives the kind of relation: `"aangenomen"` (raised as their own child), `"adoptie"` (adoption) or `"pleeg"` (foster); default is biological. The viewer then shows e.g. "raised as their own child" and the Story view explains that this parent was not the biological parent. |
| `id` | text | no | Original GEDCOM id (e.g. `I12`), informational only. |
| `beroep` | list of text | no | Occupations, literally from the GEDCOM (`1 OCCU`), in GEDCOM order: `["timmerman", "bewaker"]`. Shown in the person's details and in the Story text: "He worked as timmerman, later bewaker." / "Hij was timmerman, later bewaker." Left out for living people with `--hide-living`. |
| `media` | list | no | Photos and documents, see below. |
| `verhaal`, `verhaal_bronnen`, `verhaal_beelden` | | no | Own story, see "Stories" below. |

### Photos and documents (`media`)

Each item: `{"bestand": "media/grandma-1950.jpg", "titel": "Grandma Riet, 1950", "soort": "foto"}` (`bestand` = file, `titel` = caption, `soort` = kind). Only `bestand` is required (a plain string also works).

- `bestand`: path next to `index.html` (e.g. `media/…`), an `https://` address or a `data:` URL.
- `titel`: caption. Without it the viewer shows the file name.
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
| `note` / `notes` / `opmerking` | free text |
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
| `verhaal_bronnen` | list | Sources: `[["title", "https://…"], …]`, shown under the story. |
| `verhaal_beelden` | list | Old images with the story: `[{"bestand": "media/verhalen/x.jpg", "titel": …, "maker": …, "datering": …, "bijschrift": …, "bron": ["title", "https://…"]}]` (`maker` = artist, `datering` = dating, `bijschrift` = caption, `bron` = source). Optional `soort` as with zeitgeist images (`foto`, `tekening`, …, `krant` for a newspaper clipping). Optional `alinea` (paragraph, 1-based): the image comes right after that paragraph, in the Story view between it and the next one and in Cards as the card after it. Without `alinea` the viewer places it after the paragraph that mentions the year from `datering` or a clear word from the title or caption, and otherwise spreads the images evenly over the story. Rule: every story image fits a moment in the story (same place, within ~15 years) and has an `alinea`; `make_viewer_data.py` warns (no error) when the year in `datering` lies outside (birth − 10) to (death + 10), or when `alinea` is missing or the paragraph doesn't exist. |

A sibling with their own story appears as "Remarkable relative" with the ancestor on the trail.

With the script: `--stories stories.json`, keyed by GEDCOM id (`@I12@`) or full name. English keys (`text`, `sources`, `images`) and Dutch keys (`tekst`, `bronnen`, `beelden`) both work:

```json
{"@I12@": {"text": {"en": "…", "nl": "…"},
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
              "bron": ["Wikimedia Commons, public domain", "https://commons.wikimedia.org/wiki/File:…"], "alinea": 3},
             {"bestand": "media/verhalen/krant-1781-huwelijk.jpg", "soort": "krant", "alinea": 2,
              "titel": "Marriage announcement", "maker": "Leydse Courant", "datering": "5 May 1781",
              "bijschrift": {"en": "The announcement of his marriage (shortened: only the heading and his notice).", "nl": "De aankondiging van zijn huwelijk (ingekort: alleen de kop en zijn bericht)."},
              "bron": ["Delpher", "https://www.delpher.nl/…"]}]},
 "Pieter de Vries": "Short text without sources."}
```

## Zeitgeist (`tijdgeest`, for the Story view)

Optional top-level field. Per place it paints a picture of how people lived there. In the Story view it appears for everyone born or died in that place, in a box under the text:

- **`leven`** (daily life): one or more paragraphs about daily life in a period. Shown with the first person on the trail whose life (midpoint of birth and death year) falls in that period, and not again after that.
- **`beelden`** (images): old prints, drawings, paintings or photos. Per person the image closest in year to their life that hasn't been shown yet. Click = large.
- **`gebeurtenissen`** (events): local events with year and source. Shown for people alive and at least 6 years old at the time, each once per story, at most 4 local ones per person. A national event from the same year as a local one is left out (no double "1944").
  - Optional `"links": [["title", "https://…"], …]` with `"links_label": "…"`: links shown under the event, e.g. to images you may not copy (copyright). Only link to pages where the image can actually be seen.
- **`algemeen.gebeurtenissen`** (general events): national events, at most 1 per person.

```json
{"tijdgeest": {
  "plaatsen": [{
    "id": "katwijk", "naam": "Katwijk", "match": ["katwijk"],
    "leven": [{"van": 1625, "tot": 1800, "titel": "Life in Katwijk aan Zee", "tekst": "… (blank line = new paragraph)"}],
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

- Images are spread over the whole trail: each image goes to the person who was alive then and whose mid-life is closest to its year (first one per person, then at most two). Only if nobody on the trail was alive then may a general view of the place go to someone born up to 25 years later. Set `"gebeurtenis": true` on an image of a specific event (a sea battle, a stranded whale); it only appears for people alive at the time. Also set `"kind": true` on an image about children (children in a famine, at school): it only goes to someone on the trail who was younger than 16 at the time (at most two per person). If nobody on the trail was a child then, the image is not shown on that trail.
- `soort` on an image (kind): `foto`, `tekening`, `prent`, `schilderij`, `kaart`, `munt`, `affiche` or `krant` (newspaper clipping) (English also works in the input: photo, drawing, print, painting, map, coin, poster, newspaper; `make_viewer_data.py` stores the Dutch value). The Story view and Cards show it above the image: "A drawing from that time" / "Een tekening uit die tijd", "From the newspaper" / "Uit de krant"; without `soort`: "An image from that time". Not to be confused with `kind`, the flag for images about children.
- `match`: text fragments that must occur in the birth or death place (without capitals and accents).
- Lifespan: birth year to death year; without a death year the viewer assumes 60 years.
- Texts can also be `{"en": …, "nl": …}`. Publish images as `media/tijdgeest/<name>` next to index.html. Only use images that are free to use (public domain or CC0), and credit artist and source.
- With the script: `--zeitgeist zeitgeist.json`.

## Old format (v1)

Files without `versie` (with `root`, `eva` and region codes like `ZH`) keep working; the viewer converts them when loading.
