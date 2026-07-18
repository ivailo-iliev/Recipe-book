#!/usr/bin/env python3
"""Print compact cmap diagnostics for the legacy source fonts."""

from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]

for filename in ("BUKURSV.TTF", "karina-cyrillic.ttf"):
    path = ROOT / filename
    print(f"\n=== {filename} ===")
    font = TTFont(
        path,
        lazy=False,
        checkChecksums=0,
        ignoreDecompileErrors=True,
        recalcBBoxes=False,
        recalcTimestamp=False,
    )

    print("glyph_count:", len(font.getGlyphOrder()))
    print("glyph_order:", " ".join(font.getGlyphOrder()))

    for index, table in enumerate(font["cmap"].tables):
        print(
            f"cmap[{index}] platform={table.platformID} encoding={table.platEncID} "
            f"format={table.format} language={table.language} entries={len(table.cmap)}"
        )
        entries = []
        for codepoint, glyph_name in sorted(table.cmap.items()):
            if codepoint <= 0x00FF or 0xF000 <= codepoint <= 0xF0FF or 0x0400 <= codepoint <= 0x052F:
                entries.append(f"{codepoint:04X}:{glyph_name}")
        print("entries:", " ".join(entries))

    font.close()
