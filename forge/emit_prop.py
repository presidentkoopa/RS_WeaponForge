#!/usr/bin/env python3
"""
emit_prop.py -- the prop's MODELDEF block and its placement cvars.
Step 6 of the WeaponForge Build Guide, rules R3, R4 and R5.

R3  Scale  = donor MODELDEF Scale x 0.34, per axis, sign kept.
R4  Offset = |S| x ( t.y , t.x , donorZOffset - t.z )
R5  cvars  = yaw -90, pitch 0, roll 0, all scales 1,
             ofs_x 0, ofs_y 9.69, ofs_z 2.295

WHERE 0.34 COMES FROM. It is the exchange rate between two unit conventions in
this engine. A donor viewmodel is authored for the HUD weapon path, which
multiplies a model's coordinates by 0.01 inside a frame that already carries
vr_vunits_per_meter -- 34 map units to the metre -- so a HUD model draws at
34 x 0.01 = 0.34 map units per model unit. A world prop draws one model unit as
one map unit. Convert by 0.34 and the gun in your hand is the size the gun in
Brutal Doom's hands was; hand the world path the donor's Scale unconverted and
it is 2.941 times too big.

THE SIGN IS KEPT, PER AXIS. Every Brutal Doom donor is `Scale -1 1 1`, so every
BD prop is `Scale -0.34 0.34 0.34`. That minus is the mirror the exporter baked
in; it is part of the mesh's handedness, not a fault to correct. Drop it and the
gun is inside out -- ejection port and charging handle on the wrong side.

WHY THE OFFSET IS THE SHIFT SWAPPED. R2 moved the mesh's origin to the middle of
the gun. The offset puts it back where the donor sat in the hand, and it is the
recentring shift read in the placement frame rather than in model space: on the
follow-hand path the placement yaw of -90 turns the mesh before the offset is
added, so the mesh's x runs along the offset's y, and the mesh's y along the
offset's x. Hence (t.y, t.x, ...). Valid only at yaw -90, pitch 0, roll 0, which
is why R5 fixes those and leaves only ofs_* to be tuned.

NEVER PER GUN. A whole donor family converts at one rate. If a gun looks wrong
at 0.34 the fault is upstream -- the wrong rest frame, or a mesh already reposed
-- and a per-gun scale hides it and puts the gun permanently out of step with
its own magazine, its holster and its floor copy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# The HUD-to-world conversion: vr_vunits_per_meter (34) x the HUD model path's
# 0.01. One number, one place, so a set cannot carry its own.
WORLD_FACTOR = 0.34

# R5. The owner tunes ofs_* in the headset and nothing else; the angles are what
# R4's arithmetic is valid at.
PLACEMENT_DEFAULTS = {
    "yaw": -90.0,
    "pitch": 0.0,
    "roll": 0.0,
    "scale": 1.0,
    "scale_x": 1.0,
    "scale_y": 1.0,
    "scale_z": 1.0,
    "ofs_x": 0.0,
    "ofs_y": 9.69,
    "ofs_z": 2.295,
}
# The order they are written in, so a diff of two CVARINFOs is readable.
PLACEMENT_ORDER = ["yaw", "pitch", "roll", "scale", "scale_x", "scale_y", "scale_z",
                   "ofs_x", "ofs_y", "ofs_z"]


@dataclass
class Prop:
    gun: str
    cls: str
    mesh: str
    skin: str
    model_path: str
    scale: Tuple[float, float, float]
    offset: Tuple[float, float, float]
    cvar_stem: str
    hand: str = "main"
    flags: List[str] = field(default_factory=list)

    def modeldef(self) -> str:
        follow = "FollowMainHand" if self.hand != "off" else "FollowOffHand"
        lines = [
            f"Model {self.cls}",
            "{",
            f'\tPath "{self.model_path}"',
            f'\tModel 0 "{self.mesh}"',
            f'\tSkin 0 "{self.skin}"',
            f"\tScale {self.scale[0]:.4f} {self.scale[1]:.4f} {self.scale[2]:.4f}",
            f"\tOffset {self.offset[0]:.4f} {self.offset[1]:.4f} {self.offset[2]:.4f}",
            f"\tPlacementCVars {self.cvar_stem}",
            "\tNOAUTOREVERSE",
            "\tNoInterpolation",
            f"\t{follow}",
            "\tFrameIndex WMPR A 0 0",
            "}",
        ]
        return "\n".join(lines) + "\n"

    def cvarinfo(self) -> str:
        lines = []
        for key in PLACEMENT_ORDER:
            lines.append(f"user float {self.cvar_stem}_{key} = {PLACEMENT_DEFAULTS[key]:g};")
        return "\n".join(lines) + "\n"


def prop_scale(donor_scale: Sequence[float]) -> Tuple[float, float, float]:
    """R3, per axis, sign kept."""
    return tuple(float(s) * WORLD_FACTOR for s in donor_scale)


def prop_offset(t: Sequence[float], donor_z_offset: float,
                abs_scale: float = WORLD_FACTOR) -> Tuple[float, float, float]:
    """R4. `t` is the recentring shift emit_mesh applied, in donor model units."""
    return (abs_scale * t[1],
            abs_scale * t[0],
            abs_scale * (float(donor_z_offset) - t[2]))


def prop_class(weapon_class: str, prefix: str = "") -> str:
    """The prop's class name, from the weapon's own.

    WM_SMG becomes WM_PropSMG, which is how every shipped prop is named: the
    prefix, then Prop, then the rest. Built from the weapon class rather than
    from the set's gun id, because the id is a filename and the class is a name.
    """
    if prefix and weapon_class.startswith(prefix):
        return prefix + "Prop" + weapon_class[len(prefix):]
    return weapon_class + "Prop"


def emit_prop(gun, donor, t: Sequence[float], cls: str, mesh: str, skin: str,
              model_path: str, cvar_stem: str) -> Prop:
    """The prop block and cvars for one gun.

    `donor` is step 3's Donor: its Scale and its effective z offset are what R3
    and R4 convert. Nothing here is chosen per gun.
    """
    scale = prop_scale(donor.scale)
    # |S| is the PROP's scale magnitude, not the constant: a donor that is not
    # Scale 1 converts its own offset by its own rate. For Brutal Doom, whose
    # donors are all Scale -1 1 1, this is 0.34.
    return Prop(gun=gun.id, cls=cls, mesh=mesh, skin=skin, model_path=model_path,
                scale=scale,
                offset=prop_offset(t, donor.z_offset, abs(scale[0])),
                cvar_stem=cvar_stem, hand=getattr(gun, "hand", "main"))
