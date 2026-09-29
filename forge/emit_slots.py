#!/usr/bin/env python3
"""emit_slots.py -- the set's number keys, written from the Weapon Cards.

WHY THIS EXISTS. BD22 shipped a hand-made `RS_VR_BD22_Slots.pk3` whose KEYCONF put the
guns on ten slots (melee 1, pistols 2, shotguns 3, rifles 4, launchers 5, energy 6, BFGs
7, heavy 8, flame 9, grenade 0) while the Weapon Cards declared seven. Every slot
disagreed: the grenade was on `0` and declared 1, the SMG and MP40 sat on `2` and
declared 4, the Unmaker was on `8` and declared 7.

AND THE CARD WINS. The set bridge calls `WeaponSlots.SetupWeaponSlots(pmo)` after it swaps
the parent mod's guns for ours, which rebuilds the slots from each class's own
`Weapon.SlotNumber` -- the sheet's number. So the hand-made layout was overwritten the
moment the bridge did its job, and the pk3 was decoration that looked authoritative.

So the KEYCONF is DERIVED: slot from the sheet's `slot`, order within a slot from its
`selectionorder`. The two cannot disagree again, and a gun added to the set reaches the
number keys without anyone remembering to edit a second file.

A NEW `weaponsection` NAME IS DELIBERATE. The engine skips a weaponsection whose name has
already run, so the set needs its own rather than adding to the parent's.
"""

from __future__ import annotations

import os
import re
import zipfile
from typing import Dict, List, Optional, Tuple


def read_sheet_slots(sheet_path: str) -> Dict[str, List[str]]:
    """{slot: [class, ...]} out of a WMSHEET, each slot in selection order."""
    text = open(sheet_path, encoding="utf-8", errors="replace").read()
    by_slot: Dict[str, List[Tuple[int, str]]] = {}
    for block in re.split(r'(?m)^gun\s+"', text)[1:]:
        cls = block.split('"')[0]
        slot = re.search(r'(?m)^\s*slot\s*=\s*(\d+)', block)
        order = re.search(r'(?m)^\s*selectionorder\s*=\s*(\d+)', block)
        if not slot:
            continue                      # a gun on no slot is reached another way
        by_slot.setdefault(slot.group(1), []).append(
            (int(order.group(1)) if order else 0, cls))
    return {s: [c for _o, c in sorted(v)] for s, v in by_slot.items()}


def keyconf_text(section: str, by_slot: Dict[str, List[str]], set_id: str) -> str:
    """The KEYCONF a set's slots pk3 carries."""
    lines = [
        f"// RS_VR_{set_id.upper()}_Slots -- WRITTEN BY WEAPONFORGE from WMSHEET.{set_id}.",
        "// Do not edit by hand: change the sheet's `slot` and run RUN_SET again.",
        "//",
        "// The slot is the sheet's own `slot` and the order within it is `selectionorder`,",
        "// because the set bridge's WeaponSlots.SetupWeaponSlots rebuilds the slots from",
        "// each class's Weapon.SlotNumber -- so anything written here that disagreed with",
        "// the sheet was overwritten the moment the bridge swapped a gun.",
        "//",
        "// A NEW section name on purpose: the engine skips a weaponsection whose name has",
        "// already run, so this adds to the parent mod's rather than fighting it.",
        f'weaponsection "{section}"',
    ]
    # 1..9 then 0, the way a keyboard reads.
    for s in [str(i) for i in range(1, 10)] + ["0"]:
        if s in by_slot:
            lines.append(f"setslot {s} " + " ".join(by_slot[s]))
    return "\n".join(lines) + "\n"


def write_slots_pack(pack_dir: str, set_id: str, section: str,
                     sheet_path: Optional[str] = None) -> Optional[str]:
    """Rewrite <pack>/RS_VR_<SET>_Slots.pk3 from the sheet. Returns a one-line report.

    Only ever touches a slots pk3 that already exists: a set that does not ship one is
    not given one behind the owner's back.
    """
    sheet_path = sheet_path or os.path.join(pack_dir, f"WMSHEET.{set_id}")
    if not os.path.isfile(sheet_path):
        return None
    target = None
    for name in os.listdir(pack_dir):
        if name.lower().endswith("_slots.pk3"):
            target = os.path.join(pack_dir, name)
            break
    if target is None:
        return None

    by_slot = read_sheet_slots(sheet_path)
    if not by_slot:
        return None
    text = keyconf_text(section, by_slot, set_id)

    was = ""
    try:
        with zipfile.ZipFile(target) as z:
            was = z.read("KEYCONF.txt").decode("utf-8", "replace")
    except Exception:
        pass

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("KEYCONF.txt", text)

    guns = sum(len(v) for v in by_slot.values())
    changed = "" if _same_slots(was, text) else ", CHANGED"
    return (f"{os.path.basename(target)}: {guns} gun(s) on "
            f"{len(by_slot)} slot(s) from the sheet{changed}")


def _same_slots(a: str, b: str) -> bool:
    """Do two KEYCONFs put the same guns on the same slots? Comments do not count."""
    def rows(t):
        return sorted(m.group(0).split() for m in
                      re.finditer(r'(?m)^setslot\s+\d+\s+.*$', t))
    return rows(a) == rows(b)
