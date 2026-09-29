"""Static lint of the pending card drafts in RS_VR_Weapons/_pending (no game, no build).

Pulls every fenced block holding a `weapon "..."` card out of the _pending docs and checks:
  keys      each key is one parser.zs accepts in that block (weapon / part / dof / dof2 / store /
            verb); `pellets` / `spread` / `damage` are refused (the shot is the class's); `hands`
            is an approved pending key (reported as PENDING, not an error)
  values    firesfrom is chamber | magazine | reserve | none; casing is yes | none | no
  files     model, skin, magmodel, magskin, roundmodel, roundskin exist in RS_VR_Weapons
  surfaces  every `surface = X` (and roundsurface's surface) is a surface of the card's model
  sounds    every *sound value is a SNDINFO name in this package, the reload system, or the IWAD
  classes   the weapon class and its prop are declared somewhere under zscript/
  refs      verbs' parts / latch / rides exist; stores they name exist or are the synthesised
            mag / chamber; needs = open:X names an open verb; roundsurface stores exist
  firesfrom parser.zs FiresFromProblem, mirrored:
            reserve / none -- no declared store but a barrel's; no cycle or swap verb; load and
              eject only into / from a barrel's store; no role = action or role = feed part
              (either synthesises a verb)
            magazine -- a counted store (declared, or none declared so it is synthesised); no
              cycle and no role = action part; no load / eject / open-ejectall naming `chamber`
  barrels   G-UBL (uzdxrema-11's rules): input = altfire, one per card; trigger is a part, not
            role = trigger and not a verb's part; from is a declared store, not detach, not
            mag / chamber, not shared; needs = shut:X names an open verb; firetics a positive
            whole number. Until parser.zs reads the barrel grammar, a card with a barrel has its
            barrel and firesfrom findings listed as PENDING.
  mechanism a card's `mechanism = X` takes archetype X's verbs from RS_VR_Reload/WMCARD.txt, its own
            blocks under the same id laid over them (same kind), so refs and rules see the verbs
            the card really runs. --wmcard also lints every archetype block on its own.
  verbs     eject by = hand | tilt | muzzleup; tilt needs tiltaxis; tiltaxis not on by = hand; no
            part on a tilt eject. open close = flick | hand | none; flickaxis / flickscale only
            with close = flick; flickscale above 0, at most 4; close = flick not with a spring.
            (flickaxis = side on a part that does not move across is the rig's call -- not mirrored.)
  rules     hands = 2 has a support part
  geometry  every grab / handseat / muzzle / magcenter / ejectport / load `at` lies within the
            model's bounding box grown by 6 units

    python card_lint.py            the drafts in _pending
    python card_lint.py --wmcard   the live cards in WMCARD.txt
    python card_lint.py --sheets   every Weapon Card in WMSHEET.*: keys, class, Model Card, capacity
    python card_lint.py --file X   one file's cards: a .md's fenced blocks, anything else as WMCARD text
"""
import glob
import os
import re
import math
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")
PKG = "E:/DOOMWork/RS_VR_Weapons/"
RELOAD = "E:/DOOMWork/RS_VR_Reload/"
IWAD_SND = "E:/DOOMWork/UZDXREMA/wadsrc/static/filter/game-doomchex/sndinfo.txt"

parser = open(RELOAD + "zscript/wm/parser.zs", encoding="utf-8").read()
PARSER_KEYS = set(re.findall(r'key == "([a-z0-9_]+)"', parser))

WEAPON_KEYS = {"type", "handprofile", "prop", "hand", "model", "skin", "capacity", "magfamily", "muzzle", "exhaustport", "exhaustdir",
               "barrel", "ejectport", "ejectdir", "magmodel", "magskin", "magscale", "magcenter", "roundmodel",
               "roundskin", "roundscale",
               # NO "modelscale" HERE, DELIBERATELY. I added it and the ENGINE REFUSED THE CARD:
               # parser.zs does not know the key, so the whole weapon was skipped at load while this
               # lint said 0. A LINT THAT ACCEPTS WHAT THE REAL CONSUMER REFUSES IS WORSE THAN NO
               # LINT -- it converts a loud failure into a silent one. The draw scale travels as a
               # COMMENT the engine ignores and make_modeldef reads (`# modelscale = 4.500`).
               "firesound", "ejectsound", "drysound", "magoutsound", "maginsound",
               "slidebacksound", "slidefwdsound", "rackapexsound", "rackresetsound", "magdropsound",
               "casingsound", "cycleoutsound", "cyclehomesound", "loadsound", "opensound", "closesound",
               "firesfrom", "casing", "mechanism", "spinupsound", "spinsound", "spindownsound",
               # BODY = N (reload lane, 2026-09-18, parser.zs WM_Card.bodySurface). Which surface is the
               # gun itself, by index. On a mesh that names every surface the same string it cannot be
               # inferred -- biggest picks a slide that outweighs its frame, stillest ties because a
               # whole gun recoils together -- and a wrong pick does not give a slightly wrong number,
               # it inverts the mesh so the gun appears to move around a stationary slide. -1 = as before.
               "body",
               "pullsound", "startsound", "idlesound", "stopsound", "magskinempty",
               # BONE DRIVE (reload lane, 2026-09-15). Both repeatable, so both are collected into
               # lists below rather than into card["keys"], where a second line would silently
               # overwrite the first.
               "hidesurface", "hidejoint"}
REFUSED_WEAPON_KEYS = {"pellets", "spread", "damage"}
# `joint` is the bone-drive alternative to `surface`: the part is moved by a named joint of its
# model. Everything else on the part -- dof, dof2, grab, grabsize, handseat, take, index -- reads
# exactly as it does for a surface part.
# FINGERPRINT = <verts>, <size> (reload lane, 2026-09-18, parser.zs WM_Part.fpVerts / fpSize). A part
# addressed by surface INDEX silently means something else after a re-export renumbers the mesh; the
# vertex count and size are what turn that into a loud failure instead of a mystery. 0 = not stated.
PAWW2_KEYS = {"role", "subject", "surface", "joint", "fingerprint", "model", "grab", "grabradius", "grabsize", "handseat", "take",
             "cock", "roundsurface", "spin", "spinrate", "spinup", "spindown", "flip", "fliptics", "flipphase",
             "metersurface", "meterskins", "metersteps"}
DOF_KEYS = {"kind", "axis", "distance", "degrees", "pivot", "detach", "rest", "twist", "twistaxis"}
DOF2_KEYS = {"kind", "axis", "distance", "degrees", "pivot", "split"}
INDEX_KEYS = {"kind", "axis", "pivot", "degrees", "distance", "from", "steps"}   # G13
STORE_KEYS = {"kind", "capacity", "detach", "family", "slots", "indexed", "advance"}
VERB_KEYS = {
    "cycle": {"part", "outat", "apex", "homeat", "onout", "from", "onhome", "feed", "into", "return",
              "holdopen", "auto"},
    "open": {"part", "latch", "latchat", "latchreturn", "openat", "closeat", "rest", "return", "onopen", "from",
             "close", "button", "flickaxis", "flickscale"},
    "swap": {"part", "store", "seatat", "detachat", "pullout", "button", "handtake", "needs", "latch", "latchat",
             "latchreturn"},
    "load": {"into", "slot", "at", "size", "dir", "subject", "rides", "needs"},
    "eject": {"by", "part", "at", "from", "all", "needs", "tiltaxis", "button"},
    "start": {"part", "outat"},   # CS-G1, pull to start
}
# G-UBL, the second barrel (uzdxrema-11's names, 2026-09-13). Pending until parser.zs reads it.
BARREL_KEYS = {"input", "trigger", "from", "shotclass", "ammo", "muzzle", "barrel", "firesound", "needs",
               "firetics", "casing"}
UBL = 'key == "shotclass"' in parser and '"altfire"' in parser
# THE MAGFAMILY RULE'S SWITCH, as the parser has it (parser.zs `const MAGFAMILY_REQUIRED`): 0 warns, non-zero refuses.
MAGFAMILY_REQUIRED = bool(re.search(r"const\s+MAGFAMILY_REQUIRED\s*=\s*(true|0*[1-9]\d*)\b", parser, re.I))
# `hands` is a real key once parser.zs compares against it (uzdxrema-11, 2026-09-13); pending before.
PENDING = {"weapon": set() if 'key == "hands"' in parser else {"hands"}}
if 'key == "hands"' in parser:
    WEAPON_KEYS.add("hands")
# G16, belt links: real keys once parser.zs compares against them.
if 'key == "linkmodel"' in parser:
    WEAPON_KEYS |= {"linkmodel", "linkskin", "linkscale"}
FIRESFROM = {"chamber", "magazine", "reserve", "none"}
CASING = {"yes", "none", "no"}

# Every key the lint allows must be one the parser really compares against (or approved pending).
for group in [WEAPON_KEYS, PAWW2_KEYS, DOF_KEYS, DOF2_KEYS, INDEX_KEYS, STORE_KEYS] + list(VERB_KEYS.values()) + ([BARREL_KEYS] if UBL else []):
    missing = group - PARSER_KEYS
    if missing:
        print("NOTE: lint allows keys parser.zs does not mention:", sorted(missing))


def sndinfo_names(path):
    names = set()
    if not os.path.isfile(path):
        return names
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.split("//")[0].strip()
        if not line:
            continue
        m = re.match(r"\$random\s+(\S+)", line)
        if m:
            names.add(m.group(1).lower())
            continue
        if line.startswith("$"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            names.add(parts[0].lower())
    return names


# EVERY BALLISTICS PROFILE A SHEET NAMES MUST EXIST.
#
# THE RTCW SET SHIPPED WITH 68 DEAD PROFILE NAMES (2026-09-19). I wrote rtcw_<gun> on all
# seventeen guns; ballistics had built ww2_<gun>; nothing was ever built under a single rtcw_ name.
# The set fired with no flash, no smoke, no brass and no round look, and this lint returned 0 --
# because it checked SOUND names against SNDINFO and profile names against NOTHING AT ALL.
#
# Same shape as the pistol-magazine bug and the stray .jpg: a declaration that resolves to nothing
# looks exactly like one that works, and only a check that goes and looks can tell them apart.
# READ THE PACKED PK3, NOT THE SOURCE TREE, AND SAY WHICH.
#
# "it is in RSBDEFS" and "it is in the pk3 he is running" ARE NOT THE SAME STATEMENT. The five
# ShieldSaw deflect profiles were written, committed and never packed: this lint was green against
# the source while the owner's game had no definition for any of them, so every deflection asked
# for a profile that was not there and nothing drew. A check that quietly proves the WRONG thing
# is worse than no check, which is why the fallback announces itself.
RSB_PK3 = r"E:\DOOMWork\RS_Ballistics\RS_Ballistics.pk3"
RSBDEFS = r"E:\DOOMWork\RS_Ballistics\RSBDEFS.txt"
PROFILES = {}
try:
    try:
        import zipfile as _zf
        _rsb = _zf.ZipFile(RSB_PK3).read("RSBDEFS.txt").decode("utf-8", "replace")
    except Exception:
        _rsb = open(RSBDEFS, encoding="utf-8", errors="replace").read()
        print("  card_lint: NO RS_Ballistics.pk3 -- profiles checked against the SOURCE tree, "
              "which can be ahead of what is installed")
    for _kind in ("round", "flash", "recoil", "ejecta", "trail", "impact", "roundlook", "ballistics"):
        PROFILES[_kind] = set(re.findall(r'^%s\s+(\w+)' % _kind, _rsb, re.M))
except OSError:
    PROFILES = {}       # ballistics not checked out: skip rather than fail every card

SOUNDS = sndinfo_names(PKG + "SNDINFO.txt")
# EACH SET'S OWN SNDINFO TOO (bwolf/SNDINFO.txt, ww2/...). An add-on ships its own sound names the
# same way it ships its own MODELDEF -- SNDINFO accumulates across archives rather than replacing.
# Without this, a set's gun sound is a name the lint cannot see and every card stating one fails.
for f in glob.glob(PKG + "*/SNDINFO.txt"):
    SOUNDS |= sndinfo_names(f)
for f in glob.glob(RELOAD + "SNDINFO*") + glob.glob(RELOAD + "sndinfo*"):
    SOUNDS |= sndinfo_names(f)
SOUNDS |= sndinfo_names(IWAD_SND)

ZS = "\n".join(open(f, encoding="utf-8").read() for f in glob.glob(PKG + "zscript/**/*.zs", recursive=True))
CLASSES = set(re.findall(r"^\s*class\s+(\w+)", ZS, re.M))


def md3_info(path):
    b = open(path, "rb").read()
    h = struct.unpack_from("<4si64siiiiiiiii", b, 0)
    off = h[10]
    names, lo, hi = set(), [1e9] * 3, [-1e9] * 3
    # PER SURFACE, IN ORDER. A card may address a part by INDEX rather than by name -- the WW2 set
    # does, because every surface in it carries the same meaningless string -- and an indexed part
    # carries a fingerprint, because a re-export that renumbers the surfaces would otherwise change
    # what `surface = 4` means with nothing to say so.
    surfs = []
    for s in range(h[6]):
        sh = struct.unpack_from("<4s64siiiiiiiiii", b, off)
        sname = sh[1].split(b"\0")[0].decode("latin-1")
        names.add(sname)
        nf, nv, o_xyz = sh[3], sh[5], sh[10]
        # FRAME 0 ONLY for the fingerprint, and that is the whole difference. lo/hi below deliberately
        # span EVERY frame, because a card on a donor mesh may rest at a later one -- but a
        # fingerprint is the part's size at REST, and a magazine that swings out during the animation
        # measures half as long again across the whole run. Measured the other way, every honest card
        # fails.
        slo, shi = [1e9] * 3, [-1e9] * 3
        # EVERY FRAME, not frame 0: a card on a donor mesh (the Rifle) sits at a later rest
        # frame, and the raise frames before it swing the gun somewhere else entirely.
        for f in range(nf):
            base = off + o_xyz + 8 * nv * f
            for v in range(nv):
                x, y, z, _ = struct.unpack_from("<hhhH", b, base + 8 * v)
                for i, c in enumerate((x / 64.0, y / 64.0, z / 64.0)):
                    lo[i] = min(lo[i], c)
                    hi[i] = max(hi[i], c)
                    if f == 0:
                        slo[i] = min(slo[i], c)
                        shi[i] = max(shi[i], c)
        # THE DIAGONAL, because that is what the generator that WROTE these fingerprints measures
        # (gen_ww2_set.py size_of: sqrt of the summed squared extents). Max-extent is a different
        # number and every honest card fails against it.
        surfs.append((sname, nv, math.sqrt(sum((shi[k] - slo[k]) ** 2 for k in range(3)))))
        off += sh[11]
    return names, lo, hi, surfs


def vec(val):
    try:
        v = [float(x) for x in val.split(",")]
        return v if len(v) == 3 else None
    except ValueError:
        return None


def path_pair(val):
    m = re.findall(r'"([^"]+)"', val)
    return (m[0] + "/" + m[1]) if len(m) == 2 else None


def cards_in(md):
    text = open(md, encoding="utf-8").read()
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.S):
        if re.search(r'^weapon "\w', block, re.M):
            yield block


# ARCHETYPES: `archetype <name>` ... `end` in RS_VR_Reload/WMCARD.txt -- verb blocks and one `type`.
ARCH_FILE = RELOAD + "WMCARD.txt"


def parse_archetypes(path):
    archs, found = {}, []
    arch, verb = None, None
    for n, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        words = line.split()
        if words[0] == "archetype":
            if len(words) != 2:
                found.append(("?", f"line {n}: `archetype <name>` alone on its line"))
                continue
            if words[1] in archs:
                found.append((words[1], f"line {n}: an archetype by that name was already read"))
            arch, verb = {"name": words[1], "type": None, "verbs": []}, None
            archs[words[1]] = arch
            continue
        if arch is None:
            found.append(("?", f"line {n}: nothing here belongs to an archetype: {line}"))
            continue
        if line == "end":
            if verb is not None:
                verb = None
            else:
                if not arch["verbs"]:
                    found.append((arch["name"], "it holds no verb blocks"))
                arch = None
            continue
        if words[0] in VERB_KEYS and len(words) == 2 and "=" not in line:
            if any(v["id"] == words[1] for v in arch["verbs"]):
                found.append((arch["name"], f"line {n}: a second verb with id {words[1]}"))
            verb = {"kind": words[0], "id": words[1], "keys": {}}
            arch["verbs"].append(verb)
            continue
        if "=" not in line:
            found.append((arch["name"], f"line {n}: unparsed: {line}"))
            continue
        key, val = [x.strip() for x in line.split("=", 1)]
        if verb is not None:
            if key not in VERB_KEYS[verb["kind"]]:
                found.append((arch["name"], f"{verb['kind']} {verb['id']}: unknown key {key}"))
            verb["keys"][key] = val
        elif key == "type":
            arch["type"] = val
        else:
            found.append((arch["name"], f"line {n}: an archetype holds verb blocks and one type line -- not {key}"))
    if arch is not None:
        found.append((arch["name"], "its block was never closed with `end`"))
    return archs, found


ARCHS, ARCH_ISSUES = parse_archetypes(ARCH_FILE)


def verb_rules(v):
    """parser.zs's per-verb value checks and refusals that need no geometry (VerbKey, FinishCard)."""
    out, vk, tag = [], v["keys"], f"{v['kind']} {v['id']}"

    def low(key):
        return vk.get(key, "").strip('"').strip().lower()

    def direction(s):
        d = vec(s)
        return d is not None and any(abs(c) > 1e-9 for c in d)

    for key in ("button", "handtake", "all"):
        if key in vk and low(key) not in ("yes", "no"):
            out.append(f"{tag}: {key} is yes or no")
    if v["kind"] == "eject":
        by = low("by") or "hand"
        if by not in ("hand", "tilt", "muzzleup"):
            out.append(f"{tag}: by is hand, tilt or muzzleup")
        if "tiltaxis" in vk and low("tiltaxis") not in ("barrel", "up", "down") and not direction(vk["tiltaxis"]):
            out.append(f"{tag}: tiltaxis is barrel, up, down, or x, y, z in the gun's model axes")
        if by == "tilt" and "tiltaxis" not in vk:
            out.append(f"{tag}: by = tilt needs tiltaxis = barrel | up | down | x, y, z")
        if by == "hand" and "tiltaxis" in vk:
            out.append(f"{tag}: tiltaxis says which axis points up -- this eject is by = hand")
        if by in ("tilt", "muzzleup") and "part" in vk:
            out.append(f"{tag}: by = {by} is worked by pointing the gun, not by a part -- drop part")
    if v["kind"] == "start":
        if "part" not in vk:
            out.append(f"{tag}: a start verb needs part = <the ripcord a hand pulls>")
        if "outat" in vk:
            try:
                oa = float(low("outat"))
            except ValueError:
                oa = -1.0
            if not 0 < oa <= 1:
                out.append(f"{tag}: outat is a number above 0, at most 1")
    if v["kind"] == "open":
        close = low("close")
        if close and close not in ("flick", "hand", "none"):
            out.append(f"{tag}: close is flick, hand or none")
        if "flickaxis" in vk and low("flickaxis") not in ("up", "side") and not direction(vk["flickaxis"]):
            out.append(f"{tag}: flickaxis is up, side, or x, y, z in the gun's model axes")
        if "flickscale" in vk:
            try:
                fs = float(low("flickscale"))
            except ValueError:
                fs = -1.0
            if not 0 < fs <= 4:
                out.append(f"{tag}: flickscale is a number above 0, at most 4")
        if ("flickaxis" in vk or "flickscale" in vk) and close != "flick":
            out.append(f"{tag}: flickaxis and flickscale say how a flick shuts it -- no close = flick")
        if close == "flick" and "spring" in (low("rest"), low("return")):
            out.append(f"{tag}: close = flick shuts a part that stays open -- rest = spring already shuts it")
    if v["kind"] == "cycle":
        # parser.zs FinishCard's cycle refusals. The first skipped the whole WM_SMG card in game (09-14) while this
        # lint passed it: a spring-return action comes home by itself, so homeat is refused on it.
        ret = low("return")
        if ret == "spring" and "homeat" in vk:
            out.append(f"{tag}: homeat is where an action returned by hand counts as home -- this one is return = spring")
        elif ret and ret != "spring" and "homeat" in vk and "outat" in vk:
            try:
                ha, oa = float(low("homeat")), float(low("outat"))
            except ValueError:
                ha, oa = 0.0, 1.0
            if ha >= oa:
                out.append(f"{tag}: homeat {ha:.2f} is not short of outat {oa:.2f} -- one position would be both out and home")
    return out


def lint(block):
    issues, pend = [], []
    card = {"keys": {}, "parts": {}, "stores": {}, "verbs": [], "barrels": {}}
    ctx, cur, sub = None, None, None
    for raw in block.split("\n"):
        line = raw.split("#")[0].rstrip()
        if not line.strip():
            continue
        s = line.strip()
        words = s.split()
        if s == "end":
            if sub:
                sub = None
            elif cur is not None:
                cur = None
                ctx = None
            else:
                ctx = None
            continue
        if words[0] == "weapon" and len(words) >= 2:
            card["name"] = words[1].strip('"')
            ctx = "weapon"
            continue
        if words[0] == "part" and len(words) == 2:
            cur = {"id": words[1], "keys": {}, "surfaces": [], "dof": {}, "dof2": {}, "index": {}, "roundsurface": []}
            card["parts"][words[1]] = cur
            ctx = "part"
            continue
        if words[0] == "store" and len(words) == 2 and "=" not in s:
            cur = {"id": words[1], "keys": {}}
            card["stores"][words[1]] = cur
            ctx = "store"
            continue
        if words[0] in VERB_KEYS and len(words) == 2 and "=" not in s:
            cur = {"kind": words[0], "id": words[1], "keys": {}}
            card["verbs"].append(cur)
            ctx = "verb"
            continue
        if words[0] == "barrel" and len(words) == 2 and "=" not in s:
            cur = {"id": words[1], "keys": {}}
            card["barrels"][words[1]] = cur
            ctx = "barrel"
            continue
        if s in ("dof", "dof2", "index") and ctx == "part":
            sub = s
            continue
        if "=" not in s:
            issues.append("unparsed line: " + s)
            continue
        key, val = [x.strip() for x in s.split("=", 1)]
        if sub:
            allowed = {"dof": DOF_KEYS, "dof2": DOF2_KEYS, "index": INDEX_KEYS}[sub]
            if key not in allowed:
                issues.append(f"part {cur['id']} {sub}: unknown key {key}")
            cur[sub][key] = val
        elif ctx == "weapon" or ctx is None:
            if key in PENDING["weapon"]:
                pend.append(f"{key} = {val}")
            elif key in REFUSED_WEAPON_KEYS:
                issues.append(f"weapon: `{key}` is refused -- the shot is the weapon class's (WM_Gun.Shot*)")
            elif key not in WEAPON_KEYS:
                issues.append(f"weapon: unknown key {key}")
            # REPEATABLE, so they cannot live in card["keys"] -- a second hidesurface would
            # overwrite the first there and the card would quietly hide one mesh instead of two.
            if key in ("hidesurface", "hidejoint"):
                card.setdefault(key, []).append(val)
            else:
                card["keys"][key] = val
        elif ctx == "part":
            if key not in PAWW2_KEYS:
                issues.append(f"part {cur['id']}: unknown key {key}")
            if key == "surface":
                cur["surfaces"].append(val)
            elif key == "roundsurface":
                cur["roundsurface"].append([x.strip() for x in val.split(",")])
            else:
                cur["keys"][key] = val
        elif ctx == "store":
            if key not in STORE_KEYS:
                issues.append(f"store {cur['id']}: unknown key {key}")
            cur["keys"][key] = val
        elif ctx == "verb":
            if key not in VERB_KEYS[cur["kind"]]:
                issues.append(f"{cur['kind']} {cur['id']}: unknown key {key}")
            cur["keys"][key] = val
        elif ctx == "barrel":
            if key not in BARREL_KEYS:
                issues.append(f"barrel {cur['id']}: unknown key {key}")
            cur["keys"][key] = val

    k = card["keys"]
    name = card.get("name", "?")
    # mechanism: the archetype's verbs, the card's own blocks under the same id laid over them
    mech = k.get("mechanism", "").strip('"')
    if mech:
        arch = ARCHS.get(mech)
        if arch is None:
            issues.append(f"mechanism = {mech} names no archetype in RS_VR_Reload/WMCARD.txt")
        else:
            merged = [{"kind": v["kind"], "id": v["id"], "keys": dict(v["keys"])} for v in arch["verbs"]]
            byid = {v["id"]: v for v in merged}
            for v in card["verbs"]:
                if v["id"] not in byid:
                    merged.append(v)
                elif byid[v["id"]]["kind"] != v["kind"]:
                    issues.append(f"{v['kind']} {v['id']}: archetype {mech}'s {v['id']} is a {byid[v['id']]['kind']} block")
                else:
                    byid[v["id"]]["keys"].update(v["keys"])
            card["verbs"] = merged
    for v in card["verbs"]:
        issues += verb_rules(v)
        # F3, the latch (uzdxrema-11, 16:18): a part of this card, not the verb's own, with a surface;
        # latchat above 0, at most 1. (That the latch part exists is the refs check below.)
        vk = v["keys"]
        latch = vk.get("latch", "").strip('"')
        if latch and latch != "none":
            if latch == vk.get("part", "").strip('"'):
                issues.append(f"{v['kind']} {v['id']}: latch {latch} is the verb's own part")
            elif latch in card["parts"] and not (card["parts"][latch]["surfaces"]
                                                 or "joint" in card["parts"][latch]["keys"]):
                issues.append(f"{v['kind']} {v['id']}: latch {latch} has nothing on the mesh for a hand to throw -- no surface and no joint")
        if "latchat" in vk:
            try:
                la = float(vk["latchat"])
            except ValueError:
                la = -1.0
            if not 0 < la <= 1:
                issues.append(f"{v['kind']} {v['id']}: latchat is a number above 0, at most 1")
            if not latch or latch == "none":
                issues.append(f"{v['kind']} {v['id']}: latchat without a latch")
        if "latchreturn" in vk:
            if vk["latchreturn"].strip('"').lower() not in ("spring", "stay"):
                issues.append(f"{v['kind']} {v['id']}: latchreturn is spring or stay")
            if not latch or latch == "none":
                issues.append(f"{v['kind']} {v['id']}: latchreturn on a verb with no latch")
    if sum(1 for v in card["verbs"] if v["kind"] == "start") > 1:
        issues.append("a second start verb -- a gun has one engine to pull")
    # classes
    if name not in CLASSES:
        issues.append(f"class {name} not declared anywhere under zscript/")
    prop = k.get("prop", "").strip('"')
    if prop and prop not in CLASSES:
        issues.append(f"prop {prop} not declared")
    # A FEED PART THAT DETACHES MUST SAY WHAT COMES OFF.
    #
    # THIS IS THE PISTOL-MAGAZINE BUG (2026-09-19) AND IT REACHED THE OWNER. Thirteen WW2 cards and
    # seventeen RTCW ones declared a feed part with `detach` -- a magazine that leaves the gun --
    # and named no magmodel for it. loose.zs falls back to MODELDEF's WM_LooseMag, which the base
    # pack defines as models/pistols/wm_m4a3_mag.md3, so EVERY GUN IN BOTH SETS DROPPED AN M4A3
    # PISTOL MAGAZINE: the Kar98's stripper clip, the MG42's belt, the Flammenwerfer's fuel tank.
    # With the correct drop sound, which made it read as finished rather than broken.
    #
    # NOTHING CAUGHT IT. The cards parsed, so this lint returned 0 on all three modes. build.ps1
    # verifies that every magmodel names a file in the pk3 -- but thirteen cards named nothing, and
    # there is no reference to resolve when none was ever made. A verifier only sees what was
    # declared; this is the check for what was NOT.
    #
    # The reload lane's assemble.py now refuses to WRITE such a card. This is the second check,
    # because a card can reach us from somewhere other than their generator.
    if "magmodel" not in k:
        # THE VALUE, NOT THE KEY. `detach = no` and `detach = 0.95` both contain the word, and a
        # part with no dof at all detaches nothing. WM_RocketLauncher's drum says `detach = no` in
        # its STORE and has no dof whatsoever -- rockets go in one at a time at the muzzle -- and a
        # looser sweep of mine read it as a detaching magazine with no mesh. Adding four lines
        # would have declared a detachable drum on a gun that has none. Anchor the key AND test
        # its value: only a NUMBER means something comes off.
        def _detaches(p):
            for d in (p["dof"], p["dof2"]):
                v = str(d.get("detach", "")).strip().strip('"')
                try:
                    if float(v) > 0: return True
                except ValueError:
                    pass
            return False
        detaching = sorted(p["id"] for p in card["parts"].values()
                           if p["keys"].get("role") == "feed" and _detaches(p))
        if detaching:
            issues.append(
                "part %s: role = feed with `detach` and no magmodel -- something comes off this gun "
                "and the card does not say what it looks like, so it falls back to the base pack's "
                "pistol magazine (MODELDEF WM_LooseMag). State magmodel, magskin, magscale and "
                "magcenter; all four, or it draws offset and at the wrong size."
                % ", ".join(detaching))

    # values
    fires = k.get("firesfrom", "chamber").strip('"').lower()
    if fires not in FIRESFROM:
        issues.append(f"firesfrom = {fires}: not one of {sorted(FIRESFROM)}")
    if "hands" in k and k["hands"].strip('"') not in ("1", "2"):
        issues.append(f"hands = {k['hands']}: not 1 or 2")
    if "casing" in k and k["casing"].strip('"').lower() not in CASING:
        issues.append(f"casing = {k['casing']}: not one of {sorted(CASING)}")
    # files
    model = path_pair(k.get("model", ""))
    names, lo, hi, surfs = set(), None, None, []
    for key in ("model", "skin", "magmodel", "magskin", "magskinempty", "roundmodel", "roundskin", "linkmodel", "linkskin"):
        p = path_pair(k.get(key, ""))
        if p and not os.path.isfile(PKG + p):
            issues.append(f"{key}: missing file {p}")
    if model and os.path.isfile(PKG + model):
        names, lo, hi, surfs = md3_info(PKG + model)
    # sounds
    # Parsed, never played by any mechanism (the reload lane, 09-13): a slide's or bolt's rack sounds
    # are rackapexsound / rackresetsound.
    for key, instead in (("slidebacksound", "rackapexsound"), ("slidefwdsound", "rackresetsound")):
        if key in k:
            issues.append(f"{key} is parsed but never played -- say {instead}")
    for key, val in k.items():
        if key.endswith("sound"):
            sn = val.strip('"').lower()
            if sn not in SOUNDS:
                issues.append(f"{key}: sound {sn} is not in any SNDINFO")
    # HIDESURFACE names a surface of model 0, the same kind of name `surface =` does, so it is
    # checked the same way. HIDEJOINT is NOT checked and must not be: the model loads after the card,
    # so the engine cannot resolve a joint name at parse time either -- it logs at bind instead
    # ("part 'x' names joint 'y', which this model does not have"). Refusing one here would refuse
    # cards the engine accepts.
    for hs in card.get("hidesurface", []):
        if names and hs not in names:
            issues.append(f"hidesurface {hs} is not in the model ({sorted(names)})")
    # surfaces
    for p in card["parts"].values():
        for sname in p["surfaces"]:
            # BY INDEX OR BY NAME.
            if re.fullmatch(r"\d+", sname.strip()):
                idx = int(sname)
                if surfs and not (0 <= idx < len(surfs)):
                    issues.append(f"part {p['id']}: surface {idx} is out of range -- the model has {len(surfs)}")
                elif surfs:
                    # THE FINGERPRINT IS WHAT MAKES AN INDEX SAFE. Without it a renumbered mesh
                    # silently repoints this row at a different part.
                    fp = p["keys"].get("fingerprint", "")
                    want = [x.strip() for x in fp.split(",")] if fp else []
                    if len(want) == 2:
                        got_name, got_v, got_sz = surfs[idx]
                        wv, wsz = int(float(want[0])), float(want[1])
                        if wv != got_v:
                            issues.append(f"part {p['id']}: fingerprint says {wv} verts, surface {idx} ({got_name}) has {got_v} -- the mesh was renumbered or replaced")
                        elif abs(wsz - got_sz) > max(0.5, wsz * 0.02):
                            issues.append(f"part {p['id']}: fingerprint says {wsz:.2f} across, surface {idx} ({got_name}) measures {got_sz:.2f}")
            elif names and sname not in names:
                issues.append(f"part {p['id']}: surface {sname} not in the model ({sorted(names)})")
        for rs in p["roundsurface"]:
            if names and rs[0] not in names:
                issues.append(f"part {p['id']}: roundsurface {rs[0]} not in the model")
            if len(rs) != 3:
                issues.append(f"part {p['id']}: roundsurface {', '.join(rs)} is not <surface>, <store>, <n|any>")
                continue
            sname, sid, n = rs
            if n != "any" and not re.match(r"^\d+$", n):
                issues.append(f"part {p['id']}: roundsurface {sname}: {n} is not a whole number or any")
                continue
            st = card["stores"].get(sid)
            if st is None and sid not in ("mag", "chamber"):
                issues.append(f"part {p['id']}: roundsurface {sname}: this card has no store {sid}")
                continue
            if n == "any":
                continue
            # parser.zs (G12): on a COUNTED store the number is a count -- drawn while the store
            # holds MORE than it, so it must be under the capacity (the synthesised mag's is the
            # card's). On a slotted store it is a slot, counted from 0.
            kind = st["keys"].get("kind") if st else ("counted" if sid == "mag" else "slotted")
            if kind == "counted":
                cap = (st["keys"].get("capacity") if st else None) or k.get("capacity", "0")
                if int(n) >= int(cap):
                    issues.append(f"part {p['id']}: roundsurface {sname} names count {n} -- {sid} holds at most {cap}, so it would never show")
            else:
                sl = st["keys"].get("slots", "1") if st else "1"
                nslots = int(sl) if re.match(r"^\d+$", sl) else len([x for x in sl.split(",") if x.strip()])
                if int(n) >= nslots:
                    issues.append(f"part {p['id']}: roundsurface {sname} names slot {n} -- {sid} has {nslots}, counted from 0")
    # A roundsurface adds its surface to the part, so naming it by `surface =` too draws it twice.
    named = [s for p in card["parts"].values() for s in p["surfaces"]] + \
            [rs[0] for p in card["parts"].values() for rs in p["roundsurface"]]
    for sname in sorted({s for s in named if named.count(s) > 1}):
        issues.append(f"surface {sname} is named by more than one surface / roundsurface line")
    # refs
    stores = set(card["stores"]) | ({"mag", "chamber"} if not card["stores"] else set())
    opens = {v["id"] for v in card["verbs"] if v["kind"] == "open"}
    for v in card["verbs"]:
        vk = v["keys"]
        for ref in ("part", "latch", "rides"):
            if ref in vk and vk[ref] not in card["parts"]:
                issues.append(f"{v['kind']} {v['id']}: {ref} {vk[ref]} is not a part")
        for ref in ("store", "from", "feed", "into"):
            if ref in vk and vk[ref] not in stores:
                issues.append(f"{v['kind']} {v['id']}: {ref} {vk[ref]} is not a store ({sorted(stores)})")
        if "needs" in vk:
            m = re.match(r"open:(\w+)", vk["needs"])
            if not m or m.group(1) not in opens:
                issues.append(f"{v['kind']} {v['id']}: needs {vk['needs']} names no open verb")
    # firesfrom -- parser.zs FiresFromProblem, mirrored
    roles = {p["keys"].get("role") for p in card["parts"].values()}
    barrels = card["barrels"]
    bstores = {b["keys"].get("from") for b in barrels.values()} - {None}
    ff = []
    if fires in ("reserve", "none"):
        # A barrel's own store, and the load / eject verbs that work only it, are not the main
        # barrel's rounds (G-UBL). An open's onopen = ejectall from it was never refused here.
        for sid in card["stores"]:
            if sid not in bstores:
                ff.append(f"firesfrom = {fires} keeps no rounds -- store {sid} is refused")
        for v in card["verbs"]:
            vk = v["keys"]
            own = (v["kind"] == "load" and vk.get("into") in bstores) or (v["kind"] == "eject" and vk.get("from") in bstores)
            if v["kind"] in ("cycle", "swap", "load", "eject") and not own:
                ff.append(f"firesfrom = {fires} keeps no rounds -- {v['kind']} {v['id']} is refused")
        for p in card["parts"].values():
            if p["keys"].get("role") in ("action", "feed"):
                ff.append(f"firesfrom = {fires}: part {p['id']} is role = {p['keys']['role']}, which synthesises a verb that is refused")
    elif fires == "magazine":
        declared = card["stores"]
        if declared and not any(s["keys"].get("kind") == "counted" for s in declared.values()):
            ff.append("firesfrom = magazine spends a counted store, and the card declares stores but no counted one")
        if not declared and "feed" not in roles:
            ff.append("firesfrom = magazine but no role = feed part (nothing to synthesise the magazine's swap from)")
        if "action" in roles:
            ff.append("firesfrom = magazine but a part is role = action (it synthesises a cycle, refused)")
        for v in card["verbs"]:
            vk = v["keys"]
            if v["kind"] == "cycle":
                ff.append(f"firesfrom = magazine: cycle {v['id']} is refused")
            named = vk.get("into") if v["kind"] == "load" else (
                vk.get("from") if v["kind"] == "eject" or (v["kind"] == "open" and vk.get("onopen") == "ejectall") else None)
            if named == "chamber" and "chamber" not in declared:
                ff.append(f"firesfrom = magazine: {v['kind']} {v['id']} names chamber, and there is none")
    # barrels -- G-UBL, as uzdxrema-11 specified it
    bf = []
    altfire = 0
    verb_parts = {v["keys"].get(r) for v in card["verbs"] for r in ("part", "latch", "rides")} - {None}
    for b in barrels.values():
        bk, bid = b["keys"], b["id"]
        if bk.get("input", "").strip('"').lower() != "altfire":
            bf.append(f"barrel {bid}: input = altfire is required (the only input)")
        else:
            altfire += 1
        trig = bk.get("trigger")
        if trig:
            if trig not in card["parts"]:
                bf.append(f"barrel {bid}: trigger {trig} is not a part")
            elif card["parts"][trig]["keys"].get("role") == "trigger":
                bf.append(f"barrel {bid}: trigger {trig} is role = trigger (the main barrel's)")
            elif trig in verb_parts:
                bf.append(f"barrel {bid}: trigger {trig} is a verb's part")
        bfrom = bk.get("from")
        if not bfrom:
            bf.append(f"barrel {bid}: from = <a declared store> is required")
        elif bfrom in ("mag", "chamber"):
            bf.append(f"barrel {bid}: from = {bfrom} -- a barrel's store cannot be named mag or chamber")
        elif bfrom not in card["stores"]:
            bf.append(f"barrel {bid}: from = {bfrom} is not a declared store")
        elif "detach" in card["stores"][bfrom]["keys"]:
            bf.append(f"barrel {bid}: from = {bfrom} is a detachable store")
        elif sum(1 for o in barrels.values() if o["keys"].get("from") == bfrom) > 1:
            bf.append(f"barrel {bid}: from = {bfrom} is shared by two barrels")
        if "needs" in bk:
            m = re.match(r"shut:(\w+)$", bk["needs"])
            if not m or m.group(1) not in opens:
                bf.append(f"barrel {bid}: needs {bk['needs']} names no open verb (needs = shut:<open id>)")
        if "firetics" in bk and not re.match(r"^[1-9]\d*$", bk["firetics"]):
            bf.append(f"barrel {bid}: firetics = {bk['firetics']} is not a positive whole number")
        if "casing" in bk and bk["casing"].strip('"').lower() not in CASING:
            bf.append(f"barrel {bid}: casing = {bk['casing']}: not one of {sorted(CASING)}")
        shot = bk.get("shotclass", "").strip('"')
        if shot.startswith("WM_") and shot not in CLASSES:
            bf.append(f"barrel {bid}: shotclass {shot} is not declared anywhere under zscript/")
        if "firesound" in bk and bk["firesound"].strip('"').lower() not in SOUNDS:
            bf.append(f"barrel {bid}: firesound {bk['firesound']} is not in any SNDINFO")
        if "barrel" in bk and not vec(bk["barrel"]):
            bf.append(f"barrel {bid}: barrel = {bk['barrel']} is not x, y, z")
    if altfire > 1:
        bf.append(f"{altfire} altfire barrels -- one per card")
    if barrels and not UBL:
        pend.append("(G-UBL) parser.zs reads no barrel block yet: " + ", ".join(sorted(barrels)))
        pend += ["(G-UBL) " + f for f in ff + bf]
    else:
        issues += ff + bf
    # rules
    if k.get("hands") == "2" and "support" not in roles:
        issues.append("hands = 2 but no role = support part")
    # spin (G11, uzdxrema-11's refusals): a spinning part is a single-stage hinge whose degrees is
    # one period, with a rate under half of it, no role, no verb working it, and a surface.
    for p in card["parts"].values():
        pk = p["keys"]
        spin = pk.get("spin", "none").lower()
        if spin not in ("trigger", "fire", "none"):
            issues.append(f"part {p['id']}: spin = {spin} is not trigger, fire or none")
        if spin == "none":
            continue
        pid = p["id"]
        try:
            rate = float(pk.get("spinrate", "0"))
        except ValueError:
            rate = 0.0
        if rate == 0:
            issues.append(f"part {pid}: spin needs a non-zero spinrate")
        if p["dof"].get("kind") != "hinge" or p["dof2"]:
            issues.append(f"part {pid}: spin needs a single-stage hinge dof")
        try:
            period = float(p["dof"].get("degrees", "0"))
        except ValueError:
            period = 0.0
        if period <= 0:
            issues.append(f"part {pid}: spin needs degrees > 0 (one period of the pattern)")
        elif abs(rate) >= period / 2:
            issues.append(f"part {pid}: |spinrate| {abs(rate)} >= degrees / 2 ({period / 2}) would look still or run backwards")
        if "role" in pk:
            issues.append(f"part {pid}: a spinning part takes no role")
        if pid in verb_parts:
            issues.append(f"part {pid}: a spinning part cannot be worked by a verb")
        if not p["surfaces"]:
            issues.append(f"part {pid}: a spinning part needs a surface")
        for key in ("spinup", "spindown"):
            if key in pk and not (re.match(r"^\d+$", pk[key]) and int(pk[key]) <= 350):
                issues.append(f"part {pid}: {key} = {pk[key]} is not 0-350 tics")
    # meter (uzdxrema-11, 16:16): a part's gauge surface wears skin ceil(fill x steps) of a %d
    # file set. All three keys or none; the surface is the part's; exactly one %d; 1-32 steps;
    # every numbered file exists.
    for p in card["parts"].values():
        pk, pid = p["keys"], p["id"]
        given = [key for key in ("metersurface", "meterskins", "metersteps") if key in pk]
        if not given:
            continue
        if len(given) != 3:
            issues.append(f"part {pid}: metersurface, meterskins and metersteps go together -- only {', '.join(given)}")
            continue
        if pk["metersurface"] not in p["surfaces"]:
            issues.append(f"part {pid}: metersurface {pk['metersurface']} is not one of its surfaces {p['surfaces']}")
        steps = int(pk["metersteps"]) if re.match(r"^\d+$", pk["metersteps"]) else 0
        if not 1 <= steps <= 32:
            issues.append(f"part {pid}: metersteps = {pk['metersteps']} is not 1-32")
        mp = path_pair(pk["meterskins"])
        if not mp or mp.count("%d") != 1:
            issues.append(f"part {pid}: meterskins needs \"<path>\" \"<file with one %d>\"")
        elif steps:
            missing = [mp.replace("%d", str(i)) for i in range(1, steps + 1) if not os.path.isfile(PKG + mp.replace("%d", str(i)))]
            if missing:
                issues.append(f"part {pid}: meterskins files missing: {missing}")
    # flip (CS-G4, uzdxrema-11's refusals): a part drawn on its own phase of every 2 x fliptics
    # tics while the trigger is held (or shots leave); at rest only phase 0 shows.
    for p in card["parts"].values():
        pk, pid = p["keys"], p["id"]
        flip = pk.get("flip", "none").lower()
        if flip not in ("trigger", "fire", "none"):
            issues.append(f"part {pid}: flip = {flip} is not trigger, fire or none")
        if flip == "none":
            if "fliptics" in pk or "flipphase" in pk:
                issues.append(f"part {pid}: fliptics / flipphase without flip")
            continue
        if "role" in pk:
            issues.append(f"part {pid}: a flipping part takes no role")
        if pk.get("spin", "none").lower() != "none":
            issues.append(f"part {pid}: a part cannot both spin and flip")
        if not p["surfaces"]:
            issues.append(f"part {pid}: a flipping part needs a surface")
        if "fliptics" in pk and not (re.match(r"^\d+$", pk["fliptics"]) and 1 <= int(pk["fliptics"]) <= 35):
            issues.append(f"part {pid}: fliptics = {pk['fliptics']} is not 1-35 tics")
        if pk.get("flipphase", "0") not in ("0", "1"):
            issues.append(f"part {pid}: flipphase is 0 or 1")
    # index (G13, parser.zs IndexKey / IndexProblem mirrored): the feed part steps with its
    # magazine's count, clamp(from - rounds, 0, steps), both unset = the capacity.
    for p in card["parts"].values():
        ix = p["index"]
        if not ix:
            continue
        pid = p["id"]
        if p["keys"].get("role") != "feed":
            issues.append(f"part {pid}: an index belongs on the role = feed part")
        if p["dof2"]:
            issues.append(f"part {pid}: an index on a two-stage part (dof2) is not supported")
        kindx = ix.get("kind", "").lower()
        if kindx not in ("slide", "hinge"):
            issues.append(f"part {pid} index: kind is slide or hinge")
        av = vec(ix.get("axis", ""))
        if not av or sum(c * c for c in av) < 0.25:
            issues.append(f"part {pid} index: needs axis = x, y, z")
        amount_key = "degrees" if kindx == "hinge" else "distance"
        try:
            amount = float(ix.get(amount_key, "0"))
        except ValueError:
            amount = 0.0
        if amount == 0:
            issues.append(f"part {pid} index: needs {amount_key} = <the {'turn' if kindx == 'hinge' else 'travel'} a step>")
        counted = [s for s in card["stores"].values() if s["keys"].get("kind") == "counted"]
        cap = int((counted[0]["keys"].get("capacity") if counted else None) or k.get("capacity", "0") or 0)
        if cap < 1:
            issues.append(f"part {pid} index: an index counts the magazine, and this card has none")
        for key in ("from", "steps"):
            if key in ix:
                if not re.match(r"^[1-9]\d*$", ix[key]):
                    issues.append(f"part {pid} index: {key} is a whole number of rounds, at least 1")
                elif cap and int(ix[key]) > cap:
                    issues.append(f"part {pid} index: {key} = {ix[key]} -- the magazine holds at most {cap}")
    # geometry
    if lo:
        g = 6.0

        def inside(label, val):
            v = vec(val)
            if v and not all(lo[i] - g <= v[i] <= hi[i] + g for i in range(3)):
                issues.append(f"{label} {tuple(v)} lies outside the model's box grown by {g}")
        for key in ("muzzle", "magcenter", "ejectport"):
            if key in k:
                inside(key, k[key])
        for p in card["parts"].values():
            for key in ("grab", "handseat"):
                if key in p["keys"]:
                    inside(f"part {p['id']} {key}", p["keys"][key])
        for v in card["verbs"]:
            if "at" in v["keys"]:
                inside(f"{v['kind']} {v['id']} at", v["keys"]["at"])
        for b in card["barrels"].values():
            if "muzzle" in b["keys"]:
                inside(f"barrel {b['id']} muzzle", b["keys"]["muzzle"])
    # 3g, WHICH MAGAZINES AND ROUNDS FIT (parser.zs FinishCard 3g, card.zs TakesFromHand, mirrored): a card that takes a
    # magazine or a round from a hand -- a swap or load verb (its own or its archetype's), the swap a role = feed part
    # synthesises, a detachable counted store -- states its magfamily; unstated it counts as "pistol". Pending while the
    # parser's MAGFAMILY_REQUIRED is false, refused once it is true.
    verb_kinds = {v["kind"] for v in card["verbs"]}
    arch = ARCHS.get(k.get("mechanism", "").strip('"'))
    if arch:
        verb_kinds |= {v["kind"] for v in arch["verbs"]}
    takes = bool(verb_kinds & {"swap", "load"})
    takes = takes or ("feed" in roles and "swap" not in verb_kinds and fires not in ("reserve", "none"))
    takes = takes or any(st["keys"].get("kind") == "counted"
                         and st["keys"].get("detach", "no").strip('"').lower() in ("yes", "true", "1")
                         for st in card["stores"].values())
    if takes and not k.get("magfamily", "").strip('"'):
        why = ('magfamily is not stated, and this card takes a magazine or a round from a hand -- say which fit: '
               'magfamily = <word> (unstated it counts as "pistol")')
        (issues if MAGFAMILY_REQUIRED else pend).append(why)
    return name, issues, pend


def card_files(root):
    """Every root file named WMCARD.<anything> in `root`, in name order -- the order the engine reads them. The
    reload lane's card library splits the cards by archetype (WMCARD.01_pistol ...); WMCARD.txt keeps the index."""
    return [os.path.join(root, n) for n in sorted(os.listdir(root))
            if n.upper().startswith("WMCARD.") and os.path.isfile(os.path.join(root, n))]


def live_blocks():
    """The live cards in every root WMCARD.* file, each from its `weapon` line to the next one."""
    return text_blocks("\n".join(open(p, encoding="utf-8").read() for p in card_files(PKG)))


def text_blocks(text):
    """The cards in WMCARD-format text, each from its `weapon` line to the next one."""
    starts = [m.start() for m in re.finditer(r'^weapon "\w', text, re.M)]
    for i, a in enumerate(starts):
        b = starts[i + 1] if i + 1 < len(starts) else len(text)
        yield text[a:b]


# ---------------------------------------------------------------- CARD INHERITANCE (`base =`)
# RS_VR_Reload 8220cc3 (the reload lane): `base = <card id>` in a card's weapon block starts it from a FRESH COPY of that
# card. Its own weapon keys replace the base's; a part / store / verb / barrel block under an id the base has replaces that
# block whole, in the same place; a new id is added; `remove part|store|verb|barrel <id>` (a line between blocks) takes one
# of the base's away. A base may have a base, up to 8 deep; a base that cannot be built leaves the child unloaded. So a
# child is incomplete on its own: everything below lints the MERGED card, and says which base it started from.
BASE_DEPTH = 8
REMOVABLE = ("part", "store", "verb", "barrel")


def card_id(block):
    m = re.match(r'\s*weapon "(\w+)"', block)
    return m.group(1) if m else None


def take_block(lines, i):
    """The block opened at lines[i], through its matching `end`. A line with no `=` that is not `end` opens a nested block,
    as a part's dof / index and a verb's sub-blocks do."""
    chunk, depth = [lines[i]], 1
    i += 1
    while i < len(lines) and depth:
        t = lines[i].strip()
        chunk.append(lines[i])
        if t == "end":
            depth -= 1
        elif "=" not in t:
            depth += 1
        i += 1
    return chunk, i


def split_card(block):
    """A card's text, comments and blank lines dropped, as (name, weapon_items, blocks, removes, base): weapon_items an
    ordered list of (key, lines) -- a key line, or a sub-block inside the weapon block under its opening line -- blocks an
    ordered list of ((category, id), lines), removes a list of (category, id)."""
    lines = [l.split("#")[0].rstrip() for l in block.split("\n")]
    lines = [l for l in lines if l.strip()]
    name = base = None
    weapon_items, blocks, removes = [], [], []
    i = 0
    while i < len(lines):
        t = lines[i].strip()
        w = t.split()
        if w[0] == "weapon" and len(w) >= 2 and name is None:
            name = w[1].strip('"')
            chunk, i = take_block(lines, i)
            inner = chunk[1:-1] if chunk[-1].strip() == "end" else chunk[1:]
            j = 0
            while j < len(inner):
                u = inner[j].strip()
                km = re.match(r"(\w+)\s*=", u)
                if km:
                    if km.group(1) == "base":
                        base = u.split("=", 1)[1].strip().strip('"')
                    else:
                        weapon_items.append((km.group(1), [inner[j]]))
                    j += 1
                else:
                    sub, j = take_block(inner, j)
                    weapon_items.append(("block " + u, sub))
            continue
        if w[0] == "remove" and len(w) == 3:
            removes.append((w[1], w[2]))
            i += 1
            continue
        if "=" in t:                                  # a stray key line between blocks: kept where it is
            blocks.append((("line", str(i)), [lines[i]]))
            i += 1
            continue
        category = w[0] if w[0] in ("part", "store", "barrel") else ("verb" if w[0] in VERB_KEYS else w[0])
        chunk, i = take_block(lines, i)
        blocks.append(((category, w[1] if len(w) > 1 else ""), chunk))
    return name, weapon_items, blocks, removes, base


def join_card(name, weapon_items, blocks):
    out = ['weapon "%s"' % name]
    for _, ls in weapon_items:
        out += ls
    out.append("end")
    for _, ls in blocks:
        out += ls
    return "\n".join(out) + "\n"


def resolve(block, index, depth=0, chain=()):
    """(the card as the engine builds it, errors). A card with no `base` comes back as the very text it was; a child whose
    base cannot be built comes back as None, as the engine leaves it unloaded."""
    name, witems, blocks, removes, base = split_card(block)
    if base is None:
        return block, ["remove %s %s: `remove` needs a `base =`" % r for r in removes]
    if depth >= BASE_DEPTH:
        return None, ["base = %s: bases chain deeper than %d cards" % (base, BASE_DEPTH)]
    if base == name or base in chain:
        return None, ["base = %s: the chain comes back to %s" % (base, base)]
    if base not in index:
        return None, ["base = %s: no card by that id, so %s stays unloaded" % (base, name)]
    btext, berrs = resolve(index[base], index, depth + 1, chain + (name,))
    if btext is None:
        return None, ["base = %s cannot be built (%s), so %s stays unloaded" % (base, "; ".join(berrs), name)]
    _, bw, bb, _, _ = split_card(btext)
    errs = []
    for category, rid in removes:
        if category not in REMOVABLE:
            errs.append("remove %s %s: only a part, store, verb or barrel can be removed" % (category, rid))
        elif (category, rid) not in [k for k, _ in bb]:
            errs.append("remove %s %s: %s has no %s %s" % (category, rid, base, category, rid))
        else:
            bb = [(k, ls) for k, ls in bb if k != (category, rid)]
    for items, own in ((bw, witems), (bb, blocks)):
        for k, ls in own:
            at = next((n for n, (kk, _) in enumerate(items) if kk == k), None)
            if at is None:
                items.append((k, ls))
            else:
                items[at] = (k, ls)
    return join_card(name, bw, bb), errs


def raw_card_index():
    """Model Card id -> its text as written, from every root WMCARD.* file."""
    text = "\n".join(open(p, encoding="utf-8").read() for p in card_files(PKG))
    return {card_id(b): b for b in text_blocks(text)}


def lint_resolved(block, index):
    """lint() on the card as the engine builds it; a child's name says which base it started from."""
    text, errs = resolve(block, index)
    base = split_card(block)[4]
    if text is None:
        return (card_id(block) or "?"), errs, []
    name, issues, pend = lint(text)
    if base:
        name = "%s <- %s" % (name, base)
    return name, errs + issues, pend



# ---------------------------------------------------------------- WEAPON CARDS (WMSHEET.*)
# A gun is its Weapon Card: which Model Card it uses (`model =`, unset = the card with the gun's own name) and what it
# shoots. The reload lane's reader (RS_VR_Reload/zscript/wm/sheet.zs) refuses unknown keys at load; this says so before
# the build, and checks what the reader cannot: that every gun has a class and that its capacity fits the model.
SHEET_GUN_KEYS = {"shotpellets", "shotspread", "shotdamage", "firetics", "chambersperpull", "fullauto",
                  "firstshotsaccurate", "roundspershot", "shotclass", "shotrail", "railcolors", "trailprofile", "chargetics",
                  "chargesound", "shotsaw", "sawsounds", "sawpuff", "releasetics", "roundprofile", "flashprofile",
                  # THE THROW (RS_VR_Reload 12:02): altmode = thrown, plus what leaves the hand
                  # and how long you wind up first. Added here the same hour the reader learned
                  # them -- a lint that refuses what the real consumer accepts is the `modelscale`
                  # mistake in the mirror, and costs a build for a card that was always valid.
                  "throwclass", "throwtics",
                  # THE GUN'S OWN WEIGHT IN POUNDS, EMPTY (RS_VR_Reload 13:07). Checked against the
                  # reader BEFORE any sheet stated it -- `modelscale` as an unknown key took out a
                  # whole weapon, `chargesound` on the wrong card took out a whole set, and this
                  # would have taken out sixty-six guns at once.
                  "baseweight",
                  "altflashprofile", "ejectaprofile", "recoilprofile", "altrecoilprofile", "capacity", "firesfrom",
                  "firesound", "model", "spinuptics", "spindowntics",
                  "altmode", "altburst", "altbursttics", "altratescale", "altdamagescale", "altfanmax", "spreadshape"}
SHEET_BARREL_KEYS = {"shotclass", "ammo", "firesound", "firetics"}
FIRES_FROM = {"chamber", "magazine", "reserve", "none"}


def sheet_files(root):
    """Every root file named WMSHEET.<anything> in `root`, in name order."""
    return [os.path.join(root, n) for n in sorted(os.listdir(root))
            if n.upper().startswith("WMSHEET.") and os.path.isfile(os.path.join(root, n))]


def card_index():
    """Model Card id -> its text: the `weapon` block and the store/part/verb/barrel blocks after it."""
    raw = raw_card_index()
    return {cid: (resolve(b, raw)[0] or b) for cid, b in raw.items()}


def physical_limit(block):
    """The rounds a Model Card's gun can physically hold, from its stores: a counted store's capacity (a tube), else a
    slotted store's slots (a cylinder, the chambers) that no barrel draws from. None when it has neither (a detachable
    magazine holds what the Weapon Card says)."""
    barrel_from = set()
    for bm in re.finditer(r"^barrel \w+\n(.*?)^end", block, re.M | re.S):
        barrel_from.update(re.findall(r"^\s*from\s*=\s*(\w+)", bm.group(1), re.M))
    counted, slotted = [], []
    for sm in re.finditer(r"^store (\w+)\n(.*?)^end", block, re.M | re.S):
        sid, body = sm.group(1), sm.group(2)
        kind = re.search(r"^\s*kind\s*=\s*(\w+)", body, re.M)
        cap = re.search(r"^\s*capacity\s*=\s*(\d+)", body, re.M)
        slots = re.search(r"^\s*slots\s*=\s*(\d+)", body, re.M)
        if kind and kind.group(1) == "counted" and cap:
            counted.append((int(cap.group(1)), sid))
        elif kind and kind.group(1) == "slotted" and slots and sid not in barrel_from:
            slotted.append((int(slots.group(1)), sid))
    if counted:
        return max(counted)
    if slotted:
        return max(slotted)
    return None


def handwritten_classes():
    names = set()
    # EVERY ZSCRIPT FOLDER THIS PACKAGE SHIPS, not just rs_vr_weapons: the grenade lives in
    # zscript/rs_grenade and the ShieldSaw in zscript/rs_shieldsaw, and both are weapons with cards.
    #
    # ANY generated_guns*.zs is skipped, not just that exact name -- the set split (0d3b30a) put the
    # Vanilla+ classes in generated_guns_plus.zs, and a name-exact test read all sixteen of them as
    # handwritten: "a handwritten class AND a `class` block" on every WM_VP_ gun.
    zdir = PKG + "zscript"
    for sub, _dirs, files_ in os.walk(zdir):
        for zf in files_:
            if zf.endswith(".zs") and not zf.startswith("generated_guns"):
                names.update(re.findall(r"^class\s+(\w+)",
                                        open(os.path.join(sub, zf), encoding="utf-8").read(), re.M))
    return names


def lint_sheets():
    """Every gun in every WMSHEET.* file: (file, gun, issues)."""
    cards, classes, seen, results = card_index(), handwritten_classes(), {}, []
    for path in sheet_files(PKG):
        fn = os.path.basename(path)
        gun, depth, sub, keys, has_class, issues = None, 0, None, {}, False, []

        def finish():
            model = keys.get("model", (None, 0))[0]
            if model is not None:
                model = model.strip('"')
                if model not in cards:
                    issues.append(f"model = {model}: no Model Card by that id in any WMCARD.* file")
                if gun in cards:
                    issues.append(f"has its own Model Card AND a model line -- the reader keeps its own card")
            elif gun not in cards:
                issues.append("no Model Card: no card named for this gun, and no `model =` line")
            if gun not in classes and not has_class:
                issues.append("no class: neither a handwritten class nor a `class` block for the class writer")
            if gun in classes and has_class:
                issues.append("a handwritten class AND a `class` block -- one class per gun")
            # firesfrom = magazine spends a counted store: the model card must declare one or have a role = feed part the
            # parser synthesises one from -- else the engine refuses the whole card at load (parser.zs FiresFromProblem).
            fires_from = keys.get("firesfrom", (None, 0))[0]
            model_block = cards.get(model if model is not None else gun)
            if fires_from == "magazine" and model_block:
                counted = re.search(r"^store \w+\s*\n(?:(?!^end).)*?^\s*kind\s*=\s*counted", model_block, re.M | re.S)
                feed = re.search(r"^\s*role\s*=\s*feed\b", model_block, re.M)
                if not counted and not feed:
                    issues.append("firesfrom = magazine, but its model card has no counted store and no role = feed part -- "
                                  "the engine refuses the card (fire from the reserve, or give the card a magazine)")
            # EVERY BALLISTICS PROFILE NAMED HERE MUST EXIST. See the PROFILES note at the top:
            # the RTCW set shipped with 68 names nothing was ever built under, and this lint said 0.
            # A profile that resolves to nothing is silent -- no flash, no smoke, no brass, no error.
            if PROFILES:
                for key, kind in (("roundprofile", "round"), ("flashprofile", "flash"),
                                  ("altflashprofile", "flash"), ("recoilprofile", "recoil"),
                                  ("altrecoilprofile", "recoil"), ("ejectaprofile", "ejecta"),
                                  ("trailprofile", "trail")):
                    if key in keys:
                        nm = keys[key][0].strip('"')
                        if nm and nm not in PROFILES.get(kind, ()):
                            issues.append(f"{key} = {nm}: no `{kind} {nm}` in RS_Ballistics/RSBDEFS.txt -- "
                                          f"it resolves to nothing and the gun fires with no {kind}")
            if "firesfrom" in keys and keys["firesfrom"][0] not in FIRES_FROM:
                issues.append(f"firesfrom = {keys['firesfrom'][0]}: one of {', '.join(sorted(FIRES_FROM))}")
            if "capacity" in keys:
                val = keys["capacity"][0]
                block = cards.get(model if model is not None else gun)
                if not re.fullmatch(r"\d+", val):
                    issues.append(f"capacity = {val}: a whole number")
                elif block:
                    limit = physical_limit(block)
                    if limit and int(val) > limit[0]:
                        issues.append(f"capacity = {val}, but the model's store {limit[1]} holds {limit[0]}")
            results.append((fn, gun, list(issues)))

        for n, raw in enumerate(open(path, encoding="utf-8"), 1):
            line = raw.split("#")[0].strip()
            if not line:
                continue
            m = re.match(r'gun\s+"(\w+)"\s*$', line)
            if m:
                if gun:
                    issues.append("its block was never closed with `end`")
                    finish()
                gun, depth, sub, keys, has_class, issues = m.group(1), 1, None, {}, False, []
                if gun in seen:
                    issues.append(f"a second Weapon Card for this gun (the first is in {seen[gun]})")
                seen[gun] = f"{fn} line {n}"
                continue
            if gun is None:
                results.append((fn, "?", [f"line {n}: `{line}` is outside any `gun` block"]))
                continue
            if line == "end":
                depth -= 1
                sub = None if depth <= 1 else sub
                if depth == 0:
                    finish()
                    gun = None
                continue
            if depth == 1 and "=" not in line:
                w = line.split()
                if w == ["class"]:
                    sub, has_class, depth = "class", True, 2
                elif len(w) == 2 and w[0] == "barrel":
                    sub, depth = "barrel", 2
                else:
                    issues.append(f"line {n}: `{line}` is not a block this card knows (class, barrel <id>)")
                continue
            km = re.match(r"(\w+)\s*=\s*(.+?)\s*$", line)
            if not km:
                issues.append(f"line {n}: `{line}` is not `key = value`")
                continue
            key, val = km.group(1).lower(), km.group(2)
            if sub == "class":
                continue                       # make_gun_classes.py checks these
            if sub == "barrel":
                if key not in SHEET_BARREL_KEYS:
                    issues.append(f"line {n}: `{key}` is not a barrel shot key ({', '.join(sorted(SHEET_BARREL_KEYS))})")
                continue
            if key not in SHEET_GUN_KEYS:
                issues.append(f"line {n}: `{key}` is not a Weapon Card key")
                continue
            if key in keys:
                issues.append(f"line {n}: `{key}` set twice")
            keys[key] = (val.strip('"') if key == "firesfrom" else val, n)
        if gun:
            issues.append("its block was never closed with `end`")
            finish()
    return results


def main(argv):
    total = 0
    if "--sheets" in argv:
        for fn, gun, issues in lint_sheets():
            print(f"{fn:22s} {gun:22s} {'OK' if not issues else str(len(issues)) + ' issue(s)'}")
            for i in issues:
                print("    - " + i)
            total += len(issues)
        print("issues in the Weapon Cards (WMSHEET.*):", total)
        return 1 if total else 0
    if "--file" in argv:
        # ONE FILE: a draft card for review (tools/card_skeleton.py writes them). A .md lints its
        # fenced card blocks, as the _pending docs do; anything else lints as WMCARD text.
        i = argv.index("--file")
        if i + 1 >= len(argv):
            print("card_lint: --file needs a path")
            return 2
        path = argv[i + 1]
        if path.lower().endswith(".md"):
            blocks = list(cards_in(path))
        else:
            blocks = list(text_blocks(open(path, encoding="utf-8").read()))
        if not blocks:
            print(f"{os.path.basename(path)}: no card (no `weapon \"...\"` line)")
            return 1
        index = raw_card_index()
        index.update({card_id(b): b for b in blocks})
        for block in blocks:
            name, issues, pend = lint_resolved(block, index)
            print(f"{os.path.basename(path):22s} {name:22s} {'OK' if not issues else str(len(issues)) + ' issue(s)'}")
            for i in issues:
                print("    - " + i)
            for p in pend:
                print("    pending: " + p)
            total += len(issues)
        print(f"issues in {os.path.basename(path)}:", total)
        return 1 if total else 0
    if "--wmcard" in argv:
        for aname, arch in ARCHS.items():
            ai = [m for a, m in ARCH_ISSUES if a == aname]
            for v in arch["verbs"]:
                ai += verb_rules(v)
            print(f"RS_VR_Reload/WMCARD.txt archetype {aname:18s} {'OK' if not ai else str(len(ai)) + ' issue(s)'}"
                  f"  ({', '.join(v['kind'] + ' ' + v['id'] for v in arch['verbs'])})")
            for i in ai:
                print("    - " + i)
            total += len(ai)
        for a, m in ARCH_ISSUES:
            if a == "?":
                print("RS_VR_Reload/WMCARD.txt  - " + m)
                total += 1
        index = raw_card_index()
        for block in live_blocks():
            name, issues, pend = lint_resolved(block, index)
            print(f"WMCARD.txt             {name:22s} {'OK' if not issues else str(len(issues)) + ' issue(s)'}")
            for i in issues:
                print("    - " + i)
            for p in pend:
                print("    pending: " + p)
            total += len(issues)
        print("issues in WMCARD.txt:", total)
        return 1 if total else 0
    index = raw_card_index()
    for md in sorted(glob.glob(PKG + "_pending/*.md")):
        text = open(md, encoding="utf-8").read()
        for block in cards_in(md):
            name, issues, pend = lint_resolved(block, index)
            superseded = md.endswith("CHAINGUN_CARDS.md") and name == "WM_MachineGun" and "SUPERSEDED" in text
            tag = " (superseded draft)" if superseded else ""
            head = f"{os.path.basename(md):22s} {name:22s}{tag}"
            print(f"{head} {'OK' if not issues else str(len(issues)) + ' issue(s)'}")
            for i in issues:
                print("    - " + i)
            for p in pend:
                print("    pending: " + p)
            if not superseded:
                total += len(issues)
    print("issues (excluding superseded drafts):", total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
