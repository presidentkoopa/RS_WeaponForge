#!/usr/bin/env python3
"""
test_donor.py -- step 3's done-check: forge/donor.py reproduces every rest
frame in section 7's table, and the revolver raises.

The table in the guide is the expected output; this test is the only thing
that makes R1 more than a claim. A rest frame that comes out 0 when the table
says 4 is a mesh frozen mid-raise, which in the headset looks like a gun held
at the wrong angle rather than like a parsing bug, so it has to be caught here.

WHY THE FILE PAIRING IS DISCOVERED AND NOT TYPED

Each gun needs three files that agree: an MD3, the MODELDEF block that carries
its scale and its sprite-to-frame table, and the DECORATE class whose Ready:
state names the sprite. Typing 25 such triples by hand would let a wrong
pairing pass as a right answer -- the pairing would then be as much of a guess
as the frame.

So a candidate is built the way the engine binds them: a MODELDEF block whose
`Model 0` is this MD3, whose class name is defined as an ACTOR somewhere in the
pack, and whose own frame table contains the sprite that class's Ready state
asks for. Exactly one candidate must survive. Nothing in that chain consults
the expected answer; the table below is only ever compared against, never used
to choose a file.

That matters for nade.md3, which 49 MODELDEFs claim -- every Brutal Doom weapon
carries a grenade-throw block. Only one of those classes has a Ready state
whose sprite its own nade block actually defines.

    python tests/test_donor.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

from forge import donor as D   # noqa: E402

DONORS = r"D:\SteamLibrary\steamapps\Common\DooM VR\__Games\BrutalDoom\_BD_1.01_WeaponModels"

# Section 7, "Expected rest frames". (donor MD3 stem, ready sprite, letter, rest frame)
EXPECTED = [
    ("AssaultShotgun", "A12G", "A", 4),
    ("BFG", "BFGN", "A", 6),
    ("BFG_10k", "BG2G", "A", 6),
    ("BrutalAxe", "AXEG", "A", 5),
    ("BrutalPistol", "PIST", "F", 2),
    ("BrutalSMG", "SMGG", "A", 3),
    ("Chain_saw", "SAWG", "A", 15),
    ("DSweap", "DSLA", "A", 0),
    ("FlameCannon", "FLMG", "A", 0),
    ("Flamethrower2", "FLMT", "A", 0),
    ("HellishMissile", "RVCG", "A", 0),
    ("HitlersBuzzsaw", "HBUS", "A", 0),
    ("M79", "GLAN", "A", 3),
    ("Machinegun", "MGN1", "A", 4),
    ("minigun", "CHAG", "A", 4),
    ("MP40", "MP40", "A", 2),
    ("nade", "GRHO", "C", 2),
    ("Plasma", "PLSN", "A", 4),
    ("RailGun", "RAIL", "D", 3),
    ("Rifle", "RIFG", "A", 3),
    ("RPG", "RLNG", "A", 5),
    ("Shotgun", "SHTN", "A", 4),
    ("ssg", "SHTZ", "A", 1),
    ("Unmaker", "UNHG", "A", 0),
]

# "none in the BD 1.01 pack -- must raise; take from BD22"
MUST_RAISE = ["Revolver"]


def find_md3s(root: str) -> dict:
    """stem (lowercased) -> path, for every MD3 in the donor pack."""
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".md3"):
                out.setdefault(os.path.splitext(f)[0].lower(), os.path.join(dirpath, f))
    return out


def parse_all_modeldefs(root: str) -> dict:
    """modeldef path -> its blocks."""
    out = {}
    for f in sorted(os.listdir(root)):
        low = f.lower()
        if not low.startswith("modeldef") or not low.endswith(".def"):
            continue
        path = os.path.join(root, f)
        try:
            out[path] = D.parse_modeldef(path)
        except D.DonorError as e:
            print(f"note: skipping {f}: {e}")
    return out


def index_actors(root: str) -> dict:
    """actor name (lower) -> decorate path. First definition wins."""
    out = {}
    for f in sorted(os.listdir(root)):
        if not f.lower().endswith(".txt"):
            continue
        path = os.path.join(root, f)
        with open(path, "r", encoding="latin-1") as fh:
            for line in fh:
                m = D._ACTOR.match(line.strip())
                if m:
                    out.setdefault(m.group("name").lower(), path)
    return out


def resolve(stem: str, md3: str, modeldefs: dict, actors: dict):
    """Every (donor, modeldef, class, decorate) that binds consistently."""
    wins, tried = [], []
    for path, blocks in modeldefs.items():
        hits = D.blocks_for_md3(blocks, os.path.basename(md3))
        for name in sorted({b.name for b in hits if b.name}):
            decorate = actors.get(name.lower())
            if not decorate:
                tried.append(f"{os.path.basename(path)}:{name} (no such actor)")
                continue
            rel = os.path.relpath(md3, DONORS)
            try:
                d = D.read_donor(stem, DONORS, rel, path, decorate, actor=name)
            except D.DonorError as e:
                tried.append(f"{os.path.basename(path)}:{name} ({str(e)[:70]})")
                continue
            wins.append(d)
    return wins, tried


def main() -> int:
    if not os.path.isdir(DONORS):
        print(f"FAIL: donor pack not found at {DONORS}")
        return 1

    md3s = find_md3s(DONORS)
    modeldefs = parse_all_modeldefs(DONORS)
    actors = index_actors(DONORS)
    print(f"{len(md3s)} MD3s, {len(modeldefs)} MODELDEFs, {len(actors)} actors in the pack\n")

    failures = []
    print(f"{'donor':17}{'sprite':8}{'want':>5}{'got':>5}   binding")
    for stem, sprite, letter, want in EXPECTED:
        md3 = md3s.get(stem.lower())
        if not md3:
            failures.append(f"{stem}: no MD3 in the donor pack")
            print(f"{stem:17}{'-':8}{want:>5}{'-':>5}   MD3 NOT FOUND")
            continue

        wins, tried = resolve(stem, md3, modeldefs, actors)
        distinct = {(d.rest_frame, d.ready.sprite, d.ready.letter) for d in wins}
        if not wins:
            failures.append(f"{stem}: nothing bound. Tried: {tried[:4]}")
            print(f"{stem:17}{'-':8}{want:>5}{'-':>5}   NO BINDING")
            for t in tried[:4]:
                print(f"     tried {t}")
            continue
        if len(distinct) > 1:
            failures.append(f"{stem}: {len(distinct)} different answers from "
                            f"{[(d.block.name, os.path.basename(d.modeldef)) for d in wins]}")
            print(f"{stem:17}{'-':8}{want:>5}{'-':>5}   AMBIGUOUS {sorted(distinct)}")
            continue

        d = wins[0]
        ok = (d.rest_frame == want)
        sprite_ok = (d.ready.sprite == sprite and d.ready.letter == letter)
        if not ok:
            failures.append(f"{stem}: rest frame {d.rest_frame}, the table says {want}")
        if not sprite_ok:
            failures.append(f"{stem}: Ready sprite {d.ready.sprite} {d.ready.letter}, "
                            f"the table says {sprite} {letter}")
        mark = "ok " if (ok and sprite_ok) else "BAD"
        print(f"{stem:17}{d.ready.sprite + ' ' + d.ready.letter:8}{want:>5}{d.rest_frame:>5}   "
              f"{mark} {d.block.name} in {os.path.basename(d.modeldef)} + "
              f"{os.path.basename(d.decorate)}")

    # The revolver: BD 1.01 has no Ready state for it, so R1 cannot answer and
    # the tool must say so rather than hand back frame 0.
    for stem in MUST_RAISE:
        md3 = md3s.get(stem.lower())
        if not md3:
            print(f"{stem:17}{'-':8}{'raise':>5}{'-':>5}   ok  not in the pack at all")
            continue
        wins, tried = resolve(stem, md3, modeldefs, actors)
        if wins:
            d = wins[0]
            failures.append(f"{stem}: resolved to frame {d.rest_frame} via {d.block.name}, "
                            f"but BD 1.01 has no Ready state for it -- it must raise")
            print(f"{stem:17}{d.ready.sprite:8}{'raise':>5}{d.rest_frame:>5}   BAD did not raise")
        else:
            print(f"{stem:17}{'-':8}{'raise':>5}{'-':>5}   ok  refused, as it must")
            for t in tried[:2]:
                print(f"     {t}")

    if failures:
        print(f"\nFAIL: {len(failures)} problem(s)")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"\nPASS: {len(EXPECTED)} rest frames reproduced from the donor files; "
          f"{len(MUST_RAISE)} refused as it must")
    return 0


if __name__ == "__main__":
    sys.exit(main())
