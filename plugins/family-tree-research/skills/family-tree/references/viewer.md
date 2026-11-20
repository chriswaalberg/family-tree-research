# Building and updating the viewer

The viewer (`viewer/index.html`) contains nothing about a specific family: everything comes from `data.json`. Views: **Family** (vertical tree with side branches), **Line** (couple by couple upwards), **Story** (step by step back in time, choosing father or mother each time), **Timeline** (ancestors by birth year), **Fan** and **Cosmos**. Search, details per person with source and certainty, English/Dutch, works on phones. Full data format: `viewer/DATA-FORMAT.md`.

## 1. Building data.json

```
python3 -I scripts/make_viewer_data.py source/tree.ged data/data.json \
  --csv data/relations.csv --regions data/regions.json --stories data/stories.json --zeitgeist zeitgeist/zeitgeist.json \
  --start @I1@:Sanne --title "The Jansen family" --lang en
```

- Only the GEDCOM is required. Without `--csv` everything gets "not checked".
- Several `--start` are allowed (e.g. the user and their children); the first one opens by default.
- `--lang en` or `--lang nl`: the user's language (default en). The Dutch options (`--taal`, `--titel`, `--verhalen`, `--tijdgeest`, `--regios`, `--media-map`) still work.
- **Living people**: everything is shown, including dates and places. If the user wants that hidden for living people (e.g. for a viewer that's shared widely), use `--hide-living`.
- Check the output: number of people, "CSV: N relations read, 0 rows skipped". Rows skipped? Find out why (wrong id, relation doesn't exist in the GEDCOM).
- New places without a country: add them to `data/regions.json` (start from `examples/regions-basic.json`).
- **Stories**: `--stories data/stories.json` (optional). Check "Stories: N read".
- **Photos and documents**: add `--media-dir viewer/media`. The script copies all linked files (see `gedcom-tool.md`, "media") into `viewer/media/` and reports how many weren't found. It shrinks big photos itself if Pillow is available; otherwise shrink them first. Crop screenshots first: no browser or system chrome in the viewer (see SKILL.md, "Photos and documents"). A PNG without transparency becomes a JPG; the path in data.json changes with it, so remove the old `media/<name>.png` with `remove`.

## Stories (`data/stories.json`)

Key = GEDCOM id (`@I12@`) or full name. Value = text, `{"en": …, "nl": …}`, or with sources:

```json
{"@I12@": {"text": {"en": "…", "nl": "…"},
           "sources": [["Marriage banns Amsterdam 1776", "https://…"], ["Museum X", "https://…"]]}}
```

- Optional `"images": [{"bestand": "media/verhalen/x.jpg", "titel", "maker", "datering", "bijschrift", "bron": [title, url]}]`: old prints or photos with the story (only freely usable work; publish them as `media/verhalen/<name>`). Dutch keys (`tekst`, `bronnen`, `beelden`) also work; the image fields are explained in DATA-FORMAT.md.
- Blank line = new paragraph; `**bold**`, `*italic*` and `[text](https://…)` work.
- Never address the reader as a descendant ("your line", "your surname"): write "this family tree", "the line". The template text already does this.
- An own story replaces the template text for that person. So write it complete (who, where, when, what happened), in the user's language, warm and concrete, and stick to what the sources say. Put uncertainty in the text ("the strongest candidate is…, it's not certain yet").
- A sibling with a story appears with the ancestor on the trail as "Remarkable relative". That way an uncle who died in a camp, or a distant uncle with a famous history, comes along in the user's story.
- The richest trail scores each step by what's known (dates, places, own story +8, sibling with a story +6), weighted by the certainty of the relation. So stories pull the trail towards them.

## Zeitgeist (`zeitgeist/zeitgeist.json`)

Per place: `leven` (daily life: paragraphs per period), `gebeurtenissen` (events: year, text, source) and `beelden` (images: file, from/to, year, title, artist, dating, caption, source); plus `algemeen.gebeurtenissen` for national events. Full format and rules in `viewer/DATA-FORMAT.md` (field names are Dutch, explained there). Put the images in `zeitgeist/media/tijdgeest/` (max ±1200 px wide, JPEG) and publish them as `media/tijdgeest/<name>`.

Writing rules: concrete and sensory (what did people see, do and fear), short, in the user's language, and only what the sources say. After a few chapters a reader should feel they know the village.

The template text (written by the viewer for people without an own story) also gives ages: exact ages from full dates, and for the World Wars "he lived through the Second World War from age 3 to 8" (Netherlands: 10 May 1940 – 5 May 1945).

## 2. Publishing

**With the Artifact tool** (tools `mcp__claude-artifacts__*`), the best route:

- First time: `publish_files` with two files: `index.html` (from `viewer/`) and `data.json`, title "<Family name> family tree" (or "Stamboom <familienaam>" in Dutch), icon `tree`. The files must be where your file tools work; if they're only on the user's computer, stage them first.
- Note the link and the slug in the progress file.
- Media: publish every file from `viewer/media/` as `media/<name>` (in the same `publish_files` call; max. 256 files and 20 MB per file). Send new or changed media later too; removed media with `remove`.
- In an artifact only **images** work (thumbnail + view large). The artifact viewer can't open or download links to PDFs and other files. So convert a PDF record to an image (e.g. with `pdftoppm -jpeg -r 150`) before linking it; in the standalone HTML file PDF links do work.
- After that: only republish `data.json`, with `slug` + `base_version` of the live version (get it with `get_artifact`). If you get a conflict (409): read the live version again and retry. Only republish index.html when the plugin has a newer viewer.
- The artifact is private. The user can share it themselves via the share button in Claude. Tell them.

**No Artifact tool, but the desktop app**: build a standalone file and make a Cowork artifact from it:
```
python3 -I scripts/standalone_viewer.py viewer/index.html data/data.json family-tree.html --media viewer
```
(`--media viewer` bakes all images into the file: photos of people, images with stories and zeitgeist images. Leave it out if the file gets too big; then put the `media/` folder next to the HTML file.)
→ SendUserFile → `create_artifact` (later `update_artifact`).

**No artifacts at all**: hand over `family-tree.html` as a download (SendUserFile) and put it in the connected folder. The file works offline in any browser (only the fonts come from Google Fonts) and can be emailed.

## 3. Explaining it to the user (first time, short)

- Click a person for details: dates, places, source, how certain the relation is, and photos and documents if there are any.
- Lines: solid = certain, dashed = probable/possible, dotted = not checked yet, red = wrong, double gold = raised as their own child.
- Story: start at the start person and choose father or mother each time; the gold star marks the richest trail. When it gets uncertain, the story says so.
- At the top you switch views; with search you jump to someone and can make them the start person. The EN/NL switch changes the language (handy when sharing with family abroad).

## 4. Checking

After a big change (or the first time): look at the viewer yourself if you can (e.g. a Playwright screenshot of the standalone file, desktop and mobile) before sharing the link. Empty view or an error? Validate `data.json` (valid JSON, has `"versie": 2` and `personen`?).
