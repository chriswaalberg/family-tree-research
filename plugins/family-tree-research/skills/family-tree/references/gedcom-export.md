# Exporting a GEDCOM: steps per platform

First explain briefly (in the user's language): "A GEDCOM is a standard file (it ends in .ged) that holds your whole family tree: names, dates, places and who belongs to whom. Almost every family-tree site can make one. Your tree stays where it is; you're only making a copy."

Only give the steps for the user's platform. Menus change now and then: if a step doesn't match, ask what they see (a screenshot helps) or look up the current help page. Menu names below are given in English; on a Dutch-language site they'll be in Dutch (e.g. "Boominstellingen" for Tree Settings).

## Ancestry
1. Sign in and open your tree (**Trees** tab → choose the tree).
2. Click the tree name or **More (⋯)** in the left bar → **Tree Settings**.
3. On the right under **Manage your tree**: **Export tree** → confirm with **Export**.
4. Wait a moment (big trees take a few minutes) and click **Download your GEDCOM file**.
Only the owner of a tree can export it. Photos don't come along; that's fine.

## MyHeritage
1. Sign in, hover over **Family tree** → **Manage trees**.
2. Next to your tree click **Export to GEDCOM**.
3. Photos aren't needed → **Begin the export**. You'll get a download link (sometimes by email).

## FamilySearch
FamilySearch has one shared world tree. There's an export page (familysearch.org/innovate/export) that exports up to **8 generations** from yourself as GEDCOM 7. That's a fine start for us. If it doesn't work: no problem, we'll take the manual route (you, parents, grandparents) and use FamilySearch as a source.

## Geneanet
Sign in and look in the management of your tree for the option to download the tree or export it as GEDCOM. Choose the full file. Can't find it? Send a screenshot of the menu.

## Geni
**Family** → **Share your tree** → **GEDCOM export**. Choose GEDCOM 5.5. Geni often exports only part of the shared tree; that's enough for us.

## Findmypast
**Family tree** → **View all trees** → the export icon next to the tree.

## Programs on your computer
Almost always **File → Export → GEDCOM** (Gramps, Family Tree Maker, RootsMagic, Legacy, MacFamilyTree, Heredis, Aldfaer). If asked, choose GEDCOM 5.5.1 and "all people".

## Afterwards
Ask them to drop the file in the chat or put it in the connected family-tree folder. Keep the original unchanged in `source/` (e.g. `source/original-ancestry-2026-11-19.ged`) and work on a copy.

GEDCOM 7 files (e.g. from FamilySearch): the scripts read the basics (INDI, FAM, NAME, SEX, BIRT, DEAT, FAMC, FAMS) fine. Compare the number of people read with what the user expects.
