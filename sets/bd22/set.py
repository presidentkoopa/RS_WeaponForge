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
PARENT_MOD  = r"E:\DOOMWork\RS_VR_BD22\brutal22test6.pk3"
PACK        = r"E:\DOOMWork\RS_VR_BD22"
MODEL_PATH  = "models/bd22"
CVAR_PREFIX = "bd"

# Owner rulings on parent_audit findings; RUN_SET stops on any finding not listed.
PARENT_RULINGS = {
    "ammo:Clip->Clip2": "bridged in bridge_bd22.zs",
}

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
        "sounds":    {"magoutsound": "bd22/pistol/magout", "maginsound": "bd22/pistol/magin"},
        "body":      "#4",
        "parts": {
            "bolt2": {"surfaces": ["#1"], "role": "action", "subject": "slide"},
            "magazine": {"surfaces": ["#3"], "role": "feed", "subject": "magazine", "carve": True},
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
        "sounds":    {"magoutsound": "bd22/revolver/magout", "maginsound": "bd22/revolver/magin"},
        "body":      "#0",
        # NO MOVING PARTS, and its shipped card carried none either: nothing
        # on this gun is driven by hand.
        "parts":     {},
        "fixed":     ["#1", "#2", "#3", "#4"],
        "hidden":    ["#5", "#6", "#7", "#8", "#9"],
    },
    "shotgun": {
        "class":     "BD_Shotgun",
        "donor":     r"Models\Weapons\Hud\Shotgun\Shotgun.md3",
        "modeldef":  "Modeldef.Shotgun.def",
        "decorate":  "Shotgun.txt",
        "actor":     "Shot_Gun",
        "hand":      "main",
        "type":      "pump",
        "capacity":  8,
        "magfamily": "12ga",
        "sounds":    {"rackapexsound": "bd22/shotgun/rackback", "rackresetsound": "bd22/shotgun/rackfwd"},
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
            "magazine": {"surfaces": ["#10"], "role": "feed", "subject": "magazine", "carve": True},
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
        "body":      "#0",
        "parts": {
            "magazine": {"surfaces": ["#4"], "role": "feed", "subject": "magazine", "carve": True},
        },
        "fixed":     ["#1", "#2"],
        "hidden":    ["#3"],
    },
    "flamecannon": {
        "class":     "BD_FlameCannon",
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
        "donor":     r"Models\Weapons\Hud\HitlersBuzzsaw\HitlersBuzzsaw.md3",
        "modeldef":  "Modeldef.HitlersBuzzsaw.def",
        "decorate":  "Mp40.txt",
        "actor":     "HitlersBuzzsaw",
        "hand":      "main",
        "type":      "chaingun",
        # ITS BODY IS THE WHOLE DONOR SURFACE. The shipped mesh has a body
        # surface that is this one minus the island cut out of it, so it matches
        # no donor surface by count; the donor surface itself is the body.
        "body":      "#0",
        "capacity":  200,
        "magfamily": "bd_762",
        "parts": {
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
        "body":      "#0",
        # NO MOVING PARTS, and its shipped card carried none either: nothing
        # on this gun is driven by hand.
        "parts":     {},
        "fixed":     ["#1", "#2", "#3", "#4"],
    },
    "assaultshotgun": {
        "class":     "BD_AssaultShotgun",
        "donor":     r"Models\Weapons\Hud\AssaultShotgun\AssaultShotgun.md3",
        "modeldef":  "Modeldef.AssaultShotgun.def",
        "decorate":  "AssaultShotgun.txt",
        "actor":     "AssaultShotgun",
        "hand":      "main",
        "type":      "pump",
        "capacity":  8,
        "magfamily": "12ga",
        "sounds":    {"magoutsound": "bd22/asg/magout", "maginsound": "bd22/asg/magin", "rackapexsound": "bd22/asg/rackback", "rackresetsound": "bd22/asg/rackfwd"},
        "body":      "#3",
        "parts": {
            "bolt": {"surfaces": ["#2"], "role": "action", "subject": "slide"},
            "magazine": {"surfaces": ["#6"], "role": "feed", "subject": "magazine", "carve": True},
        },
        "fixed":     ["#1", "#4"],
        "hidden":    ["#0", "#5"],
    },
    "bfg": {
        "class":     "BD_BFG",
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
            "magazine": {"surfaces": ["#3"], "role": "feed", "subject": "magazine", "carve": True},
            "trigger": {"surfaces": ["#2"], "role": "trigger"},
        },
        "fixed":     ["#0"],
    },
    "flamethrower": {
        "class":     "BD_Flamethrower",
        "donor":     r"Models\Weapons\Hud\Flamethrower2\Flamethrower2.md3",
        "modeldef":  "Modeldef.Flamethrower2.def",
        "decorate":  "Flamethrower.txt",
        "actor":     "Flamethrower2",
        "hand":      "main",
        "type":      "flamethrower",
        # ITS BODY IS THE WHOLE DONOR SURFACE. The shipped mesh has a body
        # surface that is this one minus the island cut out of it, so it matches
        # no donor surface by count; the donor surface itself is the body.
        "body":      "#0",
        "capacity":  200,
        "magfamily": "bd_fuel",
        "parts": {
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
        "donor":     r"Models\Weapons\Hud\Machinegun\Machinegun.md3",
        "modeldef":  "Modeldef.Machinegun.def",
        "decorate":  "Machinegun.txt",
        "actor":     "Machinegun",
        "hand":      "main",
        "type":      "chaingun",
        # ITS BODY IS THE WHOLE DONOR SURFACE. The shipped mesh has a body
        # surface that is this one minus the island cut out of it, so it matches
        # no donor surface by count; the donor surface itself is the body.
        "body":      "#5",
        "capacity":  100,
        "magfamily": "bd_762",
        "parts": {
            "bolt4": {"surfaces": ["#3"], "role": "action", "subject": "slide"},
        },
        "fixed":     ["#0", "#1", "#2", "#4"],
        # ITS MAGAZINE IS NOT DECLARED: in the shipped mesh that part is an island
        # cut by hand inside this gun's body surface, and no box reproduces
        # the cut. The gun builds whole without it.
    },
    "minigun": {
        "class":     "BD_Minigun",
        "donor":     r"Models\Weapons\Hud\Minigun\minigun.md3",
        "modeldef":  "Modeldef.Minigun.def",
        "decorate":  "Minigun.txt",
        "actor":     "Minigun",
        "hand":      "main",
        "type":      "chaingun",
        "capacity":  200,
        "magfamily": "bd_762",
        "body":      "#1",
        "parts": {
            "magazine": {"surfaces": ["#2"], "role": "feed", "subject": "magazine", "carve": True},
            "forend": {"surfaces": ["#0"], "subject": "forend"},
        },
        "fixed":     ["#3", "#4", "#5"],
    },
    "plasma": {
        "class":     "BD_Plasma",
        "donor":     r"Models\Weapons\Hud\Plasma_Gun\Plasma.md3",
        "modeldef":  "Modeldef.Plasma.def",
        "decorate":  "Plasma.txt",
        "actor":     "Plasma_Gun",
        "hand":      "main",
        "type":      "plasma",
        "capacity":  60,
        "magfamily": "bd_cell",
        "body":      "#3",
        "parts": {
            "cell": {"surfaces": ["#1"], "role": "feed", "subject": "magazine", "carve": True},
        },
        "fixed":     ["#2"],
        "hidden":    ["#0"],
    },
    "rpg": {
        "class":     "BD_RPG",
        "donor":     r"Models\Weapons\Hud\RPG\RPG.md3",
        "modeldef":  "Modeldef.RPG.def",
        "decorate":  "RocketLauncher.txt",
        "actor":     "Rocket_Launcher",
        "hand":      "main",
        "type":      "launcher",
        "capacity":  1,
        "magfamily": "bd_rocket",
        "body":      "#0",
        "parts": {
            "bolt": {"surfaces": ["#1"], "role": "action", "subject": "slide"},
            "drum": {"surfaces": ["#5"], "role": "feed", "subject": "magazine", "carve": True},
        },
        "fixed":     ["#2", "#3", "#4", "#6", "#7", "#8", "#9", "#10", "#11", "#12"],
    },
    "railgun": {
        "class":     "BD_Railgun",
        "donor":     r"Models\Weapons\Hud\RailGun\RailGun.md3",
        "modeldef":  "Modeldef.Railgun.def",
        "decorate":  "Railgun.txt",
        "actor":     "RailGun",
        "hand":      "main",
        "type":      "plasma",
        "capacity":  1,
        "magfamily": "bd_rail",
        "body":      "#2",
        "parts": {
            "bolt": {"surfaces": ["#0"], "role": "action", "subject": "slide"},
            "magazine": {"surfaces": ["#4"], "role": "feed", "subject": "magazine", "carve": True},
        },
        "fixed":     ["#3"],
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
        "parts": {
            "bolt2": {"surfaces": ["#1"], "role": "action", "subject": "slide"},
            "magazine": {"surfaces": ["#3"], "role": "feed", "subject": "magazine", "carve": True},
        },
        "fixed":     ["#0", "#5"],
        "hidden":    ["#2"],
    },
    "unmaker": {
        "class":     "BD_Unmaker",
        "donor":     r"Models\Weapons\Hud\Unmaker\Unmaker.md3",
        "modeldef":  "Modeldef.Unmaker.def",
        "decorate":  "Unmaker.txt",
        "actor":     "Unmaker",
        "hand":      "main",
        "type":      "bfg",
        "capacity":  60,
        "magfamily": "bd_rune",
        "body":      "#0",
        "parts": {
            "skull": {"surfaces": ["#1", "#2"], "role": "feed", "subject": "magazine", "carve": True},
        },
    },
}
