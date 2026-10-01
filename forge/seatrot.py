#!/usr/bin/env python3
"""seatrot.py -- how the palm is TURNED on the grip, measured off the mesh.

A `seat` pins where the hand is on the gun. It says nothing about the hand's twist, so
the roll about the grip axis is whatever falls out of the model's own axes -- and it is
unset on all 62 cards today.

WHERE THE NUMBER COMES FROM, and nowhere else. The grip of a gun is a handle: a run of
vertices whose long axis IS the direction a fist closes around. So the axis is the
PRINCIPAL AXIS of the vertices in a neighbourhood of the seat, and `seatrot` is the
rotation carrying the card's reference frame onto it.

NEVER FROM A PICTURE. This project shipped a gun base rotation 45 degrees out because it
came from a render, and it was caught only in a headset. A wrong seatrot is worse than an
absent one: absent reads as "unsolved" and gets solved, wrong reads as solved and gets
trusted. So this refuses rather than guesses -- see `SeatRot.ok`.

THE ORDER MATTERS. seatrot must be solved BEFORE any grip thickness is measured, because
a thickness is the cross-section PERPENDICULAR TO THE GRIP AXIS and that plane is
undefined until the axis is known. Measure thickness first and every pistol gets a section
cut across the bore instead of across the grip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

# How big a neighbourhood of the seat counts as "the grip", in mesh units. A pistol grip
# is a few units across and a couple of times that tall; this has to take in the whole
# handle and none of the frame above it.
GRIP_RADIUS = 4.5
# Below this many vertices the principal axis is noise, not a handle.
GRIP_MIN_VERTS = 24
# A handle is LONGER than it is wide. If the first two principal extents are within this
# ratio the cloud is a blob with no long axis and the answer is refused.
ELONGATION_MIN = 1.25


@dataclass
class SeatRot:
    """The measured twist, or why there isn't one."""
    ok: bool = False
    why: str = ""
    axis: Optional[tuple] = None        # unit vector, mesh space, card axes
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    verts: int = 0
    elongation: float = 0.0
    notes: List[str] = field(default_factory=list)

    def triple(self) -> tuple:
        return (self.yaw, self.pitch, self.roll)


def _cloud_near(pts: np.ndarray, seat: np.ndarray, radius: float) -> np.ndarray:
    d = np.linalg.norm(pts - seat, axis=1)
    return pts[d <= radius]


def principal_axis(cloud: np.ndarray):
    """The long axis of a vertex cloud, and how elongated it is.

    Mean-centred SVD: the first right-singular vector is the direction of greatest
    spread. The ratio of the first two singular values says whether there IS a long
    axis -- a sphere has none and its "principal axis" is whichever way the noise fell.
    """
    c = cloud - cloud.mean(axis=0)
    # full_matrices=False: only the three right-singular vectors are wanted.
    _u, s, vt = np.linalg.svd(c, full_matrices=False)
    axis = vt[0] / np.linalg.norm(vt[0])
    elong = float(s[0] / s[1]) if s[1] > 1e-9 else float("inf")
    return axis, elong, s


def _orient(axis: np.ndarray) -> np.ndarray:
    """Point the axis DOWN the grip, the way a hand hangs on it.

    An SVD axis has no sign -- v and -v span the same line. A grip runs down and back
    from the frame, so the answer is taken with a negative Z (mesh up) component; a grip
    axis that is level is taken with a negative X so at least it is consistent.
    """
    if abs(axis[2]) > 1e-6:
        return axis if axis[2] < 0 else -axis
    return axis if axis[0] < 0 else -axis


def euler_from_axis(axis: np.ndarray) -> tuple:
    """yaw, pitch, roll in degrees that carry the card's reference down-axis onto `axis`.

    The reference is (0, 0, -1) -- straight down in mesh space -- because that is where a
    grip points on a gun held level, and it makes an unrotated grip read as 0, 0, 0
    rather than as some arbitrary triple.

    ROLL IS NOT SOLVED HERE and is returned as 0. A single axis fixes two degrees of
    freedom; the third is the hand's spin about the grip, which no axis can tell you.
    That is the finding already on record -- a grip has three degrees of freedom and the
    gun fixes two -- so the third stays 0 and honest rather than invented.
    """
    a = axis / np.linalg.norm(axis)
    # pitch away from straight-down, yaw around mesh up.
    pitch = float(np.degrees(np.arcsin(np.clip(-a[2], -1.0, 1.0))))
    pitch = 90.0 - pitch
    yaw = float(np.degrees(np.arctan2(a[1], a[0]))) if (abs(a[0]) + abs(a[1])) > 1e-9 else 0.0
    return (round(yaw, 3), round(pitch, 3), 0.0)


def measure_seatrot(model, surfaces: Sequence[int], rest: int, t: Sequence[float],
                    seat: Sequence[float], radius: float = GRIP_RADIUS) -> SeatRot:
    """The twist of the hand on the grip, from the mesh around the seat.

    `surfaces` are the body's (the grip belongs to the frame, not to a moving part),
    `t` is the recentring the shipped mesh was written with, so the cloud is in the same
    space the card's `seat` is stated in.
    """
    from .measure import _part_cloud                      # same cloud as everything else

    pts = _part_cloud(model, surfaces, rest) + np.asarray(t, dtype=float)
    s = np.asarray(seat, dtype=float)
    cloud = _cloud_near(pts, s, radius)
    out = SeatRot(verts=int(len(cloud)))

    if len(cloud) < GRIP_MIN_VERTS:
        out.why = (f"only {len(cloud)} vertices within {radius} of the seat -- too few for a "
                   f"principal axis, so the twist is not measured rather than guessed")
        return out

    axis, elong, _s = principal_axis(cloud)
    out.elongation = round(elong, 3)
    if elong < ELONGATION_MIN:
        out.why = (f"the cloud round the seat is {elong:.2f} times longer than it is wide -- "
                   f"under {ELONGATION_MIN} that is a blob, and its long axis is whichever "
                   f"way the noise fell, not a handle")
        return out

    axis = _orient(axis)
    out.ok = True
    out.axis = tuple(round(float(v), 6) for v in axis)
    out.yaw, out.pitch, out.roll = euler_from_axis(axis)
    out.notes.append(
        f"{len(cloud)} vertices within {radius} of the seat, {elong:.2f}x elongated; "
        f"axis {out.axis[0]:+.3f} {out.axis[1]:+.3f} {out.axis[2]:+.3f}; roll left at 0 "
        f"because one axis cannot fix the spin about itself")
    return out
