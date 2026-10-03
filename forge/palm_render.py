#!/usr/bin/env python3
"""
palm_render.py -- draw each gun as a SOLID SHADED OBJECT, so it can be recognised.

WHY THIS REPLACES A POINT CLOUD. The first attempt at this page shipped vertices and drew
them as dots. A gun drawn as dots is unreadable: a grip, a magazine and a trigger guard are
all the same grey speckle, and nobody can place a palm on a shape they cannot make out. The
mesh has triangles; this uses them.

Two orthographic views per gun, sharing one scale and one x axis so they read together:
    SIDE    muzzle right, up is up      (camera on the gun's left, looking along +y)
    BELOW   muzzle right, across the gun (camera underneath, looking up)

Painter's algorithm with backface culling: triangles sorted far to near and filled, which is
exact for a solid opaque body and far faster than a z-buffer in Python. Lambert shading from
a fixed three-quarter light, plus a slight darkening with depth so the near side reads
forward. Greyscale, because every marker drawn over it is coloured and the gun must not
compete with them.

Each view records the orthographic window it was drawn with, so a click in the page converts
back to mesh units exactly -- the picture and the coordinates cannot drift apart.

    python forge/palm_render.py --out ..\\WeaponForge\\palmbench
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forge import iqm as IQM          # noqa: E402
from forge import md3 as MD3          # noqa: E402

ROOT = r"E:\DOOMWork"
CSV_DEFAULT = os.path.join(ROOT, "_reports", "gun_seating_2026-10-02", "WEAPON_SETS.csv")
VERDICT_ORDER = ["GROSS", "WRONG", "N/A", "UNSURE", "LATERAL", "STOCK-WRIST", "LOW", "OK"]
LOOSE = ("shell.bmp",)

WIDTH = 1040          # the drawn width of both views
PAD = 18
LIGHT = np.array([0.45, -0.72, 0.52])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def triple(s: str) -> Optional[List[float]]:
    p = [x for x in (s or "").strip().replace(",", " ").split() if x]
    if len(p) != 3:
        return None
    try:
        return [float(x) for x in p]
    except ValueError:
        return None


# ---- geometry in, triangles and all ----------------------------------------------------

def load_md3(path: str, frame: int, hidden: str):
    model = MD3.MD3Model.load(path)
    skip = {h.strip().lower() for h in (hidden or "").split(",") if h.strip()}
    verts: List[Tuple[float, float, float]] = []
    tris: List[Tuple[int, int, int]] = []
    for surf in model.surfaces:
        if surf.name.lower() in skip:
            continue
        base = len(verts)
        f = min(frame, surf.num_frames - 1) if surf.num_frames else 0
        verts.extend(surf.verts[f])
        tris.extend((a + base, b + base, c + base) for a, b, c in surf.triangles)
    return verts, tris, {}


def load_iqm(path: str, frame: int):
    m = IQM.IQMModel.load(path)
    pv = m.posed_verts(frame)
    keep = set(m.gun_vertex_indices(frame))
    for mesh in m.meshes:
        if mesh.name.lower() in LOOSE:
            keep -= set(range(mesh.first_vertex, mesh.first_vertex + mesh.num_vertexes))
    remap = {}
    verts: List[Tuple[float, float, float]] = []
    for i in sorted(keep):
        remap[i] = len(verts)
        verts.append(pv[i])
    tris = [(remap[a], remap[b], remap[c]) for a, b, c in m.triangles
            if a in remap and b in remap and c in remap]

    joints: Dict[str, List[float]] = {}
    w = m.hand_joint("r")
    if w is not None:
        joints["wrist_r"] = [round(v, 3) for v in m.posed_joint(frame, w)]
    knuckles = []
    for finger in ("index", "ring", "pinky"):
        j = m.joint(f"{finger}_ri_1") or m.joint(finger, "_ri")
        if j is not None:
            knuckles.append(m.posed_joint(frame, j))
    if knuckles:
        joints["knuckles_r"] = [round(sum(k[a] for k in knuckles) / len(knuckles), 3)
                                for a in range(3)]
    return verts, tris, joints


# ---- the rasteriser --------------------------------------------------------------------

def render_view(V: np.ndarray, T: np.ndarray, ax: int, ay: int, depth_ax: int,
                depth_sign: float, lo, hi, scale: float) -> Tuple[Image.Image, Dict]:
    """One orthographic view, painted far to near with backface culling."""
    span_y = max(hi[ay] - lo[ay], 1e-6)
    h = int(round(span_y * scale)) + 2 * PAD
    h = max(h, 110)
    img = Image.new("L", (WIDTH, h), 18)
    dr = ImageDraw.Draw(img)

    cx = (lo[ax] + hi[ax]) / 2.0
    cy = (lo[ay] + hi[ay]) / 2.0
    ox, oy = WIDTH / 2.0, h / 2.0

    px = ox + (V[:, ax] - cx) * scale
    py = oy - (V[:, ay] - cy) * scale
    pd = V[:, depth_ax] * depth_sign

    if len(T) == 0:
        return img, {}

    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    # screen-space winding tells us which faces point away
    area = (px[b] - px[a]) * (py[c] - py[a]) - (px[c] - px[a]) * (py[b] - py[a])
    front = area < 0
    if front.sum() < len(T) * 0.05:          # a model wound the other way
        front = area > 0
    idx = np.nonzero(front)[0]
    if len(idx) == 0:
        idx = np.arange(len(T))

    e1 = V[T[idx, 1]] - V[T[idx, 0]]
    e2 = V[T[idx, 2]] - V[T[idx, 0]]
    n = np.cross(e1, e2)
    ln = np.linalg.norm(n, axis=1)
    ln[ln == 0] = 1.0
    n = n / ln[:, None]
    lam = np.abs(n @ LIGHT)

    dmid = (pd[a[idx]] + pd[b[idx]] + pd[c[idx]]) / 3.0
    dlo, dhi = float(dmid.min()), float(dmid.max())
    drange = max(dhi - dlo, 1e-6)
    near = (dmid - dlo) / drange                      # 0 far .. 1 near

    shade = 46 + 150 * lam + 48 * near
    shade = np.clip(shade, 26, 246).astype(np.int16)

    order = np.argsort(dmid)                          # far first
    polys = np.stack([px[T[idx, 0]], py[T[idx, 0]],
                      px[T[idx, 1]], py[T[idx, 1]],
                      px[T[idx, 2]], py[T[idx, 2]]], axis=1)
    poly_l = polys.tolist()
    sh_l = shade.tolist()
    for k in order:
        p = poly_l[k]
        dr.polygon([(p[0], p[1]), (p[2], p[3]), (p[4], p[5])], fill=sh_l[k])

    window = {"ax": ax, "ay": ay, "w": WIDTH, "h": h,
              "cx": round(cx, 5), "cy": round(cy, 5), "s": round(scale, 6),
              "ox": round(ox, 3), "oy": round(oy, 3)}
    return img, window


def png_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# ---- cross-sections, precomputed -------------------------------------------------------

def sections(V: np.ndarray, lo, hi, n: int = 72, keep: int = 150):
    """At n stations along the barrel, the mesh's (y, z) points in that slab. Small enough
    to ship, dense enough to judge whether a hand closes."""
    x0, x1 = lo[0], hi[0]
    step = max((x1 - x0) / n, 1e-6)
    half = step * 0.9
    out = []
    for i in range(n):
        xc = x0 + (i + 0.5) * step
        m = np.abs(V[:, 0] - xc) <= half
        pts = V[m][:, 1:3]
        if len(pts) > keep:
            sel = np.linspace(0, len(pts) - 1, keep).astype(int)
            pts = pts[sel]
        out.append([round(float(v), 2) for p in pts for v in p])
    return {"x0": round(float(x0), 4), "step": round(float(step), 5), "n": n, "slices": out}


# ---- main ------------------------------------------------------------------------------

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="solid shaded gun renders for the palm page")
    ap.add_argument("--csv", default=CSV_DEFAULT)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)

    with open(a.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    only = {w.strip() for w in a.only.split(",") if w.strip()}
    if only:
        rows = [r for r in rows if r["weapon_class"].strip() in only]

    os.makedirs(a.out, exist_ok=True)
    guns: Dict[str, Dict] = {}
    index: List[Dict] = []
    failed: List[str] = []

    for r in rows:
        w = r["weapon_class"].strip()
        path = os.path.join(a.root, r["mesh"].replace("/", os.sep))
        fmt = r["mesh_format"].strip()
        try:
            frame = int(r["draw_frame"] or 0)
        except ValueError:
            frame = 0
        try:
            if fmt == "IQM":
                verts, tris, joints = load_iqm(path, frame)
            else:
                verts, tris, joints = load_md3(path, frame, r.get("hidden", ""))
            if not verts or not tris:
                raise ValueError("no triangles")
            V = np.asarray(verts, dtype=np.float64)
            T = np.asarray(tris, dtype=np.int64)
            lo = V.min(axis=0)
            hi = V.max(axis=0)
            scale = (WIDTH - 2 * PAD) / max(hi[0] - lo[0], 1e-6)

            side, wside = render_view(V, T, 0, 2, 1, 1.0, lo, hi, scale)
            below, wbelow = render_view(V, T, 0, 1, 2, -1.0, lo, hi, scale)

            try:
                cmpu = float(r["cm_per_mesh_unit"])
            except (KeyError, TypeError, ValueError):
                cmpu = 0.0

            guns[w] = {
                "weapon": w, "set": r["set"].strip(), "type": r["card_type"].strip(),
                "verdict": r["inspection"].strip(), "note": r["inspection_note"].strip(),
                "format": fmt, "frame": frame, "cm_per_unit": cmpu,
                "bbox": [[round(float(v), 4) for v in lo], [round(float(v), 4) for v in hi]],
                "side": {"img": png_b64(side), **wside},
                "below": {"img": png_b64(below), **wbelow},
                "sec": sections(V, lo, hi),
                "markers": {
                    "palm": triple(r["palm_point"]), "seat": triple(r["card_seat"]),
                    "muzzle": triple(r["card_muzzle"]), "butt": triple(r["butt_point"]),
                    "support": triple(r["auto_support_point"]),
                },
                "joints": joints,
                "quality": {"dist_cm": r["palm_dist_to_mesh_cm"].strip(),
                            "enclosure": r["palm_enclosure"].strip(),
                            "section_cm": r["palm_section_cm"].strip()},
                "tris": len(tris),
            }
            index.append({"weapon": w, "set": guns[w]["set"], "verdict": guns[w]["verdict"],
                          "format": fmt, "enclosure": guns[w]["quality"]["enclosure"]})
            print(f"  {w:22} {fmt:4} {len(tris):7} tris  side {wside['w']}x{wside['h']}"
                  f"  below {wbelow['w']}x{wbelow['h']}")
        except Exception as e:                                   # noqa: BLE001
            failed.append(f"{w}: {type(e).__name__}: {e}")

    index.sort(key=lambda e: (VERDICT_ORDER.index(e["verdict"].upper())
                              if e["verdict"].upper() in VERDICT_ORDER else 99, e["weapon"]))
    bundle = {"order": [e["weapon"] for e in index], "index": index, "guns": guns}
    p = os.path.join(a.out, "geometry.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(bundle, f, separators=(",", ":"))
    print(f"\n{len(guns)} guns -> {p}  ({os.path.getsize(p)/1048576:.2f} MB)")
    if failed:
        print("FAILED:")
        for l in failed:
            print("  " + l)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
