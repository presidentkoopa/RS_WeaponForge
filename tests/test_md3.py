#!/usr/bin/env python3
"""
test_md3.py -- step 2's done-check: forge/md3.py round-trips with zero
differences.

Read, write, read again, and compare surface names, surface order, triangle
lists, UVs and every vertex of every frame. Zero differences, not "within
tolerance": a position read out of an MD3 is already an exact multiple of
1/64, so writing it back is exact arithmetic. Anything nonzero here is a bug
in the reader or the writer, and every later step -- the recentring of R2, the
measurements of step 7 -- is built on top of this file.

The three files are the ones the guide names, chosen because they cover what
breaks: a mesh this project already ships (smg_wm.md3, one frame), a long
animation (Rifle.md3, 32 frames), and an untouched donor straight out of
Brutal Doom (Shotgun.md3, 36 frames).

    python tests/test_md3.py
"""

from __future__ import annotations

import os
import sys
import tempfile

# Surface names carry high bytes (the BD Rifle's sight is 'tahtain' with two
# a-umlauts). A Windows console is cp1252 and raises on them, which would turn
# a reported difference into a traceback and hide the real result.
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from forge import md3   # noqa: E402

WEAPONS = r"E:\DOOMWork\RS_VR_Weapons"
DONORS = r"D:\SteamLibrary\steamapps\Common\DooM VR\__Games\BrutalDoom\_BD_1.01_WeaponModels"

CASES = [
    # path, expected frames (None = whatever the file says)
    (os.path.join(WEAPONS, r"models\vanilla\smgs\SMG\smg_wm.md3"), None),
    (os.path.join(WEAPONS, r"models\vanilla\rifles\Rifle\Rifle.md3"), 32),
    (os.path.join(DONORS, r"Models\Weapons\Hud\Shotgun\Shotgun.md3"), 36),
]


def compare(a: md3.MD3Model, b: md3.MD3Model, label: str) -> list:
    """Every difference between two models, as lines. Empty means identical."""
    bad = []

    def note(msg):
        bad.append(f"{label}: {msg}")

    if a.num_frames != b.num_frames:
        note(f"frame count {a.num_frames} -> {b.num_frames}")
    if len(a.surfaces) != len(b.surfaces):
        note(f"surface count {len(a.surfaces)} -> {len(b.surfaces)}")
        return bad

    # Surface ORDER as well as names: a reader that sorts them, or a writer
    # that emits them in dict order, silently renumbers every #N index that
    # set.py addresses parts by.
    names_a = [s.name for s in a.surfaces]
    names_b = [s.name for s in b.surfaces]
    if names_a != names_b:
        note(f"surface names/order {names_a} -> {names_b}")
        return bad

    for sa, sb in zip(a.surfaces, b.surfaces):
        where = f"surface {sa.index} ('{sa.name}')"
        if sa.triangles != sb.triangles:
            n = sum(1 for x, y in zip(sa.triangles, sb.triangles) if x != y)
            note(f"{where}: {n} of {len(sa.triangles)} triangles differ")
        if len(sa.st) != len(sb.st):
            note(f"{where}: UV count {len(sa.st)} -> {len(sb.st)}")
        else:
            off = [i for i, (x, y) in enumerate(zip(sa.st, sb.st)) if x != y]
            if off:
                note(f"{where}: {len(off)} of {len(sa.st)} UVs differ, first at vertex {off[0]}")
        if [sh.name for sh in sa.shaders] != [sh.name for sh in sb.shaders]:
            note(f"{where}: shaders {[sh.name for sh in sa.shaders]} -> "
                 f"{[sh.name for sh in sb.shaders]}")
        if sa.num_frames != sb.num_frames:
            note(f"{where}: frames {sa.num_frames} -> {sb.num_frames}")
            continue
        worst = 0.0
        worst_at = None
        count = 0
        for f in range(sa.num_frames):
            for i, (va, vb) in enumerate(zip(sa.verts[f], sb.verts[f])):
                d = max(abs(va[k] - vb[k]) for k in range(3))
                if d > 0.0:
                    count += 1
                    if d > worst:
                        worst, worst_at = d, (f, i)
        if count:
            note(f"{where}: {count} vertices moved, worst {worst} at frame {worst_at[0]} "
                 f"vertex {worst_at[1]}")
        # Not part of the guide's check, but the reason normals are kept as raw
        # shorts: a re-encode that drifts shows up here and nowhere else.
        nbad = sum(1 for f in range(sa.num_frames)
                   for x, y in zip(sa.normals_packed[f], sb.normals_packed[f]) if x != y)
        if nbad:
            note(f"{where}: {nbad} packed normals changed")
    return bad


def main() -> int:
    tmpdir = tempfile.mkdtemp(prefix="weaponforge_md3_")
    failures = []
    for path, want_frames in CASES:
        label = os.path.basename(path)
        if not os.path.exists(path):
            failures.append(f"{label}: not found at {path}")
            print(f"FAIL {label}: not found at {path}")
            continue
        a = md3.MD3Model.load(path)
        if want_frames is not None and a.num_frames != want_frames:
            failures.append(f"{label}: expected {want_frames} frames, read {a.num_frames}")
        out = os.path.join(tmpdir, label)
        md3.write(a, out)
        b = md3.MD3Model.load(out)
        diffs = compare(a, b, label)
        verts = sum(s.num_verts for s in a.surfaces)
        if diffs:
            failures.extend(diffs)
            print(f"FAIL {label}: {len(diffs)} difference(s)")
            for d in diffs:
                print(f"     {d}")
        else:
            print(f"ok   {label:16} {a.num_frames:3} frames  {len(a.surfaces):3} surfaces  "
                  f"{verts:6} verts  identical after a round trip")
        # Byte identity is NOT required and is not checked: a source file may
        # carry padding, a different model name, or frame bounds its exporter
        # computed differently, and the writer recomputes all of those on
        # purpose. What must be identical is everything a reader gets back.
    if failures:
        print(f"\nFAIL: {len(failures)} problem(s)")
        return 1
    print("\nPASS: all three round-trip with zero differences")
    return 0


if __name__ == "__main__":
    sys.exit(main())
