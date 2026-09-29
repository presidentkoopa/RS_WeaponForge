# sets/vanilla_check/set.py -- THE TEST INPUT, not a set anyone plays.
#
# The twelve guns RS_VR_Weapons already ships, mapped back onto their Brutal
# Doom donors, so the tool can be asked to rebuild a set that is known to work
# and be compared against it. Step 11 of the WeaponForge Build Guide: "This is
# the only place copying Vanilla is allowed; it is the test input."
#
# HOW THE PART MAPS WERE FOUND, since the guide forbids guessing one: each
# shipped _wm mesh's surfaces were matched to donor surfaces by vertex count
# and, where a count repeated, by centroid once the donor frame was recentred.
# The frame itself was solved the same way -- the donor frame whose recentred
# mesh matches the shipped one. Nothing here was read off a picture or inferred
# from a surface's name.
#
# The roles and subjects are the shipped cards' own, since the point is to
# reproduce those cards.

SET_ID      = "vanilla_check"
PREFIX      = "WM_"
DONOR_ROOT  = r"D:\SteamLibrary\steamapps\Common\DooM VR\__Games\BrutalDoom\_BD_1.01_WeaponModels"
PARENT_MOD  = ""
PACK        = r"E:\DOOMWork\WeaponForge\sets\vanilla_check\out"
MODEL_PATH  = "models/vanilla_check"
CVAR_PREFIX = "vc"

PARENT_RULINGS = {}

GUNS = {
    # ---------------------------------------------------------------- shotgun
    # body 3877 = #3 (2776) + #0 (665) + #4 (436); #1 is the loading shell.
    "assaultshotgun": {
        "class":     "WM_AssaultShotgun",
        "donor":     r"Models\Weapons\Hud\AssaultShotgun\AssaultShotgun.md3",
        "modeldef":  "Modeldef.AssaultShotgun.def",
        "decorate":  "AssaultShotgun.txt",
        "hand":      "main",
        "type":      "shotgun",
        "body":      "#3",
        "fixed":     ["#0", "#4"],
        "hidden":    ["#1"],
        "parts": {
            "charginghandle": {"surfaces": ["#2"], "role": "action", "subject": "slide"},
            "trigger":        {"surfaces": ["#5"], "role": "trigger"},
            "magazine":       {"surfaces": ["#6"], "role": "feed", "subject": "magazine",
                               "carve": True},
        },
    },

    # -------------------------------------------------------------------- smg
    # #0 and #1 are both called Sights; #1 is the 17,897-vertex body.
    "smg": {
        "class":     "WM_SMG",
        "donor":     r"Models\Weapons\Hud\BrutalSMG\BrutalSMG.md3",
        "modeldef":  "Modeldef.SMG.def",
        "decorate":  "SubMachinegun.txt",
        "hand":      "main",
        "type":      "smg",
        "body":      "#1",
        "parts": {
            "charginghandle": {"surfaces": ["#0"], "role": "action", "subject": "slide"},
            "trigger":        {"surfaces": ["#2"], "role": "trigger"},
            "magazine":       {"surfaces": ["#3"], "role": "feed", "subject": "magazine",
                               "carve": True},
        },
    },

    # ------------------------------------------------------------------ rifle
    # The shipped mesh keeps all 32 frames and its prop reads FrameIndex 3.
    # The charging handle is two surfaces: the moving block and the eject port.
    "rifle": {
        "class":     "WM_Rifle",
        "donor":     r"Models\Weapons\Hud\Rifle\Rifle.md3",
        "modeldef":  "Modeldef.Rifle.def",
        "decorate":  "Rifle.txt",
        "hand":      "main",
        "type":      "rifle",
        "body":      "#4",
        "fixed":     ["#5"],
        "parts": {
            "charginghandle": {"surfaces": ["#0", "#1"], "role": "action", "subject": "slide"},
            "trigger":        {"surfaces": ["#2"], "role": "trigger"},
            "magazine":       {"surfaces": ["#3"], "role": "feed", "subject": "magazine",
                               "carve": True},
        },
    },

    # --------------------------------------------------------------- launcher
    # Parts only in the acceptance. #6..#12 are the seven chambered rockets;
    # four of them have 234 vertices each, so which one the shipped card calls
    # rocket7 cannot be told apart by count. They are all hidden and none
    # carries a measurement, so nothing turns on it -- but it is why they are
    # listed as a block rather than named individually.
    "rpg": {
        "class":     "WM_RPG",
        "donor":     r"Models\Weapons\Hud\RPG\RPG.md3",
        "modeldef":  "Modeldef.RPG.def",
        "decorate":  "RocketLauncher.txt",
        "hand":      "main",
        "type":      "launcher",
        "body":      "#0",
        "fixed":     ["#1", "#2", "#3"],
        "hidden":    ["#6", "#7", "#8", "#9", "#10", "#11", "#12"],
        "parts": {
            "trigger": {"surfaces": ["#4"], "role": "trigger"},
            "drum":    {"surfaces": ["#5"], "role": "feed", "subject": "magazine",
                        "carve": True},
        },
    },

    # ------------------------------------------------------------ plasma rifle
    # body 7471 = #3 (7467) + #0 (4).
    "plasmarifle": {
        "class":     "WM_PlasmaRifle",
        "donor":     r"Models\Weapons\Hud\Plasma_Gun\Plasma.md3",
        "modeldef":  "Modeldef.Plasma.def",
        "decorate":  "Plasma.txt",
        "hand":      "main",
        "type":      "plasma",
        "body":      "#3",
        "fixed":     ["#0"],
        "parts": {
            "cell":    {"surfaces": ["#1"], "role": "feed", "subject": "magazine",
                        "carve": True},
            "trigger": {"surfaces": ["#2"], "role": "trigger"},
        },
    },

    # -------------------------------------------------------------------- bfg
    "bfgheavy": {
        "class":     "WM_BFGHeavy",
        "donor":     r"Models\Weapons\Hud\BFG\BFG.md3",
        "modeldef":  "Modeldef.BFG.def",
        "decorate":  "BFG.txt",
        "actor":     "BIG_FUCKING_GUN",
        "hand":      "main",
        "type":      "bfg",
        "body":      "#0",
        "parts": {
            "trigger": {"surfaces": ["#1"], "role": "trigger"},
        },
    },

    # ------------------------------------------------------------- machinegun
    # NOT AN R1 GUN. The shipped mesh is donor frame 10, not the Ready frame 4;
    # frame 4 is 26.44 units out. Solved from the reference mesh itself, and it
    # agrees with the REMA audit corrections.
    # Its magazine is an ISLAND inside the receiver: #5 is 11,996 vertices, of
    # which 415 are the magazine.
    "machinegun": {
        "class":      "WM_MachineGun",
        "donor":      r"Models\Weapons\Hud\Machinegun\Machinegun.md3",
        "modeldef":   "Modeldef.Machinegun.def",
        "decorate":   "Machinegun.txt",
        "hand":       "main",
        "type":       "chaingun",
        "rest_frame": 10,
        "body":       "#5",
        "fixed":      ["#1"],
        "parts": {
            "trigger":         {"surfaces": ["#4"], "role": "trigger"},
            "launchertube":    {"surfaces": ["#3"], "subject": "foregrip"},
            "launchertrigger": {"surfaces": ["#2"]},
            "launcherlatch":   {"surfaces": ["#0"]},
            "magazine":        {"surfaces": ["#5"], "role": "feed", "subject": "magazine",
                                "carve": True,
                                # 415 of the receiver's 11,996 vertices, in 31
                                # separate islands. Every island wholly inside
                                # this box is exactly those 415.
                                "island": {"of": "#5", "verts": 415,
                                           "box": [[-13.234, -5.828, -13.219],
                                                   [-5.594, 4.938, -1.750]]}},
        },
    },

    # ----------------------------------------------------------------- minigun
    # body 3209 = #1 (2336) + #5 (700) + #0 (111) + #3 (62). Its largest surface
    # is #2, the spinning barrels, which is exactly the trap the guide warns of.
    "chaingun": {
        "class":     "WM_Chaingun",
        "donor":     r"Models\Weapons\Hud\Minigun\minigun.md3",
        "modeldef":  "Modeldef.Minigun.def",
        "decorate":  "Minigun.txt",
        "hand":      "main",
        "type":      "chaingun",
        "body":      "#1",
        "fixed":     ["#0", "#3", "#5"],
        "parts": {
            "trigger": {"surfaces": ["#4"], "role": "trigger"},
            "barrels":  {"surfaces": ["#2"]},
        },
    },

    # ----------------------------------------------------------------- railgun
    # The scope and its glass slide when the gun zooms; the card does not drive
    # them, so they move with the body. #0 also fits badly (0.633 RMS) and would
    # need an island split before it could be driven.
    "railgun": {
        "class":     "WM_Railgun",
        "donor":     r"Models\Weapons\Hud\RailGun\RailGun.md3",
        "modeldef":  "Modeldef.Railgun.def",
        "decorate":  "Railgun.txt",
        "hand":      "main",
        "type":      "railgun",
        "body":      "#2",
        "fixed":     ["#0", "#1"],
        "parts": {
            "trigger":  {"surfaces": ["#3"], "role": "trigger"},
            "magazine": {"surfaces": ["#4"], "role": "feed", "subject": "magazine",
                         "carve": True},
        },
    },

    # ----------------------------------------------------------------- unmaker
    # All three surfaces are called mp_salvocannon. The card's one part, skull,
    # is the flap and the lever together.
    "unmaker": {
        "class":     "WM_Unmaker",
        "donor":     r"Models\Weapons\Hud\Unmaker\Unmaker.md3",
        "modeldef":  "Modeldef.Unmaker.def",
        "decorate":  "Unmaker.txt",
        "hand":      "main",
        "type":      "unmaker",
        "body":      "#0",
        "parts": {
            "skull": {"surfaces": ["#1", "#2"], "role": "feed", "subject": "magazine",
                      "carve": True},
        },
    },

    # ------------------------------------------------------------ flamethrower
    # Its canister is an ISLAND inside the body: #0 is 5,966 vertices, of which
    # 1,306 are the canister.
    "flamethrower": {
        "class":     "WM_Flamethrower",
        "donor":     r"Models\Weapons\Hud\Flamethrower2\Flamethrower2.md3",
        "modeldef":  "Modeldef.Flamethrower2.def",
        "decorate":  "Flamethrower.txt",
        "hand":      "main",
        "type":      "flamethrower",
        "body":      "#0",
        "hidden":    ["#2"],
        "parts": {
            "trigger":  {"surfaces": ["#1"], "role": "trigger"},
            # THE CANISTER IS NOT DECLARED YET. It is 1,306 vertices inside the
            # body's own surface, and unlike the machinegun's magazine it cannot
            # be isolated by a box: every island wholly inside the canister's own
            # bounding box comes to 1,787 vertices, because the canister sits
            # within the body's region rather than beside it. The shipped mesh
            # was split by hand ("split into body / trigger / canister /
            # pilotflame ... by the reload lane", MODELDEF.txt:293). Until there
            # is a rule that reproduces those 1,306, this part stays out rather
            # than being carved by a number that happens to look close.
        },
    },

    # ----------------------------------------------------------------- grenade
    # Parts only. #1 is three vertices and is not in the shipped mesh at all,
    # which is why its 2647 vertices do not match the donor's 2650.
    "grenade": {
        "class":     "RS_VRGrenade",
        "donor":     r"Models\Weapons\Hud\Grenade\nade.md3",
        "modeldef":  "Modeldef.Grenade.def",
        "decorate":  "Grenades.txt",
        "actor":     "HandGrenades",
        "hand":      "main",
        "type":      "grenade",
        "body":      "#0",
        "fixed":     ["#4"],
        "hidden":    ["#1"],
        "parts": {
            "pin":   {"surfaces": ["#2"], "subject": "pin"},
            "lever": {"surfaces": ["#3"], "subject": "lever"},
        },
    },
}
