#!/usr/bin/env python3
"""
md3.py -- read and write MD3, and lift surfaces out into their own file.

Ported for step 2 of the WeaponForge Build Guide from CardPipeline
tools/md3.py (reader) and tools/md3_write.py (writer, extract), which are
the archive and are never edited. Proven by tests/test_md3.py: read, write,
read again, zero differences.

WHAT CAME ACROSS AND WHAT DID NOT

The format core came across whole, including two corrections earlier
sessions paid for and which are easy to lose:

  * The packed vertex normal decodes as the ENGINE decodes it (GZDoom
    models_md3.cpp UnpackVector): HIGH byte azimuth, LOW byte polar, steps
    of pi/128. An earlier decoder read the high byte as polar in 2*pi/255
    steps, so every mesh written back came out with wrong lighting.
  * Every offset, count and frame bound a write produces is RECOMPUTED from
    what is being written, never copied from the model that was read. A
    subset has different counts, so the source header is wrong for it by
    construction, and a stale radius makes the renderer cull a model that
    is plainly on screen.

Left behind deliberately:

  * The rigid-fit (Kabsch) block at the end of CardPipeline's md3.py. Step 4
    measures motion in forge/motion.py, with numpy, where the guide puts it.
  * moves(), max_centroid_drift(), is_degenerate(), best_extended_frame(),
    stable_plateaus(). Those pick which frame and which part matter from
    thresholds. Rest frames come from the donor's Ready: state (R1) and
    parts come from set.py; nothing here guesses either.

ADDED HERE: normals are kept BOTH ways -- decoded to unit vectors for
callers, and as the raw packed shorts they arrived as. A write reuses the
raw short whenever the mesh was not reposed, so a mesh that is only frozen
and translated (R2, the emit_mesh path) keeps its author's normals exactly
instead of being re-encoded onto the pi/128 grid and drifting a step.

FORMAT REFERENCE (id Software MD3, as GZDoom and every source port read it)

    Header        108 bytes   ident, version, name, flags, counts, offsets
    Frame          56 bytes   mins, maxs, origin, radius, name        x num_frames
    Tag           112 bytes   name, origin, 3x3 axis                  x num_tags x num_frames
    Surface       108 bytes   its own sub-header, offsets relative to itself
      Shader       68 bytes   name, shader index                      x num_shaders
      Triangle     12 bytes   three vertex indices                    x num_triangles
      ST            8 bytes   texture coordinates                     x num_verts
      XYZNormal     8 bytes   packed position (x1/64) + packed normal  x num_verts x num_frames

    python -m forge.md3 path/to/model.md3     structural self-check
"""

from __future__ import annotations

import math
import struct
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

MD3_IDENT = b"IDP3"
MD3_VERSION = 15

HEADER_FMT = "<4si64s9i"
HEADER_SIZE = struct.calcsize(HEADER_FMT)           # 108
FRAME_FMT = "<10f16s"
FRAME_SIZE = struct.calcsize(FRAME_FMT)             # 56
TAG_FMT = "<64s12f"
TAG_SIZE = struct.calcsize(TAG_FMT)                 # 112
SURFACE_FMT = "<4s64s10i"
SURFACE_SIZE = struct.calcsize(SURFACE_FMT)         # 108
SHADER_FMT = "<64si"
SHADER_SIZE = struct.calcsize(SHADER_FMT)           # 68
TRIANGLE_FMT = "<3i"
TRIANGLE_SIZE = struct.calcsize(TRIANGLE_FMT)       # 12
ST_FMT = "<2f"
ST_SIZE = struct.calcsize(ST_FMT)                   # 8
VERTEX_FMT = "<3hH"
VERTEX_SIZE = struct.calcsize(VERTEX_FMT)           # 8

# One packed unit is 1/64 of a map unit. Every position in this module is in
# map units; the quantiser below is the only place the packing is known.
XYZ_STEP = 1.0 / 64.0

NUL = bytes(1)

# A generous ceiling on any count field: far above anything a real MD3 ships,
# far below what silently exhausts memory on a corrupt count. A file claiming
# more than this is corrupt, and the error says so instead of the process
# paging to death trying to honour it.
SANE_COUNT_CEILING = 200_000


class MD3Error(ValueError):
    """Anything wrong with an MD3 that stops it being read or written safely.

    The message always carries enough to go straight to the byte offset and
    the field that failed, rather than a bare struct.error three frames from
    the actual fault.
    """


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise MD3Error(msg)


def _decode_name(raw: bytes) -> str:
    # latin-1, not ascii: it maps every one of the 256 byte values to exactly
    # one character and back, so a name survives a read and a write unchanged.
    # Donor meshes really do carry high bytes -- the BD Rifle's sight surface
    # is named 'tahtain' with two a-umlauts -- and an ascii decode replaces
    # each of them, so the name written back was 't??ht??in'. Names are how
    # shaders and carved parts are addressed; a mangled one is data loss.
    return raw.split(NUL, 1)[0].decode("latin-1")


def _cstr(s: str, n: int) -> bytes:
    """Fixed width, NUL padded, and TRUNCATED rather than overflowing: id's
    name fields are fixed size, and 70 bytes in a 64-byte field silently
    shifts every structure after it."""
    b = s.encode("latin-1", "replace")[: n - 1]
    return b + NUL * (n - len(b))


def _quant(x: float) -> int:
    q = int(round(x / XYZ_STEP))
    return max(-32768, min(32767, q))


def decode_normal(packed) -> Tuple[float, float, float]:
    """The packed lat/long normal to a unit vector, EXACTLY as the engine
    decodes it: high byte azimuth, low byte polar, steps of pi/128. Accepts
    an already-decoded vector too, so callers need not know which they hold."""
    if isinstance(packed, (tuple, list)):
        return tuple(float(c) for c in packed)
    azimuth = ((int(packed) >> 8) & 0xFF) * (math.pi / 128.0)
    polar = (int(packed) & 0xFF) * (math.pi / 128.0)
    return (math.cos(azimuth) * math.sin(polar),
            math.sin(azimuth) * math.sin(polar),
            math.cos(polar))


def encode_normal(v) -> int:
    """The inverse, on the same pi/128 grid. An int passes straight through,
    so a normal that was never touched is written back bit for bit."""
    if isinstance(v, int):
        return v & 0xFFFF
    x, y, z = v
    ln = math.sqrt(x * x + y * y + z * z) or 1.0
    x, y, z = x / ln, y / ln, z / ln
    # The poles have no azimuth; id's own encoder special-cases them.
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return 0 if z > 0 else 128
    azimuth = int(round(math.atan2(y, x) * 128.0 / math.pi)) & 0xFF
    polar = int(round(math.acos(max(-1.0, min(1.0, z))) * 128.0 / math.pi)) & 0xFF
    return (azimuth << 8) | polar


@dataclass
class MD3Frame:
    mins: Tuple[float, float, float]
    maxs: Tuple[float, float, float]
    origin: Tuple[float, float, float]
    radius: float
    name: str


@dataclass
class MD3Tag:
    name: str
    origin: Tuple[float, float, float]
    axis: Tuple[float, ...]   # 9 floats, row-major 3x3


@dataclass
class MD3Shader:
    name: str
    shader_index: int


@dataclass
class MD3Surface:
    index: int
    name: str
    num_frames: int
    shaders: List[MD3Shader] = field(default_factory=list)
    triangles: List[Tuple[int, int, int]] = field(default_factory=list)
    st: List[Tuple[float, float]] = field(default_factory=list)
    # verts[frame][vert] -> (x, y, z) in map units, already scaled.
    verts: List[List[Tuple[float, float, float]]] = field(default_factory=list)
    # normals[frame][vert] -> unit (x, y, z), already decoded.
    normals: List[List[Tuple[float, float, float]]] = field(default_factory=list)
    # The same normals as the raw packed shorts they arrived as, so a write
    # that did not repose the mesh can put them back untouched. Cleared by
    # anything that rotates vertices.
    normals_packed: List[List[int]] = field(default_factory=list)

    @property
    def num_verts(self) -> int:
        return len(self.st)

    @property
    def num_triangles(self) -> int:
        return len(self.triangles)

    def centroid(self, frame: int) -> Tuple[float, float, float]:
        """The mean vertex position on one frame."""
        vs = self.verts[frame]
        n = len(vs)
        _require(n > 0, f"surface {self.index} ('{self.name}') has no vertices")
        return (sum(v[0] for v in vs) / n,
                sum(v[1] for v in vs) / n,
                sum(v[2] for v in vs) / n)

    def bounds(self, frame: int):
        """(min, max) corner of this surface's box on one frame."""
        vs = self.verts[frame]
        _require(len(vs) > 0, f"surface {self.index} ('{self.name}') has no vertices")
        lo = tuple(min(v[a] for v in vs) for a in range(3))
        hi = tuple(max(v[a] for v in vs) for a in range(3))
        return lo, hi


@dataclass
class MD3Model:
    source: str
    name: str
    num_frames: int
    frames: List[MD3Frame] = field(default_factory=list)
    tags: List[List[MD3Tag]] = field(default_factory=list)   # tags[frame][tag]
    surfaces: List[MD3Surface] = field(default_factory=list)

    # ------------------------------------------------------------- reading

    @classmethod
    def load(cls, path: str) -> "MD3Model":
        with open(path, "rb") as f:
            data = f.read()
        return cls.from_bytes(data, source=str(path))

    @classmethod
    def from_bytes(cls, data: bytes, source: str = "<bytes>") -> "MD3Model":
        size = len(data)
        _require(size >= HEADER_SIZE,
                 f"{source}: file is {size} bytes, too small for even an MD3 header ({HEADER_SIZE})")

        (ident, version, name_raw, flags, num_frames, num_tags, num_surfaces,
         num_skins, ofs_frames, ofs_tags, ofs_surfaces, ofs_eof) = \
            struct.unpack_from(HEADER_FMT, data, 0)

        _require(ident == MD3_IDENT,
                 f"{source}: not an MD3 -- ident is {ident!r}, expected {MD3_IDENT!r}")
        # A nonstandard version is not fatal: some tools write one and GZDoom
        # reads them anyway.

        for label, n in (("num_frames", num_frames), ("num_tags", num_tags),
                         ("num_surfaces", num_surfaces), ("num_skins", num_skins)):
            _require(0 <= n <= SANE_COUNT_CEILING,
                     f"{source}: header {label}={n} is out of a sane range "
                     f"(0..{SANE_COUNT_CEILING}) -- the file is likely corrupt")

        for label, o in (("ofs_frames", ofs_frames), ("ofs_tags", ofs_tags),
                         ("ofs_surfaces", ofs_surfaces), ("ofs_eof", ofs_eof)):
            _require(0 <= o <= size,
                     f"{source}: header {label}={o} falls outside the file (size {size})")

        model = cls(source=source, name=_decode_name(name_raw), num_frames=num_frames)

        # ---- FRAMES -------------------------------------------------------
        need = ofs_frames + num_frames * FRAME_SIZE
        _require(need <= size,
                 f"{source}: {num_frames} frames from ofs_frames={ofs_frames} need {need} bytes, "
                 f"file has {size}")
        for i in range(num_frames):
            vals = struct.unpack_from(FRAME_FMT, data, ofs_frames + i * FRAME_SIZE)
            model.frames.append(MD3Frame(mins=vals[0:3], maxs=vals[3:6], origin=vals[6:9],
                                         radius=vals[9], name=_decode_name(vals[10])))

        # ---- TAGS ---------------------------------------------------------
        # num_tags per frame, laid out frame-major: frame 0's tags, then frame 1's.
        need = ofs_tags + num_frames * num_tags * TAG_SIZE
        _require(need <= size,
                 f"{source}: {num_frames}x{num_tags} tags from ofs_tags={ofs_tags} need {need} "
                 f"bytes, file has {size}")
        for fr in range(num_frames):
            frame_tags: List[MD3Tag] = []
            for t in range(num_tags):
                vals = struct.unpack_from(TAG_FMT, data, ofs_tags + (fr * num_tags + t) * TAG_SIZE)
                frame_tags.append(MD3Tag(name=_decode_name(vals[0]), origin=vals[1:4],
                                         axis=vals[4:13]))
            model.tags.append(frame_tags)

        # ---- SURFACES -----------------------------------------------------
        # Each surface is self-contained; the NEXT one starts at this one's own
        # ofs_end, relative to where THIS one began -- not a fixed stride.
        # Trusting a bad ofs_end walks the rest of the file off into the weeds,
        # so it is bounds-checked before it is used to step forward.
        surf_off = ofs_surfaces
        for s in range(num_surfaces):
            _require(surf_off + SURFACE_SIZE <= size,
                     f"{source}: surface {s} header at {surf_off} runs past the file (size {size})")

            (sident, sname_raw, sflags, s_num_frames, s_num_shaders, s_num_verts,
             s_num_tris, ofs_tri, ofs_shaders, ofs_st, ofs_xyzn, ofs_send) = \
                struct.unpack_from(SURFACE_FMT, data, surf_off)

            sname = _decode_name(sname_raw)
            _require(sident == MD3_IDENT,
                     f"{source}: surface {s} ('{sname}') has bad ident {sident!r} at offset "
                     f"{surf_off} -- the previous surface's ofs_end likely walked to the wrong place")

            for label, n in (("num_frames", s_num_frames), ("num_shaders", s_num_shaders),
                             ("num_verts", s_num_verts), ("num_triangles", s_num_tris)):
                _require(0 <= n <= SANE_COUNT_CEILING,
                         f"{source}: surface {s} ('{sname}') {label}={n} is out of a sane range")

            if s_num_frames != num_frames:
                # Legal per spec, but every MD3 in this project keeps them in
                # lockstep, and a mismatch is the signature of an export gone
                # wrong far more often than an intentional choice.
                sys.stderr.write(
                    f"warning: {source}: surface {s} ('{sname}') has {s_num_frames} frames, "
                    f"the model header says {num_frames}\n")

            _require(0 <= ofs_send and surf_off + ofs_send <= size,
                     f"{source}: surface {s} ('{sname}') ofs_end={ofs_send} puts the next surface "
                     f"at {surf_off + ofs_send}, past the file (size {size})")

            def _sub_ok(label: str, ofs: int, count: int, item_size: int) -> int:
                start = surf_off + ofs
                end = start + count * item_size
                _require(0 <= ofs and end <= surf_off + ofs_send,
                         f"{source}: surface {s} ('{sname}') {label} at +{ofs} for {count} items "
                         f"({item_size}B each) runs past this surface's own ofs_end ({ofs_send})")
                return start

            shaders_start = _sub_ok("ofs_shaders", ofs_shaders, s_num_shaders, SHADER_SIZE)
            tris_start = _sub_ok("ofs_triangles", ofs_tri, s_num_tris, TRIANGLE_SIZE)
            st_start = _sub_ok("ofs_st", ofs_st, s_num_verts, ST_SIZE)
            xyzn_start = _sub_ok("ofs_xyznormal", ofs_xyzn, s_num_frames * s_num_verts, VERTEX_SIZE)

            surf = MD3Surface(index=s, name=sname, num_frames=s_num_frames)

            for i in range(s_num_shaders):
                vals = struct.unpack_from(SHADER_FMT, data, shaders_start + i * SHADER_SIZE)
                surf.shaders.append(MD3Shader(_decode_name(vals[0]), vals[1]))

            for i in range(s_num_tris):
                surf.triangles.append(
                    struct.unpack_from(TRIANGLE_FMT, data, tris_start + i * TRIANGLE_SIZE))

            for i in range(s_num_verts):
                surf.st.append(struct.unpack_from(ST_FMT, data, st_start + i * ST_SIZE))

            for fr in range(s_num_frames):
                frame_verts: List[Tuple[float, float, float]] = []
                frame_norms: List[Tuple[float, float, float]] = []
                frame_packed: List[int] = []
                base = xyzn_start + fr * s_num_verts * VERTEX_SIZE
                for v in range(s_num_verts):
                    x, y, z, n = struct.unpack_from(VERTEX_FMT, data, base + v * VERTEX_SIZE)
                    frame_verts.append((x * XYZ_STEP, y * XYZ_STEP, z * XYZ_STEP))
                    frame_norms.append(decode_normal(n))
                    frame_packed.append(n)
                surf.verts.append(frame_verts)
                surf.normals.append(frame_norms)
                surf.normals_packed.append(frame_packed)

            # A truncated or hand-edited surface can pass every offset check
            # above and still point a triangle at vertex 9000 of 80.
            for (a, b, c) in surf.triangles:
                _require(0 <= a < s_num_verts and 0 <= b < s_num_verts and 0 <= c < s_num_verts,
                         f"{source}: surface {s} ('{sname}') has a triangle indexing outside its "
                         f"{s_num_verts} vertices: ({a}, {b}, {c})")

            model.surfaces.append(surf)
            surf_off += ofs_send

        return model

    def save(self, path: str) -> None:
        write(self, path)


# ------------------------------------------------------------------ writing

def _packed_normal(surf: MD3Surface, frame: int, i: int) -> int:
    """The raw short if this surface still carries it for this frame and
    vertex, otherwise the decoded normal re-encoded."""
    if frame < len(surf.normals_packed):
        row = surf.normals_packed[frame]
        if i < len(row):
            return int(row[i]) & 0xFFFF
    return encode_normal(surf.normals[frame][i])


def _surface_bytes(surf: MD3Surface, num_frames: int) -> bytes:
    ns, nt, nv = len(surf.shaders), len(surf.triangles), len(surf.verts[0])

    off_shaders = SURFACE_SIZE
    off_tris = off_shaders + ns * SHADER_SIZE
    off_st = off_tris + nt * TRIANGLE_SIZE
    off_verts = off_st + nv * ST_SIZE
    end = off_verts + nv * num_frames * VERTEX_SIZE

    out = bytearray()
    out += struct.pack(SURFACE_FMT, MD3_IDENT, _cstr(surf.name, 64), 0,
                       num_frames, ns, nv, nt,
                       off_tris, off_shaders, off_st, off_verts, end)
    for sh in surf.shaders:
        out += struct.pack(SHADER_FMT, _cstr(sh.name, 64), int(sh.shader_index))
    for t in surf.triangles:
        out += struct.pack(TRIANGLE_FMT, *[int(i) for i in t])
    for uv in surf.st:
        out += struct.pack(ST_FMT, *[float(c) for c in uv])

    # Frame-major: every vertex of frame 0, then every vertex of frame 1.
    for f in range(num_frames):
        _require(len(surf.verts[f]) == nv,
                 f"surface '{surf.name}': frame {f} has {len(surf.verts[f])} vertices, "
                 f"frame 0 has {nv} -- an MD3 surface must keep its vertex count")
        for i in range(nv):
            x, y, z = surf.verts[f][i]
            out += struct.pack(VERTEX_FMT, _quant(x), _quant(y), _quant(z),
                               _packed_normal(surf, f, i))
    if len(out) != end:
        raise MD3Error(f"surface '{surf.name}': wrote {len(out)} bytes, its header says {end}")
    return bytes(out)


def write(model: MD3Model, path: str) -> None:
    """Serialise a model. Every offset, count and frame bound is recomputed
    from what is being written."""
    nf = model.num_frames
    _require(nf > 0, f"{path}: a model needs at least one frame")
    _require(len(model.surfaces) > 0, f"{path}: a model needs at least one surface")

    # Tags are per frame -- a list of frames, each a list of tags -- which is
    # also how the file lays them out. A flat list is accepted too, so a
    # hand-built model with one set of tags need not know that.
    tags = model.tags or []
    if tags and isinstance(tags[0], (list, tuple)):
        per_frame = [list(fr) for fr in tags]
    else:
        per_frame = [list(tags) for _ in range(nf)]
    ntag = len(per_frame[0]) if per_frame else 0

    blobs = [_surface_bytes(s, nf) for s in model.surfaces]

    off_frames = HEADER_SIZE
    off_tags = off_frames + nf * FRAME_SIZE
    off_surfs = off_tags + ntag * nf * TAG_SIZE
    eof = off_surfs + sum(len(b) for b in blobs)

    out = bytearray()
    out += struct.pack(HEADER_FMT, MD3_IDENT, MD3_VERSION,
                       _cstr(model.name or "model", 64), 0,
                       nf, ntag, len(model.surfaces), 0,
                       off_frames, off_tags, off_surfs, eof)

    # Bounds from the surfaces actually present: a subset's box is not the
    # whole gun's, and a stale radius culls a model that is on screen. They
    # are computed from the QUANTISED positions, so what the header claims is
    # what a reader will find.
    for f in range(nf):
        pts = [(_quant(v[0]) * XYZ_STEP, _quant(v[1]) * XYZ_STEP, _quant(v[2]) * XYZ_STEP)
               for s in model.surfaces for v in s.verts[f]]
        if pts:
            mins = [min(p[a] for p in pts) for a in range(3)]
            maxs = [max(p[a] for p in pts) for a in range(3)]
            radius = max(math.sqrt(p[0] ** 2 + p[1] ** 2 + p[2] ** 2) for p in pts)
        else:
            mins = maxs = [0.0, 0.0, 0.0]
            radius = 0.0
        name = model.frames[f].name if f < len(model.frames) else f"frame{f}"
        out += struct.pack(FRAME_FMT, *mins, *maxs, 0.0, 0.0, 0.0, radius, _cstr(str(name), 16))

    for f in range(nf):
        for t in (per_frame[f] if f < len(per_frame) else []):
            axis = t.axis
            flat = [c for row in axis for c in row] if isinstance(axis[0], (list, tuple)) \
                else list(axis)
            out += struct.pack(TAG_FMT, _cstr(t.name, 64), *t.origin, *flat)

    for b in blobs:
        out += b

    if len(out) != eof:
        raise MD3Error(f"{path}: wrote {len(out)} bytes, the header says {eof}")
    with open(path, "wb") as fh:
        fh.write(bytes(out))


# ----------------------------------------------------------------- geometry

def _rotation_onto(a: Sequence[float], b: Sequence[float]) -> List[List[float]]:
    """The rotation carrying unit vector a onto unit vector b (Rodrigues)."""
    ax = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    s = math.sqrt(sum(c * c for c in ax))
    c = sum(a[i] * b[i] for i in range(3))
    if s < 1e-9:
        if c > 0:
            return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        # Opposite: a half turn about any perpendicular.
        p = [1.0, 0.0, 0.0] if abs(a[0]) < 0.9 else [0.0, 1.0, 0.0]
        ax = [a[1] * p[2] - a[2] * p[1], a[2] * p[0] - a[0] * p[2], a[0] * p[1] - a[1] * p[0]]
        s = math.sqrt(sum(q * q for q in ax))
        k = [q / s for q in ax]
        return [[2 * k[i] * k[j] - (1.0 if i == j else 0.0) for j in range(3)] for i in range(3)]
    k = [q / s for q in ax]
    ang = math.atan2(s, c)
    K = [[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]]
    K2 = [[sum(K[i][m] * K[m][j] for m in range(3)) for j in range(3)] for i in range(3)]
    return [[(1.0 if i == j else 0.0) + math.sin(ang) * K[i][j] + (1 - math.cos(ang)) * K2[i][j]
             for j in range(3)] for i in range(3)]


def _apply(R: Sequence[Sequence[float]], v: Sequence[float]) -> Tuple[float, float, float]:
    return tuple(sum(R[i][j] * v[j] for j in range(3)) for i in range(3))


def extract(src: str, surfaces: Sequence[str], out: str, axis=None,
            skin: Optional[str] = None, frame: int = 0) -> dict:
    """Lift `surfaces` (by name) at `frame` out of `src` into its own
    single-frame MD3 at `out`, re-origined on their shared centroid and, if
    `axis` is given, rotated so that axis points to -Z.

    A magazine that leaves a gun has to BE that gun's magazine: it is already
    in the gun's mesh, already textured by the gun's skin, and only needed
    lifting out. Re-origined, because a loose object pitches about its model
    origin and a magazine still carrying the gun's origin tumbles about a
    point thirty units away. Axis-aligned, because the actor lies it on its
    side by rolling 90 degrees, and one still carrying the grip's rake lies
    on the floor at that angle, half sunk into it.

    Returns what the result measures, for a card: the size along each axis,
    and half the thinnest side, which is how high its origin sits above the
    floor when it lies on its side.
    """
    m = MD3Model.load(src)
    by = {s.name: s for s in m.surfaces}
    missing = [n for n in surfaces if n not in by]
    _require(not missing, f"{src}: no surface named {missing}; it has {list(by)}")
    picked = [by[n] for n in surfaces]

    pts = [tuple(v) for s in picked for v in s.verts[frame]]
    _require(len(pts) > 0, f"{src}: surfaces {list(surfaces)} have no vertices at frame {frame}")
    c = [sum(p[i] for p in pts) / len(pts) for i in range(3)]

    R = None
    if axis is not None:
        ln = math.sqrt(sum(q * q for q in axis))
        _require(ln > 1e-9, f"{src}: extract axis {list(axis)} has no length")
        R = _rotation_onto([q / ln for q in axis], [0.0, 0.0, -1.0])

    new_surfs = []
    for idx, s in enumerate(picked):
        moved = [tuple(v[i] - c[i] for i in range(3)) for v in s.verts[frame]]
        if R is None:
            verts = moved
            norms = list(s.normals[frame])
            packed = [list(s.normals_packed[frame])] if s.normals_packed else []
        else:
            verts = [_apply(R, v) for v in moved]
            norms = [_apply(R, n) for n in s.normals[frame]]
            packed = []          # reposed: the raw shorts no longer describe it
        shaders = [MD3Shader(name=skin or sh.name, shader_index=0) for sh in s.shaders] \
            or [MD3Shader(name=skin or "", shader_index=0)]
        new_surfs.append(MD3Surface(index=idx, name=s.name, num_frames=1, shaders=shaders,
                                    triangles=list(s.triangles), st=list(s.st),
                                    verts=[verts], normals=[norms], normals_packed=packed))

    frame0 = MD3Frame(mins=(0, 0, 0), maxs=(0, 0, 0), origin=(0, 0, 0), radius=0.0, name="rest")
    model = MD3Model(source=out, name="+".join(surfaces), num_frames=1,
                     frames=[frame0], tags=[], surfaces=new_surfs)
    write(model, out)

    # Prove it by reading it back with the reader everything else trusts.
    back = MD3Model.load(out)
    allv = [tuple(v) for s in back.surfaces for v in s.verts[0]]
    lo = [min(p[i] for p in allv) for i in range(3)]
    hi = [max(p[i] for p in allv) for i in range(3)]
    size = [hi[i] - lo[i] for i in range(3)]
    return {"out": out, "surfaces": [s.name for s in back.surfaces], "verts": len(allv),
            "size": size, "min": lo, "max": hi, "centroid_was": tuple(c),
            "half_thinnest": min(size) / 2.0,
            "shaders": [sh.name for s in back.surfaces for sh in s.shaders]}


# --------------------------------------------------------------- self-check

def _self_check(path: str) -> int:
    try:
        m = MD3Model.load(path)
    except MD3Error as e:
        print(f"FAIL: {e}")
        return 1
    print(f"=== {path} ===")
    print(f"name: {m.name!r}   frames: {m.num_frames}   surfaces: {len(m.surfaces)}   "
          f"tags/frame: {len(m.tags[0]) if m.tags else 0}")
    for s in m.surfaces:
        lo, hi = s.bounds(0)
        span = tuple(round(hi[a] - lo[a], 3) for a in range(3))
        print(f"  [{s.index}] {s.name:24} verts={s.num_verts:6} tris={s.num_triangles:6} "
              f"shaders={len(s.shaders)}  frame0 span={span}")
    print("OK -- structurally valid, every offset and index in range.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python md3.py path/to/model.md3")
        sys.exit(2)
    sys.exit(_self_check(sys.argv[1]))
