# Changelog

One line per version from 0.9.38 on; older versions are in the git history (`git log --oneline`).

- **0.9.38** — Newspaper clippings come into the Story view by themselves: the skill asks for a clipping (`soort: "krant"`) for every newspaper item a story quotes or leans on, and puts other finds in `media.csv` as documents; `make_viewer_data.py` warns "this story cites a newspaper without a clipping"; new `scripts/delpher.py` (search Delpher via SRU, read the OCR, crop with a ruler and cut a clipping); `references/sources.md` explains the Delpher SRU route.
