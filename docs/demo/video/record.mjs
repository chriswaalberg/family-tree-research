// record.mjs — records the Workshop demo video (README): a made-up desktop chat app (desktop.html) on the left,
// the real Workshop (live.py serve + viewer/live.html) on the right, fed with real events and three versions of
// the fictional demo tree (make_stages.py). Only fictional people.
//
//   python3 -I docs/demo/video/make_stages.py /tmp/ftr-video
//   node docs/demo/video/record.mjs /tmp/ftr-video            # needs `npm i playwright` + ffmpeg
//
// Writes workshop-demo.mp4 and workshop-demo.gif into the folder. SPEED: the recording is sped up this much.
import { spawn, execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// PW=/path/to/node_modules/playwright/index.mjs when playwright is installed elsewhere (not in this repo)
const { chromium } = await import(process.env.PW ? pathToFileURL(process.env.PW).href : "playwright");
const HERE = path.dirname(fileURLToPath(import.meta.url));
const LIVE = path.join(HERE, "..", "..", "..", "plugins", "family-tree-research", "skills", "family-tree", "scripts", "live.py");
const DIR = path.resolve(process.argv[2] || "/tmp/ftr-video");
const PORT = 8799, W = 2000, H = 1293, DPR = 1, OUT_W = 1920, SPEED = 1.8, GIF_W = 960;
const TREE = path.join(DIR, "tree"), DATA = path.join(TREE, "data.json");
const wait = ms => new Promise(r => setTimeout(r, ms));
const stage = n => fs.copyFileSync(path.join(DIR, `stage${n}.json`), DATA);

async function ev(e) {               // what live.py emit() sends
  await fetch(`http://127.0.0.1:${PORT}/event`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ t: Date.now() / 1000, ...e }) }).catch(() => {});
}

fs.rmSync(TREE, { recursive: true, force: true });
fs.mkdirSync(TREE, { recursive: true });
stage(0);
const srv = spawn("python3", ["-I", LIVE, "serve", "--data", DATA, "--local", "--exact", "--port", String(PORT)], { stdio: "inherit" });
process.on("exit", () => srv.kill());
for (let i = 0; i < 50; i++) { try { if ((await fetch(`http://127.0.0.1:${PORT}/ping`)).ok) break; } catch {} await wait(100); }

// frames come from Chrome's own screencast (CDP), so Playwright needs no browser or ffmpeg download:
// CHANNEL=chrome uses the installed Google Chrome (headless, fresh profile)
let browser, page, cdp;
const RAW = path.join(DIR, "frames"), frames = [];
fs.rmSync(RAW, { recursive: true, force: true });
fs.mkdirSync(RAW, { recursive: true });
const D = (fn, ...a) => page.evaluate(([fn, a]) => window.demo[fn](...a), [fn, a]);
const s = ms => wait(ms * SPEED);      // director time in milliseconds of the final video

try {
  browser = await chromium.launch(process.env.CHANNEL ? { channel: process.env.CHANNEL } : {});
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: DPR });
  page = await ctx.newPage();
  page.on("console", m => { if (m.type() === "error") console.log("console:", m.text()); });
  await page.goto(pathToFileURL(path.join(HERE, "desktop.html")).href);
  cdp = await ctx.newCDPSession(page);
  cdp.on("Page.screencastFrame", f => {
    const file = path.join(RAW, `f${String(frames.length).padStart(5, "0")}.jpg`);
    fs.writeFileSync(file, Buffer.from(f.data, "base64"));
    frames.push({ file, t: f.metadata.timestamp });
    cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: W * DPR, maxHeight: H * DPR, everyNthFrame: 1 });
  await s(300);
  await page.evaluate(() => window.demo.type("Keep researching Anna Lindqvist's Swedish side. Send helpers, and open the Workshop so I can watch.", 13 * 1.8));
  await s(200);
  await D("send");
  await s(700);
  await D("say", "On it. I'll open the Workshop first, then send three helpers into the Swedish archives at the same time.");
  await s(300);
  const url = `http://127.0.0.1:${PORT}/`;
  await D("open", url, "Workshop · Femke de Vries");
  await page.waitForFunction(() => document.querySelector("#ws").classList.contains("on"));
  await s(400);
  // the chat card is a still screenshot of the preview, like the app's own
  const box = await page.locator("#ws").boundingBox();
  const shot = await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: Math.round(box.width * 208 / 556) } });
  await D("ran", "Ran 2 commands, started preview, opened browser", "");
  await D("card", "data:image/png;base64," + shot.toString("base64"));
  for (const fr of page.frames().filter(f => f.url().startsWith(url))) {   // the Workshop pane
    await fr.waitForFunction(() => typeof CFG === "object").catch(() => {});
    await fr.evaluate(() => { CFG.ONE_BY_ONE = 4; CFG.CERT_ONE_BY_ONE = 3; }).catch(() => {});   // fewer one-by-one arrivals for a 15 s video
  }
  await ev({ kind: "focus", who: "Claude", person: "I5", text: "parents" });
  await s(400);
  await D("todos", ["Open the Workshop", "Kungälv parish registers (agent)", "Alingsås household surveys (agent)", "Göteborg newspapers (agent)", "Rebuild the tree and check the links"]);
  await D("step", 0, "done");
  await D("step", 1, "now"); await D("step", 2, "now"); await D("step", 3, "now");
  await ev({ kind: "read", who: "parish", person: "I132", text: "Kungälv baptisms 1836–1840" });
  await s(250);
  await ev({ kind: "read", who: "survey", person: "I133", text: "Alingsås household survey 1845" });
  await s(250);
  await ev({ kind: "read", who: "papers", person: "I5", text: "Göteborgs-Posten 1958, birth notices" });
  for (let i = 1; i <= 6; i++) {
    await ev({ kind: "progress", who: "parish", task: "Kungälv baptisms", done: i, total: 6, person: i % 2 ? "I132" : "I5" });
    if (i === 3) await ev({ kind: "found", who: "papers", person: "I5", text: "Birth notice: Anna, daughter of Per Nilsson" });
    if (i === 5) await ev({ kind: "found", who: "survey", person: "I133", text: "Ingrid, daughter of Sven Larsson, age 7" });
    await s(240);
  }
  await ev({ kind: "found", who: "parish", person: "I132", text: "Baptism of Per: parents Nils Anders Larsson and Anna Greta" });
  await D("step", 1, "done");
  await s(250);

  stage(1);                                    // 4 parent links come back: 37 ancestors fly in
  await D("step", 4, "now");
  await s(3400);
  await ev({ kind: "read", who: "papers", person: "I2", text: "Göteborg birth register 1984" });
  await D("step", 3, "done");
  await s(1400);

  stage(2);                                    // links become certain (gold), Sven Larsson cracks
  await D("step", 2, "done");
  await s(2500);
  await D("step", 4, "done");
  await D("finish", "<b>37 ancestors</b> added on the Swedish side, back to the 1700s. Five links are now certain. One was wrong: Sven Larsson was someone else, so he moved out of the fan.");
  await s(1800);
} finally {
  if (cdp) await cdp.send("Page.stopScreencast").catch(() => {});
  if (browser) await browser.close();
  srv.kill();
}
if (frames.length > 10) {
  // frames arrive only when something changes: each one lasts until the next (concat demuxer durations)
  const list = path.join(DIR, "frames.txt");
  fs.writeFileSync(list, frames.map((f, i) => `file '${f.file}'\nduration ${((frames[i + 1] || { t: f.t + 0.5 }).t - f.t).toFixed(4)}`).join("\n")
    + `\nfile '${frames[frames.length - 1].file}'\n`);
  const mp4 = path.join(DIR, "workshop-demo.mp4"), gif = path.join(DIR, "workshop-demo.gif");
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list, "-vf", `setpts=PTS/${SPEED},fps=30,scale=${OUT_W}:-2:flags=lanczos`, "-an",
    "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4]);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", mp4, "-vf",
    `fps=12,scale=${GIF_W}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle`, gif]);
  console.log("wrote", mp4, "and", gif);
}
