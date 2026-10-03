#!/usr/bin/env python3
"""
emit_grip.py -- write the owner's own placements into the cards. GUN_SEATING_PLAN phase 0.

He placed three points on every one of the 78 guns, by eye, on a solid shaded render of each
gun's real mesh: where his palm closes, where his off hand goes, and where the trigger face is.
This writes those into each gun's own card as `palm`, `supportat` and `triggerat`.

It supersedes emit_palm.py, which transcribed a measured column. Measurement put eight of the
forty-seven "good" palms on the flat side of a receiver and left WM_DoubleBarrel 20 cm off its
own mesh; his pass fixed both. Where the two disagree, he wins -- that is the whole reason the
pass happened.

THE PISTOL RULE. On the thirteen pistols and revolvers he placed the firing hand on one side of
the centreline and the off hand on the other, which is how a two-handed pistol hold actually
works and is not how a card stores it: the engine closes a hand AROUND a point, so both hands
want the handle's axis. Their midpoint is that axis, so for `type = pistol` and `type =
revolver` both `palm` and `supportat` are written as the midpoint of his two clicks. The
separation between the two hands belongs to the engine (Phase C, step 21), not to the card.

IT NEVER WRITES WMCARD.bd22 unless --bd22 is given. The merge lane edits that file, one editor
at a time by agreement; the default is to emit a table for them instead (--table).

Dry run unless --write.

    python forge/emit_grip.py --decisions <dir>              what it would do
    python forge/emit_grip.py --decisions <dir> --write
    python forge/emit_grip.py --decisions <dir> --table bd22.txt
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

ROOT = r"E:\DOOMWork"
CSV_DEFAULT = os.path.join(ROOT, "_reports", "gun_seating_2026-10-02", "WEAPON_SETS.csv")
BD22_CARD = "WMCARD.bd22"
CUPPED = ("pistol", "revolver")          # the off hand cups the firing hand; one point serves both

KEYS = ("palm", "supportat", "triggerat")


def fmt(t) -> str:
    return ", ".join(f"{v:.3f}" for v in t)


def mid(a, b):
    return [(a[i] + b[i]) / 2.0 for i in range(3)]


class Card:
    """One card file, edited line by line, keeping its own newline."""

    def __init__(self, path: str):
        self.nested_grip = 0          # line of a grip block found illegally nested, 0 = none
        raw = open(path, "rb").read()
        self.path = path
        self.crlf = b"\r\n" in raw
        self.nl = "\r\n" if self.crlf else "\n"
        self.lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
        self.dirty = False

    def save(self):
        open(self.path, "wb").write(self.nl.join(self.lines).encode("utf-8"))

    @staticmethod
    def code(l: str) -> str:
        return l.split("#", 1)[0].strip()

    def weapon_at(self, name: str) -> Optional[int]:
        want = re.compile(r'^weapon\s+"' + re.escape(name) + r'"\s*$')
        for i, l in enumerate(self.lines):
            if want.match(self.code(l)):
                return i
        return None

    def weapon_end(self, start: int) -> Optional[int]:
        depth = 0
        for i in range(start + 1, len(self.lines)):
            s = self.code(self.lines[i])
            if not s:
                continue
            head = s.split()[0].lower()
            if head == "end":
                if depth == 0:
                    return i
                depth -= 1
            # A BLOCK OPENS ALONE. `barrel = 1, 0, 0` is a KEY whose name happens to match a
            # block's, and counting it as nesting makes the weapon's own `end` look like a
            # nested one -- which then reports every existing grip block as missing and
            # opens a second.
            elif (head in ("part", "store", "verb", "barrel", "throw", "route", "fuse", "grip")
                  and (len(s.split()) == 1 or not s.split()[1].startswith("="))):
                depth += 1
            elif head == "weapon":
                return None
        return None

    def grip_block(self, weapon_start: int) -> Optional[Tuple[int, int]]:
        """This card's grip block, wherever it sits.

        Most cards put it after the weapon block's `end`, which is where the forge writes
        one. WMCARD.grenade nests it INSIDE the weapon block instead, and the parser takes
        either. So the search starts at the weapon line rather than at its end: starting
        after the end misses a nested one, reports the card as having no grip, and opens a
        second -- which the parser then refuses outright ("this card already has a grip
        block") and the refusal takes the next weapon down with it.
        """
        # A GRIP NESTED INSIDE A PART IS NOT THIS CARD'S GRIP BLOCK.
        #
        # WMCARD.grenade had one inside `part pin`, which the parser refuses outright ("a grip
        # cannot open inside a part") and the refusal takes the weapons after it down too. It
        # had been there since before this tool existed and nothing had noticed, because
        # nothing had needed to rebuild that pack. Writing keys into it is what surfaced it --
        # so this now tracks depth and only accepts a grip at the card's own level: inside the
        # weapon block, or after its `end` at the top level. A grip found deeper is reported
        # rather than written to, because the card needs fixing by hand first.
        depth = 0
        for i in range(weapon_start + 1, len(self.lines)):
            s = self.code(self.lines[i])
            if not s:
                continue
            head = s.split()[0].lower()
            alone = (len(s.split()) == 1 or not s.split()[1].startswith("="))
            if head == "weapon":
                return None
            if head == "grip" and alone:
                if depth > 0:
                    self.nested_grip = i + 1          # 1-based, for the report
                    return None
                for j in range(i + 1, len(self.lines)):
                    if self.code(self.lines[j]).lower() == "end":
                        return (i, j)
                return None
            if head == "end":
                depth = max(0, depth - 1)
            elif head in ("part", "store", "verb", "barrel", "throw", "route", "fuse") and alone:
                depth += 1
        return None

    def set_keys(self, weapon: str, vals: Dict[str, List[float]], note: str) -> str:
        w = self.weapon_at(weapon)
        if w is None:
            return f"SKIP   {weapon}: not in {os.path.basename(self.path)}"
        we = self.weapon_end(w)
        if we is None:
            return f"SKIP   {weapon}: weapon block not closed"
        self.nested_grip = 0
        blk = self.grip_block(w)
        if blk is None and self.nested_grip:
            return (f"REFUSE {weapon}: its grip block is nested inside a part or verb "
                    f"(line {self.nested_grip}) -- the parser refuses that and the refusal "
                    f"takes the next weapon with it. Move the grip out of the block first.")
        if blk is None:
            body = ["", f"# THE GRIP: placed by the owner on the mesh, {note}", "grip"]
            body += [f"  {k} = {fmt(vals[k])}" for k in KEYS if k in vals]
            body += ["end"]
            self.lines[we + 1:we + 1] = body
            self.dirty = True
            return f"NEW    {weapon}: grip block opened with {len(vals)} points"
        lo, hi = blk
        changed = []
        for k in KEYS:
            if k not in vals:
                continue
            line = f"  {k} = {fmt(vals[k])}"
            at = None
            want = re.compile(r"^" + k + r"\s*=", re.IGNORECASE)
            for i in range(lo + 1, hi):
                if want.match(self.code(self.lines[i])):
                    at = i
                    break
            if at is None:
                self.lines[lo + 1:lo + 1] = [line]
                hi += 1
                changed.append(k + "+")
            elif self.code(self.lines[at]) != line.strip():
                self.lines[at] = line
                changed.append(k)
        if changed:
            self.dirty = True
            return f"SET    {weapon}: " + " ".join(changed)
        return f"same   {weapon}"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions", required=True, help="directory of per-gun decision json")
    ap.add_argument("--csv", default=CSV_DEFAULT)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--bd22", action="store_true", help="also write WMCARD.bd22 (coordinate first)")
    ap.add_argument("--table", default="", help="write the BD22 values out as a table here")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)

    rows = {r["weapon_class"].strip(): r for r in
            csv.DictReader(open(a.csv, encoding="utf-8-sig"))}

    cards: Dict[str, Card] = {}
    out: List[str] = []
    held: List[str] = []
    table: List[str] = []
    cupped_n = 0

    for f in sorted(glob.glob(os.path.join(a.decisions, "*.json"))):
        rec = json.load(open(f, encoding="utf-8"))
        rec = rec.get("data", rec)
        w = rec.get("weapon")
        row = rows.get(w)
        if not row:
            held.append(f"{w}: not in the report")
            continue
        if rec.get("state") == "nohandle":
            held.append(f"{w}: marked 'no handle here'")
            continue

        gtype = (row.get("card_type") or "").strip().lower()
        palm = rec.get("palm")
        sup = rec.get("support")
        trg = rec.get("trigger")
        if not palm:
            held.append(f"{w}: no palm")
            continue

        vals: Dict[str, List[float]] = {}
        if gtype in CUPPED and sup:
            m = mid(palm, sup)
            vals["palm"] = m
            vals["supportat"] = m
            cupped_n += 1
        else:
            vals["palm"] = palm
            if sup:
                vals["supportat"] = sup
        if trg:
            vals["triggerat"] = trg

        rel = row["card"].split(":")[0].strip()
        if os.path.basename(rel) == BD22_CARD:
            table.append(f"{w:22} palm {fmt(vals['palm']):28} "
                         f"supportat {fmt(vals.get('supportat', vals['palm'])):28} "
                         f"triggerat {fmt(vals['triggerat']) if 'triggerat' in vals else '-'}")
            if not a.bd22:
                continue

        path = os.path.join(a.root, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            # the report's path can be stale; find the card by name under its folder
            cand = glob.glob(os.path.join(a.root, os.path.dirname(rel).replace("/", os.sep),
                                          "**", os.path.basename(rel)), recursive=True)
            if not cand:
                held.append(f"{w}: no card file at {rel}")
                continue
            path = cand[0]
        if path not in cards:
            cards[path] = Card(path)
        note = "two-handed hold averaged to the handle axis" if gtype in CUPPED else "as he placed it"
        out.append(f"  {os.path.basename(path):26} " + cards[path].set_keys(w, vals, note))

    for l in out:
        print(l)
    if held:
        print("\nHELD BACK:")
        for l in held:
            print("  " + l)
    changed = [c for c in cards.values() if c.dirty]
    print(f"\n{len(out)} guns written across {len(changed)} files; "
          f"{cupped_n} pistols/revolvers averaged to the handle axis"
          f"{'' if a.write else '   (DRY RUN -- pass --write)'}")
    if a.write:
        for c in changed:
            c.save()
            print(f"  wrote {os.path.relpath(c.path, a.root)} ({'CRLF' if c.crlf else 'LF'})")
    if a.table and table:
        with open(a.table, "w", encoding="utf-8") as fh:
            fh.write("# BD22 grip points, placed by the owner 2026-10-03, mesh units, card axes.\n")
            fh.write("# Pistols and revolvers: palm and supportat are the same point by design.\n\n")
            fh.write("\n".join(table) + "\n")
        print(f"  table -> {a.table}  ({len(table)} guns)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
