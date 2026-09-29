#!/usr/bin/env python3
"""
test_emit.py -- step 6's done-check, against the set that already works.

For the ten fully-built guns of vanilla_check: every _wm.md3 vertex within 1/64
of the shipped Vanilla mesh, and every Scale and Offset within 0.001 of the
shipped MODELDEF. BFG and Plasma may differ by exactly 1.7 in Offset z, because
Vanilla built them with the donor's ZOffset read as 0; that is the only allowed
difference.

This is the test that says R2, R3 and R4 are the rules the working set was
actually built by, rather than a plausible reconstruction of them. If the
arithmetic here is a hair out, every gun in every later set is a hair out in
the same direction, and nobody would see it as anything but "the guns feel
slightly wrong".

THE CHAIN IS FOLLOWED, NOT TYPED. Section 7 names the reference CARD per donor.
The card names its prop; the prop block gives the scale, offset, mesh and path.
So a wrong reference cannot be introduced by typing the wrong file name here.

    python tests/test_emit.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

from forge import md3 as MD3          # noqa: E402
from forge import donor as D          # noqa: E402
from forge import emit_mesh as EM     # noqa: E402
from forge import emit_prop as EP     # noqa: E402
from forge import setfile as SF       # noqa: E402
from test_donor import DONORS, find_md3s, parse_all_modeldefs, index_actors, resolve  # noqa: E402

REFERENCE = r"E:\DOOMWork\RS_VR_Weapons"

# Section 7, "The 12 guns in vanilla_check", the ten built in full.
# RPG and nade are "parts only" there, so their meshes and props are not checked.
PAIRS = [
    ("AssaultShotgun", "WM_AssaultShotgun"),
    ("BrutalSMG", "WM_SMG"),
    ("Rifle", "WM_Rifle"),
    ("Plasma", "WM_PlasmaRifle"),
    ("BFG", "WM_BFGHeavy"),
    ("Machinegun", "WM_MachineGun"),
    ("minigun", "WM_Chaingun"),
    ("RailGun", "WM_Railgun"),
    ("Unmaker", "WM_Unmaker"),
    ("Flamethrower2", "WM_Flamethrower"),
]

# Step 6: "BFG and Plasma differ by exactly 1.7 in Offset z (Vanilla used
# ZOffset 0); that is the only allowed difference."
ALLOWED_Z_SLIP = {"BFG": 1.7, "Plasma": 1.7}

VERT_TOL = 1.0 / 64.0
PROP_TOL = 0.001


def read_card(card_dir: str, weapon: str):
    """The card's own keys for one weapon, from whichever WMCARD.* holds it."""
    pat = re.compile(r'^\s*weapon\s+"?' + re.escape(weapon) + r'"?\s*$', re.I)
    for f in sorted(os.listdir(card_dir)):
        if not f.upper().startswith("WMCARD"):
            continue
        path = os.path.join(card_dir, f)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="latin-1") as fh:
            lines = fh.read().splitlines()
        for i, line in enumerate(lines):
            if not pat.match(line):
                continue
            keys = {}
            for rest in lines[i + 1:]:
                s = rest.strip()
                if s.lower() == "end":
                    break
                if s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                keys[k.strip().lower()] = v.strip()
            return f, keys
    return None, None


def read_prop_block(modeldef_paths, cls: str):
    """Scale and Offset off a prop's MODELDEF block."""
    for path in modeldef_paths:
        if not os.path.exists(path):
            continue
        text = re.sub(r"//[^\n]*", "", open(path, "r", encoding="latin-1").read())
        for m in re.finditer(r"Model\s+(\w+)\s*\{(.*?)\}", text, re.S):
            if m.group(1).lower() != cls.lower():
                continue
            body = m.group(2)
            sc = re.search(r"Scale\s+(\S+)\s+(\S+)\s+(\S+)", body)
            of = re.search(r"Offset\s+(\S+)\s+(\S+)\s+(\S+)", body)
            md = re.search(r'Model\s+0\s+"([^"]+)"', body)
            pa = re.search(r'Path\s+"([^"]+)"', body)
            return {
                "file": os.path.basename(path),
                "scale": tuple(float(sc.group(i)) for i in (1, 2, 3)) if sc else None,
                "offset": tuple(float(of.group(i)) for i in (1, 2, 3)) if of else None,
                "mesh": md.group(1) if md else None,
                "path": pa.group(1) if pa else None,
            }
    return None


def quoted(value: str):
    """`= "a" "b"` -> ('a', 'b')."""
    return re.findall(r'"([^"]*)"', value or "")


def fake_gun(model, gid: str) -> SF.Gun:
    """A minimal map: the largest surface as body, everything else fixed. Only
    the vertex positions are compared here, and R2 moves every surface by the
    same shift, so the names do not affect what this test measures."""
    body = max(range(len(model.surfaces)), key=lambda i: model.surfaces[i].num_verts)
    others = [i for i in range(len(model.surfaces)) if i != body]
    return SF.Gun(id=gid, cls="X", donor="", modeldef="", decorate="", body=body, fixed=others)


def compare_meshes(ours, theirs):
    """Worst vertex deviation between two meshes, compared as vertex CLOUDS.

    R2 is a rule about where the vertices are, and the shipped set reaches the
    same positions with the surfaces grouped differently: Plasma's two 'Frame'
    surfaces are merged into one body, the minigun's four into one, and the
    machinegun's 11,996-vertex receiver is split into a body and a magazine.
    Every one of those keeps the vertex count identical -- nothing is dropped --
    because grouping is what set.py declares and R2 does not touch it.

    So the clouds are sorted and compared. That is order-blind and
    grouping-blind and still catches a wrong frame, a missed recentring, or a
    rotation, which is everything R2 can get wrong. Whether the surfaces are
    grouped as the set asks is step 11's business, once vanilla_check's set.py
    exists to say so; it is reported here as a note.
    """
    a = sorted(v for s in ours.surfaces for v in s.verts[0])
    b = sorted(v for s in theirs.surfaces for v in s.verts[0])
    if len(a) != len(b):
        return None, f"{len(a)} vertices vs {len(b)}"
    worst = max((max(abs(p[k] - q[k]) for k in range(3)) for p, q in zip(a, b)), default=0.0)
    note = ""
    if len(ours.surfaces) != len(theirs.surfaces):
        note = (f"grouped differently: {len(ours.surfaces)} surfaces vs {len(theirs.surfaces)} "
                f"(set.py declares merges and splits)")
    if theirs.num_frames != 1:
        note = (note + "; " if note else "") + f"shipped mesh has {theirs.num_frames} frames"
    return worst, note


def main() -> int:
    md3s = find_md3s(DONORS)
    modeldefs = parse_all_modeldefs(DONORS)
    actors = index_actors(DONORS)
    ref_modeldefs = [os.path.join(REFERENCE, "MODELDEF.txt"),
                     os.path.join(REFERENCE, "plus", "MODELDEF.txt")]
    tmp = tempfile.mkdtemp(prefix="weaponforge_emit_")

    failures = []
    print(f"{'donor':16}{'card':20}{'scale':>8}{'offset dx,dy,dz':>28}{'mesh':>9}  note")
    for stem, card_name in PAIRS:
        card_file, card = read_card(REFERENCE, card_name)
        if not card:
            failures.append(f"{stem}: no card named {card_name} in {REFERENCE}")
            print(f"{stem:16}{card_name:20}  NO CARD")
            continue
        prop_cls = quoted(card.get("prop", ""))
        prop_cls = prop_cls[0] if prop_cls else ""
        block = read_prop_block(ref_modeldefs, prop_cls)
        if not block or not block["scale"] or not block["offset"]:
            failures.append(f"{stem}: no MODELDEF block for prop {prop_cls!r}")
            print(f"{stem:16}{card_name:20}  NO PROP BLOCK ({prop_cls})")
            continue

        path = md3s.get(stem.lower())
        wins, tried = resolve(stem, path, modeldefs, actors) if path else ([], [])
        if not wins:
            failures.append(f"{stem}: no rest frame: {tried[:2]}")
            print(f"{stem:16}{card_name:20}  NO REST FRAME")
            continue
        d = wins[0]

        model = MD3.MD3Model.load(d.md3)
        gun = fake_gun(model, stem)
        res = EM.emit_mesh(model, gun, d.rest_frame, os.path.join(tmp, f"{stem}_wm.md3"))
        scale = EP.prop_scale(d.scale)
        offset = EP.prop_offset(res.t, d.z_offset, abs(scale[0]))

        dscale = max(abs(a - b) for a, b in zip(scale, block["scale"]))
        doff = [a - b for a, b in zip(offset, block["offset"])]
        slip = ALLOWED_Z_SLIP.get(stem)
        z_ok = abs(doff[2]) <= PROP_TOL or (slip is not None and abs(abs(doff[2]) - slip) <= PROP_TOL)
        xy_ok = abs(doff[0]) <= PROP_TOL and abs(doff[1]) <= PROP_TOL

        ref_mesh = os.path.join(REFERENCE, (block["path"] or "").replace("/", os.sep),
                                block["mesh"] or "")
        worst, note = (None, "reference mesh not found")
        if os.path.exists(ref_mesh):
            worst, note = compare_meshes(MD3.MD3Model.load(res.out), MD3.MD3Model.load(ref_mesh))

        if dscale > PROP_TOL:
            failures.append(f"{stem}: Scale {tuple(round(c, 4) for c in scale)} vs shipped "
                            f"{block['scale']}")
        if not xy_ok:
            failures.append(f"{stem}: Offset x,y off by {doff[0]:+.4f},{doff[1]:+.4f} "
                            f"(ours {tuple(round(c, 4) for c in offset)}, "
                            f"shipped {block['offset']})")
        if not z_ok:
            failures.append(f"{stem}: Offset z off by {doff[2]:+.4f} (ours {offset[2]:.4f}, "
                            f"shipped {block['offset'][2]})"
                            + (f"; only {slip} is allowed here" if slip else ""))
        if worst is None:
            failures.append(f"{stem}: meshes not comparable: {note}")
        elif worst > VERT_TOL:
            failures.append(f"{stem}: worst vertex {worst:.4f} from the shipped mesh "
                            f"(tolerance {VERT_TOL:.4f})")

        mark = f"{worst:.4f}" if worst is not None else "  -  "
        extra = note
        if slip is not None and abs(abs(doff[2]) - slip) <= PROP_TOL:
            extra = (extra + "; " if extra else "") + f"z differs by {slip} as allowed"
        print(f"{stem:16}{card_name:20}{dscale:>8.4f}"
              f"{f'{doff[0]:+.4f},{doff[1]:+.4f},{doff[2]:+.4f}':>28}{mark:>9}  {extra}")

    if failures:
        print(f"\nFAIL: {len(failures)} problem(s)")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"\nPASS: {len(PAIRS)} guns rebuilt to within 1/64 of their shipped meshes and "
          f"0.001 of their shipped props")
    return 0


if __name__ == "__main__":
    sys.exit(main())
