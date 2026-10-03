#!/usr/bin/env python3
"""
palm_page_build.py -- put the geometry INSIDE the review page, so it can be published.

The last step of the palm-review pipeline:

    palm_render.py        meshes  ->  palmbench/geometry.json   (renders + cross-sections)
    palm_marks.py         adds the trigger and seeds the support point
    palm_page_build.py    page.html + geometry.json  ->  index.inline.html   (this)

WHY IT IS INLINED AND NOT FETCHED. A published artifact runs in a sandbox that refuses the
page's own fetch of a file published beside it, and the only thing it reports is "Failed to
fetch" -- no status, no console error, nothing naming the file. The page keeps a fetch as a
fallback for serving the same file from a local server, where it does work, but the published
copy carries its data in a <script type="application/json"> block.

The only sequence that can close that block early is `</`, which is escaped on the way in.
JSON has no other way to produce it.

    python forge/palm_page_build.py
    python forge/palm_page_build.py --page palmbench/page.html --out palmbench/index.inline.html
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANCHOR = '<script>\n"use strict";'


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=os.path.join(HERE, "palmbench", "page.html"))
    ap.add_argument("--geometry", default=os.path.join(HERE, "palmbench", "geometry.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "palmbench", "index.inline.html"))
    a = ap.parse_args(argv)

    for p in (a.page, a.geometry):
        if not os.path.isfile(p):
            print(f"missing: {p}", file=sys.stderr)
            return 2

    html = open(a.page, encoding="utf-8").read()
    if ANCHOR not in html:
        print("the page has no `<script>` + \"use strict\"; anchor to inline before",
              file=sys.stderr)
        return 2

    geo = open(a.geometry, encoding="utf-8").read().replace("</", "<\\u002f")
    block = '<script type="application/json" id="geo">' + geo + "</script>\n" + ANCHOR
    out = html.replace(ANCHOR, block, 1)

    # The page must end up with exactly two script elements: the data and the code. More means
    # the escape above missed something and the data block closed early, which renders as a
    # page that loads and then does nothing.
    if out.count("</script>") != 2:
        print(f"refusing to write: {out.count('</script>')} script tags, expected 2",
              file=sys.stderr)
        return 1

    open(a.out, "w", encoding="utf-8").write(out)
    mb = os.path.getsize(a.out) / 1048576
    print(f"{a.out}  {mb:.2f} MB")
    if mb > 16:
        print("  WARNING: a published artifact must be 16 MB or smaller", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
