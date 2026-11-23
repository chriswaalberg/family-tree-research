#!/usr/bin/env python3
"""The Workshop's three states, as Claude sees them (hook, live.py status/note, /ping):

  none     no Workshop runs for this tree           → "NOT RUNNING"
  hidden   it runs, but nobody sees it               → "NO PAGE HAS IT OPEN" / "HIDDEN" + show_pane
  visible  a page reported that it is in view        → "in view"

Run from the repo root:  python3 -I tests/test_workshop_states.py
Starts a real `live.py serve --local` on a fake tree in a temp folder (its own TMPDIR, so no real Workshop is touched)
and plays a page with a raw event stream plus /seen reports, the way live.html does.
"""
import importlib.util, json, os, shutil, socket, subprocess, sys, tempfile, time, unittest, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUG = os.path.join(REPO, "plugins", "family-tree-research")
LIVE = os.path.join(PLUG, "skills", "family-tree", "scripts", "live.py")
HOOK = os.path.join(PLUG, "hooks", "tree_hint.py")


def load_live():
    spec = importlib.util.spec_from_file_location("ftr_live_test", LIVE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class States(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ftr-states-")
        cls.env = dict(os.environ, TMPDIR=os.path.join(cls.tmp, "t"), FTR_QUIET="")
        os.makedirs(cls.env["TMPDIR"])
        cls.tree = os.path.join(cls.tmp, "tree")
        os.makedirs(os.path.join(cls.tree, "data"))
        with open(os.path.join(cls.tree, "family-tree.json"), "w") as fh:
            json.dump({"output": "data/data.json"}, fh)
        with open(os.path.join(cls.tree, "data", "data.json"), "w") as fh:
            json.dump({"versie": 2, "personen": []}, fh)
        cls.port = free_port()
        cls.srv = None

    @classmethod
    def tearDownClass(cls):
        if cls.srv:
            cls.srv.terminate()
            cls.srv.wait(5)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---- helpers
    def run_py(self, *args, stdin=None):
        return subprocess.run([sys.executable, "-I", *args], cwd=self.tree, env=self.env, input=stdin,
                              capture_output=True, text=True, timeout=20)

    def hook(self, mode):
        return self.run_py(HOOK, mode, stdin=json.dumps({"cwd": self.tree})).stdout

    def status(self):
        r = self.run_py(LIVE, "status", "--json")
        return json.loads(r.stdout), r.returncode

    def ping(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/ping", timeout=2) as r:
            return json.load(r)

    def seen(self, **body):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/seen", data=json.dumps(body).encode(), method="POST")
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.load(r)

    def open_page(self, vid):
        """A page's event stream, like EventSource("events?id=..."): stays open until closed."""
        s = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        s.sendall(f"GET /events?id={vid} HTTP/1.1\r\nHost: x\r\nAccept: text/event-stream\r\n\r\n".encode())
        buf = b""
        while b"hello" not in buf:
            buf += s.recv(65536)
        return s

    # ---- the states, in order
    def test_all(self):
        # 1. none
        st, code = self.status()
        self.assertEqual((st["state"], code), ("none", 1))
        none = self.hook("prompt")
        self.assertIn("NOT RUNNING", none)
        self.assertIn("NOT RUNNING", self.hook("start"))
        self.assertNotIn(" open on port", self.hook("prompt"))
        out = self.run_py(LIVE, "note", "hello").stdout
        self.assertIn("not shown", out)
        self.assertIn("NOT RUNNING", out)

        # 2a. running, no page
        type(self).srv = subprocess.Popen([sys.executable, "-I", LIVE, "serve", "--config", "family-tree.json",
                                           "--port", str(self.port), "--exact", "--local"],
                                          cwd=self.tree, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                self.ping()
                break
            except OSError:
                time.sleep(0.05)
        p = self.ping()
        self.assertEqual((p["viewers"], p["visible"]), (0, False))
        st, code = self.status()
        self.assertEqual((st["state"], code), ("hidden", 1))
        h = self.hook("prompt")
        self.assertIn("NO PAGE HAS IT OPEN", h)
        self.assertIn("mcp__ccd_view__show_pane with pane 'preview'", h)
        self.assertIn('"visible": true', h)
        print("\n  none    →", none.strip())
        print("  hidden0 →", h.strip())

        # 2b. a page has it open, but hidden (the desktop pane not shown)
        page = self.open_page("p1")
        r = self.seen(id="p1", visible=False)
        self.assertEqual((r["viewers"], r["visible"]), (1, False))
        h = self.hook("prompt")
        self.assertIn("HIDDEN", h)
        self.assertIn("mcp__ccd_view__show_pane with pane 'preview' now", h)
        out = self.run_py(LIVE, "note", "hello").stdout
        self.assertIn("note sent, but", out)
        self.assertIn("HIDDEN", out)
        print("  hidden  →", h.strip())

        # 3. in view
        self.seen(id="p1", visible=True)
        st, code = self.status()
        self.assertEqual((st["state"], code, st["viewers"], st["visible_here"]), ("visible", 0, 1, True))
        h = self.hook("prompt")
        self.assertIn("is in view on port", h)
        self.assertNotIn("show_pane", h)
        self.assertEqual(self.run_py(LIVE, "note", "hello").stdout, "")  # silent when the user can see it
        print("  visible →", h.strip())

        # the page closes: gone at once (pagehide beacon), and the stream breaking keeps it gone
        self.seen(id="p1", gone=True)
        self.assertEqual(self.ping()["viewers"], 0)
        page.close()
        self.assertIn("NO PAGE HAS IT OPEN", self.hook("prompt"))

        # launch spells out the next steps, show_pane and the visible check included
        out = self.run_py(LIVE, "launch", "--config", "family-tree.json", "--file", os.path.join(self.tmp, "launch.json")).stdout
        for s in ('preview_start with name "workshop"', "mcp__ccd_view__show_pane with pane 'preview'", '"visible": true'):
            self.assertIn(s, out)


class Timing(unittest.TestCase):
    """Hidden must never turn into closed (slow background timers), and a stale 'visible' must not stay visible."""

    def setUp(self):
        self.live = load_live()
        self.hub = self.live.Hub()

    def test_hidden_page_stays_open_without_beats(self):
        self.hub.viewer_join("a", True)
        self.hub.viewer_report("a", True, visible=False, now=0)
        st = self.hub.view_state(now=3600)  # an hour without a report: its stream is still open
        self.assertEqual((st["viewers"], st["visible"]), (1, False))

    def test_visible_needs_fresh_report(self):
        self.hub.viewer_join("a", True)
        self.hub.viewer_report("a", True, visible=True, now=0)
        self.assertTrue(self.hub.view_state(now=self.live.BEAT_FRESH - 1)["visible"])
        self.assertFalse(self.hub.view_state(now=self.live.BEAT_FRESH + 1)["visible"])

    def test_closed_page_goes(self):
        self.hub.viewer_join("a", True)
        self.hub.viewer_report("a", True, visible=True, now=0)
        self.hub.viewer_leave("a")  # the stream broke
        self.assertEqual(self.hub.view_state(now=self.live.VIEWER_TTL - 1)["viewers"], 1)
        self.assertEqual(self.hub.view_state(now=self.live.VIEWER_TTL + 1)["viewers"], 0)

    def test_phone_only(self):
        self.hub.viewer_join("phone", False)
        self.hub.viewer_report("phone", False, visible=True, now=0)
        st = dict(self.hub.view_state(now=1), state="visible", port=1)
        self.assertEqual((st["visible"], st["visible_here"]), (True, False))
        self.assertIn("phone only", self.live.state_text(st))

    def test_texts(self):
        t = self.live.state_text
        self.assertNotIn("open", t({"state": "none"}).replace("Open it", ""))
        self.assertIn("older live.py", t({"state": "unknown", "port": 1}))
        for s in ({"state": "hidden", "port": 1, "viewers": 0}, {"state": "hidden", "port": 1, "viewers": 2}):
            self.assertIn("mcp__ccd_view__show_pane with pane 'preview'", t(s))


if __name__ == "__main__":
    unittest.main(verbosity=2)
