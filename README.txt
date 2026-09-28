WeaponForge - a weapon set in, a world-weapon pack out.

Requires Python 3.12 and numpy. Nothing else.

RUN a set:

    RUN_SET.bat <set>

    ...or drag a set folder from sets\ onto RUN_SET.bat.

It stops at the first failure and prints one line saying why.
Exit code 0 only when every stage passed.

RE-CHECK everything that has already passed:

    CHECK_ALL.bat

    Must stay green. If it is not, the last change broke a set.

WHAT YOU EDIT:

    sets\<set>\set.py      the only human-written file in a set.
                           Class names, capacities, sounds, and which
                           donor surface is which part. No scales,
                           offsets, axes, pivots or distances - those
                           are measured from the donor.

WHAT YOU READ:

    sets\<set>\proposals\  the tool's guesses at a part map, for you
                           to accept or correct in set.py.

WHAT YOU NEVER EDIT BY HAND:

    sets\<set>\out\        everything the tool builds.
    tests\                 accepted output, kept as the reference.

    If either is wrong, fix forge\ and run again.

AFTER A GREEN RUN, in game:

    logfile proof.txt
    wm_proof <prefix>
