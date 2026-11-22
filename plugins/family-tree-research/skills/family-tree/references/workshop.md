# The Workshop: watch the tree grow while you research (Claude Code only)

The Workshop is a local page (`viewer/live.html`, served by `scripts/live.py`) that shows the start person's round Fan as a night sky and plays every change live: a scanner beam turns to the person being searched, new ancestors fly in from their source, a rejected link cracks, a link that became certain turns gold, open questions (`?`) breathe in the empty slots, and a log says in plain words what you are doing.

**Only in Claude Code**, where scripts run on the user's own computer. Never offer it in Cowork or claude.ai: the published viewer is an artifact and can't reach the user's computer. Don't mention it there at all.

## Open it at the start of research

In Claude Code, before the first research round of a session (or a check of an imported tree), open the Workshop without asking. It is part of the experience, like the first viewer.

**The Claude desktop app (a browser pane is available, tools named like `preview_start`)**: add an entry to `.claude/launch.json` in the user's family-tree folder and open it in the side panel:

```json
{"version": "0.0.1", "configurations": [
  {"name": "workshop", "runtimeExecutable": "python3",
   "runtimeArgs": ["-I", "<absolute path to the skill>/scripts/live.py", "serve", "--config", "<absolute path>/family-tree.json"],
   "port": 8790}
]}
```

Then `preview_start` with `name: "workshop"`. Keep any other entries in that file. It runs in the side panel next to the conversation; the user can make the panel narrow, the page is built for that (and for phones).

**The terminal (no browser pane)**: start `python3 -I scripts/live.py serve --config family-tree.json` as a background task and give the user the address it prints (`http://127.0.0.1:8790/`).

`--config` reads the same settings file as `make_viewer_data.py` (`--data data/data.json` also works). data.json must exist: build the first viewer before you open the Workshop. Only one Workshop runs at a time; when 8790 is taken it uses the next free port and says so (then fix the port in launch.json).

Say in one sentence what it is: "Next to our conversation you can now watch your tree grow while I search."

## What reports by itself

While a Workshop runs, these send what they do without anything extra:

- `archives.py` (every search, record and scan download; the number of hits for Open Archives) and `delpher.py` (search, text, clipping);
- `gedcom_tool.py check` (the scanner sweeps the whole fan, every person gets a ✓, then each "worth a look" lights up amber on that person) and `rebuild` (round processed, plus every **new** step of the last round that data.json can't show: notes, also "searched, nothing found", events such as a baptism or burial, removed events, other names, place names; steps it has shown before are not repeated);
- **every new data.json**: the page compares it with the previous one and animates the difference (new people, links added or removed, certainty changed, a source or reason added to a link, names, dates, occupations, new or updated stories, photos, life and times per place). Many changes at once (a round of 200 reasons) become one line and light up together. A bar under the counters shows how many links are certain, probable, possible and not checked, so verification shows as progress too. This is the heart of it: what you see is always the real tree.

When no Workshop runs, all of this does nothing (one quick file check).

## Make it live: rebuild per find

The fan only moves when data.json changes. With the Workshop open, don't wait for the end of a round: as soon as a find is confirmed (you read the record yourself), add its steps to the round file, run `rebuild` and `make_viewer_data.py --config family-tree.json`. Both take a second. The round file grows during the round; that's fine, `rebuild` replays it.

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

Only when the user asks for it (the tree contains living people): restart the Workshop with `--lan`. It prints an address with a secret key (`http://192.168.x.x:8790/?k=…`); give that to the user. The phone must be on the same Wi-Fi; macOS may ask once whether Python may accept incoming connections. Without the key nobody else on the network sees anything, and only this computer can send events. For the desktop app: add `"--lan"` to `runtimeArgs` and restart the entry.

## In the page

- The name in the title picks the start person (from the start people, or search by name); every browser remembers its own choice.
- The fan shows as many generations as the start person's tree has, plus one ring of open questions; it grows a ring when you get a generation further.
- Counters: people, links (parent-child), open questions (missing parents up to generation 9, as in `check`), sources (links with a source).
- "Viewer ↗" opens the normal viewer from the same server.
