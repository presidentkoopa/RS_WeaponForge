#!/usr/bin/env python3
"""
grip.py -- the point of each gun that is in the palm. CardPipeline/GUN_IN_HAND_PLAN.md, 1.3 and 1.5.

The engine holds a gun by its grip (models.cpp useGrip): the card's `grip` block `seat` is put on the
hand and every turn pivots about it; MODELDEF Offset and the _ofs_* sliders are then not read. So
the grip written into each card is the mesh point the gun's CURRENT placement already puts on the
hand -- its MODELDEF Scale and Offset and its seat (R5) -- and switching a set to grips moves no gun.

THE ARITHMETIC is the follow-hand branch of FSpriteModelFrame::ObjectToWorldMatrix, replayed:
a mesh point q, in the renderer's order (x, height, y), lands in the hand's frame at

    S ( o' + R ( D q - p' ) )

  S   Scale x the placement scale, per axis           D  the pixel stretch, on height only
  o'  (Offset + ofs) / Scale, with `stretch` 1 there  R  the placement turn, then the model's own
  p'  PivotOffset / Scale                             (the off hand mirrors Offset.x: fitMirrorX)

and the grip is the q that lands on the hand's origin. Solved exactly; no tuning in it.
Standard library only.
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

PIXELSTRETCH = 1.2   # Doom's. An MD3's aspect factor is 1, so the draw stretches height by 1/1.2.


def _rot(deg: float, x: float, y: float, z: float):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    n = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / n, y / n, z / n
    return [[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
            [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
            [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mv(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def _solve(a, b):
    """a x = b, 3x3, Cramer."""
    def det(m):
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    d = det(a)
    if abs(d) < 1e-12:
        raise ValueError("placement is singular -- a zero Scale?")
    out = []
    for c in range(3):
        m = [row[:] for row in a]
        for r in range(3):
            m[r][c] = b[r]
        out.append(det(m) / d)
    return out


def grip_from_placement(scale: Sequence[float], offset: Sequence[float],
                        ofs: Sequence[float] = (0.0, 0.0, 0.0),
                        turn: Sequence[float] = (0.0, 0.0, 0.0),
                        model_turn: Sequence[float] = (0.0, 0.0, 0.0),
                        pivot: Sequence[float] = (0.0, 0.0, 0.0),
                        place_scale: float = 1.0, off_hand: bool = False,
                        pixelstretch: float = PIXELSTRETCH) -> Tuple[float, float, float]:
    """The mesh point (card axes x, y, z) that this placement puts on the hand.

    scale, offset, pivot: MODELDEF Scale / Offset / PivotOffset (x, y, z as written).
    ofs, turn: the placement cvars' ofs_x/_y/_z and yaw/pitch/roll. model_turn: MODELDEF
    AngleOffset, PitchOffset, RollOffset."""
    xs, ys, zs = scale
    xo, yo, zo = offset
    px, py, pz = pivot
    yaw, pit, rol = turn
    ang, mpit, mrol = model_turn
    st = 1.0 / pixelstretch
    fit = -1.0 if off_hand else 1.0
    S = [[xs * place_scale, 0, 0], [0, zs * place_scale, 0], [0, 0, ys * place_scale]]
    o = [(fit * xo + ofs[0]) / xs, (zo + ofs[2]) / zs, (yo + ofs[1]) / ys]
    R = _mul(_mul(_mul(_rot(-yaw, 0, 1, 0), _rot(pit, 0, 0, 1)), _mul(_rot(-rol, 1, 0, 0), _rot(-ang, 0, 1, 0))),
             _mul(_rot(mpit, 0, 0, 1), _rot(-mrol, 1, 0, 0)))
    pv = [px / xs, pz / zs, py / ys]
    D = [[1, 0, 0], [0, st, 0], [0, 0, 1]]
    A = _mul(_mul(S, R), D)
    b = _mv(S, [o[i] - _mv(R, pv)[i] for i in range(3)])
    q = _solve(A, [-v for v in b])
    return (q[0], q[2], q[1])


def grip_block(grip: Sequence[float], note: str) -> str:
    return ("\n# THE GRIP: the point of this mesh that is in the palm (CardPipeline/GUN_IN_HAND_PLAN.md).\n"
            f"# {note}\n"
            "grip\n"
            f"  seat = {grip[0]:.3f}, {grip[1]:.3f}, {grip[2]:.3f}\n"
            "end\n")


def with_grip(card_text: str, grip: Sequence[float], note: str) -> str:
    """The card with its grip block after the weapon block's `end`. A card that already has a grip
    block is returned unchanged -- a hand-written grip is the owner's and is never overwritten."""
    lines = card_text.split("\n")
    if any(l.strip() == "grip" for l in lines):
        return card_text
    in_weapon = False
    for i, l in enumerate(lines):
        s = l.split("#", 1)[0].strip()
        if s.startswith("weapon "):
            in_weapon = True
        elif in_weapon and s == "end":
            return "\n".join(lines[:i + 1]) + "\n" + grip_block(grip, note).rstrip("\n") + "\n" + "\n".join(lines[i + 1:])
    raise ValueError("no `weapon ... end` block in the card")
