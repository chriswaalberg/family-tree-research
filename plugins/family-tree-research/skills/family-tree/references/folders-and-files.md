# Folders and files

Create this in the connected folder. Without a connected folder: the same structure in the session's working folder.

Use **English names by default**. If the user speaks Dutch, use the Dutch names from the right-hand column (that's how existing Dutch projects are set up). Never mix within one project; if a project already exists, keep its names. The scripts take paths as arguments, so either works.

```
Family tree/                    (Stamboom/)
├── PROGRESS.md                 (VOORTGANG.md)        ← always read first; always update at the end
├── README.md                   (LEESMIJ.md)          ← short explanation for the user: what is where
├── source/                     (bron/)               ← GEDCOMs: original unchanged + working version
│   ├── original-<platform>-<date>.ged
│   └── tree.ged                (stamboom.ged)        ← working version (copy with date before every round)
├── data/
│   ├── intake.json             (invoer.json)         ← what the user told you (onboarding)
│   ├── relations.csv           (relaties-zekerheid.csv) ← status + source per parent-child relation
│   ├── regions.json            (regios.json)         ← place → country/region (start from the plugin's basic version)
│   ├── media.csv                                     ← which photo/scan belongs to which person
│   ├── stories.json            (verhalen.json)       ← own stories per person, with sources (Story view)
│   ├── data.json                                     ← generated for the viewer
│   └── worklog.md              (werklog.md)          ← what was searched, found and not found
├── reports/                    (rapporten/)
│   ├── check.md                (controle.md)         ← output of gedcom_tool.py check
│   ├── new.md                  (nieuw.md)            ← new ancestors per round, with source
│   └── questions.md            (vragen.md)           ← open questions, contradictions, requests for help
├── zeitgeist/                  (tijdgeest/)          ← zeitgeist.json (tijdgeest.json) + media/tijdgeest/ (old prints per place)
├── scans/                                            ← photos and screenshots of records, logically renamed
├── photos/                     (fotos/)              ← the user's family photos and documents
└── viewer/                                           ← copy of index.html (from the plugin) + media/ (copied photos)
```

## PROGRESS.md (template; write it in the user's language)

```markdown
# Progress: <family name> family tree

Updated: <date>

## Agreements
- Language: en / nl
- Start person: <name> (<GEDCOM id>)
- Most curious about: …
- Way of working: independently up to … / show after every generation
- Viewer: <link> (artifact id <slug>)
- Works: Open Archives, … · Doesn't work (via the user): …

## Status
- <N> people, <M> direct ancestors, oldest generation <G>
- Relations: <x> certain, <y> probable, <z> possible, <u> unknown, <v> not checked

## Next steps
1. …

## Open questions (details in reports/questions.md)
- …
```

Keep the progress file short (max. ±1 page). Details go in the worklog and reports.

## Running the scripts

The scripts are in this skill (`scripts/`). They only use the Python standard library; run them with `python3 -I`.

- **A shell on the user's computer is available** (connected folder + device shell): at the start, copy `scripts/*.py` to `<tree folder>/data/scripts/` and `viewer/index.html` to `<tree folder>/viewer/`, and work there. That way the files stay in place and a next session can continue directly.
- **Only a cloud shell**: run the scripts in the session, fetch the files you need (GEDCOM, CSV) from the connected folder and put the results back.
- At the start, check that `python3` is there (`python3 --version`, 3.8+).
