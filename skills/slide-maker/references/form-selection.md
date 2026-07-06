# Form selection — content shape → the candidate FORMS (generate a set, then pick)

The single content-indexed map for "what visual form should this slide take?" — used by the
**slide-design** agent (designs to it, Step 2), the **builder** (SKILL.md step 4), and the **critic** (judges form
fit) so all three resolve to one surface. Each row is a **candidate SET + a tie-breaker**, never a
single answer.

> **Design is choosing, not matching.** NEVER record the first matching form. For each content slide,
> generate the **2–3 forms the content could take**, then pick with the tie-breaker and record *why the
> winner beat the runner-up* (the planner's Form ledger). The reflex form — a rounded-card / panel grid
> — is the right answer for **parallel, unordered, equal-weight** items only; the moment the content has
> **order, magnitude, a relationship, time, or two axes**, a non-card form almost always says it better.

## Concept → visualization (the FIRST move — before the content-shape map)

**Reason from the concept's *shape* to a visual language, THEN pick the concrete form/component below.**
Before opening the content-shape map, read the idea's underlying shape and reach for its visual
metaphor. The **`slide-design` agent owns this move** (step 2 of `agents/slide-design.md`); the concrete
form / component is chosen in the map below (and `design-gallery.md`).

**The single authoritative dictionary is the Concept → Visualization decision table in
`references/design-intelligence-addendum.md` §3** — with the full **Use when / Avoid when / Common AI
failure** detail for every concept. The compact reminder below is a *pointer into it*, not a second
source: reach for the visual language here, then resolve the use / avoid / failure-mode call — and any
concept not listed below — in the addendum before picking the concrete form.

| Concept | Visual language | Concept | Visual language |
|---|---|---|---|
| **Flow** | pipeline / river / conveyor | **Decision** | decision-tree |
| **Journey** | timeline / road / metro | **Process** | assembly-line |
| **Growth** | mountain / rocket / curve | **Relationship** | network |
| **Loop** | flywheel / orbit | **Dependency** | sankey |
| **Comparison** | split-screen | **Scale** | stairs |
| **Hierarchy** | pyramid | **Prioritization** | quadrant |
| **Strategy** | compass | **Evolution** | timeline |
| **Ecosystem** | galaxy / network | **Risk** | heatmap |
| **System** | circuit / layer | **Performance** | dashboard |
| **Transformation** | morphing | **Progress** | progress-bar |

## By communicative intent

| The content is… | Candidate forms (deckkit, in rough preference order) | Tie-breaker |
|---|---|---|
| **A comparison** (A vs B; before→after) | `table`(highlight row) · `dumbbell` · `slope` · `before_after` · `change_stat` · `quadrant` | table for >2 dimensions; **dumbbell** for one before→after gap *per item*; slope for a 2-point rank change; change_stat for a single baseline→after; quadrant when **two axes** carry the point |
| **A process / sequence / steps** | `step_list` · `flow_chain` · `timeline` · `node`+`connector` · `repeat_row`(if N identical stages) | timeline if the steps are **dated**; flow_chain if there are **arrows/branches** (+ stroke & shape semantics, elbow for loops); step_list if linear & numbered |
| **Parts of a whole / composition** | `native_donut` · `segmented_bar` · `stat_row` · `leaderboard` | donut for 2–4 shares; **segmented_bar** for cumulative 100%; leaderboard for a *ranked* breakdown |
| **A relationship / structure / architecture** | `hub_spoke` · `node`+`connector` · `concentric_rings` · `quadrant` | hub_spoke for one centre + spokes; concentric_rings for **nested** layers; node+connector for a general graph (one `hub`) |
| **A trend over time** | `native_chart`(line) · `slope` · `native_dual_axis` · `native_pareto` | line for many points; **slope** for two points; dual-axis for two scales (A↑ vs B↓) |
| **A few standout numbers / KPIs** | `scorecard`(3–6 tiles) · `stat_row` · `big_numeral`(one hero) · `change_stat` · `meter_bar` | big_numeral when **one** number is the whole point; scorecard for 3–6; meter_bar for a single share/percentile |
| **A set of distinct attributes / features** | **first ask:** is there magnitude (`stat_row`) or two axes (`quadrant`) or a comparison (`table`)? → use those. Only if the items are **truly parallel, unordered, equal-weight** → `icon_card` row / `columns` cards | cards are the *considered* choice for parallel-equal items, **not** the default for anything list-shaped |
| **One idea / a claim / a quote** | `pull_quote` · `big_numeral`+caption · a whole figure + assertion title · `insight_banner` | pull_quote for a verbatim line; big_numeral for a single statistic; figure when the artifact *is* the point |
| **Dense reference / many fields** | `table` · `spec_card` · `wireframe_grid`+`spec_list` | table for rows×cols; spec_card for a mono key→value placard; wireframe for a UI/layout spec |
| **A concept that needs the real thing** | a **computed/generated domain artifact** (image-generation.md) · a **whole source figure** | compute/extract the real artifact (FFT, a real plot, a patch) — never a box-and-dot cartoon |
| **A principle / mechanism / experiment / definition you're EXPLAINING** (physics · chemistry · biology · engineering · econ · *any* subject — how/why it works, an apparatus/setup, a defined concept) | a **labelled schematic diagram ALONGSIDE a short text description** (forces · signal-path · reaction · apparatus · geometry · cause→effect) · a generated/computed domain artifact · `node`+`connector` · an annotated whole figure | **default to a diagram + text, not text-alone** — and **build the schematic CORRECTLY**: components / connections / geometry / reaction / apparatus must be **domain-accurate & faithful to the source** (a wrong or generic box-and-dot cartoon is worse than none). Schematic when spatial/causal/procedural; **extract/compute the real artifact** when it must look real (a specific molecule, a real plot); an equation (mathfont) when the law *is* the relation. Text-only for something a diagram could show is a miss. **HOW to build a physical/spatial schematic (force · ray · circuit · apparatus · vector · wave) → `references/schematic-diagrams.md` — matplotlib/domain-lib for precise/label-critical ones, or the image tool for complex/stylized/template-matched ones (labels overlaid native, geometry verified) + the fidelity gate;** the deckkit node/connector kit is for conceptual box-flow only. |
| **An algorithm / method / training-or-optimization procedure** (ANY field — ML, but also a derivation, optimizer, lab/comp protocol) | `algorithm_block` (numbered pseudocode — Input/Output, for/if, indentation) · `flow_chain` / `node`+`connector` (the data-flow/architecture) · `step_list` | **`algorithm_block`** when the *exact steps, loops, Input→Output* matter (a training loop, an optimizer, a derivation); a **flow/architecture diagram** when the *data path between modules* is the point; **often BOTH** — the block for precision + a small diagram for intuition. Don't bury a precise procedure in prose. |

**Cross-links:** pick the **chart type** in `data-viz.md` (editable-native vs raster); draw a
**science schematic** (force/ray/circuit/apparatus) per `schematic-diagrams.md`; reach for the
exact **component** in `design-gallery.md`; place safely with the `deckkit` helpers in SKILL.md step 4.

## How the slide-design agent uses this (the Form ledger)
For every **content** slide, the plan records one Form-ledger row — `slide | visual protagonist |
format-family (card / chart / diagram / quote / big-number / timeline / table / photo) | build?` — plus,
in the per-slide Layout cell, the winner **and** the alternative it beat: e.g. *"dumbbell — beats
bar+table because the per-item before→after gap IS the point; a bar hides the pairing."* The **diversity
gate** then runs against the ledger: if any one format-family exceeds **~40–50%** of the content slides,
the plan is **not ready** — rework the weakest into the form its content actually wants. (Taste, not a
quota: a genuinely card-shaped run is allowed *with a one-clause justification in the ledger* — the gate
is auditable, never silent.)
