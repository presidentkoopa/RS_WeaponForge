#!/usr/bin/env python3
"""
motion.py -- what each surface of a donor does, measured against the body.
Step 4 of the WeaponForge Build Guide.

WHY A RIGID FIT AND NOT CENTROIDS

A part's centroid moves when the part translates. It also moves when the whole
gun turns underneath it, and when the part rotates about anything other than
its own centre. Differencing centroids adds those three together and reports
the sum as a translation, which is why an earlier attempt measured a pistol
slide as travelling 9.47 units along (-0.95, -0.27, -0.13) with a per-frame
length that bounced 0, 0.6, 7.6, 5.4, 1.8, 3.4, 9.5. That is not a slide
sliding, it is noise.

A rigid fit (Kabsch) answers the question actually being asked: what single
rotation and translation best carries this part's vertices from one frame to
another. The same slide, fitted, runs dead along one axis.

WHY THE BODY IS DIVIDED OUT FIRST

Every surface of an animated donor moves in model space, because the whole gun
recoils, tilts and is carried around. What matters for a world weapon is what a
part does RELATIVE TO THE GUN. So the body's own fit is solved first and applied
to every other surface before that surface is fitted. What is left is the part's
own travel.

If that leaves every surface still moving, the surface named as the body is
probably not the body. That is a real case: the Brutal Doom minigun's largest
surface is its spinning barrels.

WHAT THIS DOES NOT DO

It does not decide what a part IS. It writes a proposal -- a measured table and
a suggested role per surface -- for the owner to accept or correct in set.py.
Automatic part naming is what carded the wrong parts before; a suggestion in a
file the owner reads is not the same thing as data.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

# A part is "collapsed" on a frame when every vertex sits within this of the
# others -- the convention several donors use to hide a part instead of an
# empty frame.
COLLAPSED = 0.001
# Below this, a fit's rotation is not a turn, it is numerical noise.
PURE_TRANSLATION_DEG = 0.1
# Above this, the surface is not one rigid object and no single axis describes
# it -- usually two parts sharing a surface, which needs an island split.
NOT_RIGID = 0.05
# A hinge past this is not a trigger or a hammer.
SMALL_HINGE_DEG = 40.0
# How dominant an axis has to be before the direction is called "along" it.
AXIS_DOMINANT = 0.9


def rigid_fit(src: np.ndarray, dst: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """The rotation and translation best carrying `src` onto `dst`, and what is
    left over: the RMS per-vertex distance and the worst single one.

    THE RMS IS THE FIT ERROR the guide's numbers are quoted in, and section 7's
    railgun scope is how that was established: its RMS on the frame that fits
    worst is 0.633, which is the table's ~0.63, while the worst single vertex
    there is 1.673. The two say different things and both are worth keeping. A
    handful of vertices torn off a rigid part lift the maximum a long way and
    barely move the RMS, so the RMS is what decides whether a surface is one
    rigid object, and the maximum is what says how badly the odd vertex misses.

    Kabsch: centre both sets, take the SVD of their covariance, and the
    rotation falls out. The determinant guard matters -- without it a noisy or
    near-degenerate set produces a mirror instead of a rotation, which reads as
    a part turning itself inside out.
    """
    if src.shape != dst.shape or src.shape[0] < 3:
        raise ValueError(f"rigid_fit needs matching sets of 3+ points, got {src.shape} "
                         f"and {dst.shape}")
    cs = src.mean(axis=0)
    cd = dst.mean(axis=0)
    H = (src - cs).T @ (dst - cd)
    U, _S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d if d != 0 else 1.0])
    R = Vt.T @ D @ U.T
    t = cd - R @ cs
    dist = np.linalg.norm((src @ R.T + t) - dst, axis=1)
    if not len(dist):
        return R, t, 0.0, 0.0
    return R, t, float(np.sqrt(np.mean(dist ** 2))), float(np.max(dist))


def rotation_angle_axis(R: np.ndarray) -> Tuple[float, np.ndarray]:
    """A rotation matrix as (degrees, unit axis). The axis of a zero rotation
    is meaningless and comes back as zeros rather than as an arbitrary vector
    that a later step might take seriously."""
    cos = (float(np.trace(R)) - 1.0) / 2.0
    cos = max(-1.0, min(1.0, cos))
    ang = math.degrees(math.acos(cos))
    if ang < 1e-9:
        return 0.0, np.zeros(3)
    axis = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    n = np.linalg.norm(axis)
    if n < 1e-12:
        # A half turn: the skew part vanishes, so take the axis from R + I.
        w, v = np.linalg.eigh(R + np.eye(3))
        axis = v[:, int(np.argmax(w))]
        n = np.linalg.norm(axis) or 1.0
    return ang, axis / n


def fixed_point(R: np.ndarray, t: np.ndarray, axis: Optional[np.ndarray] = None) -> np.ndarray:
    """A point the transform leaves where it is -- the pivot.

    For a pure rotation the fixed points form a line, so the system is solved
    in the least-squares sense and, when an axis is given, the component along
    it is removed. That picks the one point on the hinge line closest to the
    origin, which is a definite answer instead of an arbitrary point on a line.
    """
    A = np.eye(3) - R
    try:
        p, *_ = np.linalg.lstsq(A, t, rcond=None)
    except np.linalg.LinAlgError:
        return np.zeros(3)
    if axis is not None and np.linalg.norm(axis) > 1e-9:
        a = axis / np.linalg.norm(axis)
        p = p - float(np.dot(p, a)) * a
    return p


@dataclass
class SurfaceMotion:
    index: int
    name: str
    verts: int
    travel: float = 0.0                 # greatest distance from rest, in map units
    travel_frame: int = 0
    direction: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    turn_at_travel: float = 0.0         # degrees of turn on the travel frame
    angle: float = 0.0                  # greatest turn over all frames
    angle_frame: int = 0
    axis: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    pivot: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    fit_error: float = 0.0              # worst per-frame RMS rigid-fit residual
    fit_worst: float = 0.0              # the worst single vertex on that frame
    fit_error_frame: int = 0
    collapsed_at_rest: bool = False
    collapses_somewhere: bool = False
    is_body: bool = False
    role: str = ""
    notes: List[str] = field(default_factory=list)

    @property
    def dominant_axis(self) -> str:
        """The direction as a signed axis name, when one axis carries it."""
        d = np.array(self.direction, dtype=float)
        if np.linalg.norm(d) < 1e-9:
            return ""
        i = int(np.argmax(np.abs(d)))
        if abs(d[i]) < AXIS_DOMINANT:
            return ""
        return ("-" if d[i] < 0 else "+") + "XYZ"[i]


@dataclass
class GunMotion:
    gun: str
    md3: str
    rest_frame: int
    frames: int
    body_index: int
    surfaces: List[SurfaceMotion] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _surface_array(surf, frame: int) -> np.ndarray:
    return np.asarray(surf.verts[frame], dtype=float)


def measure_motion(model, body_index: int, rest_frame: int, gun: str = "") -> GunMotion:
    """Measure every surface of `model` against the surface named by
    `body_index`, at `rest_frame`."""
    n_surf = len(model.surfaces)
    if not (0 <= body_index < n_surf):
        raise ValueError(f"{gun}: body #{body_index} is not one of this model's "
                         f"{n_surf} surfaces")
    body = model.surfaces[body_index]
    frames = min(model.num_frames, min(s.num_frames for s in model.surfaces))
    if not (0 <= rest_frame < frames):
        raise ValueError(f"{gun}: rest frame {rest_frame} is outside the {frames} frames "
                         f"every surface of this model has")

    out = GunMotion(gun=gun or os.path.basename(model.source), md3=model.source,
                    rest_frame=rest_frame, frames=frames, body_index=body_index)

    body_rest = _surface_array(body, rest_frame)
    # The body's own motion, per frame, as the transform carrying that frame
    # back onto the rest pose.
    body_fit = {}
    for f in range(frames):
        if f == rest_frame:
            body_fit[f] = (np.eye(3), np.zeros(3), 0.0)
            continue
        Rb, tb, err, _worst = rigid_fit(_surface_array(body, f), body_rest)
        body_fit[f] = (Rb, tb, err)
        if err > NOT_RIGID:
            out.warnings.append(
                f"the body itself does not fit rigidly on frame {f} (worst {err:.3f}) -- "
                f"either the body surface is two parts, or '{body.name}' is not the body")

    moving = 0
    for si, surf in enumerate(model.surfaces):
        m = SurfaceMotion(index=si, name=surf.name, verts=surf.num_verts,
                          is_body=(si == body_index))
        rest = _surface_array(surf, rest_frame)
        rest_c = rest.mean(axis=0)
        m.collapsed_at_rest = bool(
            np.max(rest.max(axis=0) - rest.min(axis=0)) < COLLAPSED) if len(rest) else True

        for f in range(frames):
            if f == rest_frame:
                continue
            Rb, tb, _ = body_fit[f]
            here = _surface_array(surf, f)
            if len(here) < 3:
                continue
            if np.max(here.max(axis=0) - here.min(axis=0)) < COLLAPSED:
                m.collapses_somewhere = True
                # A collapsed frame carries no pose: fitting it would report a
                # part that has travelled past where its geometry could reach.
                continue
            corrected = here @ Rb.T + tb          # the body's motion divided out
            Rs, ts, err, worst = rigid_fit(corrected, rest)
            if err > m.fit_error:
                m.fit_error, m.fit_worst, m.fit_error_frame = err, worst, f

            travel = float(np.linalg.norm(corrected.mean(axis=0) - rest_c))
            if travel > m.travel:
                m.travel, m.travel_frame = travel, f
                d = corrected.mean(axis=0) - rest_c
                m.direction = tuple((d / travel) if travel > 1e-9 else np.zeros(3))
                m.turn_at_travel, _ = rotation_angle_axis(Rs)

            ang, ax = rotation_angle_axis(Rs)
            if ang > m.angle:
                m.angle, m.angle_frame = ang, f
                m.axis = tuple(ax)
                m.pivot = tuple(fixed_point(Rs, ts, ax))

        if not m.is_body and (m.travel > 0.05 or m.angle > PURE_TRANSLATION_DEG):
            moving += 1
        out.surfaces.append(m)

    if n_surf > 2 and moving == n_surf - 1:
        out.warnings.append(
            f"every surface moves relative to '{body.name}' -- the body is probably wrong "
            f"(the minigun's largest surface is its spinning barrels, not its frame)")

    for m in out.surfaces:
        _suggest(m)
    return out


def _suggest(m: SurfaceMotion) -> None:
    """A suggested role, in the guide's words. A suggestion, never data."""
    if m.is_body:
        m.role = "body"
        return
    if m.fit_error > NOT_RIGID:
        m.role = "not rigid: needs an island split"
        m.notes.append(f"RMS {m.fit_error:.3f}, worst vertex {m.fit_worst:.3f}, "
                       f"on frame {m.fit_error_frame}")
        return
    if m.collapsed_at_rest:
        m.role = "hidden"
        m.notes.append("collapsed at the rest frame")
        return
    if m.travel < 0.05 and m.angle < PURE_TRANSLATION_DEG:
        m.role = "fixed"
        return
    pure = m.turn_at_travel < PURE_TRANSLATION_DEG
    axis = m.dominant_axis
    if pure and axis == "-Z":
        m.role = "magazine"
    elif pure and axis == "-X":
        m.role = "slide / bolt / pump / handle"
    elif pure and m.direction[2] < -0.7:
        m.role = "magazine"
        m.notes.append("mostly downward, not on one axis")
    elif m.angle <= SMALL_HINGE_DEG and m.angle >= PURE_TRANSLATION_DEG:
        m.role = "trigger or hammer"
    elif pure:
        m.role = "slides, but not along one axis"
    else:
        m.role = f"turns {m.angle:.1f} deg -- needs a ruling"
    if m.collapses_somewhere:
        m.notes.append("collapsed on some frame: may be hidden mid-animation")


def write_proposal(path: str, motion: GunMotion) -> str:
    """The proposal file the owner reads before writing a part map."""
    lines = []
    lines.append(f"{motion.gun}: what each surface does, measured against "
                 f"#{motion.body_index} at the rest frame")
    lines.append(f"  mesh        {motion.md3}")
    lines.append(f"  rest frame  {motion.rest_frame} of {motion.frames}")
    lines.append(f"  body        #{motion.body_index} "
                 f"'{motion.surfaces[motion.body_index].name}'")
    lines.append("")
    lines.append("  These are MEASUREMENTS and a SUGGESTION. Nothing here reaches the card")
    lines.append("  until it is written into set.py by hand.")
    lines.append("")
    head = (f"  {'#':>3} {'surface':22} {'verts':>6} {'travel':>8} {'@f':>4} {'direction':>22} "
            f"{'turn':>7} {'fit':>7} {'worst':>7}  suggestion")
    lines.append(head)
    lines.append("  " + "-" * (len(head) - 2))
    for m in motion.surfaces:
        d = f"({m.direction[0]:+.2f},{m.direction[1]:+.2f},{m.direction[2]:+.2f})"
        ax = m.dominant_axis
        if ax:
            d += f" {ax}"
        lines.append(f"  {m.index:>3} {m.name[:22]:22} {m.verts:>6} {m.travel:>8.2f} "
                     f"{m.travel_frame:>4} {d:>22} {m.angle:>6.1f}d {m.fit_error:>7.3f} {m.fit_worst:>7.3f}  "
                     f"{m.role}")
        for note in m.notes:
            lines.append(f"      {' ' * 65}{note}")
    if motion.warnings:
        lines.append("")
        lines.append("  WARNINGS")
        for w in motion.warnings:
            lines.append(f"    - {w}")
    text = "\n".join(lines) + "\n"
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text
