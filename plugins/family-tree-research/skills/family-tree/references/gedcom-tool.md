# gedcom_tool.py and its JSON formats

Subcommands have English names; the Dutch names (`nieuw`, `toevoegen`, `controleer`) also work. JSON keys can be English or Dutch.

## new — GEDCOM from the onboarding

```
python3 -I scripts/gedcom_tool.py new data/intake.json source/tree.ged
```

Format of `intake.json`: see onboarding.md. The script prints the mapping `p1 → @I1@`; note the GEDCOM id of the start person in the progress file.

## add — adding ancestors

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
     "note": "father 27, carpenter"}
  ]
}
```

- `child`, `father`, `mother`: an existing GEDCOM id (`@I4@` or `I4`) or a `ref` from `new`. That way you can add several generations at once.
- A separate status, source or type per parent? Use `status_father`, `status_mother`, `source_father`, `source_mother`, `type_father`, `type_mother`.
- Dutch keys also work: `nieuw`, `ouders`, `kind`, `vader`, `moeder`, `huwelijk`, `bron`, `opmerking`, `soort`, `status_vader`, `bron_moeder` and so on, and in persons the keys from onboarding.md.
- If the child already has a family with one parent, the script adds the missing parent. If the child already has **different** parents, the script stops: resolve that first and explain it in questions.md.
- With `--csv data/relations.csv` the relations with status and source are appended immediately. `--lang nl` uses `zeker` as default status and a Dutch header for a new CSV; default is English (`certain`). When appending to an existing CSV the columns are written in the order child, parent, status, source, note, type — matching both the English and the Dutch header.

```
cp source/tree.ged source/tree-$(date +%F).ged
python3 -I scripts/gedcom_tool.py add source/tree.ged data/additions.json source/tree.ged --csv data/relations.csv
```

Changing the status of an existing relation (e.g. after verifying an imported tree): edit the row in the CSV, or add a row; with duplicate rows the last one wins. (Check the output of make_viewer_data.py afterwards: it reports how many relations were read.)

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
- Working with a version that's rebuilt from the original each time? Then run `media` as the last step.
