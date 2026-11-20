# Onboarding: step by step

Goal: within a quarter of an hour, a first tree with the user, parents and grandparents, and a working viewer. Only then the big search.

Speak the user's language throughout (English by default, Dutch if they write Dutch). The example wordings below are in English; translate them naturally.

## Step 0 – Welcome (no question, just explanation)

Example (adapt to the person, keep it short):

> Great that you want to explore your family tree! Here's how we'll do it: we start with you (or whoever you like) and work our way back together. I'll search public archives for the birth, marriage and death records of your ancestors. For every find I note where it came from and how certain it is. Along the way you get an interactive family tree that keeps growing. You don't need to know anything about genealogy; I'll guide you through it.

Then check the workspace (connected folder, see SKILL.md) and create the folders.

## Step 1 – Do you already have a family tree?

AskUserQuestion, one question:

- "Do you already have your family tree somewhere?"
  - Yes, online (Ancestry, MyHeritage, FamilySearch, Geneanet, Geni…)
  - Yes, in a program on my computer (Gramps, Family Tree Maker, RootsMagic, MacFamilyTree, Aldfaer…)
  - No, I'm starting from scratch
  - I only have loose papers/notes

**Yes** → `gedcom-export.md`: give the steps for their platform. Ask them to drop the file in the chat or put it in the connected folder. Keep the original unchanged in `source/` and always work on a copy. Then go to "Checking an import".

**No / loose papers** → Step 2. With papers: ask whether they'd like to share photos of important documents (marriage booklet, memorial cards, certificates, family announcements); those are a gold mine. Read them and record them as sources.

## Step 2 – The start person

First ask: "Who is the family tree for? Yourself, or someone else (a child, a parent)?" If someone picks a child as start, the parents are the user and their partner; that makes the tree broader straight away.

Then ask, one at a time (free text, short is fine):

1. Full name (all given names + surname; for women the maiden name).
2. Date or year of birth and place of birth.
3. (Only for people who have died) date and place of death.

Mention: everything you tell me goes into your family tree and the viewer. If you'd rather hide details of living people in the viewer, that's possible.

## Step 3 – Parents, then grandparents

Order: father, mother, father's father, father's mother, mother's father, mother's mother. Always say in plain words who you mean ("your father's mother, so your grandmother on your dad's side").

Per person:

1. Name (women: maiden name; "don't know it? No problem, I'll look it up").
2. Roughly when and where born?
3. Still alive? If not: when and where did they die (roughly is fine)?
4. Once per couple: do you know when/where they married?

Quick route for the impatient: offer to type all four grandparents in one message ("Just type what you know, I'll pick it out"). Then summarise in a short list and ask whether it's right.

Bonus questions (only if the conversation invites it, max. 1–2):
- Is there a family story? ("We come from Germany", "grandpa was a sailor")
- Have relatives ever researched the family?
- Do you know the occupation or religion of a (great-)grandparent? (Helps to find church registers.)

Record everything right away in `data/intake.json` (format below) and keep adding to it.

## Step 4 – What do you want to know, and how independently may I work?

AskUserQuestion, two questions:

- "What are you most curious about?" → As far back as possible in all lines / one surname (the paternal line) / a particular country or family story / Just start, we'll see.
- "How would you like me to work?" → Search on your own and only report what you found / Show me after every generation / Look at every find together first.

Write the answers in the progress file under "Agreements".

## Step 5 – First tree and viewer

1. No GEDCOM? Make one: `python3 -I scripts/gedcom_tool.py new data/intake.json source/tree.ged` (see gedcom-tool.md).
2. Build the viewer data and publish (see `viewer.md`), with `--lang` in the user's language.
3. Share the link: "Here's your family tree. Still small, but it's going to grow." Explain in two sentences how to click and search.

## Step 6 – First research round

Start with the grandparents (the top generation with names) and look for their birth or marriage record; that gives the names of the great-grandparents. Follow `research.md`.

## Checking an import (existing GEDCOM)

Run the check (`gedcom_tool.py check … --lang <user language>`) and tell in plain words:
- Number of people and families; who seems to be the start person (ask).
- Direct ancestors per generation (expected 2, 4, 8, 16… found …).
- People without parents in the top generations (the "gaps").
- Odd things: child born after the mother's death, mother younger than 14 or older than 50, person older than 105, duplicates.
- Are there sources? (SOUR lines.) Many imported trees have few; that's normal.

Then ask: "Shall I go through the existing tree first (is everything right?), or search further where it stops?" Existing relations keep the status *not checked* until you've confirmed them with a source.

## Format of data/intake.json

English or Dutch keys both work (Dutch in brackets).

```json
{
  "lang": "en",
  "title": "The Jansen family",
  "start": "p1",
  "people": [
    {"id": "p1", "given_names": "Anna Maria", "surname": "de Vries", "sex": "F",
     "birth": {"date": "1985", "place": "Utrecht"}, "living": true,
     "father": "p2", "mother": "p3", "notes": ""},
    {"id": "p2", "given_names": "Jan", "surname": "de Vries", "sex": "M",
     "birth": {"date": "c. 1955", "place": "Zwolle"},
     "death": {"date": "12-03-2019", "place": "Utrecht"},
     "father": "p4", "mother": "p5"}
  ],
  "marriages": [
    {"husband": "p2", "wife": "p3", "date": "1982", "place": "Zwolle"}
  ]
}
```

Key aliases: `people` (`personen`), `given_names` (`voornamen`), `surname` (`achternaam`), `sex` (`geslacht`, M/F or M/V), `birth` (`geboren`), `baptism` (`gedoopt`), `death` (`overleden`), `burial` (`begraven`), `occupation` (`beroep`), `source` (`bron`), `notes` (`notities`), `father`/`mother` (`vader`/`moeder`), `marriages` (`huwelijken`) with `husband`/`wife` (`man`/`vrouw`), `date`/`place` (`datum`/`plaats`).

Dates may be vague: `1985`, `c. 1955` / `about 1955` / `ca. 1955`, `before 1900` / `voor 1900`, `12-03-2019` (day-month-year), `March 1931` / `maart 1931`. The script converts them to GEDCOM (`ABT`, `BEF`, `12 MAR 2019`). Leave unknown fields out.
