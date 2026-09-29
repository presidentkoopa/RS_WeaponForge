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

  ejectport / ejectdir     The shipped cards carry them and say in their own
                           comments that the point is an estimate. The guide
                           gives no rule for it, so writing one would be
                           inventing a measurement and dressing it as one.
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

# The sound keys a card understands, in the order the shipped cards write them.
SOUND_ORDER = ["firesound", "drysound", "magoutsound", "maginsound", "rackapexsound",
               "rackresetsound", "magdropsound", "boltsound", "pumpsound"]


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
               surface_names: Dict[int, str], notes: Optional[Sequence[str]] = None) -> str:
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

    L.append("")
    L.append(f"  muzzle    = {_triple(muzzle)}")
    L.append(f"  barrel    = {_triple(barrel, 0)}")

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

    for pid, part in gun.parts.items():
        L.append("")
        L.append(f"part {pid}")
        if part.role:
            L.append(f"  role    = {part.role}")
        if part.subject:
            L.append(f"  subject = {part.subject}")
        for idx in part.surfaces:
            L.append(f"  surface = {surface_names.get(idx, idx)}")
        grab = parts.grabs.get(pid)
        if grab is not None:
            L.append(f"  grab       = {_triple(grab.grab)}")
        for n, dof in enumerate(parts.dofs.get(pid, [])):
            L.append("  dof" if n == 0 else f"  dof{n + 1}")
            L.append(f"    kind     = {'slide' if dof.kind == 'feed' else dof.kind}")
            L.append(f"    axis     = {_triple(dof.axis)}")
            if dof.kind == "hinge":
                L.append(f"    degrees  = {_trim(dof.degrees, 2)}")
                if dof.pivot is not None:
                    L.append(f"    pivot    = {_triple(dof.pivot)}")
            else:
                L.append(f"    distance = {_trim(dof.distance, 3)}")
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
