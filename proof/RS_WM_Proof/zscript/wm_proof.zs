// ============================================================================
// RS_WM_Proof -- does every gun actually work? Asked in the game, not of the files.
//
// card_lint proves a card is WELL FORMED. This proves the gun WORKS in the load order you
// are actually playing: its card is found, it has something to reload, it can be loaded,
// and the ammo it draws on is ammo a player can pick up. Brutal Doom's guns passed every
// file check we had while their reserve was always zero -- this catches that in one line.
//
//   wm_proof            every carded gun that is loaded
//   wm_proof BD_        only guns whose class starts with BD_ (any prefix)
//   wm_why              what is holding YOUR trigger right now, then again on every pull
//                       for ten seconds (ReadyWeapon, weapon state, frozen, CanFire ...)
//
// Save the output with `logfile proof.txt` before running it.
//
// NOTHING IS CHANGED. The load test builds a throwaway ammo state from the card -- no
// actor is spawned, nothing is given, nothing is taken. wm_why only reads.
//
// Load it LAST, after RS_VR_Reload and every weapon set. Loaded alone it does nothing.
// ============================================================================

class WM_Proof : EventHandler
{
	private int whyUntil;
	private int whyLast;
	private int whyPlayer;

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Player < 0 || e.Player >= MAXPLAYERS || !playeringame[e.Player]) return;
		// Prints only. Another player's request prints on their machine, not this one.
		if (e.Player != consoleplayer) return;

		if (e.Name ~== "wm_proof" || e.Name.Left(9) ~== "wm_proof:")
		{
			String prefix = (e.Name.Length() > 9) ? e.Name.Mid(9) : "";
			RunProof(e.Player, prefix);
			return;
		}
		if (e.Name ~== "wm_why")
		{
			whyPlayer = e.Player;
			whyUntil = level.maptime + 350;
			Why("asked");
		}
	}

	// ---- wm_proof -------------------------------------------------------------

	private void RunProof(int pn, String prefix)
	{
		let sys = WM_System(EventHandler.Find("WM_System"));
		if (!sys)
		{
			Console.Printf("\cgWM PROOF: RS_VR_Reload is not loaded -- nothing to test.");
			return;
		}
		Console.Printf("\cf==== WM PROOF %s====", prefix == "" ? "" : ("(" .. prefix .. "*) "));

		int guns = 0, pass = 0, warn = 0, fail = 0;
		for (int i = 0; i < AllActorClasses.Size(); i++)
		{
			let cls = (Class<WM_Gun>)(AllActorClasses[i]);
			if (!cls) continue;
			String name = GetDefaultByType(cls).GetClassName();
			if (name ~== "WM_Gun" || name ~== "WM_ThrownGun") continue;
			if (prefix != "" && !(name.Left(prefix.Length()) ~== prefix)) continue;

			let card = sys.CardForWeapon(name);
			if (!card)
			{
				// A gun class with no card is normal for sets that are not carded yet; only
				// worth a line when a prefix says this is the set under test.
				if (prefix != "") { Console.Printf("\cg  FAIL %-22s no model card found", name); fail++; guns++; }
				continue;
			}
			guns++;
			int f = 0, w = 0;
			Array<String> notes;
			ProveGun(cls, card, notes, f, w);
			if (f > 0) { fail++; Console.Printf("\cg  FAIL %s", name); }
			else if (w > 0) { warn++; Console.Printf("\ck  WARN %s", name); }
			else { pass++; Console.Printf("\cd  PASS %s", name); }
			for (int n = 0; n < notes.Size(); n++) Console.Printf("         %s", notes[n]);
		}

		Console.Printf("\cf==== %d gun(s): %d pass, %d warn, %d fail ====", guns, pass, warn, fail);
		if (guns == 0)
			Console.Printf("\cg  No carded guns matched. Is the set's pk3 loaded, and its WMCARD lump in it?");
	}

	// One gun. Appends a line per finding; bumps f (fail) or w (warn).
	private void ProveGun(Class<WM_Gun> cls, WM_Card card, out Array<String> notes, out int f, out int w)
	{
		// 1. SOMETHING TO RELOAD. A reload set whose gun has no feed part cannot be reloaded,
		//    and nothing else in the pipeline asked. Firing from reserve or from nothing is a
		//    legitimate ruling (melee, tube, cylinder, no-reload guns) -- a warning, not a fail.
		bool hasFeed = card.FindRole("feed") != null;
		if (!hasFeed)
		{
			if (card.KeepsNoRounds())
			{
				notes.Push(String.Format("no magazine part -- fires from %s. Fine if that is a ruling.",
					card.firesFrom == WM_Card.FIRES_RESERVE ? "reserve" : "nothing"));
				w++;
			}
			else
			{
				notes.Push("NO MAGAZINE PART, but the card fires from a chamber/magazine: this gun can never be reloaded.");
				f++;
			}
		}

		// 2. THE AMMO IT DRAWS ON MUST BE AMMO A PLAYER CAN GET. A parent mod that `replaces` it
		//    (Brutal Doom: Clip -> Clip2) means every pickup gives something else and the reserve
		//    never rises. GetReplacement asks the same question the engine asks at spawn, set
		//    bridges included -- so a bridge that swaps the ammo back makes this pass.
		let def = GetDefaultByType(cls);
		Class<Ammo> ammoCls = null;
		if (def) ammoCls = def.AmmoType1;
		if (!ammoCls)
		{
			if (card.firesFrom != WM_Card.FIRES_NOTHING)
			{
				notes.Push("no Weapon.AmmoType1 -- its reserve falls back to Clip.");
				w++;
			}
		}
		else
		{
			let rep = Actor.GetReplacement(ammoCls);
			if (rep && rep != ammoCls)
			{
				notes.Push(String.Format("AMMO UNREACHABLE: %s spawns as %s in this load order -- pickups never refill this gun. Swap it back in the set bridge.",
					GetDefaultByType(ammoCls).GetClassName(), GetDefaultByType(rep).GetClassName()));
				f++;
			}
		}

		// 3. A FULL GUN FIRES. A throwaway ammo state built from the card exactly the way
		//    WM_Gun.EnsureAmmo builds one (Init fills every store), then asked the fire path's own
		//    question. If a full gun cannot fire, its card's stores are wrong. Nothing is spawned.
		let a = new("WM_Ammo");
		a.Init(card.capacity, card);
		a.firesFrom = card.firesFrom;
		bool loaded;
		if (card.KeepsNoRounds()) loaded = true;
		else if (card.FiresFromMagazine()) loaded = a.MagazineHolds(1);
		else loaded = a.CanFire();
		if (!loaded)
		{
			notes.Push(String.Format("CANNOT FIRE WHEN FULL: capacity %d, and a fully loaded copy still refuses the trigger. Check the card's stores.",
				card.capacity));
			f++;
		}

		// 4. THE THING YOU HOLD EXISTS.
		Class<Actor> propCls = (class<Actor>)(Object.FindClass(card.propClass, "Actor"));
		if (!propCls)
		{
			notes.Push(String.Format("PROP MISSING: the card names prop '%s' and no such class is loaded -- nothing will be drawn.", card.propClass));
			f++;
		}
	}

	// ---- wm_why ---------------------------------------------------------------

	override void WorldTick()
	{
		if (level.maptime > whyUntil) return;
		if (!playeringame[whyPlayer] || !players[whyPlayer].mo) return;
		let pl = players[whyPlayer].mo.player;
		bool down = (pl.cmd.buttons & (BT_ATTACK | BT_OFFHANDATTACK)) != 0;
		if (down && level.maptime - whyLast >= 17)
		{
			whyLast = level.maptime;
			Why("trigger");
		}
	}

	private static String Cls(Object o) { return o ? String.Format("%s", o.GetClassName()) : "none"; }

	private void Why(String why)
	{
		let pmo = players[whyPlayer].mo;
		if (!pmo) return;
		let pl = pmo.player;
		Console.Printf("\cf[wm_why %s] pawn %s  ready %s  pending %s  offhand %s",
			why, Cls(pmo), Cls(pl.ReadyWeapon), Cls(pl.PendingWeapon), Cls(pl.OffhandWeapon));
		Console.Printf("  weapon ready=%d  buttons=%x  frozen=%d  totallyfrozen=%d",
			(pl.WeaponState & WF_WEAPONREADY) ? 1 : 0, pl.cmd.buttons,
			(pl.cheats & CF_FROZEN) ? 1 : 0, (pl.cheats & CF_TOTALLYFROZEN) ? 1 : 0);

		let psp = pl.FindPSprite(PSP_WEAPON);
		if (psp && psp.CurState && pl.ReadyWeapon)
		{
			let wp = pl.ReadyWeapon;
			String where = "other";
			if (Actor.InStateSequence(psp.CurState, wp.FindState("Ready")))         where = "Ready";
			else if (Actor.InStateSequence(psp.CurState, wp.FindState("Fire")))     where = "Fire";
			else if (Actor.InStateSequence(psp.CurState, wp.FindState("Select")))   where = "Select";
			else if (Actor.InStateSequence(psp.CurState, wp.FindState("Deselect"))) where = "Deselect";
			Console.Printf("  weapon state: %s", where);
		}

		let sys = WM_System(EventHandler.Find("WM_System"));
		for (int h = 0; h < 2; h++)
		{
			let gun = sys ? sys.GunInHand(whyPlayer, h) : null;
			if (!gun) { Console.Printf("  hand %d: no carded gun in hand", h); continue; }
			let ammo = gun.wmAmmo;   // read, never create: this runs on one machine only
			let def = GetDefaultByType(gun.GetClass());
			Class<Ammo> ac = null;
			if (def) ac = def.AmmoType1;
			let inv = ac ? pmo.FindInventory(ac) : null;
			Console.Printf("  hand %d: %s  canfire=%d  fireblocked=%d  reserve %s=%d",
				h, Cls(gun), sys.CanFire(whyPlayer, h, 1, 1, gun) ? 1 : 0,
				(ammo && ammo.fireBlocked) ? 1 : 0,
				ac ? String.Format("%s", GetDefaultByType(ac).GetClassName()) : "none", inv ? inv.Amount : 0);
		}
	}
}
