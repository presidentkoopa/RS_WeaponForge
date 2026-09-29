#!/usr/bin/env python3
"""
parent_audit.py -- STEP 0 of a new weapon set. Run it on the mod you are building on
BEFORE you touch a gun.

    python parent_audit.py "<mod.pk3 or mod folder>"            report to the screen
    python parent_audit.py "<mod>" --out AUDIT.md --json audit.json

WHY THIS EXISTS. Brutal Doom v22 cost days because three facts about the PARENT MOD were
found one at a time, in the headset, after the set was built:

  * it REPLACES Doom's ammo (Clip -> Clip2 ...), so our guns' reserve was always zero;
  * its KEYCONF opens with `clearplayerclasses`, so our player class could never be picked;
  * its ACS switches, takes and freezes the player's weapon for its own features.

All three are sitting in the mod's text files on day one. This reads them and says what
the set will have to do about each, before any card is written.

Reads DECORATE (+ #includes, any *.dec), ZScript (*.zs/*.zc/*.txt under zscript), KEYCONF,
MAPINFO/ZMAPINFO/GAMEINFO, and ACS SOURCE (*.acs). Compiled ACS with no source is
reported as unauditable, never silently skipped.

Standard library only. Python 3.8+.
"""
import argparse
import json
import os
import re
import sys
import zipfile
from collections import defaultdict

# ---------------------------------------------------------------------------
# What Doom owns, by role. A parent mod replacing any of these changes what a set gets.
DOOM_AMMO = {
    "clip": "Clip", "clipbox": "ClipBox", "shell": "Shell", "shellbox": "ShellBox",
    "rocketammo": "RocketAmmo", "rocketbox": "RocketBox", "cell": "Cell",
    "cellpack": "CellPack", "backpack": "Backpack",
}
DOOM_WEAPONS = {
    "fist": "Fist", "chainsaw": "Chainsaw", "pistol": "Pistol", "shotgun": "Shotgun",
    "supershotgun": "SuperShotgun", "chaingun": "Chaingun", "rocketlauncher": "RocketLauncher",
    "plasmarifle": "PlasmaRifle", "bfg9000": "BFG9000",
}
DOOM_PLAYER = {"doomplayer": "DoomPlayer"}
# The ammo each Doom pickup counts as, so a replacement can be mapped back by role.
AMMO_BASE = {"clipbox": "clip", "shellbox": "shell", "rocketbox": "rocketammo", "cellpack": "cell"}

ACS_HAZARDS = [
    (re.compile(r"\bSetWeapon\s*\(", re.I), "SetWeapon",
     "switches the held weapon -- takes the player's hand off our gun"),
    (re.compile(r"PROP_TOTALLYFROZEN", re.I), "PROP_TOTALLYFROZEN",
     "freezes the player completely -- no firing"),
    (re.compile(r"PROP_FROZEN", re.I), "PROP_FROZEN",
     "freezes the player -- check whether firing is blocked"),
    (re.compile(r"PROP_INSTANTWEAPONSWITCH", re.I), "PROP_INSTANTWEAPONSWITCH",
     "forces instant weapon switches"),
    (re.compile(r"\bTakeInventory\s*\(\s*(weapon|wpn|currWpn|GetWeapon)", re.I), "TakeInventory(current weapon)",
     "removes the weapon in hand"),
]
BUTTON_RE = re.compile(r"\bBT_[A-Z0-9_]+\b")

TEXT_EXT = {".txt", ".dec", ".zs", ".zc", ".acs", ".acc", ".lmp", ""}


# ---------------------------------------------------------------------------
class Source:
    """A pk3/zip or a folder, read as {lowercase path: (display path, text)}."""

    def __init__(self, path):
        self.path = path
        self.files = {}
        self.compiled_acs = []
        if os.path.isdir(path):
            for root, _, names in os.walk(path):
                for n in names:
                    full = os.path.join(root, n)
                    rel = os.path.relpath(full, path).replace("\\", "/")
                    self._add(rel, lambda f=full: open(f, "rb").read())
        elif zipfile.is_zipfile(path):
            z = zipfile.ZipFile(path)
            for info in z.infolist():
                if info.is_dir():
                    continue
                self._add(info.filename, lambda i=info: z.read(i))
        else:
            sys.exit(f"not a folder or a pk3/zip: {path}")

    SKIP_DIRS = ("sprites/", "sounds/", "music/", "textures/", "graphics/", "patches/",
                 "flats/", "models/", "voxels/", "hires/", "brightmaps/", "maps/", "filter/")

    def _add(self, rel, reader):
        low = rel.lower()
        if low.startswith(self.SKIP_DIRS):
            return
        base = os.path.basename(low)
        ext = os.path.splitext(base)[1]
        if ext == ".o" and ("acs" in low):
            self.compiled_acs.append(rel)
            return
        if ext not in TEXT_EXT:
            return
        try:
            raw = reader()
        except Exception:
            return
        if len(raw) > 8_000_000 or b"\x00" in raw[:4096]:
            return
        self.files[low] = (rel, raw.decode("utf-8", "replace"))

    def named(self, *stems):
        """Files whose base name (without extension) is one of stems, any folder depth."""
        out = []
        for low, (rel, text) in self.files.items():
            stem = os.path.splitext(os.path.basename(low))[0]
            if stem in stems:
                out.append((rel, text))
        return out

    def by_ext(self, *exts):
        return [(rel, t) for low, (rel, t) in self.files.items() if os.path.splitext(low)[1] in exts]


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def lineno(text, pos):
    return text.count("\n", 0, pos) + 1


# ---------------------------------------------------------------------------
DEC_ACTOR = re.compile(
    r"^\s*actor\s+([\w.]+)\s*(?::\s*([\w.]+))?\s*(?:replaces\s+([\w.]+))?\s*(\d+)?\s*(?:native)?\s*\{",
    re.I | re.M)
ZS_CLASS = re.compile(
    r"^\s*class\s+([\w.]+)\s*(?::\s*([\w.]+))?\s*(?:replaces\s+([\w.]+))?", re.I | re.M)


def audit(src):
    R = {"mod": src.path, "classes": {}, "replaces": [], "keyconf": [], "mapinfo": [],
         "slots": [], "startitems": defaultdict(list), "acs_hazards": [], "acs_buttons": defaultdict(set),
         "handlers": [], "zs_replacement_hooks": [], "compiled_acs_without_source": []}

    # --- actors and classes -------------------------------------------------
    code_files = [(r, t) for r, t in src.files.values()
                  if os.path.basename(r.lower()).startswith("decorate")
                  or r.lower().endswith((".dec", ".zs", ".zc"))
                  or (r.lower().startswith("zscript") and r.lower().endswith(".txt"))
                  or r.lower().startswith("actors/")]
    for rel, text in code_files:
        clean = strip_comments(text)
        is_zs = rel.lower().endswith((".zs", ".zc")) or rel.lower().startswith("zscript")
        pat = ZS_CLASS if is_zs else DEC_ACTOR
        for m in pat.finditer(clean):
            name, parent, repl = m.group(1), m.group(2), m.group(3)
            key = name.lower()
            R["classes"].setdefault(key, {"name": name, "parent": (parent or "").lower(),
                                          "file": rel, "line": lineno(clean, m.start()), "body": ""})
            if repl:
                R["replaces"].append({"class": name, "replaces": repl, "file": rel,
                                      "line": lineno(clean, m.start()), "zscript": is_zs})
        # bodies, for Weapon.AmmoType / Player.StartItem
        for m in pat.finditer(clean):
            start = clean.find("{", m.end() - 1)
            if start < 0:
                continue
            depth, i = 0, start
            while i < len(clean):
                c = clean[i]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            R["classes"][m.group(1).lower()]["body"] = clean[start:i][:20000]
        if is_zs:
            for m in re.finditer(r"override\s+void\s+(CheckReplacement|WorldThingSpawned|PlayerSpawned|PlayerEntered)\b", clean):
                R["zs_replacement_hooks"].append({"hook": m.group(1), "file": rel, "line": lineno(clean, m.start())})

    def chain(key):
        seen = []
        while key and key in R["classes"] and key not in seen:
            seen.append(key)
            key = R["classes"][key]["parent"]
        if key and key not in seen:
            seen.append(key)
        return seen

    def is_a(key, base):
        return base in chain(key)

    # weapons and their ammo
    weapons = []
    for key, c in R["classes"].items():
        if key in ("weapon",) or not is_a(key, "weapon"):
            continue
        ammo = re.findall(r"weapon\.ammotype1?\s*,?\s*\"?([\w.]+)\"?", c["body"], re.I)
        ammo2 = re.findall(r"weapon\.ammotype2\s*,?\s*\"?([\w.]+)\"?", c["body"], re.I)
        weapons.append({"class": c["name"], "file": c["file"], "line": c["line"],
                        "ammo": ammo[0] if ammo else "", "ammo2": ammo2[0] if ammo2 else ""})
    R["weapons"] = sorted(weapons, key=lambda w: w["class"].lower())

    # player classes and their start items
    for key, c in R["classes"].items():
        if key != "playerpawn" and is_a(key, "playerpawn"):
            for m in re.finditer(r"player\.startitem\s+\"?([\w.]+)\"?\s*(?:,\s*(\d+))?", c["body"], re.I):
                R["startitems"][c["name"]].append((m.group(1), int(m.group(2) or 1)))
    R["player_classes_defined"] = sorted(c["name"] for k, c in R["classes"].items()
                                         if k != "playerpawn" and is_a(k, "playerpawn"))

    # --- KEYCONF ------------------------------------------------------------
    for rel, text in src.named("keyconf"):
        for n, line in enumerate(strip_comments(text).splitlines(), 1):
            s = line.strip()
            low = s.lower()
            if low.startswith(("clearplayerclasses", "addplayerclass")):
                R["keyconf"].append({"file": rel, "line": n, "text": s})
            if low.startswith(("weaponsection", "setslot", "addslotdefault", "clearslots")):
                R["slots"].append({"file": rel, "line": n, "text": s})

    # --- MAPINFO / GAMEINFO -------------------------------------------------
    for rel, text in src.named("mapinfo", "zmapinfo", "gameinfo"):
        clean = strip_comments(text)
        for m in re.finditer(r"^\s*(playerclasses|addplayerclasses|addeventhandlers|eventhandlers)\s*=\s*([^\n]+)",
                             clean, re.I | re.M):
            entry = {"file": rel, "line": lineno(clean, m.start()), "key": m.group(1), "value": m.group(2).strip()}
            if "eventhandler" in m.group(1).lower():
                R["handlers"].append(entry)
            else:
                R["mapinfo"].append(entry)

    # --- ACS ----------------------------------------------------------------
    acs_src = src.by_ext(".acs", ".acc")
    R["acs_archived"] = []
    for rel, text in acs_src:
        if "archive" in rel.lower() or "/old" in rel.lower() or "/unused" in rel.lower():
            R["acs_archived"].append(rel)   # an archive folder is not what the mod compiles
            continue
        clean = strip_comments(text)
        lines = clean.splitlines()
        for n, line in enumerate(lines, 1):
            for rx, label, why in ACS_HAZARDS:
                if rx.search(line):
                    R["acs_hazards"].append({"file": rel, "line": n, "hazard": label, "why": why,
                                             "text": line.strip()[:120]})
        for m in re.finditer(r"script\s+(\"[^\"]+\"|\d+)\s*(\([^)]*\))?\s*ENTER", clean, re.I):
            # the body of an ENTER script: which buttons does it read?
            start = clean.find("{", m.end())
            depth, i = 0, start
            while 0 <= i < len(clean):
                if clean[i] == "{":
                    depth += 1
                elif clean[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            body = clean[start:i] if start >= 0 else ""
            for b in BUTTON_RE.findall(body):
                R["acs_buttons"][b].add(f"{rel} script {m.group(1)}")
    acs_stems = {os.path.splitext(os.path.basename(r.lower()))[0] for r, _ in acs_src}
    for o in src.compiled_acs:
        if os.path.splitext(os.path.basename(o.lower()))[0] not in acs_stems:
            R["compiled_acs_without_source"].append(o)

    R["startitems"] = {k: v for k, v in R["startitems"].items()}
    R["acs_buttons"] = {k: sorted(v) for k, v in R["acs_buttons"].items()}
    return R


# ---------------------------------------------------------------------------
def implications(R):
    """The to-do list for the set: what each finding obliges it to do."""
    todo = []
    repl = {r["replaces"].lower(): r for r in R["replaces"]}

    ammo_hits = [(DOOM_AMMO[k], repl[k]["class"]) for k in DOOM_AMMO if k in repl]
    if ammo_hits:
        # Each of the mod's ammo classes goes back to the Doom class its NEAREST replaced
        # ancestor stands for: ClipBox2 (replaces ClipBox, child of Clip2) -> ClipBox, not Clip.
        stands_for = {theirs.lower(): doom for doom, theirs in ammo_hits}
        pairs = []
        for k, c in R["classes"].items():
            for anc in _chain(R, k):
                if anc in stands_for:
                    pairs.append((c["name"], stands_for[anc]))
                    break
        pairs.sort(key=lambda p: (p[1], p[0].lower()))
        lines = "\n".join(f'      Swap("{m}", "{doom}");' for m, doom in pairs)
        todo.append(("FAIL", "The mod replaces Doom's AMMO",
                     "Our guns draw on Doom's ammo. With this mod loaded, pickups give ITS ammo and "
                     "the reserve stays at zero: guns that fire from reserve click, nothing reloads.\n"
                     "  Do: in the set bridge's Configure(), when the parent is loaded:\n" + lines +
                     "\n  Also check its monster drops (CustomInventory drop items) and its start classes: "
                     "every start class must give Doom ammo, not the mod's."))

    kc = [k["text"].lower() for k in R["keyconf"]]
    pc = [m for m in R["mapinfo"] if m["key"].lower() == "playerclasses"]
    if any(t.startswith("clearplayerclasses") for t in kc) or pc:
        why = "KEYCONF clearplayerclasses" if any(t.startswith("clearplayerclasses") for t in kc) \
            else "MAPINFO PlayerClasses (replaces the list)"
        todo.append(("FAIL", f"The set's player class can never be picked ({why})",
                     "The New Game row is deleted before the menu is built. The set must be INJECTED:\n"
                     "  * a companion Players pk3: the mod's own player files, start items pointed at our guns and Doom ammo;\n"
                     "  * a companion Slots pk3: a KEYCONF with a NEW weaponsection name putting our guns on 1-0;\n"
                     "  * the bridge's SetClass() returns \"\" while the parent is loaded.\n"
                     "  NEVER: `replaces` on our gun classes (ZScript cannot replace DECORATE -- the pack silently "
                     "fails to load), or a timer that rebuilds weapon slots (buzzes the controller every tick)."))

    wep_hits = [(DOOM_WEAPONS[k], repl[k]["class"]) for k in DOOM_WEAPONS if k in repl]
    if wep_hits:
        todo.append(("INFO", "The mod replaces Doom's weapons",
                     "Its guns stand in for these Doom roles -- the bridge's Swap table should cover each:\n" +
                     "\n".join(f"      {doom:14} -> {theirs}" for doom, theirs in wep_hits)))

    if any(r["zscript"] is False for r in R["replaces"]):
        todo.append(("INFO", "Its actors are DECORATE",
                     "Our ZScript gun classes can NOT say `replaces` on any of them. Use the bridge (CheckReplacement)."))

    if R["weapons"]:
        mod_ammo = sorted({w["ammo"] for w in R["weapons"] if w["ammo"]
                           and w["ammo"].lower() not in DOOM_AMMO})
        if mod_ammo:
            todo.append(("INFO", "Its guns keep their own magazine ammo classes",
                         "These are the mod's internal counters (HUD, its reload). Our guns do not use them; "
                         "harmless, but its HUD will show them:\n  " + ", ".join(mod_ammo[:40])))

    haz = defaultdict(list)
    for h in R["acs_hazards"]:
        haz[h["hazard"]].append(h)
    for label, hits in haz.items():
        level = "FAIL" if label in ("SetWeapon", "PROP_TOTALLYFROZEN") else "WARN"
        where = "\n".join(f"      {h['file']}:{h['line']}  {h['text']}" for h in hits[:12])
        more = f"\n      ... and {len(hits) - 12} more" if len(hits) > 12 else ""
        todo.append((level, f"ACS: {label} ({len(hits)} place(s))", f"{hits[0]['why']}.\n{where}{more}\n"
                     "  Decide per feature: disable it for our guns, or make our guns survive it. "
                     "Test each in the headset with a diagnostic that prints ReadyWeapon."))

    if R["acs_buttons"]:
        todo.append(("WARN", "ACS reads the player's buttons every tic",
                     "Check each against what the VR controllers send. A button the mod turns into a kick, "
                     "a reload token or a weapon switch will fire under our guns too:\n" +
                     "\n".join(f"      {b:18} {', '.join(v[:3])}" for b, v in sorted(R["acs_buttons"].items()))))

    if R.get("acs_archived"):
        todo.append(("INFO", f"{len(R['acs_archived'])} ACS source file(s) in archive folders skipped",
                     "Folders named archive/old/unused are assumed not compiled. If the mod DOES compile them, "
                     "re-run after moving them:\n      " + "\n      ".join(R["acs_archived"][:10])))

    if R["compiled_acs_without_source"]:
        todo.append(("WARN", "Compiled ACS with no source",
                     "These cannot be audited -- anything above may also be hiding here:\n      " +
                     "\n      ".join(R["compiled_acs_without_source"][:20])))

    if R["zs_replacement_hooks"]:
        todo.append(("WARN", "The mod has its own ZScript spawn/replacement hooks",
                     "They may race the set bridge for the same spawns (handler order decides):\n" +
                     "\n".join(f"      {h['hook']:20} {h['file']}:{h['line']}" for h in R["zs_replacement_hooks"][:15])))
    return todo


def _chain(R, key):
    seen = []
    while key and key in R["classes"] and key not in seen:
        seen.append(key)
        key = R["classes"][key]["parent"]
    return seen


# ---------------------------------------------------------------------------
def render(R, todo):
    out = [f"# Parent mod audit: {os.path.basename(R['mod'])}", ""]
    n = {"FAIL": 0, "WARN": 0, "INFO": 0}
    for lvl, _, _ in todo:
        n[lvl] += 1
    out += [f"**{n['FAIL']} must-fix, {n['WARN']} to check, {n['INFO']} for information.**", "",
            "## What the set has to do", ""]
    for lvl, title, body in todo:
        out += [f"### [{lvl}] {title}", "", "```", body, "```", ""]

    out += ["## Findings", "", "### Doom classes it replaces", ""]
    doomish = {**DOOM_AMMO, **DOOM_WEAPONS, **DOOM_PLAYER}
    rows = [r for r in R["replaces"] if r["replaces"].lower() in doomish]
    out += [f"- `{r['replaces']}` -> `{r['class']}`  ({r['file']}:{r['line']})" for r in rows] or ["- none"]
    other = [r for r in R["replaces"] if r["replaces"].lower() not in doomish]
    out += ["", f"Plus {len(other)} other replacement(s) (monsters, decorations, effects).", ""]

    out += ["### Player classes", ""]
    out += [f"- KEYCONF `{k['text']}`  ({k['file']}:{k['line']})" for k in R["keyconf"]] or ["- KEYCONF: none"]
    out += [f"- MAPINFO `{m['key']} = {m['value']}`  ({m['file']}:{m['line']})" for m in R["mapinfo"]]
    out += ["", "Start items, per player class:", ""]
    for cls, items in sorted(R["startitems"].items()):
        out.append(f"- **{cls}**: " + ", ".join(f"{i}" + (f" x{a}" if a != 1 else "") for i, a in items[:30]))
    out += ["", "### Weapon slots", ""]
    out += [f"- `{s['text']}`" for s in R["slots"][:40]] or ["- none (engine defaults)"]
    out += ["", f"### Its weapons ({len(R['weapons'])})", "", "| class | ammo | file |", "|---|---|---|"]
    out += [f"| {w['class']} | {w['ammo'] or '-'} | {w['file']}:{w['line']} |" for w in R["weapons"][:150]]
    out += ["", "### Event handlers it registers", ""]
    out += [f"- `{h['value']}`  ({h['file']}:{h['line']})" for h in R["handlers"]] or ["- none"]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mod", help="the parent mod: a .pk3/.zip or its folder")
    ap.add_argument("--out", help="write the report here (markdown)")
    ap.add_argument("--json", help="write the raw findings here (for set_gate.py --audit)")
    a = ap.parse_args()

    R = audit(Source(a.mod))
    todo = implications(R)
    md = render(R, todo)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(md)
        print(f"wrote {a.out}")
    else:
        sys.stdout.write(md)
    if a.json:
        slim = {k: v for k, v in R.items() if k != "classes"}
        slim["implications"] = [{"level": l, "title": t, "detail": d} for l, t, d in todo]
        json.dump(slim, open(a.json, "w", encoding="utf-8"), indent=1, default=list)
        print(f"wrote {a.json}")
    fails = sum(1 for l, _, _ in todo if l == "FAIL")
    print(f"\n{fails} must-fix item(s). Read 'What the set has to do' before writing a card.", file=sys.stderr)


if __name__ == "__main__":
    main()
