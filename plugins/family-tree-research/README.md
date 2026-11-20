# Family Tree Research

A plugin for Claude (Cowork) that takes you by the hand through your family history. Works in **English and Dutch**: Claude talks in your language, and the family-tree viewer, reports and stories follow along.

## What does it do?

1. **Start where you are.** Already have a family tree on Ancestry, MyHeritage, FamilySearch or in a program? Claude explains how to export a GEDCOM file. Nothing yet? Then you tell about yourself, your parents and your grandparents, and you build from there.
2. **Claude searches further.** Generation by generation in public archives (such as Open Archives and WieWasWie for the Netherlands, FreeBMD for England, Digitalarkivet for Norway). Every new ancestor gets a source, and for every relation Claude records how certain it is: certain, probable, possible, unknown or wrong.
3. **You watch it grow.** An interactive family-tree viewer (family tree, line, timeline, fan, cosmos) that updates after every round.
4. **You read it as a story.** In the Story view you go back in time step by step from yourself and choose each time: continue with the father or the mother? Or press ▶ Cards to watch it as full-screen cards that play by themselves (made for children). For remarkable lives Claude writes a real story, with sources. Family legends ("we descend from…") get checked too.
5. **How did they live?** For the places where your ancestors lived, Claude collects daily life, local events and old prints, which show up in the story at the right moment.
6. **Photos and documents.** Link family photos and scans of records to people. They live in your GEDCOM and in the viewer.
7. **Honest about limits.** Archives Claude can't get into (login, paywall) it simply tells you, and then asks you for a specific screenshot. Old handwriting it reads itself.

## Getting started

- Install the plugin in the Claude app and open a new Cowork task.
- Tip: create a folder `Family tree` on your computer and add it to the task ("Add folder"). Then everything stays with you and you can continue later.
- Say: **"I want to research my family tree"** (or "continue my family tree"). In Dutch: "Ik wil mijn stamboom uitzoeken".

## Good to know

- Works best for Dutch and Belgian ancestors; Germany, Scandinavia, the UK, Ireland and the US work too, but there you'll more often need your own access to archives.
- Living people are not looked up in archives. What you enter yourself simply goes into your tree and the viewer.
- Data from other people's family trees only counts as a lead, never as proof.
- Raised by a step-parent, adopted or fostered? You can record that; the viewer shows that line as family by adoption, just as much your family.
- You need Claude with Cowork, internet access and preferably the desktop app with a connected folder.

## What's inside

- `skills/family-tree/SKILL.md`: the instructions Claude follows, with references for onboarding, GEDCOM export, research, sources per country, the scripts and the viewer.
- `skills/family-tree/scripts/`: `gedcom_tool.py` (create, extend and check a GEDCOM; link media), `make_viewer_data.py` (GEDCOM → data.json), `standalone_viewer.py` (one standalone HTML file). Python 3.8+, standard library only.
- `skills/family-tree/viewer/`: the viewer (`index.html`) and its data format (`DATA-FORMAT.md`).
- `skills/family-tree/examples/`: a small example family.

Made by Chris Waalberg, with Claude.
