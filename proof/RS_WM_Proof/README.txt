RS_WM_Proof -- does every gun actually work, in THIS load order?

Load it last. In the console:
  logfile proof.txt      (optional: saves the output)
  wm_proof               every carded gun
  wm_proof BD_           one set, by class prefix
  wm_why                 what is holding your trigger; then pull it a few times

PASS  card found, has a magazine, fires when full, its ammo can be picked up, its prop exists
WARN  fires from reserve or nothing with no magazine part -- fine if that is a ruling
FAIL  it will not work in play; the line under it says why

Nothing is given, taken or spawned. Printing only.
