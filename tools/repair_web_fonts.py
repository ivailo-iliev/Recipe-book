#!/usr/bin/env python3
"""Repair legacy TrueType fonts and generate Safari-compatible WOFF2 files."""

from __future__ import annotations

import re
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

ROOT = Path(__file__).resolve().parents[1]

FONT_CONFIGS = (
    {
        "source": ROOT / "BUKURSV.TTF",
        "output": ROOT / "bulgarian-kursiv.woff2",
        "family": "Bulgarian Kursiv",
        "subfamily": "Italic",
        "full_name": "Bulgarian Kursiv Italic",
        "postscript_name": "BulgarianKursiv-Italic",
        "italic": True,
    },
    {
        "source": ROOT / "karina-cyrillic.ttf",
        "output": ROOT / "karina-cyrillic.woff2",
        "family": "Karina Cyrillic",
        "subfamily": "Regular",
        "full_name": "Karina Cyrillic Regular",
        "postscript_name": "KarinaCyrillic-Regular",
        "italic": False,
    },
)


def build_name_table(config: dict[str, object]):
    table = newTable("name")
    table.names = []

    family = str(config["family"])
    subfamily = str(config["subfamily"])
    full_name = str(config["full_name"])
    postscript_name = str(config["postscript_name"])

    names = {
        0: "Regenerated for standards-compliant web use",
        1: family,
        2: subfamily,
        3: f"{family};1.000;{postscript_name}",
        4: full_name,
        5: "Version 1.000",
        6: postscript_name,
        16: family,
        17: subfamily,
    }

    for name_id, value in names.items():
        table.setName(value, name_id, 3, 1, 0x0409)
        table.setName(value, name_id, 1, 0, 0)

    return table


def rebuild_unicode_cmap(font: TTFont) -> None:
    """Convert the fonts' legacy Windows-1251 byte map to real Unicode."""
    legacy_map: dict[int, str] = {}

    for table in font["cmap"].tables:
        for codepoint, glyph_name in table.cmap.items():
            if 0 <= codepoint <= 0xFF:
                legacy_map.setdefault(codepoint, glyph_name)

    if not legacy_map:
        raise RuntimeError("The source font does not contain a legacy byte cmap")

    # Preserve ASCII directly. Decode every upper byte through Windows-1251,
    # which is how these 1990s fonts stored their Cyrillic outlines.
    unicode_map = {
        codepoint: glyph_name
        for codepoint, glyph_name in legacy_map.items()
        if codepoint < 0x80
    }

    for byte_value, glyph_name in legacy_map.items():
        if byte_value < 0x80:
            continue

        try:
            character = bytes([byte_value]).decode("cp1251")
        except UnicodeDecodeError:
            continue

        unicode_map[ord(character)] = glyph_name

    cmap = newTable("cmap")
    cmap.tableVersion = 0
    cmap.tables = []

    # Unicode BMP plus Windows Unicode BMP. Supplying both makes CoreText,
    # WebKit, and other browser font stacks choose a standards-based cmap.
    for platform_id, encoding_id in ((0, 3), (3, 1)):
        subtable = CmapSubtable.newSubtable(4)
        subtable.platformID = platform_id
        subtable.platEncID = encoding_id
        subtable.language = 0
        subtable.cmap = dict(sorted(unicode_map.items()))
        cmap.tables.append(subtable)

    font["cmap"] = cmap


def repair_font(config: dict[str, object]) -> None:
    source = Path(config["source"])
    output = Path(config["output"])
    italic = bool(config["italic"])

    if not source.exists():
        raise FileNotFoundError(f"Missing source font: {source}")

    font = TTFont(
        source,
        lazy=False,
        checkChecksums=0,
        recalcBBoxes=False,
        recalcTimestamp=False,
        ignoreDecompileErrors=True,
    )

    rebuild_unicode_cmap(font)
    font["name"] = build_name_table(config)

    for tag in ("DSIG", "LTSH", "VDMX", "hdmx"):
        if tag in font:
            del font[tag]

    if "OS/2" in font:
        if italic:
            font["OS/2"].fsSelection |= 1
            font["OS/2"].fsSelection &= ~(1 << 6)
        else:
            font["OS/2"].fsSelection &= ~1
            font["OS/2"].fsSelection |= 1 << 6

    if "head" in font:
        if italic:
            font["head"].macStyle |= 1 << 1
        else:
            font["head"].macStyle &= ~(1 << 1)

    if italic and "post" in font and font["post"].italicAngle == 0:
        font["post"].italicAngle = -12

    options = Options()
    options.hinting = False
    options.recalc_bounds = True
    options.recalc_timestamp = False
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 16, 17]
    options.name_legacy = True
    options.name_languages = [0x0409]
    options.layout_features = ["*"]
    options.notdef_glyph = True
    options.notdef_outline = True
    options.recommended_glyphs = True

    subsetter = Subsetter(options=options)
    subsetter.populate(glyphs=font.getGlyphOrder())
    subsetter.subset(font)

    font.flavor = "woff2"
    font.save(output, reorderTables=True)
    font.close()

    with TTFont(output, checkChecksums=2, lazy=False) as repaired:
        required_tables = {"cmap", "glyf", "head", "hhea", "hmtx", "maxp", "name"}
        missing = sorted(required_tables.difference(repaired.keys()))
        if missing:
            raise RuntimeError(f"{output.name} is missing required tables: {missing}")

        cmap = repaired.getBestCmap() or {}
        required_text = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЬЮЯабвгдежзийклмнопрстуфхцчшщъьюя"
        missing_chars = [char for char in required_text if ord(char) not in cmap]
        if missing_chars:
            raise RuntimeError(
                f"{output.name} is missing Bulgarian glyph mappings: {''.join(missing_chars)}"
            )

    print(f"Created and validated {output.relative_to(ROOT)}")


def update_html() -> None:
    path = ROOT / "index.html"
    html = path.read_text(encoding="utf-8")

    replacements = {
        'src: url("BUKURSV.TTF") format("truetype");': (
            'src: url("bulgarian-kursiv.woff2") format("woff2");\n'
            "      font-weight: 400;\n"
            "      font-style: italic;"
        ),
        'src: url("karina-cyrillic.ttf") format("truetype");': (
            'src: url("karina-cyrillic.woff2") format("woff2");\n'
            "      font-weight: 400;\n"
            "      font-style: normal;"
        ),
    }

    for old, new in replacements.items():
        if old not in html:
            # The script is intentionally idempotent after the first conversion.
            if new.split("\n", 1)[0] in html:
                continue
            raise RuntimeError(f"Expected CSS declaration not found: {old}")
        html = html.replace(old, new, 1)

    if "font-style: italic;" not in re.search(
        r'\.bulgarian-kursiv\s*\{[^}]*\}', html, flags=re.DOTALL
    ).group(0):
        html = re.sub(
            r'(\.bulgarian-kursiv\s*\{\s*font-family:\s*"Bulgarian Kursiv",\s*Georgia,\s*serif;)(\s*\})',
            r"\1\n      font-style: italic;\2",
            html,
            count=1,
        )

    path.write_text(html, encoding="utf-8")
    print("Updated index.html to use repaired WOFF2 files")


def main() -> None:
    for config in FONT_CONFIGS:
        repair_font(config)
    update_html()


if __name__ == "__main__":
    main()
