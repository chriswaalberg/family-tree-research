#!/usr/bin/env python3
"""tree_hint.py — a short reminder for Claude in a family tree's folder (plugin hook; standard library only).

  start    SessionStart: this folder is a family tree → load the skill, open the Workshop before any work on it.
  prompt   UserPromptSubmit: one line in one of three states, asked of the Workshop itself (/ping):
           not running (open it) · running but nobody sees it (show the pane now, then check /ping) · in view (tell it).

Prints nothing outside a tree (no family-tree.json / stamboom.json in this folder or above it), so other projects
never see it. What it prints is added to Claude's context. It never fails the session: any error → silence.
"""
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(HERE, "..", "skills", "family-tree", "scripts", "live.py")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "start"
    try:
        info = json.load(sys.stdin)
    except (ValueError, OSError):
        info = {}
    cwd = info.get("cwd") or os.getcwd()
    spec = importlib.util.spec_from_file_location("ftr_live", LIVE)
    live = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(live)
    root = live.tree_root(cwd)
    if not root:
        return
    st = live.workshop_state(cwd)  # asks the server: running is not enough, the user must be able to see it
    if mode == "start":
        print(
            f"This folder ({root}) holds a family tree made with the Family Tree Research plugin.\n"
            "- Before any work on the tree (research, preparation, reading reports, rebuilding), load the skill "
            "family-tree-research:family-tree, also when this project's CLAUDE.md already explains the research.\n"
            "- Claude Code only (never in Cowork or claude.ai): open the Workshop before the first step, preparation "
            "included (references/workshop.md: live.py launch, preview_start \"workshop\", then load and call "
            "mcp__ccd_view__show_pane with pane 'preview', then check that /ping says \"visible\": true). As soon as it "
            "is in view, send a note there with what you are doing now and what comes next, and keep telling it "
            "(live.py focus / note / progress).\n"
            "- Search through the skill's scripts (archives.py, delpher.py): they report to the Workshop by themselves. "
            "A script of the project's own stays silent there unless it calls live.emit.\n"
            "- The Workshop only counts as open when the user can see it: `curl -s http://127.0.0.1:<port>/ping` "
            "says \"visible\": true (or `live.py status`).\n"
            "- Now: " + live.state_text(st) + ("." if st["state"] == "visible" else "")
        )
    elif st["state"] == "visible":
        print(f"(Family tree: {live.state_text(st)}. Tell it what you do for this request, "
              "preparation too: live.py focus / note / progress.)")
    else:
        print(f"(Family tree, Claude Code only: {live.state_text(st)})")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a reminder must never get in the way
