# Family Tree Research

[![Latest version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fchriswaalberg%2Ffamily-tree-research%2Fmain%2Fplugins%2Ffamily-tree-research%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version&color=b48a3c)](https://github.com/chriswaalberg/family-tree-research/commits/main)

I've been researching my own family tree with Claude, including the Swedish origin of our family name. I started with an export of an old Ancestry project. Claude checked every connection and added a lot of new ancestors, every one of them with a source. I turned it into a plugin, so you can do the same.

Start with what you know (yourself, your parents, your grandparents) or with a GEDCOM export from Ancestry or MyHeritage. Claude searches public archives, notes for each ancestor how sure it is, and builds an interactive family tree. It works in **English and Dutch**. My favourite part is the Story view: you walk back through the generations and read how each of them lived.

![Three views side by side. Story: a grandfather's chapter with his story, how sure it is, life in his town and a 1955 photo. Cards: the same story as full-screen cards, here the 1955 photo. Family tree, fan view: all ancestors over 8 generations, with the new header. Fictional example families that come with the plugin.](docs/screenshots/views.png)

Not every archive lets Claude in. When one doesn't, Claude tells you exactly what to look up and asks for a screenshot.

## Install (with automatic updates)

1. Open the Claude app → **Customize** → **Plugins**.
2. Click **Add** (top right) → **Add marketplace** and enter: `chriswaalberg/family-tree-research`
3. Install **family-tree-research**.
4. Turn on automatic updates: first select the **Plugins** tab, then click **Add** (top right) → **Manage marketplaces** → **···** next to family-tree-research → **Sync automatically**.

**Not getting the latest version?** The badge at the top shows the newest one. Customize → **Plugins** → **Add** → **Manage marketplaces** → **···** → **Check for updates**. The "Synced commit" there should match the latest commit on GitHub.

## Get started

1. Create an empty folder on your computer, e.g. `Family tree`.
2. Start a new Cowork task and add that folder (**Add folder**).
3. Type **/family-tree-research:family-tree** or just say: **"I want to research my family tree."** (Dutch works too: "Ik wil mijn stamboom uitzoeken.")

Continuing later? New task, same folder, and say: **"Continue my family tree."**

More about what the plugin does: [plugins/family-tree-research/README.md](plugins/family-tree-research/README.md)

## Or if you prefer Claude Code

```
/plugin marketplace add chriswaalberg/family-tree-research
/plugin install family-tree-research@chriswaalberg
```

## Found something?

A great-great-grandparent, or a bug? [Open an issue](https://github.com/chriswaalberg/family-tree-research/issues). I'd love to hear both.

## License

MIT, see [LICENSE](LICENSE).
