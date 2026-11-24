#!/usr/bin/env python3
"""tree_hint.py — a short reminder for Claude in a family tree's folder (plugin hook; standard library only).

  start    SessionStart: this folder is a family tree → load the skill, open the Workshop before any work on it.
  prompt   UserPromptSubmit: one line in one of three states, asked of the Workshop itself (/ping):
           not running (open it) · running but nobody sees it (show the pane now, then check /ping) · in view (tell it).

Helpers (subagents) show up in the Workshop by themselves, whatever Claude remembers to put in their brief:
  agent    PreToolUse on Agent: remembers the helper's short description as its Workshop name (FTR_WHO); a brief
           that already sets FTR_WHO is left alone. Changes nothing about the call itself.
  helper   SubagentStart: gives the helper its name, FTR_TREE and how to report (scripts, scans.py, progress, note),
           as context of its own, and shows it in the Workshop at once (its own row and beam).
  bash     PreToolUse on Bash, only inside a helper: a command that runs one of the skill's scripts without FTR_WHO
           gets `export FTR_WHO=… FTR_TREE=…;` in front of it.
All three only act in a tree's folder whose Workshop runs (one of its pointer files, no network); updatedInput is
not used on Agent, because auto mode denies a changed call and drops the change when it is sent again.

Prints nothing outside a tree (no family-tree.json / stamboom.json in this folder or above it), so other projects
never see it. What it prints is added to Claude's context. It never fails the session: any error → silence.
"""
import importlib.util, json, os, re, shlex, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "skills", "family-tree", "scripts"))
LIVE = os.path.join(SCRIPTS, "live.py")
OURS = re.compile(r"\b(archives|delpher|live|scans|gedcom_tool|make_viewer_data|geocode_places)\.py\b")
NAME_MAX = 40  # live.py cuts FTR_WHO to 40 characters


def load_live():
    spec = importlib.util.spec_from_file_location("ftr_live", LIVE)
    live = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(live)
    return live


# ---------------------------------------------------------------- helpers: one small state file per session
def _state_path(live, info):
    sid = re.sub(r"[^\w-]", "", str(info.get("session_id") or "nosession"))[:64]
    return os.path.join(live.POINTERS, "helpers", f"{sid}.json")  # a folder of its own: not a Workshop pointer


def _with_state(live, info, change):
    """Read, change and write the session's helper state under a lock (helpers often start in parallel)."""
    path = _state_path(live, info)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+", encoding="utf-8") as fh:
        try:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass  # Windows: no lock; a rare mix-up of two names is all it costs
        fh.seek(0)
        try:
            st = json.loads(fh.read() or "{}")
        except ValueError:
            st = {}
        st.setdefault("queue", [])
        st.setdefault("agents", {})
        st.setdefault("n", 0)
        out = change(st)
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(st))
    return out


def _unique(st, name):
    used = set(st["agents"].values())
    base, k = name, 2
    while name in used:
        name = f"{base[:NAME_MAX - 3]} {k}"
        k += 1
    return name


def on_agent(live, info, cwd):
    """PreToolUse Agent: queue the helper's name for SubagentStart (which only gets an id and a type)."""
    inp = info.get("tool_input") or {}
    if not live.workshop_for(cwd):
        return
    brief = str(inp.get("prompt") or "")
    m = re.search(r"FTR_WHO=(?:'([^']+)'|\"([^\"]+)\"|(\S+))", brief)
    entry = {"skip": True, "name": next(g for g in m.groups() if g)[:NAME_MAX]} if m else \
            {"skip": False, "name": " ".join(str(inp.get("description") or "").split())[:NAME_MAX]}
    _with_state(live, info, lambda st: st["queue"].append(entry))


def brief_for(name, root):
    q = shlex.quote
    env = f"export FTR_WHO={q(name)} FTR_TREE={q(root)};"
    return (
        f"You work in a family tree's folder ({root}). Its Workshop, a live page the user is watching, shows every "
        f"helper as a row and a beam of its own. Your name there is {name!r}. Start every command with `{env}` and use "
        f"the skill's scripts in {SCRIPTS} (python3 -I <script> …); they report to the Workshop by themselves:\n"
        "- archives: archives.py, delpher.py;\n"
        "- local scans (a parish book, downloaded pages): `scans.py strips <image> --person <GEDCOM id> --task \"<book>\" "
        "--done <n> --total <pages>` cuts page halves and strips at true size (then Read the strips); "
        "`scans.py crop <image> x,y` for one spot;\n"
        "- after every scan or search without a script: `live.py progress \"<task>\" <done> <total> --person <id>`; "
        "a find or a dead end: `live.py note \"<one line>\" --kind found|nothing --person <id>`; "
        "who you work on: `live.py focus <id or full name>`."
    )


def on_helper(live, info, cwd):
    """SubagentStart: name the helper, brief it, and put it in the Workshop at once."""
    root = live.tree_root(cwd)
    if not root or not live.workshop_for(cwd):
        return
    aid = str(info.get("agent_id") or "")

    def take(st):
        if aid and aid in st["agents"]:  # resumed: same name, brief again (Claude Code skips it if it is still there)
            return {"skip": False, "name": st["agents"][aid], "again": True}
        e = st["queue"].pop(0) if st["queue"] else {"skip": False, "name": ""}
        st["n"] += 1
        e["name"] = _unique(st, e.get("name") or f"Helper {st['n']}")
        if aid:
            st["agents"][aid] = e["name"]
        st["root"] = root  # for a helper that runs a command from another folder
        return e

    e = _with_state(live, info, take)
    if not e.get("again"):  # its row and beam appear now, before its first command
        os.environ["FTR_WHO"] = e["name"]
        os.environ["FTR_TREE"] = root
        live.emit("helper", _where=cwd, _warn=False)
    if e.get("skip"):
        return  # the brief sets FTR_WHO already; the bash hook still knows its name
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SubagentStart",
                                             "additionalContext": brief_for(e["name"], root)}}))


def on_bash(info, cwd):
    """PreToolUse Bash inside a helper: put FTR_WHO/FTR_TREE in front of the skill's scripts when they are missing."""
    aid = str(info.get("agent_id") or "")
    inp = info.get("tool_input") or {}
    cmd = inp.get("command")
    if not aid or not isinstance(cmd, str) or not OURS.search(cmd) or "FTR_WHO=" in cmd:
        return  # the cheap checks first: this runs for every Bash call, in every project
    live = load_live()
    if not os.path.isfile(_state_path(live, info)):
        return  # no helper was named in this session
    name, root = _with_state(live, info, lambda st: (st["agents"].get(aid), live.tree_root(cwd) or st.get("root")))
    if not name or not root or not live.workshop_for(root):
        return
    new = dict(inp, command=f"export FTR_WHO={shlex.quote(name)} FTR_TREE={shlex.quote(root)}; {cmd}")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": new}}))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "start"
    try:
        info = json.load(sys.stdin)
    except (ValueError, OSError):
        info = {}
    cwd = info.get("cwd") or os.getcwd()
    if mode == "bash":
        return on_bash(info, cwd)
    live = load_live()
    if mode == "agent":
        return on_agent(live, info, cwd)
    if mode == "helper":
        return on_helper(live, info, cwd)
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
