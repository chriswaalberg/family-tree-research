#!/usr/bin/env python3
"""make_demo.py — builds a larger, fully fictional demo family for the README and Reddit screenshots.

It takes the 7-person example family (Femke de Vries and her parents and grandparents) and gives the
grandparents invented ancestors, up to about 8 generations back, with realistic gaps. Nothing here is
a real person. The plugin's own examples/ stay small on purpose (the smoke test relies on them).

  python3 -I docs/demo/make_demo.py            # writes docs/demo/demo.ged
  S=plugins/family-tree-research/skills/family-tree
  python3 -I $S/scripts/make_viewer_data.py docs/demo/demo.ged /tmp/demo.json --start @I1@:Femke
  python3 -I $S/scripts/standalone_viewer.py $S/viewer/index.html /tmp/demo.json /tmp/demo.html

Standard library only. Fixed random seed, so the output is the same every time.
"""
import os, random

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "..", "..", "plugins", "family-tree-research", "skills", "family-tree", "examples", "example.ged")
OUT = os.path.join(HERE, "demo.ged")
MAX_GEN = 8          # Femke = generation 0
rnd = random.Random(1955)

NAMES = {
    "NL": {"M": "Jan Pieter Cornelis Hendrik Willem Klaas Dirk Gerrit Jacob Adriaan Johannes Arie Teunis Barend Simon Gijsbert".split(),
           "F": "Maria Johanna Neeltje Grietje Aaltje Trijntje Cornelia Hendrika Geertruida Jannetje Dirkje Elisabeth Antje Jacoba".split(),
           "S": "Visser Mulder Bos Hendriks Dekker Koster Brouwer Kramer Post Kuiper Vermeulen Blom Zwart Veenstra Schipper Boon Hoekstra Kroon".split()
                + ["de Boer", "de Wit", "van der Meer"]},
    "BE": {"M": "Jan Petrus Josephus Franciscus Henricus Joannes Ludovicus Carolus Guilielmus Adrianus".split(),
           "F": "Maria Anna Joanna Elisabeth Catharina Theresia Rosalia Barbara Isabella Francisca".split(),
           "S": "Maes Jacobs Mertens Willems Claes Goossens Wouters Dubois Hermans Aerts Verlinden Michiels Lambrechts Vermeiren Pauwels Hendrickx".split()
                + ["De Smet", "Van den Broeck"]},
    "SE": {"M": "Anders Per Nils Lars Olof Johan Erik Sven Karl Gustaf".split(),
           "F": "Anna Maria Kristina Brita Kajsa Ingrid Elin Karin Greta Sara".split(),
           "S": "Andersson Nilsson Larsson Olsson Persson Johansson Eriksson Svensson Karlsson Gustafsson".split()},
    "DE": {"M": "Johann Heinrich Friedrich Wilhelm Hermann".split(),
           "F": "Anna Margaretha Catharina Elisabeth Gesina".split(),
           "S": "Meyer Schulte Brinkmann Wessels Lammers".split()},
}
PLACES = {
    "NL": ["Den Helder, Noord-Holland, Nederland", "Alkmaar, Noord-Holland, Nederland", "Schagen, Noord-Holland, Nederland",
           "Hoorn, Noord-Holland, Nederland", "Enkhuizen, Noord-Holland, Nederland", "Medemblik, Noord-Holland, Nederland",
           "Den Burg, Texel, Noord-Holland, Nederland", "Purmerend, Noord-Holland, Nederland"],
    "BE": ["Leuven, Vlaams-Brabant, België", "Mechelen, Antwerpen, België", "Lier, Antwerpen, België", "Aarschot, Vlaams-Brabant, België",
           "Diest, Vlaams-Brabant, België", "Herentals, Antwerpen, België", "Tienen, Vlaams-Brabant, België"],
    "SE": ["Göteborg, Västra Götaland, Sverige", "Kungälv, Västra Götaland, Sverige", "Alingsås, Västra Götaland, Sverige",
           "Uddevalla, Västra Götaland, Sverige", "Borås, Västra Götaland, Sverige"],
    "DE": ["Lingen, Niedersachsen, Deutschland", "Bentheim, Niedersachsen, Deutschland"],
}
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()

people, fams = [], []   # people: dict(id, given, surname, sex, by, dy, bplac, dplac, famc, fams[])

def date(y):
    r = rnd.random()
    if r < 0.15: return f"ABT {y}"
    if r < 0.30: return str(y)
    return f"{rnd.randint(1, 28)} {rnd.choice(MONTHS)} {y}"

def new_person(sex, surname, by, region):
    pid = f"@I{len(people) + 100}@"
    given = rnd.choice(NAMES[region][sex])
    if rnd.random() < 0.35: given += " " + rnd.choice(NAMES[region][sex])
    dy = by + rnd.randint(42, 88)
    p = {"id": pid, "given": given, "surname": surname, "sex": sex, "by": by, "dy": dy if dy < 2015 else None,
         "bplac": rnd.choice(PLACES[region]), "dplac": None, "famc": None, "fams": []}
    if p["dy"]: p["dplac"] = p["bplac"] if rnd.random() < 0.7 else rnd.choice(PLACES[region])
    people.append(p)
    return p

def p_known(gen):      # chance that a parent is known, lower further back
    return {1: 1, 2: 1, 3: 0.97, 4: 0.92, 5: 0.82, 6: 0.7, 7: 0.55, 8: 0.4}.get(gen, 0)

shared = {}            # one couple that shows up in two branches (pedigree collapse)

def add_parents(child, gen, region):
    """Give `child` (at generation gen-1) invented parents at generation `gen`."""
    if gen > MAX_GEN: return
    if gen == 6 and region == "NL" and "fam" in shared and rnd.random() < 0.5 and child["surname"] != shared["child_surname"]:
        child["famc"] = shared["fam"]["id"]; shared["fam"]["chil"].append(child["id"]); return   # second cousins married
    reg_f = "DE" if region == "NL" and gen >= 5 and rnd.random() < 0.08 else region
    father = new_person("M", child["surname"] if region != "SE" else rnd.choice(NAMES["SE"]["S"]), child["by"] - rnd.randint(24, 38), reg_f) if rnd.random() < p_known(gen) else None
    mother = new_person("F", rnd.choice(NAMES[region]["S"]), child["by"] - rnd.randint(20, 34), region) if rnd.random() < p_known(gen) else None
    if region == "SE" and father:  # patronymics: the child is named after the father
        child_sur = father["given"].split()[0] + ("son" if child["sex"] == "M" else "dotter")
        if gen >= 3: child["surname"] = child_sur
    if not father and not mother: return
    fam = {"id": f"@F{len(fams) + 100}@", "husb": father["id"] if father else None, "wife": mother["id"] if mother else None, "chil": [child["id"]]}
    fams.append(fam); child["famc"] = fam["id"]
    for p in (father, mother):
        if p: p["fams"].append(fam["id"])
    if gen == 6 and region == "NL" and "fam" not in shared:
        shared.update(fam=fam, child_surname=child["surname"])
    for p, reg in ((father, reg_f), (mother, region)):
        if p: add_parents(p, gen + 1, reg)

def write(base_lines):
    out = [l for l in base_lines if l.strip() != "0 TRLR"]
    # the 4 grandparents get a FAMC line pointing to their new parents
    gp = {g["id"]: g for g in GRANDPARENTS}
    final, cur = [], None
    for l in out:
        if l.startswith("0 @I") and l.endswith(" INDI"): cur = l.split()[1]
        final.append(l)
        if cur in gp and l.startswith("1 SEX") and gp[cur].get("famc"):
            final.append(f"1 FAMC {gp[cur]['famc']}")
    for p in people:
        final += [f"0 {p['id']} INDI", f"1 NAME {p['given']} /{p['surname']}/", f"1 SEX {p['sex']}",
                  "1 BIRT", f"2 DATE {date(p['by'])}", f"2 PLAC {p['bplac']}"]
        if p["dy"]: final += ["1 DEAT", f"2 DATE {date(p['dy'])}", f"2 PLAC {p['dplac']}"]
        if p["famc"]: final.append(f"1 FAMC {p['famc']}")
        final += [f"1 FAMS {f}" for f in p["fams"]]
    for f in fams:
        final.append(f"0 {f['id']} FAM")
        if f["husb"]: final.append(f"1 HUSB {f['husb']}")
        if f["wife"]: final.append(f"1 WIFE {f['wife']}")
        final += [f"1 CHIL {c}" for c in f["chil"]]
    final.append("0 TRLR")
    open(OUT, "w", encoding="utf-8").write("\n".join(final).replace("1 SOUR Example", "1 SOUR Fictional demo family (docs/demo/make_demo.py)") + "\n")

base = open(EXAMPLE, encoding="utf-8").read().splitlines()
GRANDPARENTS = [  # the example's grandparents (generation 2), with their region
    {"id": "@I4@", "sex": "M", "surname": "de Vries", "by": 1948, "region": "NL"},
    {"id": "@I5@", "sex": "F", "surname": "Lindqvist", "by": 1925, "region": "SE"},
    {"id": "@I6@", "sex": "M", "surname": "Peeters", "by": 1950, "region": "BE"},
    {"id": "@I7@", "sex": "F", "surname": "Janssens", "by": 1953, "region": "BE"},
]
for g in GRANDPARENTS:
    g_child = dict(g, famc=None)
    add_parents(g_child, 3, g["region"])
    g["famc"] = g_child["famc"]
write(base)
print(f"{OUT}: {7 + len(people)} people, {3 + len(fams)} families")
