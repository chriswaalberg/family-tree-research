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
  version: "0.9.82"
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
- **Always keep a GEDCOM, silently.** As soon as there are a few names and no GEDCOM yet, make `source/original.ged` with `gedcom_tool.py new`. The original (made or imported) never changes: every finding is a round file in `rounds/`, and `gedcom_tool.py rebuild` makes `source/tree.ged`, the working file behind the viewer, from the original plus all rounds (see `references/gedcom-tool.md`). Don't ask about it. Only bring up GEDCOM export (e.g. to import into Ancestry) when the user asks for it; then point to the file in `source/`.

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
- **Every link gets a source and a reason.** A source (record with link or location) and one sentence in plain words why the status holds: which record, which place and year, who is named as parent; for *probable* or *possible* also what's missing. It goes in `note` (Dutch `opmerking`; `why`/`waarom` also work) of the `parents`/`status` step, and the viewer shows it as "Why certain:" on the person card. Not "marriage 1840", but "The marriage record (Leiden, 1840) names Jan Bakker, 54, as the groom's father; he was a witness at the baptism too." Someone else's family tree is a signpost to the records, never the only reason for *certain*. `make_viewer_data.py` warns about links without a source or with a short reason; fix a few of those every round.
- **Certain needs a hard link.** *Certain* only when a record names the parents **and** something ties it hard to the person in the tree: an age that fits, the right partner, or the parent as witness or giving consent. Patronymic + naming pattern + the only candidate = *probable*. A real doubt stays out of the tree and goes into the report.
- **Big rounds with helpers.** When the user lets you work on your own for long, split the ancestors without parents by region over parallel research helpers (subagents) that only read and report, also what they didn't find; check every find's key record yourself before it goes into the tree; then the next wave on the new parents. See "A big round" in `references/research.md`.
- Don't actively search archives for **living people** (their records are usually not public anyway). What the user tells you about them simply goes into the tree and the viewer.
- **Search archives with `scripts/archives.py` first** where it covers the place: Open Archives (`oa search/show/scans`), Amsterdam City Archives open data (`saa`) and full text (`transkribus`, also Amsterdam births after 1880), SchiedamGEN (`schiedam`), Erfgoed Leiden (`leiden`) and Sweden's Riksarkivet (`riksarkivet`). It needs no browser, so it works where Chrome is blocked. Known gaps per source are in `references/sources.md`. Search text is machine-read and messy: always read the whole scan yourself before you use a record.
- Record everything: `data/relations.csv` (status + source per parent-child relation), `data/worklog.md` (what you searched, what you found, and what you did *not* find), `reports/questions.md` (open questions and contradictions).
- **One route failing isn't the end.** If the Chrome extension is missing or blocked (often by the user's organisation), switch yourself to your fetch tools, then a shell (`curl` to public APIs), then the browser built into the Claude desktop app; and if an API fails, try the website itself. See "How to reach the archives" in `references/sources.md`. Don't wait for the user to suggest it.
- Can't get in somewhere because of a login, paywall or captcha? Don't work around it. Say so honestly, tell the user exactly what to look up (archive, place, period, name) and ask for a screenshot or photo. Then read it yourself.
- After every round: write the round file, run `gedcom_tool.py rebuild`, rebuild data.json, republish the viewer, and tell in a few sentences what's new and what's next.

**Practical (lessons from long research):**
- **Network work in the foreground.** Archive searches and downloads don't belong in background tasks: there is sometimes no network there, and they hang without an error. Split long harvests into pieces of under ~10 minutes.
- **Links and to-dos for the user go in your last message**, in full, as real URLs. Text written in between often reaches the user shortened, and the links fall away.
- **Check that the Python you use has Pillow** (`python3 -c "import PIL"`). Without it the scripts copy scans and photos at full size instead of shrinking them; use a Python that has it.
- **Scans from the user** go from Downloads to `scans/` in one fixed step: rename, crop, move, link (see "Asking the user for help" in `references/research.md`).

## The Workshop (Claude Code only)

In Claude Code, open the Workshop before the first step of any work on the tree (preparation too: reading reports, planning a round), without asking, and send a note there at once with what you are doing and what comes next. It is: a local page that shows the fan as a night sky and plays live what you search, check, add and reject (`scripts/live.py`, `viewer/live.html`). In the desktop app it goes in the side panel next to the conversation: `live.py launch` (writes the `workshop` entry with the current path and this tree's port), `preview_start`, then load and call `mcp__ccd_view__show_pane` with pane `"preview"`, then check `/ping`: it must name this tree and say `"visible": true`; in a terminal give the user the address. **The Workshop is only open when `/ping` says it is visible** (`live.py status`): running but not in view means the user sees nothing, so show the pane at once. Run the scripts from the tree's folder: events only go to that tree's Workshop. With it open, rebuild the tree and data.json after every confirmed find instead of only at the end of a round, say who you turn to with `live.py focus <id or name>` (the names the user reads in the chat then light up in the sky), send a `live.py note` for work the scripts don't see, a `live.py progress` from long scripts of your own, and give helpers `FTR_WHO=<name>`. Search with the skill's scripts (`archives.py`, `delpher.py`): a project's own search scripts stay silent in the Workshop unless they call `live.emit`. A plugin hook reminds you in every tree folder and says which state the Workshop is in (not running, not in view, in view); the scripts and `note` say it too. A phone can always watch: the phone button in the Workshop shows a QR code (`--local` = this computer only). Never offer or mention it in Cowork or claude.ai. All of it: `references/workshop.md`.

## Viewer

Follow `references/viewer.md`. The viewer is `viewer/index.html` and reads a `data.json` built with `scripts/make_viewer_data.py` (Python standard library only). The data format is in `viewer/DATA-FORMAT.md`. Keep the build options in one settings file, `family-tree.json` (`stamboom.json` in Dutch), and build with `make_viewer_data.py --config family-tree.json`, so every rebuild is the same. Publish index.html + data.json together as an artifact; after changes, only data.json again. Set the viewer language to the user's language (`--lang en` or `--lang nl`); that is the language it opens in. Readers can switch between English and Dutch with the EN/NL switch in the header (remembered per browser, or force it with `?lang=en` / `?lang=nl` in the URL).

## Stories

The viewer has a **Story** view: from the start person step by step back in time, where the reader picks father or mother at every person (choose-your-own-adventure). A gold star marks the richest trail. For most people the viewer writes a text from the data; whoever has more to tell gets their own story in `data/stories.json`.

- **Look for stories yourself.** After every research round, scan the tree for remarkable lives: a place of death in a camp or at sea, war, emigration, the Dutch East India Company or the army, a famous event, an unusual occupation, a sibling with a history of their own. Suggest them actively; don't wait for the user to ask.
- **Ask about family legends** ("we descend from French nobility", "grandpa sailed the seven seas"). Test them against the tree and the archives and tell honestly what holds up, what doesn't, and what's still open.
- Only write a story with sources (listed under the story), name what's uncertain, and invent nothing. Hard things about people long dead (a conviction, a police report, forced labour, a divorce) may go in, factually and with the source; be careful with the living. Siblings with a story appear automatically as "Remarkable relative" with the ancestor.
- **Date what you change.** A round file gets `"date": "2026-11-23 14:35"` (the moment you write it), a story `"bijgewerkt": "…"` whenever you write or edit it, a row in media.csv the `added` column. The viewer's List sorts people by when they came in and last changed; without a date a change doesn't show there.
- **Two layers: `text` to read, `cards` to swipe.** The Story view shows `text`; it may be rich, with paragraphs like in an article. The Cards view plays the story as full-screen cards on a phone, like Instagram Stories, and people drop off most after the first card. So give every story a short card version too, `cards` (blank line = new card). Rules for cards:
  - **Card 1 is a hook**: the most striking fact, or a question, **without a year or age**. Not "X was born on … as the son of …": the intro card already says that. (The viewer places cards by year; a hook with "December 1943" pulls the whole series to 1943.)
  - **One moment per card**, at most ~200 characters (2–3 short sentences).
  - **Year or age at the front** of the card ("In 1953 …", "At sixteen …"); the viewer turns an age into a year.
  - **End a card with a nudge** where you can: a turn or an open question ("Which ship, we don't know yet.").
  - **Leave side matters out**: long lists of children, archive numbers. They stay in `text`.
  - **Invent nothing**; the death sentence may be short.
  - Every story image gets `card` (after which card). The same number of cards in every language.
  - Example of a hook: "An Amsterdam boy who stepped off his ship in Australia and never went back on board. Then he boxed, he drifted, and he was in the papers. That's John."
- **Card budget: at most ~15 cards per person and at most 3 text cards in a row** (counted from that person, with intro, zeitgeist, wars and farewell). Cards with an image, also text on an image, break a run. So: about 5–8 story cards, and an image (`card`) on every third card or so. `make_viewer_data.py` warns when a story alone makes more than 12 cards; the exact count per person, with the run of text and where it is, is in the viewer at the address ending in `#kaartbudget` (or `#cardbudget`). Check it after every round and fix what it marks.
- **Every round: suggest cards for stories that don't have them yet.** Without `cards` the viewer uses the paragraphs of `text` as cards, and a long paragraph gets cut mid-sentence with "…". `make_viewer_data.py` names those stories ("consider writing cards").
- **Give the surname line its stories too.** Not only remarkable lives: also write a story for every generation of the user's own name line (and other main lines) for which the research already holds records. Ordinary lives become vivid from what the records say: occupations, ages, addresses, signatures, witnesses, a child born before the wedding, a remarriage to a sister-in-law. Read the research reports and work logs first; most of the material is already there.
- **Ask what the family knows.** Occupations, a family shop, where they lived, nicknames, what grandma used to tell. One detail ("he was a milkman, they had a dairy shop") brings a story to life and is in no archive. Record it as a source: "<name> (own knowledge, <date>)".
- **Never address the reader as a descendant.** No "your line", "your surname", "to you": you don't know who reads it, and from another start person it's wrong. Write "this family tree", "the line", "this branch", "the generations after him". Interface text ("whose story do you follow?") is fine.
- Images with a story: search for 2–4 per story, but only use an image that fits a concrete moment in the story, in place and time (see "Finding images" below). Say so in the caption when it isn't the person themselves ("this is not <name> himself").
- **A newspaper the story leans on is shown, not only cited.** Every newspaper item quoted in `text`, or that a sentence rests on (an advert, an announcement, a court report), goes into the story as a clipping: a story image with `"soort": "krant"`, `alinea`, `card` and a `bron` with the link to the article. Other finds about the same matter (more adverts, job ads, New Year wishes) don't go into the story: link them to the person as `document` via `data/media.csv`, so they show as small clickable images under "Photos and documents" and the story and the cards don't get longer. `make_viewer_data.py` warns when a story cites a newspaper without a clipping ("this story cites a newspaper without a clipping").
- Write stories in the user's language. See `references/viewer.md` ("Stories") for the format.

## Zeitgeist: how did they live?

For each place where many ancestors lived, build a zeitgeist (`zeitgeist/zeitgeist.json`, format in `viewer/DATA-FORMAT.md`, "Zeitgeist"): a few paragraphs about daily life per period, local events with year and source (storms, disasters, epidemics, war, buildings, notable incidents) and old prints, drawings or photos of the place. The viewer links it automatically to everyone who lived there at the time, only for the years they provably lived there: birth, baptism, `RESI` (residence), marriages and the births of their children in that place, never after death. So record moves as `RESI` with date and place (from population registers, for example) when you find them; without them someone born in Rotterdam who moved to Amsterdam as a child only gets Rotterdam for their first few years. Record a stay abroad too (`EVEN` with `TYPE Emigratie`/`Emigration`, `EMIG`, or a `RESI` abroad; an uncertain date like `AFT 1952` is fine): in those years the viewer shows nothing of the home country, so no flood of 1953 for a sailor who was in Australia.

- **Two layers for daily life, as with stories.** `tekst` is for the Story view and may be rich. `kaarten` (blank line = new card) is the short version for Cards: 2–4 cards per block. Card 1 is a hook (the most striking thing about life there, no year); then **one picture of daily life per card**, at most ~200 characters, concrete: numbers, places, objects ("Drinking water from the canal, where the waste went too."). A card about one moment starts with its year ("In 1881 the first tram …", "After 1880 …"): Cards then only show it to people alive then (from 10 years before birth). A card about the whole period has no year at the front. Without `kaarten` every paragraph of `tekst` becomes a card. `make_viewer_data.py` warns about cards over 250 characters and blocks without cards that have a paragraph over 350 characters; suggest cards for those every round.
- In Cards a zeitgeist image becomes the background of a life card, and a story image the background of the card it follows, with the text over it (clippings, scans, documents and maps stay separate). Prefer images that still read with text over the lower half; the long caption only shows in the Story view, so put "this is not <name> himself" in the title or keep it short.
- Cards show at most 3 events per person; give the events that matter most for the family `"gewicht": 1` or higher (a flood that hit their street, the war), and minor ones nothing.
- Start with the place with the most ancestors. Search local history sites, monument registers, museum collections and lists of disasters; give a source for every event and invent nothing.
- Images: at least 4–6 per place, spread over the centuries the family lived there. How to find, check and process them: "Finding images (generously)" below.
- Old newspapers bring places and businesses to life. Delpher (the Netherlands) can be searched directly with `scripts/delpher.py` (see `references/sources.md`); if a newspaper site is blocked, ask the user for screenshots of search results.
- See `references/viewer.md`, "Zeitgeist".

## Finding images (generously)

Images make the stories and the zeitgeist come alive, so searching for them is a fixed step in every round, not an extra. Better a well-chosen print of the village church than an empty chapter.

**Targets**
- Per own story: **search for 2–4 images**. That is a search target, not a quota: no good image, then no image. Think of the occupation (a smith at work, a dairy shop), the town or street, an event from the story (a flood, a ship, a fire), the church or village, the ship or factory.
- **Newspaper clippings are good story images, and required ones when the story leans on the paper** (Delpher, Trove, family papers): an announcement, an advert, a court report, a sports result. Every newspaper item quoted in the text or that a sentence rests on becomes a story image (`"soort": "krant"`, `alinea`, `card`, `bron` with the link); further finds about the same matter go to the person as `document` via `media.csv` (see "Stories" above). Crop to the heading and the relevant paragraph only, and say in the caption that it was shortened.
- **Cutting a Delpher clipping:** `scripts/delpher.py` searches (`search`), reads the OCR text (`text`), and makes a wide crop around a word with a ruler and a faint grid in page pixels (`locate <article urn> "<name>"`). Look at that crop at true size, read the edges off the grid's numbers (from the rule above the heading to the rule below the last relevant line, inside the column rules; the numbers, never the image's own pixel positions: the crop has a 70 px margin, so pixel positions come out ~70 px too far right and down), then cut exactly that box (`cut <urn> x0,y0,x1,y1 --out … --check`) and look at the check: the box in red, everything outside it veiled, so you see exactly what is cut. Then look at the result: letters cut off at an edge, or a strip of the neighbouring advert, means another try with a few pixels more or less. Don't let a script guess the edges between separator lines: that proved unreliable. `cut` enlarges narrow clippings to 1000 px wide. Keep clippings at least ~1000 px wide (don't shrink them further): on a phone the Cards view shows the whole clipping at full width, and small print must stay readable. If the full scan hangs in the tree (an `OBJE` of that person), always point to it with `"scan": "<path as in the GEDCOM>"`: a tap on the clipping then opens the whole page, and the scan isn't shown twice. Old newspapers are usually public domain; check the archive's terms.
- Per zeitgeist place: **at least 4–6 images**, spread over the centuries the family lived there: roughly one every 30–50 years.
- Big events (a siege, a flood, a famine, a war): an image with `"gebeurtenis": true`, so it only appears with people alive then. Images about children get `"kind": true`: a famine photo of children then lands with the ancestor who was a child at the time (see `viewer/DATA-FORMAT.md`).

**Story images: same place, same time**
Every story image belongs to one concrete moment in the story, and fits it in **place** (the same town, or the occupation or event from that paragraph) **and time** (rule of thumb: within ~15 years of that moment). A wider gap only for buildings that still stood the same way then: the caption says so ("the church looked like this when he was baptised there in 1802") and the image gets `"stond_er_al": <year built>` (e.g. `1653`), which turns the dating warning off. The same goes for a later drawing of something that already existed then, like a coat of arms (`"stond_er_al": <year it existed>`). Every story image gets `alinea`: the paragraph it belongs to (and `card`, the card it belongs to, when the story has cards). If you can't point to a paragraph, the image doesn't belong in the story (perhaps in the zeitgeist of the place). `make_viewer_data.py` warns when a dating falls outside birth − 10 to death + 10 or when `alinea` is missing or doesn't exist.

**Every round**
1. First count which stories and places have 0–1 images, and fill those first. (Count in `data/stories.json` and `zeitgeist/zeitgeist.json`: the `beelden`/`images` lists per story and per place.)
2. Make search terms per story and place: occupation, place, event, year (e.g. "smid", "Katwijk strand", "watersnood 1861", "Den Helder 1955"), in the language of the country.
3. Search in the order of "Images" in `references/sources.md`: Rijksmuseum, Wikimedia Commons, Dutch National Archives (Anefo, Van de Poll), regional image banks; abroad national museums and libraries, and Commons.
4. In the final report of the round, give per story and per place the number of images.
5. Close the round with a check, card by card (Story view or Cards): does every image fit the text just before it, in place **and** time? If not, move it (`alinea`, `card`) or drop it. Fix every warning from `make_viewer_data.py`.

**Check before you use**
- Only public domain or CC0, or CC BY / CC BY-SA with the maker's name and the licence in `maker`. Read the licence in the object record itself (museum record, Commons `extmetadata`), never assume it.
- No images under copyright, and no photos of recognisable private people found on the internet. (The user's own family photos are fine: see "Photos and documents".)
- Don't link to pages where the image can't actually be seen.

**Processing**
- Crop away borders, mounts (passe-partouts), rulers, colour charts and the rest of a book page, so only the image remains (Pillow if available; IIIF regions for small drawings on a large mount: `…/pct:x,y,w,h/1400,/0/default.jpg`).
- At most ~1400 px on the long side, JPEG, a tidy file name (`katwijk-strand-1660.jpg`, `smid-aan-het-werk-1890.jpg`).
- Then make a contact sheet of all new images (one image with thumbnails) and **look at it yourself**: crooked crops, leftover borders, the wrong image, a near-duplicate.

**Always fill in per image**
`titel`, `maker`, `datering`, `soort` (`foto`, `tekening`, `prent`, `schilderij`, `kaart`, `munt`, `affiche` or `krant`, from the museum record, not from the caption), `bron` (`[label, url]`) and a `bijschrift` (caption) in the user's language. The caption explains the link with the person or place, and says so when it is another place ("this is Dordrecht, not Zwijndrecht itself, but the market looked like this here too"). Zeitgeist images also get `van`/`tot`/`jaar`. Story images always get `alinea` (the paragraph they belong to, 1-based), so the clipping about boxing sits next to the paragraph about boxing.

## Raised, adopted, foster

If the user says a parent wasn't the biological parent but raised the child as their own (or in case of adoption or foster care): record it with the `type` column in `relations.csv` (`raised`, `adopted`, `foster`). First ask how openly the user wants this shown in the viewer (the viewer may be shared with family). The viewer then shows the relation as a double gold line, hatches the family above it in the Fan view ("family by adoption") and tells it with warm words in the Story view. An unknown biological parent simply stays empty.

## Photos and documents

Users may add photos, scans of records and other documents per person. They're stored in the GEDCOM as standard `OBJE`/`FILE` links (so they also work in other genealogy programs) and appear in the viewer under "Photos and documents" for that person.

- Files belong in the connected folder: records in `scans/`, family photos in `photos/`. Let the user put them there (or in Downloads; then move them), with who's in it in the file name.
- Linking: one row per file in `data/media.csv`, with the moment in the `added` column (`2026-11-24 09:15`) → `gedcom_tool.py media` (see `references/gedcom-tool.md`). A scan you read yourself and used as a source: link it right away too. A good photo of the person themselves (a portrait, a wedding photo): put `yes` in the `portrait` column, so it becomes the polaroid at the top of their block in Story; without it the first photo is used.
- Viewer: `make_viewer_data.py … --media-dir viewer/media` copies and publishes them (see `references/viewer.md`).
- **Crop screenshots first.** If an image is a screenshot, cut away all browser and system chrome before linking: tab bar, address bar, menu bar, Dock, buttons and toolbars of the archive viewer. Only the record or photo remains. Set the original aside first (e.g. `_to_delete/originals-with-browser-chrome/`), crop (Pillow), and look at the result. An archive header line with the source reference is not browser chrome; keep it unless the user wants otherwise.
- **Privacy:** photos of living people only if the user wants that; they'll be in the (private) artifact. Ask at the first photo of a living person.

## What's in this skill

| file | what for |
|---|---|
| `references/onboarding.md` | Question order for new users, intake.json format |
| `references/gedcom-export.md` | Downloading a GEDCOM per platform (Ancestry, MyHeritage, FamilySearch…) |
| `references/research.md` | Method, rules of evidence, statuses, plausibility, privacy |
| `references/sources.md` | Archives per country, `archives.py` per source with its gaps, what's often blocked, where to find free images |
| `references/gedcom-tool.md` | Round files and `rebuild` (adding, correcting, removing wrong links, merging), check report, media |
| `references/viewer.md` | Building data.json, publishing, updating, stories, zeitgeist |
| `references/workshop.md` | The Workshop (Claude Code only): opening it in the side panel, `note`, `progress`, helpers, phone |
| `references/folders-and-files.md` | Folder layout (English/Dutch), progress template, where scripts run |
| `scripts/gedcom_tool.py` | `new` / `rebuild` / `add` / `check` / `media` |
| `scripts/make_viewer_data.py` | GEDCOM (+CSV, +regions, +stories, +zeitgeist, +coordinates, +media) → data.json |
| `scripts/geocode_places.py` | GEDCOM (+stories) → coordinates per place (Nominatim, cached, manual fixes stay) for the maps |
| `scripts/standalone_viewer.py` | Viewer + data (+ media) in one standalone HTML file |
| `scripts/archives.py` | Archives without a browser: Open Archives (search, show, scans), Amsterdam open data and Transkribus, SchiedamGEN, Erfgoed Leiden, Riksarkivet |
| `scripts/live.py` | The Workshop: `serve` (local page, watches data.json), `launch`, `status`, `note`, `focus`, `progress` |
| `scripts/delpher.py` | Delpher newspapers: `search`, `text`, `locate` (crop with ruler) and `cut` (the clipping) |
| `viewer/index.html`, `viewer/DATA-FORMAT.md` | The viewer and the data format |
| `viewer/live.html` | The Workshop page (served by `live.py`, never published) |
| `examples/` | Mini family tree (7 people) and `regions-basic.json` |

## At the end of every session

Update the progress file (status, agreements, next steps, open questions) so a next session can continue without explanation. With an attached project: put a copy there too. Close with: what was found, the link to the viewer, and what you'll do next time or need from the user.
