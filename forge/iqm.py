#!/usr/bin/env python3
"""
iqm.py -- read an Inter-Quake Model far enough to MEASURE it. GUN_SEATING_PLAN.md phase 0.

WHAT THIS IS FOR, AND WHAT IT IS NOT. The engine already loads IQM; this is the tooling side,
so a palm point can be measured off a Breach gun the same way it is measured off an MD3. It
reads vertex positions, triangles, and the JOINTS with their bind-pose positions resolved into
model space. It does not read animation frames, normals, texcoords, blend weights or materials,
and it is not a loader for anything to draw.

WHY THE JOINTS MATTER HERE. The ten Breach guns are rigged, and a rigged gun carries the hand
that was posed on it. That is the plan's own step 3 -- take the rig's right-hand joint as the
palm rather than guessing a point on the mesh -- and it is why those ten are the EASIEST of the
78 rather than the hardest: the answer is in the file.

Format: https://github.com/lsalzman/iqm -- version 2 header, 27 uint32 after a 16-byte magic.
Standard library only.
"""

from __future__ import annotations

import math
import struct
from typing import Dict, List, Optional, Sequence, Tuple

MAGIC = b"INTERQUAKEMODEL\0"

# iqmvertexarraytype
POSITION, TEXCOORD, NORMAL, TANGENT, BLENDINDEXES, BLENDWEIGHTS, COLOR = range(7)

# iqmformat -> (struct code, bytes)
_FMT = {0: ("b", 1), 1: ("B", 1), 2: ("h", 2), 3: ("H", 2), 4: ("i", 4),
        5: ("I", 4), 6: ("e", 2), 7: ("f", 4), 8: ("d", 8)}

_HDR = ("version filesize flags num_text ofs_text num_meshes ofs_meshes num_vertexarrays "
        "num_vertexes ofs_vertexarrays num_triangles ofs_triangles ofs_adjacency num_joints "
        "ofs_joints num_poses ofs_poses num_anims ofs_anims num_frames num_framechannels "
        "ofs_frames ofs_bounds num_comment ofs_comment num_extensions ofs_extensions").split()


class IQMError(ValueError):
    pass


class Joint:
    __slots__ = ("index", "name", "parent", "translate", "rotate", "scale", "world")

    def __init__(self, index, name, parent, translate, rotate, scale):
        self.index = index
        self.name = name
        self.parent = parent
        self.translate = translate      # local, relative to parent
        self.rotate = rotate            # quaternion x, y, z, w
        self.scale = scale
        self.world: Tuple[float, float, float] = (0.0, 0.0, 0.0)   # filled by _resolve

    def __repr__(self):
        return f"Joint({self.index} {self.name!r} parent={self.parent})"


class Mesh:
    __slots__ = ("name", "first_vertex", "num_vertexes", "first_triangle", "num_triangles")

    def __init__(self, name, fv, nv, ft, nt):
        self.name = name
        self.first_vertex = fv
        self.num_vertexes = nv
        self.first_triangle = ft
        self.num_triangles = nt

    def __repr__(self):
        return f"Mesh({self.name!r} verts={self.num_vertexes} tris={self.num_triangles})"


def _mat(t, q, s):
    """A 4x4 row-major matrix from translate, quaternion (x,y,z,w) and scale.
    The quaternion is normalised here: IQM stores them unnormalised and a frame's
    interpolated channels drift, which shows up as a limb that slowly grows."""
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n > 1e-12:
        x, y, z, w = x / n, y / n, z / n, w / n
    sx, sy, sz = s
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return [
        (1 - 2 * (yy + zz)) * sx, (2 * (xy - wz)) * sy, (2 * (xz + wy)) * sz, t[0],
        (2 * (xy + wz)) * sx, (1 - 2 * (xx + zz)) * sy, (2 * (yz - wx)) * sz, t[1],
        (2 * (xz - wy)) * sx, (2 * (yz + wx)) * sy, (1 - 2 * (xx + yy)) * sz, t[2],
        0.0, 0.0, 0.0, 1.0,
    ]


def _mm(a, b):
    """a x b, both 4x4 row-major affine."""
    out = [0.0] * 16
    for r in range(3):
        ar = r * 4
        for c in range(4):
            out[ar + c] = (a[ar] * b[c] + a[ar + 1] * b[4 + c]
                           + a[ar + 2] * b[8 + c] + a[ar + 3] * (1.0 if c == 3 else 0.0))
    out[12] = out[13] = out[14] = 0.0
    out[15] = 1.0
    return out


def _minv(m):
    """Inverse of an affine 4x4 whose upper 3x3 may carry scale. Cofactor inverse of the
    3x3, then the translation through it. A singular 3x3 (a zero scale on some rig) gives
    the identity rather than a crash, and the caller sees the joint simply not move."""
    a, b, c = m[0], m[1], m[2]
    d, e, f = m[4], m[5], m[6]
    g, h, i = m[8], m[9], m[10]
    A, B, C = e * i - f * h, -(d * i - f * g), d * h - e * g
    det = a * A + b * B + c * C
    if abs(det) < 1e-18:
        return [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
    s = 1.0 / det
    r = [A * s, (-(b * i - c * h)) * s, (b * f - c * e) * s, 0.0,
         B * s, (a * i - c * g) * s, (-(a * f - c * d)) * s, 0.0,
         C * s, (-(a * h - b * g)) * s, (a * e - b * d) * s, 0.0,
         0.0, 0.0, 0.0, 1.0]
    tx, ty, tz = m[3], m[7], m[11]
    r[3] = -(r[0] * tx + r[1] * ty + r[2] * tz)
    r[7] = -(r[4] * tx + r[5] * ty + r[6] * tz)
    r[11] = -(r[8] * tx + r[9] * ty + r[10] * tz)
    return r


def _mxv(m, v):
    return (m[0] * v[0] + m[1] * v[1] + m[2] * v[2] + m[3],
            m[4] * v[0] + m[5] * v[1] + m[6] * v[2] + m[7],
            m[8] * v[0] + m[9] * v[1] + m[10] * v[2] + m[11])


def _qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def _qrot(q, v):
    """v turned by quaternion q (x, y, z, w)."""
    x, y, z, w = q
    vx, vy, vz = v
    # t = 2 * (q_vec x v)
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx))


class IQMModel:
    """One IQM file's geometry and skeleton, in model space."""

    def __init__(self):
        self.header: Dict[str, int] = {}
        self.verts: List[Tuple[float, float, float]] = []
        self.triangles: List[Tuple[int, int, int]] = []
        self.meshes: List[Mesh] = []
        self.joints: List[Joint] = []
        # WHICH BONE EACH VERTEX FOLLOWS. Every gun mesh in the ten Breach files is bound
        # one-bone-per-vertex with no multi-weighting, so a single index is exact and no
        # weight blending is needed. Empty when the file has no BLENDINDEXES array.
        self.bone_index: List[int] = []
        self.poses: List[Tuple[int, int, Tuple[float, ...], Tuple[float, ...]]] = []
        self.frames: List[Tuple[int, ...]] = []

    # ---- loading -------------------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> "IQMModel":
        with open(path, "rb") as f:
            return cls.from_bytes(f.read(), path)

    @classmethod
    def from_bytes(cls, data: bytes, source: str = "<bytes>") -> "IQMModel":
        if len(data) < 16 + 27 * 4:
            raise IQMError(f"{source}: too short to be an IQM")
        if data[:16] != MAGIC:
            raise IQMError(f"{source}: not an IQM (magic {data[:16]!r})")
        m = cls()
        m.header = dict(zip(_HDR, struct.unpack_from("<27I", data, 16)))
        h = m.header
        if h["version"] != 2:
            raise IQMError(f"{source}: IQM version {h['version']}, this reads version 2")
        if h["filesize"] > len(data):
            raise IQMError(f"{source}: header says {h['filesize']} bytes, file has {len(data)}")

        text = data[h["ofs_text"]:h["ofs_text"] + h["num_text"]] if h["num_text"] else b""

        def name_at(off: int) -> str:
            if not text or off >= len(text):
                return ""
            end = text.find(b"\0", off)
            return text[off:end if end >= 0 else len(text)].decode("utf-8", "replace")

        m._read_vertexarrays(data, source)
        m._read_triangles(data, source)
        m._read_meshes(data, name_at)
        m._read_joints(data, name_at)
        m._resolve_joints()
        m._read_poses(data)
        m._read_frames(data)
        return m

    def _read_poses(self, data: bytes) -> None:
        """iqmpose: parent, channelmask, 10 channel offsets, 10 channel scales."""
        h = self.header
        for i in range(h.get("num_poses", 0)):
            off = h["ofs_poses"] + i * 88
            if off + 88 > len(data):
                break
            parent, mask = struct.unpack_from("<iI", data, off)
            chans = struct.unpack_from("<20f", data, off + 8)
            self.poses.append((parent, mask, chans[:10], chans[10:]))

    def _read_frames(self, data: bytes) -> None:
        nf = self.header.get("num_frames", 0)
        nc = self.header.get("num_framechannels", 0)
        if not nf or not nc:
            return
        ofs = self.header["ofs_frames"]
        need = ofs + nf * nc * 2
        if need > len(data):
            return
        unpack = struct.Struct("<" + "H" * nc).unpack_from
        self.frames = [unpack(data, ofs + f * nc * 2) for f in range(nf)]

    def _read_vertexarrays(self, data: bytes, source: str) -> None:
        h = self.header
        n, ofs = h["num_vertexarrays"], h["ofs_vertexarrays"]
        nv = h["num_vertexes"]
        for i in range(n):
            va_type, flags, fmt, size, off = struct.unpack_from("<5I", data, ofs + i * 20)
            if va_type != POSITION:
                continue
            if fmt not in _FMT:
                raise IQMError(f"{source}: position array has unknown format {fmt}")
            if size < 3:
                raise IQMError(f"{source}: position array has {size} components, needs 3")
            code, width = _FMT[fmt]
            stride = width * size
            need = off + stride * nv
            if need > len(data):
                raise IQMError(f"{source}: position array runs {need - len(data)} bytes past the file")
            unpack = struct.Struct("<" + code * size).unpack_from
            self.verts = [tuple(unpack(data, off + j * stride)[:3]) for j in range(nv)]
            break
        else:
            raise IQMError(f"{source}: no POSITION vertex array")
        self._read_bone_index(data, n, ofs, nv)

    def _read_bone_index(self, data: bytes, n: int, ofs: int, nv: int) -> None:
        """The FIRST blend index per vertex. Exact for these files -- all ten have zero
        multi-weighted vertices, gun meshes and hands alike -- and a safe approximation
        for any file that does blend, since the first index carries the largest weight by
        convention."""
        for i in range(n):
            va_type, flags, fmt, size, off = struct.unpack_from("<5I", data, ofs + i * 20)
            if va_type != BLENDINDEXES or fmt not in _FMT:
                continue
            code, width = _FMT[fmt]
            stride = width * size
            if off + stride * nv > len(data):
                return
            unpack = struct.Struct("<" + code * size).unpack_from
            self.bone_index = [unpack(data, off + j * stride)[0] for j in range(nv)]
            return

    def _read_triangles(self, data: bytes, source: str) -> None:
        h = self.header
        nt, ofs = h["num_triangles"], h["ofs_triangles"]
        if ofs + nt * 12 > len(data):
            raise IQMError(f"{source}: triangle array runs past the file")
        unpack = struct.Struct("<3I").unpack_from
        nv = len(self.verts)
        tris = []
        for i in range(nt):
            t = unpack(data, ofs + i * 12)
            if max(t) < nv:
                tris.append(t)
        self.triangles = tris

    def _read_meshes(self, data: bytes, name_at) -> None:
        h = self.header
        for i in range(h["num_meshes"]):
            name, _mat, fv, nv, ft, nt = struct.unpack_from("<6I", data, h["ofs_meshes"] + i * 24)
            self.meshes.append(Mesh(name_at(name), fv, nv, ft, nt))

    def _read_joints(self, data: bytes, name_at) -> None:
        h = self.header
        if not h["num_joints"]:
            return
        for i in range(h["num_joints"]):
            off = h["ofs_joints"] + i * 48
            name, parent = struct.unpack_from("<Ii", data, off)
            tx, ty, tz, rx, ry, rz, rw, sx, sy, sz = struct.unpack_from("<10f", data, off + 8)
            self.joints.append(Joint(i, name_at(name), parent,
                                     (tx, ty, tz), (rx, ry, rz, rw), (sx, sy, sz)))

    def _resolve_joints(self) -> None:
        """Each joint's BIND-POSE position in model space, by walking its parent chain.
        A joint's stored translate/rotate are relative to its parent, so a hand bone's
        position means nothing until the chain above it is applied."""
        for j in self.joints:
            pos = (0.0, 0.0, 0.0)
            rot = (0.0, 0.0, 0.0, 1.0)
            chain: List[Joint] = []
            k: Optional[Joint] = j
            seen = set()
            while k is not None:
                if k.index in seen:        # a malformed file can loop; refuse to hang
                    break
                seen.add(k.index)
                chain.append(k)
                k = self.joints[k.parent] if 0 <= k.parent < len(self.joints) else None
            for node in reversed(chain):
                turned = _qrot(rot, node.translate)
                pos = (pos[0] + turned[0], pos[1] + turned[1], pos[2] + turned[2])
                rot = _qmul(rot, node.rotate)
            j.world = pos

    # ---- what the palm pass asks of it ---------------------------------------------

    # ---- the DRAWN pose -------------------------------------------------------------
    #
    # THE BIND POSE IS NOT WHAT THE ENGINE DRAWS, and on these ten files that is not a
    # detail. The five Breach rifles are drawn at frame 25 of 360, the MP5 at 109 of 244,
    # the Benelli at 59 of 243. In the bind pose the right wrist sits ABOVE the receiver,
    # where no hand could be; at the drawn frame it is on the grip. Anything measured off
    # the bind pose -- a palm, a bounding box, a support point -- is measured off a pose
    # the player never sees.

    def _frame_matrices(self, frame: int) -> List[List[float]]:
        """Each pose's model-space matrix at this frame, parents applied."""
        out: List[List[float]] = []
        if not self.frames:
            return out
        f = self.frames[max(0, min(frame, len(self.frames) - 1))]
        ch = 0
        for parent, mask, offs, scales in self.poses:
            v = list(offs)
            for c in range(10):
                if mask & (1 << c):
                    if ch < len(f):
                        v[c] = offs[c] + f[ch] * scales[c]
                    ch += 1
            local = _mat((v[0], v[1], v[2]), (v[3], v[4], v[5], v[6]), (v[7], v[8], v[9]))
            out.append(_mm(out[parent], local) if 0 <= parent < len(out) else local)
        return out

    def skin_matrices(self, frame: int) -> List[List[float]]:
        """frame x inverse(bind), per joint -- what takes a bind-pose vertex to the frame."""
        fm = self._frame_matrices(frame)
        if not fm:
            return []
        out = []
        for j in self.joints:
            bind = _mat(j.translate, j.rotate, j.scale)
            if 0 <= j.parent < len(self.joints):
                # the bind chain, same accumulation _resolve_joints does
                chain = []
                k: Optional[Joint] = j
                seen = set()
                while k is not None and k.index not in seen:
                    seen.add(k.index)
                    chain.append(k)
                    k = self.joints[k.parent] if 0 <= k.parent < len(self.joints) else None
                bind = _mat(chain[-1].translate, chain[-1].rotate, chain[-1].scale)
                for node in reversed(chain[:-1]):
                    bind = _mm(bind, _mat(node.translate, node.rotate, node.scale))
            m = fm[j.index] if j.index < len(fm) else bind
            out.append(_mm(m, _minv(bind)))
        return out

    def posed_verts(self, frame: int) -> List[Tuple[float, float, float]]:
        """Every vertex at the drawn frame. Falls back to the bind pose when the file
        carries no animation, which is the correct answer for a static model."""
        sk = self.skin_matrices(frame)
        if not sk or not self.bone_index:
            return list(self.verts)
        out = []
        for i, v in enumerate(self.verts):
            b = self.bone_index[i] if i < len(self.bone_index) else 0
            out.append(_mxv(sk[b], v) if 0 <= b < len(sk) else v)
        return out

    def posed_joint(self, frame: int, joint: Joint) -> Tuple[float, float, float]:
        """Where a joint actually is at the drawn frame."""
        fm = self._frame_matrices(frame)
        if not fm or joint.index >= len(fm):
            return joint.world
        m = fm[joint.index]
        return (m[3], m[7], m[11])

    def gun_vertex_indices(self, frame: Optional[int] = None) -> List[int]:
        """The gun as the player sees it: every vertex except the viewmodel hands and,
        when a frame is given, any PART PARKED OFF-SCREEN at that frame.

        The parked part is not a curiosity. At frame 25 the MK18 carries a second
        magazine on `j_mag2`, 3430 vertices sitting at z -141 while the gun occupies
        z -22..1 -- which is how a reload animation stows the spare where the player
        cannot see it. Include it and the gun's bounding box is six times too tall, every
        derived measurement scales off that box, and a palm computed as a fraction of it
        lands nowhere near the gun. Excluding it reproduces the CSV's own bbox and vertex
        count exactly, on all ten files.

        The rule is geometric rather than a list of bone names, because the bone names
        differ per rig (`j_mag2`, a spare shell, a sling tag) and a name list would miss
        the next one: take the bone carrying the most vertices as the gun's body, then
        drop any bone whose own posed box lies wholly outside that body's box, generously
        inflated. A part that overlaps the gun at all is kept.
        """
        keep: List[int] = []
        for mm in self.meshes:
            if "v_hands" in mm.name.lower():
                continue
            keep.extend(range(mm.first_vertex,
                              min(mm.first_vertex + mm.num_vertexes, len(self.verts))))
        if frame is None or not self.bone_index:
            return keep

        pv = self.posed_verts(frame)
        by_bone: Dict[int, List[int]] = {}
        for i in keep:
            by_bone.setdefault(self.bone_index[i] if i < len(self.bone_index) else 0, []).append(i)
        if len(by_bone) < 2:
            return keep

        body = max(by_bone, key=lambda b: len(by_bone[b]))
        blo = [min(pv[i][a] for i in by_bone[body]) for a in range(3)]
        bhi = [max(pv[i][a] for i in by_bone[body]) for a in range(3)]
        # Inflate by the body's own size: a magazine or stock legitimately sticks out,
        # a part stowed off-screen is orders of magnitude away.
        pad = [max(bhi[a] - blo[a], 1.0) for a in range(3)]
        out: List[int] = []
        for b, idxs in by_bone.items():
            lo = [min(pv[i][a] for i in idxs) for a in range(3)]
            hi = [max(pv[i][a] for i in idxs) for a in range(3)]
            parked = any(hi[a] < blo[a] - pad[a] or lo[a] > bhi[a] + pad[a] for a in range(3))
            if not parked:
                out.extend(idxs)
        return out

    def hand_vertex_indices(self) -> List[int]:
        keep: List[int] = []
        for mm in self.meshes:
            if "v_hands" in mm.name.lower():
                keep.extend(range(mm.first_vertex,
                                  min(mm.first_vertex + mm.num_vertexes, len(self.verts))))
        return keep

    def bounds(self):
        if not self.verts:
            return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        lo = tuple(min(v[a] for v in self.verts) for a in range(3))
        hi = tuple(max(v[a] for v in self.verts) for a in range(3))
        return lo, hi

    def joint(self, *fragments: str) -> Optional[Joint]:
        """The first joint whose name contains every fragment, case-insensitively.
        Rig naming is not consistent between the Breach rigs, so callers pass several
        spellings rather than one exact name."""
        for j in self.joints:
            low = j.name.lower()
            if all(f.lower() in low for f in fragments):
                return j
        return None

    def hand_joint(self, side: str = "r") -> Optional[Joint]:
        """The hand joint for a side, trying the spellings these rigs actually use.
        NEVER the thumb -- thumb joints are inconsistent between rigs (RS_AVATAR.md)."""
        s = side.lower()[0]
        for frags in ((f"hand_{s}",), (f"hand.{s}",), (f"{s}_hand",), (f"hand{s}",),
                      ("hand", f"_{s}"), ("hand", f".{s}"), ("palm", s), ("wrist", s)):
            j = self.joint(*frags)
            if j is not None and "thumb" not in j.name.lower():
                return j
        return None


def load(path: str) -> IQMModel:
    return IQMModel.load(path)


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        m = IQMModel.load(p)
        lo, hi = m.bounds()
        print(f"{p}")
        print(f"  verts {len(m.verts)}  tris {len(m.triangles)}  meshes {len(m.meshes)}  "
              f"joints {len(m.joints)}")
        print(f"  bounds {tuple(round(v, 2) for v in lo)} .. {tuple(round(v, 2) for v in hi)}")
        for side in ("r", "l"):
            j = m.hand_joint(side)
            if j:
                print(f"  {side} hand: {j.name!r} at {tuple(round(v, 2) for v in j.world)}")
        for mesh in m.meshes:
            print(f"    {mesh!r}")
