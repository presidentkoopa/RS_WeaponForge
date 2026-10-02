#!/usr/bin/env python3
"""
emit_card.py -- write a gun's WMCARD text. Step 7 of the WeaponForge Build Guide.

The grammar is the one RS_VR_Reload/zscript/wm/parser.zs reads and the shipped
RS_VR_Weapons/WMCARD.* files are written in: `weapon "<class>"` opens a card and
everything after it belongs to that card until the next `weapon`, with the
weapon's own keys first and then one `part` block per moving part.

WHERE EVERY VALUE COMES FROM, and nowhere else:

  measured   muzzle, barrel, each dof's axis, distance, degrees and pivot,
             magcenter, magscale, grab. These come out of measure.py and are
             never typed.
  set.py     class, prop, hand, type, capacity, magfamily, sounds, and which
             surfaces make each part. These are the owner's decisions and are
             never measured.

Nothing is inferred from a part's name. A part called "magazine" gets a feed
dof because set.py gave it role feed, not because of what it is called.

WHAT THIS DELIBERATELY DOES NOT WRITE

  (ejectport and ejectdir are written now: the SIDE is measured from the
  action's own side, and the point and direction are written as the estimates
  they are, in the shipped cards' own words.)
  role-specific grab       The guide's rule is that a forend or handle's grab is
                           the surface centroid. The shipped cards use something
                           else per role -- the floorplate for a magazine, the
                           front end for a charging handle -- which is where you
                           would actually pinch each. That rule is not written
                           down anywhere, so this writes the centroid the guide
                           specifies and the difference is reported by compare,
                           rather than guessed at here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

# THE SOUND KEYS A CARD UNDERSTANDS, in the order a reload runs them. Every one of
# these is read by RS_VR_Reload/zscript/wm/parser.zs; the parser refuses an unknown
# key and skips the whole card, so this list is not a style choice.
#
# `pumpsound` and `boltsound` used to sit here and are NOT card keys -- the parser has
# never read either. Nothing caught it because the ordering list only orders keys that
# are present, so the two names sat here inert, looking available. A pump's two strokes
# are cycleoutsound / cyclehomesound, and a bolt's are rackapexsound / rackresetsound.
SOUND_ORDER = ["firesound", "drysound",
               "magoutsound", "maginsound", "magdropsound",
               "rackapexsound", "rackresetsound",
               "cycleoutsound", "cyclehomesound",
               "opensound", "closesound", "ejectsound", "loadsound",
               "spinupsound", "spinsound", "spindownsound",
               "pullsound", "startsound", "idlesound", "stopsound",
               "casingsound"]


def _triple(v: Sequence[float], dp: int = 3) -> str:
    return ", ".join(f"{float(c):.{dp}f}" for c in v)


def _trim(v: float, dp: int = 3) -> str:
    """A number without a trailing run of zeros, as the shipped cards write
    them: 0.34 rather than 0.340, 90.0 rather than 90.000."""
    s = f"{float(v):.{dp}f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


@dataclass
class CardParts:
    """What measure.py found, keyed by part id."""
    dofs: Dict[str, list] = field(default_factory=dict)      # part id -> [DOF, DOF]
    carves: Dict[str, object] = field(default_factory=dict)  # part id -> Carve
    grabs: Dict[str, object] = field(default_factory=dict)   # part id -> Grab


def write_card(gun, prop, muzzle: Sequence[float], barrel: Sequence[float],
               parts: CardParts, model_path: str, mesh: str, skin_path: str, skin: str,
               surface_names: Dict[int, str], notes: Optional[Sequence[str]] = None,
               part_names: Optional[Dict[str, List[str]]] = None,
               ejection=None, support=None, load=None) -> str:
    """The card text for one gun."""
    L: List[str] = []
    if notes:
        for n in notes:
            L.append(f"# {n}")
    L.append(f'weapon "{gun.cls}"')
    L.append(f"  hand      = {gun.hand}")
    if gun.type:
        L.append(f"  type      = {gun.type}")
    L.append(f'  prop      = "{prop.cls}"')
    L.append(f'  model     = "{model_path}" "{mesh}"')
    L.append(f'  skin      = "{skin_path}" "{skin}"')
    if gun.capacity is not None:
        L.append(f"  capacity  = {gun.capacity}")
    if gun.magfamily:
        L.append(f'  magfamily = "{gun.magfamily}"')
    if gun.firesfrom:
        L.append(f"  firesfrom = {gun.firesfrom}")
    # WHETHER A CASE LEAVES THE GUN. Unstated, the card already means yes, so this only
    # ever writes a line to turn brass OFF -- on a plasma rifle, a rail, a rocket, a
    # flame. The ejectport below is still written at `none`: it is the emptier wall of
    # the receiver either way, and rig.zs:3122 throws LIVE rounds from that same point
    # when a breech opens, so dropping it would break a gun that ejects loaded rounds.
    if getattr(gun, "casing", ""):
        L.append(f"  casing    = {gun.casing}")
    if gun.mechanism:
        L.append(f"  mechanism = {gun.mechanism}")

    L.append("")
    L.append(f"  muzzle    = {_triple(muzzle)}")
    L.append(f"  barrel    = {_triple(barrel, 0)}")
    if ejection is not None:
        L.append(f"  # {ejection.note}")
        L.append(f"  ejectport = {_triple(ejection.port)}")
        L.append(f"  ejectdir  = {_triple(ejection.direction, 4)}")

    # The loose magazine, when a part was carved.
    for pid, carve in parts.carves.items():
        L.append("")
        L.append(f'  magmodel  = "{model_path}" "{os.path.basename(carve.out)}"')
        L.append(f'  magskin   = "{skin_path}" "{skin}"')
        L.append(f"  magscale  = {_trim(carve.magscale, 4)}")
        L.append(f"  magcenter = {_triple(carve.magcenter)}")
        break     # one loose magazine per card

    sounds = {k.lower(): v for k, v in (gun.sounds or {}).items()}
    if sounds:
        L.append("")
        for key in SOUND_ORDER:
            if key in sounds:
                L.append(f'  {key:14s} = "{sounds[key]}"')
        for key in sorted(set(sounds) - set(SOUND_ORDER)):
            L.append(f'  {key:14s} = "{sounds[key]}"')
    L.append("end")

    for st in getattr(gun, "stores", []) or []:
        L.append("")
        L.append(f"store {st.id}")
        L.append(f"  kind     = {st.kind}")
        if st.capacity is not None:
            L.append(f"  capacity = {st.capacity}")
        if st.slots is not None:
            L.append(f"  slots    = {st.slots}")
        if st.detach:
            L.append(f"  detach   = {st.detach}")
        L.append("end")

    if load is not None and getattr(gun, "load", None) is not None:
        at, direction = load
        L.append("")
        L.append(f"# WHERE A ROUND GOES IN. The face is the set file's choice ({gun.load.where});")
        L.append("# the point is the body's own surface on that face at the breech, and the")
        L.append("# direction is into the gun.")
        # A LOAD WITH NO STORE IS REFUSED AT LOAD TIME and takes the card with it.
        if not getattr(gun.load, "into", ""):
            raise ValueError(
                f"{gun.id}: load '{gun.load.id}' names no store. The reload system "
                f"refuses a load verb with no `into` and skips the whole card, so this "
                f"gun would not load at all. Give the set file's load block "
                f"into = <one of this gun's stores>.")
        L.append(f"load {gun.load.id}")
        L.append(f"  into = {gun.load.into}")
        # A SLOTTED STORE IS FILLED ONE POSITION AT A TIME, and the reload system refuses
        # a load into one that does not say which -- another refusal that skips the card.
        # DERIVED, NOT RESTATED: the store already declares its kind, so a set file that
        # says `slotted` cannot then forget the slot. `next` is the only sane answer for
        # a hand feeding rounds in -- slot 0 first, then the next empty one.
        _into = next((st for st in (getattr(gun, "stores", []) or [])
                      if st.id == gun.load.into), None)
        if _into is None:
            raise ValueError(
                f"{gun.id}: load '{gun.load.id}' goes into '{gun.load.into}', which is "
                f"not one of this gun's stores "
                f"({', '.join(st.id for st in (getattr(gun, 'stores', []) or [])) or 'none'}).")
        if _into.kind == "slotted":
            L.append("  slot = next")
        L.append(f"  at   = {_triple(at)}")
        if gun.load.size:
            L.append(f"  size = {_triple(gun.load.size, 2)}")
        L.append(f"  dir  = {_triple(direction, 4)}")
        L.append("end")

    if support is not None:
        L.append("")
        L.append("# WHERE THE OFF HAND GOES. The height is measured -- the underside of the")
        L.append("# body there. The length along the gun is an ESTIMATE: the middle of the")
        L.append("# body's thick run forward of the magazine, since a handguard is thick and")
        L.append("# a barrel is thin. Check it in the headset.")
        L.append("part support")
        L.append("  role    = support")
        L.append("  subject = support")
        L.append(f"  grab       = {_triple(support.grab)}")
        L.append(f"  grabradius = {_trim(support.radius, 2)}")
        L.append("end")

    for pid, part in gun.parts.items():
        L.append("")
        L.append(f"part {pid}")
        if part.role:
            L.append(f"  role    = {part.role}")
        if part.subject:
            L.append(f"  subject = {part.subject}")
        if part.take:
            L.append(f"  take    = {part.take}")
        # WHAT SPINS IT (card.zs WM_Part.spinBy). A rotor is not a part a hand works,
        # and without this the card's spinup/spin/spindown sounds have nowhere to play.
        if getattr(part, "spin", ""):
            L.append(f"  spin    = {part.spin}")
            if getattr(part, "spinrate", None) is None:
                raise ValueError(
                    f"{gun.id} part '{pid}': spin = {part.spin} with no spinrate. The "
                    f"parser refuses a spinning part that names no rate, which skips the "
                    f"whole card -- a gun that loads silent is better than one that does "
                    f"not load. Give it spinrate (degrees a tic, under half its period).")
            L.append(f"  spinrate = {_trim(part.spinrate, 2)}")
            if getattr(part, "spinup", None) is not None:
                L.append(f"  spinup   = {int(part.spinup)}")
            if getattr(part, "spindown", None) is not None:
                L.append(f"  spindown = {int(part.spindown)}")
        # THE NAMES THE MESH WAS WRITTEN WITH. An island part's surfaces list
        # holds the host it was cut from, whose written name is still `body`; the
        # island itself went out under the part's own name. Naming the host here
        # points the card at the whole gun again -- the same failure the split was
        # made to fix, moved from the mesh to the card.
        for name in (part_names or {}).get(pid, [surface_names.get(i, i)
                                                 for i in part.surfaces]):
            L.append(f"  surface = {name}")
        grab = parts.grabs.get(pid)
        if grab is not None:
            L.append(f"  grab       = {_triple(grab.grab)}")
            L.append(f"  grabradius = {_trim(grab.radius, 2)}")
        for n, dof in enumerate(parts.dofs.get(pid, [])):
            # A DOF WITH NO AXIS IS NOT A DOF. It reached the card as
            # "axis = 0,0,0, distance = 0.0, detach = 0.9" on three guns: a part
            # the reload system is told to pull, in no direction, no distance.
            # Nothing downstream can tell that from a real one.
            if max(abs(c) for c in dof.axis) < 1e-9:
                raise ValueError(
                    f"{gun.id} part '{pid}': measured no axis at all "
                    f"({dof.kind}). Nothing moves it and nothing clears it, so "
                    f"there is no motion to write. Give it a part map that is a "
                    f"moving part, or leave it out of parts.")
            L.append("  dof" if n == 0 else f"  dof{n + 1}")
            L.append(f"    kind     = {'slide' if dof.kind == 'feed' else dof.kind}")
            L.append(f"    axis     = {_triple(dof.axis)}")
            if dof.kind == "hinge":
                L.append(f"    degrees  = {_trim(dof.degrees, 2)}")
                if dof.pivot is not None:
                    L.append(f"    pivot    = {_triple(dof.pivot)}")
            else:
                L.append(f"    distance = {_trim(dof.distance, 3)}")
            # How far through the travel the hand lets go. A behaviour default per
            # role, not a measurement, and the shipped cards' own values: a magazine
            # is loose near the end of its run (0.9), an action a little later
            # (0.95) since it stays on the gun.
            if dof.kind == "feed":
                L.append("    detach   = 0.9")
            elif part.role == "action":
                L.append("    detach   = 0.95")
            L.append("  end")
        L.append("end")

    return "\n".join(L) + "\n"


def write_set_cards(path: str, cards: Sequence[str], set_id: str = "") -> str:
    """Every card of a set in one lump, as a WMCARD.<set> file."""
    head = [f"# WMCARD.{set_id} -- written by WeaponForge. Do not edit by hand:",
            f"# fix the tool or sets/{set_id}/set.py and run RUN_SET again.",
            ""]
    text = "\n".join(head) + "\n".join(cards)
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text
