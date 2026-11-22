# The Workshop: watch the tree grow while you research (Claude Code only)

The Workshop is a local page (`viewer/live.html`, served by `scripts/live.py`) that shows the start person's ancestors as a night sky and plays every change live. It opens in the **Cosmos**: every ancestor a star in a fixed place (father's side left, one orbit per generation), constellation lines from child to parent in the colour of their certainty, missing parents as hollow ghost stars; names up to the great-grandparents, a tap on any star shows who it is. A switch at the top shows the same as a **Fan** (slices with names, open questions as empty slices); every browser remembers its choice. In both: a scanner beam turns to the person being searched, new ancestors fly in from their source, a rejected link cracks, a link that became certain turns gold, open questions (`?`) breathe in the empty slots, and a log says in plain words what you are doing.

**Only in Claude Code**, where scripts run on the user's own computer. Never offer it in Cowork or claude.ai: the published viewer is an artifact and can't reach the user's computer. Don't mention it there at all.

## Open it at the start of research

In Claude Code, before the first research round of a session (or a check of an imported tree), open the Workshop without asking. It is part of the experience, like the first viewer.

Every tree has its own Workshop. Several can run at once (two family trees, or a test tree next to the real one), each on its own port; opening one that already runs reuses it.

**The Claude desktop app (a browser pane is available, tools named like `preview_start`)**, every time, in this order:

1. From the tree's folder: `python3 -I <skill>/scripts/live.py launch --config family-tree.json`. It writes the `workshop` entry in that folder's `.claude/launch.json` with the live.py of the current plugin version (a plugin update moves the path) and this tree's own port (its running Workshop's port, else a free one). Other entries stay. Never write that entry by hand.
2. `preview_start` with `name: "workshop"`.
3. Show the side panel: `show_pane` with `pane: "preview"` (the pane can be hidden after `preview_start`).
4. Check that it is **this** tree: `curl -s http://127.0.0.1:<port>/ping` must name this tree's data.json, and `tabs_context` (or a screenshot) shows the tab "Werkplaats · <start person>" / "Workshop · <start person>". Close tabs of another tree's Workshop in the pane (`tabs_close`). Only then tell the user it's there.

**The terminal (no browser pane)**: from the tree's folder, start `python3 -I <skill>/scripts/live.py serve --config family-tree.json` as a background task and give the user the address it prints. If this tree's Workshop already runs, it prints that address and stops.

`--config` reads the same settings file as `make_viewer_data.py` (`--data data/data.json` also works). data.json must exist: build the first viewer before you open the Workshop.

**Run the scripts from the tree's folder.** Events go only to the Workshop of the tree you are in: the one whose folder holds the current folder (for `rebuild` and `check`: the file they write or read). From elsewhere nothing arrives (never in another tree's Workshop); `note`/`progress` take `--tree <folder>`, other scripts `FTR_TREE=<folder>` in front.

Say in one sentence what it is: "Next to our conversation you can now watch your tree grow while I search."

## What reports by itself

While a Workshop runs, these send what they do without anything extra:

- `archives.py` (every search, record and scan download; the number of hits for Open Archives) and `delpher.py` (search, text, clipping);
- `gedcom_tool.py check` (the scanner sweeps the whole fan, every person gets a ✓, then each "worth a look" lights up amber on that person) and `rebuild` (round processed, plus every **new** step of the last round that data.json can't show: notes, also "searched, nothing found", events such as a baptism or burial, removed events, other names, place names; steps it has shown before are not repeated);
- **every new data.json**: the page compares it with the previous one and animates the difference (new people, links added or removed, certainty changed, a source or reason added to a link, names, dates, occupations, new or updated stories, photos, life and times per place). Many changes at once (a round of 200 reasons) become one line and light up together. A bar under the counters shows how many links are certain, probable, possible and not checked, so verification shows as progress too. This is the heart of it: what you see is always the real tree.

When no Workshop runs, all of this does nothing (one quick file check).

## Make it live: rebuild per find

The fan only moves when data.json changes. With the Workshop open, don't wait for the end of a round: as soon as a find is confirmed (you read the record yourself), add its steps to the round file, run `rebuild` and `make_viewer_data.py --config family-tree.json`. Both take a second. The round file grows during the round; that's fine, `rebuild` replays it.

## Say who you are working on: `focus`

The user reads names in the chat ("Now Jan de Vries: first I check who Griet Bakker is"); the Workshop should show the same. **Every time you turn to a person**, before you search for them:

```
python3 -I scripts/live.py focus "Jan de Vries" "his marriage around 1946"
```

A GEDCOM id (`I87`) is surest; a name works too. It puts a ring and the name at that person's star (in the helper's colour, one per helper) and a line "Working on" above the log; it stays until your next focus or two minutes. Someone without a star of their own (a wife, a brother, a child who is not an ancestor) shows at their nearest relative in the fan, with the relation: "Griet Bakker · wife of Jan de Vries".

Searches with a name (`archives.py`, `delpher.py`, `note --person`, `progress --person`) do this by themselves. Names are recognised the way genealogists search them: spelling variants (Marritje = Maritje = Marretje, IJ = Y, double letters), a surname with a first name, two given names or a patronymic ("Grietje Jans"), or a surname that only one person in the fan has; years in the search pick between namesakes. A name nobody in the tree has (yet) just shows in the log.

## Tell what you do: `note` and `progress`

For work the scripts don't see (reading a web page, a screenshot from the user, thinking about a candidate), one line:

```
python3 -I scripts/live.py note "Reading the baptism register of Leiden, 1802" --kind read --person I87
python3 -I scripts/live.py note "Is this Jan your great-grandfather? See the question in the chat" --kind ask --person I87
```

Kinds: `note` (default), `read`, `found`, `nothing` (searched and found nothing: say where and which years, e.g. "Burial registers Göteborg 1760-1777 read in full: no Lindqvist"; the person's slot greys out briefly; a negative result is research too), `ask` (a red callout on that person: use it when you ask the user something). `--person` is a GEDCOM id or a name; the beam turns there. Write the text in the user's language. Don't narrate every step: one line per real step is enough.

**A long script of your own** (checking 123 families, harvesting an index) shows a progress bar with time left. Send the progress every step, with the person or family being checked:

```
python3 -I scripts/live.py progress "side branches" 42 123 --person I87 --text "family Bakker-Smit"
```

From inside a Python script, load `emit` once instead of starting a process per step:

```python
import importlib.util
spec = importlib.util.spec_from_file_location("ftr_live", "<skill>/scripts/live.py")
live = importlib.util.module_from_spec(spec); spec.loader.exec_module(live)
live.emit("progress", task="side branches", done=42, total=123, person="I87")
```

Only the start and the end of a task go into the log; the bar follows every step. Reading scans page by page (a burial register, a parish book, alone or with reading helpers) is such a task too: `progress "Göteborg burials 1752-1767" 23 50 --person <whose parents you look for>`.

## Helpers (subagents)

Give every research helper a short name and let it put `FTR_WHO=<name>` in front of its commands (`FTR_WHO=Noord-Holland python3 -I scripts/archives.py oa search …`). Each name gets its own coloured beam in the fan, labelled with that name, so five helpers are five beams searching at once. Put this in the helper's brief.

## On a phone

Always available: the Workshop also listens on the Wi-Fi. The user taps the **phone button** at the top of the Workshop on the computer; it shows a QR code to point the phone's camera at (no typing; the address is worked out on every tap, so it follows the laptop to another network). Mention it once when you open the Workshop: "Tap the phone button to watch on your phone." The first time, macOS may ask whether Python may accept incoming connections: the user clicks Allow, or the phone can't connect. `--local` (on `launch` or `serve`) keeps it to this computer, only when the user asks for that.

The address carries a secret key, because the Workshop is reachable for everyone on that network (an office, a train, a café). Without the key nobody else sees anything, and only this computer can send events. The key is fixed per tree (kept in `~/.config/family-tree-research/workshop-keys.json`, never in the tree's folder) and the phone remembers it for 30 days, so it is needed once: after that a bookmark works, also after a restart. The QR code needs the internet once (a small library from cdnjs); without it the dialog shows the address to type.

## In the page

- The name in the title picks the start person (from the start people, or search by name); every browser remembers its own choice.
- Cosmos and Fan show as many generations as the start person's tree has, plus one orbit/ring of open questions; they grow one when you get a generation further.
- Counters: people, links (parent-child), open questions (missing parents up to generation 9, as in `check`), sources (links with a source).
- "Viewer ↗" opens the normal viewer from the same server.
- EN/NL switches the language, like in the viewer, and the choice is shared with it (same browser, same key `stamboomLang`). Without a choice it opens in the tree's language (`taal` in data.json, set from the language the user talks in); `?lang=en`/`?lang=nl` in the address wins.
- The replay button (⟲) plays the whole session again, from the tree as it was when this Workshop started: every search, note, check and round with the same animations, with pause, 1×/2×/4× and "Back to live". The server keeps it in memory until the Workshop stops (every data.json version, compressed); a new start begins a new session. Point the user to it after a long or overnight round: "press ⟲ to watch what happened while you were away".
