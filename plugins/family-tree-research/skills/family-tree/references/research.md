# Research: method and rules of evidence

## Order

1. Determine the **search frontier**: all direct ancestors without (confirmed) parents. Work from young to old; finish one generation before starting the next, unless the user wants to follow one line.
2. Per person, in this order of usefulness:
   - **Marriage record** of the person: almost always names both parents (Netherlands from 1811), plus age and birthplace.
   - **Birth record** or **baptism entry**: parents, date, place.
   - **Death record**: parents and partner (Netherlands from 1811), age.
   - Then: population registers and censuses, family cards, notarial deeds, church membership registers, memorial cards, family announcements in newspapers.
3. Before civil registration (Netherlands/Belgium before ~1811, other countries see sources.md) there are only church registers (in Dutch: DTB — *doop, trouw, begraven*: baptism, marriage, burial). Baptism registers name the parents, often only the father in full; marriage registers often name no parents. Combine: baptism of the child + marriage of the parents + baptism of the parents, and watch the naming patterns.
4. After every person, record what you found *and* what you didn't, in `data/worklog.md`.

## Rules of evidence

- **No new parent without a source.** Source = archive + kind of record + date + place + link (or inventory/record number). Give it as `source` in the round's step; `rebuild` puts it in the GEDCOM and the CSV.
- **Read the rejected register first.** Before adding a parent, look in `reports/rejected.md` (Dutch: `rapporten/afgewezen.md`). If the link is there, don't add it again, unless a new source refutes the reason (then say so with `despite`, see gedcom-tool.md).
- **A wrong link goes out.** Does a source contradict a parent in the tree? Remove the link with `drop_link` and a reason (and where it came from, e.g. "Ancestry export" or a hint from someone else's tree). Don't keep it with status `error`. The reason goes into the register, so the link doesn't come back in a later round.
- **Has the record a scan link? Read the scan first.** The index gives names; the hard link (age, partner, a parent as witness or giving consent) is often only on the scan. Read the whole record, not just the search snippet: machine-read text is messy (see sources.md).
- A found record only fits if at least two of these three match: name (including spelling variants), age/year (±3 years), place or region. Plus: the parents in the record must fit what's already known (e.g. the partner).
- **Two candidates** that both fit? Don't choose. Note both in `reports/questions.md` and look for a record that settles it (marriage, death with partner's name, witnesses).
- Data from an imported GEDCOM is a hypothesis, not proof. Confirm it with a source before calling it *certain*.
- Don't take anything from other people's online trees as proof. They're only a lead: find the record behind it.

## Statuses (per parent-child relation)

Write the status in the user's language; both are accepted.

| status (en / nl) | when |
|---|---|
| `certain` / `zeker` | A record names this parent for this child **and** there is a hard link to the person in the tree: an age that fits, the right partner, or the parent as witness, godparent or giving consent at an event of the child. |
| `probable` / `waarschijnlijk` | Strong indications, but no hard link: e.g. a patronymic + a child named after the grandparent + the only candidate in the place, or a baptism with only the father's name + a matching marriage. |
| `possible` / `mogelijk` | Plausible candidate, but there are alternatives or too little data. |
| `unknown` / `onbekend` | Searched, nothing found yet. |
| `error` / `fout` | Only for a doubt you can't settle yet (two sources disagree): explain in questions.md. If a source clearly contradicts the relation, remove it with `drop_link` instead. |
| `not checked` / `niet gecheckt` | Not yet researched (default on import) or a living/recent person. |

**Every link gets a source and a reason.** Each certain, probable or possible link gets a `source` (record with link or location) **and** a `note`: one sentence in plain words saying why the status holds: which record, which place and year, who is named as parent, and what ties it to the person in the tree. For probable and possible, also say what is missing ("no baptism found yet", "the mother's name only from a burial"). The viewer shows it on every person card as "Why certain:" with the source below, so readers who aren't genealogists see the reasoning. Someone else's family tree (Geneanet, MyHeritage, a website) is a signpost to the records, never the only reason for *certain*. `make_viewer_data.py` warns about certain/probable/possible links without a source or with a reason under 25 characters.

**A real doubt doesn't go into the tree.** If even `possible` would be a guess, leave the link out and describe it in the work log or round report (what fits, what doesn't, which record would settle it).

**The user's own knowledge** of recent relations ("John really was my father") is a valid source: status `certain`, source "<name> (own knowledge, confirmed <date>)". At the first viewer, ask whether the user wants to confirm their own parents and grandparents this way.

**Kind of relation** (optional column `type`): `biological` (default), `raised` (raised as their own child), `adopted` or `foster` (Dutch: `biologisch`, `aangenomen`, `adoptie`, `pleeg`). Status and type are independent: a father who raised the child can be *certain*.

`data/relations.csv` is made by `rebuild` from the rounds (`parents` and `status` steps); don't edit it by hand. Format (UTF-8, commas, quotes `"`; Dutch column names also work, see `viewer/DATA-FORMAT.md`; `rebuild` adds the names in `child_name`/`parent_name` for reading):

```
child_id,parent_id,status,source,note,type
@I12@,@I15@,certain,"Marriage record Leiden 1902, no. 112, https://www.openarchieven.nl/...","The marriage record (Leiden, 1902) names Jan de Wit, 54, carpenter, as the groom's father; same age and trade as in the 1880 census.",
@I20@,@I22@,certain,"Sanne (own knowledge, confirmed 2026-11-19)","Sanne confirmed it herself: not her biological father, but the dad who raised her.",raised
```

## Plausibility checks (do them for every new person)

- Mother between 14 and 50 at the child's birth; father between 16 and 75.
- Child not born after the mother's death, or more than 10 months after the father's death.
- Not married before age 14; nobody older than ~105.
- Same person twice? (Pedigree collapse can be real: cousin marriages. Then one person, two routes.)

## Names

- Spelling variants are normal (Waalberg/Walberg/Wahlberg; Jansen/Janssen/Janse; Smith/Smyth). Search with variants and wildcards.
- Patronymics (in the Netherlands until ~1811, longer in Friesland and Scandinavia): "Jan Pietersz" = Jan, son of Pieter. A surname can change every generation. In Sweden and Norway: -son/-dotter, -sen/-datter.
- In Dutch and Belgian records women appear under their own birth name. In English-speaking records, look for both maiden and married name.
- Children were often named after grandparents (first son after the father's father, first daughter after the mother's mother): a useful hint, not proof.

## Working in rounds

A round = one generation (or ±10 people). The original GEDCOM in `source/` is never changed; every round is a block of its own, and the working version is rebuilt from the original plus all rounds every time. That way a mistake in an old round can be fixed in that round, and nothing gets lost.

1. Write what you found as one round file: `rounds/<number>-<short name>.json` (Dutch: `rondes/`), with a title, the date and a source per step (format and steps in gedcom-tool.md). New people, parents, events, occupations, notes, other names, wrong links out (`drop_link` with a reason), duplicates merged, place names made uniform ("Place, Province, Country").
2. Rebuild: `gedcom_tool.py rebuild <original> rounds source/tree.ged --csv data/relations.csv --rejected reports/rejected.md --media data/media.csv --lang <user language>`. It stops with the round and step if something doesn't fit; fix the round and run again. Look at what changed (a diff of `tree.ged`, or the list it prints): only what you meant?
3. Build the viewer data and publish (see viewer.md).
4. Add to `reports/new.md` (who, what, source) and regenerate the gaps (`gedcom_tool.py check`).
5. Short report to the user in plain words: "This round I found 6 new ancestors. Your oldest known ancestor is now … (born c. 1742 in …). I got stuck at …; could you have a look there?" Follow the agreement from onboarding step 4 on how independently you continue.

## A big round (overnight round)

When the user lets you work on your own for a long time ("search as far as you can tonight"), work in waves:

1. **Frontier.** List all ancestor couples without parents (the gaps from `gedcom_tool.py check`) and split them by region or archive into groups of ±30 couples.
2. **Helpers search in parallel.** Give each group to a research helper (a subagent), several at once. Helpers **only read**: they search the archives and write a report per couple in `reports/research-<date>/` (Dutch: `rapporten/onderzoek-<datum>/`), with every record and its link, a proposed status with the reason, and also **what they did not find** and where they looked. They don't change the tree. In Claude Code with the Workshop open, each helper puts `FTR_WHO=<its short name>` in front of its commands, so it gets its own beam (see `workshop.md`).
3. **Check every find yourself.** The main session fetches the key record of every proposal (and its scan where there is one) and checks it against the rules above. Only then does it go into a round file. Downgrade a status when the hard link is missing; leave doubts out.
4. **Next wave.** Rebuild, then repeat from step 1 for the parents just found, until no wave finds anything or the time is up.
5. **Summary report.** One report for the user: the count at the start and at the end (people, direct ancestors, oldest ancestor), the best finds, what was left out and why, and a link to the helpers' full reports.

## Asking the user for help

Make it concrete and small:

> I can't get into the Swedish archive ArkivDigital (you need a login there). Could you look in the **baptism register of Åhus, 1750–1755**, for a **Hans**, son of a **Hans**? A photo or screenshot of the page is enough; I'll read the old handwriting.

Also put the request in `reports/questions.md` so it doesn't get lost. Put the links and the exact request in your **last message** of the turn, in full: text written in between often reaches the user shortened, without the links.

**Scans the user sends** (usually in Downloads) always go the same way: take them from Downloads, rename them to `year – kind – place – who (archive, inventory, page).jpg` (e.g. `1752 – baptism – Åhus – Hans Hansson (Riksarkivet, C 2, p. 14).jpg`), crop away browser chrome and borders, and move them to `scans/`. Then read them and link them to the person (`data/media.csv`).

## Privacy

- Don't search archives for living people; when in doubt, assume living (born < 100 years ago without a death date).
- Recent records are usually not public (Netherlands: births < 100 years, marriages < 75 years, deaths < 50 years; other countries have similar rules): don't expect to find them.
- **Hard facts about people long dead may be told.** A conviction, a police report, forced labour, a child born before the wedding: put it in the tree and the story, factually and with the source, without asking first. Stay careful with living people and their parents' secrets: ask the user first.
