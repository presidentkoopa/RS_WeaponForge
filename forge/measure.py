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
                     NOT_RIGID,
                     SMALL_HINGE_DEG)

MUZZLE_BAND = 0.5          # how deep a slice of the barrel's front face to average
# A frame counts as pure translation when its turn BARELY MOVES the part: the
# arc a vertex travels, radius times the angle, against the part's travel. A flat
# angle gate is the wrong test at both ends -- 0.1 degrees swings a 30-unit drum
# by 0.05, and on a trigger 1.5 units across it is 0.003, which is nothing. The
# shipped machinegun card is the case that shows it: "axis = -1, 0, -0.008,
# distance = 0.598" is its frame 5, whose turn measures 0.11 degrees, so a 0.1
# gate throws away the frame the card was written from and takes 0.392 instead.
PURE_ARC_FRACTION = 0.05
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
    radius: float = 3.0


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


def turn_is_negligible(cloud: np.ndarray, degrees: float, travel: float) -> bool:
    """Whether a frame's turn is small enough to call the motion a translation.

    The arc the outermost vertex travels is radius x angle. Compared against how
    far the part moved, that says whether the turn matters, which a bare angle
    cannot: see PURE_ARC_FRACTION.
    """
    if degrees <= 0.0:
        return True
    radius = float(np.max(np.linalg.norm(cloud - cloud.mean(axis=0), axis=1)))
    arc = radius * math.radians(degrees)
    return arc <= max(PURE_ARC_FRACTION * travel, 1.0 / 64.0)


def measure_dof(model, body_index: int, rest: int, part_id: str,
                part_surfaces: Sequence[int], t: Sequence[float],
                kind: str = "auto", _split_ok: bool = True) -> DOF:
    """The slide or hinge of one part, with the body's motion divided out.

    A PART WHOSE SURFACES DO NOT MOVE AS ONE BODY is measured on its largest
    surface, and the others are reported. The rifle's charging handle is the
    case: its handle and its dust cover both slide along -x, but 7.117 and
    10.439 respectively, so fitted together as one rigid body they cannot fit at
    all (error 1.366) and the fit reports a 3-degree turn about nothing. Its
    shipped card carries 7.117 -- the handle. Most of the geometry is the part;
    the rest is along for the ride, and saying so is better than averaging two
    motions into a third that neither surface makes.
    """
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

        if turn_is_negligible(corrected, deg, travel) and travel > best_pure[0]:
            best_pure = (travel, f, disp / travel if travel > 1e-9 else np.zeros(3))
        if deg > best_turn[0]:
            best_turn = (deg, f, axis, fixed_point(Rs, ts, axis), rms)

    # Do the surfaces move as one body? If not, fall back to the largest.
    if _split_ok and len(part_surfaces) > 1:
        probe = measure_dof(model, body_index, rest, part_id, part_surfaces, t, kind,
                            _split_ok=False)
        if probe.fit > NOT_RIGID:
            biggest = max(part_surfaces, key=lambda i: model.surfaces[i].num_verts)
            out = measure_dof(model, body_index, rest, part_id, [biggest], t, kind,
                              _split_ok=False)
            others = []
            for i in part_surfaces:
                if i == biggest:
                    continue
                one = measure_dof(model, body_index, rest, part_id, [i], t, kind,
                                  _split_ok=False)
                others.append(f"#{i} '{model.surfaces[i].name}' {one.kind} "
                              f"{one.distance:.3f} / {one.degrees:.2f} deg")
            out.notes.append(f"these surfaces do not move as one body (fitted together, "
                             f"{probe.fit:.3f} off); measured on #{biggest} "
                             f"'{model.surfaces[biggest].name}', the largest. The others: "
                             + "; ".join(others))
            return out

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
        disp = corrected.mean(axis=0) - rest_c
        travel = float(np.linalg.norm(disp))
        if not turn_is_negligible(corrected, deg, travel):
            continue
        if travel > 0.05:
            samples.append((travel, f, disp / travel))

    dof = DOF(part=part_id, kind="feed")
    if not samples:
        dof.notes.append("no frame moves this part in a straight line")
        return dof
    furthest = max(s[0] for s in samples)
    leg = [s for s in samples if s[0] >= fraction * furthest]
    travel, frame, direction = min(leg or samples, key=lambda s: s[0])
    # A MAGAZINE FEEDS IN THE GUN'S MID-PLANE. Model space is x along the barrel,
    # y across, z up, and a magazine drops straight down the well rather than
    # sideways out of it, so a small y on a feed axis is the animation rocking the
    # magazine in, not a direction the part travels.
    #
    # The shipped cards are written that way and it is exact: the plasma cell's
    # card axis (0.1942, 0, -0.9810) is our measured (0.194, -0.041, -0.980) with
    # y dropped and renormalised, and its distance 12.33 is the cell's length
    # along THAT axis (12.326) rather than along the tilted one (12.446). The
    # grenade pin's (0, 1, 0) is ours with a 0.011 z dropped. This is a rule about
    # a FEED axis, not about axes generally -- the RPG's trigger card keeps a
    # -0.011 in z, so nothing else is snapped.
    direction = np.asarray(direction, dtype=float)
    if 0.0 < abs(direction[1]) < 0.05:
        dof.notes.append(f"y of {direction[1]:+.3f} dropped: a magazine feeds in the gun's "
                         f"mid-plane")
        direction[1] = 0.0
        direction = direction / np.linalg.norm(direction)
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


GRAB_BAND = 2.0          # how deep a slice of the part's trailing end to average
# How close a hand has to be to take the part. This is a COMFORT NUMBER, not a
# measurement: a hand is a hand. It narrows for a small part so that two nearby
# parts on the same gun do not both answer to the same reach.
GRAB_RADIUS_BY_SIZE = ((10.0, 3.0), (6.0, 2.5), (0.0, 2.0))


def measure_grab(model, part_surfaces: Sequence[int], rest: int, t: Sequence[float],
                 part_id: str = "", axis: Optional[Sequence[float]] = None,
                 hinge: bool = False) -> Grab:
    """Where a hand takes this part.

    WITH AN AXIS -- a part that slides, hinges or feeds -- the grab is the mean of
    the vertices at the part's TRAILING end along that axis: the end that leads as
    the part comes toward you, which is the end you can actually get hold of. That
    is a charging handle's rear and a magazine's floorplate, and it reproduces the
    shipped cards exactly: the SMG magazine's 0.94, -0.16, -22.23 and the rifle
    handle's -16.48, 0.97, 2.59, both to the digit, with a two-unit band.

    ON A HINGE there is no travel direction to trail, and what you take is the
    forward tip: the SMG's folding charging handle is grabbed at its front, and
    the mean of the vertices within one unit of the part's greatest x reproduces
    its card exactly -- 20.16, 2.81, 3.65.

    WITHOUT EITHER -- a forend, a support -- the grab is the centroid, because a
    hand wraps the middle of a forend rather than pulling its end.

    The seat is under the grab: the hand closes round the part, so it sits at the
    bottom of it rather than in its middle.
    """
    cloud = _part_cloud(model, part_surfaces, rest) + np.asarray(t)
    if hinge:
        front = cloud[cloud[:, 0] >= cloud[:, 0].max() - 1.0]
        c = front.mean(axis=0) if len(front) else cloud.mean(axis=0)
    elif axis is not None and np.linalg.norm(np.asarray(axis, dtype=float)) > 1e-9:
        a = np.asarray(axis, dtype=float)
        a = a / np.linalg.norm(a)
        p = cloud @ a
        end = cloud[p >= p.max() - GRAB_BAND]
        c = end.mean(axis=0) if len(end) else cloud.mean(axis=0)
    else:
        c = cloud.mean(axis=0)
    span = float(np.max(cloud.max(axis=0) - cloud.min(axis=0)))
    radius = next(r for lim, r in GRAB_RADIUS_BY_SIZE if span >= lim)
    return Grab(part=part_id, grab=tuple(c), radius=radius,
                handseat=(float(c[0]), float(c[1]), float(cloud[:, 2].min())))


@dataclass
class Ejection:
    port: Tuple[float, float, float]
    direction: Tuple[float, float, float]
    side: int                      # -1 or +1: which side of the gun the brass leaves
    counts: Tuple[int, int] = (0, 0)
    note: str = ""


# The shape of an ejection: mostly out the side, a little up, a little back. These
# are the proportions the shipped cards use, and they are an ESTIMATE in those
# cards' own words -- brass leaving a port has a direction nothing in a static
# mesh records.
EJECT_SHAPE = (-0.3, 0.9, 0.4)


def measure_ejection(model, body_index: int, rest: int, t: Sequence[float],
                     action_surfaces: Optional[Sequence[int]] = None,
                     feed_surfaces: Optional[Sequence[int]] = None) -> Ejection:
    """Where the brass leaves, and which way.

    THE SIDE IS MEASURED. A charging handle sits on one side of the receiver and
    the port on the other -- the shipped SMG card says so and counts the vertices
    to prove it: "299 on -y against 461 on +y, where the charging handle is: the
    port is on -y, the side away from the handle". With an action part named, its
    own side answers the question directly; without one, the emptier wall of the
    receiver does, since a port is a hole and a hole has fewer vertices around it.

    THE POINT AND THE DIRECTION ARE ESTIMATES, as they are in every shipped card
    that carries them. The point is put on the receiver wall on the port side, at
    the height and along the length of the action; the direction is out of that
    side with a little up and back. Nothing in a mesh at rest records where brass
    actually leaves, so this is a considered placement and is written down as one.
    """
    body = _part_cloud(model, [body_index], rest) + np.asarray(t, dtype=float)
    if action_surfaces:
        act = _part_cloud(model, action_surfaces, rest) + np.asarray(t, dtype=float)
        # THE PORT IS AT THE BREECH, not at the handle. A charging handle can sit a
        # long way forward of the chamber -- the SMG's reaches x 20 while its card
        # puts the port at 0 -- so the length along the gun comes from the FEED: a
        # round comes up out of the magazine into the chamber and the empty leaves
        # beside it. The handle only answers which SIDE.
        z0, z1 = float(act[:, 2].min()) - 2.0, float(act[:, 2].max()) + 2.0
        side = -1 if float(act[:, 1].mean()) > 0 else 1
        why = "the side away from the action"
        if feed_surfaces:
            fed = _part_cloud(model, feed_surfaces, rest) + np.asarray(t, dtype=float)
            mid = float(fed[:, 0].mean())
            half = max(2.0, float(fed[:, 0].max() - fed[:, 0].min()) / 2.0)
            x0, x1 = mid - half, mid + half
        else:
            x0, x1 = float(act[:, 0].min()), float(act[:, 0].max())
    else:
        lo, hi = float(body[:, 0].min()), float(body[:, 0].max())
        x0, x1 = lo + (hi - lo) / 3.0, hi - (hi - lo) / 3.0
        zl, zh = float(body[:, 2].min()), float(body[:, 2].max())
        z0, z1 = zl + (zh - zl) / 4.0, zh - (zh - zl) / 4.0
        side = 0
        why = "the emptier wall of the receiver"
    band = body[(body[:, 0] >= x0) & (body[:, 0] <= x1)
                & (body[:, 2] >= z0) & (body[:, 2] <= z1)]
    if not len(band):
        band = body
    neg = int((band[:, 1] < 0).sum())
    pos = int((band[:, 1] > 0).sum())
    if side == 0:
        side = -1 if neg < pos else 1
    wall = band[band[:, 1] < 0] if side < 0 else band[band[:, 1] > 0]
    if not len(wall):
        wall = band
    y = float(wall[:, 1].min()) if side < 0 else float(wall[:, 1].max())
    port = (float(wall[:, 0].mean()), y, float(wall[:, 2].mean()))
    d = np.array([EJECT_SHAPE[0], side * EJECT_SHAPE[1], EJECT_SHAPE[2]], dtype=float)
    d = d / np.linalg.norm(d)
    return Ejection(port=port, direction=tuple(d), side=side, counts=(neg, pos),
                    note=f"side measured ({neg} vertices on -y against {pos} on +y), "
                         f"{why}; the point and the direction are estimates")


def measure_support(model, body_index: int, rest: int, t: Sequence[float],
                    feed_surfaces: Optional[Sequence[int]] = None) -> Grab:
    """Where the off hand goes: under the handguard.

    THE HEIGHT IS MEASURED -- the underside of the body at that point, which is
    what a palm rests against, and it lands within half a unit of the shipped
    cards on three of the four that carry one.

    THE LENGTH ALONG THE GUN IS AN ESTIMATE, and the shipped cards say the same of
    theirs: "ESTIMATE: where the other hand goes", "ESTIMATE for the placement
    page". Three derivations were tried against those cards -- the middle of the
    flat underside, the midpoint from the magazine to the muzzle, and the middle
    of the thick part of the body -- and each fits some guns and misses others by
    ten units, because the shipped numbers were placed per gun by eye. The one
    below is the middle of the body's THICK run forward of the magazine: a
    handguard is thick and a barrel is thin, so that is the stretch a hand can
    actually hold. On the assault shotgun it lands 0.5 off the shipped value.

    This is the number to check in the headset. It is written as an estimate
    rather than left out, because an off hand with nowhere to go is worse than one
    with a considered place to start.
    """
    body = _part_cloud(model, [body_index], rest) + np.asarray(t, dtype=float)
    x = body[:, 0]
    lo, hi = float(x.min()), float(x.max())
    bins = 40
    edges = np.linspace(lo, hi, bins + 1)
    area = np.zeros(bins)
    for i in range(bins):
        sel = body[(x >= edges[i]) & (x < edges[i + 1])]
        if len(sel) >= 4:
            area[i] = float((sel[:, 1].max() - sel[:, 1].min())
                            * (sel[:, 2].max() - sel[:, 2].min()))
    thick = area.max() or 1.0
    front = lo
    if feed_surfaces:
        fed = _part_cloud(model, feed_surfaces, rest) + np.asarray(t, dtype=float)
        front = float(fed[:, 0].max())
    start = int(np.searchsorted(edges, front))
    end = start
    for i in range(start, bins):
        if area[i] >= 0.5 * thick:
            end = i
    x1 = float(edges[min(end + 1, bins)])
    xs = (front + x1) / 2.0
    near = body[(body[:, 0] >= xs - 2.0) & (body[:, 0] <= xs + 2.0)]
    z = float(near[:, 2].min()) if len(near) else float(body[:, 2].min())
    return Grab(part="support", grab=(xs, 0.0, z), radius=3.0,
                handseat=(xs, 0.0, z))


LOAD_FACES = {"under": (0, 0, -1), "left": (0, -1, 0), "right": (0, 1, 0),
              "breech": (-1, 0, 0)}
# A gate is a hand-sized opening; the shipped cards use this box and it is a
# comfort figure, not a measurement.
LOAD_GATE_SIZE = (2.5, 1.5, 2.0)


def measure_load(model, body_index: int, rest: int, t: Sequence[float], where: str,
                 feed_surfaces: Optional[Sequence[int]] = None):
    """Where a round goes in, on the face the set file names.

    THE FACE IS THE DECISION -- a pump shotgun loads underneath, a break-action at
    its breech -- and the point on it is measured: the body's own surface on that
    face, at the breech along the gun. The direction is into the gun, normal to
    the face, which is the way a round is pushed.
    """
    body = _part_cloud(model, [body_index], rest) + np.asarray(t, dtype=float)
    n = np.asarray(LOAD_FACES.get(where, LOAD_FACES["under"]), dtype=float)
    x = body[:, 0]
    if feed_surfaces:
        fed = _part_cloud(model, feed_surfaces, rest) + np.asarray(t, dtype=float)
        mid = float(fed[:, 0].mean())
    else:
        mid = float((x.min() + x.max()) / 2.0)
    if where == "breech":
        # The breech is the rear face of the receiver, so the point is the back of
        # the body's thick run rather than a point along its length.
        band = body[x <= float(np.percentile(x, 25))]
        at = band.mean(axis=0) if len(band) else body.mean(axis=0)
        return tuple(at), tuple(-n)
    band = body[(x >= mid - 3.0) & (x <= mid + 3.0)]
    if not len(band):
        band = body
    axis = int(np.argmax(np.abs(n)))
    edge = band[:, axis].min() if n[axis] < 0 else band[:, axis].max()
    at = list(band.mean(axis=0))
    at[axis] = float(edge)
    return tuple(at), tuple(-n)


CLEARANCE_SPARE = 0.5      # a little past the obstruction, so it is not grazing it


def measure_clearance(model, body_index: int, rest: int, part_surfaces: Sequence[int],
                      t: Sequence[float], part_id: str = "") -> DOF:
    """How far a part must move to come clear of the body, when no frame moves it.

    Several donors never animate the magazine leaving. The shipped cards measure
    those from the geometry instead, and say so: the Unmaker's skull "lifts
    STRAIGHT UP (+z) ... to come clear", the grenade's pin needs 5.92 because "the
    body reaches y 3.94 ... the pin's trailing end starts at y -1.48. 5.92 along
    +y puts the trailing end past both with half a unit to spare".

    So: of the six axes, take the one where the part has the shortest run to clear
    everything the body puts inside its own footprint, and add that half unit. This
    is a measurement of the mesh, not a guess -- but it is a measurement of where
    the part CAN go, not of where the author moved it, and it says so on the card.
    """
    part = _part_cloud(model, part_surfaces, rest) + np.asarray(t, dtype=float)
    body = _part_cloud(model, [body_index], rest) + np.asarray(t, dtype=float)
    lo, hi = part.min(axis=0), part.max(axis=0)
    best = None
    for axis in range(3):
        for sign in (+1, -1):
            other = [a for a in range(3) if a != axis]
            inside = body
            for a in other:
                inside = inside[(inside[:, a] >= lo[a]) & (inside[:, a] <= hi[a])]
            if not len(inside):
                need = 0.0
            elif sign > 0:
                need = float(inside[:, axis].max() - lo[axis])
            else:
                need = float(hi[axis] - inside[:, axis].min())
            if need <= 0:
                continue
            if best is None or need < best[0]:
                best = (need, axis, sign)
    dof = DOF(part=part_id, kind="feed")
    if best is None:
        dof.notes.append("nothing in the body obstructs this part on any axis")
        return dof
    need, axis, sign = best
    v = [0.0, 0.0, 0.0]
    v[axis] = float(sign)
    dof.axis = tuple(v)
    dof.distance = need + CLEARANCE_SPARE
    dof.notes.append(f"no frame moves this part; {dof.distance:.2f} along "
                     f"{'+' if sign > 0 else '-'}{'xyz'[axis].upper()} is what clears the body "
                     f"inside its own footprint, with {CLEARANCE_SPARE} to spare")
    return dof


def index_step(chambers: int) -> float:
    """A revolving feed's step: the circle divided by its chambers.

    The RPG's drum turns a seventh of a turn for every rocket short of seven, and
    its shipped card carries -51.43 for exactly that reason -- the count, not the
    animation, which turns it 76.74. Nothing in a mesh's symmetry gives this
    either: the drum's own geometry does not land on itself at 51.43.
    """
    return 360.0 / max(1, int(chambers))


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
