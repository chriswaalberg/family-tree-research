#!/usr/bin/env python3
"""publish_cloudflare.py — puts the viewer online as a website on Cloudflare (Workers, static assets).

Uses the same settings file as make_viewer_data.py (family-tree.json / stamboom.json), with a "publish" part:

  "publish": {"cloudflare": "smith-family-tree",            the worker name -> https://<name>.<account>.workers.dev
              "media": ["zeitgeist/media", "stories/media"]} extra folders whose contents go into media/

What it does:
  1. builds data.json with make_viewer_data.py --config <settings file>
  2. puts index.html (with noindex), data.json, the media folder and the extra media folders in a temporary folder,
     with a _headers file (X-Robots-Tag: noindex), and checks that every media/... file in data.json is there
  3. asks "Put N people (M living) online?" and runs: npx --yes wrangler@4 deploy --name <name> --assets <folder>

Anyone with the link can see the site (search engines are asked not to index it). Living people are in it unless the
settings file says "hide_living": true. Claude always asks the user before running this without --dry-run.

Examples:
  python3 -I publish_cloudflare.py --config family-tree.json --dry-run       build and check only
  python3 -I publish_cloudflare.py --config family-tree.json                 asks before deploying
  python3 -I publish_cloudflare.py --config family-tree.json --yes           no question (the user already said yes)

Once beforehand: install Node.js and log in with `npx --yes wrangler@4 login` (a free Cloudflare account is enough).
No account details are stored by this script. Standard library only; Python 3.8+.
"""
import argparse, importlib.util, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(HERE, "..", "viewer", "index.html")
COMPAT_DATE = "2026-11-01"
MAX_FILE = 25 * 1024 * 1024  # Cloudflare Workers static assets: max 25 MiB per file
MAX_FILES = 20000
NOINDEX = '<meta name="robots" content="noindex, nofollow">'


def load_mvd():
    """make_viewer_data.py from this folder (python3 -I doesn't put this folder on sys.path)."""
    spec = importlib.util.spec_from_file_location("make_viewer_data", os.path.join(HERE, "make_viewer_data.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pick(d, *keys):
    for k in keys:
        if d.get(k) not in (None, "", []):
            return d[k]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", "--instellingen", dest="config",
                    help="settings file (default: family-tree.json or stamboom.json in this folder)")
    ap.add_argument("--name", "--naam", dest="name", help="worker name (default: publish.cloudflare in the settings file)")
    ap.add_argument("--yes", "--ja", dest="yes", action="store_true", help="don't ask before deploying (only after the user said yes)")
    ap.add_argument("--dry-run", "--proef", dest="dry", action="store_true", help="build and check the site, don't deploy")
    ap.add_argument("--site", "--map", dest="site", help="build the site in this folder and keep it (default: a temporary folder)")
    ap.add_argument("--no-build", "--niet-bouwen", dest="no_build", action="store_true", help="use the existing data.json")
    a = ap.parse_args()

    mvd = load_mvd()
    cfg = a.config or mvd.find_config()
    if not cfg:
        ap.error(f"give --config, or put {' or '.join(mvd.CONFIG_NAMES)} in this folder")
    opts, pub, base = mvd.load_config(cfg)
    pub = {str(k).lower().replace("-", "_"): v for k, v in pub.items()}
    name = a.name or pick(pub, "cloudflare", "worker", "name", "naam")
    if not name and not a.dry:
        sys.exit(f"{cfg}: no worker name. Add \"publish\": {{\"cloudflare\": \"<name>\"}} (or give --name).")
    if name and not re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?", name):
        sys.exit(f"Worker name {name!r}: use lower-case letters, digits and dashes only (max. 63)")
    extra = pick(pub, "media", "extra_media") or []
    extra = [extra] if isinstance(extra, str) else list(extra)
    extra = [os.path.join(base, os.path.expanduser(str(x))) for x in extra]
    for x in extra:
        if not os.path.isdir(x):
            sys.exit(f"{cfg}: media folder not found: {x}")

    # 1. data.json
    data = opts["uit"]
    if not a.no_build:
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "make_viewer_data.py"), "--config", cfg])
        if r.returncode:
            sys.exit("Building data.json failed; nothing was published.")
    if not os.path.isfile(data):
        sys.exit(f"No data.json at {data}")

    # 2. the site
    site = os.path.abspath(a.site) if a.site else tempfile.mkdtemp(prefix="family-tree-site-")
    try:
        if a.site:
            if os.path.exists(site) and os.listdir(site):
                if not os.path.isfile(os.path.join(site, "_headers")):
                    sys.exit(f"--site {site}: folder exists and isn't an earlier site; pick an empty folder")
                shutil.rmtree(site)
            os.makedirs(site, exist_ok=True)
        html = open(VIEWER, encoding="utf-8").read()
        if "<head>" not in html:
            sys.exit("viewer/index.html has no <head>")
        html = html.replace("<head>", "<head>\n" + NOINDEX, 1)
        with open(os.path.join(site, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(html)
        with open(os.path.join(site, "_headers"), "w", encoding="utf-8") as fh:
            fh.write("/*\n  X-Robots-Tag: noindex, nofollow\n")
        shutil.copyfile(data, os.path.join(site, "data.json"))
        media = os.path.join(site, "media")
        os.makedirs(media, exist_ok=True)
        for src in ([opts["media_map"]] if opts.get("media_map") and os.path.isdir(opts["media_map"]) else []) + extra:
            shutil.copytree(src, media, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".DS_Store", "Thumbs.db"))

        text = open(os.path.join(site, "data.json"), encoding="utf-8").read()
        missing = sorted(p for p in set(re.findall(r'"(media/[^"]+)"', text)) if not os.path.isfile(os.path.join(site, p)))
        if missing:
            sys.exit(f"{len(missing)} media file(s) in data.json are missing (add their folder to publish.media):\n  "
                     + "\n  ".join(missing[:20]) + ("\n  …" if len(missing) > 20 else ""))
        files = [os.path.join(d, f) for d, _, fs in os.walk(site) for f in fs]
        big = [os.path.relpath(f, site) for f in files if os.path.getsize(f) > MAX_FILE]
        if big:
            sys.exit("Over 25 MB, Cloudflare won't take these: " + ", ".join(big))
        if len(files) > MAX_FILES:
            sys.exit(f"{len(files)} files; Cloudflare takes at most {MAX_FILES}")
        d = json.loads(text)
        people = d.get("personen", [])
        living = sum(1 for p in people if p.get("levend"))
        size = sum(os.path.getsize(f) for f in files)
        print(f"Site: {site}: {len(files)} files, {size / 1e6:.1f} MB; {len(people)} people, {living} living"
              + (" (details hidden)" if living and not d.get("levenden_tonen") else ""))

        if a.dry:
            print("Dry run: nothing published." + ("" if a.site else " (temporary folder removed; use --site to keep it)"))
            return
        # 3. ask, then deploy
        if not a.yes:
            if not sys.stdin.isatty():
                sys.exit("Not published: ask the user first (the site is public for anyone with the link), then run again with --yes.")
            ans = input(f"Put {len(people)} people ({living} living) online as \"{name}\" (anyone with the link can look)? [y/N] ")
            if ans.strip().lower() not in ("y", "yes", "j", "ja"):
                sys.exit("Not published.")
        npx = shutil.which("npx")
        if not npx:
            sys.exit("npx not found: install Node.js (https://nodejs.org), then log in once with: npx --yes wrangler@4 login")
        r = subprocess.run([npx, "--yes", "wrangler@4", "deploy", "--name", name, "--assets", site,
                            "--compatibility-date", COMPAT_DATE])
        if r.returncode:
            sys.exit("wrangler deploy failed (not logged in? run: npx --yes wrangler@4 login)")
    finally:
        if not a.site:
            shutil.rmtree(site, ignore_errors=True)


if __name__ == "__main__":
    main()
