# Parent mod audit: brutal22test6.pk3

**4 must-fix, 5 to check, 3 for information.**

## What the set has to do

### [FAIL] The mod replaces Doom's AMMO

```
Our guns draw on Doom's ammo. With this mod loaded, pickups give ITS ammo and the reserve stays at zero: guns that fire from reserve click, nothing reloads.
  Do: in the set bridge's Configure(), when the parent is loaded:
      Swap("AmmoSuply", "Backpack");
      Swap("AmmoCell", "Cell");
      Swap("AmmoCellPack", "CellPack");
      Swap("Clip2", "Clip");
      Swap("EasyClip2", "Clip");
      Swap("ClipBox2", "ClipBox");
      Swap("EasyAmmoBox", "ClipBox");
      Swap("RealismAmmoBox", "ClipBox");
      Swap("AmmoRocket", "RocketAmmo");
      Swap("AmmoRocketBox", "RocketBox");
      Swap("AmmoRocketBoxEZ", "RocketBox");
      Swap("AmmoShell", "Shell");
      Swap("AmmoShellBox", "ShellBox");
      Swap("AmmoShellBoxEZ", "ShellBox");
  Also check its monster drops (CustomInventory drop items) and its start classes: every start class must give Doom ammo, not the mod's.
```

### [FAIL] The set's player class can never be picked (KEYCONF clearplayerclasses)

```
The New Game row is deleted before the menu is built. The set must be INJECTED:
  * a companion Players pk3: the mod's own player files, start items pointed at our guns and Doom ammo;
  * a companion Slots pk3: a KEYCONF with a NEW weaponsection name putting our guns on 1-0;
  * the bridge's SetClass() returns "" while the parent is loaded.
  NEVER: `replaces` on our gun classes (ZScript cannot replace DECORATE -- the pack silently fails to load), or a timer that rebuilds weapon slots (buzzes the controller every tick).
```

### [INFO] The mod replaces Doom's weapons

```
Its guns stand in for these Doom roles -- the bridge's Swap table should cover each:
      Fist           -> Melee_Attacks
      Chainsaw       -> ChainsawSpawnerReplacer
      Pistol         -> PistolSpawnerReplacer
      Shotgun        -> ShotgunSpawnerReplacer
      SuperShotgun   -> SSGSpawnerReplacer
      Chaingun       -> ChaingunSpawnerReplacer
      RocketLauncher -> RLSpawnerReplacer
      PlasmaRifle    -> PlasmagunReplacer
      BFG9000        -> BFGReplacer
```

### [INFO] Its actors are DECORATE

```
Our ZScript gun classes can NOT say `replaces` on any of them. Use the bridge (CheckReplacement).
```

### [FAIL] ACS: SetWeapon (16 place(s))

```
switches the held weapon -- takes the player's hand off our gun.
      src/Inputs.acs:51  setweapon(lastwep[playernumber()]);
      src/Inputs.acs:57  {setweapon("ClassicPistol");}
      src/Inputs.acs:58  Else{setweapon("BrutalPistol");}
      src/Inputs.acs:371  SetWeapon("AmmoDroper");
      src/Inputs.acs:611  SetWeapon("Melee_Attacks");
      src/Inputs.acs:839  SetWeapon(shieldWep);
      src/Inputs.acs:861  SetWeapon(lastwep[playernumber()]);
      src/Inputs.acs:900  SetWeapon(lastwep[playernumber()]);
      src/Inputs.acs:944  SetWeapon("ExecutionWeapon");
      src/Inputs.acs:956  SetWeapon(lastwep[playernumber()]);
      src/Mantling.acs:36  SetWeapon("LedgeGrab");
      src/Mantling.acs:42  SetWeapon("LedgeGrab");
      ... and 4 more
  Decide per feature: disable it for our guns, or make our guns survive it. Test each in the headset with a diagnostic that prints ReadyWeapon.
```

### [WARN] ACS: PROP_INSTANTWEAPONSWITCH (6 place(s))

```
forces instant weapon switches.
      src/Inputs.acs:610  SetPlayerproperty(0, 1, PROP_INSTANTWEAPONSWITCH );
      src/Inputs.acs:614  SetPlayerproperty(0, 0, PROP_INSTANTWEAPONSWITCH );
      src/Inputs.acs:938  SetPlayerProperty(0, 1, PROP_INSTANTWEAPONSWITCH);
      src/Inputs.acs:950  SetPlayerProperty(0, 0, PROP_INSTANTWEAPONSWITCH);
      src/Mantling.acs:20  SetPlayerProperty(0, 1, PROP_INSTANTWEAPONSWITCH);
      src/Mantling.acs:60  SetPlayerProperty(0, 0, PROP_INSTANTWEAPONSWITCH);
  Decide per feature: disable it for our guns, or make our guns survive it. Test each in the headset with a diagnostic that prints ReadyWeapon.
```

### [FAIL] ACS: PROP_TOTALLYFROZEN (4 place(s))

```
freezes the player completely -- no firing.
      src/Inputs.acs:939  SetPlayerProperty(0, 1, PROP_TOTALLYFROZEN);
      src/Inputs.acs:951  SetPlayerProperty(0, 0, PROP_TOTALLYFROZEN);
      src/Mantling.acs:21  SetPlayerProperty(0, 1, PROP_TOTALLYFROZEN);
      src/Mantling.acs:61  SetPlayerProperty(0, 0, PROP_TOTALLYFROZEN);
  Decide per feature: disable it for our guns, or make our guns survive it. Test each in the headset with a diagnostic that prints ReadyWeapon.
```

### [WARN] ACS: TakeInventory(current weapon) (3 place(s))

```
removes the weapon in hand.
      src/Mantling.acs:28  if (!CheckInventory("RevenantLauncherSelected"))TakeInventory(weapon, 1);
      src/WeapSelect.acs:34  TakeInventory(currWpn, 1);
      src/WeapSelect.acs:61  TakeInventory(wpnToTake, 1);
  Decide per feature: disable it for our guns, or make our guns survive it. Test each in the headset with a diagnostic that prints ReadyWeapon.
```

### [WARN] ACS reads the player's buttons every tic

```
Check each against what the VR controllers send. A button the mod turns into a kick, a reload token or a weapon switch will fire under our guns too:
      BT_ALTATTACK       src/Inputs.acs script "CheckAttackButtons"
      BT_ATTACK          src/Inputs.acs script "CheckAttackButtons"
      BT_JUMP            src/VEHICLECONTROL.acs script "BDGeneralInput"
      BT_RELOAD          src/Inputs.acs script "CheckWeaponAction"
      BT_SPEED           src/Inputs.acs script "CheckSprint"
      BT_USE             src/Inputs.acs script "BD_UseInput", src/VEHICLECONTROL.acs script "BDGeneralInput"
      BT_USER1           src/Inputs.acs script "CheckWeaponAction"
      BT_USER2           src/Inputs.acs script "CheckWeaponAction"
      BT_USER3           src/Inputs.acs script "CheckWeaponAction"
      BT_USER4           src/Inputs.acs script "CheckWeaponAction"
      BT_ZOOM            src/Inputs.acs script "CheckWeaponAction"
```

### [INFO] 14 ACS source file(s) in archive folders skipped

```
Folders named archive/old/unused are assumed not compiled. If the mod DOES compile them, re-run after moving them:
      src/src_archive/AmmoDropHandler.acs
      src/src_archive/COMMANDS.acs
      src/src_archive/CVARS.acs
      src/src_archive/CommonFunc.acs
      src/src_archive/FLight.acs
      src/src_archive/HeadShot.acs
      src/src_archive/IDDQDSTUFF.acs
      src/src_archive/LedgeGrab.acs
      src/src_archive/OneLiners (old).acs
      src/src_archive/SLAUGHTERCHECK.acs
```

### [WARN] Compiled ACS with no source

```
These cannot be audited -- anything above may also be hiding here:
      acs/BD_Hash.o
      acs/acs_archive/DoxStuff.o
      acs/acs_archive/NAZICHECK.o
      acs/acs_archive/PAINEFFECT.o
      acs/acs_archive/REALISM.o
      acs/acs_archive/SCREENEFFECTS.o
      acs/acs_archive/SPLASHES.o
```

### [WARN] The mod has its own ZScript spawn/replacement hooks

```
They may race the set bridge for the same spawns (handler order decides):
      PlayerEntered        zscript/DamageHandler.zc:28
      WorldThingSpawned    zscript/DamageHandler.zc:40
```

## Findings

### Doom classes it replaces

- `Clip` -> `Clip2`  (actors/MISC/Ammo.dec:1)
- `Clipbox` -> `ClipBox2`  (actors/MISC/Ammo.dec:159)
- `RocketAmmo` -> `AmmoRocket`  (actors/MISC/Ammo.dec:230)
- `RocketBox` -> `AmmoRocketBox`  (actors/MISC/Ammo.dec:331)
- `Cell` -> `AmmoCell`  (actors/MISC/Ammo.dec:412)
- `CellPack` -> `AmmoCellPack`  (actors/MISC/Ammo.dec:440)
- `Shell` -> `AmmoShell`  (actors/MISC/Ammo.dec:463)
- `SHellBox` -> `AmmoShellBox`  (actors/MISC/Ammo.dec:504)
- `DoomPlayer` -> `Doomer`  (actors/PlayerClasses/23Player.dec:2)
- `DoomPlayer` -> `Doomer`  (actors/PlayerClasses/Player.dec:2)
- `Fist` -> `Melee_Attacks`  (actors/Weapons/Melee.dec:1)
- `Backpack` -> `AmmoSuply`  (actors/Weapons/WeaponSpawners.dec:22)
- `Chainsaw` -> `ChainsawSpawnerReplacer`  (actors/Weapons/WeaponSpawners.dec:181)
- `Pistol` -> `PistolSpawnerReplacer`  (actors/Weapons/WeaponSpawners.dec:222)
- `Shotgun` -> `ShotgunSpawnerReplacer`  (actors/Weapons/WeaponSpawners.dec:256)
- `SuperShotgun` -> `SSGSpawnerReplacer`  (actors/Weapons/WeaponSpawners.dec:285)
- `Chaingun` -> `ChaingunSpawnerReplacer`  (actors/Weapons/WeaponSpawners.dec:320)
- `RocketLauncher` -> `RLSpawnerReplacer`  (actors/Weapons/WeaponSpawners.dec:361)
- `PLasmaRifle` -> `PlasmagunReplacer`  (actors/Weapons/WeaponSpawners.dec:410)
- `BFG9000` -> `BFGReplacer`  (actors/Weapons/WeaponSpawners.dec:444)

Plus 144 other replacement(s) (monsters, decorations, effects).

### Player classes

- KEYCONF `clearplayerclasses`  (KEYCONF.txt:1)
- KEYCONF `addplayerclass Doomer2`  (KEYCONF.txt:2)
- KEYCONF `addplayerclass BDoomer`  (KEYCONF.txt:3)
- KEYCONF `addplayerclass Doomer3`  (KEYCONF.txt:4)
- KEYCONF `addplayerclass TacticalDoomer`  (KEYCONF.txt:5)
- KEYCONF `addplayerclass Purist`  (KEYCONF.txt:6)

Start items, per player class:

- **BDoomer**: Rifle, Clip2 x30, Melee_Attacks, IsPlayer, RevolverAmmo x6, BDPistolAmmo x16, BDDualPistolAmmo x32, BDSMGAmmo x41, BDDualSMGAmmo x82, MP40Ammo x32, DualMP40Ammo x64, ShotgunAmmo x10, AssaultShotgunAmmo x20, SSGAmmo x2, RifleAmmo x31, DoubleRifleAmmo x62, xm21Ammo x11, GLAmmo, RocketRounds x6, RailgunAmmo x50, PlasmaAmmo x50, DoublePlasmaAmmo x100, HandGrenades, GrenadeAmmo, NeverSelectedPistol, NeverSelectedSMG, NeverSelectedMP40, NeverSelectedRevolver, NeverSelectedShotgun, NeverSelectedASG
- **Doomer**: NormalWeaponStarter, Melee_Attacks, Clip x60, ShotgunAmmo x8, AssaultShotgunAmmo x20, PlasmaAmmo x50, DoublePlasmaAmmo x50, SSGAmmo x2, RocketRounds x6, RailgunAmmo x50, IsPlayer, HandGrenades, JustStartedGame
- **Doomer2**: BrutalPistol, Clip1 x45, Melee_Attacks, IsPlayer, RevolverAmmo x6, BDPistolAmmo x16, BDDualPistolAmmo x32, BDSMGAmmo x41, BDDualSMGAmmo x82, MP40Ammo x32, DualMP40Ammo x64, ShotgunAmmo x10, AssaultShotgunAmmo x20, SSGAmmo x2, RifleAmmo x31, DoubleRifleAmmo x62, xm21Ammo x11, GLAmmo, RocketRounds x6, RailgunAmmo x50, PlasmaAmmo x50, DoublePlasmaAmmo x100, HandGrenades, GrenadeAmmo, NeverSelectedPistol, NeverSelectedSMG, NeverSelectedMP40, NeverSelectedRevolver, NeverSelectedShotgun, NeverSelectedASG
- **Doomer3**: Melee_Attacks, IsPlayer, RevolverAmmo x6, BDPistolAmmo x16, BDDualPistolAmmo x32, BDSMGAmmo x41, BDDualSMGAmmo x82, MP40Ammo x32, DualMP40Ammo x64, ShotgunAmmo x10, AssaultShotgunAmmo x20, SSGAmmo x2, RifleAmmo x31, DoubleRifleAmmo x62, xm21Ammo x11, GLAmmo, RocketRounds x6, RailgunAmmo x50, PlasmaAmmo x50, DoublePlasmaAmmo x100, HandGrenades, GrenadeAmmo, NeverSelectedPistol, NeverSelectedSMG, NeverSelectedMP40, NeverSelectedRevolver, NeverSelectedShotgun, NeverSelectedASG, NeverSelectedMinigun, NeverSelectedRifle
- **Purist**: NoReloading, BrutalPistol, Clip1 x45, Melee_Attacks, RevolverAmmo x6, BDPistolAmmo x16, BDDualPistolAmmo x32, BDSMGAmmo x41, BDDualSMGAmmo x82, MP40Ammo x32, DualMP40Ammo x64, ShotgunAmmo x10, AssaultShotgunAmmo x20, SSGAmmo x2, RifleAmmo x31, DoubleRifleAmmo x62, xm21Ammo x11, GLAmmo, RocketRounds x6, RailgunAmmo x50, PlasmaAmmo x50, DoublePlasmaAmmo x100, GrenadeAmmo, SSGLoaded, GLLoaded, IsPlayer, IsPlayingAsPurist, AmmoDroper, IsNOTTacticalClass, NoFatality
- **TacticalDoomer**: Rifle, BrutalPistol, Melee_Attacks, Clip1 x15, Clip2 x30, IsPlayer, IsTacticalClass, JustStartedGame, NoAutoReload, RevolverAmmo x6, BDPistolAmmo x16, BDDualPistolAmmo x32, BDSMGAmmo x41, BDDualSMGAmmo x82, MP40Ammo x32, DualMP40Ammo x64, ShotgunAmmo x10, AssaultShotgunAmmo x20, SSGAmmo x2, RifleAmmo x31, DoubleRifleAmmo x62, xm21Ammo x11, GLAmmo, RocketRounds x6, RailgunAmmo x50, PlasmaAmmo x50, DoublePlasmaAmmo x100, HandGrenades, GrenadeAmmo, NeverSelectedPistol

### Weapon slots

- `weaponsection "Brutal_Doom"`
- `setslot 1 DSweap BrutalAxe Chain_Saw Melee_Attacks`
- `setslot 2 BrutalPistol DualPistols PuristPistol BrutalSMG DualSMG PuristSMG MP40 DualMP40 PuristMP40 Revolver PuristRevolver`
- `setslot 3 Shot_Gun PuristShot_Gun AssaultShotgun PuristAssaultShotgun SSG PuristSSG`
- `setslot 4 Sniper PuristSniper Rifle DualRifles PuristRifle MiniGun PuristMiniGun MG42 PuristMG42`
- `setslot 5 IncendiaryLauncher PuristIncendiaryLauncher GrenadeLauncher PuristGrenadeLauncher Rocket_Launcher PuristRocket_Launcher Devastator PuristDevastator`
- `setslot 6 Plasma_Gun DUalPlasmaRifles PuristPlasma_Gun RailGun PuristRailGun`
- `setslot 7 NukeLauncher PuristNukeLauncher BFG10k PuristBFG10k BIG_FUCKING_GUN PuristBIG_FUCKING_GUN`
- `setslot 8 HellishMissileLauncher PuristHellishMissileLauncher Unmaker PuristUnmaker`
- `setslot 9 FlameCannon DualFlameCannon PuristFlameCannon Flamethrower2 PuristFlamethrower2`
- `setslot 0 HandGrenades PuristHandGrenades`

### Its weapons (3)

| class | ammo | file |
|---|---|---|
| ExecutionWeapon | - | actors/ExecutionsWeap.dec:1 |
| LedgeGrab | - | actors/LedgeGrab.dec:17 |
| RepairTool | - | actors/VEHICLES/Repairs.dec:1 |

### Event handlers it registers

- `"ZC_TMapHack", "Script_DamageMult"`  (MAPINFO.txt:3)
