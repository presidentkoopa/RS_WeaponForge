#!/usr/bin/env python3
"""
emit_mesh.py -- write the world-weapon mesh: one frame, recentred, renamed.
Step 6 of the WeaponForge Build Guide, rule R2.

R2: THE _wm.md3 IS THE REST FRAME, NEVER ROTATED. Take frame N (R1's rest
frame) and write it as frame 0. Translate every vertex by

    t = -round(centroid * 64) / 64

where centroid is the mean of all vertices of all surfaces at frame N. Never
rotate the mesh.

WHY RECENTRE. A donor viewmodel's origin is wherever its author left it, often
tens of units from the gun -- it does not matter for a HUD model, which is
placed by an offset anyway. A world object turns about its own origin, so a gun
whose origin sits behind its stock swings around a point in mid-air when the
hand rolls. Recentring puts the origin in the middle of the gun; R4 then gives
back the offset that returns it to where the donor sat in the hand, so nothing
is lost by moving it.

WHY THE 1/64. The shift is quantised to the MD3 grid before it is applied, so
the translation is exact in the format's own units and the mesh is not nudged by
a rounding error on the way out. Positions read out of an MD3 are already
multiples of 1/64; a shift that is also a multiple of 1/64 keeps them so.

WHY NEVER ROTATE. Every measurement in the card -- muzzle, eject port, slide
axis, hinge, feed axis -- is taken in this mesh's own space. Rotating the mesh
to "fix" how it sits in the hand silently invalidates all of them, and the
placement cvars exist to do that job instead. Rotating on the way out is how a
whole set ended up 45 degrees off.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from . import md3 as MD3

GRID = 64.0      # MD3 packs positions as int16 sixty-fourths of a map unit


@dataclass
class MeshResult:
    out: str
    rest_frame: int
    centroid: Tuple[float, float, float]
    t: Tuple[float, float, float]
    names: Dict[int, str] = field(default_factory=dict)   # donor index -> written name
    verts: int = 0
    surfaces: int = 0


def recentre_shift(model, rest_frame: int):
    """(centroid, t) for one frame: the mean of every vertex of every surface,
    and the quantised shift that moves it to the origin.

    Every surface, not only the body: the whole gun is being recentred, and a
    centroid taken from the body alone would move as soon as a set named a
    different surface as the body.
    """
    total = [0.0, 0.0, 0.0]
    n = 0
    for s in model.surfaces:
        for v in s.verts[rest_frame]:
            total[0] += v[0]
            total[1] += v[1]
            total[2] += v[2]
            n += 1
    if not n:
        raise ValueError(f"{model.source}: no vertices at frame {rest_frame}")
    centroid = tuple(c / n for c in total)
    t = tuple(-round(c * GRID) / GRID for c in centroid)
    return centroid, t


def islands(surf, frame: int = 0) -> List[List[int]]:
    """A surface's connected components, biggest first, as lists of vertex
    indices.

    A donor often packs two objects into one surface: the machinegun's
    11,996-vertex receiver holds its 415-vertex magazine, and the
    flamethrower's 5,966-vertex body holds its 1,306-vertex canister. They are
    separate objects sharing a surface, not one object, and a part cannot be
    driven until it is lifted out. Components are found through the triangle
    list -- two vertices belong together when a triangle joins them -- so this
    is the mesh's own answer, not a guess from positions.
    """
    n = len(surf.st)
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for (a, b, c) in surf.triangles:
        union(a, b)
        union(b, c)
    groups: Dict[int, List[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=len, reverse=True)


def islands_in_box(surf, frame: int, lo: Sequence[float], hi: Sequence[float],
                   shift: Sequence[float] = (0.0, 0.0, 0.0), tol: float = 1.0 / 64.0) -> List[int]:
    """Every vertex of every island that lies WHOLLY inside the box, with
    `shift` added to the surface's positions first (so a box may be quoted in
    _wm space, which is the space everything else the owner reads is in).

    WHOLE islands, never part of one: a box that cuts an island in half tears a
    mesh, leaving triangles with vertices in two different surfaces. Selecting by
    island keeps every object intact.

    THE BOX IS INCLUSIVE BY ONE QUANTUM (1/64), which is the mesh's own
    resolution. Without that slack a box quoted to three decimals drops the
    islands sitting exactly on its faces -- the machinegun's magazine came out
    415 vertices with the slack and 249 without it, from a box whose true bounds
    are -13.23438 and -5.59375. The margin is not delicate: anything from one
    quantum to 0.2 gives the same 415, because the magazine stands clear of the
    receiver. The count in the set file is what catches a box that is actually
    wrong.

    This is how the shipped machinegun was split. Its magazine is 415 of the
    receiver's 11,996 vertices, spread across 31 separate islands -- it is not
    one connected component, and 'the island containing the magazine' would have
    found 81 vertices of it. Every island wholly inside the magazine's own box
    is exactly those 415, with none missing and none extra.
    """
    import numpy as np
    pts = np.asarray(surf.verts[frame], dtype=float) + np.asarray(shift, dtype=float)
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    out: List[int] = []
    for group in islands(surf, frame):
        g = np.asarray(group, dtype=int)
        if bool(((pts[g] >= lo - tol) & (pts[g] <= hi + tol)).all()):
            out.extend(group)
    return sorted(out)


def resolve_island(surf, frame: int, spec: dict, shift: Sequence[float],
                   where: str = "") -> List[int]:
    """The vertices an island spec names, refusing the spec if the count is not
    what it claims.

    The count is the guard. A box written against one export of a mesh, or
    rounded a little too far, picks up a bolt from the receiver or drops a
    corner of the magazine, and nothing downstream would ever say so -- the part
    would simply be the wrong shape for the rest of the set's life.
    """
    if "box" not in spec:
        raise ValueError(f"{where}: an island needs a box; only a count was given")
    lo, hi = spec["box"]
    got = islands_in_box(surf, frame, lo, hi, shift)
    want = int(spec.get("verts", -1))
    if want >= 0 and len(got) != want:
        raise ValueError(f"{where}: the box holds {len(got)} vertices, the set file says {want}. "
                         f"Either the box is wrong or this is not the mesh it was written for.")
    return got


def split_surface(surf, vertex_ids: Sequence[int], name: str, frame: int = 0):
    """A new single-frame surface holding just those vertices and the triangles
    entirely within them, renumbered."""
    keep = sorted(set(vertex_ids))
    remap = {v: i for i, v in enumerate(keep)}
    tris = [tuple(remap[i] for i in t) for t in surf.triangles
            if all(i in remap for i in t)]
    out = MD3.MD3Surface(
        index=0, name=name, num_frames=1,
        shaders=[MD3.MD3Shader(name=sh.name, shader_index=0) for sh in surf.shaders]
                or [MD3.MD3Shader(name="", shader_index=0)],
        triangles=tris, st=[surf.st[v] for v in keep],
        verts=[[surf.verts[frame][v] for v in keep]],
        normals=[[surf.normals[frame][v] for v in keep]],
        normals_packed=[[surf.normals_packed[frame][v] for v in keep]]
                       if surf.normals_packed else [])
    return out


def surface_names(gun, n_surfaces: int) -> Dict[int, str]:
    """What each donor surface is called in the written mesh.

    The body is 'body'; a part's surfaces take the part's id; everything that
    only moves with the gun is 'fixed', 'fixed2', ...; anything drawn only
    mid-animation is 'hidden', 'hidden2', ... A part with more than one surface
    numbers them the same way. Names are made unique, because two surfaces
    sharing a name is how the donor got here in the first place -- the SMG's #0
    and #1 are both called Sights -- and the card addresses parts by name.
    """
    names: Dict[int, str] = {}
    used: Dict[str, int] = {}

    def take(stem: str) -> str:
        used[stem] = used.get(stem, 0) + 1
        return stem if used[stem] == 1 else f"{stem}{used[stem]}"

    if gun.body is not None:
        names[gun.body] = take("body")
    for pid, part in gun.parts.items():
        for idx in part.surfaces:
            names[idx] = take(pid)
    for idx in gun.fixed:
        names[idx] = take("fixed")
    for idx in gun.hidden:
        names[idx] = take("hidden")
    for i in range(n_surfaces):
        names.setdefault(i, take("spare"))
    return names


def emit_mesh(model, gun, rest_frame: int, out: str) -> MeshResult:
    """Write `out` as the gun's world mesh and report the shift R4 needs."""
    frames = min(model.num_frames, min(s.num_frames for s in model.surfaces))
    if not (0 <= rest_frame < frames):
        raise ValueError(f"{gun.id}: rest frame {rest_frame} is outside the {frames} frames "
                         f"every surface of {os.path.basename(model.source)} has")

    centroid, t = recentre_shift(model, rest_frame)
    names = surface_names(gun, len(model.surfaces))

    out_surfaces: List[MD3.MD3Surface] = []
    total_verts = 0
    for i, s in enumerate(model.surfaces):
        moved = [(v[0] + t[0], v[1] + t[1], v[2] + t[2]) for v in s.verts[rest_frame]]
        # The mesh is translated and not rotated, so every normal is unchanged:
        # the raw packed shorts carry across untouched rather than being decoded
        # and re-encoded onto the pi/128 grid.
        packed = [list(s.normals_packed[rest_frame])] if s.normals_packed else []
        out_surfaces.append(MD3.MD3Surface(
            index=len(out_surfaces), name=names[i], num_frames=1,
            shaders=[MD3.MD3Shader(name=sh.name, shader_index=0) for sh in s.shaders]
                    or [MD3.MD3Shader(name="", shader_index=0)],
            triangles=list(s.triangles), st=list(s.st),
            verts=[moved], normals=[list(s.normals[rest_frame])], normals_packed=packed))
        total_verts += len(moved)

    written = MD3.MD3Model(
        source=out, name=os.path.basename(out), num_frames=1,
        frames=[MD3.MD3Frame(mins=(0, 0, 0), maxs=(0, 0, 0), origin=(0, 0, 0),
                             radius=0.0, name="rest")],
        tags=[], surfaces=out_surfaces)
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    MD3.write(written, out)

    return MeshResult(out=out, rest_frame=rest_frame, centroid=centroid, t=t,
                      names=names, verts=total_verts, surfaces=len(out_surfaces))
