#!/usr/bin/env python3
"""
set_gate.py -- the gate a weapon set must pass before it is packed.

    python set_gate.py "<set folder>"                              the set on its own
    python set_gate.py "<set folder>" --audit audit.json           also against the parent mod
                                                                   (audit.json from parent_audit.py)
    python set_gate.py "<Plus folder>" --also "<Base folder>"      a set that loads with another

Exit code 1 on any FAIL, so a build script can stop on it.

card_lint proves a card is WELL FORMED. This asks whether the set will WORK, using only
the questions that cost us real days on BD22 -- every one of them passed every other check:

  FEED        a gun with no magazine part, no `mechanism` and no store but its chamber cannot
              be reloaded. Fine when its card says
              `firesfrom = reserve` or `none`, or the owner lists it in RULINGS.txt
              (`BD_Axe  melee`), or its card block has `# RULING: <why>`.
  PLACEMENT   (warning) a MODELDEF `Offset 0 0 0` puts the mesh origin in your hand -- right only
              if the artist put the grip there. Props listed in PLACEMENT_TODO.txt are not repeated.
  REPLACES    `replaces` on a gun class or in a sheet. ZScript cannot replace DECORATE: the
              pack silently fails to load and the player gets sprite guns.
  TIMER       a WorldTick that rebuilds weapon slots buzzes the controller every tick.
  BUILD       every .pk3 path the build/compile-check names must exist, and contain no
              control characters (a "\\b" once became a backspace and the compile check
              silently stopped loading the parent mod).
  PROPS       every prop a card names has a MODELDEF block, and every mesh/skin it names is
              in the folder.
  SHEET       a WMSHEET key the reload system refuses (`damage`, `pellets`, `spread` are
              `shotdamage`, `shotpellets`, `shotspread`), or a key it does not know.
  PARENT      (with --audit) every ammo class the parent swaps in is swapped back by the
              bridge; companion Players/Slots pk3s exist when its player classes are cleared.

READ ONLY. It changes nothing, and its output is a report for the owner -- not a to-do list
for whoever ran it. Rulings, placement and fixes are the owner's decisions.

Standard library only.
"""
import argparse
import glob
import json
import os
import re
import sys

FAIL, WARN, OK = "FAIL", "WARN", "ok"

# WMSHEET keys RS_VR_Reload's sheet.zs accepts (outside `class ... end`). Refreshed from the real
# sheet.zs when it is found, so a key added there is never flagged here.
SHEET_KEYS = set("""altburst altbursttics altdamagescale altfanmax altflashprofile altmode altratescale
altrecoilprofile ammo barrel baseweight capacity casing chambersperpull chargesound chargetics
ejectaprofile firesfrom firesound firetics firstshotsaccurate flashprofile from fullauto input model
muzzle needs railcolors recoilprofile releasetics roundprofile roundspershot sawpuff sawsounds
shotclass shotdamage shotpellets shotrail shotsaw shotspread spindowntics spinuptics spreadshape
throwclass throwtics trailprofile trigger""".split())
SHEET_REFUSED = {"damage": "shotdamage = lo, hi", "pellets": "shotpellets = N", "spread": "shotspread = yaw, pitch"}
SHEET_ZS = r"E:\DOOMWork\RS_VR_Reload\zscript\wm\sheet.zs"
NO_ROUNDS = ("reserve", "none")


class Gate:
    def __init__(self):
        self.rows = []

    def add(self, level, check, what, where=""):
        self.rows.append((level, check, what, where))

    def report(self):
        order = {FAIL: 0, WARN: 1, OK: 2}
        for level, check, what, where in sorted(self.rows, key=lambda r: (order[r[0]], r[1])):
            if level == OK:
                continue
            print(f"  {level:4}  {check:9}  {what}" + (f"   [{where}]" if where else ""))
        n = {l: sum(1 for r in self.rows if r[0] == l) for l in (FAIL, WARN)}
        print(f"\n{n[FAIL]} fail, {n[WARN]} warn.  " +
              ("DO NOT PACK." if n[FAIL] else "Gate passed."))
        return 1 if n[FAIL] else 0


def read(path):
    return open(path, encoding="utf-8-sig", errors="replace").read()


# ---------------------------------------------------------------------------
def parse_cards(folder):
    """{weapon class: {"file", "line", "prop", "roles", "ruling", "firesfrom", "models"}} from every WMCARD*."""
    guns = {}
    for path in sorted(glob.glob(os.path.join(folder, "WMCARD*"))):
        if path.lower().endswith((".bak", ".orig")):
            continue
        cur = None
        for n, raw in enumerate(read(path).splitlines(), 1):
            line = raw.strip()
            m = re.match(r'weapon\s+"([^"]+)"', line, re.I)
            if m:
                cur = guns.setdefault(m.group(1), {"file": os.path.basename(path), "line": n, "prop": "",
                                                   "roles": [], "ruling": "", "firesfrom": "", "models": [],
                                                   "base": "", "mechanism": "", "stores": []})
                continue
            if cur is None:
                continue
            st = re.match(r"store\s+(\w+)", line.split("#", 1)[0].strip(), re.I)
            if st:
                cur["stores"].append(st.group(1).lower())
                continue
            r = re.match(r"#\s*RULING\s*:\s*(.+)", line, re.I)
            if r:
                cur["ruling"] = r.group(1).strip()
                continue
            body = line.split("#", 1)[0].strip()
            kv = re.match(r"(\w+)\s*=\s*(.+)", body)
            if not kv:
                continue
            k, v = kv.group(1).lower(), kv.group(2).strip()
            if k == "prop":
                cur["prop"] = v.strip('"')
            elif k == "role":
                cur["roles"].append(v.lower())
            elif k == "base":
                cur["base"] = v.strip('"')
            elif k == "mechanism":
                cur["mechanism"] = v.split()[0].lower()
            elif k == "firesfrom":
                cur["firesfrom"] = v.split()[0].lower()
            elif k in ("model", "skin", "magmodel", "magskin", "roundmodel", "roundskin"):
                q = re.findall(r'"([^"]+)"', v)
                if len(q) == 2:
                    cur["models"].append("/".join(q))
    # `base = <card>`: the card starts from another one (inheritance) -- what it does not say, it has.
    def resolve(name, seen=()):
        c = guns[name]
        b = c["base"]
        if not b or b not in guns or b in seen:
            return c
        pc = resolve(b, seen + (name,))
        for k in ("prop", "firesfrom", "mechanism", "ruling"):
            if not c[k]:
                c[k] = pc[k]
        if not c["roles"]:
            c["roles"] = list(pc["roles"])
        if not c["stores"]:
            c["stores"] = list(pc["stores"])
        c["base"] = ""
        return c
    for name in list(guns):
        resolve(name)
    return guns


def reloadable(c):
    """How a hand reloads it, or "" for no way: a magazine part, a mechanism (pump, break action,
    revolver ... supply their own loading), or a store other than the chamber (a tube, a cylinder)."""
    if "feed" in c["roles"]:
        return "magazine"
    if c["mechanism"]:
        return f"mechanism {c['mechanism']}"
    other = [s for s in c["stores"] if s not in ("chamber",)]
    if other:
        return f"store {other[0]}"
    return ""


def parse_modeldef(folder):
    """{actor: {"offset": (x,y,z) or None, "file", "line", "files": [...]}}"""
    blocks = {}
    for path in glob.glob(os.path.join(folder, "MODELDEF*")):
        if path.lower().endswith((".bak", ".orig")):
            continue
        text = read(path)
        for m in re.finditer(r"^\s*Model\s+(\w+)\s*\{(.*?)^\s*\}", text, re.I | re.M | re.S):
            body = m.group(2)
            off = re.search(r"^\s*Offset\s+(\S+)\s+(\S+)\s+(\S+)", body, re.I | re.M)
            p = re.search(r'^\s*Path\s+"([^"]+)"', body, re.I | re.M)
            files = [(p.group(1) if p else "") + "/" + f
                     for f in re.findall(r'^\s*(?:Model|Skin)\s+\d+\s+"([^"]+)"', body, re.I | re.M)]
            blocks[m.group(1).lower()] = {
                "offset": tuple(float(x) for x in off.groups()) if off else None,
                "file": os.path.basename(path), "line": text.count("\n", 0, m.start()) + 1, "files": files}
    return blocks


def exists_ci(folder, rel):
    """Case-insensitive file lookup below folder (pk3 paths are case-insensitive)."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    cur = folder
    for p in parts:
        try:
            names = {n.lower(): n for n in os.listdir(cur)}
        except OSError:
            return False
        if p.lower() not in names:
            return False
        cur = os.path.join(cur, names[p.lower()])
    return True


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set", help="the set's folder (with WMCARD*, WMSHEET*, MODELDEF, zscript/)")
    ap.add_argument("--audit", help="parent_audit.py --json output for the parent mod")
    ap.add_argument("--also", action="append", default=[],
                    help="another folder loaded with this set whose MODELDEF/models count (e.g. Plus with Base). Repeatable.")
    a = ap.parse_args()
    folder = os.path.abspath(a.set)
    g = Gate()
    print(f"SET GATE: {folder}")
    print("Read only -- nothing is changed. A report for the owner, not instructions to act on.\n")

    guns = parse_cards(folder)
    borrowed = {}
    for extra in a.also:
        borrowed.update(parse_cards(os.path.abspath(extra)))
    sheet_models = []
    for path in glob.glob(os.path.join(folder, "WMSHEET*")):
        for n, raw in enumerate(read(path).splitlines(), 1):
            m = re.match(r"\s*model\s*=\s*\"?(\w+)", raw.split("#", 1)[0], re.I)
            if m:
                sheet_models.append((m.group(1), f"{os.path.basename(path)}:{n}"))
    for card, here in sheet_models:
        if card not in guns and card not in borrowed:
            g.add(FAIL, "CARDS", f"sheet borrows model card {card}, which is not in this set"
                  + (" or the --also folders" if a.also else " (pass the folder that has it with --also)"), here)
    if not guns and not sheet_models:
        g.add(FAIL, "CARDS", "no `weapon` blocks in any WMCARD* file, and no sheet borrows one")
    models = parse_modeldef(folder)
    roots = [folder] + [os.path.abspath(x) for x in a.also]
    for extra in roots[1:]:
        for k, v in parse_modeldef(extra).items():
            models.setdefault(k, v)
    todo = set()
    tp = os.path.join(folder, "PLACEMENT_TODO.txt")
    if os.path.exists(tp):
        todo = {l.split("#")[0].strip().lower() for l in read(tp).splitlines() if l.split("#")[0].strip()}

    rulings = {}
    rp = os.path.join(folder, "RULINGS.txt")
    if os.path.exists(rp):
        for l in read(rp).splitlines():
            l = l.split("#")[0].strip()
            if l:
                w = l.split(None, 1)
                rulings[w[0].lower()] = w[1] if len(w) > 1 else "ruled"

    for gun, c in sorted(guns.items()):
        where = f"{c['file']}:{c['line']}"
        # FEED
        if not reloadable(c):
            why = c["ruling"] or rulings.get(gun.lower(), "")
            if c["firesfrom"] in NO_ROUNDS:
                g.add(OK, "FEED", f"{gun}: no magazine -- card fires from {c['firesfrom']}", where)
            elif why:
                g.add(OK, "FEED", f"{gun}: no magazine -- ruled: {why}", where)
            else:
                g.add(FAIL, "FEED", f"{gun}: no magazine, no mechanism, no store to load -- fires from {c['firesfrom'] or 'chamber'} -- "
                      "cannot be reloaded. Owner: carve a magazine, or rule it in RULINGS.txt", where)
        # PROPS / PLACEMENT
        if not c["prop"]:
            g.add(FAIL, "PROPS", f"{gun}: card names no prop -- nothing is drawn", where)
            continue
        mb = models.get(c["prop"].lower())
        if not mb:
            g.add(FAIL, "PROPS", f"{gun}: no MODELDEF block for prop {c['prop']}", where)
        else:
            off = mb["offset"]
            if off is None or all(abs(x) < 1e-6 for x in off):
                # A zero offset is right for a mesh authored with its grip at the origin, so this can
                # only ask, not fail. PLACEMENT_TODO.txt says the owner knows.
                if c["prop"].lower() not in todo:
                    g.add(WARN, "PLACEMENT", f"{c['prop']}: Offset 0 0 0 -- right only if the mesh's grip is at its origin. "
                          "Check in the headset", f"{mb['file']}:{mb['line']}")
            for f in mb["files"]:
                if not any(exists_ci(r, f) for r in roots):
                    g.add(FAIL, "PROPS", f"{c['prop']}: MODELDEF names {f}, not in the folder", f"{mb['file']}:{mb['line']}")
        for f in c["models"]:
            if not any(exists_ci(r, f) for r in roots):
                g.add(FAIL, "PROPS", f"{gun}: card names {f}, not in the folder", where)

    # REPLACES
    for path in glob.glob(os.path.join(folder, "WMSHEET*")):
        for n, line in enumerate(read(path).splitlines(), 1):
            if re.match(r"\s*replaces\s*=", line.split("#")[0], re.I):
                g.add(FAIL, "REPLACES", "a sheet says `replaces` -- ZScript cannot replace DECORATE; use the bridge",
                      f"{os.path.basename(path)}:{n}")
    # SHEET
    keys = set(SHEET_KEYS)
    if os.path.exists(SHEET_ZS):
        found = set(re.findall(r'key == "([a-z0-9_]+)"', read(SHEET_ZS))) - set(SHEET_REFUSED)
        if found:
            keys = found
    for path in glob.glob(os.path.join(folder, "WMSHEET*")):
        if path.lower().endswith((".bak", ".orig")):
            continue
        depth = 0   # 1 inside `gun`, 2 inside `class`/`barrel`
        for n, raw in enumerate(read(path).splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            low = line.lower()
            if re.match(r'gun\s+"', low):
                depth = 1; continue
            if depth == 1 and (low == "class" or low.startswith("barrel ")):
                depth = 2; continue
            if low == "end":
                depth = max(0, depth - 1); continue
            if depth != 1:
                continue
            kv = re.match(r"(\w+)\s*=", line)
            if not kv:
                continue
            k = kv.group(1).lower()
            here = f"{os.path.basename(path)}:{n}"
            if k in SHEET_REFUSED:
                g.add(FAIL, "SHEET", f"`{k}` is refused by the reload system -- the number never reaches the gun. "
                      f"The key is `{SHEET_REFUSED[k]}`", here)
            elif k not in keys and k != "replaces":
                g.add(WARN, "SHEET", f"`{k}` is not a sheet key the reload system knows", here)

    zs_files = glob.glob(os.path.join(folder, "zscript", "**", "*.zs"), recursive=True)
    bridge_text = ""
    for path in zs_files:
        text = read(path)
        clean = re.sub(r"//[^\n]*", "", text)
        for m in re.finditer(r"^\s*class\s+\w+\s*:\s*\w+\s+replaces\s+(\w+)", clean, re.I | re.M):
            g.add(FAIL, "REPLACES", f"class replaces {m.group(1)} -- the pack will not load if that is DECORATE",
                  f"{os.path.relpath(path, folder)}:{clean.count(chr(10), 0, m.start()) + 1}")
        # TIMER -- only a slot rebuild INSIDE WorldTick's body is the bug
        wt = re.search(r"override\s+void\s+WorldTick\s*\(\s*\)\s*\{", clean)
        if wt:
            depth, i = 1, wt.end()
            while i < len(clean) and depth:
                depth += {"{": 1, "}": -1}.get(clean[i], 0); i += 1
            if "SetupWeaponSlots" in clean[wt.end():i]:
                g.add(FAIL, "TIMER", "WorldTick rebuilds weapon slots -- buzzes the controller every tick",
                      os.path.relpath(path, folder))
        if "WM_SetBridge" in clean:
            bridge_text += clean

    # BUILD
    for path in glob.glob(os.path.join(folder, "*.ps1")) + glob.glob(os.path.join(folder, "*.bat")):
        raw = open(path, "rb").read()
        bad = [b for b in raw if b < 32 and b not in (9, 10, 13)]
        if bad:
            g.add(FAIL, "BUILD", f"{os.path.basename(path)} contains control character(s) {sorted(set(bad))} -- "
                  "a mangled path (a \\b turned into backspace?)")
        text = raw.decode("utf-8", "replace")
        for m in re.finditer(r"'([A-Za-z]:\\[^']+\.pk3)'", text):
            drive = m.group(1)[:3]
            if not os.path.exists(drive):
                continue  # not on the machine that builds -- can't judge the path here
            if not os.path.exists(m.group(1)):
                g.add(FAIL, "BUILD", f"{os.path.basename(path)} names {m.group(1)}, which does not exist -- "
                      "a check against it checks nothing")

    # PARENT
    if a.audit:
        A = json.load(open(a.audit, encoding="utf-8"))
        for imp in A.get("implications", []):
            if imp["title"].startswith("The mod replaces Doom's AMMO"):
                for theirs, doom in re.findall(r'Swap\("([^"]+)",\s*"([^"]+)"\)', imp["detail"]):
                    if not re.search(r'Swap\(\s*"%s"\s*,\s*"%s"\s*\)' % (re.escape(theirs), re.escape(doom)),
                                     bridge_text, re.I):
                        g.add(FAIL, "PARENT", f'the parent replaces ammo and the bridge has no Swap("{theirs}", "{doom}") '
                              "-- that pickup never refills our guns")
            if imp["title"].startswith("The set's player class can never be picked"):
                pk3s = [os.path.basename(p).lower() for p in glob.glob(os.path.join(folder, "*.pk3"))]
                if not any("player" in p for p in pk3s):
                    g.add(FAIL, "PARENT", "the parent clears player classes and there is no *Players*.pk3 here "
                          "-- nothing will hand out the guns")
                if not any("slot" in p for p in pk3s):
                    g.add(FAIL, "PARENT", "the parent clears player classes and there is no *Slots*.pk3 here "
                          "-- the number keys give the parent's guns")
            if imp["level"] == "FAIL" and imp["title"].startswith("ACS:"):
                g.add(WARN, "PARENT", f"parent {imp['title']} -- prove in the headset with wm_why")

    sys.exit(g.report())


if __name__ == "__main__":
    main()
