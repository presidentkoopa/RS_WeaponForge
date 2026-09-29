#!/usr/bin/env python3
"""
donor.py -- read a donor weapon's MODELDEF and DECORATE, and resolve its rest
frame. Step 3 of the WeaponForge Build Guide; the inputs R1, R3 and R4 need.

R1: THE REST FRAME IS THE DONOR'S READY FRAME. In the DECORATE, find the
Ready: state and the first line inside it that calls A_WeaponReady; take that
line's sprite and frame letter. In the MODELDEF, find
`FrameIndex <sprite> <letter> 0 N` inside the block whose `Model 0` is this
gun's MD3. N is the rest frame.

It is usually NOT 0. The //Ready block at the top of a Brutal Doom MODELDEF is
the RAISE animation -- the gun swinging up into view -- and a mesh frozen
there is a gun held at the wrong angle, halfway out of frame. The SMG's raise
is frames 0, 1, 2 and its rest is 3.

NOTHING HERE DEFAULTS. If the Ready state is missing, or has no
A_WeaponReady, or the sprite and letter are not in the MODELDEF, this raises
and names the gun. A donor whose rest frame cannot be resolved is a donor the
owner has to rule on (set.py's rest_frame, with a comment saying where the
number came from) -- it is not a donor that quietly gets frame 0. CardPipeline
assumed 0 for every gun; that assumption is what put BD22's meshes in the
wrong pose.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class DonorError(ValueError):
    """A donor whose rest frame, scale or offset cannot be resolved. Always
    names the gun, the file, and what was looked for."""


# ---------------------------------------------------------------- MODELDEF

@dataclass
class ModelBlock:
    """One `Model <name> { ... }` block of a MODELDEF."""
    name: str
    source: str
    path: str = ""
    models: Dict[int, str] = field(default_factory=dict)      # index -> file
    skins: Dict[int, str] = field(default_factory=dict)
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    zoffset: Optional[float] = None
    # Which of `Offset`'s z and `ZOffset` was written last. The engine applies
    # whichever came last, so a block carrying both is only read correctly by
    # remembering the order.
    z_from: str = "none"                                       # offset | zoffset | none
    # (sprite upper, letter, model index) -> frame
    frames: Dict[Tuple[str, str, int], int] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)

    @property
    def z(self) -> float:
        """The z offset the engine actually uses."""
        if self.z_from == "zoffset":
            return float(self.zoffset)
        return float(self.offset[2])

    def frame_for(self, sprite: str, letter: str, model_index: int = 0) -> Optional[int]:
        return self.frames.get((sprite.upper(), letter.upper(), model_index))


_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)


def _strip_comments(text: str) -> str:
    text = _COMMENT_BLOCK.sub(" ", text)
    out = []
    for line in text.splitlines():
        cut = line.find("//")
        out.append(line[:cut] if cut >= 0 else line)
    return "\n".join(out)


def _floats(tokens: List[str], n: int, what: str, source: str) -> Tuple[float, ...]:
    if len(tokens) < n:
        raise DonorError(f"{source}: {what} needs {n} numbers, got {tokens}")
    try:
        return tuple(float(t) for t in tokens[:n])
    except ValueError as e:
        raise DonorError(f"{source}: {what} has a non-number in {tokens[:n]}: {e}") from e


def parse_modeldef(path: str) -> List[ModelBlock]:
    """Every Model block in one MODELDEF file, in file order."""
    if not os.path.exists(path):
        raise DonorError(f"MODELDEF not found: {path}")
    with open(path, "r", encoding="latin-1") as f:
        text = _strip_comments(f.read())

    blocks: List[ModelBlock] = []
    cur: Optional[ModelBlock] = None
    depth = 0
    source = os.path.basename(path)

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # A brace can share a line with the keyword before or after it.
        while line:
            if line.startswith("{"):
                depth += 1
                line = line[1:].strip()
                continue
            if line.startswith("}"):
                depth -= 1
                if depth <= 0 and cur is not None:
                    blocks.append(cur)
                    cur = None
                    depth = 0
                line = line[1:].strip()
                continue
            break
        if not line:
            continue

        tokens = line.replace("\t", " ").split()
        if not tokens:
            continue
        key = tokens[0].lower()

        if key == "model" and cur is None:
            # `Model <name>` opens a block; `Model 0 "file"` inside one does not.
            cur = ModelBlock(name=tokens[1] if len(tokens) > 1 else "", source=source)
            continue

        if cur is None:
            continue

        if key == "model" and len(tokens) >= 3:
            try:
                idx = int(tokens[1])
            except ValueError:
                continue
            cur.models[idx] = tokens[2].strip('"')
        elif key == "skin" and len(tokens) >= 3:
            try:
                idx = int(tokens[1])
            except ValueError:
                continue
            cur.skins[idx] = tokens[2].strip('"')
        elif key == "path" and len(tokens) >= 2:
            cur.path = " ".join(tokens[1:]).strip('"')
        elif key == "scale":
            cur.scale = _floats(tokens[1:], 3, "Scale", source)
        elif key == "offset":
            cur.offset = _floats(tokens[1:], 3, "Offset", source)
            cur.z_from = "offset"
        elif key == "zoffset":
            cur.zoffset = _floats(tokens[1:], 1, "ZOffset", source)[0]
            cur.z_from = "zoffset"
        elif key == "frameindex" and len(tokens) >= 5:
            sprite, letter = tokens[1].upper(), tokens[2].upper()
            try:
                model_index, frame = int(tokens[3]), int(tokens[4])
            except ValueError:
                raise DonorError(f"{source}: FrameIndex has non-numbers: {line!r}")
            # First writing wins: a sprite and letter listed twice in one block
            # is the donor's own duplicate, and the engine takes the first.
            cur.frames.setdefault((sprite, letter[:1], model_index), frame)
        elif len(tokens) == 1:
            cur.flags.append(tokens[0])

    if cur is not None:      # a block left unclosed by a missing brace
        blocks.append(cur)
    if not blocks:
        raise DonorError(f"{path}: no Model blocks found")
    return blocks


def blocks_for_md3(blocks: List[ModelBlock], md3_name: str) -> List[ModelBlock]:
    """Every block whose `Model 0` is this MD3, matched on the file name alone
    (a MODELDEF's Path is a directory, and an MD3 name is unique within a
    donor pack)."""
    want = os.path.basename(md3_name).lower()
    return [b for b in blocks if os.path.basename(b.models.get(0, "")).lower() == want]


def merge_blocks(blocks: List[ModelBlock], source: str) -> ModelBlock:
    """One class's blocks for one MD3, merged into a single view of it.

    A MODELDEF may define the same class several times over the same mesh, and
    the engine keeps every FrameIndex from all of them -- Brutal Doom's
    Chain_saw does this seven times, one block per animation, and the axe four.
    Reading only the first block loses most of the sprite-to-frame table, and
    the rest frame is then 'not found' for a gun whose MODELDEF plainly has it.

    Scale and the z offset must agree across them: they describe the same mesh,
    so a disagreement is a real ambiguity and is refused rather than averaged
    or taken from whichever block happened to come first.
    """
    if not blocks:
        raise DonorError(f"{source}: merge_blocks called with nothing")
    first = blocks[0]
    frames: Dict[Tuple[str, str, int], int] = {}
    for b in blocks:
        if tuple(round(c, 6) for c in b.scale) != tuple(round(c, 6) for c in first.scale):
            raise DonorError(f"{source}: blocks for '{first.name}' disagree on Scale "
                             f"({first.scale} vs {b.scale})")
        if round(b.z, 6) != round(first.z, 6):
            raise DonorError(f"{source}: blocks for '{first.name}' disagree on the z offset "
                             f"({first.z} vs {b.z})")
        for k, v in b.frames.items():
            frames.setdefault(k, v)      # first writing wins, as the engine takes it
    merged = ModelBlock(name=first.name, source=first.source, path=first.path,
                        models=dict(first.models), skins=dict(first.skins),
                        scale=first.scale, offset=first.offset, zoffset=first.zoffset,
                        z_from=first.z_from, frames=frames,
                        flags=list(first.flags))
    return merged


def block_for_md3(blocks: List[ModelBlock], md3_name: str, source: str,
                  actor: Optional[str] = None) -> ModelBlock:
    """The class's merged block for this MD3.

    `actor` picks the class when more than one claims the mesh. That is not
    unusual: every Brutal Doom weapon MODELDEF carries a block for nade.md3,
    because every weapon can throw a grenade, so nade.md3 is claimed by 49
    files. Without a class named, that is a genuine ambiguity and is refused.
    """
    hits = blocks_for_md3(blocks, md3_name)
    want = os.path.basename(md3_name).lower()
    if not hits:
        have = sorted({b.models.get(0, "?") for b in blocks})
        raise DonorError(f"{source}: no Model block whose 'Model 0' is {want!r}; it has {have}")
    if actor:
        named = [b for b in hits if b.name.lower() == actor.lower()]
        if not named:
            raise DonorError(f"{source}: no Model block for class {actor!r} with 'Model 0' "
                             f"{want!r}; the classes that claim it are "
                             f"{sorted({b.name for b in hits})}")
        hits = named
    else:
        names = sorted({b.name for b in hits})
        if len(names) > 1:
            raise DonorError(f"{source}: {len(names)} classes claim 'Model 0' {want!r} ({names}); "
                             f"the set file must name the class")
    return merge_blocks(hits, source)


def block_for_sprite(blocks: List[ModelBlock], md3_name: str, source: str,
                     sprite: str, letter: str, actor: Optional[str] = None) -> ModelBlock:
    """The block that draws this mesh for THIS sprite and frame letter.

    A class can define the same mesh more than once at different scales:
    Flamethrower2 has one block at `Scale -1 1 1, ZOffset -5` and a second at
    `Scale -0.8 0.8 0.8, Offset 25 0 20`. Both are real; they draw at different
    moments, and which one draws is decided by the sprite and frame the actor
    is showing. So the sprite has to choose the block. Merging first and looking
    the sprite up afterwards asks two blocks to agree on a scale they were never
    meant to share.

    Blocks that carry this sprite and agree on scale are merged, so a class
    spread over several blocks (Chain_saw's seven) still yields one frame table.
    """
    hits = blocks_for_md3(blocks, md3_name)
    if actor:
        hits = [b for b in hits if b.name.lower() == actor.lower()]
    key = (sprite.upper(), letter.upper()[:1], 0)
    carrying = [b for b in hits if key in b.frames]
    if not carrying:
        listed = sorted({f"{s} {l}" for b in hits for (s, l, mi) in b.frames if mi == 0})
        names = sorted({b.name for b in hits})
        raise DonorError(
            f"{source}: no block for {names} with 'Model 0' {os.path.basename(md3_name)!r} "
            f"defines FrameIndex {sprite} {letter} 0 N. Those blocks list: {listed}")
    return merge_blocks(carrying, source)


# ---------------------------------------------------------------- DECORATE

# A state line: SPRITE FRAMES TICS [action...]. The sprite is four characters,
# or a placeholder meaning "keep the one before it".
_STATE_LINE = re.compile(
    r"^(?P<sprite>[A-Za-z0-9_\-#\[\]\\]{4})\s+(?P<frames>[A-Z#\[\]\\\]]+)\s+(?P<tics>-?\d+)"
    r"(?P<rest>.*)$")
_LABEL = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_.]*)\s*:\s*$")
_PLACEHOLDER = {"----", "####", "#####"}


@dataclass
class ReadyFrame:
    sprite: str
    letter: str
    line_no: int
    line: str


_ACTOR = re.compile(r"^(?:actor|class)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)", re.I)


def actor_span(lines: List[str], actor: str) -> Tuple[int, int]:
    """The half-open line range of one ACTOR's definition.

    A donor DECORATE is not one gun per file: Mp40.txt defines both MP40 and
    HitlersBuzzsaw, BFG.txt defines a weapon and twenty-two projectiles. The
    first Ready: in such a file belongs to whichever actor was written first,
    so the search has to be confined to the class being asked about. The class
    is the MODELDEF block's own name -- that is what binds a MODELDEF to an
    actor in the engine -- so nothing new has to be declared to find it.
    """
    want = actor.lower()
    start = None
    for i, raw in enumerate(lines):
        m = _ACTOR.match(raw.strip())
        if not m:
            continue
        if start is None:
            if m.group("name").lower() == want:
                start = i
        else:
            return (start, i)
    if start is None:
        return (-1, -1)
    return (start, len(lines))


def find_ready_frame(path: str, gun: str = "", actor: Optional[str] = None) -> ReadyFrame:
    """The sprite and frame letter of the first A_WeaponReady inside the
    Ready: state. With `actor`, only that class's own lines are read.

    Labels stack: Brutal Doom's SMG writes `Ready3:` and `Ready:` on
    consecutive lines, both naming the same run of state lines, so the state
    begins after the LAST label in the run and a stacked label is not the end
    of anything. The state ends at the next label, or at a flow-control word
    (goto, stop, loop, wait, fail) that closes it.
    """
    who = gun or os.path.basename(path)
    if not os.path.exists(path):
        raise DonorError(f"{who}: DECORATE not found: {path}")
    with open(path, "r", encoding="latin-1") as f:
        text = _strip_comments(f.read())

    lines = text.splitlines()
    first_line = 1
    if actor:
        lo, hi = actor_span(lines, actor)
        if lo < 0:
            names = sorted({_ACTOR.match(l.strip()).group("name")
                            for l in lines if _ACTOR.match(l.strip())})
            raise DonorError(f"{who}: {os.path.basename(path)} defines no actor named "
                             f"{actor!r}; it defines {names}")
        lines = lines[lo:hi]
        first_line = lo + 1

    in_ready = False
    last_sprite = None
    for i, raw in enumerate(lines, start=first_line):
        line = raw.strip()
        if not line:
            continue

        label = _LABEL.match(line)
        if label:
            # A LABEL DOES NOT END A STATE. Execution falls straight through it;
            # only a flow-control word does. Brutal Doom's shotgun relies on
            # this: its Ready: state runs on into OkToFire:, and the
            # A_WeaponReady that names the rest frame is the first line under
            # THAT label. Treating a label as the end of the state loses it, and
            # the gun then looks like a donor with no Ready frame at all.
            if label.group("name").lower() == "ready":
                in_ready = True
                last_sprite = None
            continue

        if not in_ready:
            continue

        low = line.lower()
        if low.split("(")[0].strip() in ("goto", "stop", "loop", "wait", "fail"):
            in_ready = False
            continue

        m = _STATE_LINE.match(line)
        if not m:
            continue
        sprite = m.group("sprite")
        if sprite in _PLACEHOLDER:
            sprite = last_sprite
        else:
            last_sprite = sprite
        if "a_weaponready" in low:
            if not sprite:
                raise DonorError(
                    f"{who}: the A_WeaponReady on line {i} of {os.path.basename(path)} carries a "
                    f"placeholder sprite and no earlier line in the Ready state names one")
            letter = m.group("frames")[0].upper()
            return ReadyFrame(sprite=sprite.upper(), letter=letter, line_no=i, line=line)

    raise DonorError(
        f"{who}: {os.path.basename(path)} has no A_WeaponReady inside a Ready: state. "
        f"The rest frame cannot be resolved from this donor; the owner must set rest_frame "
        f"in set.py and say where the number came from.")


# ------------------------------------------------------------------- donor

@dataclass
class Donor:
    gun: str
    md3: str                 # absolute path to the donor MD3
    md3_rel: str             # as the set file wrote it
    rest_frame: int
    ready: ReadyFrame
    scale: Tuple[float, float, float]
    z_offset: float          # the donor's effective z offset, in donor units
    block: ModelBlock
    modeldef: str
    decorate: str

    @property
    def abs_scale(self) -> float:
        """|S| -- the magnitude the R4 offset converts by. Uniform in every
        donor seen so far; a donor with non-uniform scale is refused below
        rather than silently reduced to one number."""
        return abs(self.scale[0])


def read_donor(gun: str, donor_root: str, md3_rel: str, modeldef: str, decorate: str,
               rest_frame: Optional[int] = None, actor: Optional[str] = None) -> Donor:
    """Everything R1, R3 and R4 need for one gun.

    `rest_frame` overrides R1, for the donor whose Ready state cannot answer
    (the BD revolver). It is the owner's ruling, recorded in set.py.

    `actor` names the class when more than one claims the mesh, as for a
    grenade. Left out, a shared mesh is refused rather than guessed at.
    """
    md3_path = os.path.join(donor_root, md3_rel)
    if not os.path.exists(md3_path):
        raise DonorError(f"{gun}: donor MD3 not found: {md3_path}")

    modeldef_path = modeldef if os.path.isabs(modeldef) else os.path.join(donor_root, modeldef)
    decorate_path = decorate if os.path.isabs(decorate) else os.path.join(donor_root, decorate)

    blocks = parse_modeldef(modeldef_path)
    source = os.path.basename(modeldef_path)

    # R1 runs first, because the sprite it finds is what selects the MODELDEF
    # block: one class may draw the same mesh from more than one block, at
    # different scales, and the frame being shown decides which.
    if rest_frame is None:
        # The block's own name is the class the MODELDEF binds to, so it is
        # also the actor whose Ready: state governs -- see actor_span.
        klass = actor or (blocks_for_md3(blocks, md3_rel) or [ModelBlock("", source)])[0].name
        ready = find_ready_frame(decorate_path, gun=gun, actor=klass or None)
        block = block_for_sprite(blocks, md3_rel, source, ready.sprite, ready.letter, actor=actor)
        frame = block.frame_for(ready.sprite, ready.letter, 0)
    else:
        block = block_for_md3(blocks, md3_rel, source, actor=actor)
        ready = ReadyFrame(sprite="(owner)", letter="-", line_no=0,
                           line=f"rest_frame={rest_frame} set in set.py")
        frame = int(rest_frame)

    sx, sy, sz = block.scale
    if abs(abs(sx) - abs(sy)) > 1e-6 or abs(abs(sx) - abs(sz)) > 1e-6:
        raise DonorError(f"{gun}: MODELDEF Scale {block.scale} is not uniform in magnitude. "
                         f"R4's offset conversion uses one |S|; this donor needs a ruling.")

    if frame is None:
        raise DonorError(f"{gun}: block '{block.name}' of {block.source} was selected for "
                         f"{ready.sprite} {ready.letter} but has no frame for it")

    return Donor(gun=gun, md3=md3_path, md3_rel=md3_rel, rest_frame=frame, ready=ready,
                 scale=block.scale, z_offset=block.z, block=block,
                 modeldef=modeldef_path, decorate=decorate_path)
