#!/usr/bin/env python3
"""make_stages.py — three versions of the fictional demo tree for the Workshop demo video.

  stage0.json  the demo family without Anna Lindqvist's Swedish grandparents (a gap in the fan)
  stage1.json  the research "found" them: four parent links come back, 37 ancestors fly in
  stage2.json  checks done: a few links become certain (gold), one is rejected (it cracks)

  python3 -I docs/demo/video/make_stages.py <out-dir>

Uses docs/demo/demo.ged (fictional, made by docs/demo/make_demo.py). Standard library only.
"""
import copy, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
S = os.path.join(ROOT, "plugins", "family-tree-research", "skills", "family-tree")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    full = os.path.join(out, "full.json")
    subprocess.run([sys.executable, "-I", os.path.join(S, "scripts", "make_viewer_data.py"),
                    os.path.join(ROOT, "docs", "demo", "demo.ged"), full,
                    "--csv", os.path.join(S, "examples", "example-relations.csv"),
                    "--start", "@I1@:Femke", "--updated", "none"], check=True, stdout=subprocess.DEVNULL)
    d = json.load(open(full, encoding="utf-8"))
    P = d["personen"]
    at = {p["id"]: i for i, p in enumerate(P)}
    per, ingrid = P[at["I132"]], P[at["I133"]]       # Anna Lindqvist's father and mother

    s1 = copy.deepcopy(d)
    q = s1["personen"]
    reg = "Riksarkivet: Kungälv parish register"
    q[at["I132"]]["c"] = {"f": ["waarschijnlijk", reg + " 1838", "Per's baptism names Nils Anders Larsson as father."],
                          "m": ["waarschijnlijk", reg + " 1838", "The same baptism names Anna Greta Larsdotter."]}
    q[at["I133"]]["c"] = {"f": ["mogelijk", "Alingsås household survey 1845", "A Sven Larsson with a daughter Ingrid, age fits."],
                          "m": ["waarschijnlijk", "Alingsås household survey 1845", "Kajsa Karldotter is listed as Sven's wife."]}

    s0 = copy.deepcopy(s1)
    for p in (s0["personen"][at["I132"]], s0["personen"][at["I133"]]):
        p.pop("f", None); p.pop("m", None); p.pop("c", None)

    s2 = copy.deepcopy(s1)
    q = s2["personen"]
    q[at["I2"]]["c"]["m"] = ["zeker", "Göteborg birth register 1984", "Thomas's birth record names Anna Lindqvist as his mother."]
    q[at["I5"]]["c"] = {"f": ["zeker", "Göteborg parish register 1958", "Anna's baptism names Per Nilsson as her father."],
                        "m": ["zeker", "Göteborg parish register 1958", "The same baptism names Ingrid Svendotter."]}
    q[at["I132"]]["c"]["f"][0] = "zeker"
    q[at["I132"]]["c"]["m"][0] = "zeker"
    q[at["I133"]].pop("f", None)                    # Sven Larsson turns out to be someone else
    q[at["I133"]]["c"].pop("f", None)

    for name, data in (("stage0", s0), ("stage1", s1), ("stage2", s2)):
        with open(os.path.join(out, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    print(f"stages written to {out} (Per: {per['n']}, Ingrid: {ingrid['n']})")


if __name__ == "__main__":
    main()
