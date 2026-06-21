#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""presets — named DESIGN-LANGUAGE presets: one switch sets a coherent palette + fonts + surface
treatment + image-prompt style, so a deck's look is consistent from the first slide.

These are *starting languages*, not straitjackets — the model still tunes to the brand/purpose and
the user's references always win. Apply one like:

    from presets import preset
    p = preset("glassmorphism")
    deckkit.FONT = p["font"]; INK = p["ink"]; ACCENTS = p["accents"]; BG = p["bg"]
    # build glass cards on a BG-filled slide lit by deckkit.glow(...), per p["surface"]

`image_prompt` is the prefix to feed the generated-template image route (references/
generated-template.md) so generated plates match the chosen language. Pair with the Style library
in references/generated-template.md and the per-purpose guidance in references/design-by-purpose.md.
"""
from pptx.dml.color import RGBColor
def C(h): return RGBColor.from_string(h)

PRESETS = {
    "glassmorphism": {
        "mood": "premium dark UI / tech — depth, light, frosted glass",
        "bg": C("0A0E27"), "ink": C("F2F5FC"), "muted": C("AEB7CC"),
        "accents": [C("5B8DEF"), C("3DDDFC"), C("A26BFA"), C("FB7185"), C("4ADE80")],
        "font": "Arial", "display": "Arial", "mono": "Consolas",
        "surface": "glass_card (tint+sheen+rim) on a BG-filled slide lit by 1-2 glow()s; KPI tiles "
                   "use scorecard(glass_tint=); white headline keyword in the accent.",
        "image_prompt": "dark atmospheric gradient background, deep navy to violet, soft neon color "
                        "glows and subtle bokeh, premium tech mood, no text, calm zone for a title",
        "when": "launches, product/tech talks, dashboards, design-forward decks. NEEDS a dark base.",
    },
    "swiss": {
        "mood": "International Typographic Style — grid, restraint, one red",
        "bg": C("FFFFFF"), "ink": C("111111"), "muted": C("777777"),
        "accents": [C("E2231A")], "font": "Arial", "display": "Arial", "mono": "Consolas",
        "surface": "strict flush-left columns(), hairline rules, big type-scale ratio, generous "
                   "whitespace; spend the ONE red on the single focal item (accent_one); ghost "
                   "numerals for enumerated grids.",
        "image_prompt": "minimal swiss graphic, faint grid / graph-paper texture, a single red disc, "
                        "lots of white space, no text",
        "when": "research, design, editorial, defense, any minimal/typographic register.",
    },
    "editorial_paper": {
        "mood": "luxury magazine — warm paper, serif, gold, big photography",
        "bg": C("FAF6EE"), "ink": C("1C1A17"), "muted": C("8A8275"),
        "accents": [C("B58A2E"), C("CBB46A")], "font": "Arial", "display": "Georgia", "mono": "Consolas",
        "surface": "editorial_header (caps eyebrow + serif title + hairline); full-bleed photos under "
                   "scrim_overlay; big italic Georgia numerals (big_numeral); stat_row for figures; "
                   "photos carry all saturation, chrome stays neutral.",
        "image_prompt": "warm, refined editorial photography (architecture / interiors / lifestyle), "
                        "soft natural light, magazine quality, no text",
        "when": "brand, portfolio, award, culture/lifestyle, showcase — tone over data density.",
    },
    "editorial_report": {
        "mood": "serious dark briefing — FT/Bloomberg gravitas, one-red discipline",
        "bg": C("0E0E12"), "ink": C("ECECEF"), "muted": C("8C8C97"),
        "accents": [C("E0392B"), C("D9A441")], "font": "Arial", "display": "Georgia", "mono": "Consolas",
        "surface": "serif display headlines + caps kicker over a hairline; a designed chart per slide "
                   "(designed_charts) with single-highlight + takeaway_rail; per-slide source line; "
                   "roman-numeral section dividers; atmospheric orb image ONLY on dividers.",
        "image_prompt": "a single abstract glowing orb / eclipse on near-black, restrained, mood-shifted "
                        "per chapter, no text — for section dividers only",
        "when": "market/landscape reports, investor/strategy briefings, thought-leadership.",
    },
    "risograph": {
        "mood": "indie print zine — 2-color riso, halftone, hard offset shadows",
        "bg": C("F3ECD9"), "ink": C("1B2A4A"), "muted": C("6B7280"),
        "accents": [C("FF4D8D"), C("F5B301"), C("1B2A4A")], "font": "Arial", "display": "Arial Black",
        "mono": "Consolas",
        "surface": "offset_shadow 'sticker' cards/numbers/headlines (hard, not soft); mono chrome "
                   "(eyebrows/footers/page-markers); full-bleed duotone halftone illustrations.",
        "image_prompt": "two-color risograph halftone print, navy + fluorescent pink on cream paper, "
                        "grain and slight misregistration, bold flat illustration, no text",
        "when": "culture, marketing, teaching, launch — audiences that reward personality.",
    },
    "memphis": {
        "mood": "80s-90s New Wave — bold, playful, chaotic-geometric",
        "bg": C("FCF2D8"), "ink": C("1A1A17"), "muted": C("9A9384"),
        "accents": [C("F76302"), C("0548C5"), C("E2342B"), C("1B7A3D"), C("F6BE1A")],
        "font": "Arial", "display": "Arial Black", "mono": "Consolas",
        "surface": "cream bg; rounded cards with colored header bands (auto-contrast label); dark "
                   "emphasis bands; scattered Memphis motifs (dots/zigzags/triangles) as margin accents.",
        "image_prompt": "Memphis / New Wave 80s-90s flat illustration, bold black outlines, squiggles "
                        "zigzags dots triangles, vivid colors on cream, no text, calm title zone",
        "when": "events, festivals, launches, culture decks wanting energy.",
    },
}


def preset(name):
    """Return a COPY of the named preset dict (palette as RGBColor, fonts, surface + image-prompt
    guidance). Raises KeyError on an unknown name — see names()."""
    if name not in PRESETS:
        raise KeyError(f"unknown preset '{name}'; choose from {list(PRESETS)}")
    p = PRESETS[name]
    out = dict(p)
    out["accents"] = list(p["accents"])
    return out


def names():
    return list(PRESETS)
