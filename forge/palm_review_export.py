#!/usr/bin/env python3
"""
palm_review_export.py -- the geometry the owner looks at when he places 78 palm points.

WHY A PAGE AND NOT A PICTURE. Every palm point in WEAPON_SETS.csv was derived by a program
and then read back by the same program's own quality columns. Eight of the forty-seven the
report calls good have a palm the mesh does not wrap -- two with no measured handle
cross-section at all -- and nothing in the numbers says so until you ask for enclosure
specifically. Nobody has LOOKED at any of the seventy-eight. This exports what is needed to
look at all of them, and to click the answer rather than type it.

WHAT IT WRITES, per gun, into --out:
    <weapon>.json   downsampled gun geometry in mesh units, plus every marker worth seeing
and one index.json listing the guns in review order, worst verdict first.

THE GEOMETRY IS WHAT THE ENGINE DRAWS, which for the ten IQM guns is not the bind pose:
the five Breach rifles draw at frame 25 of 360, the MP5 at 109, the Benelli at 59. At the
bind pose their right wrist sits above the receiver where no hand could be. Posed geometry
reproduces the report's own bounding boxes and vertex counts exactly on eight of the ten;
the other two differ only by a suppressor held in extra_models and a loose ejecting shell,
neither of which is near a grip.

DOWNSAMPLING. A point cloud is voxel-reduced to about 200 cells across the gun's longest
axis, which keeps a handle's profile legible while bringing a 36,000-vertex rifle down to
something a browser can draw instantly. The palm is judged on the handle's SHAPE, and that
survives the reduction; nothing measured is taken from the reduced cloud.

    python forge/palm_review_export.py --out ..\\_reports\\palmreview
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forge import iqm as IQM          # noqa: E402
from forge import md3 as MD3          # noqa: E402

ROOT = r"E:\DOOMWork"
CSV_DEFAULT = os.path.join(ROOT, "_reports", "gun_seating_2026-10-02", "WEAPON_SETS.csv")

# Worst first: the owner's attention is worth most where the data is weakest.
VERDICT_ORDER = ["GROSS", "WRONG", "N/A", "UNSURE", "LATERAL", "STOCK-WRIST", "LOW", "OK"]

# Loose ammunition that is modelled in flight rather than as part of the gun. Cartridges
# sitting IN a magazine are part of the gun and are NOT named here.
LOOSE = ("shell.bmp",)


def triple(s: str) -> Optional[List[float]]:
    parts = [p for p in (s or "").strip().replace(",", " ").split() if p]
    if len(parts) != 3:
        return None
    try:
        return [float(p) for p in parts]
    except ValueError:
        return None


def voxel_reduce(pts: Sequence[Sequence[float]], cells: int = 200
                 ) -> List[Tuple[float, float, float]]:
    """One point per occupied cell of a grid `cells` across the longest axis."""
    if not pts:
        return []
    lo = [min(p[a] for p in pts) for a in range(3)]
    hi = [max(p[a] for p in pts) for a in range(3)]
    span = max(hi[a] - lo[a] for a in range(3)) or 1.0
    step = span / max(cells, 1)
    seen = {}
    for p in pts:
        key = (int((p[0] - lo[0]) / step), int((p[1] - lo[1]) / step), int((p[2] - lo[2]) / step))
        if key not in seen:
            seen[key] = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
    return list(seen.values())


# ---- the two loaders ------------------------------------------------------------------

def load_md3(path: str, frame: int, hidden: str) -> List[Tuple[float, float, float]]:
    model = MD3.MD3Model.load(path)
    skip = {h.strip().lower() for h in (hidden or "").split(",") if h.strip()}
    out: List[Tuple[float, float, float]] = []
    for surf in model.surfaces:
        if surf.name.lower() in skip:
            continue
        f = min(frame, surf.num_frames - 1) if surf.num_frames else 0
        out.extend(surf.verts[f])
    return out


def load_iqm(path: str, frame: int) -> Tuple[List[Tuple[float, float, float]],
                                             Dict[str, List[float]]]:
    """Posed gun geometry, and the posed right-hand joints worth marking."""
    m = IQM.IQMModel.load(path)
    pv = m.posed_verts(frame)
    keep = m.gun_vertex_indices(frame)
    loose = set()
    for mesh in m.meshes:
        if mesh.name.lower() in LOOSE:
            loose.update(range(mesh.first_vertex, mesh.first_vertex + mesh.num_vertexes))
    pts = [pv[i] for i in keep if i not in loose]

    joints: Dict[str, List[float]] = {}
    wrist = m.hand_joint("r")
    if wrist is not None:
        joints["wrist_r"] = [round(v, 3) for v in m.posed_joint(frame, wrist)]
    # The knuckles: the base of index, ring and pinky. Their centroid is the palm's
    # centre far better than the wrist is, and the thumb is deliberately left out --
    # thumb joints are inconsistent between these rigs.
    knuckles = []
    for finger in ("index", "ring", "pinky"):
        j = m.joint(f"{finger}_ri_1") or m.joint(finger, "_ri")
        if j is not None:
            p = m.posed_joint(frame, j)
            knuckles.append(p)
            joints[f"{finger}_r"] = [round(v, 3) for v in p]
    if knuckles:
        joints["knuckles_r"] = [round(sum(k[a] for k in knuckles) / len(knuckles), 3)
                                for a in range(3)]
    return pts, joints


# ---- main ----------------------------------------------------------------------------

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="export gun geometry for the palm review page")
    ap.add_argument("--csv", default=CSV_DEFAULT)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--out", required=True, help="directory for the per-gun json")
    ap.add_argument("--cells", type=int, default=200, help="downsample grid across the gun")
    ap.add_argument("--only", default="", help="comma-separated weapon classes")
    a = ap.parse_args(argv)

    with open(a.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    only = {w.strip() for w in a.only.split(",") if w.strip()}
    if only:
        rows = [r for r in rows if r["weapon_class"].strip() in only]

    os.makedirs(a.out, exist_ok=True)
    index: List[Dict] = []
    failed: List[str] = []

    for r in rows:
        weapon = r["weapon_class"].strip()
        path = os.path.join(a.root, r["mesh"].replace("/", os.sep))
        fmt = r["mesh_format"].strip()
        try:
            frame = int(r["draw_frame"] or 0)
        except ValueError:
            frame = 0
        joints: Dict[str, List[float]] = {}
        try:
            if fmt == "IQM":
                pts, joints = load_iqm(path, frame)
            else:
                pts = load_md3(path, frame, r.get("hidden", ""))
        except Exception as e:                                   # noqa: BLE001
            failed.append(f"{weapon}: {type(e).__name__}: {e}")
            continue
        if not pts:
            failed.append(f"{weapon}: no geometry after hiding surfaces")
            continue

        full = len(pts)
        pts = voxel_reduce(pts, a.cells)
        lo = [round(min(p[i] for p in pts), 3) for i in range(3)]
        hi = [round(max(p[i] for p in pts), 3) for i in range(3)]

        try:
            cmpu = float(r["cm_per_mesh_unit"])
        except (KeyError, TypeError, ValueError):
            cmpu = 0.0

        gun = {
            "weapon": weapon,
            "set": r["set"].strip(),
            "type": r["card_type"].strip(),
            "verdict": r["inspection"].strip(),
            "note": r["inspection_note"].strip(),
            "card": r["card"].strip(),
            "mesh": r["mesh"].strip(),
            "format": fmt,
            "frame": frame,
            "cm_per_unit": cmpu,
            "bbox": [lo, hi],
            "points": [c for p in pts for c in p],      # flat, x y z x y z ...
            "n_points": len(pts),
            "n_full": full,
            "markers": {
                "palm": triple(r["palm_point"]),
                "seat": triple(r["card_seat"]),
                "muzzle": triple(r["card_muzzle"]),
                "butt": triple(r["butt_point"]),
                "support": triple(r["auto_support_point"]),
                "owner_support": triple(r["owner_support_centre"]),
            },
            "joints": joints,
            "quality": {
                "dist_cm": r["palm_dist_to_mesh_cm"].strip(),
                "enclosure": r["palm_enclosure"].strip(),
                "section_cm": r["palm_section_cm"].strip(),
                "lateral_cm": r["palm_lateral_off_cm"].strip(),
            },
        }
        with open(os.path.join(a.out, f"{weapon}.json"), "w", encoding="utf-8") as f:
            json.dump(gun, f, separators=(",", ":"))

        index.append({
            "weapon": weapon, "set": gun["set"], "type": gun["type"],
            "verdict": gun["verdict"], "format": fmt,
            "enclosure": gun["quality"]["enclosure"],
            "dist_cm": gun["quality"]["dist_cm"],
            "has_palm": gun["markers"]["palm"] is not None,
            "n_points": len(pts),
        })

    def rank(e):
        v = e["verdict"].upper()
        return (VERDICT_ORDER.index(v) if v in VERDICT_ORDER else 99, e["weapon"])

    index.sort(key=rank)
    with open(os.path.join(a.out, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"guns": index, "count": len(index)}, f, indent=1)

    total = sum(os.path.getsize(os.path.join(a.out, f))
                for f in os.listdir(a.out) if f.endswith(".json"))
    print(f"{len(index)} guns exported to {a.out}  ({total/1048576:.2f} MB total)")
    for e in index[:12]:
        print(f"  {e['verdict']:12} {e['weapon']:22} {e['format']:4} "
              f"{e['n_points']:6} pts  enclosure {e['enclosure'] or '-'}")
    if failed:
        print("\nFAILED:")
        for l in failed:
            print(f"  {l}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
