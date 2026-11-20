# Family Tree Research

A plugin for Claude (Cowork) that guides you step by step through your family history, in **English or Dutch**. Start with a GEDCOM file or with yourself, your parents and your grandparents. Claude searches public archives, notes the source and how certain it is for every ancestor, and builds an interactive family-tree viewer you can read as a story.

## Install (with automatic updates)

1. Open the Claude app → **Customize** → **Plugins**.
2. Click **Add** (top right) → **Add marketplace** and enter: `chriswaalberg/family-tree-research`
3. Install **family-tree-research**.
4. Turn on automatic updates: on the **Plugins** tab (the **Add** menu only shows marketplace options there), click **Add** (top right) → **Manage marketplaces** → **···** next to family-tree-research → **Sync automatically**. If the app asks you to connect GitHub, that's fine. Afterwards, check that the switch is still on.

**Not getting the latest version?** Customize → **Plugins** → **Add** → **Manage marketplaces** → **···** → **Check for updates**. The "Synced commit" there should match the latest commit on GitHub.

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

## License

MIT — see [LICENSE](LICENSE).
