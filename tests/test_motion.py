#!/usr/bin/env python3
"""
test_motion.py -- step 4's done-check: forge/motion.py reproduces section 7's
motion table within 0.02 units / 0.1 degrees.

The table is thirteen rows over seven guns, and it is the only thing that says
the measurements mean what they claim. A magazine measured along the wrong axis
produces a carve that lies on the floor at an angle; a hinge measured with the
wrong sign swings a trigger the wrong way. Neither looks like a maths error
from inside the headset.

TOLERANCE. The guide allows 0.02 units and 0.1 degrees. The expected values are
quoted to the precision the guide prints them at, so the check also allows half
of that last printed digit -- 16.8 in the table stands for anything from 16.75
to 16.85, and demanding 16.800 of it would be reading a precision the table does
not carry.

THE BODY. Each gun's body here is its surface with the most vertices, and the
table is what confirms that choice: a wrong body leaves its own motion in every
other surface, and no row would match. In a real set the body is named in
set.py and never guessed -- the guide's own warning is the minigun, whose
largest surface is its spinning barrels.

    python tests/test_motion.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

from forge import md3 as MD3        # noqa: E402
from forge import motion as MO      # noqa: E402
from forge import donor as D        # noqa: E402
from test_donor import DONORS, find_md3s, parse_all_modeldefs, index_actors, resolve  # noqa: E402

# Section 7, "Expected motion". Body divided out, at the rest frame.
# (gun, surface index, name fragment, expectations)
EXPECTED = [
    ("BrutalSMG", 3, "Lipas", {"travel": 16.8, "dir": (-0.30, 0.0, -0.95), "turn": 0.0}),
    ("BrutalSMG", 2, "Trigger", {"travel": 0.98, "axis": "-X"}),
    ("AssaultShotgun", 6, "Mag", {"travel": 28.0, "axis": "-Z"}),
    ("AssaultShotgun", 2, "Receiver", {"travel": 10.00, "axis": "-X"}),
    ("AssaultShotgun", 5, "Trigger", {"angle": 19.9}),
    ("Rifle", 0, "liikkuvat", {"travel": 7.12, "axis": "-X"}),
    ("Rifle", 2, "trigger", {"angle": 17.0}),
    ("Shotgun", 4, "pump", {"travel": 6.27, "axis": "-X", "turn": 0.0}),
    ("BrutalPistol", 1, "Cube", {"travel": 4.59, "axis": "-X"}),
    ("BrutalPistol", 3, "Cube", {"travel": 30.0, "axis": "-Z"}),
    ("MP40", 10, "magazynek", {"travel": 25.0, "axis": "-Z"}),
    ("RailGun", 4, "Mag-Bat", {"travel": 30.0, "axis": "-Z"}),
    ("RailGun", 0, "Scope", {"fit": 0.63}),
]


def printed_slack(value: float) -> float:
    """Half of the last digit the table prints, so a quoted 16.8 is not read as
    16.800."""
    s = f"{value!r}"
    if "." in s:
        dp = len(s.split(".", 1)[1].rstrip("0")) or 1
    else:
        dp = 0
    return 0.5 * (10 ** -dp)


def main() -> int:
    md3s = find_md3s(DONORS)
    modeldefs = parse_all_modeldefs(DONORS)
    actors = index_actors(DONORS)

    guns = []
    seen = set()
    for gun, *_rest in EXPECTED:
        if gun not in seen:
            seen.add(gun)
            guns.append(gun)

    measured = {}
    failures = []

    for gun in guns:
        path = md3s.get(gun.lower())
        if not path:
            failures.append(f"{gun}: no MD3 in the donor pack")
            continue
        wins, tried = resolve(gun, path, modeldefs, actors)
        if not wins:
            failures.append(f"{gun}: could not resolve a rest frame: {tried[:2]}")
            continue
        d = wins[0]
        model = MD3.MD3Model.load(d.md3)
        body = max(range(len(model.surfaces)), key=lambda i: model.surfaces[i].num_verts)
        mo = MO.measure_motion(model, body_index=body, rest_frame=d.rest_frame, gun=gun)
        measured[gun] = mo
        print(MO.write_proposal("", mo))

    for gun, idx, frag, want in EXPECTED:
        mo = measured.get(gun)
        if mo is None:
            continue
        if idx >= len(mo.surfaces):
            failures.append(f"{gun} #{idx}: the mesh has only {len(mo.surfaces)} surfaces")
            continue
        m = mo.surfaces[idx]
        where = f"{gun} #{idx} '{m.name}'"
        if frag.lower() not in m.name.lower():
            failures.append(f"{where}: the table calls this surface {frag!r}")

        if "travel" in want:
            tol = 0.02 + printed_slack(want["travel"])
            if abs(m.travel - want["travel"]) > tol:
                failures.append(f"{where}: travel {m.travel:.3f}, table says {want['travel']} "
                                f"(tolerance {tol:.3f})")
        if "dir" in want:
            for a, (got, wnt) in enumerate(zip(m.direction, want["dir"])):
                if abs(got - wnt) > 0.02 + printed_slack(wnt):
                    failures.append(f"{where}: direction {tuple(round(c, 3) for c in m.direction)}, "
                                    f"table says {want['dir']}")
                    break
        if "axis" in want and m.dominant_axis != want["axis"]:
            failures.append(f"{where}: direction {tuple(round(c, 3) for c in m.direction)} reads as "
                            f"{m.dominant_axis or 'no single axis'}, table says {want['axis']}")
        if "turn" in want and abs(m.turn_at_travel - want["turn"]) > 0.1:
            failures.append(f"{where}: turn at the travel frame {m.turn_at_travel:.3f} deg, "
                            f"table says {want['turn']}")
        if "angle" in want:
            tol = 0.1 + printed_slack(want["angle"])
            if abs(m.angle - want["angle"]) > tol:
                failures.append(f"{where}: hinge {m.angle:.2f} deg, table says {want['angle']} "
                                f"(tolerance {tol:.2f})")
        if "fit" in want:
            tol = 0.02 + printed_slack(want["fit"])
            if abs(m.fit_error - want["fit"]) > tol:
                failures.append(f"{where}: worst fit {m.fit_error:.3f}, table says ~{want['fit']} "
                                f"(tolerance {tol:.3f})")
            if m.fit_error <= MO.NOT_RIGID:
                failures.append(f"{where}: fit {m.fit_error:.3f} is not flagged as 'not rigid'")

    if failures:
        print(f"FAIL: {len(failures)} problem(s)")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"PASS: {len(EXPECTED)} motion rows reproduced over {len(guns)} guns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
