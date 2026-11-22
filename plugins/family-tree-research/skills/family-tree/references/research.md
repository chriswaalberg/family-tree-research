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
- A found record only fits if at least two of these three match: name (including spelling variants), age/year (±3 years), place or region. Plus: the parents in the record must fit what's already known (e.g. the partner).
- **Two candidates** that both fit? Don't choose. Note both in `reports/questions.md` and look for a record that settles it (marriage, death with partner's name, witnesses).
- Data from an imported GEDCOM is a hypothesis, not proof. Confirm it with a source before calling it *certain*.
- Don't take anything from other people's online trees as proof. They're only a lead: find the record behind it.

## Statuses (per parent-child relation)

Write the status in the user's language; both are accepted.

| status (en / nl) | when |
|---|---|
| `certain` / `zeker` | A record names this parent for this child and name/age/place match. |
| `probable` / `waarschijnlijk` | Strong indications (e.g. baptism with only the father's name + a matching marriage), but no record that says it directly. |
| `possible` / `mogelijk` | Plausible candidate, but there are alternatives or too little data. |
| `unknown` / `onbekend` | Searched, nothing found yet. |
| `error` / `fout` | Only for a doubt you can't settle yet (two sources disagree): explain in questions.md. If a source clearly contradicts the relation, remove it with `drop_link` instead. |
| `not checked` / `niet gecheckt` | Not yet researched (default on import) or a living/recent person. |

**The user's own knowledge** of recent relations ("John really was my father") is a valid source: status `certain`, source "<name> (own knowledge, confirmed <date>)". At the first viewer, ask whether the user wants to confirm their own parents and grandparents this way.

**Kind of relation** (optional column `type`): `biological` (default), `raised` (raised as their own child), `adopted` or `foster` (Dutch: `biologisch`, `aangenomen`, `adoptie`, `pleeg`). Status and type are independent: a father who raised the child can be *certain*.

`data/relations.csv` is made by `rebuild` from the rounds (`parents` and `status` steps); don't edit it by hand. Format (UTF-8, commas, quotes `"`; Dutch column names also work, see `viewer/DATA-FORMAT.md`; `rebuild` adds the names in `child_name`/`parent_name` for reading):

```
child_id,parent_id,status,source,note,type
@I12@,@I15@,certain,"Marriage record Leiden 1902, no. 112, https://www.openarchieven.nl/...","father 54, carpenter",
@I20@,@I22@,certain,"Sanne (own knowledge, confirmed 2026-11-19)","not the biological father, but her dad",raised
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

## Asking the user for help

Make it concrete and small:

> I can't get into the Swedish archive ArkivDigital (you need a login there). Could you look in the **baptism register of Åhus, 1750–1755**, for a **Hans**, son of a **Hans**? A photo or screenshot of the page is enough; I'll read the old handwriting.

Also put the request in `reports/questions.md` so it doesn't get lost. Scans and screenshots: give them a logical name (`1752-baptism-ahus-hans-hansson.jpg`) and put them in `scans/`.

## Privacy

- Don't search archives for living people; when in doubt, assume living (born < 100 years ago without a death date).
- Recent records are usually not public (Netherlands: births < 100 years, marriages < 75 years, deaths < 50 years; other countries have similar rules): don't expect to find them.
