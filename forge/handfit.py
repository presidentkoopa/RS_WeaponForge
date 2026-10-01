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

THE HAND is hand_left_poses.iqm, 1937 vertices over 1705 frames, which is the same mesh
that produced the 45-of-1937 datum. Frames 1494+ are the authored gun-hand grips.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

# The posed hand. It survives only in a backup: the live packs carry the hand inside the
# avatar body rather than as its own mesh, and the harness this replaces lived in a session
# scratchpad and is gone.
HAND_IQM = ('E:/DOOMWork/_backups/handsbody_before_stabilize_merge_2026-09-18/'
            'RS_WorldHands/models/hands/hand_left_poses.iqm')
# Frames 1494+ are the authored gun grips; 0 is the open hand.
FRAME_GUN_GRIP = 1494
# How far to move the hand for the calibration pass, in mesh units.
CLEAR_DISTANCE = 200.0


@dataclass
class HandFit:
    ok: bool = False
    inside: int = 0
    total: int = 0
    clear_inside: int = 0          # the calibration: must be 0
    why: str = ""
    notes: List[str] = field(default_factory=list)


def _tris(model, surfaces: Sequence[int], frame: int = 0):
    """Gun triangles as an (n, 3, 3) array of corner positions."""
    pts, tris, base = [], [], 0
    for i in surfaces:
        s = model.surfaces[i]
        v = np.asarray(s.verts[frame], dtype=float)
        pts.append(v)
        for t in s.triangles:
            tris.append([t[0] + base, t[1] + base, t[2] + base])
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


def hand_points(frame: int = FRAME_GUN_GRIP, path: str = HAND_IQM) -> Optional[np.ndarray]:
    """The posed hand's vertices in its own space, or None when the mesh is not there."""
    if not os.path.isfile(path):
        return None
    sys.path.insert(0, 'E:/DOOMWork/UZDXREMA/tools/avatar')
    from iqm import IQM                                   # noqa: E402
    m = IQM(path)
    pts = np.asarray(m.positions, dtype=float).reshape(-1, 3)
    return pts


def fit_at(model, surfaces: Sequence[int], seat: Sequence[float], axis=None,
           frame: int = FRAME_GUN_GRIP, tolerance: int = 0) -> HandFit:
    """Place the hand at `seat` and count what ends up inside the gun.

    `tolerance` is how many vertices inside still counts as a pass. It defaults to 0 and
    should stay there unless there is a measured reason: the number this replaces was 45,
    on a grip that looked right, and calling that acceptable is how it shipped.
    """
    out = HandFit()
    hand = hand_points(frame)
    if hand is None:
        out.why = (f"the posed hand is not at {HAND_IQM} -- without it this measures "
                   f"nothing, and a silent pass would be worse than no check")
        return out

    tri = _tris(model, surfaces)
    out.total = int(len(hand))

    # CALIBRATION FIRST, and the result is reported whatever happens. A parity count that
    # does not zero in free space is measuring its own bugs.
    clear = hand + np.asarray([CLEAR_DISTANCE, CLEAR_DISTANCE, CLEAR_DISTANCE])
    out.clear_inside = count_inside(clear, tri)
    if out.clear_inside != 0:
        out.why = (f"calibration failed: {out.clear_inside} of {out.total} hand vertices "
                   f"read as INSIDE the gun while {CLEAR_DISTANCE} units clear of it. The "
                   f"gun's surface is not closed, or the ray is degenerate. Any number this "
                   f"gives for a real grip would be meaningless.")
        return out

    # The hand's own origin sits at its wrist; move it so that origin is the seat.
    placed = hand - hand.mean(axis=0) + np.asarray(seat, dtype=float)
    out.inside = count_inside(placed, tri)
    out.ok = out.inside <= tolerance
    if not out.ok:
        out.why = (f"{out.inside} of {out.total} hand vertices are inside the gun -- the "
                   f"fist closes THROUGH the mesh rather than around it")
    out.notes.append(f"calibration {out.clear_inside}, placed {out.inside} of {out.total}")
    return out
