#!/usr/bin/env python3
"""
test_setfile.py -- step 5's done-check: a test set with one surface left out is
refused, and the message names that surface.

Naming it is the whole point. "gun 'smg': 1 surface unaccounted for" sends the
owner to count surfaces by hand; "#2 'trigger'" is a line they can act on.

The set files here are written into a temporary directory at run time, against
the real SMG donor, so the indices and surface names are the mesh's own.

    python tests/test_setfile.py
"""

from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

from forge import md3 as MD3       # noqa: E402
from forge import setfile as SF    # noqa: E402

DONORS = r"D:\SteamLibrary\steamapps\Common\DooM VR\__Games\BrutalDoom\_BD_1.01_WeaponModels"
SMG = os.path.join(DONORS, r"Models\Weapons\Hud\BrutalSMG\BrutalSMG.md3")

HEAD = '''
SET_ID      = "testset"
PREFIX      = "TS_"
DONOR_ROOT  = r"%s"
PARENT_MOD  = ""
PACK        = r"%s"
MODEL_PATH  = "models/testset"
CVAR_PREFIX = "ts"
PARENT_RULINGS = {}
''' % (DONORS, tempfile.gettempdir())

GUN_HEAD = '''
GUNS = {
    "smg": {
        "class":    "TS_SMG",
        "donor":    r"Models\\Weapons\\Hud\\BrutalSMG\\BrutalSMG.md3",
        "modeldef": "Modeldef.SMG.def",
        "decorate": "SubMachinegun.txt",
        "hand":     "main",
        "type":     "smg",
'''


def write_set(tmp: str, name: str, body: str) -> str:
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEAD + body)
    return path


def expect_refusal(label: str, fn, must_mention) -> str:
    """Run fn, require a SetError, and require its message to carry each of
    `must_mention`."""
    try:
        fn()
    except SF.SetError as e:
        msg = str(e)
        missing = [m for m in must_mention if m.lower() not in msg.lower()]
        if missing:
            print(f"BAD  {label}: refused, but the message never says {missing}")
            print(f"       {msg}")
            return f"{label}: message missing {missing}"
        print(f"ok   {label}: refused, naming {list(must_mention)}")
        return ""
    print(f"BAD  {label}: accepted, and it should not have been")
    return f"{label}: accepted"


def main() -> int:
    if not os.path.exists(SMG):
        print(f"FAIL: donor SMG not found at {SMG}")
        return 1
    model = MD3.MD3Model.load(SMG)
    names = [s.name for s in model.surfaces]
    print(f"donor BrutalSMG.md3 has {len(names)} surfaces: "
          + ", ".join(f"#{i} '{n}'" for i, n in enumerate(names)) + "\n")

    tmp = tempfile.mkdtemp(prefix="weaponforge_set_")
    failures = []

    # THE DONE-CHECK: a complete map with exactly one surface left out (#2, the
    # SMG's trigger) must be refused, by name.
    left_out = write_set(tmp, "set_left_out.py", GUN_HEAD + '''
        "body":  "#1",
        "parts": {
            "charginghandle": {"surfaces": ["#0"], "role": "action", "subject": "slide"},
            "magazine":       {"surfaces": ["#3"], "role": "feed", "subject": "magazine"},
        },
        "hidden": [],
    },
}
''')
    s = SF.load_set(left_out)
    failures.append(expect_refusal(
        "one surface left out",
        lambda: SF.check_against_mesh(s.guns["smg"], model.surfaces, s.set_id),
        ["#2", names[2], "unaccounted"]))

    # A complete map passes.
    full = write_set(tmp, "set_full.py", GUN_HEAD + '''
        "body":  "#1",
        "parts": {
            "charginghandle": {"surfaces": ["#0"], "role": "action", "subject": "slide"},
            "trigger":        {"surfaces": ["#2"], "role": "trigger"},
            "magazine":       {"surfaces": ["#3"], "role": "feed", "subject": "magazine",
                               "carve": True},
        },
        "hidden": [],
    },
}
''')
    s2 = SF.load_set(full)
    try:
        SF.check_against_mesh(s2.guns["smg"], model.surfaces, s2.set_id)
        print("ok   complete map: accepted")
    except SF.SetError as e:
        failures.append(f"complete map: refused ({e})")
        print(f"BAD  complete map: refused: {e}")

    # An index past the end of the mesh.
    over = write_set(tmp, "set_over.py", GUN_HEAD + '''
        "body":  "#1",
        "parts": {"ghost": {"surfaces": ["#9"], "role": "action"}},
        "fixed": ["#0", "#2", "#3"],
    },
}
''')
    s3 = SF.load_set(over)
    failures.append(expect_refusal(
        "index past the end",
        lambda: SF.check_against_mesh(s3.guns["smg"], model.surfaces, s3.set_id),
        ["#9", "4 surfaces"]))

    # A part with no surfaces at all -- caught at load, before any mesh.
    failures.append(expect_refusal(
        "part with no surfaces",
        lambda: SF.load_set(write_set(tmp, "set_empty_part.py", GUN_HEAD + '''
        "body":  "#1",
        "parts": {"trigger": {"surfaces": [], "role": "trigger"}},
    },
}
''')),
        ["trigger", "no surfaces"]))

    # The same surface owned twice.
    failures.append(expect_refusal(
        "surface claimed twice",
        lambda: SF.load_set(write_set(tmp, "set_twice.py", GUN_HEAD + '''
        "body":  "#1",
        "parts": {
            "trigger": {"surfaces": ["#2"], "role": "trigger"},
            "second":  {"surfaces": ["#2"], "role": "action"},
        },
    },
}
''')),
        ["#2", "two parts"]))

    # A surface named instead of indexed.
    failures.append(expect_refusal(
        "surface given by name",
        lambda: SF.load_set(write_set(tmp, "set_named.py", GUN_HEAD + '''
        "body":  "Sights",
        "parts": {"trigger": {"surfaces": ["#2"], "role": "trigger"}},
    },
}
''')),
        ["Sights", "names repeat"]))

    # A gun with no body and no parts is NOT an error: it is unmapped, and
    # RUN_SET is what stops on it.
    unmapped = SF.load_set(write_set(tmp, "set_unmapped.py", GUN_HEAD + '''
    },
}
'''))
    if unmapped.unmapped == ["smg"]:
        print("ok   unmapped gun: loaded and reported as unmapped, not refused")
    else:
        failures.append(f"unmapped gun: expected ['smg'], got {unmapped.unmapped}")
        print(f"BAD  unmapped gun: {unmapped.unmapped}")

    # A typo in a key must not pass silently.
    failures.append(expect_refusal(
        "typo in a key",
        lambda: SF.load_set(write_set(tmp, "set_typo.py", GUN_HEAD + '''
        "capacty": 40,
        "body":  "#1",
        "parts": {"trigger": {"surfaces": ["#2"], "role": "trigger"}},
    },
}
''')),
        ["capacty", "unknown"]))

    failures = [f for f in failures if f]
    if failures:
        print(f"\nFAIL: {len(failures)} problem(s)")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the set loader refuses an unaccounted surface by name, and every other "
          "malformed map")
    return 0


if __name__ == "__main__":
    sys.exit(main())
