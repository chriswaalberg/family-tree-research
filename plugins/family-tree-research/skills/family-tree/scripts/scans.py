#!/usr/bin/env python3
"""scans.py — read local scans (a parish book, downloaded register pages) at true size, and show it in the Workshop.

  strips <image> [--person I4] [--task "<task>" --done 3 --total 41]
         cut a scan into pieces you can read: a two-page spread into its left and right page, each page into
         strips of about STRIP_H pixels (with some overlap, so no line is lost between two strips), at full
         resolution. Prints one line per piece: the file and where it sits in the scan (x0,y0,x1,y1).
  crop <image> <x,y | x0,y0,x1,y1> [--size 1400x1000]
         one piece at true size: a box, or a box of --size around a spot (coordinates of the full scan, as
         `strips` prints them).

Every call tells the Workshop (live.py) what is being read, under the helper's FTR_WHO name, with --person as the
one the scan is about. With --task/--done/--total it also moves that task's progress bar. Nothing is sent when no
Workshop runs for this tree.

Examples:
  FTR_WHO=reader-1 python3 -I scans.py strips scans/karlshamn-1791-p12.jpg --person I87 --task "Karlshamn baptisms 1791" --done 12 --total 41
  python3 -I scans.py crop scans/karlshamn-1791-p12.jpg 820,2210 --size 1200x700

Pillow is needed (pip install Pillow). Dutch aliases: stroken, uitsnede; --persoon, --taak, --klaar, --totaal, --uit, --boom.
"""
import argparse, os, sys, tempfile

STRIP_H = 1600       # strip height in scan pixels: about one screen at true size
OVERLAP = 150        # pixels shared by two neighbouring strips
SPREAD = 1.15        # width / height above which a scan counts as a two-page spread
CROP_SIZE = (1400, 1000)
QUALITY = 88

_LIVE = []


def live(kind, **fields):
    """Tell a running Workshop what happens. Does nothing when none runs for this tree."""
    try:
        if not _LIVE:
            import importlib.util
            spec = importlib.util.spec_from_file_location("ftr_live", os.path.join(os.path.dirname(os.path.abspath(__file__)), "live.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _LIVE.append(mod.emit)
        _LIVE[0](kind, **fields)
    except Exception:
        pass


def open_image(path):
    try:
        from PIL import Image
    except ImportError:
        sys.exit("scans.py needs Pillow: pip install Pillow")
    Image.MAX_IMAGE_PIXELS = None  # archive scans are big on purpose
    im = Image.open(path)
    im.load()
    return im.convert("RGB") if im.mode not in ("RGB", "L") else im


def out_dir(a):
    d = a.out or os.path.join(tempfile.gettempdir(), "family-tree-scans", os.path.splitext(os.path.basename(a.image))[0])
    os.makedirs(d, exist_ok=True)
    return d


def save(im, box, path):
    im.crop(box).save(path, quality=QUALITY)
    print(f"{path}\t{box[0]},{box[1]},{box[2]},{box[3]}")


def pages(w, h, split):
    if split == "yes" or (split == "auto" and w > SPREAD * h):
        return [("L", 0, w // 2), ("R", w // 2, w)]
    return [("", 0, w)]


def tell(a, what):
    if a.tree:
        os.environ["FTR_TREE"] = a.tree
    live("read", source=os.path.basename(a.image), q=what, person=a.person)
    if a.task and a.total:
        live("progress", task=a.task, done=a.done or 0, total=a.total, person=a.person)


def cmd_strips(a):
    im = open_image(a.image)
    w, h = im.size
    d, stem = out_dir(a), os.path.splitext(os.path.basename(a.image))[0]
    step, n = max(200, a.height - OVERLAP), 0
    for side, x0, x1 in pages(w, h, a.split):
        y = 0
        while True:
            y1 = min(h, y + a.height)
            save(im, (x0, y, x1, y1), os.path.join(d, f"{stem}{'-' + side if side else ''}-y{y:05d}.jpg"))
            n += 1
            if y1 >= h:
                break
            y += step
    halves = "2 pages" if a.split == "yes" or (a.split == "auto" and w > SPREAD * h) else "1 page"
    print(f"({w}×{h} px, {halves}, {n} pieces in {d})", file=sys.stderr)
    tell(a, f"{halves} · {n} strips")


def cmd_crop(a):
    im = open_image(a.image)
    w, h = im.size
    try:
        v = [int(float(x)) for x in a.box.split(",")]
    except ValueError:
        sys.exit("give x,y or x0,y0,x1,y1")
    if len(v) == 2:
        sw, sh = (int(x) for x in (a.size or "%dx%d" % CROP_SIZE).lower().split("x"))
        v = [v[0] - sw // 2, v[1] - sh // 2, v[0] + sw // 2, v[1] + sh // 2]
    if len(v) != 4:
        sys.exit("give x,y or x0,y0,x1,y1")
    box = (max(0, v[0]), max(0, v[1]), min(w, v[2]), min(h, v[3]))
    if box[2] <= box[0] or box[3] <= box[1]:
        sys.exit(f"that box lies outside the scan ({w}×{h})")
    stem = os.path.splitext(os.path.basename(a.image))[0]
    save(im, box, a.to or os.path.join(out_dir(a), f"{stem}-crop-{box[0]}-{box[1]}.jpg"))
    tell(a, f"{box[0]},{box[1]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("image")
        p.add_argument("--person", "--persoon", help="GEDCOM id or name of the one this scan is about")
        p.add_argument("--task", "--taak", help="the task's name, for its progress bar in the Workshop")
        p.add_argument("--done", "--klaar", type=int)
        p.add_argument("--total", "--totaal", type=int)
        p.add_argument("--out", "--uit", help="folder for the pieces (default: the system temp folder)")
        p.add_argument("--tree", "--boom", help="the tree's folder, when you run this from somewhere else")

    s = sp.add_parser("strips", aliases=["stroken"], help="page halves and strips at true size")
    common(s)
    s.add_argument("--height", "--hoogte", type=int, default=STRIP_H)
    s.add_argument("--split", choices=["auto", "yes", "no"], default="auto", help="cut into a left and right page")
    s.set_defaults(fn=cmd_strips)
    c = sp.add_parser("crop", aliases=["uitsnede"], help="one piece at true size")
    common(c)
    c.add_argument("box", help="x,y (a spot) or x0,y0,x1,y1 (a box), in scan pixels")
    c.add_argument("--size", "--maat", help=f"box size around a spot, default {CROP_SIZE[0]}x{CROP_SIZE[1]}")
    c.add_argument("--to", "--naar", help="the output file")
    c.set_defaults(fn=cmd_crop)
    a = ap.parse_args()
    if not os.path.isfile(a.image):
        sys.exit(f"not found: {a.image}")
    a.fn(a)


if __name__ == "__main__":
    main()
