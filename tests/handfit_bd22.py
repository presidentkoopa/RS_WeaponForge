#!/usr/bin/env python3
"""Run the rewritten handfit against real BD22 guns -- it has never run on anything.

Three things are being checked, in this order, because the third is worthless
without the first two:
  1. THE REFUSAL. No axis must give no number.
  2. THE CALIBRATION. The hand 200 units clear of the gun must read EXACTLY 0
     inside. A parity test that does not zero in free space is measuring its own
     bugs, and every count below it would be noise.
  3. THE COUNT at each gun's shipped grip seat.
"""
import re
import sys

sys.path.insert(0, 'E:/DOOMWork/WeaponForge')
import numpy as np
from forge.md3 import MD3Model
from forge import emit_mesh, handfit
from forge.setfile import load_set

SET = 'E:/DOOMWork/WeaponForge/sets/bd22/set.py'
CARD = 'E:/DOOMWork/RS_VR_Weapons/bd22/WMCARD.bd22'
sf = load_set(SET)

# The shipped seats, read out of the card rather than recomputed.
text = open(CARD, encoding='utf-8').read()
seats = {}
for m in re.finditer(r'weapon "(\w+)"(.*?)(?=\nweapon "|\Z)', text, re.S):
    g = re.search(r'^grip\n(?:.*\n)*?  seat = ([^\n]+)', m.group(2), re.M)
    if g:
        seats[m.group(1)] = [float(x) for x in g.group(1).split(',')]

by_class = {g.cls: g for g in sf.guns.values()}
print('seats read from the shipped card: %d' % len(seats))

# 1. THE REFUSAL -------------------------------------------------------------
gid = sf.guns['pistol']
m = MD3Model.load(sf.donor_root.replace('\\', '/') + '/' + gid.donor.replace('\\', '/'))
r = handfit.fit_at(m, [gid.body], seats['BD_Pistol'])
print()
print('1. no axis ->  ok=%s' % r.ok)
print('   %s' % r.why)
assert not r.ok and 'no grip axis' in r.why, 'a missing axis must refuse, not answer'

# 2 and 3 --------------------------------------------------------------------
print()
print('%-20s %6s %7s %7s  %s' % ('gun', 'calib', 'inside', 'of', 'verdict'))
print('-' * 78)
for name in ('BD_Pistol', 'BD_Revolver', 'BD_Shotgun', 'BD_Machinegun', 'BD_RPG'):
    gun = by_class.get(name)
    if gun is None or name not in seats or gun.body is None:
        print('%-20s (not mapped or no seat)' % name)
        continue
    path = sf.donor_root.replace('\\', '/') + '/' + gun.donor.replace('\\', '/')
    model = MD3Model.load(path)
    rest = gun.rest_frame if gun.rest_frame is not None else 0
    _, t = emit_mesh.recentre_shift(model, rest)
    surfaces = [gun.body] + [i for p in gun.parts.values() for i in p.surfaces]
    surfaces = sorted(set(surfaces))
    seat = seats[name]
    # The grip axis: the gun's own bore is the wrong answer for a pistol and the right
    # one for a foregrip, and GripFit is what solves it properly. Here the bore stands
    # in so the machinery is exercised end to end; the count is labelled provisional
    # because of it, which is exactly what the tool is meant to do.
    fit = handfit.fit_at(model, surfaces, seat, axis=(0.0, 1.0, 0.0),
                         rest=rest, t=t, scale=handfit.WORLD_FACTOR)
    verdict = 'PASS' if fit.ok else (fit.why[:44] if fit.why else '?')
    print('%-20s %6d %7d %7d  %s' % (name, fit.clear_inside, fit.inside, fit.total, verdict))
    for n in fit.notes:
        print('%-20s   %s' % ('', n))
