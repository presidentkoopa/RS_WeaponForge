#!/usr/bin/env python3
"""
compare.py -- build a set and check it against a reference, value by value.
Step 8 of the WeaponForge Build Guide.

    python -m forge.compare <set.py> <reference pack> [out dir]

Tolerances are the roadmap's Stage 1 gate and section 7's table:

    dof axis      <= 0.01 per component
    dof distance  <= 0.01
    dof degrees   <= 0.05
    pivot         <= 0.01
    magcenter     <= 0.01

WHY A VALUE-BY-VALUE COMPARE AND NOT A DIFF. A card that is textually different
may be identical in every number that matters -- key order, decimal places,
comments -- and a card that is textually close can be wrong in the one axis that
sends a magazine out sideways. So the numbers are read back out of both cards
and compared as numbers, and anything outside tolerance is printed with both
values and what it drives.

WHAT IT REPORTS BUT DOES NOT FAIL ON. A value the reference carries and we do
not write at all -- an ejectport, a hand-seated grab, a second stage the mesh
does not contain -- is listed as missing, with no verdict. Those are the places
the reference was authored rather than measured; the guide gives no rule for
them, and a compare that failed on them would be pressure to invent one.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import donor as D
from . import emit_card as EC
from . import emit_mesh as EM
from . import emit_prop as EP
from . import measure as ME
from . import md3 as MD3
from . import setfile as SF

TOL = {"axis": 0.01, "distance": 0.01, "degrees": 0.05, "pivot": 0.01, "magcenter": 0.01}


# ------------------------------------------------------------ reading a card

@dataclass
class RefDof:
    kind: str = ""
    axis: Optional[Tuple[float, float, float]] = None
    distance: Optional[float] = None
    degrees: Optional[float] = None
    pivot: Optional[Tuple[float, float, float]] = None
    extras: Dict[str, str] = field(default_factory=dict)


@dataclass
class RefPart:
    id: str
    role: str = ""
    subject: str = ""
    surfaces: List[str] = field(default_factory=list)
    grab: Optional[Tuple[float, float, float]] = None
    dofs: List[RefDof] = field(default_factory=list)


@dataclass
class RefCard:
    cls: str
    source: str = ""
    keys: Dict[str, str] = field(default_factory=dict)
    parts: Dict[str, RefPart] = field(default_factory=dict)

    def triple(self, key: str):
        return _triple(self.keys.get(key))

    def number(self, key: str):
        v = self.keys.get(key)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


def _triple(value: Optional[str]):
    if not value:
        return None
    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", value)
    if len(nums) < 3:
        return None
    return tuple(float(n) for n in nums[:3])


def read_card(reference: str, cls: str) -> Optional[RefCard]:
    """One weapon's card out of whichever WMCARD.* in `reference` holds it.

    A card runs from its own `weapon` line to the next one, which is what
    parser.zs does: a part block after the weapon's keys belongs to that weapon.
    """
    want = re.compile(r'^\s*weapon\s+"?' + re.escape(cls) + r'"?\s*$', re.I)
    another = re.compile(r"^\s*(weapon|archetype)\s", re.I)
    for name in sorted(os.listdir(reference)):
        if not name.upper().startswith("WMCARD"):
            continue
        path = os.path.join(reference, name)
        if not os.path.isfile(path):
            continue
        lines = open(path, "r", encoding="latin-1").read().splitlines()
        start = next((i for i, l in enumerate(lines) if want.match(l)), None)
        if start is None:
            continue
        card = RefCard(cls=cls, source=name)
        part: Optional[RefPart] = None
        dof: Optional[RefDof] = None
        for raw in lines[start + 1:]:
            line = raw.split("#")[0].strip()
            if not line:
                continue
            if another.match(line):
                break
            m = re.match(r"^part\s+(\S+)", line, re.I)
            if m:
                part = RefPart(id=m.group(1))
                card.parts[part.id] = part
                dof = None
                continue
            if re.match(r"^dof\d*\s*$", line, re.I) and part is not None:
                dof = RefDof()
                part.dofs.append(dof)
                continue
            if line.lower() == "end":
                if dof is not None:
                    dof = None
                elif part is not None:
                    part = None
                continue
            if "=" not in line:
                continue
            key, val = [x.strip() for x in line.split("=", 1)]
            key = key.lower()
            val = val.strip()
            if dof is not None:
                if key == "kind":
                    dof.kind = val
                elif key == "axis":
                    dof.axis = _triple(val)
                elif key == "distance":
                    dof.distance = float(val)
                elif key == "degrees":
                    dof.degrees = float(val)
                elif key == "pivot":
                    dof.pivot = _triple(val)
                else:
                    dof.extras[key] = val
            elif part is not None:
                if key == "surface":
                    part.surfaces.append(val.strip('"'))
                elif key == "role":
                    part.role = val
                elif key == "subject":
                    part.subject = val
                elif key == "grab":
                    part.grab = _triple(val)
            else:
                card.keys[key] = val
        return card
    return None


# --------------------------------------------------------------- building ours

@dataclass
class BuiltGun:
    gun: object
    donor: object
    mesh: object
    prop: object
    muzzle: Tuple[float, float, float]
    barrel: Tuple[float, float, float]
    parts: EC.CardParts
    surface_names: Dict[int, str]
    skipped: List[str] = field(default_factory=list)
    ejection: object = None
    support: object = None
    load: object = None


def _part_surfaces(model, gun, part, rest_frame, t, where: str):
    """A part's vertices: either whole surfaces, or an island inside one."""
    if part.island is None:
        return list(part.surfaces), None
    surf = model.surfaces[part.island["of"]]
    ids = EM.resolve_island(surf, rest_frame, part.island, t, where)
    return [part.island["of"]], ids


def build_gun(sf: SF.SetFile, gun, out_dir: str) -> BuiltGun:
    """Everything the tool would write for one gun, in memory."""
    d = D.read_donor(gun.id, sf.donor_root, gun.donor, gun.modeldef, gun.decorate,
                     rest_frame=gun.rest_frame, actor=gun.actor)
    model = MD3.MD3Model.load(d.md3)
    SF.check_against_mesh(gun, model.surfaces, sf.set_id)

    mesh = EM.emit_mesh(model, gun, d.rest_frame, os.path.join(out_dir, f"{gun.id}_wm.md3"))
    # THE SKIN COMES WITH THE MESH. The donor's MODELDEF names it, and a card that
    # points at a skin nobody copied is a gun that draws untextured -- which reads
    # as a broken model rather than as a missing file.
    skin_name = os.path.basename(d.block.skins.get(0, "") or "")
    if skin_name:
        src = os.path.join(sf.donor_root, d.block.path.replace("/", os.sep), skin_name)
        if os.path.exists(src):
            import shutil as _sh
            _sh.copy2(src, os.path.join(out_dir, f"{gun.id}.png"))
    prop = EP.emit_prop(gun, d, mesh.t, EP.prop_class(gun.cls, sf.prefix),
                        f"{gun.id}_wm.md3", f"{gun.id}.png", sf.model_path,
                        f"{sf.cvar_prefix}_{gun.id}")
    muzzle, barrel = ME.measure_muzzle(model, gun.body, d.rest_frame, mesh.t)
    action = [i for p in gun.parts.values() if p.role == "action" for i in p.surfaces]
    feed = [i for p in gun.parts.values() if p.role == "feed" for i in p.surfaces]
    ejection = ME.measure_ejection(model, gun.body, d.rest_frame, mesh.t,
                                   action or None, feed or None)
    support = ME.measure_support(model, gun.body, d.rest_frame, mesh.t, feed or None)
    load = (ME.measure_load(model, gun.body, d.rest_frame, mesh.t, gun.load.where, feed or None)
            if gun.load else None)

    parts = EC.CardParts()
    skipped: List[str] = []
    for pid, part in gun.parts.items():
        where = f"{sf.set_id}: {gun.id} part '{pid}'"
        try:
            surfaces, island_ids = _part_surfaces(model, gun, part, d.rest_frame, mesh.t, where)
        except ValueError as e:
            skipped.append(f"{pid}: {e}")
            continue
        if island_ids is not None:
            # An island is measured on a surface of its own, so the rest of the
            # donor surface it lives in does not drag the fit around.
            lifted = EM.split_surface(model.surfaces[part.island["of"]], island_ids, pid,
                                      frame=d.rest_frame)
            skipped.append(f"{pid}: island parts are lifted but not yet measured over frames "
                           f"({len(island_ids)} vertices)")
            continue
        if part.chambers:
            # A REVOLVING FEED indexes by its chamber count, not by how far the
            # animation turns it: seven rockets, a seventh of a turn.
            turn = ME.measure_dof(model, gun.body, d.rest_frame, pid, surfaces, mesh.t,
                                  kind="hinge")
            turn.kind = "hinge"
            turn.notes.append(f"turned {turn.degrees:.2f} in the animation; the step is "
                              f"360/{part.chambers} for its {part.chambers} chambers")
            turn.degrees = ME.index_step(part.chambers)
            # A CYLINDER SPINS ABOUT ITS OWN CENTRE. The fixed point of the fitted
            # rotation is not that centre when the animation also carries the drum
            # somewhere -- it came out 27 units below the launcher, which would swing
            # the drum through an arc instead of indexing it in place. Its axis runs
            # through its own centroid.
            import numpy as _np
            cloud = (_np.vstack([_np.asarray(model.surfaces[i].verts[d.rest_frame], float)
                                 for i in surfaces]) + _np.asarray(mesh.t))
            centre = cloud.mean(axis=0)
            a = _np.asarray(turn.axis, float)
            a = a / (_np.linalg.norm(a) or 1.0)
            centre = centre - float(_np.dot(centre, a)) * a
            turn.pivot = tuple(centre)
            parts.dofs[pid] = [turn]
            parts.grabs[pid] = ME.measure_grab(model, surfaces, d.rest_frame, mesh.t, pid,
                                               axis=turn.axis, hinge=True)
            continue
        if part.role == "feed" or part.subject == "magazine":
            slide = ME.measure_dof(model, gun.body, d.rest_frame, pid, surfaces, mesh.t,
                                   kind="slide")
            if max(abs(c) for c in slide.axis) < 1e-9:
                # Nothing animates it, so measure where it CAN go: the clearance out
                # of the body, which is how the shipped cards did these too.
                slide = ME.measure_clearance(model, gun.body, d.rest_frame, surfaces,
                                             mesh.t, pid)
            if max(abs(c) for c in slide.axis) < 1e-9:
                # THE MESH DOES NOT CONTAIN THIS MOTION. Several donors never
                # animate the magazine leaving -- the Unmaker's skull and the
                # RPG's drum never move in any frame -- and the shipped cards
                # carry an authored number for them (the Unmaker's "7.0 along
                # +Z"). There is nothing to measure, so nothing is written, and
                # the owner is told rather than handed a fabricated axis.
                skipped.append(f"{pid}: no frame moves this part, so its feed cannot be "
                               f"measured; the reference card's value is authored")
                continue
            carve = ME.carve_part(model, surfaces, d.rest_frame, mesh.t, slide.axis,
                                  os.path.join(out_dir, f"{gun.id}_{pid}.md3"),
                                  abs(prop.scale[0]), pid)
            parts.carves[pid] = carve
            if slide.notes and "clears the body" in slide.notes[-1]:
                feed = slide            # a clearance IS the answer; do not re-measure
            else:
                feed = ME.measure_feed(model, gun.body, d.rest_frame, pid, surfaces,
                                       mesh.t, carve)
            parts.dofs[pid] = [feed]
            parts.grabs[pid] = ME.measure_grab(model, surfaces, d.rest_frame, mesh.t, pid,
                                               axis=feed.axis)
        else:
            dof = ME.measure_dof(model, gun.body, d.rest_frame, pid, surfaces, mesh.t)
            if dof.kind == "hinge" and dof.degrees > ME.SMALL_HINGE_DEG:
                # A big turn may be a rotor rather than a hinge, and a rotor's
                # angle is one period of its own symmetry, not how far the
                # animation happened to turn it.
                deg, fold, miss = ME.spin_period(model, surfaces, d.rest_frame, mesh.t,
                                                 dof.axis, dof.pivot or (0, 0, 0))
                if deg is not None:
                    dof.notes.append(f"turned {dof.degrees:.2f} in the animation; the period is "
                                     f"360/{fold} and it lands on itself to {miss:.4f}")
                    dof.degrees = deg
            parts.dofs[pid] = [dof]
            # A TRIGGER IS NOT GRABBED. Your finger pulls it because you are holding
            # the gun; it is not a thing you reach out and take, and the shipped
            # cards give a trigger a dof and no grab. A grab on it would make it
            # grabbable, which is a different gun.
            if part.role != "trigger":
                parts.grabs[pid] = ME.measure_grab(model, surfaces, d.rest_frame, mesh.t, pid,
                                                   axis=dof.axis, hinge=(dof.kind == "hinge"))
    out = BuiltGun(gun=gun, donor=d, mesh=mesh, prop=prop, muzzle=muzzle, barrel=barrel,
                   parts=parts, surface_names=mesh.names, skipped=skipped)
    out.ejection = ejection
    out.support = support
    out.load = load
    return out


# ----------------------------------------------------------------- comparing

@dataclass
class Finding:
    gun: str
    what: str
    ours: str
    theirs: str
    off: float
    tol: float
    hard: bool = True


def _cmp(findings, gun, what, ours, theirs, tol, hard=True):
    if ours is None or theirs is None:
        return
    if isinstance(ours, (list, tuple)):
        off = max(abs(a - b) for a, b in zip(ours, theirs))
        ours_s = ", ".join(f"{c:+.3f}" for c in ours)
        theirs_s = ", ".join(f"{c:+.3f}" for c in theirs)
    else:
        off = abs(float(ours) - float(theirs))
        ours_s, theirs_s = f"{float(ours):.3f}", f"{float(theirs):.3f}"
    if off > tol:
        findings.append(Finding(gun, what, ours_s, theirs_s, off, tol, hard))


def compare_gun(built: BuiltGun, ref: RefCard) -> Tuple[List[Finding], List[str]]:
    """Every value both sides carry, compared. Returns (findings, notes)."""
    findings: List[Finding] = []
    notes: List[str] = []
    gid = built.gun.id

    _cmp(findings, gid, "magcenter", None, None, TOL["magcenter"])
    for pid, carve in built.parts.carves.items():
        _cmp(findings, gid, "magcenter", carve.magcenter, ref.triple("magcenter"),
             TOL["magcenter"])
        _cmp(findings, gid, "magscale", carve.magscale, ref.number("magscale"), 0.001)

    for pid, dofs in built.parts.dofs.items():
        rp = ref.parts.get(pid)
        if rp is None:
            notes.append(f"part '{pid}' is not in the reference card")
            continue
        for n, ours in enumerate(dofs):
            if n >= len(rp.dofs):
                notes.append(f"part '{pid}' dof{n + 1}: the reference has no such stage")
                continue
            theirs = rp.dofs[n]
            tag = f"{pid} dof{n + 1 if n else ''}"
            _cmp(findings, gid, f"{tag} axis", ours.axis, theirs.axis, TOL["axis"])
            if ours.kind == "hinge":
                _cmp(findings, gid, f"{tag} degrees", ours.degrees, theirs.degrees,
                     TOL["degrees"])
                _cmp(findings, gid, f"{tag} pivot", ours.pivot, theirs.pivot, TOL["pivot"])
            else:
                _cmp(findings, gid, f"{tag} distance", ours.distance, theirs.distance,
                     TOL["distance"])
        for n in range(len(dofs), len(rp.dofs)):
            notes.append(f"part '{pid}' dof{n + 1} is in the reference and not measured here")

    for pid in ref.parts:
        if pid not in built.parts.dofs and pid not in built.parts.carves:
            notes.append(f"the reference has a part '{pid}' this set does not build")
    for s in built.skipped:
        notes.append(s)
    return findings, notes


def compare_set(set_path: str, reference: str, out_dir: str) -> Tuple[List[Finding], List[str]]:
    sf = SF.load_set(set_path)
    os.makedirs(out_dir, exist_ok=True)
    all_findings: List[Finding] = []
    all_notes: List[str] = []
    print(f"{sf.set_id}: {len(sf.guns)} guns against {reference}\n")
    for gid, gun in sf.guns.items():
        if not gun.mapped:
            all_notes.append(f"{gid}: not mapped yet")
            continue
        try:
            built = build_gun(sf, gun, out_dir)
        except (D.DonorError, SF.SetError, ValueError) as e:
            all_findings.append(Finding(gid, "build", "-", "-", 0.0, 0.0))
            print(f"  {gid:16} BUILD FAILED: {e}")
            continue
        ref = read_card(reference, gun.cls)
        if ref is None:
            all_notes.append(f"{gid}: no reference card for {gun.cls}")
            print(f"  {gid:16} no reference card for {gun.cls}")
            continue
        findings, notes = compare_gun(built, ref)
        all_findings.extend(findings)
        all_notes.extend(f"{gid}: {n}" for n in notes)
        mark = "ok " if not findings else "BAD"
        print(f"  {mark} {gid:16} {len(built.parts.dofs)} dofs, "
              f"{len(built.parts.carves)} carves, {len(findings)} outside tolerance"
              f" (ref {ref.source})")
        for f in findings:
            print(f"        {f.what:28} ours {f.ours:26} ref {f.theirs:26} "
                  f"off {f.off:.3f} > {f.tol}")
    return all_findings, all_notes


def main(argv: Sequence[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    set_path, reference = argv[1], argv[2]
    out_dir = argv[3] if len(argv) > 3 else os.path.join(os.path.dirname(set_path), "out")
    findings, notes = compare_set(set_path, reference, out_dir)
    if notes:
        print("\nNotes (reported, not failed on):")
        for n in notes:
            print(f"  {n}")
    if findings:
        print(f"\nFAIL: {len(findings)} value(s) outside tolerance")
        return 1
    print("\nPASS: every value both sides carry is within tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
