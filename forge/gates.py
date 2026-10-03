#!/usr/bin/env python3
"""G1-G12: what DONE means for one gun, and a report per run.

CODER_PLAN step 59. The owner asked for "better" to be defined for WeaponForge, so this is
the definition: twelve gates, each one a question with a yes, a no, or an honest "not from
here".

THE THING THIS MUST NOT DO IS REPORT TWELVE GREENS WHEN IT CHECKED EIGHT.

Four of the twelve cannot be answered by a static tool -- a wireframe render has to be
LOOKED at, and a headset smoke test has to be worn. A report that quietly counted those as
passes would read exactly like a set that was finished, which is the same failure as a lint
rule that can never fire or a test harness that cannot fail. Both cost real time on
2026-10-02. So every gate returns one of:

    PASS      checked here, and it holds
    FAIL      checked here, and it does not
    NEEDS EYE not answerable offline, and the report says which human act would answer it

and the summary counts them separately. A set is DONE when there are no FAILs and the
NEEDS EYE list has been walked in a headset -- not when this tool is quiet.

Standard library only, like the rest of the forge.
"""
from __future__ import annotations

import html
import json
import os
import re

PASS, FAIL, EYE = "PASS", "FAIL", "NEEDS EYE"

# Each gate: id, one-line question, and how it is answered.
GATES = [
    ("G1",  "The card loads",              "the parser accepts it; a refusal takes the next gun with it"),
    ("G2",  "It fires more than once",     "a chamber gun with no way to chamber the next round fires once"),
    ("G3",  "Its rate is stated",          "firetics, and fullauto where the real gun is automatic"),
    ("G4",  "A hand can reload it",        "a magazine a verb can work, a mechanism, or a store to load"),
    ("G5",  "The palm is on the gun",      "distance from the palm point to the mesh SURFACE"),
    ("G6",  "The grip has an axis",        "rake, or a type whose default rake is right for this gun"),
    ("G7",  "The hand does not sink in",   "the palm is not deep inside the solid"),
    ("G8",  "The off hand has a place",    "supportat, on the mesh, for anything held two-handed"),
    ("G9",  "The reload moves the right way", "watched: does the magazine leave the way it should"),
    ("G10", "Brass is stated either way",  "casing yes with a port, or casing none said out loud"),
    ("G11", "It renders whole",            "looked at: one gun, no stray islands, no missing parts"),
    ("G12", "It survives a headset",       "worn: drawn, held, fired, reloaded without a fault"),
]
EYE_ONLY = {"G9", "G11", "G12"}


def _num3(txt):
    try:
        v = [float(x) for x in txt.replace(",", " ").split()]
        return v if len(v) == 3 else None
    except ValueError:
        return None


def evaluate(gun, card, mesh_probe=None):
    """{gate: (verdict, why)} for one gun.

    `card` is the parsed dict from set_gate.parse_cards (file, line, prop, roles, stores,
    verbs, mechanism, firesfrom, models). `mesh_probe(point)` returns the distance from a
    point to the nearest mesh TRIANGLE, or None when the mesh could not be read -- never a
    vertex distance, which reads far too far on a coarse gun and told the owner his own
    placements were worse than they were on 2026-10-03.
    """
    import set_gate as G
    out = {}

    # G1 -- the card parsed at all. If it is in this dict, the forge's reader took it;
    # whether the GAME's parser takes it is set_gate's business and is reported there.
    out["G1"] = (PASS, "read by the forge; the engine's own verdict is the boot log's")

    # G2 -- the fire-once rule, step 58.
    if G.fires_once(card):
        out["G2"] = (FAIL, "fires from the chamber, declares %s, and nothing chambers the next round"
                     % (", ".join(card["verbs"]) or "no verbs"))
    else:
        out["G2"] = (PASS, "chambers, or does not feed from the chamber")

    # G3/G4/G10 are card facts.
    out["G3"] = ((PASS, "stated") if card.get("firetics") else
                 (EYE, "firetics is not on the card -- it may be on the weapon sheet, which this does not read"))
    r = G.reloadable(card)
    out["G4"] = (PASS, r) if r else (
        (PASS, "fires from %s, so there is nothing to reload" % card["firesfrom"])
        if card["firesfrom"] in ("reserve", "none")
        else (FAIL, "no magazine a verb can work, no mechanism, no store to load"))
    cas = (card.get("casing") or "").lower()
    out["G10"] = ((PASS, "casing = %s" % cas) if cas else
                  (FAIL, "casing is not stated; unstated MEANS yes, so this gun throws brass whether or not it has a port"))

    # G5/G7/G8 need the mesh.
    palm = _num3(card.get("palm", "")) if card.get("palm") else None
    sup = _num3(card.get("supportat", "")) if card.get("supportat") else None
    if palm is None:
        out["G5"] = (FAIL, "no palm point")
        out["G7"] = (EYE, "no palm point to test")
    elif mesh_probe is None:
        out["G5"] = (EYE, "mesh not readable here")
        out["G7"] = (EYE, "mesh not readable here")
    else:
        d = mesh_probe(palm)
        out["G5"] = ((PASS, "%.2f units from the surface" % d) if d <= 4.0 else
                     (FAIL, "%.2f units from the nearest triangle -- off the gun" % d))
        # A palm sits a little INSIDE the skin: that is a hand holding something, not a fault.
        # Deep inside is a fault, and there is no offline way to tell deep from snug on every
        # shape, so this one asks rather than guesses.
        out["G7"] = (EYE, "palm is %.2f from the surface; whether that reads as held or sunk is a look" % d)
    if sup is None:
        out["G8"] = (EYE, "no supportat -- right for a one-handed gun, missing for anything else")
    elif mesh_probe is None:
        out["G8"] = (EYE, "mesh not readable here")
    else:
        d = mesh_probe(sup)
        out["G8"] = ((PASS, "%.2f units from the surface" % d) if d <= 4.0 else
                     (FAIL, "%.2f units from the nearest triangle -- off the gun" % d))

    out["G6"] = ((PASS, "rake stated") if card.get("rake") else
                 (EYE, "no rake; it takes its type's default, which is right for most guns and wrong for some"))

    for g in EYE_ONLY:
        if g not in out:
            out[g] = (EYE, dict((a, c) for a, b, c in GATES)[g])
    return out


def summarise(rows):
    n = dict.fromkeys((PASS, FAIL, EYE), 0)
    for _gun, gates in rows:
        for v, _why in gates.values():
            n[v] += 1
    return n


def write_report(set_id, rows, out_dir):
    """REPORT.html and REPORT.json beside the run's output."""
    tally = summarise(rows)
    data = {"set": set_id,
            "gates": [{"id": a, "question": b, "how": c} for a, b, c in GATES],
            "tally": tally,
            "guns": [{"gun": g, "gates": {k: {"verdict": v, "why": w} for k, (v, w) in gt.items()}}
                     for g, gt in rows]}
    with open(os.path.join(out_dir, "REPORT.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)

    cls = {PASS: "p", FAIL: "f", EYE: "e"}
    head = "".join("<th title='%s'>%s</th>" % (html.escape(q), g) for g, q, _ in GATES)
    body = []
    for gun, gates in rows:
        cells = []
        for g, _q, _h in GATES:
            v, why = gates.get(g, (EYE, "not evaluated"))
            cells.append("<td class='%s' title='%s'>%s</td>"
                         % (cls[v], html.escape(why), {PASS: "ok", FAIL: "FAIL", EYE: "eye"}[v]))
        bad = [("%s: %s" % (g, gates[g][1])) for g, _q, _h in GATES
               if gates.get(g, (EYE,))[0] == FAIL]
        body.append("<tr><th class='gun'>%s</th>%s</tr>" % (html.escape(gun), "".join(cells)))
        if bad:
            body.append("<tr class='why'><td colspan='%d'>%s</td></tr>"
                        % (len(GATES) + 1, html.escape(" / ".join(bad))))

    doc = """<!doctype html><meta charset="utf-8"><title>%s gates</title>
<style>
 body{background:#111317;color:#e8ecf2;font:15px/1.5 "Segoe UI",system-ui,sans-serif;margin:24px}
 h1{font-size:22px;margin:0 0 2px} .sub{color:#8b95a5;margin-bottom:18px}
 table{border-collapse:collapse} th,td{border:1px solid #2a303a;padding:5px 9px;text-align:center}
 th.gun{text-align:left;font-weight:600} td.p{color:#3fbf6f} td.f{background:#e2544a;color:#2b0705;font-weight:700}
 td.e{color:#c9a227} tr.why td{text-align:left;color:#e2544a;font-size:13px;background:#1a1e25}
 .key{margin-top:16px;color:#8b95a5}
</style>
<h1>%s &mdash; G1 to G12</h1>
<div class="sub">%d gun(s) &middot; <b style="color:#3fbf6f">%d pass</b> &middot;
 <b style="color:#e2544a">%d fail</b> &middot; <b style="color:#c9a227">%d need an eye</b></div>
<table><tr><th class="gun">gun</th>%s</tr>%s</table>
<p class="key"><b>eye</b> is not a pass. It is a question this tool cannot answer &mdash; a render to look
at or a headset to wear. A set is done when there are no fails AND the eye column has been walked.
Hover any cell for its reason.</p>
""" % (html.escape(set_id), html.escape(set_id), len(rows),
       tally[PASS], tally[FAIL], tally[EYE], head, "".join(body))
    p = os.path.join(out_dir, "REPORT.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(doc)
    return p, tally
