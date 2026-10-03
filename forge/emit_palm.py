#!/usr/bin/env python3
"""
emit_palm.py -- write each gun's PALM POINT into its own card. GUN_SEATING_PLAN.md step 2.

WHY A PALM AND NOT A SEAT
-------------------------
A card's `seat` is the mesh point that sits at the OpenXR AIM pose's origin, because every one
of the 62 seats was back-solved from MODELDEF Offset (grip.py grip_from_placement). On a real
gun the aim origin is about the TRIGGER: on WM_M4A3 the handle's centre is 4.65 cm behind the
seat and 11.5 cm below it. So a seat cannot place a hand, and no amount of tuning would make it
able to -- the offset a seat absorbs is the gap between the controller's aim pose and its grip
pose, which is a fact about the CONTROLLER, not about the gun. That is what 61 per-gun sets of
ten sliders were trying to cancel, and 29 of 76 guns were still wrong.

`palm` is a point ON THE HANDLE instead. That makes it a fact about the mesh, true whatever the
engine, the controller or the body does, which is the whole reason this stops being a fight.

WHERE THE NUMBERS COME FROM
---------------------------
_reports/gun_seating_2026-10-02/WEAPON_SETS.csv, column `palm_point`, measured off each mesh.
This tool only transcribes; it does not derive. Two independent checks that the column is a real
palm derivation and not something else wearing its name:

  * The six Star Wars guns were authored origin-on-grip and carry no grip block at all. Their
    measured palm points land 1.6-2.6 cm from the model origin -- the measurement rediscovers a
    convention it was never told about.
  * Only WM_M4A3 and WM_Pistolet have a palm point equal to their card's `magcenter`, and both
    are 1911-pattern pistols whose magazine genuinely sits inside the grip frame. The other 32
    guns with a magazine differ by 2.7 to 67 cm, so the column is not the magazine centroid.

WHAT IT WILL NOT DO
-------------------
  * It will not touch a card whose palm is already stated and DIFFERENT -- a hand-placed palm is
    the owner's and outranks a measurement (--force overrides, and says so per gun).
  * It will not emit a palm further than --max-mesh-cm from the mesh surface. That is forge gate
    G-PALM (step 5) applied at the source: a palm floating off the gun is the one failure that
    looks fine in a card and wrong only in a headset.
  * It will not regenerate a card. Vanilla, Vanilla+ and the hand-authored sets stay exactly as
    they are; this inserts or updates ONE line and leaves every comment and every byte else
    alone, including each file's own line endings (bd22's cards are CRLF, the rest LF).

Dry run unless --write is given. Standard library only.

  python forge/emit_palm.py                          what it would do to the 47 OK guns
  python forge/emit_palm.py --write
  python forge/emit_palm.py --verdict OK,LOW --write
  python forge/emit_palm.py --only WM_M4A3 --write
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

ROOT = r"E:\DOOMWork"
CSV_DEFAULT = os.path.join(ROOT, "_reports", "gun_seating_2026-10-02", "WEAPON_SETS.csv")

# Step 5's threshold. A palm more than this from the mesh surface is not on the gun.
MAX_MESH_CM = 2.5

# ...BUT DISTANCE ALONE IS NOT ENOUGH, and this is the one place to say why.
#
# `palm_dist_to_mesh_cm` is satisfied by being near ANY surface, including the flat side of the
# gun's body. All 47 verdict-OK guns pass the 2.5 cm gate, and eight of them still have a palm
# that no hand could close on: WM_PumpM37 at 0.17 enclosure, BD_Flamethrower at 0.27,
# BD_RPG and BD_Dragonslayer with no measured cross-section at all. A palm beside the receiver
# is 1 cm from the mesh and completely wrong.
#
# `palm_enclosure` is the test that separates them: how much of the mesh wraps the point. A real
# handle encloses it (35 of the 47 are at 0.9 or better); a point lying against a flat face does
# not. A zero section means the measurement found no handle there at all, which is a refusal
# rather than a low score.
MIN_ENCLOSURE = 0.5


# ---- values ----------------------------------------------------------------------------

def read_triple(s: str) -> Optional[Tuple[float, float, float]]:
    """A CSV triple, space- or comma-separated, or None."""
    parts = [p for p in s.strip().replace(",", " ").split() if p]
    if len(parts) != 3:
        return None
    try:
        return tuple(float(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def fmt_triple(t: Tuple[float, float, float]) -> str:
    """Three decimals, which is 0.008 mm at the finest scale in the fleet and matches the
    precision the cards already use for `seat` and `magcenter`."""
    return ", ".join(f"{v:.3f}" for v in t)


def same_point(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> bool:
    # Half of the written precision, so a re-run of this tool is a no-op rather than a rewrite.
    return all(abs(x - y) < 0.0005 for x, y in zip(a, b))


# ---- cards -----------------------------------------------------------------------------

class Card:
    """One card file, held as lines, with its own newline kept."""

    def __init__(self, path: str):
        with open(path, "rb") as f:
            raw = f.read()
        self.path = path
        self.crlf = b"\r\n" in raw
        self.nl = "\r\n" if self.crlf else "\n"
        self.text = raw.decode("utf-8")
        self.lines = self.text.replace("\r\n", "\n").split("\n")
        self.dirty = False

    def save(self) -> None:
        out = self.nl.join(self.lines)
        with open(self.path, "wb") as f:
            f.write(out.encode("utf-8"))

    @staticmethod
    def _code(line: str) -> str:
        return line.split("#", 1)[0].strip()

    def weapon_at(self, name: str) -> Optional[int]:
        want = re.compile(r'^weapon\s+"' + re.escape(name) + r'"\s*$')
        for i, l in enumerate(self.lines):
            if want.match(self._code(l)):
                return i
        return None

    def weapon_end(self, start: int) -> Optional[int]:
        """The `end` closing the weapon block itself. Nested blocks (part, store, verb, barrel)
        each have their own `end`, so count depth rather than taking the first one."""
        depth = 0
        for i in range(start + 1, len(self.lines)):
            s = self._code(self.lines[i])
            if not s:
                continue
            head = s.split()[0].lower()
            if head == "end":
                if depth == 0:
                    return i
                depth -= 1
            elif head in ("part", "store", "verb", "barrel", "throw", "route", "fuse", "grip") \
                    and (len(s.split()) == 1 or "=" not in s.split()[1][:1]):
                depth += 1
            elif head == "weapon":
                return None
        return None

    def grip_block(self, weapon_end: int) -> Optional[Tuple[int, int]]:
        """(open line, end line) of the grip block belonging to the weapon that closes at
        weapon_end -- the next grip block before the next weapon. The parser attaches a grip to
        the card it is reading (parser.zs:513), and the forge writes it right after the weapon's
        `end` (grip.py with_grip), so position is the association."""
        for i in range(weapon_end + 1, len(self.lines)):
            s = self._code(self.lines[i])
            if not s:
                continue
            head = s.split()[0].lower()
            if head == "weapon":
                return None
            if head == "grip" and (len(s.split()) == 1 or not s.split()[1].startswith("=")):
                for j in range(i + 1, len(self.lines)):
                    if self._code(self.lines[j]).lower() == "end":
                        return (i, j)
                return None
        return None

    def grip_key(self, lo: int, hi: int, key: str) -> Optional[int]:
        want = re.compile(r"^" + re.escape(key) + r"\s*=", re.IGNORECASE)
        for i in range(lo + 1, hi):
            if want.match(self._code(self.lines[i])):
                return i
        return None


# ---- the one edit ----------------------------------------------------------------------

def set_palm(card: Card, weapon: str, palm: Tuple[float, float, float], note: str,
             force: bool) -> str:
    """Insert or update `palm` in this weapon's grip block. Returns what happened."""
    w = card.weapon_at(weapon)
    if w is None:
        return f"SKIP   no `weapon \"{weapon}\"` in {os.path.basename(card.path)}"
    we = card.weapon_end(w)
    if we is None:
        return f"SKIP   {weapon}: weapon block is not closed by an `end`"

    line = f"  palm = {fmt_triple(palm)}"
    blk = card.grip_block(we)

    if blk is None:
        # No grip block yet -- open one straight after the weapon's `end`, which is where the
        # forge puts it and where the parser expects to find it.
        block = ["", f"# THE PALM: the centre of the handle where the palm closes ({note})",
                 "grip", line, "end"]
        card.lines[we + 1:we + 1] = block
        card.dirty = True
        return f"NEW    {weapon}: grip block opened, palm = {fmt_triple(palm)}"

    lo, hi = blk
    at = card.grip_key(lo, hi, "palm")
    if at is None:
        card.lines[lo + 1:lo + 1] = [line]
        card.dirty = True
        return f"ADD    {weapon}: palm = {fmt_triple(palm)}"

    cur = read_triple(card._code(card.lines[at]).split("=", 1)[1])
    if cur is not None and same_point(cur, palm):
        return f"same   {weapon}: palm already {fmt_triple(palm)}"
    if cur is not None and not force:
        return (f"KEPT   {weapon}: card says {fmt_triple(cur)}, measured {fmt_triple(palm)} "
                f"-- a stated palm is the owner's; --force to overwrite")
    card.lines[at] = line
    card.dirty = True
    return f"FORCED {weapon}: {fmt_triple(cur) if cur else '?'} -> {fmt_triple(palm)}"


# ---- main ------------------------------------------------------------------------------

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="write measured palm points into weapon cards")
    ap.add_argument("--csv", default=CSV_DEFAULT)
    ap.add_argument("--root", default=ROOT, help="what the CSV's card paths are relative to")
    ap.add_argument("--verdict", default="OK",
                    help="comma-separated `inspection` verdicts to emit (default OK)")
    ap.add_argument("--only", default="", help="comma-separated weapon classes, for one gun")
    ap.add_argument("--max-mesh-cm", type=float, default=MAX_MESH_CM,
                    help=f"refuse a palm further than this from the mesh (G-PALM, default {MAX_MESH_CM})")
    ap.add_argument("--min-enclosure", type=float, default=MIN_ENCLOSURE,
                    help=f"refuse a palm the mesh does not wrap this much (default {MIN_ENCLOSURE})")
    ap.add_argument("--force", action="store_true", help="overwrite a palm already on a card")
    ap.add_argument("--write", action="store_true", help="apply; otherwise print and change nothing")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.csv):
        print(f"no CSV at {a.csv}", file=sys.stderr)
        return 2

    verdicts = {v.strip().upper() for v in a.verdict.split(",") if v.strip()}
    only = {w.strip() for w in a.only.split(",") if w.strip()}

    with open(a.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    cards: Dict[str, Card] = {}
    out: List[str] = []
    refused: List[str] = []
    done = 0

    for r in rows:
        weapon = r["weapon_class"].strip()
        verdict = r["inspection"].strip().upper()
        if only:
            if weapon not in only:
                continue
        elif verdict not in verdicts:
            continue

        palm = read_triple(r["palm_point"])
        if palm is None:
            refused.append(f"{weapon}: no palm_point in the CSV")
            continue

        # G-PALM at the source. A palm off the mesh is the failure that reads fine in a card.
        try:
            dist = float(r["palm_dist_to_mesh_cm"])
        except (KeyError, TypeError, ValueError):
            dist = -1.0
        if dist > a.max_mesh_cm:
            refused.append(f"{weapon}: palm is {dist:.1f} cm from the mesh, over the "
                           f"{a.max_mesh_cm} cm gate -- it is not on the gun")
            continue

        # ...and the gate that actually discriminates: is there a HANDLE there?
        section = r.get("palm_section_cm", "").strip()
        if section in ("", "0.0x0.0"):
            refused.append(f"{weapon}: no handle cross-section measured at the palm "
                           f"({dist:.1f} cm from the mesh) -- the measurement found nothing to hold")
            continue
        try:
            encl = float(r["palm_enclosure"])
        except (KeyError, TypeError, ValueError):
            encl = -1.0
        if 0.0 <= encl < a.min_enclosure:
            refused.append(f"{weapon}: palm enclosure {encl:.2f} is under {a.min_enclosure} "
                           f"-- the mesh does not wrap it, so it is beside the gun and not in a hand")
            continue

        rel = r["card"].split(":")[0].strip()
        path = os.path.join(a.root, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            refused.append(f"{weapon}: no card file at {rel}")
            continue
        if path not in cards:
            cards[path] = Card(path)

        note = f"measured {verdict}, {r['set'].strip()}, {dist:.1f} cm from the mesh"
        msg = set_palm(cards[path], weapon, palm, note, a.force)
        out.append(f"  {rel:42} {msg}")
        if msg.split()[0] in ("NEW", "ADD", "FORCED"):
            done += 1

    for l in out:
        print(l)
    if refused:
        print("\nREFUSED:")
        for l in refused:
            print(f"  {l}")

    changed = [c for c in cards.values() if c.dirty]
    print(f"\n{done} palm points in {len(changed)} of {len(cards)} card files"
          f"{'' if a.write else '  (dry run -- nothing written; pass --write)'}")
    if a.write:
        for c in changed:
            c.save()
            print(f"  wrote {os.path.relpath(c.path, a.root)} ({'CRLF' if c.crlf else 'LF'})")
    return 1 if refused and not out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
