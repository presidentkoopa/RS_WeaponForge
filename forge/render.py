#!/usr/bin/env python3
"""
render.py -- look at the mesh. Three orthographic views of a surface, with a
chosen set of vertices picked out in a second colour.

    python -m forge.render <set> <gun> [--surface N] [--out FILE.png]

WHY THIS EXISTS. A carve can be checked two ways: against a number, or by
looking at it. Numbers caught a great deal in this tool -- a magazine measured
along the wrong axis, a pivot quoted in the wrong space -- but they cannot say
whether the lump a search just found IS the magazine. Two different cuts of the
same machinegun came out at exactly 415 vertices each and shared only 225 of
them; no count separates those. A picture does.

Panels: TOP (x right, y up), SIDE (x right, z up), FRONT (y right, z up), each
to the same scale, with the axes through the origin in grey. Vertices in the
highlight set are drawn over the rest, so a proposed carve can be seen sitting
in the gun it came out of.
"""

from __future__ import annotations

import os
import sys
from typing import Iterable, Optional, Sequence, Set

try:
    from PIL import Image, ImageDraw
except ImportError:                                     # pragma: no cover
    Image = ImageDraw = None

BG = (16, 16, 20)
AXIS = (70, 70, 80)
MESH = (120, 130, 145)
PICK = (255, 120, 40)
LABEL = (200, 200, 210)


def _panel(draw, ox: int, oy: int, size: int, pts, tris, ax: int, ay: int,
           picked: Set[int], scale: float, centre, title: str) -> None:
    def to_screen(p):
        return (ox + size / 2 + (p[ax] - centre[ax]) * scale,
                oy + size / 2 - (p[ay] - centre[ay]) * scale)

    zero = to_screen([0.0, 0.0, 0.0])
    draw.line([(ox, zero[1]), (ox + size, zero[1])], fill=AXIS)
    draw.line([(zero[0], oy), (zero[0], oy + size)], fill=AXIS)
    draw.rectangle([ox, oy, ox + size, oy + size], outline=AXIS)
    draw.text((ox + 6, oy + 4), title, fill=LABEL)

    # The unpicked mesh first, as wireframe; then the picked vertices on top, so a
    # small part inside a big body is still visible.
    for a, b, c in tris:
        if picked and (a in picked or b in picked or c in picked):
            continue
        pa, pb, pc = to_screen(pts[a]), to_screen(pts[b]), to_screen(pts[c])
        draw.line([pa, pb, pc, pa], fill=MESH)
    for a, b, c in tris:
        if not picked or not (a in picked and b in picked and c in picked):
            continue
        pa, pb, pc = to_screen(pts[a]), to_screen(pts[b]), to_screen(pts[c])
        draw.line([pa, pb, pc, pa], fill=PICK)


def render_surface(pts: Sequence[Sequence[float]], tris: Sequence[Sequence[int]],
                   out: str, picked: Optional[Iterable[int]] = None,
                   title: str = "", size: int = 460) -> str:
    """Three views of one surface's vertices and triangles."""
    if Image is None:
        raise RuntimeError("rendering needs Pillow: python -m pip install pillow")
    picked = set(picked or ())
    lo = [min(p[a] for p in pts) for a in range(3)]
    hi = [max(p[a] for p in pts) for a in range(3)]
    centre = [(lo[a] + hi[a]) / 2 for a in range(3)]
    span = max(hi[a] - lo[a] for a in range(3)) or 1.0
    scale = (size * 0.86) / span

    img = Image.new("RGB", (size * 3 + 40, size + 40), BG)
    draw = ImageDraw.Draw(img)
    for i, (ax, ay, name) in enumerate(((0, 1, "TOP  x right, y up"),
                                        (0, 2, "SIDE  x right, z up"),
                                        (1, 2, "FRONT  y right, z up"))):
        _panel(draw, 10 + i * (size + 10), 30, size, pts, tris, ax, ay, picked,
               scale, centre, name)
    if title:
        draw.text((12, 10), title, fill=LABEL)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out)
    return out


def render_gun(set_path: str, gun_id: str, surface: Optional[int] = None,
               out: Optional[str] = None, picked: Optional[Iterable[int]] = None,
               title: str = "") -> str:
    """One gun's donor surface, straight out of the set file."""
    from . import donor as D
    from . import md3 as MD3
    from . import setfile as SF

    sf = SF.load_set(set_path)
    gun = sf.guns[gun_id]
    d = D.read_donor(gun_id, sf.donor_root, gun.donor, gun.modeldef, gun.decorate,
                     rest_frame=gun.rest_frame, actor=gun.actor)
    model = MD3.MD3Model.load(d.md3)
    idx = surface if surface is not None else (gun.body if gun.body is not None else 0)
    surf = model.surfaces[idx]
    out = out or os.path.join(os.path.dirname(set_path), "proposals",
                              f"{gun_id}_surface{idx}.png")
    return render_surface(surf.verts[d.rest_frame], surf.triangles, out, picked,
                          title or f"{sf.set_id} {gun_id} surface #{idx} "
                                   f"'{surf.name}' at frame {d.rest_frame}")


def main(argv: Sequence[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    set_name, gun_id = argv[1], argv[2]
    set_path = set_name
    if not os.path.isfile(set_path):
        set_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "sets", set_name, "set.py")
    surface = None
    if "--surface" in argv:
        surface = int(argv[argv.index("--surface") + 1])
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    print(render_gun(set_path, gun_id, surface, out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
