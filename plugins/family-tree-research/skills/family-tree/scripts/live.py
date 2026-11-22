#!/usr/bin/env python3
"""live.py — the Workshop: watch the family tree grow while Claude researches (Claude Code only).

  serve [--config family-tree.json | --data data.json]   start the local Workshop page (viewer/live.html)
        [--port 8790] [--lan] [--media DIR ...]
  note "<text>" [--person I4] [--kind note|read|found|nothing|ask]
                                                        tell the Workshop what you are doing (one line)
  progress "<task>" <done> <total> [--person I4] [--text ...]
                                                        a progress bar for a long script; send it every step

The page shows the round Fan of the start person. Every time data.json changes (after gedcom_tool.py rebuild
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

Standard library only. Dutch aliases: serveer/start, notitie (--persoon, --soort), voortgang (--tekst).
"""
import argparse, json, os, queue, secrets, signal, socket, sys, tempfile, threading, time, urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

POINTER = os.path.join(tempfile.gettempdir(), "family-tree-research-live.json")
HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.normpath(os.path.join(HERE, "..", "viewer"))
CONFIG_NAMES = ("family-tree.json", "stamboom.json")


# ---------------------------------------------------------------- sending events (used by the other scripts too)
def _pointer():
    try:
        with open(POINTER, encoding="utf-8") as fh:
            p = json.load(fh)
        os.kill(int(p["pid"]), 0)  # is that Workshop still running?
        return p
    except (OSError, ValueError, KeyError, TypeError):
        return None


def emit(kind, **fields):
    """Send one event to a running Workshop. Silent and fast (one file read) when none is running."""
    p = _pointer()
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


def watch(path, hub, stop):
    """Tell the pages when data.json changed (and is complete JSON again)."""
    last = None
    while not stop.is_set():
        try:
            st = os.stat(path)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        if sig and sig != last:
            try:
                with open(path, encoding="utf-8") as fh:
                    json.load(fh)
                if last is not None:
                    hub.send({"kind": "data", "t": round(time.time(), 2), "v": sig[0]}, keep=False)
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
                extra["Set-Cookie"] = f"ftrk={cfg['token']}; Path=/; SameSite=Strict"
            p = unquote(u.path)
            if p in ("/", "/index.html"):
                return self.file(os.path.join(VIEWER, "live.html"), extra)
            if p in ("/data.json", "/viewer/data.json"):
                return self.file(cfg["data"], extra)
            if p in ("/viewer", "/viewer/"):
                return self.file(os.path.join(VIEWER, "index.html"), extra)
            if p == "/events":
                return self.events()
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
    return data, media


def cmd_serve(a):
    data, media = resolve(a)
    old = _pointer()
    if old:
        sys.exit(f"A Workshop is already running on port {old['port']} (pid {old['pid']}). Stop it first.")
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    hub = Hub()
    cfg = {"data": data, "media": media, "token": secrets.token_urlsafe(9)}
    srv = None
    for port in range(a.port, a.port + 20):
        try:
            srv = ThreadingHTTPServer((host, port), make_handler(cfg, hub))
            break
        except OSError:
            continue
    if not srv:
        sys.exit(f"No free port between {a.port} and {a.port + 19}")
    srv.daemon_threads = True
    port = srv.server_address[1]
    with open(POINTER, "w", encoding="utf-8") as fh:
        json.dump({"port": port, "pid": os.getpid()}, fh)
    stop = threading.Event()
    threading.Thread(target=watch, args=(data, hub, stop), daemon=True).start()
    print(f"Workshop: http://127.0.0.1:{port}/   (viewer: http://127.0.0.1:{port}/viewer/)")
    print(f"watching {data}")
    if a.lan:
        ip = lan_ip()
        print(f"phone on the same Wi-Fi: http://{ip or '<this computer>'}:{port}/?k={cfg['token']}")
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


def cmd_progress(a):
    if not emit("progress", task=a.task, done=a.done, total=a.total, person=a.person, text=a.text):
        print("(no Workshop running: progress not shown)")


def cmd_note(a):
    ok = emit(a.kind, text=a.text, person=a.person)
    if not ok:
        print("(no Workshop running: note not shown)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("serve", aliases=["serveer", "start"], help="start the Workshop page")
    s.add_argument("--config", "--instellingen", help="settings file (family-tree.json / stamboom.json)")
    s.add_argument("--data", help="data.json (instead of --config)")
    s.add_argument("--port", "--poort", type=int, default=8790)
    s.add_argument("--lan", "--wifi", action="store_true", help="also listen on the local network (address with a key)")
    s.add_argument("--media", action="append", help="extra folder to serve viewer media from (repeatable)")
    s.set_defaults(func=cmd_serve)
    n = sp.add_parser("note", aliases=["notitie"], help="show one line in the Workshop")
    n.add_argument("text")
    n.add_argument("--person", "--persoon", help="GEDCOM id (I4 or @I4@) or name: the scanner points there")
    n.add_argument("--kind", "--soort", default="note",
                   choices=["note", "read", "found", "nothing", "ask", "notitie", "lees", "gevonden", "niets", "vraag"])
    n.set_defaults(func=cmd_note)
    g = sp.add_parser("progress", aliases=["voortgang"], help="a progress bar for a long script (send it every step)")
    g.add_argument("task", help="short name of the task, e.g. 'side branches'")
    g.add_argument("done", type=int)
    g.add_argument("total", type=int)
    g.add_argument("--person", "--persoon", help="who is being checked now (GEDCOM id or name): the scanner points there")
    g.add_argument("--text", "--tekst", help="one line about this step")
    g.set_defaults(func=cmd_progress)
    a = ap.parse_args()
    if getattr(a, "kind", None):
        a.kind = {"notitie": "note", "lees": "read", "gevonden": "found", "niets": "nothing", "vraag": "ask"}.get(a.kind, a.kind)
    a.func(a)


if __name__ == "__main__":
    main()
