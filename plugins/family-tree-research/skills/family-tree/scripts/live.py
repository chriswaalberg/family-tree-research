#!/usr/bin/env python3
"""live.py — the Workshop: watch the family tree grow while Claude researches (Claude Code only).

  serve [--config family-tree.json | --data data.json]   start the local Workshop page (viewer/live.html); one per tree:
        [--port 8790] [--lan] [--media DIR ...]           if this tree's Workshop already runs, it says where and stops (0)
  launch [--config ... | --data ...] [--lan]            desktop app: write the `workshop` entry in the tree's
                                                        .claude/launch.json (this live.py, this tree's own port);
                                                        run it before every preview_start
  note "<text>" [--person I4] [--kind note|read|found|nothing|ask]
                                                        tell the Workshop what you are doing (one line)
  focus <I4 or name> ["what you look for"]            who you are working on now: ring + name at their star
  progress "<task>" <done> <total> [--person I4] [--text ...]
                                                        a progress bar for a long script; send it every step

Events go only to the Workshop of the tree you work in: the one whose folder holds the current folder (or the file
that rebuild/check writes, or FTR_TREE / --tree). Run scripts from the tree's folder.

The page shows the start person's ancestors (Cosmos, or the round Fan). Every time data.json changes (after gedcom_tool.py rebuild
and make_viewer_data.py) it compares the old and the new tree and animates the difference: new people fly in,
rejected links crack, links that became certain turn gold. archives.py, delpher.py and gedcom_tool.py check/
rebuild report what they do by themselves while a Workshop is running; for anything else use `note`.

By default only this computer can open the page (127.0.0.1). With --lan it also listens on the local network
and prints an address with a secret key (?k=...) for a phone; without the key nobody else sees anything, and
only this computer can send events.

A long script of your own can also call emit() directly instead of starting live.py for every step:
    spec = importlib.util.spec_from_file_location("ftr_live", "<skill>/scripts/live.py")
    live = importlib.util.module_from_spec(spec); spec.loader.exec_module(live)
    live.emit("progress", task="side branches", done=42, total=123, person="I87")
Helpers (subagents) set FTR_WHO=<short name> in front of their commands: each gets its own scanner beam.

Standard library only. Dutch aliases: serveer/start, notitie (--persoon, --soort, --boom), voortgang (--tekst, --boom).
"""
import argparse, hashlib, json, zlib, os, queue, secrets, signal, socket, sys, tempfile, threading, time, urllib.request
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
def emit(kind, _where=None, **fields):
    """Send one event to the Workshop of this tree. Silent and fast when none is running or none belongs here."""
    p = workshop_for(_where)
    if not p:
        return False
    ev = {"kind": kind, "t": round(time.time(), 2)}
    who = os.environ.get("FTR_WHO") or os.environ.get("STAMBOOM_WIE")
    if who:
        ev["who"] = who[:40]
    ev.update({k: v for k, v in fields.items() if v not in (None, "", [])})
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{p['port']}/event", data=json.dumps(ev).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=0.6).read()
        return True
    except Exception:
        return False


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

    def add_version(self, raw):
        if len(self.versions) >= MAX_VERSIONS:
            return None
        self.versions.append(zlib.compress(raw, 6))
        return len(self.versions) - 1

    def record(self, ev):
        if len(self.timeline) < MAX_TIMELINE and ev.get("kind") != "hello":
            self.timeline.append(ev)

    def send(self, ev, keep=True):
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
        if ev.get("kind") == "progress":
            name = str(ev.get("task") or "")
            first, done = name not in self.tasks, ev.get("done") == ev.get("total")
            self.tasks[name] = ev
            if done:
                self.tasks.pop(name, None)
            keep = keep and (first or done)  # the log keeps only the start and the end of a task
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


def watch(path, hub, stop):
    """Tell the pages when data.json changed (and is complete JSON again); keep every version for the replay."""
    last = None
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
                json.loads(raw.decode("utf-8"))
                n = hub.add_version(raw)
                if last is not None:
                    ev = {"kind": "data", "t": round(time.time(), 2), "v": sig[0]}
                    if n is not None:
                        ev["n"] = n
                    hub.send(ev, keep=False)
                last = sig
            except (OSError, ValueError):
                pass  # still being written: try again in a moment
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
                return self.events()
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
                return self.body(200, json.dumps({"url": cfg.get("phone")}).encode("utf-8"), "application/json")
            if p == "/ping":  # which tree this Workshop shows (live.py serve/launch use it to reuse a running one)
                return self.body(200, json.dumps({"data": cfg["data"], "pid": os.getpid()}).encode("utf-8"), "application/json")
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
            if urlparse(self.path).path != "/event" or not self.local():
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
            self.body(200, b"ok", "text/plain")

        def events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            q = hub.join()
            try:
                hello = {"kind": "hello", "history": list(hub.history), "tasks": list(hub.tasks.values())}
                self.wfile.write(f"data: {json.dumps(hello)}\n\n".encode("utf-8"))
                self.wfile.flush()
                while True:
                    try:
                        ev = q.get(timeout=15)
                        self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": still here\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.leave(q)

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
            s.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            s.close()
    return None


def cmd_serve(a):
    data, media, root = resolve(a)
    old = running_for(data)
    if old:  # this tree already has a Workshop: use that one (exit 0, so the desktop app's preview_start doesn't fail)
        print(f"Workshop for this tree is already running: http://127.0.0.1:{old['port']}/")
        return
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    hub = Hub()
    cfg = {"data": data, "media": media, "token": tree_key(data) if a.lan else secrets.token_urlsafe(9)}
    srv = None
    for port in ([a.port] if a.exact else range(a.port, a.port + 40)):  # another tree may have the first port
        try:
            srv = ThreadingHTTPServer((host, port), make_handler(cfg, hub))
            break
        except OSError:
            continue
    if not srv:
        sys.exit(f"Port {a.port} is taken by something else: run `live.py launch` again (it picks a free port)" if a.exact
                 else f"No free port between {a.port} and {a.port + 39}")
    srv.daemon_threads = True
    port = srv.server_address[1]
    os.makedirs(POINTERS, exist_ok=True)
    POINTER = os.path.join(POINTERS, _key(data) + ".json")
    with open(POINTER, "w", encoding="utf-8") as fh:
        json.dump({"port": port, "pid": os.getpid(), "data": data, "root": root}, fh)
    if port != a.port:
        print(f"(port {a.port} was taken, probably by another tree's Workshop: this one uses {port})")
    stop = threading.Event()
    threading.Thread(target=watch, args=(data, hub, stop), daemon=True).start()
    print(f"Workshop: http://127.0.0.1:{port}/   (viewer: http://127.0.0.1:{port}/viewer/)")
    print(f"watching {data}")
    if a.lan:
        ip = lan_ip()
        cfg["phone"] = f"http://{ip}:{port}/?k={cfg['token']}" if ip else None
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
             + (["--lan"] if a.lan else []),
             "port": port}
    confs = [c for c in conf.get("configurations", []) if c.get("name") != a.name]  # other entries stay
    conf["configurations"] = confs + [entry]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(conf, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    print(f"{path}: entry \"{a.name}\" on port {port}" + (" (this tree's Workshop is already running there)" if w else "")
          + f". Open it with preview_start name \"{a.name}\".")


def cmd_focus(a):
    if a.tree:
        os.environ["FTR_TREE"] = a.tree
    if not emit("focus", person=a.person, text=a.text):
        print("(no Workshop for this tree: focus not shown)")


def cmd_progress(a):
    if a.tree:
        os.environ["FTR_TREE"] = a.tree
    if not emit("progress", task=a.task, done=a.done, total=a.total, person=a.person, text=a.text):
        print("(no Workshop for this tree: progress not shown)")


def cmd_note(a):
    if a.tree:
        os.environ["FTR_TREE"] = a.tree
    ok = emit(a.kind, text=a.text, person=a.person)
    if not ok:
        print("(no Workshop for this tree: note not shown)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("serve", aliases=["serveer", "start"], help="start the Workshop page")
    s.add_argument("--config", "--instellingen", help="settings file (family-tree.json / stamboom.json)")
    s.add_argument("--data", help="data.json (instead of --config)")
    s.add_argument("--port", "--poort", type=int, default=8790)
    s.add_argument("--lan", "--wifi", action="store_true", help="also listen on the local network (address with a key)")
    s.add_argument("--media", action="append", help="extra folder to serve viewer media from (repeatable)")
    s.add_argument("--root", help="the tree's folder (default: where the settings file is, else above data/)")
    s.add_argument("--exact", action="store_true", help="only this port (launch.json entries use it)")
    s.set_defaults(func=cmd_serve)
    la = sp.add_parser("launch", help="write the workshop entry in the tree's .claude/launch.json (desktop app)")
    la.add_argument("--config", "--instellingen")
    la.add_argument("--data")
    la.add_argument("--port", "--poort", type=int, default=8790)
    la.add_argument("--lan", "--wifi", action="store_true")
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
    g.add_argument("done", type=int)
    g.add_argument("total", type=int)
    g.add_argument("--person", "--persoon", help="who is being checked now (GEDCOM id or name): the scanner points there")
    g.add_argument("--text", "--tekst", help="one line about this step")
    g.add_argument("--tree", "--boom", help="the tree's folder, when you run this from somewhere else")
    g.set_defaults(func=cmd_progress)
    a = ap.parse_args()
    if getattr(a, "kind", None):
        a.kind = {"notitie": "note", "lees": "read", "gevonden": "found", "niets": "nothing", "vraag": "ask"}.get(a.kind, a.kind)
    a.func(a)


if __name__ == "__main__":
    main()
