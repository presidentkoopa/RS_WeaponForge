#!/usr/bin/env python3
"""handfit.py -- does a hand actually CLOSE on this grip, or through it?

WHY A PICTURE CANNOT ANSWER THIS. A fist closed THROUGH a barrel reads as "wrapped" in
silhouette. Judging a grip by eye failed twice in one session on this project, and the IK
lane's best result on a grip that LOOKED correct still had 45 of 1937 hand vertices inside
the gun. So a render can REJECT a handhold -- it is the only thing that can say "that is
the magazine, not the grip" -- and it can never CONFIRM one.

WHAT THIS DOES INSTEAD. Places the posed hand at the seat, then counts how many of its
vertices are inside the gun's solid by ray parity: cast a ray from each hand vertex and
count how many gun triangles it crosses. An odd count means the vertex started inside.

THE CALIBRATION IS THE WHOLE POINT (the IK lane's, 2026-09-18): move the hand 200 units
clear of the gun and require EXACTLY ZERO. A parity test that does not zero out in free
space is measuring its own bugs -- a leaking mesh, a ray along a triangle edge, a winding
problem -- and would then report a number for a grip that means nothing.

===========================================================================
REWRITTEN 2026-10-02 (CODER_PLAN step 45). EVERY NUMBER THIS GAVE BEFORE WAS
MEANINGLESS, and nothing said so: it returned a count, and a count reads as a
measurement. Five separate faults, each of them silent:

  1. THE BIND POSE. hand_points took a `frame` argument and never used it -- it read
     IQM.positions, which is the OPEN hand. An open hand does not penetrate a barrel
     and a closed one does, so the tool was measuring the wrong hand entirely. The
     pose it should read is frames 1494+ and iqm.py has had posed_positions all along.
  2. THE CENTROID, NOT THE PALM. It placed `hand - hand.mean(axis=0) + seat`, while
     its own comment said "the hand's own origin sits at its wrist; move it so that
     origin is the seat". MEASURED: HANDPALM_joint sits at (0, 0, 0.01) on every one
     of the 1705 frames -- the mesh's origin IS the palm -- and the centroid is 10.3
     to 10.8 units away from it. So the hand was placed a whole palm's length off the
     seat, which is further than the width of the thing being tested.
  3. NO ORIENTATION. `axis` was accepted and ignored, so the hand was tested in
     whatever direction the mesh was authored in, against a grip pointing wherever
     the gun's grip points. A grip held crosswise penetrates differently from one
     held along. Now required, and REFUSED when absent rather than answered: see
     "WHY AN ABSENT AXIS IS A REFUSAL" below.
  4. NO UNIT CONVERSION between a hand mesh and a gun mesh. The answer turns out to
     be a factor of ONE, but only at the standard scale and only by a cancellation --
     see "THE UNITS" -- so it is computed from the set's own scale, not assumed.
  5. THE GUN AT FRAME 0 IN DONOR SPACE. _tris defaulted to frame 0 with no shift,
     while a card's `seat` is in the gun's REST frame after the forge's recentring.
     Two different spaces, compared without conversion.

THE SUM OF 2, 3 AND 5 is a differently-posed hand, facing a different way, placed a
palm's length off, against a gun in another coordinate frame. What came out of that
was a number, and numbers are believed.
===========================================================================

THE UNITS, and they cancel -- which is exactly why this has to be written down.

  a hand mesh unit   0.01 m. The hand bbox is 14.9882 x 9.0510 x 32.9533 and its long
                     axis is the 0.3295 m hand-and-forearm the psprite hands were signed
                     off at (RS_WorldHands/MODELDEF.txt's own derivation; the bbox read
                     out of the file here reproduces all three figures to four decimals).
  a gun model unit   scale / vr_vunits_per_meter metres, where `scale` is what the prop
                     is drawn at. emit_prop.WORLD_FACTOR is 0.34 and says where it comes
                     from: 34 x 0.01 -- vr_vunits_per_meter times that same 0.01.

  so hand units -> gun model units  =  0.01 / (scale / 34)  =  WORLD_FACTOR / scale

At the standard 0.34 that is 1.0. IT IS NOT ALWAYS 1.0: Vanilla's guns draw at 1.35,
where the factor is 0.252. A hard-coded 1 would be right for BD22 and wrong by four
times for the set next door, which is the same class of mistake as the x34 and the
x0.01 this project has now made in both directions.

WHY AN ABSENT AXIS IS A REFUSAL AND NOT A DEFAULT. A grip has three degrees of freedom
and the gun fixes two of them (the grip axis); the third, the roll about that axis, is
pinned by the handle's cross-section -- GripFit.clock -- and GripFit.roll is documented
as "never solved from geometry". With no axis there is no frame at all, and a hand
tested in an arbitrary direction produces a count that looks exactly like a real one.
Returning ok = False with a reason is the only honest answer: this tool's whole job is
to be trusted where a render cannot be, and it was not.

THE HAND is hand_left_poses.iqm, 1937 vertices over 1705 frames, which is the same mesh
that produced the 45-of-1937 datum. Frames 1494+ are the authored gun-hand grips.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

# THE POSED HAND, out of the sanctioned asset folder. It used to be read from
# E:/DOOMWork/_backups/handsbody_before_stabilize_merge_2026-09-18/... -- a DATED BACKUP,
# which is a path that exists until somebody tidies up. _assets_safe/hands holds the same
# file byte for byte (sha1 779a8adcfccdc94e on both) and is where it is meant to live.
#
# THE BINARY IS NOT COPIED IN HERE. Step 45 said to copy the IQM into WeaponForge; a
# second copy of a 714 KB mesh is one more thing to keep in step, and this file already
# has two homes. Pointing at the single sanctioned copy fixes the actual defect, which
# was the dependence on a backup directory.
HAND_IQM = 'E:/DOOMWork/_assets_safe/hands/hand_left_poses.iqm'

# iqm.py LIVES ONCE, in the engine's avatar tools, and is imported rather than forked. A
# vendored copy of an IQM parser is a copy that drifts from the one the avatars are built
# with, and a skinning difference between the two would surface here as a penetration
# count. The path is a named constant because it used to be a sys.path.insert buried in
# the middle of a function body.
IQM_TOOLS = 'E:/DOOMWork/UZDXREMA/tools/avatar'

# Frames 1494+ are the authored gun grips; 0 is the open hand.
FRAME_GUN_GRIP = 1494
# How far to move the hand for the calibration pass, in mesh units.
CLEAR_DISTANCE = 200.0
# emit_prop's own, repeated rather than imported so this module stands alone: the
# exchange rate between a gun's model units and map units, 34 x 0.01.
WORLD_FACTOR = 0.34
# The hand's joint names. HANDPALM is the mesh's origin -- measured at (0, 0, 0.01) on
# every frame -- so it is the anchor a card's `seat` means by "the point in the palm".
JOINT_PALM = 'HANDPALM_joint'
JOINT_INDEX = 'INDEX_MID_joint'
JOINT_MIDDLE = 'MIDDLE_F_MID_joint'
JOINT_PINKY = 'PINK_MID_joint'


@dataclass
class HandFit:
    ok: bool = False
    inside: int = 0
    total: int = 0
    clear_inside: int = 0          # the calibration: must be 0
    why: str = ""
    notes: List[str] = field(default_factory=list)


def _tris(model, surfaces: Sequence[int], frame: int = 0,
          t: Sequence[float] = (0.0, 0.0, 0.0)):
    """Gun triangles as an (n, 3, 3) array of corner positions, IN CARD SPACE.

    `frame` is the gun's REST frame and `t` the forge's recentring shift
    (emit_mesh.recentre_shift), because that is the space a card's seat, muzzle and grab
    points are written in. Defaulting to frame 0 with no shift -- which is what this did
    -- compares the seat against a different pose of the gun about a different origin.
    """
    pts, tris, base = [], [], 0
    shift = np.asarray(t, dtype=float)
    for i in surfaces:
        s = model.surfaces[i]
        v = np.asarray(s.verts[frame], dtype=float) + shift
        pts.append(v)
        for tr in s.triangles:
            tris.append([tr[0] + base, tr[1] + base, tr[2] + base])
        base += len(v)
    P = np.vstack(pts)
    T = np.asarray(tris, dtype=int)
    return P[T]


def count_inside(points: np.ndarray, tri: np.ndarray,
                 direction=(0.5773, 0.5774, 0.5775)) -> int:
    """How many of `points` are inside the closed surface `tri`, by ray parity.

    The direction is deliberately irrational-ish rather than an axis: a ray along +X on a
    box-modelled gun runs along edges and through shared vertices, and each of those is a
    double count or a miss. An oblique ray hits faces squarely.

    Moller-Trumbore, vectorised over triangles for one point at a time -- a gun is tens of
    thousands of triangles and a hand is two thousand points, which is small enough that a
    BVH would be more code than it saves.
    """
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    v0, v1, v2 = tri[:, 0], tri[:, 1], tri[:, 2]
    e1, e2 = v1 - v0, v2 - v0
    h = np.cross(d, e2)
    a = np.einsum('ij,ij->i', e1, h)
    live = np.abs(a) > 1e-9              # rays parallel to a face never cross it
    inv = np.zeros_like(a)
    inv[live] = 1.0 / a[live]

    n = 0
    for p in points:
        s = p - v0
        u = np.einsum('ij,ij->i', s, h) * inv
        ok = live & (u >= 0.0) & (u <= 1.0)
        if not ok.any():
            continue
        q = np.cross(s, e1)
        v = np.einsum('ij,ij->i', np.broadcast_to(d, s.shape), q) * inv
        ok &= (v >= 0.0) & (u + v <= 1.0)
        if not ok.any():
            continue
        t = np.einsum('ij,ij->i', e2, q) * inv
        if int(np.count_nonzero(ok & (t > 1e-6))) % 2 == 1:
            n += 1
    return n


def _iqm(path: str):
    """The IQM reader, imported from the one copy of it that exists."""
    if IQM_TOOLS not in sys.path:
        sys.path.insert(0, IQM_TOOLS)
    from iqm import IQM                                   # noqa: E402
    return IQM(path)


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])


def hand_points(frame: int = FRAME_GUN_GRIP, path: str = HAND_IQM) -> Optional[np.ndarray]:
    """The hand's vertices AS THE FRAME POSES THEM, in its own space.

    `frame` used to be accepted and discarded, which handed back the open hand -- fault 1
    at the top of this file. posed_positions raises if the mesh carries no blend weights
    rather than quietly returning the bind pose, which is the right behaviour and the
    reason it is used here instead of skinning by hand.
    """
    if not os.path.isfile(path):
        return None
    m = _iqm(path)
    return np.asarray(m.posed_positions(frame), dtype=float).reshape(-1, 3)


def hand_frame(frame: int = FRAME_GUN_GRIP,
               path: str = HAND_IQM) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """(palm origin, grip axis, palm normal) of the posed hand, orthonormal.

    THE GRIP AXIS is the line from the index finger's middle joint to the little finger's:
    four fingers closed round a handle lie side by side ACROSS it, so the line through
    them runs ALONG it. THE PALM NORMAL is the palm joint toward the middle finger's
    middle joint -- out of the palm and into the handle.

    THE TWO ARE NOT PERPENDICULAR, and are not assumed to be: measured over frames 1494
    to 1704 their dot product runs -0.18 to -0.29, which is 73 to 80 degrees apart. A
    frame built by assuming a right angle would be out by up to 17 degrees, so the normal
    is orthogonalised against the axis.
    """
    if not os.path.isfile(path):
        return None
    m = _iqm(path)
    names = [j.name for j in m.joints]
    for n in (JOINT_PALM, JOINT_INDEX, JOINT_MIDDLE, JOINT_PINKY):
        if n not in names:
            return None
    g = m._globals(m.frame_pose(frame))

    def pos(n):
        return np.asarray(g[names.index(n)][1], dtype=float)

    palm = pos(JOINT_PALM)
    axis = _unit(pos(JOINT_PINKY) - pos(JOINT_INDEX))
    raw = pos(JOINT_MIDDLE) - palm
    normal = _unit(raw - float(raw @ axis) * axis)      # Gram-Schmidt, not an assumption
    return palm, axis, normal


def _rotation(from_axis, from_normal, to_axis, to_normal) -> np.ndarray:
    """The rotation taking one orthonormal pair onto another.

    Each frame is completed to a right-handed triple by its own cross product, so this is
    an exact rotation and not a least-squares fit: R = B A^T with A and B orthonormal.
    """
    def basis(a, n):
        a = _unit(np.asarray(a, dtype=float))
        n = np.asarray(n, dtype=float)
        n = _unit(n - float(n @ a) * a)
        return np.column_stack([a, n, np.cross(a, n)])
    return basis(to_axis, to_normal) @ basis(from_axis, from_normal).T


def fit_at(model, surfaces: Sequence[int], seat: Sequence[float], axis=None,
           clock_normal=None, rest: int = 0, t: Sequence[float] = (0.0, 0.0, 0.0),
           scale: float = WORLD_FACTOR, frame: int = FRAME_GUN_GRIP,
           tolerance: int = 0) -> HandFit:
    """Place the posed hand on `seat`, pointing along `axis`, and count what is inside.

    `axis` is the grip axis in CARD SPACE -- GripFit.axis is exactly this. `clock_normal`
    is which way the palm faces about that axis; unstated, the handle's cross-section has
    not been resolved and a perpendicular is chosen, which is reported as an assumption in
    the notes rather than hidden.

    `rest`, `t` and `scale` put the gun in the same space and the same units as the seat:
    the gun's rest frame, the recentring shift, and the prop's drawn scale.

    `tolerance` is how many vertices inside still counts as a pass. It defaults to 0 and
    should stay there unless there is a measured reason: the number this replaces was 45,
    on a grip that looked right, and calling that acceptable is how it shipped.
    """
    out = HandFit()

    # NO AXIS, NO ANSWER. See "WHY AN ABSENT AXIS IS A REFUSAL" at the top of this file.
    # This used to take `axis` and ignore it, and the count it returned looked exactly
    # like a measurement.
    if axis is None:
        out.why = ("no grip axis given, so there is no orientation to place the hand in. "
                   "A hand tested in an arbitrary direction returns a count that looks "
                   "exactly like a real one -- pass GripFit.axis for this seat.")
        return out

    hand = hand_points(frame)
    hf = hand_frame(frame)
    if hand is None or hf is None:
        out.why = (f"the posed hand is not at {HAND_IQM} -- without it this measures "
                   f"nothing, and a silent pass would be worse than no check")
        return out
    palm, hand_axis, hand_normal = hf

    if abs(scale) < 1e-6:
        out.why = f"scale {scale} is zero -- nothing can be converted into the gun's units"
        return out

    tri = _tris(model, surfaces, rest, t)
    out.total = int(len(hand))

    # THE UNITS, derived and not assumed: see "THE UNITS" at the top. 1.0 at the standard
    # 0.34, and 0.252 on a Vanilla gun drawn at 1.35.
    factor = WORLD_FACTOR / abs(scale)

    gun_axis = _unit(np.asarray(axis, dtype=float))
    if clock_normal is None:
        # A direction across the axis, taken from whichever world axis is least parallel
        # to it so the pick is stable rather than arbitrary. STILL AN ASSUMPTION, so the
        # notes say so and the number is provisional.
        w = np.eye(3)[int(np.argmin(np.abs(gun_axis)))]
        gun_normal = _unit(w - float(w @ gun_axis) * gun_axis)
        out.notes.append("no clock_normal: the roll about the grip axis is an assumption, "
                         "so this count is provisional (GripFit.clock pins it)")
    else:
        gun_normal = np.asarray(clock_normal, dtype=float)

    R = _rotation(hand_axis, hand_normal, gun_axis, gun_normal)
    # PALM TO THE ORIGIN, ROTATE, SCALE, THEN TO THE SEAT. The palm is the anchor and not
    # the centroid: HANDPALM_joint is the mesh's own origin and the centroid is a palm's
    # length away from it (fault 2 at the top).
    local = (hand - palm) @ R.T * factor

    # CALIBRATION FIRST, and the result is reported whatever happens. A parity count that
    # does not zero in free space is measuring its own bugs.
    clear = local + np.asarray([CLEAR_DISTANCE, CLEAR_DISTANCE, CLEAR_DISTANCE])
    out.clear_inside = count_inside(clear, tri)
    if out.clear_inside != 0:
        out.why = (f"calibration failed: {out.clear_inside} of {out.total} hand vertices "
                   f"read as INSIDE the gun while {CLEAR_DISTANCE} units clear of it. The "
                   f"gun's surface is not closed, or the ray is degenerate. Any number this "
                   f"gives for a real grip would be meaningless.")
        return out

    placed = local + np.asarray(seat, dtype=float)
    out.inside = count_inside(placed, tri)
    out.ok = out.inside <= tolerance
    if not out.ok:
        out.why = (f"{out.inside} of {out.total} hand vertices are inside the gun -- the "
                   f"fist closes THROUGH the mesh rather than around it")
    out.notes.append(f"frame {frame}, units x{factor:.4f}, calibration {out.clear_inside}, "
                     f"placed {out.inside} of {out.total}")
    return out
