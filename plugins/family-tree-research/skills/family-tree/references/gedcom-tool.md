# gedcom_tool.py and its JSON formats

Subcommands have English names; the Dutch names (`nieuw`, `toevoegen`, `controleer`, `opbouwen`) also work. JSON keys can be English or Dutch.

## new — GEDCOM from the onboarding

```
python3 -I scripts/gedcom_tool.py new data/intake.json source/original.ged
```

Format of `intake.json`: see onboarding.md. The script prints the mapping `p1 → @I1@`; note the GEDCOM id of the start person in the progress file. This file is the starting point: from here on it doesn't change, the rounds build on it (see `rebuild`).

## rebuild — the tree from the original plus all rounds

The way to change the tree. The original GEDCOM (the import, or what `new` made) is **never** changed. Every research round is one JSON file in `rounds/` (Dutch: `rondes/`); `rebuild` applies all rounds to the original, in order, and writes the working version, the relations CSV and the register of rejected links:

```
python3 -I scripts/gedcom_tool.py rebuild source/original-ancestry-2026-11-19.ged rounds source/tree.ged \
  --csv data/relations.csv --rejected reports/rejected.md --media data/media.csv --lang en
```

- Rounds are read in the order of the number at the start of the file name: `001-grandparents.json`, `002-zwolle.json`, …, `052-….json`. One number per round.
- Same input gives byte for byte the same output, so a diff of `source/tree.ged` shows exactly what a new round changed. Never edit `tree.ged`, `relations.csv` or `rejected.md` by hand: the next rebuild overwrites them. Change a round file instead (or add one).
- `--csv` writes every parent-child link in the tree with its status (from the rounds; else from `--base-csv`; else `not checked`). `--rejected` writes the register (see below). `--media` links photos and scans at the end (as the `media` subcommand). `--places-report` lists the place names that aren't yet "Place, Province, Country". `--lang nl` makes the generated notes, CSV header and register Dutch.
- A step that points to an unknown person, or that can't be done, stops the rebuild with the file and step number. Fix the round and run again.

### A round file

```json
{
  "title": "Parents of Hendrik Jansen",
  "date": "2026-11-19",
  "source": "Death record Zwolle 1868, no. 41 https://www.openarchieven.nl/...",
  "steps": [
    {"op": "event", "person": "@I7@", "type": "death", "date": "3-1-1868", "place": "Zwolle"},
    {"op": "event", "person": "@I7@", "type": "birth", "date": "c. 1795", "if_empty": true},
    {"op": "add", "ref": "jacob", "given_names": "Jacob", "surname": "Jansen", "sex": "M"},
    {"op": "parents", "child": "@I7@", "father": "jacob", "status": "probable"},
    {"op": "drop_link", "child": "@I4@", "parent": "@I9@", "reason": "She was his stepmother",
     "from": "Ancestry hint", "source": "Population register Zwolle 1920, p. 7"},
    {"op": "merge", "keep": "@I12@", "drop": "@I31@", "reason": "the same man, Jan is his everyday name"},
    {"op": "places", "map": {"Swol": "Zwolle, Overijssel, Nederland"}}
  ]
}
```

Dutch: `titel`, `datum`, `bron`, `stappen`, and the Dutch step names and keys below. The round's `source` is the default for every step without its own `source`. A source is text with an optional link (`"... https://..."`), or `{"text": "...", "url": "..."}`, or a list of those. In the GEDCOM it becomes a citation (`SOUR` / `PAGE` / `WWW`) of a source record for the round.

**Who is who.** A person is a GEDCOM id (`@I4@` or `I4`) or a `ref` from an `add` earlier in the same round. A new person gets the id `@I<round>_<ref>@` (`@I52_jacob@`): it never shifts when an earlier round changes, so stories and links that use it keep working. Later rounds use that id. A person who already had an id elsewhere (from an older script, in stories, media lists or shared links) can keep it: give the `add` step `"id": "@I90012@"` (or `I90012`); the `ref` still works within the round. In the same way a `parents` step (or an `event` with `person` + `partner`) that makes a new family can get `"family_id": "@F90039@"` (`gezin_id`). An id that exists in the original or an earlier round, or that was removed or merged away, stops the rebuild with file and step. After a `merge`, the dropped id keeps working and points to the kept person.

### Steps

| op (en / nl) | keys | what it does |
|---|---|---|
| `add` / `nieuw` | `ref`, `id` (optional fixed id), `given_names`, `surname`, `sex`, `birth`, `baptism`, `death`, `burial` (each `{date, place}` or a date), `occupation`, `aka`, `notes` | a new person, with the step's source |
| `parents` / `ouders` | `child`, `father`, `mother`, `family_id` (`gezin_id`, optional, only for a new family), `marriage`, `status`, `note`, `type`; per parent `status_father`, `source_mother`, … | links parents to a child. Joins the couple's existing family if there is one; adds a missing parent to the child's family. Stops if the child already has *another* father/mother (remove that link first with `drop_link`) or if the link is in the rejected register (see below) |
| `status` / `zekerheid` | `child`, `father`/`mother`/`parent`, `status`, `source`, `note`, `type` | only the status and source of an existing link (e.g. after checking an imported tree, or the user's own knowledge) |
| `event` / `gebeurtenis` | `person` (or `family`, or `person` + `partner`), `type`, `date`, `place`, `note`, `age`, `description`; `if_empty`, `separate` | birth, baptism, death, burial, marriage, divorce, banns (`ondertrouw`), residence, emigration, census, … or your own kind (`"type": "Award"` becomes `EVEN` + `TYPE Award`). Birth, baptism, death, burial, marriage and divorce exist once: a new date/place replaces the old one, which stays in a note ("Earlier value: …"). `if_empty` only fills what's empty; `separate` adds a second one. Residences and other events are always added |
| `occupation` / `beroep` | `person`, `occupation`, `date`, `place`, `note` | `OCCU` with only the occupation itself; explanation in `note` (the viewer shows OCCU literally) |
| `note` / `notitie` | `person` or `family`, `text` | a note, with the source next to it |
| `aka` / `roepnaam` | `person`, `name` (`"Piet /de Vries/"`) or `given_names` + `surname`, `note` | another name: `NAME … TYPE aka` (everyday name, spelling variant, alias in a record) |
| `name` / `naam` | `person`, `given_names`, `surname`; `keep_old` (default true) | changes the main name; the old one stays as aka |
| `drop_link` / `koppeling_weg` | `child`, `parent` (or `father`/`mother`), `reason` (required), `from`, `source`; `couple` | removes a wrong parent. The reason goes into the rejected register and as a note on the child. If the family has a marriage or other children, the couple stays and only this child moves out. If the family was only there because of this child, the parent leaves it. `"couple": "split"` (`"paar": "splitsen"`): this parent was never part of the family (e.g. a wrong husband): he leaves it for all its children |
| `merge` / `samenvoegen` | `keep` (`houd`), `drop` (`weg`), `reason` | merges a duplicate: the other name becomes aka, events and sources move over (a single event the kept person already has stays; a different value goes into a note), families are joined, and families that now have the same couple become one |
| `drop_event` / `gebeurtenis_weg` | `person` or `family`, `type`, `match` (text in the event, e.g. `"1792"`), `reason` (required) | removes a wrong event (e.g. a baptism that belongs to an older brother); goes into the register |
| `drop_person` / `persoon_weg` | `person`, `reason` (required), `from` | removes a person who doesn't exist or doesn't belong in the tree; goes into the register |
| `places` / `plaatsen` | `map`: `{"old name": "Place, Province, Country"}` | place names made uniform. Applied at the end to every `PLAC`, over all rounds (a later round wins). Exact names (case and extra spaces don't matter) |
| `lines` / `regels` | `person` or `family`, `lines` | escape hatch: raw GEDCOM lines (level 1 and deeper) for what the steps don't cover |

Status words, relation types (`raised`, `adopted`, `foster`) and their Dutch versions: see research.md. `adopted` and `foster` also become `PEDI` in the GEDCOM.

### The rejected register

`reports/rejected.md` (Dutch: `rapporten/afgewezen.md`) is made from the `drop_link`, `drop_event` and `drop_person` steps. **Read it before adding a parent.** `parents` refuses a link that's in it (same person, or a new person with the same name for the same child). Only when a new source refutes the reason: add `"despite": "<new source and why>"` (`"ondanks"`) to the `parents` step; the register then says it was added again.

### Switching from a hand-edited tree

Someone who has worked on the tree in place, or with their own scripts (like a long cleanup script), doesn't have to redo everything:
1. Keep the real original (the platform export) as it is.
2. Make the current, edited tree the starting point for the rebuild: `source/original-<date>-edited.ged` (a copy; it doesn't change any more).
3. Turn the current `relations.csv` into the base: `--base-csv data/relations-<date>.csv` (rows by GEDCOM id), or write it into a first round with `status` steps.
4. Links removed before the switch are already out of the starting point, so the generated register doesn't know them. Keep the old list as `reports/rejected-before-<date>.md` and read it together with the new register.
5. Turning the old script's changes into round files? Give every person and family it created its old id (`"id": "@I90012@"` on `add`, `"family_id": "@F90039@"` on `parents`), so stories, media lists, zeitgeist files and shared links (`#story/I90012`) keep working. Without `id` a new person gets `@I<round>_<ref>@`.
6. From now on, every new finding is a round file.

## add — adding ancestors (in place; older way)

`rebuild` with rounds is the recommended way. `add` still works, but changes the GEDCOM in place.

Per round, make a `data/additions.json`:

```json
{
  "new": [
    {"ref": "father_hendrik", "given_names": "Jan", "surname": "Jansen", "sex": "M",
     "birth": {"date": "c. 1898", "place": "Zwolle"},
     "death": {"date": "4-11-1961", "place": "Zwolle"},
     "occupation": "carpenter",
     "source": "Marriage record Zwolle 1922, no. 88, https://www.openarchieven.nl/..."},
    {"ref": "mother_hendrik", "given_names": "Geesje", "surname": "Smit", "sex": "F"}
  ],
  "parents": [
    {"child": "@I4@", "father": "father_hendrik", "mother": "mother_hendrik",
     "marriage": {"date": "1922", "place": "Zwolle"},
     "status": "certain",
     "source": "Birth record Hendrik Jansen, Zwolle 1925, no. 301, https://...",
     "note": "Hendrik's birth record (Zwolle, 1925) names Jan Jansen, 27, carpenter, and Geesje Smit as parents; they married in Zwolle in 1922."}
  ]
}
```

- `child`, `father`, `mother`: an existing GEDCOM id (`@I4@` or `I4`) or a `ref` from `new`. That way you can add several generations at once.
- `note` is the reason the status holds, shown in the viewer as "Why certain:": one plain sentence with the record, place and year and who is named as parent; for probable/possible also what's missing. `why` (Dutch `waarom`) is an alias. A `status` step takes it too.
- A separate status, source, reason or type per parent? Use `status_father`, `status_mother`, `source_father`, `source_mother`, `note_father`/`why_father`, `note_mother`/`why_mother`, `type_father`, `type_mother`.
- Dutch keys also work: `nieuw`, `ouders`, `kind`, `vader`, `moeder`, `huwelijk`, `bron`, `opmerking` (or `waarom`), `soort`, `status_vader`, `bron_moeder` and so on, and in persons the keys from onboarding.md.
- If the child already has a family with one parent, the script adds the missing parent. If the child already has **different** parents, the script stops: resolve that first and explain it in questions.md.
- With `--csv data/relations.csv` the relations with status and source are appended immediately. `--lang nl` uses `zeker` as default status and a Dutch header for a new CSV; default is English (`certain`). When appending to an existing CSV the columns are written in the order child, parent, status, source, note, type — matching both the English and the Dutch header.

```
cp source/tree.ged source/tree-$(date +%F).ged
python3 -I scripts/gedcom_tool.py add source/tree.ged data/additions.json source/tree.ged --csv data/relations.csv
```

Changing the status of an existing relation (e.g. after verifying an imported tree): with `rebuild`, a `status` step in a round (the CSV is generated). Without rounds: edit the row in the CSV, or add a row; with duplicate rows the last one wins. (Check the output of make_viewer_data.py afterwards: it reports how many relations were read.)

## check — report

```
python3 -I scripts/gedcom_tool.py check source/tree.ged reports/check.md --start @I1@ [--gaps-to 8] [--lang nl]
```

Gives counts, ancestors per generation (expected/found), the gaps and things worth a look (parents' ages, born after death, possible duplicates). Without `--start` it picks the person with the most ancestors. Run it again after every round; the report then doubles as the list of gaps. Use `--lang` in the user's language.

## media — linking photos and documents

```
python3 -I scripts/gedcom_tool.py media source/tree.ged data/media.csv source/tree.ged
```

`data/media.csv` (delimiter `,` `;` or tab), one row per file:

```
person,file,title,type
@I4@,photos/grandpa-hendrik-1950.jpg,"Grandpa Hendrik on his wedding day, 1950",photo
Jan Jansen (1898),scans/1922 marriage Zwolle no 88.jpg,"Marriage record Zwolle 1922, no. 88",scan
```

- Dutch column names also work: `persoon`, `bestand`, `titel`, `soort` (`foto`, `scan`, `document`).
- `person`: GEDCOM id, or a name with optional birth year in brackets if the name isn't unique.
- `file`: path from the family-tree folder (`scans/…`, `photos/…`). Never put absolute paths from the user's computer in the GEDCOM.
- `type`: `photo`, `scan` or `document` (becomes GEDCOM `TYPE photo/document`).
- `portrait` (optional; Dutch `portret`): `yes` for the photo that is the person's portrait (becomes `2 _PRIM Y`). Without it the first photo is used. It also works for a file that is already linked: run `media` again with `portrait` filled in and only the mark is added.
- Per file the script writes `1 OBJE / 2 FILE … / 3 FORM jpg / 4 TYPE photo / 2 TITL …` with the person. Files already linked are skipped, so it may run again after every round with the whole CSV.
- Working with `rebuild`? Pass `--media data/media.csv` to it: the photos are linked as the last step.
