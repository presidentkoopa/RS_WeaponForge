#!/usr/bin/env python3
"""
setfile.py -- load a set's set.py and refuse it if it does not account for the
donor. Step 5 of the WeaponForge Build Guide.

set.py is the only human-written file in a set. Everything a person decides
about the set lives there: class names, capacities, sounds, and which donor
surface is which part. Nothing measured is ever typed there -- no scale,
offset, axis, pivot or distance.

WHAT THIS REFUSES, AND WHY EACH ONE MATTERS

  * A donor surface that is not accounted for. Every surface must be the body,
    inside a part, in `hidden`, or listed in `fixed`. An unaccounted surface is
    the failure that does not announce itself: the gun builds, loads, and is
    missing its charging handle, or carries a stray mesh floating beside it,
    and nothing in the log says why.
  * A #N index outside the mesh. A part map written against one version of a
    mesh, or renumbered by a re-export, silently points at another part.
  * A part with no surfaces. It reaches the card as a part with no geometry,
    which the reload code then tries to move.
  * The same surface claimed twice. Two parts cannot both own one mesh.

A gun with no `body` and no `parts` is NOT an error: it is a gun the owner has
not mapped yet. RUN_SET writes its proposal and stops, naming it.

Addressing is by index -- "#3" -- because donor surface names repeat. The SMG's
body and its charging handle are both called Sights.
"""

from __future__ import annotations

import importlib.util
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


class SetError(ValueError):
    """A set.py that cannot be trusted. Always names the set, the gun, and the
    surface or key at fault."""


_HASH = re.compile(r"^#(\d+)$")

# Keys a gun may carry. Anything else is a typo, and a typo in a key is silent
# otherwise -- "capacty" would simply mean the capacity never arrives.
GUN_KEYS = {
    "class", "donor", "modeldef", "decorate", "actor", "hand", "type",
    "capacity", "magfamily", "sounds", "body", "parts", "hidden", "fixed",
    "rest_frame", "notes", "firesfrom", "stores", "load", "mechanism",
}
PART_KEYS = {"surfaces", "role", "subject", "carve", "notes", "island", "take",
             "chambers", "spin", "spinrate", "spinup", "spindown"}
SET_KEYS = {
    "SET_ID", "PREFIX", "DONOR_ROOT", "PARENT_MOD", "PACK", "MODEL_PATH",
    "CVAR_PREFIX", "PARENT_RULINGS", "GUNS", "NOTES",
}


def _surface_index(value: Any, where: str) -> int:
    """"#3" -> 3. A bare integer is accepted; a name is refused, because donor
    names repeat and a name would silently pick the wrong one of two."""
    if isinstance(value, bool):
        raise SetError(f"{where}: {value!r} is not a surface index")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        m = _HASH.match(value.strip())
        if m:
            return int(m.group(1))
        raise SetError(f"{where}: {value!r} is not a surface index. Surfaces are addressed by "
                       f"position, as \"#3\", because donor surface names repeat -- the SMG's "
                       f"body and its charging handle are both called Sights.")
    raise SetError(f"{where}: {value!r} is not a surface index")


@dataclass
class Part:
    id: str
    surfaces: List[int]
    role: str = ""
    subject: str = ""
    carve: bool = False
    # Whether a hand may pull this part off the gun. A DECISION, not a
    # measurement: the RPG's drum comes out by its button and goes back in by the
    # hand carrying one, so its shipped card says take = no.
    take: str = ""
    # A revolving feed's chamber count. A DECISION about the gun, and what its
    # index step is divided from: seven rockets, a seventh of a turn.
    chambers: Optional[int] = None
    notes: str = ""
    # WHAT SPINS THIS PART, when it is a rotor rather than a part a hand works
    # (card.zs WM_Part.spinBy): `trigger` while the trigger is held, `fire` a turn
    # a shot. A DECISION about the gun -- a minigun's barrels spin off the trigger,
    # a revolver's cylinder indexes off the shot -- and the card's spin sounds have
    # no home without it, which is how the BD minigun shipped silent.
    spin: str = ""
    # HOW FAST, AND HOW LONG IT TAKES TO GET THERE: degrees a tic at full speed, and
    # the tics winding up and running down. DECISIONS, not measurements -- the mesh
    # says how far a period is, never how fast a motor drives it. The parser refuses a
    # spinning part with no rate, and refuses a rate at or past half a period a tic
    # (it would look still or run backwards at 35 tics a second).
    spinrate: Optional[float] = None
    spinup: Optional[int] = None
    spindown: Optional[int] = None
    # An island inside one donor surface, when a part shares a surface with the
    # body: {"of": "#5", "verts": 415}. The vertex count is checked against the
    # island actually found, so a mapping written against a different export of
    # the mesh is refused rather than lifting whatever happens to be there.
    island: Optional[dict] = None


@dataclass
class Store:
    """Where rounds live on the gun. A DECISION: how many a tube holds, how many
    chambers a breech has. Nothing in a mesh says it."""
    id: str
    kind: str = "counted"          # counted (a tube) | slotted (chambers)
    capacity: Optional[int] = None
    slots: Optional[int] = None
    detach: str = ""


@dataclass
class Load:
    """Which face of the gun rounds go in by. The FACE is the decision; the point
    and the direction on it are measured from the body."""
    id: str = "gate"
    where: str = "under"           # under | left | right | breech
    size: Optional[tuple] = None
    # WHICH STORE A ROUND GOES INTO. NOT optional: the reload system refuses a load
    # verb that names no store and skips the whole card, so a gun that omits this does
    # not load at all. It is a DECISION -- a shotgun shell goes into the tube, a
    # revolver round into the cylinder -- and it must name one of the gun's own stores.
    into: str = ""


@dataclass
class Gun:
    id: str
    cls: str
    donor: str
    modeldef: str
    decorate: str
    hand: str = "main"
    type: str = ""
    capacity: Optional[int] = None
    magfamily: str = ""
    # none | reserve | chamber. A gun that takes no magazine says so, and that is
    # not the same as one whose magazine nobody has carved yet: an axe fires from
    # nothing, and set_gate treats the two differently for good reason.
    firesfrom: str = ""
    # Which reload archetype drives it: pump, breakaction, breaktop_revolver,
    # swingout_revolver. A DECISION about the gun -- nothing in a mesh says how a
    # breech opens -- and it is what gives the gun its loading verbs.
    mechanism: str = ""
    sounds: Dict[str, str] = field(default_factory=dict)
    actor: Optional[str] = None
    body: Optional[int] = None
    parts: Dict[str, Part] = field(default_factory=dict)
    hidden: List[int] = field(default_factory=list)
    fixed: List[int] = field(default_factory=list)
    rest_frame: Optional[int] = None
    notes: str = ""
    # Whether set.py said anything about parts at all. "parts": {} is a decision --
    # an axe has nothing driven by hand -- and a gun with no parts KEY is a gun
    # nobody has mapped yet. Without the difference, every melee weapon in a set
    # would block the build for ever waiting on a part map it does not need.
    parts_declared: bool = False
    stores: List[Store] = field(default_factory=list)
    load: Optional[Load] = None

    @property
    def mapped(self) -> bool:
        """A gun is built once it has a body and its parts have been decided."""
        return self.body is not None and (bool(self.parts) or self.parts_declared)

    @property
    def claimed(self) -> List[int]:
        out = [] if self.body is None else [self.body]
        for p in self.parts.values():
            out.extend(p.surfaces)
        out.extend(self.hidden)
        out.extend(self.fixed)
        return out

    def owner_of(self, index: int) -> str:
        if self.body == index:
            return "body"
        for name, p in self.parts.items():
            if index in p.surfaces:
                return f"part '{name}'"
        if index in self.hidden:
            return "hidden"
        if index in self.fixed:
            return "fixed"
        return ""


@dataclass
class SetFile:
    set_id: str
    prefix: str
    donor_root: str
    parent_mod: str
    pack: str
    model_path: str
    cvar_prefix: str
    parent_rulings: Dict[str, str]
    guns: Dict[str, Gun]
    path: str

    @property
    def unmapped(self) -> List[str]:
        return [g for g, gun in self.guns.items() if not gun.mapped]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise SetError(msg)


def load_set(path: str) -> SetFile:
    """Read a set.py and check everything checkable without the meshes."""
    path = os.path.abspath(path)
    _require(os.path.exists(path), f"set file not found: {path}")

    spec = importlib.util.spec_from_file_location(f"weaponforge_set_{abs(hash(path))}", path)
    if spec is None or spec.loader is None:
        raise SetError(f"{path}: cannot be loaded as Python")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:      # a set file is the owner's own code; say where it broke
        raise SetError(f"{path}: failed to run: {type(e).__name__}: {e}") from e

    declared = {k for k in vars(mod) if k.isupper() and not k.startswith("_")}
    unknown = sorted(declared - SET_KEYS)
    _require(not unknown, f"{path}: unknown top-level names {unknown}; expected only "
                          f"{sorted(SET_KEYS)}")

    def need(name: str) -> Any:
        _require(hasattr(mod, name), f"{path}: {name} is missing")
        return getattr(mod, name)

    guns_raw = need("GUNS")
    _require(isinstance(guns_raw, dict), f"{path}: GUNS must be a dict of gun id -> settings")

    guns: Dict[str, Gun] = {}
    for gid, raw in guns_raw.items():
        where = f"{path}: gun '{gid}'"
        _require(isinstance(raw, dict), f"{where}: must be a dict")
        unknown = sorted(set(raw) - GUN_KEYS)
        _require(not unknown, f"{where}: unknown keys {unknown}; expected only {sorted(GUN_KEYS)}")
        for k in ("class", "donor", "modeldef", "decorate"):
            _require(k in raw and isinstance(raw[k], str) and raw[k].strip(),
                     f"{where}: {k!r} is required")

        parts: Dict[str, Part] = {}
        for pname, praw in (raw.get("parts") or {}).items():
            pwhere = f"{where}, part '{pname}'"
            _require(isinstance(praw, dict), f"{pwhere}: must be a dict")
            punknown = sorted(set(praw) - PART_KEYS)
            _require(not punknown, f"{pwhere}: unknown keys {punknown}; expected only "
                                   f"{sorted(PART_KEYS)}")
            surfaces = praw.get("surfaces")
            _require(isinstance(surfaces, (list, tuple)) and len(surfaces) > 0,
                     f"{pwhere}: has no surfaces. A part with no geometry reaches the card as "
                     f"a part the reload code then tries to move.")
            island = praw.get("island")
            if island is not None:
                _require(isinstance(island, dict) and "of" in island and "verts" in island
                         and ("box" in island or "cut" in island),
                         f'{pwhere}: island must be {{"of": "#N", "box": [[lo],[hi]], '
                         f'"verts": <count>}} -- the surface it lives in, the box in _wm space '
                         f'that holds it, and how many vertices it has. Every island wholly '
                         f'inside the box is taken, and the count is checked against what is '
                         f'found so a box written for another mesh is refused.')
                spec = {"of": _surface_index(island["of"], f"{pwhere}, island of"),
                        "verts": int(island["verts"])}
                if "box" in island:
                    box = island["box"]
                    _require(isinstance(box, (list, tuple)) and len(box) == 2
                             and all(isinstance(c, (list, tuple)) and len(c) == 3 for c in box),
                             f"{pwhere}: island box must be [[x,y,z],[x,y,z]]")
                    spec["box"] = [[float(c) for c in box[0]], [float(c) for c in box[1]]]
                if "cut" in island:
                    spec["cut"] = str(island["cut"])
                island = spec
                _require(island["of"] in [_surface_index(s, pwhere) for s in surfaces],
                         f"{pwhere}: island of #{island['of']} but that surface is not in this "
                         f"part's own surfaces")

            parts[pname] = Part(
                id=pname,
                surfaces=[_surface_index(s, f"{pwhere}") for s in surfaces],
                role=praw.get("role", ""), subject=praw.get("subject", ""),
                carve=bool(praw.get("carve", False)), notes=praw.get("notes", ""),
                take=str(praw.get("take", "")),
                chambers=praw.get("chambers"),
                spin=str(praw.get("spin", "")),
                spinrate=praw.get("spinrate"), spinup=praw.get("spinup"),
                spindown=praw.get("spindown"),
                island=island)

        body = raw.get("body")
        gun = Gun(
            id=gid, cls=raw["class"], donor=raw["donor"], modeldef=raw["modeldef"],
            decorate=raw["decorate"], hand=raw.get("hand", "main"), type=raw.get("type", ""),
            capacity=raw.get("capacity"), magfamily=raw.get("magfamily", ""),
            firesfrom=raw.get("firesfrom", ""),
            mechanism=raw.get("mechanism", ""),
            sounds=dict(raw.get("sounds") or {}), actor=raw.get("actor"),
            body=None if body is None else _surface_index(body, f"{where}, body"),
            parts=parts,
            hidden=[_surface_index(s, f"{where}, hidden") for s in (raw.get("hidden") or [])],
            fixed=[_surface_index(s, f"{where}, fixed") for s in (raw.get("fixed") or [])],
            rest_frame=raw.get("rest_frame"), notes=raw.get("notes", ""),
            parts_declared=("parts" in raw),
            stores=[Store(id=k,
                          kind=str(v.get("kind", "counted")),
                          capacity=v.get("capacity"), slots=v.get("slots"),
                          detach=str(v.get("detach", "")))
                    for k, v in (raw.get("stores") or {}).items()],
            load=(Load(id=str((raw.get("load") or {}).get("id", "gate")),
                       where=str((raw.get("load") or {}).get("where", "under")),
                       into=str((raw.get("load") or {}).get("into", "")),
                       size=tuple((raw.get("load") or {}).get("size", ()))
                       or None)
                  if raw.get("load") else None))

        # Who claims what, listed per claimant rather than looked up per index:
        # owner_of answers with the FIRST owner it finds, so asking it about a
        # surface two parts both list gets the same answer twice and the clash
        # goes unseen.
        claims: Dict[int, List[str]] = {}
        for idx in ([] if gun.body is None else [gun.body]):
            claims.setdefault(idx, []).append("body")
        for pname, p in gun.parts.items():
            for idx in p.surfaces:
                claims.setdefault(idx, []).append(f"part '{pname}'")
        for idx in gun.hidden:
            claims.setdefault(idx, []).append("hidden")
        for idx in gun.fixed:
            claims.setdefault(idx, []).append("fixed")
        # An ISLAND part shares its surface on purpose: the machinegun's magazine
        # lives inside the same surface as its body, and lifting it out is the
        # whole point. So a surface may be claimed twice when one of the
        # claimants is an island of it -- and only then.
        islanders = {p.island["of"] for p in gun.parts.values() if p.island}
        for idx in sorted(claims):
            owners = claims[idx]
            if len(owners) > 1 and idx not in islanders:
                raise SetError(f"{where}: surface #{idx} is claimed by {' and '.join(owners)}. "
                               f"One mesh cannot belong to two parts.")

        guns[gid] = gun

    return SetFile(
        set_id=str(need("SET_ID")), prefix=str(need("PREFIX")),
        donor_root=str(need("DONOR_ROOT")), parent_mod=str(getattr(mod, "PARENT_MOD", "")),
        pack=str(need("PACK")), model_path=str(need("MODEL_PATH")),
        cvar_prefix=str(need("CVAR_PREFIX")),
        parent_rulings=dict(getattr(mod, "PARENT_RULINGS", {}) or {}),
        guns=guns, path=path)


def check_against_mesh(gun: Gun, surfaces: Sequence, set_id: str = "") -> None:
    """Refuse the gun unless its map accounts for every surface of its donor.

    `surfaces` is the donor MD3's surface list, so the message can name the
    surface rather than only its number -- "#4 'pump'" is something the owner
    can find in the proposal; "#4" is a number to go and count out by hand.
    """
    where = f"{set_id + ': ' if set_id else ''}gun '{gun.id}'"
    n = len(surfaces)

    for idx in sorted(set(gun.claimed)):
        if not (0 <= idx < n):
            raise SetError(f"{where}: {gun.owner_of(idx)} names surface #{idx}, but the donor "
                           f"mesh has {n} surfaces (#0 to #{n - 1})")

    missing = [i for i in range(n) if not gun.owner_of(i)]
    if missing:
        named = ", ".join(f"#{i} '{surfaces[i].name}'" for i in missing)
        raise SetError(
            f"{where}: {len(missing)} donor surface(s) unaccounted for: {named}. "
            f"Every surface must be the body, in a part, in hidden, or in fixed. "
            f"An unaccounted surface builds quietly and then the gun is missing a piece, "
            f"or carries a stray mesh, with nothing in the log to say why.")
