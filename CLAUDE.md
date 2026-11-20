# CLAUDE.md — working on this repo

This repo is a **Claude plugin marketplace** with one plugin: `family-tree-research` (Family Tree Research). Read this before changing anything.

## Layout

```
.claude-plugin/marketplace.json      marketplace "chriswaalberg" → ./plugins/family-tree-research (no version field; plugin.json leads)
plugins/family-tree-research/
  .claude-plugin/plugin.json         name, version, description
  README.md                          user-facing (English)
  skills/family-tree/
    SKILL.md                         instructions Claude follows (English, with a language rule)
    references/*.md                  onboarding, gedcom-export, research, sources, gedcom-tool, viewer, folders-and-files
    scripts/gedcom_tool.py           new / add / check / media   (Dutch aliases: nieuw / toevoegen / controleer)
    scripts/make_viewer_data.py      GEDCOM (+csv, regions, stories, zeitgeist, media) → data.json
    scripts/standalone_viewer.py     index.html + data.json → one HTML file
    viewer/index.html                the viewer (single file, ~320 kB, minified-ish JS; English + Dutch via I18N table)
    viewer/DATA-FORMAT.md            data.json format (field names are Dutch, documented in English)
    examples/                        7-person example family + regions-basic.json, example-stories.json and
                                     example-zeitgeist.json (fictional, to test the Story view) and one real CC0 photo in
                                     examples/media/tijdgeest/ (Den Helder, 1955, Anefo)
README.md, LICENSE (MIT)
```

The plugin name `family-tree-research`, skill name `family-tree` and marketplace name `chriswaalberg` must not change once published (it would break existing installs). Slash command: `/family-tree-research:family-tree`.

## Conventions

- **Bilingual, English default.** All docs, code, comments, script messages: English. Claude talks to end users in their language; Dutch must keep working everywhere:
  - scripts accept Dutch option names and JSON keys as aliases (`--taal`, `--titel`, `--verhalen`, `--tijdgeest`, `--regios`, `--media-map`, `--levenden-verbergen`; `voornamen`, `vader`, `bron`, …);
  - certainty statuses are accepted in both languages; `make_viewer_data.py` stores the Dutch value (`zeker`, `waarschijnlijk`, `mogelijk`, `onbekend`, `fout`, `niet gecheckt`), the viewer shows the label in its language;
  - relation types `raised/adopted/foster` map to the stored Dutch `aangenomen/adoptie/pleeg`.
- **data.json field names stay Dutch** (`versie`, `personen`, `taal`, `verhaal`, `tijdgeest`, …). Don't rename them: the viewer depends on them. Explain new fields in DATA-FORMAT.md.
- Viewer language: `taal`/`lang` in data.json; anything other than `"nl"` means English.
- Scripts: Python 3.8+, **standard library only** (Pillow optional for shrinking photos). Run with `python3 -I`.
- User-facing writing style (README, SKILL tone): warm, short, plain words, no jargon.

## Smoke test (run after every change)

```
S=plugins/family-tree-research/skills/family-tree
python3 -I $S/scripts/make_viewer_data.py $S/examples/example.ged /tmp/ex.json \
  --csv $S/examples/example-relations.csv --regions $S/examples/regions-basic.json \
  --stories $S/examples/example-stories.json --zeitgeist $S/examples/example-zeitgeist.json \
  --start @I1@:Femke --start @I2@:Thomas
python3 -I $S/scripts/gedcom_tool.py check $S/examples/example.ged /tmp/check.md --start @I1@
python3 -I $S/scripts/gedcom_tool.py check $S/examples/example.ged /tmp/check-nl.md --start @I1@ --lang nl
python3 -I $S/scripts/standalone_viewer.py $S/viewer/index.html /tmp/ex.json /tmp/ex.html
cp -R $S/examples/media /tmp/media   # zeitgeist images are not embedded; they load from media/ next to the HTML
```

Then open `/tmp/ex.html` (or screenshot it with Playwright, desktop + mobile) and click through all tabs: Family, Line, Story, Timeline, Fan, Cosmos. In the Story view, follow Femke → Thomas → Pieter: Pieter must show his own (example) story, a "Life in Den Helder" block with the 1955 photo, and the 1963 example event with a source link and an "Example links" line; Anna's template text must say she lived through the Second World War "roughly from age 15 to 20". In English, no Dutch words may appear (e.g. "bron"). Check the browser console for errors. Also test with `--lang nl`. If you touched `gedcom_tool.py new/add`, test them with both English and Dutch JSON keys (formats in references/onboarding.md and references/gedcom-tool.md).

If `examples/example-data.json` should change, regenerate it with the first command (output to `$S/examples/example-data.json`).

## Viewer map (index.html)

The viewer is one file (~1,700 lines, CSS + HTML + JS). Find your way by these markers (search for them; line numbers drift):

- `/* ===== TEKSTEN (NL / EN) ===== */` → `const I18N = {nl:{…}, en:{…}}`. More keys are added later with `Object.assign(I18N.nl,…)` / `Object.assign(I18N.en,…)` (Story texts: `vh_*`, events `e_*`). Every user-visible string lives here, in both languages.
- `function certOf`, `isAdopt`, `hasAdopt`, `adoptSet`: certainty of a parent link and raised/adopted/foster lines (gold double line, hatching, "family by adoption").
- `/* ===== WAAIER` (Fan), `KOSMOS` (Cosmos), `TIJDLIJN` (Timeline), `STAMLIJN` (Line), `function drawFamilie` (Family).
- `/* ===== VERHAAL` (Story view):
  - `vhRich`, `vhBest`, `vhDepth`, `vhStories`: scoring of the "richest trail" (gold star).
  - `vhYMD`, `vhAge`: exact ages from GEDCOM dates; "about" only when a date is estimated.
  - `vhTemplate`: the generated text for people without an own story (birth, age at child's birth, family, move, death, eras, World War ages "from age 3 to 8", note on church records before 1811). Never addresses the reader as a descendant.
  - `vhTG`, `vhSpan`, `vhPlacesOf`: zeitgeist lookup by birth/death place (`match`).
  - `vhAssignImages(path)`: spreads zeitgeist images over the whole trail. Images with `kind:true` first go to someone who was under 16 at the time (max. 2), then one per person alive at the time, then two; plain views may go to someone born up to 25 years later only as a last resort; `gebeurtenis:true` images only to people alive then.
  - `vhTijdgeest`: renders "Life in …", the assigned images and "Around that time" (max 4 local + 1 national event; a national event in the same year as a local one is dropped; optional `links`).
  - `drawVerhaal`: the chapters, father/mother choice, route bar, "Remarkable relative" asides, certainty and adoption callouts.
- Menu: Story is a separate gold button (`#storyBtn`, CSS under `/* story-knop`) before the tab group `#tabs`; `render()` sets its `aria-pressed`.
- `/* ===== DATA` → `function prepareData` (also sets the language: `LANG=(d.taal||d.lang)==="nl"?"nl":"en"`), `const VIEWS`, and the `fetch("data.json")` line that `standalone_viewer.py` looks for.

## Releasing a new version

1. Bump the version in `plugins/family-tree-research/.claude-plugin/plugin.json` **and** in the `metadata.version` of `SKILL.md`.
2. Validate: `claude plugin validate .` (marketplace) and `claude plugin validate plugins/family-tree-research/.claude-plugin/plugin.json`.
3. Commit and push to `main`. Users with "Sync automatically" on get it by themselves.
4. Optional: rebuild the standalone package: `cd plugins/family-tree-research && zip -r -X ../../family-tree-research.plugin README.md .claude-plugin skills -x "*.DS_Store" "*__pycache__*"` (don't commit the .plugin file).

## Gotchas

- `viewer/index.html` loads data with exactly `fetch("data.json").then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()})`; `standalone_viewer.py` searches for that string. Keep it in sync if you change it.
- The viewer's language default lives in two places in index.html: `let LANG="en";` and in `prepareData`: `LANG=(d.taal||d.lang)==="nl"?"nl":"en";`.
- New user-visible viewer text goes into the `I18N` table (both `nl` and `en`), not hard-coded. The EN/NL switch (`langInit`/`setLang`, marked `/* taalswitch */`) re-runs `applyTexts()` and `render()`; anything computed once at load (like `META.titel`) must be recomputed in `setLang` too.
- In the published artifact only images work as media; PDFs only work in the standalone file.
