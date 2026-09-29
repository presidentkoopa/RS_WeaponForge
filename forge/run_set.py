#!/usr/bin/env python3
"""
run_set.py -- the six stages, in order, stopping at the first failure.
Step 10 of the WeaponForge Build Guide. RUN_SET.bat calls this.

    python -m forge.run_set <set> [--no-copy] [--reference <pack>]

    1  parent_audit on the set's parent mod. Stops if a finding is not ruled on
       in set.py's PARENT_RULINGS.
    2  Per gun: resolve the rest frame, measure the motion, write a proposal.
       Stops if any gun has no part map yet, and names it.
    3  Emit the meshes, carves, cards, prop MODELDEF and cvars into out\\.
    4  card_lint, set_gate, and compare when the set has a reference.
    5  Only if all pass: copy out\\ into the pack.
    6  Print the in-game step.

Exit code 0 only when every stage passed.

ONE LINE PER FAILURE. A build tool that stops with a stack trace makes the next
person read code to find out what is wrong with their data. Every stop here says
what failed, for which gun, and what to do about it -- and the stage that stops
is the stage that found it, so nothing downstream runs on a bad input and
produces a second, misleading error.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from . import compare as CM
from . import donor as D
from . import emit_card as EC
from . import emit_prop as EP
from . import measure as ME
from . import md3 as MD3
from . import motion as MO
from . import setfile as SF

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _run(script: str, args: Sequence[str], pkg: Optional[str] = None) -> Tuple[int, str]:
    """A ported checker, run as its own process so its exit code is its verdict."""
    cmd = [sys.executable, os.path.join(HERE, script), *args]
    env = dict(os.environ)
    if pkg:
        env["WEAPONFORGE_PKG"] = pkg.replace("\\", "/").rstrip("/") + "/"
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def stage_parent(sf: SF.SetFile, out_dir: str) -> Optional[str]:
    """parent_audit, and every finding it reports must be ruled on in set.py."""
    if not sf.parent_mod:
        print("  1 parent mod   none declared, nothing to audit")
        return None
    if not os.path.exists(sf.parent_mod):
        return f"the parent mod is not there: {sf.parent_mod}"
    report = os.path.join(out_dir, "PARENT_AUDIT.md")
    code, text = _run("parent_audit.py", [sf.parent_mod, "--out", report])
    must = [l for l in text.splitlines() if "must-fix" in l]
    print(f"  1 parent mod   audited, report in {os.path.relpath(report, ROOT)}"
          + (f" ({must[-1].strip()})" if must else ""))
    unruled = [k for k in _findings(text) if k not in sf.parent_rulings]
    if unruled:
        return (f"{len(unruled)} parent-mod finding(s) with no ruling in set.py's "
                f"PARENT_RULINGS: {unruled[:4]}")
    return None


def _findings(text: str) -> List[str]:
    """The audit's must-fix items, as keys a set file can rule on."""
    keys = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("- `ammo:") or s.startswith("`ammo:"):
            keys.append(s.strip("- `").split("`")[0])
    return keys


def stage_proposals(sf: SF.SetFile, out_dir: str) -> Optional[str]:
    """A proposal per gun, and a stop on any gun with no part map."""
    prop_dir = os.path.join(os.path.dirname(sf.path), "proposals")
    os.makedirs(prop_dir, exist_ok=True)
    written = 0
    for gid, gun in sf.guns.items():
        try:
            d = D.read_donor(gid, sf.donor_root, gun.donor, gun.modeldef, gun.decorate,
                             rest_frame=gun.rest_frame, actor=gun.actor)
        except D.DonorError as e:
            return f"{gid}: {e}"
        model = MD3.MD3Model.load(d.md3)
        body = gun.body if gun.body is not None else max(
            range(len(model.surfaces)), key=lambda i: model.surfaces[i].num_verts)
        mo = MO.measure_motion(model, body_index=body, rest_frame=d.rest_frame, gun=gid)
        MO.write_proposal(os.path.join(prop_dir, f"{gid}.txt"), mo)
        written += 1
    print(f"  2 proposals    {written} written to "
          f"{os.path.relpath(prop_dir, ROOT)}")
    unmapped = sf.unmapped
    if unmapped:
        return (f"{len(unmapped)} gun(s) have no part map yet: {unmapped}. Read their "
                f"proposals and write body and parts into set.py.")
    return None


def stage_emit(sf: SF.SetFile, out_dir: str) -> Tuple[Optional[str], List[str]]:
    """Meshes, carves, cards, the prop MODELDEF and the cvars."""
    models_dir = os.path.join(out_dir, sf.model_path.replace("/", os.sep))
    os.makedirs(models_dir, exist_ok=True)
    cards, props, cvars, skipped = [], [], [], []
    for gid, gun in sf.guns.items():
        try:
            built = CM.build_gun(sf, gun, models_dir)
        except (D.DonorError, SF.SetError, ValueError) as e:
            return f"{gid}: {e}", []
        skipped.extend(f"{gid}: {s}" for s in built.skipped)
        cards.append(EC.write_card(gun, built.prop, built.muzzle, built.barrel, built.parts,
                                   sf.model_path, f"{gid}_wm.md3", sf.model_path,
                                   f"{gid}.png", built.surface_names,
                                   ejection=built.ejection, support=built.support,
                                   load=built.load, part_names=built.mesh.part_names))
        props.append(built.prop.modeldef())
        cvars.append(built.prop.cvarinfo())

    card_path = os.path.join(out_dir, f"WMCARD.{sf.set_id}")
    EC.write_set_cards(card_path, cards, sf.set_id)
    with open(os.path.join(out_dir, "MODELDEF.txt"), "w", encoding="utf-8") as f:
        f.write(f"// Written by WeaponForge for set {sf.set_id}. Do not edit by hand.\n\n")
        f.write("\n".join(props))
    with open(os.path.join(out_dir, "CVARINFO.txt"), "w", encoding="utf-8") as f:
        f.write(f"// Written by WeaponForge for set {sf.set_id}. Do not edit by hand.\n")
        f.write("// The owner tunes ofs_* in the headset; the angles are what the offset\n")
        f.write("// arithmetic is valid at.\n\n")
        f.write("\n".join(cvars))
    # The set's own human files travel with it: a ruling belongs to the set, not to
    # the pack it lands in, so it ships from beside set.py rather than being typed
    # into the pack by hand.
    carried = []
    for name in ("RULINGS.txt", "PLACEMENT_TODO.txt"):
        src = os.path.join(os.path.dirname(sf.path), name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(out_dir, name))
            carried.append(name)
    print(f"  3 emitted      {len(cards)} card(s), {len(props)} prop(s), meshes in "
          f"{os.path.relpath(models_dir, ROOT)}"
          + (f"; carried {', '.join(carried)}" if carried else ""))
    return None, skipped


def stage_check(sf: SF.SetFile, out_dir: str, reference: Optional[str]) -> Optional[str]:
    """card_lint, set_gate, and compare against a reference when there is one.

    card_lint and set_gate ask whether a set will PLAY: they want the weapon
    classes declared in ZScript, the props declared, the ammo bridged. A set whose
    PACK is its own out/ folder is not packed anywhere and has no ZScript -- it
    exists to be measured and compared, which is what vanilla_check is. Running a
    playability gate on it would report a missing class as a fault in a set that
    was never meant to load, so those two run for a set that ships, and compare
    runs for every set.
    """
    card_path = os.path.join(out_dir, f"WMCARD.{sf.set_id}")
    ships = bool(sf.pack) and os.path.abspath(sf.pack) != os.path.abspath(out_dir)
    if not ships:
        print("  4 card_lint    not run: this set is not packed anywhere, so it has no "
              "classes to check")
        print("  4 set_gate     not run, same reason")
        if reference:
            findings, notes = CM.compare_set(sf.path, reference, out_dir)
            if findings:
                return (f"compare: {len(findings)} value(s) outside tolerance against "
                        f"{reference}")
            print(f"  4 compare      every value within tolerance of {reference}")
        return None
    # WHAT THE PACK WILL BE, not what out/ is on its own. card_lint asks whether a
    # class is declared, whether a sound is in a SNDINFO, whether a mesh is on disk
    # -- and those live in the pack this set ships into, while the meshes are the
    # ones just written. So the two are staged together, exactly as the copy will
    # leave them, and the card is checked against that. Checking out/ alone reports
    # every class in the set as undeclared, which is true of the folder and false of
    # the pack.
    root = _stage(sf, out_dir) if ships else out_dir
    code, text = _run("card_lint.py", ["--file", card_path], pkg=root)
    last = text.strip().splitlines()[-1] if text.strip() else ""
    if code != 0:
        print(text.strip()[-2000:])
        return f"card_lint: {last}"
    print(f"  4 card_lint    {last}")

    # THE WEAPON CARD (WMSHEET.*) IS CHECKED TOO. card_lint has always been able to do
    # this and RUN_SET never asked it to, so what a gun IS went unchecked while how it
    # MOVES was checked every run. BD22 shipped green with twelve ballistics profiles
    # that resolved to nothing: eight guns firing with no recoil, two rounds with no
    # look, and two beams declared as bullets. The check existed. Nothing called it.
    code, text = _run("card_lint.py", ["--sheets"], pkg=root)
    last = text.strip().splitlines()[-1] if text.strip() else ""
    if code != 0:
        print(text.strip()[-2000:])
        return f"card_lint --sheets: {last}"
    print(f"  4 sheet_lint   {last}")

    code, text = _run("set_gate.py", [root])
    gate = [l for l in text.splitlines() if l.strip().startswith(("FAIL", "PASS"))]
    print(f"  4 set_gate     {gate[-1].strip() if gate else 'ran'}")
    if code != 0:
        print(text.strip()[-2000:])
        return "set_gate refused the set"

    if reference:
        findings, notes = CM.compare_set(sf.path, reference, out_dir)
        if findings:
            return f"compare: {len(findings)} value(s) outside tolerance against {reference}"
        print(f"  4 compare      every value within tolerance of {reference}")
    return None


def _stage(sf: SF.SetFile, out_dir: str) -> str:
    """The pack with this build overlaid on it, for the checkers to read.

    Only what a checker reads is staged -- lumps, zscript, models -- and never the
    pk3s, which are 175MB in BD22's case and are not what a checker looks at. The
    overlay order is the copy's: ours wins, because ours is what will replace them.
    """
    stage = os.path.join(os.path.dirname(out_dir), "_staging")
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage, exist_ok=True)
    for root, dirs, files in os.walk(sf.pack):
        rel = os.path.relpath(root, sf.pack)
        if rel != "." and rel.split(os.sep)[0] in ("_staging", "out"):
            continue
        target = stage if rel == "." else os.path.join(stage, rel)
        os.makedirs(target, exist_ok=True)
        for f in files:
            if f.lower().endswith((".pk3", ".wad", ".zip")):
                continue
            shutil.copy2(os.path.join(root, f), os.path.join(target, f))
    for root, _dirs, files in os.walk(out_dir):
        rel = os.path.relpath(root, out_dir)
        target = stage if rel == "." else os.path.join(stage, rel)
        os.makedirs(target, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(target, f))
    return stage


def stage_copy(sf: SF.SetFile, out_dir: str, do_copy: bool) -> Optional[str]:
    if not do_copy:
        print("  5 copy         skipped (--no-copy)")
        return None
    if not sf.pack:
        return "set.py names no PACK to copy into"
    dest = sf.pack
    if os.path.abspath(dest) == os.path.abspath(out_dir):
        print("  5 copy         PACK is out\\ itself, nothing to copy")
        return None
    os.makedirs(dest, exist_ok=True)
    n = 0
    for root, _dirs, files in os.walk(out_dir):
        rel = os.path.relpath(root, out_dir)
        target = dest if rel == "." else os.path.join(dest, rel)
        os.makedirs(target, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(target, f))
            n += 1
    print(f"  5 copy         {n} file(s) into {dest}")
    return None


def stage_ingame(sf: SF.SetFile) -> None:
    print("  6 in game      load the pack, then:")
    print("                   logfile proof.txt")
    print(f"                   wm_proof {sf.prefix}")


def run(set_name: str, do_copy: bool = True, reference: Optional[str] = None) -> int:
    set_path = set_name
    if not os.path.isfile(set_path):
        set_path = os.path.join(ROOT, "sets", set_name, "set.py")
    if not os.path.isfile(set_path):
        print(f"RUN_SET: no set file at {set_path}")
        return 2
    sf = SF.load_set(set_path)
    out_dir = os.path.join(os.path.dirname(set_path), "out")
    # OUT IS THE TOOL'S, and it is emptied at the start of every run. A file left
    # from a previous run is worse than no file: it is a mesh or a card that
    # nothing in this run produced, sitting in the folder that gets copied into
    # the pack, and it would be checked and shipped as though it belonged.
    if os.path.isdir(out_dir):
        for name in os.listdir(out_dir):
            victim = os.path.join(out_dir, name)
            if name == ".gitkeep":
                continue
            shutil.rmtree(victim) if os.path.isdir(victim) else os.remove(victim)
    os.makedirs(out_dir, exist_ok=True)
    print(f"RUN_SET {sf.set_id}: {len(sf.guns)} gun(s), out in "
          f"{os.path.relpath(out_dir, ROOT)}")

    for stage in (lambda: stage_parent(sf, out_dir),
                  lambda: stage_proposals(sf, out_dir)):
        why = stage()
        if why:
            print(f"\nSTOPPED: {why}")
            return 1

    why, skipped = stage_emit(sf, out_dir)
    if why:
        print(f"\nSTOPPED: {why}")
        return 1

    for stage in (lambda: stage_check(sf, out_dir, reference),
                  lambda: stage_copy(sf, out_dir, do_copy)):
        why = stage()
        if why:
            print(f"\nSTOPPED: {why}")
            return 1

    stage_ingame(sf)
    if skipped:
        print("\nParts not built (each says why):")
        for s in skipped:
            print(f"  {s}")
    print("\nPASSED")
    return 0


def check_all(reference: Optional[str] = None) -> int:
    """Every set that has passed, re-run and compared against its accepted output.

    A set earns a folder under tests/ when it passes; from then on this is what
    says a change to the tool has not moved a number on a set that was already
    right. Nothing under tests/ yet means nothing has been accepted yet, which is
    a pass -- there is nothing to contradict.
    """
    tests = os.path.join(ROOT, "tests")
    sets = [d for d in sorted(os.listdir(tests))
            if os.path.isdir(os.path.join(tests, d))
            and os.path.exists(os.path.join(ROOT, "sets", d, "set.py"))]
    if not sets:
        print("CHECK_ALL: no set has been accepted yet (nothing under tests), so there "
              "is nothing to re-check.")
        return 0
    bad = []
    for name in sets:
        print(f"\n=== {name}")
        if run(name, do_copy=False, reference=os.path.join(tests, name)) != 0:
            bad.append(name)
    if bad:
        print(f"\nCHECK_ALL: {len(bad)} set(s) no longer match their accepted "
              f"output: {bad}")
        return 1
    print(f"\nCHECK_ALL: {len(sets)} set(s) still match")
    return 0


def main(argv: Sequence[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if "--check-all" in argv:
        return check_all()
    if not args:
        print(__doc__)
        return 2
    reference = None
    if "--reference" in argv:
        i = list(argv).index("--reference")
        if i + 1 < len(argv):
            reference = argv[i + 1]
            args = [a for a in args if a != reference]
    return run(args[0], do_copy="--no-copy" not in argv, reference=reference)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
