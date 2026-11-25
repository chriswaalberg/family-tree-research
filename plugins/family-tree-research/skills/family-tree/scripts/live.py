#!/usr/bin/env python3
"""live.py — the Workshop: watch the family tree grow while Claude researches (Claude Code only).

  serve [--config family-tree.json | --data data.json]   start the local Workshop page (viewer/live.html); one per tree:
        [--port 8790] [--local] [--media DIR ...]         the server runs on its own (a session that ends or is archived
                                                        doesn't stop it); this command stays as its keeper while it runs
                                                        and reuses a Workshop that already runs for this tree.
                                                        Ctrl+C stops it; a stop from the desktop app only ends the keeper.
                                                        Nobody watching and nothing sent for IDLE_STOP: it stops itself.
  stop [--tree DIR]                                     stop this tree's Workshop
  launch [--config ... | --data ...] [--local]          desktop app: write the `workshop` entry in the tree's
                                                        .claude/launch.json (this live.py, this tree's own port);
                                                        run it before every preview_start
  note "<text>" [--person I4] [--kind note|read|found|nothing|ask]
                                                        tell the Workshop what you are doing (one line)
  focus <I4 or name> ["what you look for"]            who you are working on now: ring + name at their star
  progress "<task>" <done> <total> [--person I4] [--text ...]
                                                        a progress bar for a long script; send it every step
  progress "<task>" --stop                              close a bar that won't finish (grey, then gone; see TASK_QUIET)
  status [--json] [--wait 10]                           not running / running but hidden / in view (exit 0 = in view);
                                                        --wait: wait up to that many seconds for the page to be in view

The Workshop is only "open" when the user can see it: the page reports whether it is in view, and /ping answers
with `viewers` (pages that have it open) and `visible`. note/focus/progress say every time when nobody sees it.

Events go only to the Workshop of the tree you work in: the one whose folder holds the current folder (or the file
that rebuild/check writes, or FTR_TREE / --tree). Run scripts from the tree's folder. In a tree's folder (one with
family-tree.json / stamboom.json) where its Workshop isn't running or nobody sees it, emit() says so on stderr (at most
every 10 / 5 minutes; FTR_QUIET=1: never).

The page has a Changes tab: the server compares every data.json with the one before (tree_changes) and keeps the list
of real changes for the whole session, plus the round steps data.json can't show; `hello` and every `data` event
carry it, so a reopened page or a phone sees all of it.

The page shows the start person's ancestors (Cosmos, or the round Fan). Every time data.json changes (after gedcom_tool.py rebuild
and make_viewer_data.py) it compares the old and the new tree and animates the difference: new people fly in,
rejected links crack, links that became certain turn gold. archives.py, delpher.py and gedcom_tool.py check/
rebuild report what they do by themselves while a Workshop is running; for anything else use `note`.

The page also listens on the local network, so a phone on the same Wi-Fi can watch: its address carries the tree's
secret key (?k=..., fixed per tree; the phone button in the page shows it as a QR code). Without the key nobody else
on the network sees anything, and only this computer can send events. --local: only this computer.

A long script of your own can also call emit() directly instead of starting live.py for every step:
    spec = importlib.util.spec_from_file_location("ftr_live", "<skill>/scripts/live.py")
    live = importlib.util.module_from_spec(spec); spec.loader.exec_module(live)
    live.emit("progress", task="side branches", done=42, total=123, person="I87")
Helpers (subagents) set FTR_WHO=<short name> in front of their commands: each gets its own scanner beam.

Standard library only. Dutch aliases: serveer/start, notitie (--persoon, --soort, --boom), voortgang (--tekst, --boom).
"""
import argparse, errno, hashlib, json, zlib, os, queue, secrets, signal, socket, subprocess, sys, tempfile, threading, time, urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

POINTERS = os.path.join(tempfile.gettempdir(), "family-tree-research-live")  # one file per running Workshop (per tree)
HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.normpath(os.path.join(HERE, "..", "viewer"))
CONFIG_NAMES = ("family-tree.json", "stamboom.json")


# ---------------------------------------------------------------- which Workshops run (one per tree)
def _key(data):
    return hashlib.sha1(os.path.realpath(data).encode("utf-8")).hexdigest()[:12]


def workshops():
    """The running Workshops: [{port, pid, data, root}]. Files of stopped ones are removed on the way."""
    out = []
    try:
        names = os.listdir(POINTERS)
    except OSError:
        return out
    for n in names:
        if not n.endswith(".json"):
            continue  # the server logs live there too
        f = os.path.join(POINTERS, n)
        try:
            with open(f, encoding="utf-8") as fh:
                p = json.load(fh)
            os.kill(int(p["pid"]), 0)  # still running?
            out.append(p)
        except ProcessLookupError:
            try:
                os.remove(f)
            except OSError:
                pass
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return out


def _inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def workshop_for(where=None):
    """The Workshop of the tree you are working in: the one whose folder holds `where` (a file the script writes),
    else the current folder (FTR_TREE overrides). None when no Workshop belongs here: then nothing is sent."""
    spots = [p for p in (os.environ.get("FTR_TREE"), where, os.getcwd()) if p]
    for spot in spots:
        hits = [w for w in workshops() if w.get("root") and _inside(os.path.abspath(spot), w["root"])]
        if hits:
            return max(hits, key=lambda w: len(w["root"]))
    return None


# ---------------------------------------------------------------- the phone key: the same for a tree on every start
KEYS = os.path.join(os.path.expanduser("~"), ".config", "family-tree-research", "workshop-keys.json")


def tree_key(data):
    """The secret for the phone address of this tree. Kept in the user's own config folder (never in the tree's folder,
    which may be in git), so a bookmark on the phone keeps working after a restart."""
    try:
        with open(KEYS, encoding="utf-8") as fh:
            keys = json.load(fh)
    except (OSError, ValueError):
        keys = {}
    k = _key(data)
    if not isinstance(keys.get(k), str):
        keys[k] = secrets.token_urlsafe(9)
        try:
            os.makedirs(os.path.dirname(KEYS), exist_ok=True)
            fd = os.open(KEYS + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(keys, fh, indent=1)
            os.replace(KEYS + ".tmp", KEYS)
        except OSError:
            pass  # no config folder: this start gets a key of its own
    return keys[k]


# ---------------------------------------------------------------- sending events (used by the other scripts too)
def tree_root(spot=None):
    """The tree's folder that holds `spot` (default: the current folder): the nearest folder upwards with a
    settings file (family-tree.json / stamboom.json). None outside a tree."""
    d = os.path.abspath(spot or os.getcwd())
    if os.path.isfile(d):
        d = os.path.dirname(d)
    for _ in range(6):
        if any(os.path.isfile(os.path.join(d, n)) for n in CONFIG_NAMES):
            return d
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    return None


# ---------------------------------------------------------------- can the user see it? (three states)
# A running server is not enough: the desktop app's browser pane can be hidden, or no page has the Workshop open at all.
# The page (live.html) tells the server whether it is in view (POST /seen, on every visibility change and every
# BEAT_MS while visible; in view = visibilityState "visible", a real size and frames at screen speed, because the
# desktop app's closed pane keeps "visible" and its size but paints at ~30 fps, see live.html); /ping answers with `viewers` and `visible`. The states:
#   none     no Workshop answers for this tree
#   hidden   it runs, but nobody sees it (no page open, or the page is hidden)
#   visible  a page shows it right now
#   unknown  an older live.py runs it, which can't tell (restart it)
# Whether a page is still open comes from its event stream (/events), not from its timers: a hidden pane runs as a
# background page whose timers the browser slows to about once a minute, so "hidden" never turns into "closed".
WARN_NONE_EVERY = 600    # seconds: "not running" on stderr from emit() at most once per 10 minutes per tree
WARN_HIDDEN_EVERY = 300  # "nobody sees it" at most once per 5 minutes (live.py note/focus/progress say it every time)
BEAT_FRESH = 20   # a "visible" report counts this long (a page in view reports every 3 s; its timers aren't slowed)
VIEWER_TTL = 150  # a page without an open event stream counts this long after its last report


def _paint_hint(port):
    return ("load and call mcp__ccd_view__show_pane with pane 'preview' now, then check that "
            f"`live.py status --wait 10` (or curl -s http://127.0.0.1:{port}/ping) says \"visible\": true")


def state_text(st):
    """One plain line for Claude about what the user can see of this tree's Workshop (hooks and live.py use it)."""
    port, state = st.get("port"), st.get("state")
    term = f" (In a terminal without a browser pane: give the user the address http://127.0.0.1:{port}/ instead.)"
    if state == "none":
        return ("this tree's Workshop is NOT RUNNING, so the user can't watch. Open it: live.py launch --config "
                "<settings file>, then preview_start name \"workshop\", then load and call mcp__ccd_view__show_pane with "
                "pane 'preview', then check that /ping says \"visible\": true (references/workshop.md).")
    if state == "unknown":
        return (f"this tree's Workshop runs on port {port} with an older live.py that can't tell whether anyone sees it: "
                "restart it (preview_stop it, live.py launch, preview_start name \"workshop\"), then " + _paint_hint(port) + ".")
    if state == "hidden":
        if not st.get("viewers"):
            return (f"this tree's Workshop runs on port {port} but NO PAGE HAS IT OPEN, so the user sees nothing. "
                    f"preview_start name \"workshop\" (or navigate the browser pane to http://127.0.0.1:{port}/), then "
                    + _paint_hint(port) + "." + term)
        return (f"this tree's Workshop runs on port {port} and a page has it open, but it is HIDDEN (not in view), so the "
                "user sees nothing. Do this: " + _paint_hint(port) + "." + term)
    where = "" if st.get("visible_here", True) else " (on a phone only; the side panel here doesn't show it)"
    return f"this tree's Workshop is in view on port {port}{where}"


def workshop_state(where=None, timeout=0.6):
    """What the user can see of the Workshop of the tree here: {"state": none|hidden|visible|unknown, "port", ...}.
    Asks the server itself: a pointer file with a live pid is not enough (pids get reused, a server can hang)."""
    w = workshop_for(where)
    if not w:
        return {"state": "none"}
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{w['port']}/ping", timeout=timeout) as r:
            j = json.load(r)
    except Exception:
        return {"state": "none", "port": w["port"]}
    if os.path.realpath(j.get("data", "")) != os.path.realpath(w.get("data", "")):
        return {"state": "none", "port": w["port"]}
    if "visible" not in j:
        return {"state": "unknown", "port": w["port"]}
    return dict(j, state="visible" if j.get("visible") else "hidden", port=w["port"])


def _once(root, kind, every):
    """True at most once per `every` seconds per tree and kind (a mark file in the temp folder)."""
    mark = os.path.join(tempfile.gettempdir(), "family-tree-research-warned", _key(root) + "-" + kind)
    try:
        if time.time() - os.path.getmtime(mark) < every:
            return False
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(mark), exist_ok=True)
        open(mark, "w").close()
    except OSError:
        pass
    return True


def warn_state(st, where=None):
    """Research in a tree's folder while the user can't see its Workshop: say so on stderr, so Claude acts on it.
    Silent outside a tree, when it is in view, with FTR_QUIET set, and for a while after it said it (WARN_*_EVERY)."""
    if os.environ.get("FTR_QUIET") or st.get("state") == "visible":
        return
    root = tree_root(os.environ.get("FTR_TREE") or where)
    if not root:
        return
    if not _once(root, st.get("state") or "none", WARN_NONE_EVERY if st.get("state") == "none" else WARN_HIDDEN_EVERY):
        return
    print("Note (Claude Code only, ignore in Cowork): " + state_text(st), file=sys.stderr)


def warn_closed(where=None):  # the old name, kept for scripts that call it
    warn_state({"state": "none"}, where)


LAST = {}  # what the last emit() learned: {"state", "port", "viewers", "visible", ...}


def emit(kind, _where=None, _warn=True, **fields):
    """Send one event to the Workshop of this tree. Silent and fast when none is running or none belongs here.
    Inside a tree's folder it says on stderr (now and then) when the Workshop isn't running or nobody sees it.
    LAST keeps what the server answered, so live.py note/focus/progress can say it every time."""
    LAST.clear()
    p = workshop_for(_where)
    if not p:
        LAST.update(state="none")
        if _warn:
            warn_state(LAST, _where)
        return False
    ev = {"kind": kind, "t": round(time.time(), 2)}
    who = os.environ.get("FTR_WHO") or os.environ.get("STAMBOOM_WIE")
    if who:
        ev["who"] = who[:40]
    ev.update({k: v for k, v in fields.items() if v not in (None, "", [])})
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{p['port']}/event", data=json.dumps(ev).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        raw = urllib.request.urlopen(req, timeout=0.6).read()
    except Exception:
        LAST.update(state="none", port=p["port"])
        if _warn:
            warn_state(LAST, _where)
        return False
    try:
        j = json.loads(raw.decode("utf-8"))
        LAST.update(j, state="visible" if j.get("visible") else "hidden", port=p["port"])
    except (ValueError, UnicodeDecodeError, AttributeError, TypeError):
        LAST.update(state="unknown", port=p["port"])  # an older server answers "ok"
    if _warn:
        warn_state(LAST, _where)
    return True


# ---------------------------------------------------------------- what changed in the tree (the Changes tab)
def _pkey(p, i):
    return str(p.get("id") or f"#{i}").replace("@", "")


def _yrs(p):
    if p.get("levend") or p.get("living"):
        return ""
    by, dy = p.get("by"), p.get("dy")
    return f"{by or '?'}{'–' + str(dy) if dy else ''}" if (by or dy) else ""


def _cert(p, s):
    c = (p.get("c") or {}).get(s) or []
    return (list(c) + ["", "", "", ""])[:4]


def tree_changes(old, new):
    """The real changes between two data.json versions, one item per change, with names so the page needs no
    lookup: people added/removed, parent links added/removed, certainty, source or reason, kind of link
    (raised/adopted), name, dates, own story, photos, occupations."""
    oP, nP = old.get("personen") or [], new.get("personen") or []
    oi = {_pkey(p, i): i for i, p in enumerate(oP)}
    ni = {_pkey(p, i): i for i, p in enumerate(nP)}
    nm = lambda P, i: P[i].get("n") or " ".join(x for x in (P[i].get("g"), P[i].get("s")) if x) or "?"
    par = lambda P, i, s: _pkey(P[P[i][s]], P[i][s]) if isinstance(P[i].get(s), int) and P[i][s] >= 0 else None
    out = []
    for k, i in ni.items():
        n = nP[i]
        if k not in oi:
            out.append({"op": "add", "k": k, "name": nm(nP, i), "yrs": _yrs(n)})
        else:
            o = oP[oi[k]]
            if o.get("n") != n.get("n"):
                out.append({"op": "name", "k": k, "name": nm(nP, i), "from": o.get("n") or "", "to": n.get("n") or ""})
            od = " – ".join(x for x in (o.get("bdate"), o.get("ddate")) if x)
            nd = " – ".join(x for x in (n.get("bdate"), n.get("ddate")) if x)
            if od != nd:
                out.append({"op": "dates", "k": k, "name": nm(nP, i), "from": od, "to": nd})
            if n.get("verhaal") and not o.get("verhaal"):
                out.append({"op": "story", "k": k, "name": nm(nP, i)})
            elif n.get("verhaal") and json.dumps(o.get("verhaal"), sort_keys=True) != json.dumps(n.get("verhaal"), sort_keys=True):
                out.append({"op": "storyEdit", "k": k, "name": nm(nP, i)})
            if len(n.get("media") or []) > len(o.get("media") or []):
                out.append({"op": "media", "k": k, "name": nm(nP, i), "n": len(n.get("media") or []) - len(o.get("media") or [])})
            ob, nb = o.get("beroep") or [], n.get("beroep") or []
            for j in nb:
                if j not in ob:
                    out.append({"op": "job", "k": k, "name": nm(nP, i), "text": j})
        for s in ("f", "m"):
            a = par(oP, oi[k], s) if k in oi else None
            b = par(nP, i, s)
            nc = _cert(n, s)
            if a != b:
                if a:
                    out.append({"op": "unlink", "k": k, "name": nm(nP, i), "p": a, "pname": nm(oP, oi[a]), "s": s})
                if b:
                    out.append({"op": "link", "k": k, "name": nm(nP, i), "p": b, "pname": nm(nP, ni[b]), "s": s,
                                "to": nc[0], "src": nc[1], "why": nc[2], "type": nc[3]})
            elif b:
                oc = _cert(oP[oi[k]], s)
                base = {"k": k, "name": nm(nP, i), "p": b, "pname": nm(nP, ni[b]), "s": s}
                if oc[0] != nc[0]:
                    out.append(dict(base, op="cert", **{"from": oc[0], "to": nc[0], "src": nc[1], "why": nc[2]}))
                elif oc[1] != nc[1] or oc[2] != nc[2]:
                    out.append(dict(base, op="why", src=nc[1], why=nc[2]))
                if oc[3] != nc[3]:
                    out.append(dict(base, op="type", **{"from": oc[3], "to": nc[3]}))
    for k, i in oi.items():
        if k not in ni:
            out.append({"op": "del", "k": k, "name": nm(oP, i), "yrs": _yrs(oP[i])})
    return out


STEP_CHANGES = ("event", "drop_event", "aka", "places", "note")  # round steps that change the tree but not data.json's people


# ---------------------------------------------------------------- the server
class Hub:
    def __init__(self):
        self.clients, self.lock = [], threading.Lock()
        self.history = deque(maxlen=80)
        self.tasks = {}  # latest progress per task, so a page opened halfway sees the bars
        self.seen = set()  # round steps already shown (rebuild sends the whole last round every time)
        # the whole session, for the replay button: every event in order, every data.json version (compressed)
        self.start = round(time.time(), 2)
        self.timeline, self.versions = [], []
        self.changes = []  # [{t, n?, title?, items}] every real change to the tree in this session, for the Changes tab
        self.viewers = {}  # page id → {"sse": open event streams, "vis": in view, "beat": last report, "local": this computer}
        self.last = time.time()  # last sign of use (an event, a page): IDLE_STOP counts from here

    # ---- who sees it (the three states, see BEAT_FRESH / VIEWER_TTL)
    def _viewer(self, vid, local):
        v = self.viewers.setdefault(vid, {"sse": 0, "vis": False, "beat": 0.0, "local": local})
        v["local"] = v["local"] or local
        return v

    def viewer_join(self, vid, local):
        with self.lock:
            self._viewer(vid, local)["sse"] += 1

    def viewer_leave(self, vid):
        with self.lock:
            v = self.viewers.get(vid)
            if v:
                v["sse"] = max(0, v["sse"] - 1)

    def viewer_report(self, vid, local, visible=False, gone=False, now=None, size=None):
        with self.lock:
            if gone:  # the page closes (pagehide): it is gone at once, even before its event stream breaks
                self.viewers.pop(vid, None)
                return
            v = self._viewer(vid, local)
            v["vis"], v["beat"] = bool(visible), now if now is not None else time.time()
            if size:
                v["size"] = size

    def view_state(self, now=None):
        """{"viewers": pages that have it open, "visible": any page shows it now, "visible_here": one on this computer}.
        Open = its event stream is connected (or it reported within VIEWER_TTL). In view = it said so within BEAT_FRESH."""
        now = now if now is not None else time.time()
        with self.lock:
            for k in [k for k, v in self.viewers.items() if not v["sse"] and now - v["beat"] > VIEWER_TTL]:
                del self.viewers[k]
            vs = list(self.viewers.values())
        seen = [v for v in vs if v["vis"] and now - v["beat"] <= BEAT_FRESH]
        pages = [{"visible": v in seen, "here": v["local"], "size": v.get("size", ""),
                  "said": round(now - v["beat"]) if v["beat"] else None} for v in vs]
        return {"viewers": len(vs), "visible": bool(seen), "visible_here": any(v["local"] for v in seen), "pages": pages}

    def add_changes(self, t, items, n=None, title=None):
        if not items:
            return None
        g = {"t": t, "items": items}
        if n is not None:
            g["n"] = n
        if title:
            g["title"] = title
        self.changes.append(g)
        return g

    def add_version(self, raw):
        if len(self.versions) >= MAX_VERSIONS:
            return None
        self.versions.append(zlib.compress(raw, 6))
        return len(self.versions) - 1

    def record(self, ev):
        if len(self.timeline) < MAX_TIMELINE and ev.get("kind") != "hello":
            self.timeline.append(ev)

    def idle(self, now=None):
        """Seconds without use: 0 while a page has an event stream open."""
        with self.lock:
            if self.clients:
                self.last = time.time()
                return 0
        return (now if now is not None else time.time()) - self.last

    def stop_tasks(self, task=None, who=None, why="stop", now=None):
        """Grey the open bars of one task or one worker (or every bar when both are None)."""
        now = now if now is not None else time.time()
        hits = [e for e in list(self.tasks.values()) if not e.get("stopped")
                and (task is None or e.get("task") == task) and (who is None or e.get("who") == who)]
        for e in hits:
            self.send(dict(e, t=round(now, 2), stopped=why, last=e.get("t")), use=False)
        return len(hits)

    def drop_grey(self):
        """A new session: the grey bars of earlier work leave the list now."""
        for e in [e for e in list(self.tasks.values()) if e.get("stopped")]:
            self.send({"kind": "progress", "t": round(time.time(), 2), "task": e.get("task"), "gone": True}, keep=False, use=False)

    def sweep_tasks(self, now=None):
        """Bars nobody finishes: grey after TASK_QUIET, gone later. Not a sign of use (IDLE_STOP keeps counting)."""
        now = now if now is not None else time.time()
        for e in list(self.tasks.values()):
            if not e.get("stopped"):
                if now - (e.get("t") or now) > TASK_QUIET:
                    self.stop_tasks(task=e.get("task"), why="quiet", now=now)
                continue
            gone = (e.get("last") or e["t"]) + TASK_QUIET_GONE if e["stopped"] == "quiet" else e["t"] + TASK_STOPPED_GONE
            if now > gone:
                self.send({"kind": "progress", "t": round(now, 2), "task": e.get("task"), "gone": True}, keep=False, use=False)

    def send(self, ev, keep=True, use=True):
        if use:
            self.last = time.time()
        if ev.get("kind") == "stop":  # live.py progress --stop, a helper that ended, a new session
            if ev.get("grey"):
                self.drop_grey()
            elif ev.get("task") is not None or ev.get("who"):
                self.stop_tasks(task=ev.get("task"), who=ev.get("who") if ev.get("task") is None else None, now=ev.get("t"))
            return
        if ev.get("kind") == "steps":
            rnd, new = str(ev.get("round") or ""), []
            for st in ev.get("steps") or []:
                k = rnd + json.dumps(st, sort_keys=True, ensure_ascii=False)
                if k not in self.seen:
                    self.seen.add(k)
                    new.append(st)
            if not new:
                return
            ev = dict(ev, steps=new)
            ch = [dict(st, op="step:" + str(st.get("op"))) for st in new if st.get("op") in STEP_CHANGES]
            g = self.add_changes(ev.get("t") or round(time.time(), 2), ch, title=ev.get("title") or ev.get("round"))
            if g:
                ev["ch"] = g
        if ev.get("kind") == "progress":
            name = str(ev.get("task") or "")
            old = self.tasks.get(name)
            first = not old or bool(old.get("stopped"))
            done = ev.get("done") == ev.get("total") or bool(ev.get("gone"))
            self.tasks[name] = ev
            if done:
                self.tasks.pop(name, None)
            # the log keeps only the start and the end of a task (finished or stopped), never the bar leaving
            keep = keep and not ev.get("gone") and (first or done or bool(ev.get("stopped")))
        if keep:
            self.history.append(ev)
        self.record(ev)
        with self.lock:
            for q in list(self.clients):
                q.put(ev)

    def join(self):
        q = queue.Queue()
        with self.lock:
            self.clients.append(q)
        return q

    def leave(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)


MAX_VERSIONS, MAX_TIMELINE = 600, 60000  # ~150 kB per version of a 1,200-person tree
# progress bars that never got their last step (a helper stopped early, a usage limit, the end of the night):
TASK_QUIET = 30 * 60         # a bar without a new step this long turns grey: "stopped at 53 / 80"
TASK_QUIET_GONE = 3 * 3600   # ...and leaves the list this long after its last step (the log keeps one line)
TASK_STOPPED_GONE = 10 * 60  # a bar stopped on purpose (progress --stop, its helper ended) stays grey this long
IDLE_STOP = 6 * 3600  # a Workshop nobody has open and nobody sends anything to stops itself after this long
KEEPER_CHECK = 3  # seconds between the keeper's checks that its Workshop still answers
KEEPALIVE = 10  # seconds between keep-alive lines on an event stream: a page that went away is noticed within ~2 of them


def _plugin_version():
    try:
        with open(os.path.join(HERE, "..", "..", "..", ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            return json.load(fh).get("version") or ""
    except (OSError, ValueError):
        return ""


PLUGIN_VERSION = _plugin_version()


def watch(path, hub, stop):
    """Tell the pages when data.json changed (and is complete JSON again); keep every version for the replay."""
    last, doc, swept = None, None, 0.0
    while not stop.is_set():
        try:
            st = os.stat(path)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        if sig and sig != last:
            try:
                with open(path, "rb") as fh:
                    raw = fh.read()
                new = json.loads(raw.decode("utf-8"))
                n = hub.add_version(raw)
                if last is not None:
                    ev = {"kind": "data", "t": round(time.time(), 2), "v": sig[0]}
                    if n is not None:
                        ev["n"] = n
                    try:
                        g = hub.add_changes(ev["t"], tree_changes(doc or {}, new), n=n)
                    except Exception:  # a change list must never stop the Workshop
                        g = None
                    if g:
                        ev["ch"] = g
                    hub.send(ev, keep=False)
                last, doc = sig, new
            except (OSError, ValueError):
                pass  # still being written: try again in a moment
        if time.time() - swept > 30:
            hub.sweep_tasks()
            swept = time.time()
        stop.wait(0.5)


def make_handler(cfg, hub):
    loopback = ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    class H(BaseHTTPRequestHandler):
        server_version = "FamilyTreeWorkshop"

        def log_message(self, *a):
            pass

        def local(self):
            return self.client_address[0] in loopback

        def allowed(self, qs):
            if self.local():
                return True
            if qs.get("k", [""])[0] == cfg["token"]:
                return True
            cookie = self.headers.get("Cookie", "")
            return f"ftrk={cfg['token']}" in cookie.replace(" ", "").split(";")

        def body(self, code, data, ctype, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def file(self, path, extra=None):
            ext = os.path.splitext(path)[1].lower()
            ctype = {".html": "text/html; charset=utf-8", ".json": "application/json", ".js": "text/javascript",
                     ".css": "text/css", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                     ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
                     ".pdf": "application/pdf"}.get(ext, "application/octet-stream")
            try:
                with open(path, "rb") as fh:
                    self.body(200, fh.read(), ctype, extra)
            except OSError:
                self.body(404, b"not found", "text/plain")

        def do_GET(self):
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if not self.allowed(qs):
                return self.body(403, b"This Workshop needs the address with ?k=... that live.py printed.", "text/plain")
            extra = {}
            if not self.local() and qs.get("k"):
                extra["Set-Cookie"] = f"ftrk={cfg['token']}; Path=/; Max-Age=2592000; SameSite=Strict"  # 30 days"
            p = unquote(u.path)
            if p in ("/", "/index.html"):
                return self.file(os.path.join(VIEWER, "live.html"), extra)
            if p in ("/data.json", "/viewer/data.json"):
                return self.file(cfg["data"], extra)
            if p in ("/viewer", "/viewer/"):
                return self.file(os.path.join(VIEWER, "index.html"), extra)
            if p == "/events":
                return self.events((qs.get("id") or [""])[0][:40])
            if p == "/session":  # the replay: when it started and everything that happened, in order
                return self.body(200, json.dumps({"start": hub.start, "events": hub.timeline}).encode("utf-8"), "application/json")
            if p.startswith("/session/data/"):  # one data.json version of this session (0 = how the tree was at the start)
                try:
                    raw = zlib.decompress(hub.versions[int(p.rsplit("/", 1)[1])])
                except (ValueError, IndexError):
                    return self.body(404, b"no such version", "text/plain")
                return self.body(200, raw, "application/json")
            if p == "/phone":  # the phone address with its key, only for the page on this computer (the QR button)
                if not self.local():
                    return self.body(403, b"only on this computer", "text/plain")
                if cfg["local"]:
                    return self.body(200, b'{"url": null, "why": "local"}', "application/json")
                ip = lan_ip()  # asked on every tap: a laptop changes networks
                body = {"url": f"http://{ip}:{cfg['port']}/?k={cfg['token']}"} if ip else {"url": None, "why": "nonet"}
                return self.body(200, json.dumps(body).encode("utf-8"), "application/json")
            if p == "/ping":  # which tree this Workshop shows (serve/launch reuse a running one) and whether anyone sees it
                body = dict({"data": cfg["data"], "pid": os.getpid(), "version": PLUGIN_VERSION}, **hub.view_state())
                return self.body(200, json.dumps(body).encode("utf-8"), "application/json")
            if p.startswith("/viewer/"):  # media next to the viewer: media/x.jpg
                rel = os.path.normpath(p[len("/viewer/"):])
                if rel.startswith("..") or os.path.isabs(rel):
                    return self.body(404, b"not found", "text/plain")
                for root in cfg["media"]:
                    f = os.path.join(root, rel)
                    if os.path.isfile(f):
                        return self.file(f)
            self.body(404, b"not found", "text/plain")

        def do_POST(self):
            u = urlparse(self.path)
            if u.path == "/seen":  # a page says whether it is in view (live.html; a phone with the key too)
                if not self.allowed(parse_qs(u.query)):
                    return self.body(403, b"no key", "text/plain")
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    r = json.loads(self.rfile.read(min(n, 4000)).decode("utf-8") or "{}")
                    vid = str(r.get("id") or "")[:40]
                    if not vid:
                        raise ValueError
                except (ValueError, UnicodeDecodeError, AttributeError):
                    return self.body(400, b"bad report", "text/plain")
                size = (f"{r.get('w')}x{r.get('h')} {r.get('vs') or ''}" + (f" {r['fps']} fps" if "fps" in r else "")).strip() if "w" in r else None
                hub.viewer_report(vid, self.local(), visible=r.get("visible"), gone=r.get("gone"), size=size)
                return self.body(200, json.dumps(hub.view_state()).encode("utf-8"), "application/json")
            if u.path != "/event" or not self.local():
                return self.body(403, b"only this computer can send events", "text/plain")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                ev = json.loads(self.rfile.read(min(n, 1000000)).decode("utf-8"))
                if not isinstance(ev, dict) or not ev.get("kind"):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                return self.body(400, b"bad event", "text/plain")
            ev = {k: (v[:400] if isinstance(v, str) else v) for k, v in ev.items()}
            hub.send(ev)
            self.body(200, json.dumps(dict({"ok": True}, **hub.view_state())).encode("utf-8"), "application/json")

        def events(self, vid=""):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            q = hub.join()
            if vid:
                hub.viewer_join(vid, self.local())
            try:
                hello = {"kind": "hello", "history": list(hub.history), "tasks": list(hub.tasks.values()),
                         "changes": list(hub.changes)}
                self.wfile.write(f"data: {json.dumps(hello)}\n\n".encode("utf-8"))
                self.wfile.flush()
                while True:
                    try:
                        ev = q.get(timeout=KEEPALIVE)
                        self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": still here\n\n")  # also how a closed page is noticed (the write fails)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.leave(q)
                if vid:
                    hub.viewer_leave(vid)

    return H


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; this only picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def resolve(a):
    """data.json and media folders from --config / --data (or a settings file in this folder)."""
    media = [os.path.abspath(m) for m in (a.media or [])]
    if a.data:
        data = os.path.abspath(a.data)
    else:
        cfgp = a.config or next((n for n in CONFIG_NAMES if os.path.isfile(n)), None)
        if not cfgp:
            sys.exit("No data: give --config family-tree.json or --data data.json")
        try:
            raw = json.load(open(cfgp, encoding="utf-8-sig"))
        except (OSError, ValueError) as e:
            sys.exit(f"Settings file {cfgp}: {e}")
        base = os.path.dirname(os.path.abspath(cfgp))
        out = raw.get("output") or raw.get("uit") or "data.json"
        data = os.path.join(base, os.path.expanduser(out))
        md = raw.get("media_dir") or raw.get("media_map")
        if md:
            media.append(os.path.dirname(os.path.join(base, md)))  # media/x.jpg is relative to the folder above media/
    if not os.path.isfile(data):
        sys.exit(f"{data} does not exist yet: build it first with make_viewer_data.py")
    media.append(os.path.dirname(data))
    # the tree's folder: where the settings file is, else above data/ (events from scripts run there go to this Workshop)
    root = os.path.abspath(a.root) if getattr(a, "root", None) else (
        os.path.dirname(os.path.abspath(cfgp)) if not a.data else
        (os.path.dirname(os.path.dirname(data)) if os.path.basename(os.path.dirname(data)).lower() == "data" else os.path.dirname(data)))
    return data, media, root


def running_for(data):
    """A Workshop that already shows this data.json (and answers), or None."""
    for w in workshops():
        if os.path.realpath(w.get("data", "")) != os.path.realpath(data):
            continue
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{w['port']}/ping", timeout=1) as r:
                if os.path.realpath(json.load(r).get("data", "")) == os.path.realpath(data):
                    return w
        except Exception:
            pass
    return None


def free_port(start, n=40):
    for port in range(start, start + n):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("0.0.0.0", port))  # free for the Wi-Fi as well as for this computer
            return port
        except OSError:
            continue
        finally:
            s.close()
    return None


def _log_path(data):
    return os.path.join(POINTERS, _key(data) + ".log")


def cmd_serve(a):
    """Make sure this tree's Workshop runs, on its own, then keep it company.
    The desktop app stops a session's servers when that session is archived; the Workshop belongs to the tree, not
    to one session, so the server itself runs in its own process group and this process is only its keeper: it
    stays while the Workshop answers (so the app sees a running server) and ends quietly on the app's stop (SIGTERM).
    Ctrl+C (in a terminal) stops the Workshop too."""
    if a.detached:
        return serve_here(a)
    data, _, _ = resolve(a)
    old = running_for(data)
    if old:
        print(f"Workshop for this tree is already running: http://127.0.0.1:{old['port']}/")
    else:
        os.makedirs(POINTERS, exist_ok=True)
        log = _log_path(data)
        with open(log, "w", encoding="utf-8") as fh:
            child = subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__)] + sys.argv[1:] + ["--detached"],
                                     stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                                     start_new_session=True, close_fds=True)
        end = time.time() + 20
        while not old and child.poll() is None and time.time() < end:
            time.sleep(0.2)  # its own signal: the pointer file plus an answer on /ping
            old = running_for(data)
        try:
            print(open(log, encoding="utf-8").read().rstrip())
        except OSError:
            pass
        if not old:
            if child.poll() is None:
                child.terminate()
            sys.exit(child.returncode or "The Workshop did not start (see above)")
    sys.stdout.flush()
    keep(old, data)


def keep(w, data):
    """Stay while the Workshop answers. SIGTERM (the desktop app) leaves it running; Ctrl+C stops it."""
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    try:
        while not done.wait(KEEPER_CHECK):
            if not running_for(data):
                print("The Workshop stopped.")
                return
    except KeyboardInterrupt:
        try:
            os.kill(int(w["pid"]), signal.SIGTERM)
            print("Workshop stopped.")
        except (OSError, ValueError, KeyError):
            pass


def cmd_stop(a):
    if a.tree:
        os.environ["FTR_TREE"] = a.tree
    w = workshop_for()
    if not w:
        print("No Workshop runs for this tree.")
        return
    try:
        os.kill(int(w["pid"]), signal.SIGTERM)
    except (OSError, ValueError) as e:
        sys.exit(f"Could not stop it: {e}")
    print(f"Workshop on port {w['port']} stopped.")


def serve_here(a):
    """The server itself (started by cmd_serve in its own process group)."""
    data, media, root = resolve(a)
    if running_for(data):
        return
    hub = Hub()
    cfg = {"data": data, "media": media, "local": a.local, "token": secrets.token_urlsafe(9) if a.local else tree_key(data)}
    srv = None
    for port in ([a.port] if a.exact else range(a.port, a.port + 40)):  # another tree may have the first port
        for host in (["127.0.0.1"] if a.local else ["0.0.0.0", "127.0.0.1"]):  # the Wi-Fi too, unless that isn't possible here
            try:
                srv = ThreadingHTTPServer((host, port), make_handler(cfg, hub))
                break
            except OSError as e:
                if e.errno == errno.EADDRINUSE:
                    break  # the port is taken (perhaps by another tree on 0.0.0.0): never sneak in on 127.0.0.1, next port
                continue
        if srv:
            break
    if srv and srv.server_address[0] == "127.0.0.1":
        cfg["local"] = True
    if not srv:
        sys.exit(f"Port {a.port} is taken by something else: run `live.py launch` again (it picks a free port)" if a.exact
                 else f"No free port between {a.port} and {a.port + 39}")
    srv.daemon_threads = True
    port = cfg["port"] = srv.server_address[1]
    os.makedirs(POINTERS, exist_ok=True)
    POINTER = os.path.join(POINTERS, _key(data) + ".json")
    with open(POINTER, "w", encoding="utf-8") as fh:
        json.dump({"port": port, "pid": os.getpid(), "data": data, "root": root}, fh)
    if port != a.port:
        print(f"(port {a.port} was taken, probably by another tree's Workshop: this one uses {port})")
    stop = threading.Event()
    threading.Thread(target=watch, args=(data, hub, stop), daemon=True).start()

    def idle_stop():
        while not stop.wait(60):
            if hub.idle() > IDLE_STOP:
                print(f"Nobody watched and nothing was sent for {IDLE_STOP // 3600} hours: the Workshop stops.")
                sys.stdout.flush()
                srv.shutdown()
                return
    threading.Thread(target=idle_stop, daemon=True).start()
    print(f"Workshop: http://127.0.0.1:{port}/   (viewer: http://127.0.0.1:{port}/viewer/)")
    print(f"watching {data}")
    if not cfg["local"]:
        ip = lan_ip()
        print(f"phone on the same Wi-Fi: http://{ip or '<this computer>'}:{port}/?k={cfg['token']}  (or tap the phone button in the Workshop for a QR code)")
        print("(only with that key; if macOS asks whether Python may accept incoming connections, allow it)")
    sys.stdout.flush()

    def on_term(*_):
        raise KeyboardInterrupt  # a stop from the desktop app or kill: clean up the pointer too
    signal.signal(signal.SIGTERM, on_term)
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        try:
            p = json.load(open(POINTER, encoding="utf-8"))
            if p.get("pid") == os.getpid():
                os.remove(POINTER)
        except (OSError, ValueError):
            pass


def cmd_launch(a):
    """Write the `workshop` entry of the tree's .claude/launch.json with this live.py (so a plugin update never starts
    an old one) and a port that is this tree's own: the running Workshop's port, else a free one."""
    data, _, root = resolve(a)
    w = running_for(data)
    port = w["port"] if w else free_port(a.port)
    if not port:
        sys.exit(f"No free port from {a.port}")
    path = os.path.abspath(a.file) if a.file else os.path.join(root, ".claude", "launch.json")
    try:
        with open(path, encoding="utf-8") as fh:
            conf = json.load(fh)
    except FileNotFoundError:
        conf = {"version": "0.0.1", "configurations": []}
    except ValueError as e:
        sys.exit(f"{path} is not valid JSON ({e}): fix it first, nothing was changed")
    src = ["--config", os.path.abspath(a.config or next(n for n in CONFIG_NAMES if os.path.isfile(n)))] if not a.data else ["--data", data]
    entry = {"name": a.name, "runtimeExecutable": sys.executable or "python3",
             "runtimeArgs": ["-I", os.path.abspath(__file__), "serve", *src, "--root", root, "--port", str(port), "--exact"]
             + (["--local"] if a.local else []),
             "port": port}
    confs = [c for c in conf.get("configurations", []) if c.get("name") != a.name]  # other entries stay
    conf["configurations"] = confs + [entry]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(conf, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    print(f"{path}: entry \"{a.name}\" on port {port}" + (" (this tree's Workshop is already running there)" if w else "")
          + ".")
    print(launch_steps(a.name, port))


def launch_steps(name, port):
    """The steps after `launch`, spelled out: the Workshop is only open once the user can see it."""
    return (
        "Next, in the Claude desktop app (all three, every time):\n"
        f"  1. preview_start with name \"{name}\"\n"
        "  2. load and call mcp__ccd_view__show_pane with pane 'preview' (ToolSearch \"select:mcp__ccd_view__show_pane\"); "
        "the pane can stay hidden after preview_start\n"
        "  3. check: live.py status --wait 10 must say \"visible\" (it waits for the page's own signal; or "
        f"curl -s http://127.0.0.1:{port}/ping: \"visible\": true and this tree's data.json).\n"
        "     Not visible = the user sees nothing yet: call show_pane again (or tabs_select the Workshop tab). If show_pane\n"
        "     says the session isn't open in any window, the user is elsewhere: say in the chat that the Workshop is ready.\n"
        "Only then tell the user it is there, and send a note with what you are doing.\n"
        f"In a terminal without a browser pane: run `live.py serve` in the background and give the user http://127.0.0.1:{port}/")


def _say_state(what):
    """After note/focus/progress: say plainly when the user can't see it (every time; silent when in view)."""
    if LAST.get("state") != "visible":
        print(f"({what} {'sent' if LAST.get('state') != 'none' else 'not shown'}, but {state_text(LAST)})")


def cmd_focus(a):
    if a.tree:
        os.environ["FTR_TREE"] = a.tree
    emit("focus", _warn=False, person=a.person, text=a.text)
    _say_state("focus")


def cmd_progress(a):
    if a.tree:
        os.environ["FTR_TREE"] = a.tree
    if a.stop:  # a bar that won't finish (the find came early): grey now, gone in a few minutes
        emit("stop", _warn=False, task=a.task)
    elif a.done is None or a.total is None:
        sys.exit('live.py progress "<task>" <done> <total>, or progress "<task>" --stop')
    else:
        emit("progress", _warn=False, task=a.task, done=a.done, total=a.total, person=a.person, text=a.text)
    _say_state("progress")


def cmd_note(a):
    if a.tree:
        os.environ["FTR_TREE"] = a.tree
    emit(a.kind, _warn=False, text=a.text, person=a.person)
    _say_state("note")
    if not a.person:  # the page then points at the last person this helper worked on; say so, so a new person gets named
        print("(no --person: the beam stays on the last person you worked on; add --person <GEDCOM id or full name> when this is about someone else)",
              file=sys.stderr)


def cmd_status(a):
    """Which of the three states this tree's Workshop is in (exit 0 only when the user can see it)."""
    if a.tree:
        os.environ["FTR_TREE"] = a.tree
    st = workshop_state()
    end = time.time() + max(0, a.wait or 0)
    while st["state"] != "visible" and time.time() < end:  # wait for the page's own signal, not a guess
        time.sleep(0.5)
        st = workshop_state()
    if a.json:
        print(json.dumps(st))
    else:
        print(st["state"] + ": " + state_text(st))
    sys.exit(0 if st["state"] == "visible" else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("serve", aliases=["serveer", "start"], help="start the Workshop page")
    s.add_argument("--config", "--instellingen", help="settings file (family-tree.json / stamboom.json)")
    s.add_argument("--data", help="data.json (instead of --config)")
    s.add_argument("--port", "--poort", type=int, default=8790)
    s.add_argument("--local", "--lokaal", action="store_true", help="only this computer (by default a phone on the same Wi-Fi can watch, with the key)")
    s.add_argument("--lan", "--wifi", action="store_true", help=argparse.SUPPRESS)  # the default since 0.9.67; kept so old entries still start
    s.add_argument("--media", action="append", help="extra folder to serve viewer media from (repeatable)")
    s.add_argument("--root", help="the tree's folder (default: where the settings file is, else above data/)")
    s.add_argument("--exact", action="store_true", help="only this port (launch.json entries use it)")
    s.add_argument("--detached", action="store_true", help=argparse.SUPPRESS)  # the server itself, started by serve
    s.set_defaults(func=cmd_serve)
    st = sp.add_parser("stop", help="stop this tree's Workshop")
    st.add_argument("--tree", "--boom", help="the tree's folder, when you run this from somewhere else")
    st.set_defaults(func=cmd_stop)
    la = sp.add_parser("launch", help="write the workshop entry in the tree's .claude/launch.json (desktop app)")
    la.add_argument("--config", "--instellingen")
    la.add_argument("--data")
    la.add_argument("--port", "--poort", type=int, default=8790)
    la.add_argument("--local", "--lokaal", action="store_true")
    la.add_argument("--lan", "--wifi", action="store_true", help=argparse.SUPPRESS)
    la.add_argument("--root")
    la.add_argument("--media", action="append")
    la.add_argument("--name", default="workshop")
    la.add_argument("--file", help="launch.json to write (default: <tree folder>/.claude/launch.json)")
    la.set_defaults(func=cmd_launch)
    n = sp.add_parser("note", aliases=["notitie"], help="show one line in the Workshop")
    n.add_argument("text")
    n.add_argument("--person", "--persoon", help="GEDCOM id (I4 or @I4@) or name: the scanner points there")
    n.add_argument("--kind", "--soort", default="note",
                   choices=["note", "read", "found", "nothing", "ask", "notitie", "lees", "gevonden", "niets", "vraag"])
    n.add_argument("--tree", "--boom", help="the tree's folder, when you run this from somewhere else")
    n.set_defaults(func=cmd_note)
    f = sp.add_parser("focus", aliases=["bezig"], help="show who you are working on now (a ring + name at their star)")
    f.add_argument("person", help="GEDCOM id (I4) or name; someone outside the fan shows at their nearest relative")
    f.add_argument("text", nargs="?", help="what you are looking for, e.g. 'parents'")
    f.add_argument("--tree", "--boom", help="the tree's folder, when you run this from somewhere else")
    f.set_defaults(func=cmd_focus)
    g = sp.add_parser("progress", aliases=["voortgang"], help="a progress bar for a long script (send it every step)")
    g.add_argument("task", help="short name of the task, e.g. 'side branches'")
    g.add_argument("done", type=int, nargs="?")
    g.add_argument("total", type=int, nargs="?")
    g.add_argument("--stop", action="store_true", help="close this bar without finishing it (it turns grey, then goes)")
    g.add_argument("--person", "--persoon", help="who is being checked now (GEDCOM id or name): the scanner points there")
    g.add_argument("--text", "--tekst", help="one line about this step")
    g.add_argument("--tree", "--boom", help="the tree's folder, when you run this from somewhere else")
    g.set_defaults(func=cmd_progress)
    t = sp.add_parser("status", help="is this tree's Workshop running, and can the user see it? (exit 0 = in view)")
    t.add_argument("--json", action="store_true")
    t.add_argument("--wait", type=float, default=0, help="seconds to wait until it is in view (after show_pane)")
    t.add_argument("--tree", "--boom", help="the tree's folder, when you run this from somewhere else")
    t.set_defaults(func=cmd_status)
    a = ap.parse_args()
    if getattr(a, "kind", None):
        a.kind = {"notitie": "note", "lees": "read", "gevonden": "found", "niets": "nothing", "vraag": "ask"}.get(a.kind, a.kind)
    a.func(a)


if __name__ == "__main__":
    main()
