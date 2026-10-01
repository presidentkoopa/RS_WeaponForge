#!/usr/bin/env python3
"""grip_fit.py -- the hand's hold on a grip: its axis, its twist and its cross-section,
from ONE fit of the mesh around the card's seat.

WHY ONE FIT AND NOT TWO MEASUREMENTS. A grip's thickness is the cross-section
PERPENDICULAR TO THE GRIP AXIS, so a thickness measured before the axis is known is cut in
whatever plane happened to be handy -- across the bore on every pistol. Fitting the axis
and the section together removes the ordering entirely: the section is perpendicular to the
fitted axis by construction.

WHY NOT A PRINCIPAL AXIS THROUGH A BALL. That was tried first and it fails, measurably.
Sweeping the ball's radius as a fraction of each gun's length over all 25 BD22 guns:

    radius 0.08 x length :  2 of 25 give a strong axis
    radius 0.12          :  7 of 25
    radius 0.18          : 12 of 25
    radius 0.25          : 14 of 25

The axis gets STRONGER as the region grows, because the cloud becomes a quarter of the
weapon and its principal axis is the BARREL. The shotgun ran 1.58 -> 2.18 -> 3.49 -> 4.40
as the ball opened; nothing about its grip got clearer. A ball cannot separate a handle
from a gun, so the best setting is the one that most reliably measures the wrong thing.

WHAT A GRIP ACTUALLY IS: a run of mesh, near the seat, of roughly constant and SMALL
cross-section, extended along one direction. So the region is a CAPSULE, not a ball --
bounded tightly across the axis and loosely along it -- and it is grown iteratively from
the seat. A capsule cannot wander down the barrel, because the barrel lies outside the
perpendicular bound and off the seat's own line.

NEVER FROM A PICTURE. A gun base rotation once shipped 45 degrees out because it came from
a render, caught only in a headset. A wrong hold reads as solved and gets trusted; an
absent one reads as unsolved and gets solved. So this refuses -- see `GripFit.ok` and the
residual gate -- rather than returning its best guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

# THE CAPSULE. Across the axis: a handle a hand closes round is a few units thick, and
# anything past this is the frame it hangs off. Along the axis: a grip is a palm's width
# and a bit. Mesh units.
PERP_MAX = 3.6
ALONG_MAX = 7.0
# Fewer than this in the capsule and there is no surface to fit.
MIN_VERTS = 40
# How round-ish a handle has to be. The cross-section's major half-extent over its minor:
# a grip is oblong (a pistol's is markedly deeper than wide) but a FLAT plate is not a
# handle at all.
FLATNESS_MAX = 3.2
# How well the section has to hold its shape ALONG the run. A handle keeps roughly the
# same section; a flare, a trigger guard or an open void does not. Fraction of the minor
# half-extent, so it scales with the grip.
SECTION_DRIFT_MAX = 0.45
ITERATIONS = 6


@dataclass
class GripFit:
    """One hold, or why there isn't one."""
    ok: bool = False
    why: str = ""
    axis: Optional[tuple] = None        # unit vector, mesh space, card axes
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0                   # never solved from geometry; see euler_from_axis
    major: float = 0.0                  # half-extent across the axis, wide way
    minor: float = 0.0                  # half-extent across the axis, narrow way
    clock: float = 0.0                  # degrees of the major axis in the seat frame
    verts: int = 0
    drift: float = 0.0
    notes: List[str] = field(default_factory=list)


def _basis(axis: np.ndarray):
    """Two unit vectors spanning the plane perpendicular to `axis`.

    The first is taken from whichever world axis is least parallel to `axis`, so the pair
    is stable rather than flipping between neighbouring fits.
    """
    a = axis / np.linalg.norm(axis)
    seed = np.eye(3)[int(np.argmin(np.abs(a)))]
    u = np.cross(a, seed)
    u /= np.linalg.norm(u)
    v = np.cross(a, u)
    return u, v


def _capsule(pts: np.ndarray, seat: np.ndarray, axis: np.ndarray,
             perp: float, along: float) -> np.ndarray:
    d = pts - seat
    t = d @ axis
    radial = np.linalg.norm(d - np.outer(t, axis), axis=1)
    return pts[(np.abs(t) <= along) & (radial <= perp)]


def _section(cloud: np.ndarray, seat: np.ndarray, axis: np.ndarray):
    """The cross-section perpendicular to `axis`: half-extents and the major's clock angle.

    Half-extents are taken at the 92nd percentile rather than the maximum: one stray
    vertex on a sight rail should not widen a grip by a third.
    """
    u, v = _basis(axis)
    d = cloud - seat
    flat = np.column_stack([d @ u, d @ v])
    c = flat - flat.mean(axis=0)
    _uu, _s, vt = np.linalg.svd(c, full_matrices=False)
    maj_dir, min_dir = vt[0], vt[1]
    maj = float(np.percentile(np.abs(c @ maj_dir), 92))
    mnr = float(np.percentile(np.abs(c @ min_dir), 92))
    clock = float(np.degrees(np.arctan2(maj_dir[1], maj_dir[0])))
    return maj, mnr, clock, flat


def _drift(cloud: np.ndarray, seat: np.ndarray, axis: np.ndarray) -> float:
    """How much the section changes along the run, as a fraction of the minor half-extent.

    A handle holds its shape; a flare or a void does not. This is the refusal test that
    replaced an elongation ratio, which passed a 1.60 that was noise on both BFGs.
    """
    d = cloud - seat
    t = d @ axis
    if t.max() - t.min() < 1e-6:
        return float("inf")
    edges = np.linspace(t.min(), t.max(), 4)
    mins = []
    for i in range(3):
        band = cloud[(t >= edges[i]) & (t <= edges[i + 1])]
        if len(band) < 8:
            return float("inf")
        _maj, mnr, _clk, _f = _section(band, seat, axis)
        mins.append(mnr)
    base = float(np.mean(mins))
    return float((max(mins) - min(mins)) / base) if base > 1e-6 else float("inf")


def run_length(pts, centre, axis, major):
    """The axial extent of the run the fit sits on, in mesh units.

    Measured from the vertices near the AXIS rather than from the capsule, because the
    capsule is a search box: its length is a setting, and reporting it back as the
    handle's length would just be reporting the setting.
    """
    d = pts - centre
    t = d @ axis
    radial = np.linalg.norm(d - np.outer(t, axis), axis=1)
    near = t[radial <= major * RUN_WIDE]
    if len(near) < 8:
        return 0.0
    return float(np.percentile(near, 97) - np.percentile(near, 3))


def _orient(axis: np.ndarray) -> np.ndarray:
    """Point the axis DOWN the grip. An SVD axis has no sign; a grip hangs downward."""
    if abs(axis[2]) > 1e-6:
        return axis if axis[2] < 0 else -axis
    return axis if axis[0] < 0 else -axis


def euler_from_axis(axis: np.ndarray) -> tuple:
    """yaw, pitch that carry straight-down (0, 0, -1) onto `axis`, in degrees.

    ROLL IS RETURNED 0 AND THAT IS DELIBERATE. One axis fixes two degrees of freedom; the
    third is the hand's spin about the grip, which no axis can tell you -- the finding
    already on record that a grip has three degrees of freedom and the gun fixes two. The
    cross-section's clock angle is reported separately and is the honest place to take a
    roll from later, because an oblong grip DOES imply one.
    """
    a = axis / np.linalg.norm(axis)
    pitch = 90.0 - float(np.degrees(np.arcsin(np.clip(-a[2], -1.0, 1.0))))
    yaw = float(np.degrees(np.arctan2(a[1], a[0]))) if (abs(a[0]) + abs(a[1])) > 1e-9 else 0.0
    return round(yaw, 3), round(pitch, 3), 0.0


def fit_grip(model, surfaces: Sequence[int], rest: int, t: Sequence[float],
             seat: Sequence[float], perp: float = PERP_MAX,
             along: float = ALONG_MAX) -> GripFit:
    """Fit a handle to the mesh around the seat. Refuses when it is not one."""
    from .measure import _part_cloud

    pts = _part_cloud(model, surfaces, rest) + np.asarray(t, dtype=float)
    s = np.asarray(seat, dtype=float)
    out = GripFit()

    # SEEDED STRAIGHT DOWN, because that is where a grip runs on every gun measured: the
    # seat sits below the bore line on all 25 BD22 guns. Then refined.
    axis = np.array([0.0, 0.0, -1.0])
    cloud = np.empty((0, 3))
    for _i in range(ITERATIONS):
        cloud = _capsule(pts, s, axis, perp, along)
        if len(cloud) < MIN_VERTS:
            break
        c = cloud - cloud.mean(axis=0)
        _u, _sv, vt = np.linalg.svd(c, full_matrices=False)
        nxt = _orient(vt[0])
        if float(np.dot(nxt, axis)) > 0.9999:
            axis = nxt
            break
        axis = nxt

    out.verts = int(len(cloud))
    if len(cloud) < MIN_VERTS:
        out.why = (f"only {len(cloud)} vertices in a {perp} x {along} capsule at the seat -- "
                   f"there is no handle there to fit")
        return out

    cloud = _capsule(pts, s, axis, perp, along)
    out.verts = int(len(cloud))
    maj, mnr, clock, _flat = _section(cloud, s, axis)
    out.major, out.minor, out.clock = round(maj, 3), round(mnr, 3), round(clock, 2)

    if mnr < 1e-3:
        out.why = "the section has no thickness -- the seat is on a flat face, not a handle"
        return out
    flat = maj / mnr
    if flat > FLATNESS_MAX:
        out.why = (f"the section is {flat:.2f} times wider than it is thick -- past "
                   f"{FLATNESS_MAX} that is a plate, not something a fist closes round")
        return out

    out.drift = round(_drift(cloud, s, axis), 3)
    if out.drift > SECTION_DRIFT_MAX:
        out.why = (f"the section changes by {out.drift:.2f} of its own thickness along the "
                   f"run -- a handle holds its shape, so this is a flare or a void")
        return out

    out.ok = True
    out.axis = tuple(round(float(v), 6) for v in axis)
    out.yaw, out.pitch, out.roll = euler_from_axis(axis)
    out.notes.append(
        f"{out.verts} vertices in a {perp} x {along} capsule; section {out.major:.2f} x "
        f"{out.minor:.2f} at {out.clock:+.1f} deg, holding to {out.drift:.2f} along the run")
    return out


# ---------------------------------------------------------------- finding a handle

# HOW WIDE A FIST IS, as a half-extent across the grip, in mesh units. The measured grips
# that survived every other test on BD22 ran 1.16 to 2.59 minor; outside this band a run
# of mesh is a barrel, a pin or a body panel rather than something a hand closes on.
# THE NARROW WAY ACROSS what a hand closes on, in MAP units. A grip is rarely under 1.5 cm
# or over 5.5 cm on its short axis. Kept as map units so it means the same thing on a model
# at scale 0.34 and one at 1.35.
FIST_MU_MIN = 0.50
FIST_MU_MAX = 1.85
FIST_MIN = 1.0
FIST_MAX = 2.7
# How far past the end of a fitted handle to look for more mesh, and how big a ball to
# look in. See free_end.
END_STEP = 2.5
END_BALL = 3.0
# Below this many vertices past an end, that end is FREE -- the mesh stops there.
END_FREE_MAX = 6
# How far off the bore a run has to hang before it can be a trigger grip, in degrees.
# A slide or a barrel is a few degrees off; a pistol grip is 50-80.
RAKE_MIN = 30.0
# A PALM, in map units: 0.10 m across at 34 map units per metre. Divide by a gun's
# MODELDEF scale for mesh units.
PALM_MAP = 3.40
# How long a handle may be, in palms. One hand closing round something leaves nothing
# over, so a grip runs about a palm; past this it is a bar, a tube or a barrel.
PALM_MIN = 0.65
PALM_MAX = 1.9
# Past PALM_MAX a run may still be a handle, but only a two-handed one -- a chainsaw's
# rear handle, an axe haft, a sword grip. Allowed up to here ONLY with a single free end
# and a passing width, because what the maximum was really excluding was barrels and bars,
# and those fail the width rule and have no free end.
PALM_LONG = 4.0

# WHAT A HAND CLOSES ON, in MAP units: 2.5 to 4.5 cm, and a map unit is about 2.94 cm.
# A fact about hands, so it holds whatever a model's scale is. Full width, not half.
GRIP_W_MIN = 0.85
# 2.04 MU is 6 cm, the widest a fist closes on. I argued this up to 2.4 on the BD rifle's
# 2.21 and the argument had a unit slip in it: 2.21 MU is 6.5 cm ACROSS, which is about
# 20 cm AROUND, and a real M16 grip is 3.2 cm across. So the rifle's number was evidence the
# fit was swallowing its trigger guard, not evidence that grips are chunky.
GRIP_W_MAX = 2.04
# Comfortable rather than maximum. Between this and GRIP_W_MAX a candidate is plausible but
# wants looking at.
GRIP_W_EASY = 1.70
# A WRIST IS JUDGED ON ITS NARROW AXIS, because a stock wrist is broad and shallow and the
# hand wraps the short way. The confirmed BD shotgun wrist is 3.05 x 1.18 MU.
WRIST_MINOR_MIN = 0.90
WRIST_MINOR_MAX = 1.60
WRIST_MAJOR_MAX = 3.50
# How far out from the axis a vertex still counts as part of the run, as a multiple of the
# major half-extent -- used to measure the run's own length rather than the capsule's.
RUN_WIDE = 1.6


def free_end(pts, centre, axis, cloud, step=END_STEP, ball=END_BALL):
    """Does this run of mesh STOP at one end? Returns (free_ends, counts).

    A GRIP HAS A BUTT AND A FRAME DOES NOT. The pistol's frame-and-slide run is a middle
    section of the body: continuous with the receiver at both ends. The handle terminates
    in a capped free end pointing away from the bore with no mesh beyond it. So stepping a
    short way past each end and counting vertices separates them -- a grip gives roughly
    zero at the butt and plenty at the receiver, a slide gives plenty at both.

    This is the test that catches the failure a residual cannot: the frame IS a
    handle-shaped run of mesh, it fits a cylinder well, and it is not the handle.

    It generalises the right way. A forend is open at both ends so it cannot beat a grip
    here -- correct, since a forend is the SUPPORT point rather than the trigger hand. A
    closed loop like a chainsaw's top handle has no free end at all and is refused rather
    than guessed at.
    """
    # PAST WHERE THE MESH ACTUALLY STOPS, not past the search box. Probing at the capsule
    # bound reports a free end whenever the run is shorter than the capsule, which is the
    # edge of the search and not a property of the gun.
    t = (cloud - centre) @ axis
    counts = []
    for end in (float(t.max()), float(t.min())):
        probe = centre + axis * (end + step * (1.0 if end >= 0 else -1.0))
        d = np.linalg.norm(pts - probe, axis=1)
        counts.append(int(np.count_nonzero(d <= ball)))
    return sum(1 for c in counts if c <= END_FREE_MAX), counts


def find_handles(model, surfaces, rest, t, muzzle=None, bore_z=None,
                 seeds=260, perp=PERP_MAX, along=ALONG_MAX, scale=0.34, strict=True):
    """Every handle-shaped run on the mesh, ranked, with the reasons each survived.

    Searched over the WHOLE mesh rather than a neighbourhood of a seat, because a
    neighbourhood search cannot help when the seat is in a void -- and because a seat that
    is merely NEAR a surface can still be nowhere near a handle, which is how the BD
    pistol's seat sat on the frame while scoring 0.68 units from mesh.

    The filters are filters, never a score: fist-wide, below the bore, behind the muzzle,
    and a free end. Runners-up are returned so a wrong pick is visible rather than silent.
    """
    from .measure import _part_cloud

    pts = _part_cloud(model, surfaces, rest) + np.asarray(t, dtype=float)
    if len(pts) < MIN_VERTS:
        return []
    palm = PALM_MAP / abs(scale) if abs(scale) > 1e-6 else PALM_MAP

    # The bore, as a unit vector: toward the muzzle when one is known, else the mesh's
    # own long axis, which on every gun measured here is the barrel.
    if muzzle is not None:
        bore = np.asarray(muzzle, dtype=float) - pts.mean(axis=0)
    else:
        c = pts - pts.mean(axis=0)
        bore = np.linalg.svd(c, full_matrices=False)[2][0]
    n = np.linalg.norm(bore)
    bore = bore / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])

    # THE CAPSULE IS A FRACTION OF A PALM, NOT A FIXED NUMBER OF MESH UNITS. It was 3.6 x
    # 7.0 absolute, which is 0.36 x 0.70 of a palm on BD22 (palm 10.0) but 1.5 x 2.8 palms
    # on a Vanilla gun (palm 2.5 at scale 1.35) -- a search box several palms wide that
    # swallows the whole weapon. Every other band here is a fact about a HAND, so the box
    # that gathers the vertices has to be one too, or the tool only works at one scale.
    perp = palm * 0.36
    along = palm * 0.70

    step = max(1, len(pts) // seeds)
    found = []
    for seed in pts[::step]:
        fit = _fit_at(pts, np.asarray(seed, dtype=float), perp, along)
        if fit is None:
            continue
        axis, centre, maj, mnr, clock, drift, n = fit
        fails = []
        # IN MAP UNITS, like every other band. FIST_MIN/FIST_MAX were mesh units, which is
        # a different physical size on every model: 1.0 to 2.7 is 0.34 to 0.92 MU on a BD22
        # gun (scale 0.34) and 1.35 to 3.65 MU on a Vanilla one (scale 1.35). It rejected
        # 309 of 374 Vanilla candidates, including every real grip, because a correct grip
        # there measures about 0.44 mesh units across.
        minor_mu = 2.0 * mnr * abs(scale)
        if not (FIST_MU_MIN <= minor_mu <= FIST_MU_MAX):
            fails.append(f"fist({minor_mu:.2f})")
        if maj / max(mnr, 1e-6) > FLATNESS_MAX:
            fails.append(f"flat({maj / max(mnr, 1e-6):.2f})")
        if drift > SECTION_DRIFT_MAX:
            fails.append(f"drift({drift:.2f})")
        if bore_z is not None and centre[2] > bore_z:
            fails.append("above bore")
        if muzzle is not None:
            if (centre[0] - muzzle[0]) * (1.0 if muzzle[0] >= 0 else -1.0) > 0:
                fails.append("ahead of muzzle")
        cloud = _capsule(pts, np.asarray(seed, dtype=float), axis, perp, along)
        # A TRIGGER GRIP IS RAKED AWAY FROM THE BORE; A SLIDE RUNS ALONG IT. This is the
        # discriminator the section shape could not give: a pistol's frame run and its
        # handle are both handle-shaped, both fit a cylinder, and both terminate -- but
        # one lies along the barrel and the other hangs off it at 50-80 degrees. Ranking
        # on section put the slide first every time; this cannot.
        rake = float(np.degrees(np.arccos(min(1.0, abs(float(np.dot(axis, bore)))))))
        if rake < RAKE_MIN:
            fails.append(f"rake({rake:.0f})")
        # ONE PALM LONG, OR IT IS NOT A GRIP. The filter that rejects the bars every other
        # test passed: a chainsaw bar, a launcher tube and a pistol frame all fit a
        # cylinder well and all run two to four palms.
        length = run_length(pts, centre, axis, maj)
        palms = length / palm if palm > 1e-6 else 0.0
        # WIDTH FIRST, because it is the only test that is a fact about hands rather than
        # a property of this mesh. Full width in map units.
        width_mu = 2.0 * maj * abs(scale)
        if not (GRIP_W_MIN <= width_mu <= GRIP_W_MAX):
            fails.append(f"width({width_mu:.2f})")
        if palms < PALM_MIN:
            fails.append(f"short({palms:.2f})")
        # SCALED TO THE SECTION, not absolute: an absolute step is a long way past a
        # thin grip and nowhere near past a fat one, which is how two sessions measuring
        # the same candidate got [56, 3] and 0/0.
        # THE BALL MUST CLEAR THE MESH BEFORE IT COUNTS. Stepping 1.2x the major with a
        # 1.5x ball leaves the ball still overlapping the run it is probing past, so a
        # free butt reads as attached -- that is what rejected the BD pistol's confirmed
        # grip at [87, 926]. Step 2.2x with a 0.9x ball puts the ball's near edge a full
        # major clear of the end.
        frees, counts = free_end(pts, centre, axis, cloud,
                                 step=maj * 2.2, ball=maj * 0.9)
        if frees < 1:
            fails.append("no free end")
        long_handle = palms > PALM_MAX
        if long_handle and (palms > PALM_LONG or frees != 1):
            fails.append(f"long({palms:.2f})")
        if strict and fails:
            continue
        found.append(dict(axis=tuple(float(v) for v in axis),
                          centre=tuple(float(v) for v in centre),
                          major=round(maj, 3), minor=round(mnr, 3), clock=round(clock, 2),
                          drift=round(drift, 3), verts=int(n), free_ends=int(frees),
                          rake=round(rake, 1), palms=round(palms, 2),
                          run_len=round(length, 2), width_mu=round(width_mu, 2),
                          long_handle=bool(long_handle),
                          note=("long handle -- axial position chosen, not measured"
                                if long_handle else ""),
                          fails=fails, passes=not fails,
                          end_counts=counts))

    # Collapse seeds that converged on the same run.
    # WHAT MAKES A GRIP, in the order it distinguishes one. A handle terminates at ONE
    # end and is attached at the other -- free at both is a floating lump, free at neither
    # was already filtered. Then oblong, because a grip is deeper than it is wide and a
    # barrel is round. Drift is the weakest signal and ranks last: a frame is MORE uniform
    # than a grip, so leading with it puts the slide first, which is what it did.
    def rank(h):
        one_free = 0 if h['free_ends'] == 1 else 1
        attached = -min(h['end_counts'])      # the attached end should be well connected
        # Steepest rake first: the more a run hangs off the bore, the more it is a grip.
        return (one_free, -h['rake'], attached, h['drift'])

    kept = []
    for c in sorted(found, key=rank):
        if any(np.linalg.norm(np.asarray(c['centre']) - np.asarray(k['centre'])) < 2.5
               and abs(float(np.dot(c['axis'], k['axis']))) > 0.9 for k in kept):
            continue
        kept.append(c)
    return kept


def _fit_at(pts, seat, perp, along):
    """One capsule fit seeded at a point. None when there is nothing to fit."""
    axis = np.array([0.0, 0.0, -1.0])
    cloud = np.empty((0, 3))
    for _i in range(ITERATIONS):
        cloud = _capsule(pts, seat, axis, perp, along)
        if len(cloud) < MIN_VERTS:
            return None
        c = cloud - cloud.mean(axis=0)
        _u, _s, vt = np.linalg.svd(c, full_matrices=False)
        nxt = _orient(vt[0])
        if float(np.dot(nxt, axis)) > 0.9999:
            axis = nxt
            break
        axis = nxt
    cloud = _capsule(pts, seat, axis, perp, along)
    if len(cloud) < MIN_VERTS:
        return None
    centre = cloud.mean(axis=0)
    maj, mnr, clock, _f = _section(cloud, centre, axis)
    if mnr < 1e-3:
        return None
    return axis, centre, maj, mnr, clock, _drift(cloud, centre, axis), len(cloud)


# ---------------------------------------------------------------- the stock wrist

# How far back along the gun to look for a waist, as a fraction of its length from the
# muzzle. A wrist is always behind the action.
WRIST_FROM = 0.45
# How many slices to cut the searched run into. Enough to see a waist, few enough that
# each slice has vertices in it.
WRIST_SLICES = 26
# How much narrower than its neighbours a slice has to be to count as a waist.
WRIST_DROP = 0.08


def find_wrist(model, surfaces, rest, t, muzzle=None, scale=0.34, strict=True):
    """Waists in the rear of the gun: where a hand closes on a stock.

    Returns the same shape of record as find_handles so the two can be reviewed together,
    with kind='wrist' rather than kind='grip'.
    """
    from .measure import _part_cloud

    pts = _part_cloud(model, surfaces, rest) + np.asarray(t, dtype=float)
    if len(pts) < MIN_VERTS:
        return []
    palm = PALM_MAP / abs(scale) if abs(scale) > 1e-6 else PALM_MAP

    # The gun's own long axis, pointed toward the muzzle.
    centre0 = pts.mean(axis=0)
    if muzzle is not None:
        axis = np.asarray(muzzle, dtype=float) - centre0
    else:
        axis = np.linalg.svd(pts - centre0, full_matrices=False)[2][0]
    n = np.linalg.norm(axis)
    if n < 1e-9:
        return []
    axis = axis / n

    t_all = (pts - centre0) @ axis
    lo, hi = float(t_all.min()), float(t_all.max())
    # the rear portion only: from the back end forward to WRIST_FROM of the length
    back = lo
    front = lo + (hi - lo) * WRIST_FROM
    edges = np.linspace(back, front, WRIST_SLICES + 1)

    widths, mids = [], []
    for i in range(WRIST_SLICES):
        band = pts[(t_all >= edges[i]) & (t_all < edges[i + 1])]
        if len(band) < 10:
            widths.append(np.nan)
            mids.append(None)
            continue
        c = band.mean(axis=0)
        maj, mnr, _clk, _f = _section(band, c, axis)
        widths.append(float(np.hypot(maj, mnr)))
        mids.append(c)
    w = np.array(widths, dtype=float)

    out = []
    for i in range(1, WRIST_SLICES - 1):
        if not np.isfinite(w[i - 1]) or not np.isfinite(w[i]) or not np.isfinite(w[i + 1]):
            continue
        # a local minimum, and meaningfully narrower than at least one neighbour
        if not (w[i] <= w[i - 1] and w[i] <= w[i + 1]):
            continue
        drop = (max(w[i - 1], w[i + 1]) - w[i]) / max(w[i], 1e-6)
        wfails = []
        if drop < WRIST_DROP:
            wfails.append(f"shallow({drop:.2f})")
        c = mids[i]
        band = pts[(t_all >= edges[i] - palm * 0.5) & (t_all < edges[i + 1] + palm * 0.5)]
        if len(band) < 12:
            continue
        maj, mnr, clock, _f = _section(band, c, axis)
        # THE NARROW AXIS, in map units. A wrist is broad and shallow; the hand wraps the
        # short way. No palm filter here: a wrist is a slice, not a run, so every one
        # measures a fraction of a palm and a length test would reject the whole class.
        minor_mu = 2.0 * mnr * abs(scale)
        major_mu = 2.0 * maj * abs(scale)
        if not (WRIST_MINOR_MIN <= minor_mu <= WRIST_MINOR_MAX):
            wfails.append(f"minor({minor_mu:.2f})")
        if major_mu > WRIST_MAJOR_MAX:
            wfails.append(f"major({major_mu:.2f})")
        if not (FIST_MIN <= mnr <= FIST_MAX):
            wfails.append(f"fist({mnr:.2f})")
        if strict and wfails:
            continue
        out.append(dict(kind='wrist', minor_mu=round(minor_mu, 2),
                        major_mu=round(major_mu, 2), axis=tuple(float(v) for v in axis),
                        centre=tuple(float(v) for v in c),
                        major=round(maj, 3), minor=round(mnr, 3), clock=round(clock, 2),
                        drop=round(drop, 3), width=round(float(w[i]), 3),
                        palms=round(palm and (edges[i + 1] - edges[i]) / palm, 2),
                        verts=int(len(band)), free_ends=0, end_counts=[-1, -1],
                        rake=0.0, drift=0.0, fails=wfails, passes=not wfails))
    # deepest waist first: the more a stock narrows there, the more it is a wrist
    out.sort(key=lambda h: -h['drop'])
    return out
