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
from typing import Dict, List, Optional, Sequence, Tuple

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


def read_cut(path: str, surf, where: str = "") -> List[int]:
    """A cut file: one vertex index per line, the exact set to lift.

    FOR A PART NO RULE CAN FIND. A magazine welded into a body can be beyond any
    description a set file can carry -- the buzzsaw's drum touches the receiver
    more closely (0.256) than its own two halves touch each other (0.404), so no
    gap separates it, and the machinegun's 415 vertices are three whole objects
    while the buzzsaw's cut slices through sixteen. Where the shape cannot be
    described, the set names the vertices, and the tool checks them: every index
    inside the surface, the count as declared.

    These are not typed by hand either. They are recovered from a mesh that
    already carries the part as its own surface -- an earlier build of the same
    gun -- by fitting a surface the two meshes share and mapping the positions
    back. On the buzzsaw and the flamethrower that fit is exact to 0.0000.
    """
    if not os.path.exists(path):
        raise ValueError(f"{where}: no cut file at {path}")
    ids = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                ids.append(int(line))
    n = len(surf.st)
    bad = [i for i in ids if not (0 <= i < n)]
    if bad:
        raise ValueError(f"{where}: {os.path.basename(path)} names vertex {bad[:3]} but the "
                         f"surface has {n}; it was written for another mesh")
    return sorted(set(ids))


def resolve_island(surf, frame: int, spec: dict, shift: Sequence[float],
                   where: str = "", cut_dir: str = "") -> List[int]:
    """The vertices an island spec names, refusing the spec if the count is not
    what it claims.

    The count is the guard. A box written against one export of a mesh, or
    rounded a little too far, picks up a bolt from the receiver or drops a
    corner of the magazine, and nothing downstream would ever say so -- the part
    would simply be the wrong shape for the rest of the set's life.
    """
    if spec.get("cut"):
        got = read_cut(os.path.join(cut_dir, spec["cut"]), surf, where)
    elif "box" in spec:
        lo, hi = spec["box"]
        got = islands_in_box(surf, frame, lo, hi, shift)
    else:
        raise ValueError(f"{where}: an island needs a box or a cut file")
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


def surface_names(gun, n_surfaces: int, island_hosts: Optional[set] = None) -> Dict[int, str]:
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

    island_hosts = island_hosts or set()
    if gun.body is not None:
        names[gun.body] = take("body")
    for pid, part in gun.parts.items():
        for idx in part.surfaces:
            # AN ISLAND PART DOES NOT TAKE ITS HOST'S NAME. Its surfaces list holds
            # the surface it lives inside -- which is normally the body -- so naming
            # the host after the part renames the whole gun "magazine", leaves the
            # mesh with no body at all, and hands the reload system the entire
            # weapon to pull out of itself. The island is written as a surface of
            # its own below and takes the part's name there; the host keeps its own.
            if part.island and idx in island_hosts:
                continue
            names[idx] = take(pid)
    for idx in gun.fixed:
        names[idx] = take("fixed")
    for idx in gun.hidden:
        names[idx] = take("hidden")
    for i in range(n_surfaces):
        names.setdefault(i, take("spare"))
    return names


def emit_mesh(model, gun, rest_frame: int, out: str, cut_dir: str = "") -> MeshResult:
    """Write `out` as the gun's world mesh and report the shift R4 needs.

    An island part is SPLIT OUT here: its host surface is written twice, once as
    the island under the part's own name and once as what is left under the host's
    name. Both halves have to exist in the mesh, or the card names a part the
    engine cannot find -- or worse, finds the whole gun under.
    """
    frames = min(model.num_frames, min(s.num_frames for s in model.surfaces))
    if not (0 <= rest_frame < frames):
        raise ValueError(f"{gun.id}: rest frame {rest_frame} is outside the {frames} frames "
                         f"every surface of {os.path.basename(model.source)} has")

    centroid, t = recentre_shift(model, rest_frame)

    # Resolve every island first: which host surface it lives in and which of its
    # vertices it is.
    islands: Dict[int, Dict[str, List[int]]] = {}
    for pid, part in gun.parts.items():
        if not part.island:
            continue
        host = model.surfaces[part.island["of"]]
        ids = resolve_island(host, rest_frame, part.island, t,
                             f"{gun.id} part '{pid}'", cut_dir)
        islands.setdefault(part.island["of"], {})[pid] = ids

    names = surface_names(gun, len(model.surfaces), island_hosts=set(islands))

    def shifted(surf, ids: Optional[Sequence[int]], name: str) -> MD3.MD3Surface:
        """One written surface: all of a donor surface, or just the island's
        vertices, translated by t."""
        src = split_surface(surf, ids, name, frame=rest_frame) if ids is not None else None
        verts = (src.verts[0] if src is not None else surf.verts[rest_frame])
        moved = [(v[0] + t[0], v[1] + t[1], v[2] + t[2]) for v in verts]
        # The mesh is translated and not rotated, so every normal is unchanged:
        # the raw packed shorts carry across untouched rather than being decoded
        # and re-encoded onto the pi/128 grid.
        if src is not None:
            packed = [list(src.normals_packed[0])] if src.normals_packed else []
            normals = list(src.normals[0])
            tris, st = list(src.triangles), list(src.st)
            shaders = list(src.shaders)
        else:
            packed = [list(surf.normals_packed[rest_frame])] if surf.normals_packed else []
            normals = list(surf.normals[rest_frame])
            tris, st = list(surf.triangles), list(surf.st)
            shaders = [MD3.MD3Shader(name=sh.name, shader_index=0) for sh in surf.shaders]
        return MD3.MD3Surface(
            index=0, name=name, num_frames=1,
            shaders=shaders or [MD3.MD3Shader(name="", shader_index=0)],
            triangles=tris, st=st, verts=[moved], normals=[normals], normals_packed=packed)

    out_surfaces: List[MD3.MD3Surface] = []
    total_verts = 0
    for i, s in enumerate(model.surfaces):
        if i in islands:
            taken: set = set()
            for pid, ids in islands[i].items():
                out_surfaces.append(shifted(s, ids, names.get(f"island:{pid}", pid)))
                total_verts += len(ids)
                taken |= set(ids)
            rest_ids = [v for v in range(len(s.st)) if v not in taken]
            out_surfaces.append(shifted(s, rest_ids, names[i]))
            total_verts += len(rest_ids)
        else:
            out_surfaces.append(shifted(s, None, names[i]))
            total_verts += s.num_verts
    for n, surf in enumerate(out_surfaces):
        surf.index = n

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
