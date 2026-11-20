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
docs/screenshots/                    screenshots for the README (example family only, never real data)
docs/demo/make_demo.py, demo.ged     larger fictional demo family (133 people) for the fan screenshot
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
python3 -I $S/scripts/standalone_viewer.py $S/viewer/index.html /tmp/ex.json /tmp/ex.html --media $S/examples
```

Then open `/tmp/ex.html` (or screenshot it with Playwright, desktop + mobile) and click through all tabs: Family, Line, Story, Timeline, Fan, Cosmos, and open ▶ Cards (tap through Femke → Thomas → Pieter; the Den Helder photo card must show). Click the name in the title and pick Thomas: title, Story and Cards must follow. The footer must say "Made with Family Tree Research v<version>" with the version from plugin.json. In the Story view, follow Femke → Thomas → Pieter: Pieter must show his own (example) story, a "Life in Den Helder" block with the 1955 photo, and the 1963 example event with a source link and an "Example links" line; Anna's template text must say she lived through the Second World War "roughly from age 15 to 20". In English, no Dutch words may appear (e.g. "bron"). Check the browser console for errors. Also test with `--lang nl`. If you touched `gedcom_tool.py new/add`, test them with both English and Dutch JSON keys (formats in references/onboarding.md and references/gedcom-tool.md).

If `examples/example-data.json` should change, regenerate it with the first command (output to `$S/examples/example-data.json`).

## Viewer map (index.html)

The viewer is one file (~1,700 lines, CSS + HTML + JS). Find your way by these markers (search for them; line numbers drift):

- `/* ===== TEKSTEN (NL / EN) ===== */` → `const I18N = {nl:{…}, en:{…}}`. More keys are added later with `Object.assign(I18N.nl,…)` / `Object.assign(I18N.en,…)` (Story texts: `vh_*`, events `e_*`). Every user-visible string lives here, in both languages.
- `function certOf`, `isAdopt`, `hasAdopt`, `adoptSet`: certainty of a parent link and raised/adopted/foster lines (gold double line, hatching, "family by adoption"). On the parent's card and sheet the label is `vh_adopt_par` ("nam {child} aan als eigen kind"), never `vh_adopt`.
- `/* ===== WAAIER` (Fan), `KOSMOS` (Cosmos), `TIJDLIJN` (Timeline), `STAMLIJN` (Line), `function drawFamilie` (Family).
- `/* ===== VERHAAL` (Story view):
  - `vhRich`, `vhBest`, `vhDepth`, `vhStories`: scoring of the "richest trail" (gold star).
  - `vhYMD`, `vhAge`: exact ages from GEDCOM dates; "about" only when a date is estimated.
  - `vhTemplate`: the generated text for people without an own story (birth, occupations (`beroep`, from GEDCOM `OCCU`: "He worked as X, later Y"), age at child's birth, the start person's brothers and sisters (`vhSibSentences`, half-siblings separately), children by name and year in birth order, each with the parent's age at the birth (`vhNames(kids, ageOf)`: `vh_ageIn`/`vh_ageInC`; more than 4 children: only at the first and last; the very young/old warning only for the child of the path; max. 8 + "and n others"; numbers up to twelve in words via `vhNum`; living people get `vh_kids*_living`, without "that we know of"), children with another partner (`vh_other1/N`), move, death, eras, World War ages "from age 3 to 8", note on church records before 1811). Never addresses the reader as a descendant.
  - `vhTG`, `vhSpan`, `vhPlacesOf`, `vhInIv`: zeitgeist lookup by the person's `woon` periods (place + years, made by `make_viewer_data.py` from birth, RESI, marriages, children's births, death); life, events and images only within those years. Old data without `woon`: birth/death place, whole life. Years abroad (`weg`, from EMIG/IMMI/EVEN Emigratie/RESI abroad) are cut out of home periods (`vhCutWeg`) and national events skip them (`vhAbroad`, `landAt`).
  - `vhAssignImages(path)`: spreads zeitgeist images over the whole trail. Images with `kind:true` only go to someone who was under 16 at the time (max. 2; nobody → not shown on that trail); other images one per person alive at the time, then two; plain views may go to someone born up to 25 years later only as a last resort; `gebeurtenis:true` images only to people alive then.
  - One timeline per person: `vhParaYears` (year per paragraph of an own story: first year in it, else an age in words via `vhAgeInText` ("op zijn zestiende", "at 16") = birth year + age; first paragraph without one = birth; others between their neighbours), `vhTgPieces` (the zeitgeist block cut into life/image/event pieces with `data-y`), `vhSortByYear` (stable; no year = stays after the previous item), `vhTgBox`. `drawVerhaal` mixes paragraphs and zeitgeist pieces by year; without an own story the zeitgeist block sits between life and death. `swBuild` gives every card a `y` and sorts: intro first, death/fork/end last, one "lived through" card per war, neighbouring event cards merged.
  - `vhScans`/`vhScanItems`: a story image with `scan` (full scan of a clipping, one of the person's media): that scan is left out of the document buttons in Story and Cards (the person sheet keeps it); a tap on the clipping opens clipping + scan (Cards: middle third of the image or the "Whole page" button, via `swMedia`).
  - `vhImgSlots`/`vhStoryHtml`: story images next to their paragraph (`alinea`, else year or a clear word from title/caption, else spread evenly); used by the Story view and by Cards.
  - `vhTijdgeest`: renders "Life in …", the assigned images (each with a label by `soort` via `vhKind`: "A drawing from that time") and "Around that time" (max 4 local + 1 national event; a national event in the same year as a local one is dropped; optional `links`).
  - `drawVerhaal`: the chapters, father/mother choice, route bar, "Remarkable relative" asides, certainty and adoption callouts.
- `/* ===== SWIPE` ("Cards" in the UI, button `#swBtn`; CSS under `/* ===== SWIPE` too): full-screen cards that play by themselves, overlay `#sw`.
  - `swSentences`: vhTemplate's sentences sorted by kind (birth, family, death, era) by wrapping `_t` for one call, so the Story view's code stays untouched. New template keys go into `SW_KIND`.
  - `swCardText`/`swCardImgs`: Cards use the card version `verhaal_kaarten` (images placed by `kaart`) when there is one, else the paragraphs of `verhaal`; the first card of a card version is the hook (`hook:true`) and always follows the intro. The Story view never uses them.
  - `swBuild`: cards per ancestor (intro with certainty/adoption chip, birth, occupation, siblings and the children (`SW_KIND` "k"); a separate family card only when there is more than the children, i.e. another partner or a move to another country, a portrait only from media with `soort:"foto"` (a `.sw-por-btn` button: tap opens `mediaView` and pauses, never steps) and small "view document" buttons for scans/documents, own story per paragraph or family, the `vhTijdgeest` block cut into life (the block's `kaarten` via `swLifeCards`, else one card per paragraph; a card with a year at the front (`swFrontYear`: "In 1881", "Na 1880", "Tot 1806") only between birth − `SW_LIFE_BEFORE` and death)/photo/events cards (at most `SW_EV_MAX` events per person, picked by `swPickEvents`: `gewicht`, own place, war years; an event within `SW_ERA_NEAR` years of a "lived through" card joins it; neighbouring events merged up to ~220 characters), a separate "Brothers and sisters" card (then children) when the intro would pass ~200 characters, remarkable relatives with their hook card, lived-through, remarkable relatives, farewell, fork or end). `swPlan` = chosen path + richest continuation.
  - `swFit`/`swSplit`: after showing a card (and on resize, image and font load) it is measured; if it doesn't fit: classes `f1` (smaller photo next to the title), `f2` (smaller title), `f3` (text 17px), then the last paragraphs/sentences move to an extra card with its own bar (`cont:true`); a single paragraph that is still too long is cut word by word (`swMoveWord`, links stay whole, "…" on both sides). Image cards with `soort` krant/scan/document/kaart (`SW_PAPER`, `c.paper`, `data-paper` on the card) are fitted like text cards: whole image (`contain`) on paper, caption below, scroll when tall, 12 s in `swDur`. The fit classes and swFit's inline styles on `.sw-body` must survive the fade-out: `swShow` only swaps the animation classes on the old card (`classList`, never `className=`). `fscroll` (scroll) is only an invisible safety net (scroll inside the card, below the header; the timer waits).
  - `swShow`/`swTick`/`swStep`/`swGen`/`swWire`: player (timer per card, tap left/right (left on a first card = last card of the person before), hold = pause, swipe up/down = generation, arrow keys/space/Esc). Starts at `state.root`; `setLang` calls `swRelang`. The route at the top shows only the generations already travelled (earlier names jump back) plus a quiet "next: …" on the last card.
- Header (CSS under `/* ===== bovenbalk`): the title is "Family tree of {name}" (`titleOf`), built in `render()`; the name is `#rootBtn` and opens `rootPick()` (start people + "find someone else", which opens search with `SEARCH_ROOT` so the pick becomes the start person). Data `titel`/`familienaam` are no longer shown.
- Menu: three modes `.modes` = `#storyBtn` (view `verhaal`), `#swBtn` (opens Cards) and `#treeBtn` (back to `state.lastTree`); the tree views `#tabs` only show outside Story. `render()` sets `aria-pressed` and `#tabs.hidden`.
- Settings bar `#setbar` (`.legwrap`) under the header: `#genWrap` (one slider: `state.gens` 3–12 for Fan/Cosmos, `state.tlGens` 3–14 for Timeline; `initGenSlider`/`GSL_SHOW`), `#colorWrap` (Fan/Cosmos) and `#legend` (plain text). Hidden when empty (Story).
- `/* ===== DATA` → `function prepareData` (also sets the language: `LANG=(d.taal||d.lang)==="nl"?"nl":"en"`), `const VIEWS`, and the `fetch("data.json")` line that `standalone_viewer.py` looks for.

## Releasing a new version

1. Bump the version in three places: `plugins/family-tree-research/.claude-plugin/plugin.json`, the `metadata.version` of `SKILL.md`, and `PLUGIN_VERSION` in `viewer/index.html` (shown in the viewer's footer, "Made with Family Tree Research v…"). Check that they match:
   ```
   V=$(python3 -c 'import json;print(json.load(open("plugins/family-tree-research/.claude-plugin/plugin.json"))["version"])')
   grep -q "version: \"$V\"" plugins/family-tree-research/skills/family-tree/SKILL.md && grep -q "PLUGIN_VERSION=\"$V\"" plugins/family-tree-research/skills/family-tree/viewer/index.html && echo "versions match: $V"
   ```
2. Validate: `claude plugin validate .` (marketplace) and `claude plugin validate plugins/family-tree-research/.claude-plugin/plugin.json`.
3. Commit and push to `main`. Users with "Sync automatically" on get it by themselves.
4. Optional: rebuild the standalone package: `cd plugins/family-tree-research && zip -r -X ../../family-tree-research.plugin README.md .claude-plugin skills -x "*.DS_Store" "*__pycache__*"` (don't commit the .plugin file).

## Gotchas

- `viewer/index.html` loads data with exactly `fetch("data.json").then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()})`; `standalone_viewer.py` searches for that string. Keep it in sync if you change it.
- The viewer's language default lives in two places in index.html: `let LANG="en";` and in `prepareData`: `LANG=(d.taal||d.lang)==="nl"?"nl":"en";`.
- New user-visible viewer text goes into the `I18N` table (both `nl` and `en`), not hard-coded. The EN/NL switch (`langInit`/`setLang`, marked `/* taalswitch */`) re-runs `applyTexts()` and `render()`; anything computed once at load (like `META.titel`) must be recomputed in `setLang` too.
- In the published artifact only images work as media; PDFs only work in the standalone file.
