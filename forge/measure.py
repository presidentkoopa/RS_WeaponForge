#!/usr/bin/env python3
"""
measure.py -- the numbers a card carries, measured in the written mesh's space.
Step 7 of the WeaponForge Build Guide.

EVERYTHING HERE IS IN _wm SPACE, which is donor space plus t, the recentring
shift emit_mesh applied. That is the space the engine draws the prop in, so it
is the space every point on the card has to be in. A number measured in donor
space and written to a card is wrong by t -- tens of units -- and it will look
like the muzzle flash coming out of the stock.

Axes and angles are translation-invariant, so they are measured on the donor's
own frames; points (pivots, muzzle, grab, magcenter) have t added.

WHAT EACH MEASUREMENT IS

  slide   axis = the unit centroid displacement on the frame of greatest PURE
          translation (turn < 0.1 degrees); distance = its length. Restricting
          to pure frames matters: a part that both slides and tips reports a
          longer travel along a tilted axis if the tipping frames are allowed
          in, and the slide then drives along a line the real part never takes.

  hinge   axis and angle from the rotation on the frame that turns furthest;
          pivot = the transform's fixed point with the along-axis component
          removed, which is the point on the hinge line closest to the origin
          rather than an arbitrary point on it. The removal happens AFTER t is
          added: a hinge line is a line, so where along it the pivot is quoted
          is a choice, and the choice has to be made in the space the card is
          read in. Zeroing in donor space and then shifting by t puts the pivot
          back off the origin by t's own along-axis component -- 5.98 for the
          SMG's charging handle, against the shipped card's 0.

          THE SIGN IS CHECKED BOTH WAYS, because a rotation matrix's axis and
          its negation describe the same turn, and the card drives the part by
          a signed angle. +angle must carry the rest centroid onto where the
          part actually is on that frame; if -angle does it instead, the axis
          is flipped. Reported as both margins, so a near-tie is visible
          instead of being silently resolved.

  feed    axis from the frames the magazine travels on; distance = the carve's
          own extent along that axis, so the magazine slides exactly its own
          length out of the well rather than a number someone chose.

  carve   the part's surfaces at rest, lifted into their own mesh, moved onto
          their centroid and turned so the feed axis points at -Z: a loose
          magazine lies on its side when the actor rolls it 90 degrees, and one
          still carrying the grip's rake lies half sunk into the floor.

  muzzle  the mean of the body vertices within 0.5 of its greatest x. Not the
          single furthest vertex, which is a modelling accident; the mean of
          the front face is the middle of the bore.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import md3 as MD3
from .motion import (rigid_fit, rotation_angle_axis, fixed_point, PURE_TRANSLATION_DEG,
                     SMALL_HINGE_DEG)

MUZZLE_BAND = 0.5          # how deep a slice of the barrel's front face to average
SIGN_MARGIN = 0.05         # a sign check closer than this either way is a tie


@dataclass
class DOF:
    part: str
    kind: str                                   # slide | hinge | feed
    axis: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    distance: float = 0.0
    degrees: float = 0.0
    pivot: Optional[Tuple[float, float, float]] = None
    frame: int = 0
    span: Tuple[int, int] = (0, 0)
    fit: float = 0.0
    sign_ok: bool = True
    plus_miss: float = 0.0
    minus_miss: float = 0.0
    notes: List[str] = field(default_factory=list)


@dataclass
class Carve:
    part: str
    out: str
    magcenter: Tuple[float, float, float]
    magscale: float
    extent: float
    verts: int


@dataclass
class Grab:
    part: str
    grab: Tuple[float, float, float]
    handseat: Tuple[float, float, float]


def _verts(surf, frame: int) -> np.ndarray:
    return np.asarray(surf.verts[frame], dtype=float)


def _part_cloud(model, part_surfaces: Sequence[int], frame: int) -> np.ndarray:
    return np.vstack([_verts(model.surfaces[i], frame) for i in part_surfaces])


def _body_fits(model, body_index: int, rest: int, frames: int):
    """Per frame, the transform carrying the body back onto its rest pose."""
    body_rest = _verts(model.surfaces[body_index], rest)
    out = {}
    for f in range(frames):
        if f == rest:
            out[f] = (np.eye(3), np.zeros(3))
            continue
        R, t, _rms, _worst = rigid_fit(_verts(model.surfaces[body_index], f), body_rest)
        out[f] = (R, t)
    return out


def usable_frames(model) -> int:
    return min(model.num_frames, min(s.num_frames for s in model.surfaces))


def measure_dof(model, body_index: int, rest: int, part_id: str,
                part_surfaces: Sequence[int], t: Sequence[float],
                kind: str = "auto") -> DOF:
    """The slide or hinge of one part, with the body's motion divided out."""
    frames = usable_frames(model)
    fits = _body_fits(model, body_index, rest, frames)
    rest_cloud = _part_cloud(model, part_surfaces, rest)
    rest_c = rest_cloud.mean(axis=0)

    best_pure = (0.0, None, None)      # travel, frame, direction
    best_turn = (0.0, None, None, None, 0.0)   # deg, frame, axis, pivot, fit
    per_frame = {}

    for f in range(frames):
        if f == rest:
            continue
        cloud = _part_cloud(model, part_surfaces, f)
        if len(cloud) != len(rest_cloud):
            continue
        if np.max(cloud.max(axis=0) - cloud.min(axis=0)) < 0.001:
            continue                   # collapsed: this frame carries no pose
        Rb, tb = fits[f]
        corrected = cloud @ Rb.T + tb
        Rs, ts, rms, _worst = rigid_fit(corrected, rest_cloud)
        deg, axis = rotation_angle_axis(Rs)
        disp = corrected.mean(axis=0) - rest_c
        travel = float(np.linalg.norm(disp))
        per_frame[f] = (travel, deg, rms)

        if deg < PURE_TRANSLATION_DEG and travel > best_pure[0]:
            best_pure = (travel, f, disp / travel if travel > 1e-9 else np.zeros(3))
        if deg > best_turn[0]:
            best_turn = (deg, f, axis, fixed_point(Rs, ts, axis), rms)

    want = kind
    if want == "auto":
        want = "hinge" if (best_turn[0] >= PURE_TRANSLATION_DEG
                           and best_turn[0] > 0 and best_pure[0] < 0.05) else "slide"

    dof = DOF(part=part_id, kind=want)
    if want == "hinge":
        deg, frame, axis, pivot, fit = best_turn
        if frame is None:
            dof.notes.append("no frame turns this part at all")
            return dof
        dof.degrees, dof.frame, dof.fit = deg, frame, fit
        dof.axis = tuple(axis)
        # t first, then drop the along-axis part: see the note above.
        p = np.asarray(pivot) + np.asarray(t)
        n = np.linalg.norm(axis)
        if n > 1e-9:
            k = np.asarray(axis) / n
            # A PIN IS QUOTED IN THE PLANE IT TURNS IN. Where an axis is a
            # cardinal direction to within the axis tolerance -- as every trigger
            # pin in these donors is -- the dropped coordinate is that cardinal
            # one. Dropping along the measured axis instead leaves the axis's own
            # thousandth multiplied by the pin's distance from the origin: the
            # chaingun trigger sits at x -35.63, and an axis of (0.001, 1, 0.001)
            # leaves 0.016 in y, past the 0.01 the pivot is checked to. The
            # shipped card writes that pin as two numbers, "-35.631, 6.618",
            # which is the same convention said out loud.
            dominant = int(np.argmax(np.abs(k)))
            if abs(abs(k[dominant]) - 1.0) <= 0.01:
                p[dominant] = 0.0
            else:
                p = p - float(np.dot(p, k)) * k
        dof.pivot = tuple(p)
        dof.span = _active_span(per_frame, frame)
        # The sign check: turn the rest cloud by +deg about the axis through the
        # pivot and see whether it lands where the part actually is.
        cloud = _part_cloud(model, part_surfaces, frame)
        Rb, tb = fits[frame]
        actual = (cloud @ Rb.T + tb).mean(axis=0)
        dof.plus_miss = _turn_miss(rest_c, np.asarray(pivot), np.asarray(axis), +deg, actual)
        dof.minus_miss = _turn_miss(rest_c, np.asarray(pivot), np.asarray(axis), -deg, actual)
        if dof.minus_miss < dof.plus_miss:
            dof.axis = tuple(-np.asarray(axis))
            dof.plus_miss, dof.minus_miss = dof.minus_miss, dof.plus_miss
            dof.notes.append("axis flipped so that +angle is the direction the part turns")
        dof.sign_ok = dof.minus_miss - dof.plus_miss > SIGN_MARGIN
        if not dof.sign_ok:
            dof.notes.append(f"the two signs are within {SIGN_MARGIN} of each other "
                             f"(+{dof.plus_miss:.3f} against {dof.minus_miss:.3f}): "
                             f"a near-symmetrical part, needs a ruling")
    else:
        travel, frame, direction = best_pure
        if frame is None:
            dof.notes.append("no frame moves this part without also turning it")
            return dof
        dof.distance, dof.frame = travel, frame
        dof.axis = tuple(direction)
        dof.fit = per_frame[frame][2]
        dof.span = _active_span(per_frame, frame)
    return dof


def _active_span(per_frame: Dict[int, Tuple[float, float, float]], frame: int):
    """The contiguous run of frames the part is in motion for, around `frame`.

    This is the part's own window in a shared animation, and it is what the
    shipped cards quote -- the SMG's charging handle turns 12, 45, 78, 90, 68
    and 22 degrees over frames 20 to 25, and the card says "frames 20-25", not
    "frame 23". A run found by where the part actually moves also holds up in a
    donor that packs several parts' travel into one frame range.
    """
    active = {f for f, (tr, d, _r) in per_frame.items()
              if d >= PURE_TRANSLATION_DEG or tr > 0.05}
    if frame not in active:
        return (frame, frame)
    lo = hi = frame
    while lo - 1 in active:
        lo -= 1
    while hi + 1 in active:
        hi += 1
    return (lo, hi)


INSERT_FRACTION = 0.25     # how far out a frame must be to be part of the insert leg
# A spinning part's period is found by turning it onto itself; this is how close
# it has to land to count, as a median over its vertices.
SPIN_LANDS = 0.05
SPIN_MAX_FOLD = 12         # nobody builds a thirteen-barrel gun


def spin_period(model, part_surfaces: Sequence[int], rest: int, t: Sequence[float],
                axis: Sequence[float], pivot: Sequence[float],
                max_fold: int = SPIN_MAX_FOLD, lands: float = SPIN_LANDS):
    """The angle a spinning part turns onto itself, from the MESH rather than
    from the animation.

    A barrel cluster's dof is not how far the animation happens to turn it: it is
    one period of its own symmetry, because turning it by that lands every barrel
    where the next one was and the part looks continuous. The animation stops
    wherever the author left it -- the minigun's turns 106 degrees, which is not
    a period of anything.

    So each 360/k is tried and the part is turned onto itself about its measured
    axis; the smallest k that lands is the period. On the BD minigun that is 120
    degrees with a median miss of 0.015, while 60 misses by 0.174 -- three-fold
    clamps on six barrels. The shipped card says the same in its own words:
    "turned 120 the barrels land on themselves, median miss 0.017; turned 60 they
    do not".

    Returns (degrees, k, median_miss) or (None, None, best_miss) when nothing
    lands, which is the answer for a part that is not a rotor.
    """
    pts = _part_cloud(model, part_surfaces, rest) + np.asarray(t, dtype=float)
    a = np.asarray(axis, dtype=float)
    n = np.linalg.norm(a)
    if n < 1e-9 or len(pts) < 8:
        return None, None, float("inf")
    a = a / n
    p = np.asarray(pivot, dtype=float)
    K = np.array([[0.0, -a[2], a[1]], [a[2], 0.0, -a[0]], [-a[1], a[0], 0.0]])
    best = float("inf")
    for k in range(2, max_fold + 1):
        th = 2.0 * math.pi / k
        R = (math.cos(th) * np.eye(3) + math.sin(th) * K
             + (1.0 - math.cos(th)) * np.outer(a, a))
        turned = (pts - p) @ R.T + p
        miss = np.empty(len(turned))
        for i in range(0, len(turned), 512):
            chunk = turned[i:i + 512]
            d = np.linalg.norm(chunk[:, None, :] - pts[None, :, :], axis=2)
            miss[i:i + 512] = d.min(axis=1)
        med = float(np.median(miss))
        best = min(best, med)
        if med <= lands:
            return 360.0 / k, k, med
    return None, None, best


def measure_insert(model, body_index: int, rest: int, part_id: str,
                   part_surfaces: Sequence[int], t: Sequence[float],
                   fraction: float = INSERT_FRACTION) -> DOF:
    """The axis a magazine goes IN along, taken from the insert frames.

    A donor's reload animation runs inward: the magazine starts out of shot and
    travels to its seat, so the frames furthest from rest are it flying in from
    off-screen and the frames nearest rest are it seating. Neither end is the
    insert. The far end is the author's entrance -- the rifle's magazine swings
    through (-0.041, +0.559, -0.828) out there, which is an arc, not a feed --
    and the last fraction of a unit before the seat is dominated by rounding, so
    its direction wanders.

    So the axis is read from the frame NEAREST the seat that is still at least a
    quarter of the way out. That is the straight leg into the well, and it is
    what the shipped cards carry: the rifle's (-0.025, 0, -1) is its frame 13,
    the grenade pin's (0, 1, 0) its frame 6.

    Measuring at greatest travel instead is how the grenade pin came out as 37.25
    units: the animation throws the pin away, and the throw is not the pull.
    """
    frames = usable_frames(model)
    fits = _body_fits(model, body_index, rest, frames)
    rest_cloud = _part_cloud(model, part_surfaces, rest)
    rest_c = rest_cloud.mean(axis=0)

    samples = []          # (travel, frame, direction)
    for f in range(frames):
        if f == rest:
            continue
        cloud = _part_cloud(model, part_surfaces, f)
        if len(cloud) != len(rest_cloud):
            continue
        if np.max(cloud.max(axis=0) - cloud.min(axis=0)) < 0.001:
            continue
        Rb, tb = fits[f]
        corrected = cloud @ Rb.T + tb
        Rs, _ts, _rms, _worst = rigid_fit(corrected, rest_cloud)
        deg, _axis = rotation_angle_axis(Rs)
        if deg >= PURE_TRANSLATION_DEG:
            continue
        disp = corrected.mean(axis=0) - rest_c
        travel = float(np.linalg.norm(disp))
        if travel > 0.05:
            samples.append((travel, f, disp / travel))

    dof = DOF(part=part_id, kind="feed")
    if not samples:
        dof.notes.append("no frame moves this part in a straight line")
        return dof
    furthest = max(s[0] for s in samples)
    leg = [s for s in samples if s[0] >= fraction * furthest]
    travel, frame, direction = min(leg or samples, key=lambda s: s[0])
    dof.axis = tuple(direction)
    dof.frame = frame
    dof.distance = travel
    dof.span = (min(f for _tr, f, _d in leg or samples),
                max(f for _tr, f, _d in leg or samples))
    dof.notes.append(f"axis from frame {frame}, {travel:.2f} out of {furthest:.2f}")
    return dof


def extent_along(model, part_surfaces: Sequence[int], rest: int,
                 axis: Sequence[float]) -> float:
    """How long the part is along an axis, at rest.

    Measured on the part itself rather than on the written carve: the carve is
    quantised to 1/64 on the way out and turned, which adds a hundredth that the
    part does not have.
    """
    a = np.asarray(axis, dtype=float)
    n = np.linalg.norm(a)
    if n < 1e-9:
        return 0.0
    p = _part_cloud(model, part_surfaces, rest) @ (a / n)
    return float(p.max() - p.min())


def measure_feed(model, body_index: int, rest: int, part_id: str,
                 part_surfaces: Sequence[int], t: Sequence[float], carve: "Carve") -> DOF:
    """A magazine's feed: the axis it travels on, and its OWN length along that
    axis as the distance.

    The travel in the animation is how far the author dragged the magazine, which
    includes it flying off out of shot. What the reload needs is how far the
    magazine has to move to clear the well, which is the magazine's own extent --
    measured on the carve, so the number and the object it drives can never
    disagree.
    """
    dof = measure_insert(model, body_index, rest, part_id, part_surfaces, t)
    if max(abs(c) for c in dof.axis) < 1e-9:
        return dof
    travel = dof.distance
    dof.distance = extent_along(model, part_surfaces, rest, dof.axis)
    dof.notes.append(f"travelled {travel:.2f} on that frame; the distance is the part's own "
                     f"length along the axis, which is how far it must move to clear the well")
    return dof


def _turn_miss(point: np.ndarray, pivot: np.ndarray, axis: np.ndarray, degrees: float,
               target: np.ndarray) -> float:
    """How far a turn of `degrees` about `axis` through `pivot` leaves `point`
    from `target`."""
    n = np.linalg.norm(axis)
    if n < 1e-9:
        return float(np.linalg.norm(point - target))
    k = axis / n
    v = point - pivot
    th = math.radians(degrees)
    turned = (v * math.cos(th) + np.cross(k, v) * math.sin(th)
              + k * float(np.dot(k, v)) * (1 - math.cos(th)))
    return float(np.linalg.norm(turned + pivot - target))


def measure_muzzle(model, body_index: int, rest: int, t: Sequence[float]):
    """(muzzle point, barrel direction) in _wm space."""
    body = _verts(model.surfaces[body_index], rest) + np.asarray(t)
    front = body[body[:, 0] >= body[:, 0].max() - MUZZLE_BAND]
    if not len(front):
        front = body
    return tuple(front.mean(axis=0)), (1.0, 0.0, 0.0)


def measure_grab(model, part_surfaces: Sequence[int], rest: int, t: Sequence[float],
                 part_id: str = "") -> Grab:
    """A forend or handle: the grab is the surface centroid, and the seat is
    under it -- the hand closes round the part, so the seat sits at the bottom
    of it rather than in its middle."""
    cloud = _part_cloud(model, part_surfaces, rest) + np.asarray(t)
    c = cloud.mean(axis=0)
    return Grab(part=part_id, grab=tuple(c), handseat=(float(c[0]), float(c[1]),
                                                       float(cloud[:, 2].min())))


def carve_part(model, part_surfaces: Sequence[int], rest: int, t: Sequence[float],
               feed_axis: Sequence[float], out: str, mag_scale: float,
               part_id: str = "", skin: Optional[str] = None) -> Carve:
    """Lift a part into its own single-frame mesh for the loose object.

    The mesh is written on its own centroid and turned so the feed axis points
    at -Z; magcenter is that centroid in _wm space, which is where the part
    sits in the gun, and magscale is the prop's own scale magnitude so the loose
    copy is the same size as the one in the well.
    """
    # By index, never by name: the donor's names repeat.
    MD3.extract(model.source, [], out, axis=list(feed_axis), skin=skin, frame=rest,
                indices=list(part_surfaces))
    cloud = _part_cloud(model, part_surfaces, rest) + np.asarray(t)
    centre = cloud.mean(axis=0)
    back = MD3.MD3Model.load(out)
    pts = np.vstack([np.asarray(s.verts[0], float) for s in back.surfaces])
    extent = float(pts[:, 2].max() - pts[:, 2].min())
    return Carve(part=part_id, out=out, magcenter=tuple(centre), magscale=float(mag_scale),
                 extent=extent, verts=int(len(pts)))
