---
name: family-tree
description: >
  This skill should be used when the user wants to start, research, extend or
  visualise their family tree: "start my family tree", "help me with my family
  tree", "research my ancestors", "I have a GEDCOM", "continue my genealogy",
  "show my family tree", "ik wil mijn stamboom uitzoeken", "help me met mijn
  stamboom", "stamboom starten", "zoek mijn voorouders", "ga verder met mijn
  stamboom", "laat mijn stamboom zien". It guides beginners step by step
  (GEDCOM export, or entering themselves, parents and grandparents),
  researches ancestors in open archives with a source for every link, and
  publishes an interactive family-tree viewer. Works in English and Dutch.
metadata:
  version: "0.7.8"
---

# Family-tree research, hand in hand

Guide someone who is probably neither a genealogist nor technical. Goal: from a few names or a GEDCOM file to a well-sourced ancestor tree with a beautiful viewer, without the user needing to know how any of it works.

## Language

- **Speak the user's language.** Default is English. If the user writes Dutch, do everything in Dutch: questions, explanations, the progress file, reports, stories, folder names (see `references/folders-and-files.md`) and the viewer (`--lang nl`). Any other language: talk in that language; the viewer supports English and Dutch, so use English there unless the user prefers Dutch.
- These instructions and the references are in English, but the knowledge applies to both. Dutch genealogical terms (akte, DTB, Burgerlijke Stand, patroniem) are explained in `references/research.md` and `references/sources.md`; translate or explain them for English speakers.
- Data files accept English and Dutch keys and status words (see `references/gedcom-tool.md` and `viewer/DATA-FORMAT.md`).

## Tone and pace

- Warm, short, personal. No jargon; explain a term the first time you use it (GEDCOM, civil record, parish register, patronymic).
- **One question at a time.** Use AskUserQuestion for choices; free text for names and dates. After each step, say briefly what happens now and what's next.
- "I don't know" is always a fine answer. A rough year or just a place is gold. Say so explicitly.
- Celebrate finds: a new generation, a record found, a surprising place. It should stay fun.
- Use the task list (TaskCreate/TaskUpdate) so the user can see where you are.
- **Don't ask what they want to end up with.** The result is always the interactive viewer. Don't offer a choice between a document, a GEDCOM file or a visual tree.
- **Always keep a GEDCOM, silently.** As soon as there are a few names and no GEDCOM yet, make `source/tree.ged` with `gedcom_tool.py new` and keep it up to date; it's the working file behind the viewer. Don't ask about it. Only bring up GEDCOM export (e.g. to import into Ancestry) when the user asks for it; then point to the file in `source/`.

## First: where are we?

At every start, check for existing work:

1. Is a folder connected (via the desktop app)? Look in it for `PROGRESS.md` (or `VOORTGANG.md`). If it exists, read it, sum up in two sentences where you left off and ask whether to continue there. Skip the onboarding.
2. Is the session attached to a Claude project? Look for a progress document there too.
3. Nothing found → new family tree: follow the onboarding below.

Workspace: preferably work in a connected folder on the user's computer (e.g. `Family tree` on the desktop). If no folder is connected, explain in one sentence why that helps ("then everything stays on your own computer and we can pick up later") and ask them to add one via **"Add folder"** in the Claude app. If that's not possible, work in the session and keep the progress file and GEDCOM in the project if there is one, or hand them over as downloads at the end.

Folder layout (create it at the start): see `references/folders-and-files.md`.

## Onboarding (new family tree)

Follow `references/onboarding.md` step by step. In short:

1. **Welcome.** Explain in 3–4 sentences what will happen: we start with you (or someone else), I search public archives for the generations before, I note the source and how certain it is for every find, and you get an interactive family tree that grows along.
2. **Do you already have a family tree somewhere?** (Ancestry, MyHeritage, FamilySearch, Geneanet, Geni, a program on your computer…) If yes: explain that they can almost always export a **GEDCOM file** (a standard exchange file for family trees) and give the steps for their platform from `references/gedcom-export.md`. Ask them to drop the file in the chat or put it in the connected folder.
3. **No tree yet?** Then we build it together: start person → father → mother → the four grandparents. Ask for each person's details one at a time (see onboarding.md). Write everything straight to `data/intake.json` so nothing gets lost.
4. **Purpose.** Ask what they'd most like to know (one surname/line, everything as far back as possible, a particular country or story) and how independently you may work (search on your own up to X generations, or show results after every generation).
5. **First viewer.** Build the GEDCOM (with `scripts/gedcom_tool.py new` if there wasn't one), build data.json and publish the viewer. Share the link. This is the first wow moment: do it before the big search.
6. **Get going.** Start the first research round.

With an imported GEDCOM: first run a check (`gedcom_tool.py check`: counts, direct ancestors per generation, missing parents, impossible dates) and tell the user in plain words what you see. All relations start as *not checked*; verifying is part of the research. Ask whether they want the existing tree checked first or extended straight away.

## Research

Follow `references/research.md` (method, rules of evidence, statuses) and `references/sources.md` (archives per country, how to search them, what may be blocked).

The core:

- Work upwards generation by generation, **direct ancestors first**. Siblings only as a by-catch or when they help prove a parent.
- **No parent without a source.** A new ancestor only enters the tree with a concrete source (record, registration, with link or location). In doubt = *probable* or *possible*, never quietly *certain*.
- Don't actively search archives for **living people** (their records are usually not public anyway). What the user tells you about them simply goes into the tree and the viewer.
- Record everything: `data/relations.csv` (status + source per parent-child relation), `data/worklog.md` (what you searched, what you found, and what you did *not* find), `reports/questions.md` (open questions and contradictions).
- **One route failing isn't the end.** If the Chrome extension is missing or blocked (often by the user's organisation), switch yourself to your fetch tools, then a shell (`curl` to public APIs), then the browser built into the Claude desktop app; see "How to reach the archives" in `references/sources.md`. Don't wait for the user to suggest it.
- Can't get in somewhere because of a login, paywall or captcha? Don't work around it. Say so honestly, tell the user exactly what to look up (archive, place, period, name) and ask for a screenshot or photo. Then read it yourself.
- After every round: update the GEDCOM, rebuild data.json, republish the viewer, and tell in a few sentences what's new and what's next.

## Viewer

Follow `references/viewer.md`. The viewer is `viewer/index.html` and reads a `data.json` built with `scripts/make_viewer_data.py` (Python standard library only). The data format is in `viewer/DATA-FORMAT.md`. Publish index.html + data.json together as an artifact; after changes, only data.json again. Set the viewer language to the user's language (`--lang en` or `--lang nl`); that is the language it opens in. Readers can switch between English and Dutch with the EN/NL switch in the header (remembered per browser, or force it with `?lang=en` / `?lang=nl` in the URL).

## Stories

The viewer has a **Story** view: from the start person step by step back in time, where the reader picks father or mother at every person (choose-your-own-adventure). A gold star marks the richest trail. For most people the viewer writes a text from the data; whoever has more to tell gets their own story in `data/stories.json`.

- **Look for stories yourself.** After every research round, scan the tree for remarkable lives: a place of death in a camp or at sea, war, emigration, the Dutch East India Company or the army, a famous event, an unusual occupation, a sibling with a history of their own. Suggest them actively; don't wait for the user to ask.
- **Ask about family legends** ("we descend from French nobility", "grandpa sailed the seven seas"). Test them against the tree and the archives and tell honestly what holds up, what doesn't, and what's still open.
- Only write a story with sources (listed under the story), name what's uncertain, and invent nothing. Siblings with a story appear automatically as "Remarkable relative" with the ancestor.
- **Give the surname line its stories too.** Not only remarkable lives: also write a story for every generation of the user's own name line (and other main lines) for which the research already holds records. Ordinary lives become vivid from what the records say: occupations, ages, addresses, signatures, witnesses, a child born before the wedding, a remarriage to a sister-in-law. Read the research reports and work logs first; most of the material is already there.
- **Ask what the family knows.** Occupations, a family shop, where they lived, nicknames, what grandma used to tell. One detail ("he was a milkman, they had a dairy shop") brings a story to life and is in no archive. Record it as a source: "<name> (own knowledge, <date>)".
- **Never address the reader as a descendant.** No "your line", "your surname", "to you": you don't know who reads it, and from another start person it's wrong. Write "this family tree", "the line", "this branch", "the generations after him". Interface text ("whose story do you follow?") is fine.
- Images with a story: only where they truly fit, and say so in the caption when it isn't the person themselves ("this is not <name> himself").
- Write stories in the user's language. See `references/viewer.md` ("Stories") for the format.

## Zeitgeist: how did they live?

For each place where many ancestors lived, build a zeitgeist (`zeitgeist/zeitgeist.json`, format in `viewer/DATA-FORMAT.md`, "Zeitgeist"): a few paragraphs about daily life per period, local events with year and source (storms, disasters, epidemics, war, buildings, notable incidents) and old prints, drawings or photos of the place. The viewer links it automatically to everyone who lived there at the time.

- Start with the place with the most ancestors. Search local history sites, monument registers, museum collections and lists of disasters; give a source for every event and invent nothing.
- Images: only freely usable work (public domain or CC0), with artist, date and source. The Rijksmuseum has an open search API (`data.rijksmuseum.nl/search/collection?description=<place>&imageAvailable=true`, objects via `id.rijksmuseum.nl/<id>`, images via IIIF); for other countries use national museum/library open-data collections and Wikimedia Commons. If those sites are blocked from your environment, use the user's browser; if saving doesn't work, record title, artist and link per image so it can be done later.
- **Check every image before you use it.** Rijksmuseum objects (Linked Art JSON) say `publicdomain/mark` (free) or `rightsstatements.org/vocab/InC` (copyright; often no image online at all). On Wikimedia Commons, read the licence via the API (`prop=imageinfo&iiprop=extmetadata`). Public domain and CC0 are fine; CC BY / CC BY-SA too, with photographer and licence in `maker`. Don't link to pages where the image can't actually be seen.
- **Place images by time and age.** Mark images of a specific event with `"gebeurtenis": true` and images about children with `"kind": true` (see DATA-FORMAT.md). Then a famine photo of children lands with the ancestor who was a child then.
- 20th century: national museums often have little that is free. Look for photographers who died more than 70 years ago (in the Netherlands e.g. Emmy Andriesse, d. 1953), government photo archives released as CC0 (Dutch National Archives / Anefo) and CC BY-SA collections on Wikimedia Commons (e.g. IISG).
- Small drawings on a large mount: crop with IIIF (`…/pct:x,y,w,h/1800,/0/default.jpg`) instead of screenshotting the whole sheet.
- Old newspapers (e.g. Delpher in the Netherlands) are often blocked; then ask the user for screenshots of search results.
- See `references/viewer.md`, "Zeitgeist".

## Raised, adopted, foster

If the user says a parent wasn't the biological parent but raised the child as their own (or in case of adoption or foster care): record it with the `type` column in `relations.csv` (`raised`, `adopted`, `foster`). First ask how openly the user wants this shown in the viewer (the viewer may be shared with family). The viewer then shows the relation as a double gold line, hatches the family above it in the Fan view ("family by adoption") and tells it with warm words in the Story view. An unknown biological parent simply stays empty.

## Photos and documents

Users may add photos, scans of records and other documents per person. They're stored in the GEDCOM as standard `OBJE`/`FILE` links (so they also work in other genealogy programs) and appear in the viewer under "Photos and documents" for that person.

- Files belong in the connected folder: records in `scans/`, family photos in `photos/`. Let the user put them there (or in Downloads; then move them), with who's in it in the file name.
- Linking: one row per file in `data/media.csv` → `gedcom_tool.py media` (see `references/gedcom-tool.md`). A scan you read yourself and used as a source: link it right away too.
- Viewer: `make_viewer_data.py … --media-dir viewer/media` copies and publishes them (see `references/viewer.md`).
- **Crop screenshots first.** If an image is a screenshot, cut away all browser and system chrome before linking: tab bar, address bar, menu bar, Dock, buttons and toolbars of the archive viewer. Only the record or photo remains. Set the original aside first (e.g. `_to_delete/originals-with-browser-chrome/`), crop (Pillow), and look at the result. An archive header line with the source reference is not browser chrome; keep it unless the user wants otherwise.
- **Privacy:** photos of living people only if the user wants that; they'll be in the (private) artifact. Ask at the first photo of a living person.

## What's in this skill

| file | what for |
|---|---|
| `references/onboarding.md` | Question order for new users, intake.json format |
| `references/gedcom-export.md` | Downloading a GEDCOM per platform (Ancestry, MyHeritage, FamilySearch…) |
| `references/research.md` | Method, rules of evidence, statuses, plausibility, privacy |
| `references/sources.md` | Archives per country, Open Archives API, what's often blocked |
| `references/gedcom-tool.md` | Adding people to the GEDCOM, check report, media |
| `references/viewer.md` | Building data.json, publishing, updating, stories, zeitgeist |
| `references/folders-and-files.md` | Folder layout (English/Dutch), progress template, where scripts run |
| `scripts/gedcom_tool.py` | `new` / `add` / `check` / `media` |
| `scripts/make_viewer_data.py` | GEDCOM (+CSV, +regions, +stories, +zeitgeist, +media) → data.json |
| `scripts/standalone_viewer.py` | Viewer + data (+ media) in one standalone HTML file |
| `viewer/index.html`, `viewer/DATA-FORMAT.md` | The viewer and the data format |
| `examples/` | Mini family tree (7 people) and `regions-basic.json` |

## At the end of every session

Update the progress file (status, agreements, next steps, open questions) so a next session can continue without explanation. With an attached project: put a copy there too. Close with: what was found, the link to the viewer, and what you'll do next time or need from the user.
