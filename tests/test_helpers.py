#!/usr/bin/env python3
"""Helpers (subagents) keep their own name in the Workshop, also when Agent calls don't start in order;
the progress bars they leave open turn grey and go (live.py TASK_*, progress --stop, SubagentStop, a new session).

The hooks see: PreToolUse Agent (description + brief), SubagentStart (only an agent id: a guess from the oldest
recent call), and PreToolUse Bash inside the helper (its transcript, whose first line is its brief, is there now:
the name is checked by the brief's hash). Plays the night-round case: an Agent call that never starts a helper
(denied) used to shift every later name by one.

Run from the repo root:  python3 -I tests/test_helpers.py
Starts a real `live.py serve --local` on a fake tree in a temp folder (its own TMPDIR, no real Workshop touched).
"""
import json, os, shutil, socket, subprocess, sys, tempfile, time, unittest, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUG = os.path.join(REPO, "plugins", "family-tree-research")
LIVE = os.path.join(PLUG, "skills", "family-tree", "scripts", "live.py")
HOOK = os.path.join(PLUG, "hooks", "tree_hint.py")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Names(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ftr-names-")
        cls.env = dict(os.environ, TMPDIR=os.path.join(cls.tmp, "t"), FTR_QUIET="")
        cls.env.pop("FTR_WHO", None)
        cls.env.pop("FTR_TREE", None)
        os.makedirs(cls.env["TMPDIR"])
        cls.tree = os.path.join(cls.tmp, "tree")
        os.makedirs(os.path.join(cls.tree, "data"))
        with open(os.path.join(cls.tree, "family-tree.json"), "w") as fh:
            json.dump({"output": "data/data.json"}, fh)
        with open(os.path.join(cls.tree, "data", "data.json"), "w") as fh:
            json.dump({"versie": 2, "personen": []}, fh)
        cls.port = free_port()
        cls.srv = subprocess.Popen([sys.executable, "-I", LIVE, "serve", "--config", "family-tree.json",
                                    "--port", str(cls.port), "--exact", "--local"],
                                   cwd=cls.tree, env=cls.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/ping", timeout=2).read()
                break
            except OSError:
                time.sleep(0.05)
        cls.sess = os.path.join(cls.tmp, "sess")
        os.makedirs(os.path.join(cls.sess, "subagents"))

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(5)
        subprocess.run([sys.executable, "-I", LIVE, "stop"], cwd=cls.tree, env=cls.env, capture_output=True, timeout=20)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def hook(self, mode, **info):
        info = dict(cwd=self.tree, session_id=self.id().rsplit(".", 1)[-1], transcript_path=self.sess + ".jsonl", **info)
        r = subprocess.run([sys.executable, "-I", HOOK, mode], cwd=self.tree, env=self.env, input=json.dumps(info),
                           capture_output=True, text=True, timeout=20)
        try:
            return json.loads(r.stdout) if r.stdout.strip() else None
        except ValueError:
            return r.stdout  # start/prompt: a plain line for Claude

    def call(self, desc, brief):
        self.hook("agent", tool_name="Agent", tool_input={"description": desc, "prompt": brief})

    def start(self, aid, brief):
        out = self.hook("helper", agent_id=aid, agent_type="general-purpose")
        with open(os.path.join(self.sess, "subagents", f"agent-{aid}.jsonl"), "w") as fh:  # written after the hook
            fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": brief}}) + "\n")
        return out

    def who(self, aid):
        out = self.hook("bash", agent_id=aid, tool_name="Bash",
                        tool_input={"command": f"python3 -I {LIVE} note hi"})
        cmd = out["hookSpecificOutput"]["updatedInput"]["command"]
        return cmd.split("FTR_WHO=", 1)[1].split(" FTR_TREE=")[0].strip("'")

    def test_denied_call_shifts_nobody(self):
        self.call("Denied reader", "read book X")  # PreToolUse ran, the call was denied: no helper
        self.call("Reader Katwijk", "read the Katwijk baptisms")
        brief = self.start("a1", "read the Katwijk baptisms")
        self.assertNotIn("FTR_WHO=", brief["hookSpecificOutput"]["additionalContext"])  # no fixed name in the brief
        self.call("Reader Anholt", "read the Anholt baptisms")
        self.start("a2", "read the Anholt baptisms")
        self.assertEqual(self.who("a1"), "Reader Katwijk")
        self.assertEqual(self.who("a2"), "Reader Anholt")
        self.assertEqual(self.who("a1"), "Reader Katwijk")  # checked once, stays

    def test_out_of_order(self):
        for d in ("Alpha", "Beta", "Gamma"):
            self.call(d, f"brief {d}")
        self.start("g", "brief Gamma")
        self.start("a", "brief Alpha")
        self.start("b", "brief Beta")
        self.assertEqual([self.who(x) for x in ("b", "g", "a")], ["Beta", "Gamma", "Alpha"])

    def test_own_name_kept(self):
        self.call("ignored", "export FTR_WHO='Lezer 3' and read")
        self.assertIsNone(self.start("x", "export FTR_WHO='Lezer 3' and read"))  # its brief names it: no extra brief
        self.assertEqual(self.who("x"), "Lezer 3")

    def test_same_description_twice(self):
        self.call("Reader", "brief one")
        self.call("Reader", "brief two")
        self.start("r1", "brief one")
        self.start("r2", "brief two")
        self.assertEqual(sorted([self.who("r1"), self.who("r2")]), ["Reader", "Reader 2"])

    # ---- progress bars a helper leaves open (wish 52)
    def tasks(self):
        """The bars a page opened now would see (the event stream's hello)."""
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        sock.sendall(b"GET /events?id=t HTTP/1.1\r\nHost: x\r\nAccept: text/event-stream\r\n\r\n")
        buf = b""
        while b"\n\n" not in buf.split(b"data: ", 1)[-1]:
            buf += sock.recv(65536)
        sock.close()
        hello = json.loads(buf.split(b"data: ", 1)[1].split(b"\n\n", 1)[0])
        return {t["task"]: t for t in hello["tasks"]}

    def live(self, *args, who=None):
        env = dict(self.env, **({"FTR_WHO": who} if who else {}))
        return subprocess.run([sys.executable, "-I", LIVE, *args], cwd=self.tree, env=env,
                              capture_output=True, text=True, timeout=20)

    def test_bars_stop(self):
        self.live("progress", "Katwijk 1647", "2", "5", who="Reader Katwijk")
        self.live("progress", "Anholt 1695", "53", "80", who="Reader Anholt")
        self.live("progress", "Own task", "1", "4")
        self.assertFalse(any(t.get("stopped") for t in self.tasks().values()))
        self.live("progress", "Own task", "--stop")
        self.assertEqual(self.tasks()["Own task"]["stopped"], "stop")
        self.call("Reader Katwijk", "read Katwijk")
        self.start("k1", "read Katwijk")
        self.hook("helper_end", agent_id="k1")  # SubagentStop: only this helper's bar
        t = self.tasks()
        self.assertEqual((t["Katwijk 1647"]["stopped"], t["Katwijk 1647"]["done"]), ("stop", 2))
        self.assertNotIn("stopped", t["Anholt 1695"])
        self.hook("start")  # a new session: grey bars leave, open ones stay
        self.assertEqual(list(self.tasks()), ["Anholt 1695"])


class Sweep(unittest.TestCase):
    """The times, on the server's own Hub (no waiting): grey after TASK_QUIET, gone after TASK_QUIET_GONE."""
    def test_sweep(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ftr_live_sweep", LIVE)
        live = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(live)
        hub, t0 = live.Hub(), 1000.0
        hub.send({"kind": "progress", "t": t0, "task": "A", "done": 53, "total": 80})
        hub.send({"kind": "progress", "t": t0, "task": "B", "done": 1, "total": 4})
        hub.send({"kind": "stop", "t": t0, "task": "B"})
        idle = hub.last
        hub.sweep_tasks(now=t0 + live.TASK_QUIET - 1)
        self.assertNotIn("stopped", hub.tasks["A"])
        hub.sweep_tasks(now=t0 + live.TASK_QUIET + 1)
        self.assertEqual((hub.tasks["A"]["stopped"], hub.tasks["A"]["done"]), ("quiet", 53))
        self.assertEqual(hub.last, idle)  # the sweep is no sign of use: IDLE_STOP keeps counting
        hub.sweep_tasks(now=t0 + live.TASK_QUIET_GONE + 1)
        self.assertEqual(hub.tasks, {})  # A gone after its time; B (stopped on purpose) long gone
        log = [(e.get("task"), e.get("stopped")) for e in hub.history if e.get("kind") == "progress"]
        self.assertEqual(log, [("A", None), ("B", None), ("B", "stop"), ("A", "quiet")])  # one line each, no "gone"


if __name__ == "__main__":
    unittest.main(verbosity=2)
