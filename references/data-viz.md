# Designed plots — pick the chart per argument, don't default to bars

A weak data deck reaches for the same bar chart (or a number table) every slide. A strong one
**chooses the chart TYPE that fits each argument**, themes it to the deck, **highlights the one
thing that matters**, and pairs it with a one-line "so-what". This file is the repertoire + the
rules. (For raw data with an *obvious* single comparison, a plain bar/line is still right — this
is for when the relationship is richer.)

## Pick by argument
| The point you're making | Chart | Helper (`scripts/designed_charts.py`) |
|---|---|---|
| Part-to-whole + one headline number | **donut + centre KPI** | `donut_kpi(...)` |
| Before→after / a gap per category | **dumbbell** | `dumbbell(rows, ...)` |
| Rank/level change between **two** dates | **slope / bump** | `slope(series, ...)` |
| Two trends on different scales (A↑ while B↓) | **dual-axis line** | `dual_axis(x, left, right, ...)` |
| x vs y with a 3rd (size) dimension + fair value | **bubble + trend line** | `bubble_trend(points, ...)` |
| The "vital few" that drive a total | **Pareto** (bars + cumulative %) | `pareto(items, ...)` |
| Current state in numbers (3-6 metrics) | **KPI scorecards** (native) | `deckkit.scorecard(...)` ×N |
| Ranked / part list keyed to a chart | **leaderboard** (native) | `deckkit.leaderboard(rows)` |
| One hub, many dependents | **hub-and-spoke** | native (`box`+connectors); radial layout |
| A simple single comparison / one trend | **bar / line** | `matplotlib` (the existing path) |

The recipes render a themed PNG → place with `deckkit.picture(out, ..., fit="contain")`.

## The four rules every designed plot follows
1. **Single highlight (one-accent discipline).** Recolor only the ONE series/wedge/row that
   carries the point in the accent; drop everything else to a neutral grey. The recipes take a
   `highlight` index and do this; for a multi-series categorical chart where every series matters,
   skip the highlight. Never let a chart use >2 saturated hues unless it's genuinely categorical.
2. **Theme it to the deck.** Pass the deck's palette (`palette=ACCENTS`, or pull from a generated
   template with `palette_from_image`) and `dark=True` for a dark deck, so the chart looks built-in,
   not pasted. Charts render on a transparent background, so they sit on any slide fill.
3. **Carry a "so-what".** Split the slide ~**65% chart / ~35% narrative rail** and add a
   `deckkit.takeaway_rail(label, hero_stat, body)` — a small caps label, the one restated number,
   and a 2-3 line interpretation. A chart without a stated conclusion makes the audience guess.
4. **Label directly, don't rely on colour alone.** End-of-line value labels, a legend keyed by
   the SAME colours as a paired `leaderboard`, markers as well as hue — so it survives a projector
   and colour-blind viewers (the deck-wide accessibility rule).

## Native vs matplotlib
- **Default to the `designed_charts` (matplotlib) recipes** — they're robust, themable, and fast to
  author, and transparent PNGs blend into any deck.
- **Build a chart natively** (freeform lines/shapes via `deckkit`) only when you need *total* theme
  control (e.g. a glass/Memphis deck where even a themed matplotlib plot would clash) or for
  diagram-like "charts" (hub-and-spoke, a flow/Sankey, an annotated timeline) that are really
  layout. Keep them measure-then-place so they slot into a `content_band`.
- Either way: **whole chart, legible from the back, one message, one highlight, a takeaway.**

## Native data furniture (deckkit)
- `scorecard(slide, x,y,w,h, label, value, delta=, caption=, good_up=, glass_tint=)` — a KPI tile
  (big value + auto-coloured ▲/▼ delta). Lay out 3-6 with `columns()`/a 2×2 grid; pass
  `glass_tint=` on a dark deck to make them glass.
- `leaderboard(slide, x,y,w, rows=[(color,name,value[,sub])])` — ranked rows with a colour swatch
  that **keys back to a paired chart** (use the chart's colour list so legend ↔ chart stay in sync).
- `takeaway_rail(slide, x,y,w, label, hero, body)` — the narrative rail beside a chart.

## Example
```python
import designed_charts as dc, deckkit as dk
band = dk.content_band(s)                       # the safe region
dc.dumbbell("assets/gap.png", rows, palette=ACCENTS, highlight=1, a_label="2024", b_label="2026")
dk.picture(s, "assets/gap.png", band[0], band[1], band[2]*0.62, band[3], fit="contain")
dk.takeaway_rail(s, band[0]+band[2]*0.66, band[1]+0.3, band[2]*0.34,
                 "Key shift", "+5 dB", "Model B closes most of the gap by 2026 — the one to back.")
```

## When NOT to use this
Short status updates, qualitative talks, or a slide with a single obvious number (use a hero stat /
`scorecard`, not a chart). Reserve the richer roster for data/report/market/strategy decks that have
many distinct quantitative relationships to show.
