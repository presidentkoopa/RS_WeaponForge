# Measuring a rigged model: use the frame the engine draws

2026-10-02. Written after the Breach IQM guns cost most of an afternoon to measure correctly.
This is not Breach-specific; it applies to any rigged model this toolchain measures.

## The rule

**Measure at the frame MODELDEF draws. Never the bind pose.**

The bind pose is the rig's rest configuration. It is not what the player sees and, on a
viewmodel, it is usually nowhere near it.

| gun | drawn frame | of |
|---|---|---|
| Breach MK18, MK18S, HK416S, MCX, G36C | 25 | 360 |
| Breach MP5 | 109 | 244 |
| Breach Benelli | 59 | 243 |
| Breach Glock, GlockS, Kimber | 0 | 209 |

In the bind pose the Breach right wrist sits **above the receiver**, where no hand could be.
At the drawn frame it is on the grip. The `GUN_SEATING_PLAN.md` step that says "use the rig's
own right-hand joints as the palm" produces a point in mid-air if taken literally, because it
reads the rest pose.

## Parts are parked off-screen at the drawn frame

At frame 25 the MK18's bone `j_mag2` holds a **second magazine** at z −141, while the gun
itself occupies z −22..1. That is 3430 vertices — exactly the count by which an earlier
report's vertex total was out. A reload animation stows the spare magazine where the player
cannot see it, and it is still in the file.

Include it and the gun's bounding box is six times too tall. Every measurement derived as a
fraction of that box — a palm at 20% of length, a support point 60% of the way to the muzzle —
then lands nowhere near the gun, and nothing in the numbers says so.

**Exclude it geometrically, not by name.** Take the bone carrying the most vertices as the
gun's body, then drop any bone whose own posed bounding box lies wholly outside that body's
box, generously inflated. A magazine or a stock that legitimately sticks out still overlaps
and is kept; a part stowed off-screen is orders of magnitude away.

Names will not do this job. The parked bone is `j_mag2` here; on another rig it is a spare
shell or a sling tag. A name list catches the one you have seen and misses the next.

This rule reproduces the measured bounding boxes and vertex counts **exactly on 8 of the 10**
Breach guns. The two that differ do so for understood reasons: MK18S has a suppressor held in
`extra_models`, and the Benelli carries a 103-vertex loose ejecting shell. Neither is near a
grip.

## Two things that make posing cheap

**Gun meshes are rigidly bound.** All ten Breach files have one bone per vertex and *zero*
multi-weighted vertices, hands included. So a posed vertex is exactly `F_j · M_j⁻¹ · v` for
its single bone — no weight blending, no approximation.

**The arms are in the file.** Each Breach IQM ships the viewmodel hands as a `v_hands` mesh
that MODELDEF hides. Drop it for any measurement of the gun — but pose it first if you want
the hand, because a rigged gun carries the hand that was posed on it, and that is better
evidence for a grip than anything derived from the mesh alone.

## Where the code is

`WeaponForge/forge/iqm.py` — vertex positions, triangles, joints, bind-pose resolution, frame
evaluation (`posed_verts`, `posed_joint`, `skin_matrices`) and the parked-part rule
(`gun_vertex_indices(frame)`). It reads version 2 IQM and deliberately does not read normals,
texcoords, materials or blend weights: this is a measuring tool, not a loader.
