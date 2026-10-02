# sets/bd22/set.py -- BRUTAL DOOM v22, 25 guns.
#
# The one file a person edits for this set. Everything measured comes out of the
# donor meshes; nothing measured is typed here.
#
# WHERE THE PART MAPS CAME FROM. Not from guesses and not from the tool's own
# suggestions: from the BD22 pack that already exists. Every surface of every
# shipped bd22 _wm mesh was matched back to a donor surface by vertex count --
# the totals agree exactly, gun for gun, so those meshes came from these donors
# -- and each part keeps the role and subject its shipped card gave it.
#
# WHAT THIS CHANGES ABOUT THE CURRENT PACK. The shipped BD22 was built with the
# rest pose assumed to be frame 0 for every gun (CardPipeline's REST = {g: 0}).
# It is not: the pistol's is 2, the shotgun's 4, the chainsaw's 15, the SSG's 1.
# Frame 0 is usually the RAISE -- the gun swinging up into view -- so those guns
# have been frozen mid-raise, which is why they sit wrong in the hand however the
# offsets are tuned. Every rest frame below is resolved from the donor's own
# Ready: state.
#
# EXPECT THE PLACEMENT TO NEED REDOING. The mesh moves, so the offsets that were
# tuned against the old pose no longer mean the same thing: clear every bd_* line
# from the ini before the headset pass.
#
# THREE GUNS LOSE A PART for now -- the buzzsaw's and machinegun's magazines and
# the flamethrower's canister. In the shipped meshes each is an island cut by hand
# inside the gun's body surface, and no box reproduces those cuts. Each gun builds
# whole without it.

SET_ID      = "bd22"
PREFIX      = "BD_"
DONOR_ROOT  = r"D:\SteamLibrary\steamapps\Common\DooM VR\__Games\BrutalDoom\_BD_1.01_WeaponModels"
PARENT_MOD  = r"E:\DOOMWork\RS_VR_Weapons\bd22\brutal22test6.pk3"
PACK        = r"E:\DOOMWork\RS_VR_Weapons\bd22"
MODEL_PATH  = "models/bd22"
CVAR_PREFIX = "bd"

# THE FIRING LINE (forge/emit_prop.firing_line). The owner, 09-29: recentre the set on the M4A3 through
# the BD pistol, then every other gun from the pistol. Each gun's bore goes on the M4A3's bore line; the
# pistol's grip on the M4A3's grip, and every gun moves along its length by what the pistol moved. The
# reference numbers are the M4A3's own, copied from where they live: its tuned block (RS_VR_Weapons
# MODELDEF, WM_PropM4A3) and its card (RS_VR_Weapons WMCARD.01_pistol: muzzle, and magcenter -- its grip).
# Melee and thrown weapons have no bore to put on a line and keep their donor seat.
FIRING_LINE = {
    "scale":  (-0.2788, 0.2788, 0.2788),
    "offset": (0.0044, -9.555, -2.8679),
    "muzzle": (18.99, -0.07, 4.27),
    "grip":   (-5.181, 0.022, -8.665),
    "anchor": "pistol",
    # The flamethrower too: its flame leaves a nozzle hung under the pipe, and putting that on the line
    # lifts the whole gun a hand-width; BD's own seat already has its handle in the hand.
    "skip":   ["axe", "dragonslayer", "chainsaw", "grenade", "flamethrower"],
    # WHERE THE CARD'S MUZZLE IS NOT THE BORE (the middle of the mesh's cross-section 0-4 units behind
    # the muzzle, measured 09-29). The BFG and BFG10k are ONE mesh with two barrels, and the card picked
    # the top one for one and the bottom one for the other: both get the middle, so they sit alike.
    # The flame cannon's and the Revenant launcher's front-most vertices are a rim, not the axis.
    # WHERE THE HAND GOES (owner, 10-01: "the exact same method" that seats the Star Wars guns). Each gun
    # named here puts ITS OWN HANDLE -- mesh (x, z), the trigger hand's palm on the grip's centre line --
    # on the M4A3's grip, along the gun AND in height; side stays on the bore line. This replaces the
    # anchor shift and the bore height for these guns. Picks: owner's boxes and HAND_DECISIONS.md, read
    # off renders 10-01 (proposals/grips). UNSURE: flamecannon, hellish, unmaker -- the owner's call.
    "hand": {
        "pistol":          (-5.80, -6.50),   # handle centreline
        "revolver":        (-11.90, -7.50),   # handle centreline
        "shotgun":         (-28.50, -2.50),   # stock wrist behind trigger guard
        "ssg":             (-11.50, -3.50),   # sawn-off pistol grip
        "mp40":            (-18.50, -8.50),   # owner, hand-placed
        "m79":             (-15.00, -3.00),   # stock wrist behind trigger group
        "flamecannon":     (-16.00, -6.00),   # lower tube handle (UNSURE)
        "hellish":         (-14.00, -19.00),   # lower bar (UNSURE)
        "buzzsaw":         (-23.00, -9.00),   # pistol grip
        "chainsaw":        (-24.00, 8.00),   # rear top handle (owner box)
        "assaultshotgun":  (-21.76, -4.28),   # owner box pick
        "bfg":             (-25.50, -9.00),   # rear handle (owner box)
        "bfg10k":          (-32.00, -9.00),   # rear handle
        "smg":             (-12.50, -4.00),   # pistol grip (owner box)
        "flamethrower":    (-28.00, 7.00),   # high rear handle (owner)
        "machinegun":      (-26.30, -8.00),   # pistol grip (owner box)
        "minigun":         (-43.50, 2.00),   # big rear handle (owner)
        "plasma":          (-32.65, -10.86),   # owner, hand-placed
        "rpg":             (19.00, -16.00),   # handle below ammo box (owner)
        "railgun":         (-27.99, -12.57),   # owner, hand-placed
        "rifle":           (-14.70, -9.00),   # pistol grip
        "unmaker":         (-24.00, -14.00),   # low rear jaw (UNSURE)
    },
    "bore": {
        "bfg":         (0.08, 3.69),
        "bfg10k":      (0.08, 3.69),
        "flamecannon": (-2.00, -0.52),
        "hellish":     (-0.75, 7.36),
    },
}

# Owner rulings on parent_audit findings; RUN_SET stops on any finding not listed.
PARENT_RULINGS = {
    "ammo:Clip->Clip2": "bridged in bridge_bd22.zs",
}

# NO CASE LEAVES NINE OF THESE GUNS (`casing: "none"`, 2026-10-02).
#
# A card that says nothing about casing MEANS YES (parser.zs:1776-1781, noCasing
# defaults false), so every gun in this set threw brass -- including the plasma
# rifle, the rail gun, the BFG, the rocket launcher and both flame guns. It came
# out of the measured ejection port, which on a gun with no port at all is just
# the emptier wall of the receiver, so the brass appeared beside the gun rather
# than from it.
#
# THE PORT STAYS MEASURED. rig.zs:3122 throws LIVE rounds from the same point when
# a breech is opened, so `casing: "none"` turns off the brass and leaves the point
# where a round comes out alone.
#
GUNS = {
    "pistol": {
        "class":     "BD_Pistol",
        "donor":     r"Models\Weapons\Hud\BrutalPistol\BrutalPistol.md3",
        "modeldef":  "Modeldef.Pistol.def",
        "decorate":  "Pistol.txt",
        "actor":     "BrutalPistol",
        "hand":      "main",
        "type":      "pistol",
        "capacity":  15,
        "magfamily": "bd_9mm",
        "sounds":    {"magoutsound": "bd22/pistol/magout", "maginsound": "bd22/pistol/magin", "rackapexsound": "bd22/pistol/slideback", "rackresetsound": "bd22/pistol/slidefwd"},
        "body":      "#4",
        "parts": {
            "bolt2": {"surfaces": ["#1"], "role": "action", "subject": "slide"},
            "magazine": {"surfaces": ["#3"], "role": "feed", "subject": "magazine", "carve": True, "take": "no"},
        },
        "fixed":     ["#0", "#2", "#5"],
    },
    "revolver": {
        "class":     "BD_Revolver",
        "donor":     r"Models\Weapons\Hud\Revolver\Revolver.md3",
        "modeldef":  "Modeldef.Revolver.def",
        "decorate":  "Revolver.txt",
        "actor":     "Revolver",
        # R1 CANNOT ANSWER HERE: the BD 1.01 pack defines no Revolver actor.
        # BD22 does, and its Ready: state shows sprite REVO A
        # (brutal22test6.pk3, actors/Weapons/Revolver.dec:173), which
        # Modeldef.Revolver.def:13 maps to frame 0.
        "rest_frame": 0,
        "hand":      "main",
        "type":      "revolver",
        "capacity":  6,
        "magfamily": "bd_357",
        "sounds":    {"opensound": "bd22/revolver/open", "closesound": "bd22/revolver/close", "ejectsound": "bd22/revolver/unload", "loadsound": "bd22/revolver/load"},
        # SIX CHAMBERS, loaded at the breech: the shipped card had no store at all,
        # so the gun could not be reloaded by hand.
        # its cylinder swings out, as its own card named a cylinder part
        "mechanism": "swingout_revolver",
        "stores":    {"cylinder": {"kind": "slotted", "slots": 6}},   # the archetype names it
        "load":      {"into": "cylinder", "id": "cylinder", "where": "breech"},   # id MUST match the archetype's load
        "body":      "#0",
        "parts": {
            # THE CRANE: #1 is the cylinder assembly, which swings 90 degrees out of
            # the frame, and #2 rides with it. The swingout archetype drives a part
            # by this name. The five `shells` are the rounds sitting in it.
            "crane": {"surfaces": ["#1", "#2"], "subject": "cylinder"},
        },
        "fixed":     ["#3", "#4"],
        "hidden":    ["#5", "#6", "#7", "#8", "#9"],
    },
    "shotgun": {
        "class":     "BD_Shotgun",
        "donor":     r"Models\Weapons\Hud\Shotgun\Shotgun.md3",
        "modeldef":  "Modeldef.Shotgun.def",
        "decorate":  "Shotgun.txt",
        "actor":     "Shot_Gun",
        "hand":      "main",
        # NOT "pump" (2026-10-02). `type` is the HAND-SEAT PROFILE, and
        # WM_HandProfile.TypeAt has no "pump" -- so this gun read
        # wm_hs_default_* for every seat, and wm_feel_default_home (0.0)
        # instead of wm_feel_shotgun_home (0.25), which is the "a pump moved
        # a hair would not fire" threshold. DefaultGripClass already treats
        # pump and shotgun as one thing. The word belongs in `mechanism`.
        "type":      "shotgun",
        "capacity":  8,
        "magfamily": "12ga",
        "sounds":    {"cycleoutsound": "bd22/shotgun/pumpout", "cyclehomesound": "bd22/shotgun/pumphome", "loadsound": "bd22/shotgun/load"},
        # IT LOADS THROUGH A GATE UNDERNEATH, eight in the tube and one in the
        # chamber, as its shipped card declared before this rebuild.
        # a tube under the barrel, worked by its forend
        "mechanism": "pump",
        "stores":    {"tube": {"kind": "counted", "capacity": 8, "detach": "no"},
                      "chamber": {"kind": "slotted", "slots": 1}},
        "load":      {"into": "tube", "id": "gate", "where": "under", "size": [2.5, 1.5, 2.0]},
        "body":      "#6",
        "parts": {
            "forend": {"surfaces": ["#4"], "subject": "forend"},
        },
        "fixed":     ["#5"],
        "hidden":    ["#0", "#1", "#2", "#3"],
    },
    "ssg": {
        "class":     "BD_SSG",
        "donor":     r"Models\Weapons\Hud\SSG\ssg.md3",
        "modeldef":  "Modeldef.SSG.def",
        "decorate":  "SSG.txt",
        "actor":     "SSG",
        "hand":      "main",
        "type":      "breakaction",
        "capacity":  2,
        "magfamily": "12ga",
        # IT BREAKS OPEN AND TAKES TWO, loaded at the breech.
        # it breaks open and takes two
        "mechanism": "breakaction",
        "stores":    {"chambers": {"kind": "slotted", "slots": 2}},
        "load":      {"into": "chambers", "id": "breech", "where": "breech"},
        "sounds":    {"opensound": "bd22/ssg/open", "closesound": "bd22/ssg/close", "loadsound": "bd22/ssg/load"},
        "body":      "#1",
        "parts": {
            "barrels": {"surfaces": ["#0"], "subject": "forend"},
            "trigger": {"surfaces": ["#2"], "role": "trigger"},
        },
        "fixed":     ["#3", "#4", "#5", "#6"],
    },
    "mp40": {
        "class":     "BD_MP40",
        "donor":     r"Models\Weapons\Hud\MP40\MP40.md3",
        "modeldef":  "Modeldef.MP40.def",
        "decorate":  "Mp40.txt",
        "actor":     "MP40",
        "hand":      "main",
        "type":      "smg",
        "capacity":  32,
        "magfamily": "bd_9mm",
        "sounds":    {"magoutsound": "bd22/mp40/magout", "maginsound": "bd22/mp40/magin", "rackapexsound": "bd22/mp40/rackback", "rackresetsound": "bd22/mp40/rackfwd"},
        "body":      "#7",
        "parts": {
            "bolt": {"surfaces": ["#0"], "role": "action", "subject": "slide"},
            "magazine": {"surfaces": ["#10"], "role": "feed", "subject": "magazine", "carve": True, "take": "no"},
        },
        "fixed":     ["#1", "#2", "#3", "#4", "#5", "#6", "#8", "#9"],
    },
    "m79": {
        "class":     "BD_M79",
        "donor":     r"Models\Weapons\Hud\M79\M79.md3",
        "modeldef":  "Modeldef.M79.def",
        "decorate":  "GrenadeLaunch.txt",
        "actor":     "GrenadeLauncher",
        "hand":      "main",
        "type":      "launcher",
        "capacity":  1,
        "magfamily": "bd_40mm",
        # ONE IN THE BREECH: a single-shot break-action.
        # single shot, breaks open at the breech
        "mechanism": "breakaction",
        "stores":    {"chambers": {"kind": "slotted", "slots": 1}},   # the archetype names it
        "load":      {"into": "chambers", "id": "breech", "where": "breech"},
        "sounds":    {"opensound": "bd22/m79/open", "closesound": "bd22/m79/close", "loadsound": "bd22/m79/load"},
        "body":      "#0",
        "parts": {
            # ITS "MAGAZINE" WAS THE BARREL. The shipped card drove #4 as a feed;
            # it hinges 53.7 degrees, which is the barrel tipping open -- the M79
            # is a break-action single-shot and loads at the breech, which its
            # store and load blocks above now say. #1 tips with it.
            # ITS BARRELS ARE MOST OF THE GUN, and that is correct. #1 and #4 are
            # 5,647 of 6,858 vertices -- 82% -- which looks like the break tipping
            # the whole weapon, but an M79 IS a fat 40mm tube on a small frame:
            # the body is a 241-vertex stub because there is hardly any receiver.
            # Both surfaces fit as one rigid body turning 45 degrees, so the
            # geometry agrees: they are the barrel assembly, not the gun.
            "barrels": {"surfaces": ["#1", "#4"], "subject": "barrels"},
        },
        "fixed":     ["#2"],
        "hidden":    ["#3"],
    },
    "flamecannon": {
        "class":     "BD_FlameCannon",
        "casing":    "none",   # a flame gun: nothing is chambered and nothing comes out
        # FIRES FROM THE RESERVE, as Brutal Doom does (owner, 2026-10-02).
        #
        # Without this the gun fires ONCE and stops, and the usual explanation --
        # "it has no magazine" -- is wrong. With no `store` and no `firesfrom`,
        # SynthesiseStores (card.zs:715-730) gives it a COUNTED detachable magazine at
        # the stated capacity plus a live chamber. The magazine is not absent, it is
        # UNREACHABLE: SynthesiseVerbs (card.zs:917-926) makes a SWAP only on a
        # `role = feed` part and a CYCLE only on `role = action`, and this gun carries
        # neither -- so nothing in the card can ever refill either store.
        #
        # Reserve is also what BD itself does: FlameCannon.dec and HellishMissile.dec
        # have no A_ReFire and simply spend from the ammo pool. Carving a real magazine
        # would need a magazine class, a MODELDEF prop per gun and a mesh for four of
        # the five -- none of which exist.
        "firesfrom": "reserve",
        "donor":     r"Models\Weapons\Hud\FlameCannon\FlameCannon.md3",
        "modeldef":  "Modeldef.FlameCannon.def",
        "decorate":  "FlameCannon.txt",
        "actor":     "FlameCannon",
        "hand":      "main",
        "type":      "flamethrower",
        "capacity":  100,
        "magfamily": "bd_fuel",
        "body":      "#0",
        # NO MOVING PARTS, and its shipped card carried none either: nothing
        # on this gun is driven by hand.
        "parts":     {},
    },
    "hellish": {
        "class":     "BD_Hellish",
        "casing":    "none",   # a missile tube: nothing is chambered and nothing comes out
        # FIRES FROM THE RESERVE, as Brutal Doom does (owner, 2026-10-02).
        #
        # Without this the gun fires ONCE and stops, and the usual explanation --
        # "it has no magazine" -- is wrong. With no `store` and no `firesfrom`,
        # SynthesiseStores (card.zs:715-730) gives it a COUNTED detachable magazine at
        # the stated capacity plus a live chamber. The magazine is not absent, it is
        # UNREACHABLE: SynthesiseVerbs (card.zs:917-926) makes a SWAP only on a
        # `role = feed` part and a CYCLE only on `role = action`, and this gun carries
        # neither -- so nothing in the card can ever refill either store.
        #
        # Reserve is also what BD itself does: FlameCannon.dec and HellishMissile.dec
        # have no A_ReFire and simply spend from the ammo pool. Carving a real magazine
        # would need a magazine class, a MODELDEF prop per gun and a mesh for four of
        # the five -- none of which exist.
        "firesfrom": "reserve",
        "donor":     r"Models\Weapons\Hud\HellishMissile\HellishMissile.md3",
        "modeldef":  "Modeldef.HellishMissile.def",
        "decorate":  "HellishMissile.txt",
        "actor":     "HellishMissileLauncher",
        "hand":      "main",
        "type":      "launcher",
        "capacity":  6,
        "magfamily": "bd_hell",
        "body":      "#0",
        # NO MOVING PARTS, and its shipped card carried none either: nothing
        # on this gun is driven by hand.
        "parts":     {},
    },
    "buzzsaw": {
        "class":     "BD_Buzzsaw",
        # FIRES FROM THE MAGAZINE, not through a chamber (owner, 2026-10-02).
        #
        # This gun HAS a feed part, so SynthesiseVerbs gives it a SWAP and the magazine
        # can be changed -- but it has no `role = action` part, so it gets no CYCLE.
        # With firesfrom unstated the card defaults to firing through a CHAMBER
        # (card.zs:916-926), and nothing can ever refill that chamber: one shot per
        # magazine, which is not a plasma rifle.
        #
        # Saying `magazine` takes the chamber out of the path: a pull spends a round
        # straight from the magazine, which is how a gun with no bolt to work behaves.
        "firesfrom": "magazine",
        "donor":     r"Models\Weapons\Hud\HitlersBuzzsaw\HitlersBuzzsaw.md3",
        "modeldef":  "Modeldef.HitlersBuzzsaw.def",
        "decorate":  "Mp40.txt",
        "actor":     "HitlersBuzzsaw",
        "hand":      "main",
        "type":      "chaingun",
        # ITS BODY IS THE WHOLE DONOR SURFACE. The shipped mesh has a body
        # surface that is this one minus the island cut out of it, so it matches
        # no donor surface by count; the donor surface itself is the body.
        "sounds":    {"magoutsound": "bd22/generic/magout", "maginsound": "bd22/generic/magin"},
        "body":      "#0",
        "capacity":  200,
        "magfamily": "bd_762",
        "parts": {
            # ITS SADDLE DRUM. Welded into the body surface and beyond any shape
            # rule: the drum's own two halves sit 0.404 apart while the receiver
            # comes within 0.256 of it, so no gap separates them, and the cut
            # slices through sixteen of the welded objects it touches. The vertex
            # set is recovered exactly from the mesh this set shipped before the
            # rebuild -- fit rms 0.0000 -- and checked on every build.
            "magazine": {"surfaces": ["#0"], "role": "feed", "subject": "magazine",
                         "carve": True, "take": "no",
                         "island": {"of": "#0", "verts": 3059,
                                    "cut": "buzzsaw_mag.cut"}},
            "trigger": {"surfaces": ["#1"], "role": "trigger"},
        },
        # ITS MAGAZINE IS NOT DECLARED: in the shipped mesh that part is an island
        # cut by hand inside this gun's body surface, and no box reproduces
        # the cut. The gun builds whole without it.
    },
    "axe": {
        "class":     "BD_Axe",
        "donor":     r"Models\Weapons\Hud\BrutalAxe\BrutalAxe.md3",
        "modeldef":  "Modeldef.BrutalAxe.def",
        "decorate":  "Axe.txt",
        "actor":     "BrutalAxe",
        "hand":      "main",
        "type":      "melee",
        "firesfrom": "none",   # a blade takes no ammunition
        "body":      "#1",
        # NO MOVING PARTS, and its shipped card carried none either: nothing
        # on this gun is driven by hand.
        "parts":     {},
        "fixed":     ["#0"],
    },
    "dragonslayer": {
        "class":     "BD_Dragonslayer",
        "donor":     r"Models\Weapons\Hud\DSweap\DSweap.md3",
        "modeldef":  "Modeldef.DSweap.def",
        "decorate":  "Dragonslayer.txt",
        "actor":     "DSweap",
        "hand":      "main",
        "type":      "melee",
        "firesfrom": "none",   # a blade takes no ammunition
        "body":      "#0",
        # NO MOVING PARTS, and its shipped card carried none either: nothing
        # on this gun is driven by hand.
        "parts":     {},
    },
    "chainsaw": {
        "class":     "BD_Chainsaw",
        "donor":     r"Models\Weapons\Hud\Chain_saw\Chain_saw.md3",
        "modeldef":  "Modeldef.Chain_saw.def",
        "decorate":  "Saw.txt",
        "actor":     "Chain_saw",
        "hand":      "main",
        "type":      "melee",
        "firesfrom": "none",   # a blade takes no ammunition
        # TWO BODIES, ALTERNATING. #0 and #1 are the same 15,188-vertex saw at two
        # chain positions, and the donor flickers between them: #0 has extent only
        # on even frames, #1 only on odd. The Ready frame is 15, odd, so the body
        # that is actually drawn there is #1 -- with #0 collapsed to a point.
        # Freezing #0 gave a body of 15,188 vertices all at one place: a gun that
        # draws nothing.
        "body":      "#1",
        # NO MOVING PARTS, and its shipped card carried none either: nothing
        # on this gun is driven by hand.
        "parts":     {},
        "fixed":     ["#2", "#3", "#4"],
        "hidden":    ["#0"],   # collapsed on the rest frame

    },
    "assaultshotgun": {
        "class":     "BD_AssaultShotgun",
        "donor":     r"Models\Weapons\Hud\AssaultShotgun\AssaultShotgun.md3",
        "modeldef":  "Modeldef.AssaultShotgun.def",
        "decorate":  "AssaultShotgun.txt",
        "actor":     "AssaultShotgun",
        "hand":      "main",
        # NOT "pump" (2026-10-02). `type` is the HAND-SEAT PROFILE, and
        # WM_HandProfile.TypeAt has no "pump" -- so this gun read
        # wm_hs_default_* for every seat, and wm_feel_default_home (0.0)
        # instead of wm_feel_shotgun_home (0.25), which is the "a pump moved
        # a hair would not fire" threshold. DefaultGripClass already treats
        # pump and shotgun as one thing. The word belongs in `mechanism`.
        "type":      "shotgun",
        "capacity":  8,
        "magfamily": "12ga",
        "sounds":    {"magoutsound": "bd22/asg/magout", "maginsound": "bd22/asg/magin", "rackapexsound": "bd22/asg/rackback", "rackresetsound": "bd22/asg/rackfwd"},
        "body":      "#3",
        "parts": {
            "bolt": {"surfaces": ["#2"], "role": "action", "subject": "slide"},
            "magazine": {"surfaces": ["#6"], "role": "feed", "subject": "magazine", "carve": True, "take": "no"},
        },
        "fixed":     ["#1", "#4"],
        "hidden":    ["#0", "#5"],
    },
    "bfg": {
        "class":     "BD_BFG",
        "casing":    "none",   # a cell gun: no case
        # FIRES FROM THE RESERVE, as Brutal Doom does (owner, 2026-10-02).
        #
        # Without this the gun fires ONCE and stops, and the usual explanation --
        # "it has no magazine" -- is wrong. With no `store` and no `firesfrom`,
        # SynthesiseStores (card.zs:715-730) gives it a COUNTED detachable magazine at
        # the stated capacity plus a live chamber. The magazine is not absent, it is
        # UNREACHABLE: SynthesiseVerbs (card.zs:917-926) makes a SWAP only on a
        # `role = feed` part and a CYCLE only on `role = action`, and this gun carries
        # neither -- so nothing in the card can ever refill either store.
        #
        # Reserve is also what BD itself does: FlameCannon.dec and HellishMissile.dec
        # have no A_ReFire and simply spend from the ammo pool. Carving a real magazine
        # would need a magazine class, a MODELDEF prop per gun and a mesh for four of
        # the five -- none of which exist.
        "firesfrom": "reserve",
        "donor":     r"Models\Weapons\Hud\BFG\BFG.md3",
        "modeldef":  "Modeldef.BFG.def",
        "decorate":  "BFG.txt",
        "actor":     "BIG_FUCKING_GUN",
        "hand":      "main",
        "type":      "bfg",
        "capacity":  40,
        "magfamily": "bd_cell",
        "body":      "#0",
        # NO MOVING PARTS, and its shipped card carried none either: nothing
        # on this gun is driven by hand.
        "parts":     {},
        "hidden":    ["#1"],
    },
    "bfg10k": {
        "class":     "BD_BFG10k",
        "casing":    "none",   # a cell gun: no case
        # FIRES FROM THE RESERVE, as Brutal Doom does (owner, 2026-10-02).
        #
        # Without this the gun fires ONCE and stops, and the usual explanation --
        # "it has no magazine" -- is wrong. With no `store` and no `firesfrom`,
        # SynthesiseStores (card.zs:715-730) gives it a COUNTED detachable magazine at
        # the stated capacity plus a live chamber. The magazine is not absent, it is
        # UNREACHABLE: SynthesiseVerbs (card.zs:917-926) makes a SWAP only on a
        # `role = feed` part and a CYCLE only on `role = action`, and this gun carries
        # neither -- so nothing in the card can ever refill either store.
        #
        # Reserve is also what BD itself does: FlameCannon.dec and HellishMissile.dec
        # have no A_ReFire and simply spend from the ammo pool. Carving a real magazine
        # would need a magazine class, a MODELDEF prop per gun and a mesh for four of
        # the five -- none of which exist.
        "firesfrom": "reserve",
        "donor":     r"Models\Weapons\Hud\BFG\BFG_10k.md3",
        "modeldef":  "Modeldef.BFG10k.def",
        "decorate":  "BFG10k.txt",
        "actor":     "BFG10k",
        "hand":      "main",
        "type":      "bfg",
        "capacity":  99,
        "magfamily": "bd_cell",
        "body":      "#0",
        # NO MOVING PARTS, and its shipped card carried none either: nothing
        # on this gun is driven by hand.
        "parts":     {},
        "hidden":    ["#1"],
    },
    "smg": {
        "class":     "BD_SMG",
        # FIRES FROM THE MAGAZINE, not through a chamber (owner, 2026-10-02).
        #
        # This gun HAS a feed part, so SynthesiseVerbs gives it a SWAP and the magazine
        # can be changed -- but it has no `role = action` part, so it gets no CYCLE.
        # With firesfrom unstated the card defaults to firing through a CHAMBER
        # (card.zs:916-926), and nothing can ever refill that chamber: one shot per
        # magazine, which is not a plasma rifle.
        #
        # Saying `magazine` takes the chamber out of the path: a pull spends a round
        # straight from the magazine, which is how a gun with no bolt to work behaves.
        "firesfrom": "magazine",
        "donor":     r"Models\Weapons\Hud\BrutalSMG\BrutalSMG.md3",
        "modeldef":  "Modeldef.SMG.def",
        "decorate":  "SubMachinegun.txt",
        "actor":     "BrutalSMG",
        "hand":      "main",
        "type":      "smg",
        "capacity":  40,
        "magfamily": "bd_9mm",
        "sounds":    {"magoutsound": "bd22/smg/magout", "maginsound": "bd22/smg/magin"},
        "body":      "#1",
        "parts": {
            "magazine": {"surfaces": ["#3"], "role": "feed", "subject": "magazine", "carve": True, "take": "no"},
            "trigger": {"surfaces": ["#2"], "role": "trigger"},
        },
        "fixed":     ["#0"],
    },
    "flamethrower": {
        "class":     "BD_Flamethrower",
        "casing":    "none",   # a flame gun: nothing is chambered and nothing comes out
        # FIRES FROM THE MAGAZINE, not through a chamber (owner, 2026-10-02).
        #
        # This gun HAS a feed part, so SynthesiseVerbs gives it a SWAP and the magazine
        # can be changed -- but it has no `role = action` part, so it gets no CYCLE.
        # With firesfrom unstated the card defaults to firing through a CHAMBER
        # (card.zs:916-926), and nothing can ever refill that chamber: one shot per
        # magazine, which is not a plasma rifle.
        #
        # Saying `magazine` takes the chamber out of the path: a pull spends a round
        # straight from the magazine, which is how a gun with no bolt to work behaves.
        "firesfrom": "magazine",
        "donor":     r"Models\Weapons\Hud\Flamethrower2\Flamethrower2.md3",
        "modeldef":  "Modeldef.Flamethrower2.def",
        "decorate":  "Flamethrower.txt",
        "actor":     "Flamethrower2",
        "hand":      "main",
        "type":      "flamethrower",
        # ITS BODY IS THE WHOLE DONOR SURFACE. The shipped mesh has a body
        # surface that is this one minus the island cut out of it, so it matches
        # no donor surface by count; the donor surface itself is the body.
        "sounds":    {"magoutsound": "bd22/generic/magout", "maginsound": "bd22/generic/magin"},
        "body":      "#0",
        "capacity":  200,
        "magfamily": "bd_fuel",
        "parts": {
            # ITS FUEL CANISTER, recovered the same way: 1,306 vertices of the body
            # surface, fit rms 0.0000 against the mesh this set shipped before.
            "canister": {"surfaces": ["#0"], "role": "feed", "subject": "magazine",
                         "carve": True, "take": "no",
                         "island": {"of": "#0", "verts": 1306,
                                    "cut": "flamethrower_canister.cut"}},
            "trigger": {"surfaces": ["#1"], "role": "trigger"},
        },
        "fixed":     ["#2"],
        # ITS CANISTER IS NOT DECLARED: in the shipped mesh that part is an island
        # cut by hand inside this gun's body surface, and no box reproduces
        # the cut. The gun builds whole without it.
    },
    "grenade": {
        "class":     "BD_Grenade",
        "donor":     r"Models\Weapons\Hud\Grenade\nade.md3",
        "modeldef":  "Modeldef.Grenade.def",
        "decorate":  "Grenades.txt",
        "actor":     "HandGrenades",
        "hand":      "main",
        "type":      "melee",
        "firesfrom": "none",   # a blade takes no ammunition
        "capacity":  1,
        "body":      "#0",
        # NO MOVING PARTS, and its shipped card carried none either: nothing
        # on this gun is driven by hand.
        "parts":     {},
        "fixed":     ["#2", "#3"],
        "hidden":    ["#1", "#4"],
    },
    "machinegun": {
        "class":     "BD_Machinegun",
        # FIRES FROM THE MAGAZINE, not through a chamber. The same ruling the owner
        # gave on 2026-10-02 for the seven guns with a feed part and no action: this
        # gun joins them the moment `role = action` comes off its launcher tube.
        # Without it, SynthesiseVerbs gives it a SWAP and no CYCLE, and firing runs
        # through a chamber nothing can refill -- one shot per magazine.
        "firesfrom": "magazine",
        "donor":     r"Models\Weapons\Hud\Machinegun\Machinegun.md3",
        "modeldef":  "Modeldef.Machinegun.def",
        "decorate":  "Machinegun.txt",
        "actor":     "Machinegun",
        "hand":      "main",
        "type":      "chaingun",
        # ITS BODY IS THE WHOLE DONOR SURFACE. The shipped mesh has a body
        # surface that is this one minus the island cut out of it, so it matches
        # no donor surface by count; the donor surface itself is the body.
        "sounds":    {"magoutsound": "bd22/generic/magout", "maginsound": "bd22/generic/magin", "rackapexsound": "bd22/machinegun/rackback", "rackresetsound": "bd22/machinegun/rackfwd"},
        "body":      "#5",
        "capacity":  100,
        "magfamily": "bd_762",
        "parts": {
            # ITS TRIGGER MOVES and the shipped card never drove it: a slide of 0.59 along -X.
            "trigger": {"surfaces": ["#4"], "role": "trigger"},
            # WHAT RACKS HERE IS THE LAUNCHER, not the gun. #3 is the underslung
            # launcher's tube, sliding 9.50 forward; the M249's own bolt is not a
            # separate surface. Named for what it is, as Vanilla's machinegun card
            # names it, with the launcher's own trigger and latch beside it.
            # ITS MAGAZINE IS RECOVERED. It is welded into the receiver -- 415 of
            # #5's 11,996 vertices, in 31 separate islands -- and every island lying
            # wholly inside this box is exactly those 415, with none missing and
            # none extra. The box is the same one vanilla_check carries, because it
            # is the same donor mesh at the same rest frame.
            "magazine":        {"surfaces": ["#5"], "role": "feed", "subject": "magazine",
                                "carve": True, "take": "no",
                                "island": {"of": "#5", "verts": 415,
                                           # in this set's own space: frame 4, the
                                           # Ready frame, not the frame 10 the
                                           # Vanilla mesh was built at.
                                           "box": [[-13.300, -5.878, -13.269],
                                                   [-5.559, 4.987, -1.684]]}},
            # NOT AN ACTION (2026-10-02). It carried role = action, which is what
            # gives a gun its CYCLE verb -- so "racking" this machine gun slid the
            # UNDERSLUNG GRENADE LAUNCHER'S TUBE forward. The role also earned it
            # `detach = 0.95` from the emitter, so pulling the tube far enough took
            # it off the gun. Both faults have the one cause and both go with it.
            #
            # The M249's own bolt is not a separate surface, so there is nothing
            # here to rack; the card gives the tube an `open breech` verb instead,
            # as Vanilla's WM_MachineGun does with this same part map.
            "launchertube":    {"surfaces": ["#3"], "subject": "foregrip"},
            "launchertrigger": {"surfaces": ["#2"]},
            "launcherlatch":   {"surfaces": ["#0"]},
        },
        "fixed":     ["#1"],
        # IN THE CARD AND NOT HERE, because emit_card writes no verb blocks at all:
        #
        #   open breech   on launchertube, latched by launcherlatch, latchreturn spring.
        #                 What the tube is actually for. BD's own ReloadGrenade plays
        #                 GRLLO1 / insertshell / GRLLO2 (Machinegun.txt:222-236).
        #   swap magwell  on magazine, SynthSwap's own numbers. NOT optional and NOT
        #                 new: SynthesiseVerbs is all-or-nothing (card.zs:918), so the
        #                 open verb above stopped the magazine's swap being synthesised.
        #                 Declaring one verb means declaring them all.
        #
        # NOT CARDED: the grenade launcher itself (a `store gl`, a `load grenade` and a
        # `barrel launcher` on altfire, as Vanilla's WM_MachineGun has). A card has ONE
        # magfamily and this gun has already spent it on bd_762 -- unlike Vanilla's, this
        # machine gun has a carved magazine a hand swaps, where Vanilla's is reserve-fed
        # and a grenade is the only thing a hand ever brings it. Carding the grenade here
        # would stop the 7.62 magazine fitting. The grenade still fires off BD's AltFire.
        # ITS MAGAZINE IS NOT DECLARED: in the shipped mesh that part is an island
        # cut by hand inside this gun's body surface, and no box reproduces
        # the cut. The gun builds whole without it.
    },
    "minigun": {
        "class":     "BD_Minigun",
        # FIRES FROM THE RESERVE, as Brutal Doom does (owner, 2026-10-02).
        #
        # Without this the gun fires ONCE and stops, and the usual explanation --
        # "it has no magazine" -- is wrong. With no `store` and no `firesfrom`,
        # SynthesiseStores (card.zs:715-730) gives it a COUNTED detachable magazine at
        # the stated capacity plus a live chamber. The magazine is not absent, it is
        # UNREACHABLE: SynthesiseVerbs (card.zs:917-926) makes a SWAP only on a
        # `role = feed` part and a CYCLE only on `role = action`, and this gun carries
        # neither -- so nothing in the card can ever refill either store.
        #
        # Reserve is also what BD itself does: FlameCannon.dec and HellishMissile.dec
        # have no A_ReFire and simply spend from the ammo pool. Carving a real magazine
        # would need a magazine class, a MODELDEF prop per gun and a mesh for four of
        # the five -- none of which exist.
        "firesfrom": "reserve",
        "donor":     r"Models\Weapons\Hud\Minigun\minigun.md3",
        "modeldef":  "Modeldef.Minigun.def",
        "decorate":  "Minigun.txt",
        "actor":     "Minigun",
        "hand":      "main",
        "type":      "chaingun",
        "capacity":  200,
        "magfamily": "bd_762",
        "sounds":    {"spinupsound": "bd22/minigun/spinup", "spinsound": "bd22/minigun/spin", "spindownsound": "bd22/minigun/spindown"},
        "body":      "#1",
        "parts": {
            # ITS "MAGAZINE" WAS THE ROTOR. The shipped card drove #2 `Pipe` as a
            # feed; it hinges 106 degrees -- it is the spinning barrel cluster. A
            # minigun is belt fed and has no magazine at all, which RULINGS.txt now
            # says. Driven as barrels, like the chaingun's.
            "barrels": {"surfaces": ["#2"], "spin": "trigger", "spinrate": 20.0, "spinup": 14, "spindown": 25},
            "trigger": {"surfaces": ["#4"], "role": "trigger"},
            "forend": {"surfaces": ["#0"], "subject": "forend"},
        },
        "fixed":     ["#3", "#5"],
    },
    "plasma": {
        "class":     "BD_Plasma",
        "casing":    "none",   # a cell gun: no case
        # FIRES FROM THE MAGAZINE, not through a chamber (owner, 2026-10-02).
        #
        # This gun HAS a feed part, so SynthesiseVerbs gives it a SWAP and the magazine
        # can be changed -- but it has no `role = action` part, so it gets no CYCLE.
        # With firesfrom unstated the card defaults to firing through a CHAMBER
        # (card.zs:916-926), and nothing can ever refill that chamber: one shot per
        # magazine, which is not a plasma rifle.
        #
        # Saying `magazine` takes the chamber out of the path: a pull spends a round
        # straight from the magazine, which is how a gun with no bolt to work behaves.
        "firesfrom": "magazine",
        "donor":     r"Models\Weapons\Hud\Plasma_Gun\Plasma.md3",
        "modeldef":  "Modeldef.Plasma.def",
        "decorate":  "Plasma.txt",
        "actor":     "Plasma_Gun",
        "hand":      "main",
        "type":      "plasma",
        "capacity":  60,
        "magfamily": "bd_cell",
        "sounds":    {"magoutsound": "bd22/plasma/magout", "maginsound": "bd22/plasma/magin"},
        "body":      "#3",
        "parts": {
            "cell": {"surfaces": ["#1"], "role": "feed", "subject": "magazine", "carve": True, "take": "no"},
        },
        "fixed":     ["#2"],
        "hidden":    ["#0"],
    },
    "rpg": {
        "class":     "BD_RPG",
        "casing":    "none",   # rockets leave by the bore; nothing is thrown out
        # FIRES FROM THE MAGAZINE, not through a chamber (owner, 2026-10-02).
        #
        # This gun HAS a feed part, so SynthesiseVerbs gives it a SWAP and the magazine
        # can be changed -- but it has no `role = action` part, so it gets no CYCLE.
        # With firesfrom unstated the card defaults to firing through a CHAMBER
        # (card.zs:916-926), and nothing can ever refill that chamber: one shot per
        # magazine, which is not a plasma rifle.
        #
        # Saying `magazine` takes the chamber out of the path: a pull spends a round
        # straight from the magazine, which is how a gun with no bolt to work behaves.
        "firesfrom": "magazine",
        "donor":     r"Models\Weapons\Hud\RPG\RPG.md3",
        "modeldef":  "Modeldef.RPG.def",
        "decorate":  "RocketLauncher.txt",
        "actor":     "Rocket_Launcher",
        "hand":      "main",
        "type":      "launcher",
        # SIX, NOT ONE. BD's own RocketLauncher.txt states it twice: the magazine is
        # the RocketRounds ammo class at Inventory.MaxAmount 6 (line 395-401), and the
        # reload loop stops at A_JumpIfInventory("RocketRounds", 6, "NoNeedToReload")
        # (lines 264, 287). The drum has SEVEN chambers and the seventh is never
        # loaded, which is why the count and the chamber count differ -- see the
        # roundsurface lines on `part drum` in the card.
        "capacity":  6,
        "magfamily": "bd_rocket",
        "sounds":    {"magoutsound": "bd22/rpg/magout", "maginsound": "bd22/rpg/magin"},
        "body":      "#0",
        "parts": {
            # ITS TRIGGER MOVES and the shipped card never drove it: a slide of 1.39 along -X.
            "trigger": {"surfaces": ["#4"], "role": "trigger"},
            # NO ACTION. The shipped card drove #1 as one, and #1 travels 0.01
            # units -- it does not move. Nothing on this launcher is racked; it is
            # loaded through its drum.
            "drum": {"surfaces": ["#5"], "role": "feed", "subject": "magazine", "take": "no",
                     # SEVEN CHAMBERS: #6..#12 are the seven rockets. The drum
                     # indexes a seventh of a turn per rocket short of seven, and
                     # stays on the gun, so it is not carved.
                     "chambers": 7},
        },
        # #6..#12 ARE THE SEVEN ROCKETS and they are not merely fixed scenery any
        # more: six of them are `roundsurface` lines on the drum in the card, so the
        # drum shows its count, and the seventh is a hidden `part emptychamber`.
        "fixed":     ["#1", "#10", "#11", "#12", "#2", "#3", "#6", "#7", "#8", "#9"],
        # IN THE CARD AND NOT HERE. emit_card writes no index block, no roundsurface
        # lines and no muzzle load, so the drum's whole carding is hand-written:
        #
        #   store drum       counted, 6. Declared so the lines below can name it.
        #   part drum        dof slide (0, -0.944, 0.329) x 10.75, NO detach (there is
        #                    no loose drum mesh in this set, and feed + detach + no
        #                    magmodel is something coming off with nothing to draw).
        #   roundsurface x6  fixed2, fixed3, fixed4, fixed7, fixed8, fixed9 -- the
        #                    chambers IN FIRING ORDER, which had to be measured: the
        #                    emitter named them off a counter, so the names carry no
        #                    order. Sorted by clock angle about the drum's own axis.
        #   index            hinge -51.43 (a seventh of a turn) about +x through
        #                    3.636, -4.595, 2.353. The emitter MEASURED this turn and
        #                    wrote it as the drum's pull-off dof, which is why the
        #                    drum's reload was a 51-degree twist in place.
        #   part emptychamber  role = hidden on fixed10: the seventh chamber, never
        #                    loaded, as Vanilla's WM_RPG has it.
        #   load muzzle      rockets go in the front of the tube. Not generated because
        #                    emit_card places a load from set.py's `where` face, which
        #                    is under | left | right | breech -- there is no muzzle face.
        #
        # THE NUMBERS ARE VANILLA WM_RPG'S, and that is checked rather than assumed:
        # both cards draw a file called rpg_wm.md3 but the two files have 13 and 10
        # surfaces. Measured in THIS donor, the out axis over insert frames 30-33 is
        # (0, -0.9458, 0.3248) against Vanilla's quoted (0, -0.944, 0.329), the drum
        # centroid lands on Vanilla's index pivot x of 3.636, and the trigger slides
        # 1.386 here against 1.397 there. Same asset, exported twice.
    },
    "railgun": {
        "class":     "BD_Railgun",
        "casing":    "none",   # a rail: no case
        # FIRES FROM THE MAGAZINE, not through a chamber (owner, 2026-10-02).
        #
        # This gun HAS a feed part, so SynthesiseVerbs gives it a SWAP and the magazine
        # can be changed -- but it has no `role = action` part, so it gets no CYCLE.
        # With firesfrom unstated the card defaults to firing through a CHAMBER
        # (card.zs:916-926), and nothing can ever refill that chamber: one shot per
        # magazine, which is not a plasma rifle.
        #
        # Saying `magazine` takes the chamber out of the path: a pull spends a round
        # straight from the magazine, which is how a gun with no bolt to work behaves.
        "firesfrom": "magazine",
        "donor":     r"Models\Weapons\Hud\RailGun\RailGun.md3",
        "modeldef":  "Modeldef.Railgun.def",
        "decorate":  "Railgun.txt",
        "actor":     "RailGun",
        "hand":      "main",
        "type":      "plasma",
        "capacity":  1,
        "magfamily": "bd_rail",
        "sounds":    {"magoutsound": "bd22/railgun/magout", "maginsound": "bd22/railgun/magin"},
        "body":      "#2",
        "parts": {
            # ITS TRIGGER MOVES and the shipped card never drove it: a hinge of 22.85 degrees about +Y.
            "trigger": {"surfaces": ["#3"], "role": "trigger"},
            # NO ACTION EITHER. The shipped card drove #0, which is the Scope --
            # it and its glass drop 5.75 and 6.25 when the gun zooms. That is a
            # sight moving, not a handle being pulled, and #0 also fails to fit as
            # one rigid body (0.633 RMS), so it would need splitting before it
            # could be driven at all.
            "magazine": {"surfaces": ["#4"], "role": "feed", "subject": "magazine", "carve": True, "take": "no"},
        },
        "fixed":     ["#0"],
        "hidden":    ["#1"],
    },
    "rifle": {
        "class":     "BD_Rifle",
        "donor":     r"Models\Weapons\Hud\Rifle\Rifle.md3",
        "modeldef":  "Modeldef.Rifle.def",
        "decorate":  "Rifle.txt",
        "actor":     "Rifle",
        "hand":      "main",
        "type":      "rifle",
        "capacity":  30,
        "magfamily": "bd_762",
        "sounds":    {"magoutsound": "bd22/rifle/magout", "maginsound": "bd22/rifle/magin", "rackapexsound": "bd22/rifle/rackback", "rackresetsound": "bd22/rifle/rackfwd"},
        "body":      "#4",
        # ITS ACTION IS BOTH SURFACES, and the shipped card had this wrong. It
        # drove #1 alone -- 79 vertices the artist named `ejectport`, the dust
        # cover -- because that surface travels further (10.44) than the handle
        # does (7.12), and the old pipeline picked the action by travel. So racking
        # the rifle took hold of the cover. #0 `liikkuvat` is the handle; both are
        # named here and the measurement follows the larger, as Vanilla's own
        # rifle card does.
        "parts": {
            "charginghandle": {"surfaces": ["#0", "#1"], "role": "action", "subject": "slide"},
            "magazine": {"surfaces": ["#3"], "role": "feed", "subject": "magazine", "carve": True, "take": "no"},
        },
        "fixed":     ["#5"],
        "hidden":    ["#2"],
    },
    "unmaker": {
        "class":     "BD_Unmaker",
        "casing":    "none",   # a cell gun: no case
        # FIRES FROM THE MAGAZINE, not through a chamber (owner, 2026-10-02).
        #
        # This gun HAS a feed part, so SynthesiseVerbs gives it a SWAP and the magazine
        # can be changed -- but it has no `role = action` part, so it gets no CYCLE.
        # With firesfrom unstated the card defaults to firing through a CHAMBER
        # (card.zs:916-926), and nothing can ever refill that chamber: one shot per
        # magazine, which is not a plasma rifle.
        #
        # Saying `magazine` takes the chamber out of the path: a pull spends a round
        # straight from the magazine, which is how a gun with no bolt to work behaves.
        "firesfrom": "magazine",
        "donor":     r"Models\Weapons\Hud\Unmaker\Unmaker.md3",
        "modeldef":  "Modeldef.Unmaker.def",
        "decorate":  "Unmaker.txt",
        "actor":     "Unmaker",
        "hand":      "main",
        "type":      "bfg",
        "capacity":  60,
        "magfamily": "bd_rune",
        "sounds":    {"magoutsound": "bd22/generic/magout", "maginsound": "bd22/generic/magin"},
        "body":      "#0",
        "parts": {
            "skull": {"surfaces": ["#1", "#2"], "role": "feed", "subject": "magazine", "carve": True, "take": "no"},
        },
    },
}
