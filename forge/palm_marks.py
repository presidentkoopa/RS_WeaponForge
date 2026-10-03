#!/usr/bin/env python3
"""
palm_marks.py -- add the TRIGGER and a seeded SUPPORT point to an existing palmbench bundle.

Patches geometry.json in place rather than re-rendering: the pictures do not change, only the
markers the page starts you on. Run it after palm_render.py.

THE TRIGGER comes from the mesh itself wherever the mesh says where it is -- an MD3 surface
named for the trigger, or a rigged gun's own trigger bone at the frame it is drawn. Guessing
is worse than leaving it unset, so a gun with neither gets nothing and the page starts its
trigger mark at the palm for you to drag.

THE SUPPORT is seeded, never decided: the owner's own measured boxes first (twelve BD22 guns
have them and nothing has ever read them), then the forge's estimate, and failing both the
plan's mesh rule -- 0.60 of the way from palm to muzzle, held between 15 and 50 cm ahead of
the palm, dropped to the underside of the mesh there. The page is where it gets decided.

    python forge/palm_marks.py --bundle palmbench/geometry.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forge import iqm as IQM          # noqa: E402
from forge import md3 as MD3          # noqa: E402

ROOT = r"E:\DOOMWork"
CSV_DEFAULT = os.path.join(ROOT, "_reports", "gun_seating_2026-10-02", "WEAPON_SETS.csv")
TRIGGER_WORDS = ("trigger",)
NOT_TRIGGER = ("triggerguard", "trigger_guard", "guard")


def triple(s: str) -> Optional[List[float]]:
    p = [x for x in (s or "").strip().replace(",", " ").split() if x]
    if len(p) != 3:
        return None
    try:
        return [float(x) for x in p]
    except ValueError:
        return None


def is_trigger(name: str) -> bool:
    low = name.lower()
    if not any(w in low for w in TRIGGER_WORDS):
        return False
    return not any(w in low.replace(" ", "") for w in NOT_TRIGGER)


def md3_trigger(path: str, frame: int) -> Optional[List[float]]:
    model = MD3.MD3Model.load(path)
    for surf in model.surfaces:
        if is_trigger(surf.name):
            f = min(frame, surf.num_frames - 1) if surf.num_frames else 0
            v = np.asarray(surf.verts[f], dtype=np.float64)
            if len(v):
                return [round(float(x), 3) for x in v.mean(axis=0)]
    return None


def iqm_trigger(path: str, frame: int) -> Optional[List[float]]:
    m = IQM.IQMModel.load(path)
    for j in m.joints:
        if is_trigger(j.name):
            return [round(float(x), 3) for x in m.posed_joint(frame, j)]
    pv = m.posed_verts(frame)
    for mesh in m.meshes:
        if is_trigger(mesh.name):
            seg = pv[mesh.first_vertex:mesh.first_vertex + mesh.num_vertexes]
            if seg:
                a = np.asarray(seg, dtype=np.float64)
                return [round(float(x), 3) for x in a.mean(axis=0)]
    return None


def seed_support(gun: Dict, row: Dict) -> List[float]:
    """Where the off hand starts. Owner's boxes, then the forge, then the mesh rule."""
    for col in ("owner_support_centre", "auto_support_point"):
        t = triple(row.get(col, ""))
        if t:
            return [round(v, 3) for v in t]
    palm = gun["markers"].get("palm") or [0, 0, 0]
    muzzle = gun["markers"].get("muzzle")
    cm = gun.get("cm_per_unit") or 0.8
    lo, hi = gun["bbox"]
    if muzzle:
        reach = muzzle[0] - palm[0]
        ahead = 0.60 * reach
        lo_u, hi_u = 15.0 / cm, 50.0 / cm       # the plan's 15-50 cm band, in mesh units
        ahead = max(min(ahead, hi_u), min(lo_u, max(reach * 0.9, 0.0)))
        x = palm[0] + ahead
    else:
        x = (lo[0] + hi[0]) / 2
    x = max(lo[0], min(hi[0], x))
    # the bore line's height, which is where a handguard sits, not the grip's height
    z = muzzle[2] if muzzle else (lo[2] + hi[2]) / 2
    y = muzzle[1] if muzzle else 0.0
    return [round(x, 3), round(y, 3), round(z, 3)]


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--csv", default=CSV_DEFAULT)
    ap.add_argument("--root", default=ROOT)
    a = ap.parse_args(argv)

    with open(a.csv, encoding="utf-8-sig") as f:
        rows = {r["weapon_class"].strip(): r for r in csv.DictReader(f)}
    with open(a.bundle, encoding="utf-8") as f:
        bundle = json.load(f)

    found = seeded = 0
    for w, gun in bundle["guns"].items():
        row = rows.get(w, {})
        path = os.path.join(a.root, row.get("mesh", "").replace("/", os.sep))
        frame = gun.get("frame", 0)
        trig = None
        if os.path.isfile(path):
            try:
                trig = iqm_trigger(path, frame) if gun["format"] == "IQM" \
                    else md3_trigger(path, frame)
            except Exception:                                    # noqa: BLE001
                trig = None
        gun["markers"]["trigger"] = trig
        gun["markers"]["support_seed"] = seed_support(gun, row)
        if trig:
            found += 1
        seeded += 1

    with open(a.bundle, "w", encoding="utf-8") as f:
        json.dump(bundle, f, separators=(",", ":"))
    print(f"{seeded} guns patched; trigger found on {found}, "
          f"{seeded-found} start their trigger mark at the palm")
    print(f"{a.bundle}  {os.path.getsize(a.bundle)/1048576:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
