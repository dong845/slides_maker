#!/usr/bin/env python3
"""extract_pdf — pull a figure OUT of a source PDF (paper / report) as a clean PNG.

The skill's first rule of figures is *use the source's own figure, whole* (step 4) — but
a figure trapped in a PDF can't be placed until it's a PNG. This gets it out, three ways,
in order of how often you want them:

1. render_page  — rasterise a WHOLE page to high-DPI PNG. The most reliable: it captures
   the figure exactly as it appears (vector + text + raster composited), so a multi-panel
   figure, axis labels, and a colour bar all come through. Then crop/place it in the build.
2. crop_region  — rasterise just a rectangle of a page (a single figure on a busy page),
   so you don't carry the surrounding body text. Give the rectangle in page POINTS
   (72/inch, origin top-left) or as fractions of the page with frac=True.
3. extract_images — dump the page's EMBEDDED raster images at native resolution. Highest
   quality for a single photo/bitmap figure, but a vector chart or a multi-image panel can
   come out fragmented or empty — fall back to render_page/crop_region when it does.

Why rasterise rather than always extract: a paper figure is usually vector + text, not one
bitmap; rendering the page is what reproduces what the reader actually sees. Use a high DPI
(>=300) so the placed figure stays crisp when it fills a slide.

PREFERRED — auto-detect & crop figures straight from the paper (no manual coordinates,
no asking the user for originals). It anchors on captions ("Figure N" / "Fig. N" / "Table N"),
grows into the adjacent graphics bounded by body text + neighbouring captions, then snaps to
content. This is the *primary* path; the manual page/crop commands below are the fallback.
    python extract_pdf.py figures paper.pdf            # list every detected figure + checks
    python extract_pdf.py figures paper.pdf 4          # just page 4
    python extract_pdf.py figure  paper.pdf 2 fig.png  # render detected figure #2 (auto-trimmed)
    python extract_pdf.py autofig paper.pdf figs/      # render ALL detected figures to figs/
`figures` prints each box with cov= (graphics coverage), bodyov= (body-text overlap) and a
"⚠ CHECK" flag when a crop looks suspect (low coverage, body/foreign-caption bleed) — ALWAYS
view a rendered crop before using it, and for a flagged one fall back to the manual loop.

Quick start (manual fallback):
    python extract_pdf.py info paper.pdf                      # page count + sizes
    python extract_pdf.py page paper.pdf 4 fig.png --dpi 300  # page 4 (1-based) -> PNG
    python extract_pdf.py crop paper.pdf 4 fig.png 60 90 540 360
    python extract_pdf.py crop paper.pdf 4 fig.png 0.1 0.12 0.95 0.55 --frac
    python extract_pdf.py images paper.pdf 4 figdir/          # embedded images -> figdir/

To find a manual crop box: render the page once, open the PNG, read off the figure's pixel
box with `crop_helper.py grid`, divide by the render scale (dpi/72) to get points — or use
--frac and eyeball fractions. Importable: from extract_pdf import find_figures, render_figure.
"""
import sys
import os
import fitz   # PyMuPDF


def _open(pdf):
    doc = fitz.open(pdf)
    if doc.needs_pass:
        raise SystemExit("PDF is password-protected — can't read it.")
    return doc


def info(pdf):
    """Print page count and per-page size in points and inches — so you can pick a page
    and reason about crop coordinates."""
    doc = _open(pdf)
    print(f"{pdf}: {doc.page_count} pages")
    for i, page in enumerate(doc, start=1):
        r = page.rect
        print(f"  p{i}: {r.width:.0f} x {r.height:.0f} pt  "
              f"({r.width/72:.2f} x {r.height/72:.2f} in)"
              f"  images={len(page.get_images())}")
    doc.close()


def render_page(pdf, page_no, out, dpi=300):
    """Rasterise a whole page (1-based) to a PNG at `dpi`. Returns the output path.
    This is the default, most reliable extractor — what the reader sees, composited."""
    doc = _open(pdf)
    page = doc[page_no - 1]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    pix.save(out)
    doc.close()
    print(f"wrote {out}  ({pix.width}x{pix.height}px @ {dpi}dpi)")
    return out


def crop_region(pdf, page_no, out, x0, y0, x1, y1, dpi=300, frac=False):
    """Rasterise a rectangle of a page (1-based) to PNG. Coordinates in page POINTS
    (origin top-left), or as fractions 0..1 of the page when frac=True. Use this to lift a
    single figure off a page that also has body text."""
    doc = _open(pdf)
    page = doc[page_no - 1]
    r = page.rect
    if frac:
        x0, y0, x1, y1 = x0 * r.width, y0 * r.height, x1 * r.width, y1 * r.height
    clip = fitz.Rect(x0, y0, x1, y1)
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
    pix.save(out)
    doc.close()
    print(f"wrote {out}  ({pix.width}x{pix.height}px, clip {clip})")
    return out


def extract_images(pdf, page_no, out_dir, min_px=120):
    """Dump the page's embedded raster images (native resolution) to out_dir, skipping
    anything smaller than min_px on a side (filters logos/rules/icons). Returns the list
    of written paths. Best for a single photo/bitmap figure; a vector chart won't appear
    here — use render_page/crop_region for those."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    doc = _open(pdf)
    page = doc[page_no - 1]
    written = []
    for k, img in enumerate(page.get_images(full=True), start=1):
        xref = img[0]
        try:
            pix = fitz.Pixmap(doc, xref)
        except Exception:
            continue
        if pix.width < min_px or pix.height < min_px:
            continue
        if pix.n - pix.alpha >= 4:          # CMYK/other -> convert to RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)
        path = os.path.join(out_dir, f"p{page_no}_img{k}_{pix.width}x{pix.height}.png")
        pix.save(path)
        written.append(path)
        print(f"wrote {path}")
    doc.close()
    if not written:
        print("no embedded raster images above min_px — try `page` or `crop` instead "
              "(the figure is likely vector + text, not a bitmap).")
    return written


# ===================================================================== figure detection
import re
from collections import Counter

_CAP = re.compile(r'^\s*(fig(?:ure)?|tab(?:le)?|scheme|algorithm)\.?\s*'
                  r'(\d+|[ivxlc]+|[A-Z])\b', re.I)


def _spans(b):
    return [sp for ln in b.get("lines", []) for sp in ln.get("spans", [])]


def _btext(b):
    return "".join(sp["text"] for sp in _spans(b))


def _first_line(b):
    lns = b.get("lines", [])
    return "".join(sp["text"] for sp in lns[0].get("spans", [])) if lns else ""


def _text_blocks(page):
    return [b for b in page.get_text("dict")["blocks"] if b.get("type") == 0
            and b.get("lines")]


def _modal_size(blocks):
    c = Counter()
    for b in blocks:
        for sp in _spans(b):
            c[round(sp["size"])] += max(1, len(sp["text"]))
    return c.most_common(1)[0][0] if c else 10.0


def _is_body(b, modal, page_w):
    """A full-prose paragraph (NEVER part of a figure) — used to bound figure growth.
    Short/centered/odd-font blocks (captions, axis labels, legends, sub-panel letters)
    are NOT body, so they can live inside a figure."""
    if len(b.get("lines", [])) < 2:
        return False
    r = fitz.Rect(b["bbox"])
    if r.width < 0.30 * page_w:
        return False
    sizes = [sp["size"] for sp in _spans(b)] or [modal]
    return abs(sum(sizes) / len(sizes) - modal) <= 1.5


def _cluster(rects, tol=8):
    """Union rects that touch/are within `tol` points, repeatedly, until stable."""
    rects = [fitz.Rect(r) for r in rects]
    changed = True
    while changed:
        changed = False
        out, used = [], [False] * len(rects)
        for i in range(len(rects)):
            if used[i]:
                continue
            r = fitz.Rect(rects[i])
            for j in range(i + 1, len(rects)):
                if used[j]:
                    continue
                infl = fitz.Rect(r.x0 - tol, r.y0 - tol, r.x1 + tol, r.y1 + tol)
                if infl.intersects(rects[j]):
                    r |= rects[j]; used[j] = True; changed = True
            used[i] = True; out.append(r)
        rects = out
    return rects


def _graphics(page, R):
    """Figure-sized graphics rects: clustered vector drawings + raster placements, with
    hairline rules / page borders / tiny specks / page-spanning thin rules filtered out."""
    rects = []
    if hasattr(page, "cluster_drawings"):
        try:
            rects += list(page.cluster_drawings(x_tolerance=6, y_tolerance=6))
        except Exception:
            rects += [fitz.Rect(d["rect"]) for d in page.get_drawings()]
    else:
        rects += [fitz.Rect(d["rect"]) for d in page.get_drawings()]
    for im in page.get_images(full=True):
        try:
            rects += list(page.get_image_rects(im[0]))
        except Exception:
            pass
    try:
        rects += [fitz.Rect(ii["bbox"]) for ii in page.get_image_info(xrefs=True)]
    except Exception:
        pass
    pa = R.get_area()
    keep = []
    for r in rects:
        r = r & R
        if r.is_empty or r.is_infinite:
            continue
        if r.width < 8 or r.height < 8:                       # speck / hairline
            continue
        if r.width > 0.92 * R.width and r.height < 6:         # full-width rule
            continue
        if r.get_area() < 0.004 * pa:                         # too small to be a figure
            continue
        keep.append(r)
    return _cluster(keep, tol=10)


def _xshare(a, b):
    """Horizontal overlap as a fraction of the narrower box — i.e. 'same column?'."""
    ov = min(a.x1, b.x1) - max(a.x0, b.x0)
    m = min(a.width, b.width)
    return ov / m if m > 0 else 0


def _ovfrac(a, b):
    """Area overlap as a fraction of the smaller box."""
    inter = (a & b).get_area()
    m = min(a.get_area(), b.get_area())
    return inter / m if m > 0 else 0


def find_figures(pdf, page_no=None):
    """Detect figure/table regions in a born-digital PDF by anchoring on captions
    ("Figure N" / "Fig. N" / "Table N") and growing into the adjacent graphics, bounded by
    body text. Returns a list of dicts: {page, label, kind, side, bbox(points), caption,
    checks}. When a page has graphics but NO caption (a figure-only page), the graphics
    clusters are returned as unlabelled figures. The manual `crop_helper grid`→`crop` loop
    remains the fallback when a `checks` warning shows detection is off."""
    doc = _open(pdf)
    pages = [page_no - 1] if page_no else range(doc.page_count)
    out = []
    for pi in pages:
        page = doc[pi]; R = page.rect
        blocks = _text_blocks(page)
        modal = _modal_size(blocks)
        caps = []
        for b in blocks:
            m = _CAP.match(_first_line(b))
            if m:
                kind = "table" if m.group(1).lower().startswith("tab") else \
                       ("figure" if m.group(1).lower().startswith("fig") else m.group(1).lower())
                caps.append({"r": fitz.Rect(b["bbox"]), "kind": kind,
                             "label": f"{m.group(1).title().split('.')[0]} {m.group(2)}",
                             "text": _btext(b)[:140]})
        cap_rects = [c["r"] for c in caps]
        body = [fitz.Rect(b["bbox"]) for b in blocks
                if _is_body(b, modal, R.width) and not any(fitz.Rect(b["bbox"]).intersects(cr) for cr in cap_rects)]
        nonbody = [fitz.Rect(b["bbox"]) for b in blocks
                   if not _is_body(b, modal, R.width) and not any(fitz.Rect(b["bbox"]).intersects(cr) for cr in cap_rects)]
        gfx = _graphics(page, R)
        hdr, ftr = R.y0 + 0.045 * R.height, R.y1 - 0.045 * R.height
        accepted = []                      # boxes already taken on this page (no overlap)

        def _take(rec):
            """Accept a detection only if it doesn't substantially overlap one already
            taken — dedups the 'same pixels under two labels' and figure/figure swaps."""
            b = fitz.Rect(*rec["bbox"])
            if any(_ovfrac(b, a) > 0.45 for a in accepted):
                return
            accepted.append(b); out.append(rec)

        if not caps:                       # figure-only page: emit graphics clusters
            for g in sorted(gfx, key=lambda r: (r.y0, r.x0)):
                _take(_emit(pi, None, "figure", None, g, "", gfx, body, R, cap_rects))
            continue

        for c in caps:
            cr = c["r"]; cx = (cr.x0 + cr.x1) / 2

            # teaser case: caption sits INSIDE a much larger graphics cluster — the whole
            # cluster is the figure (caption is part of its layout); emit it whole.
            host = next((g for g in gfx if (g & cr).get_area() > 0.55 * cr.get_area()
                         and g.get_area() > 4 * cr.get_area()), None)
            if host is not None:
                box = fitz.Rect(host) & R
                # a big cluster can over-merge the figure with body-text vector elements
                # (citation links etc); clamp the box away from body paragraphs.
                for bb in body:
                    if box.intersects(bb) and (bb & box).get_area() > 0.3 * bb.get_area():
                        if bb.y0 >= cr.y1 - 2:
                            box.y1 = min(box.y1, bb.y0 - 1)
                        elif bb.y1 <= cr.y0 + 2:
                            box.y0 = max(box.y0, bb.y1 + 1)
                box.y0 = max(box.y0, hdr); box.y1 = min(box.y1, ftr); box &= R
                if not box.is_empty and box.width > 12 and box.height > 12:
                    _take(_emit(pi, c["label"], c["kind"], "around", box, c["text"], gfx, body, R, cap_rects, c["r"]))
                continue

            def collect(side):
                """Graphics on one side of the caption; a cluster straddling the caption is
                clipped to that side so it still counts (and never includes the caption)."""
                rs = []
                for g in gfx:
                    hov = min(g.x1, cr.x1) - max(g.x0, cr.x0)
                    if hov <= 0 and not (g.x0 - 24 <= cx <= g.x1 + 24):
                        continue
                    if side == "above" and g.y0 < cr.y0 - 2:
                        gg = fitz.Rect(g); gg.y1 = min(gg.y1, cr.y0 - 1)
                        if gg.height > 10:
                            rs.append(gg)
                    elif side == "below" and g.y1 > cr.y1 + 2:
                        gg = fitz.Rect(g); gg.y0 = max(gg.y0, cr.y1 + 1)
                        if gg.height > 10:
                            rs.append(gg)
                return rs

            aRs, bRs = collect("above"), collect("below")
            aA = sum(r.get_area() for r in aRs); bA = sum(r.get_area() for r in bRs)
            if aA == 0 and bA == 0:                # caption with no graphics (text table)
                continue
            side, rs = ("above", aRs) if aA >= bA else ("below", bRs)
            box = fitz.Rect(rs[0])
            for r in rs[1:]:
                box |= r
            # grow to swallow nearby in-figure text (axis labels, legend, panel letters)
            for t in nonbody:
                infl = fitz.Rect(box.x0 - 16, box.y0 - 16, box.x1 + 16, box.y1 + 16)
                if infl.intersects(t):
                    cand = box | t
                    if not any(cand.intersects(bb) and (bb & cand).get_area() > 0.3 * bb.get_area()
                               for bb in body):
                        box = cand
            # never include the caption; clamp to header/footer band & page
            # bound the figure to its OWN band: between this caption and the nearest other
            # caption (same column) on the figure side — stops a caption grabbing a
            # neighbour's figure/table on dense multi-element pages.
            others = [o["r"] for o in caps if o is not c and _xshare(o["r"], cr) > 0.3]
            if side == "above":
                lim = max([o.y1 for o in others if o.y1 <= cr.y0 - 2] + [hdr])
                box.y0 = max(box.y0, lim); box.y1 = min(box.y1, cr.y0 - 1)
            else:
                lim = min([o.y0 for o in others if o.y0 >= cr.y1 + 2] + [ftr])
                box.y1 = min(box.y1, lim); box.y0 = max(box.y0, cr.y1 + 1)
            box &= R
            if box.is_empty or box.width < 12 or box.height < 12:
                continue
            _take(_emit(pi, c["label"], c["kind"], side, box, c["text"], gfx, body, R, cap_rects, c["r"]))
    doc.close()
    return out


def _emit(pi, label, kind, side, box, caption, gfx, body, R, cap_rects=(), self_cap=None):
    """Package a detection + run cheap geometric validity checks so the caller can flag a
    suspect crop. The crucial mislocalization check is `foreign_caption`: if the crop
    swallows a DIFFERENT figure/table's caption it has bled into a neighbour — the silent
    failure mode on dense pages — so it's flagged even when body-text overlap is low."""
    A = box.get_area() or 1
    gcov = sum((g & box).get_area() for g in gfx) / A
    bover = max([(b & box).get_area() / b.get_area() for b in body if b.intersects(box)] or [0])
    ar = box.width / box.height if box.height else 0
    foreign = any(cr is not self_cap and (cr & box).get_area() > 0.5 * cr.get_area()
                  for cr in cap_rects)
    checks = {
        "graphics_coverage": round(min(gcov, 1.0), 2),
        "body_text_overlap": round(bover, 2),
        "aspect": round(ar, 2),
        "foreign_caption": bool(foreign),
        "in_page": bool((box & R).get_area() >= 0.999 * box.get_area()),
    }
    checks["ok"] = (checks["graphics_coverage"] >= 0.40 and checks["body_text_overlap"] <= 0.20
                    and 0.08 <= ar <= 14 and checks["in_page"] and not foreign)
    return {"page": pi + 1, "label": label, "kind": kind, "side": side,
            "bbox": [round(box.x0, 1), round(box.y0, 1), round(box.x1, 1), round(box.y1, 1)],
            "caption": caption, "checks": checks}


def render_figure(pdf, bbox, out, dpi=300, pad=5, do_trim=True):
    """Render a detected figure bbox (page points) to PNG, with a small outward pad so
    edge axis-labels/colour-bars aren't clipped, then snap-to-content trim the residual
    background. pad is in points; bbox = (page_no, x0, y0, x1, y1)."""
    doc = _open(pdf)
    pno, x0, y0, x1, y1 = bbox
    page = doc[pno - 1]; R = page.rect
    clip = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad) & R
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
    pix.save(out)
    doc.close()
    if do_trim:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from crop_helper import trim
            trim(out, out, margin=0.012)
        except Exception as e:
            print(f"(trim skipped: {e})")
    print(f"wrote {out}")
    return out


def _print_figures(pdf, page_no=None):
    figs = find_figures(pdf, page_no)
    if not figs:
        print("no figures detected (try `page`/`crop`, or the page may be text-only/scanned)")
    for i, f in enumerate(figs):
        warn = "" if f["checks"]["ok"] else "  ⚠ CHECK (verify by viewing)"
        print(f"[{i}] p{f['page']} {f['label'] or '(figure)'} {f['bbox']} "
              f"cov={f['checks']['graphics_coverage']} bodyov={f['checks']['body_text_overlap']} "
              f"ar={f['checks']['aspect']}{warn}")
        if f["caption"]:
            print(f"      {f['caption']!r}")
    return figs


def _autofig(pdf, out_dir, dpi=300):
    os.makedirs(out_dir, exist_ok=True)
    figs = find_figures(pdf)
    for i, f in enumerate(figs):
        lab = (f["label"] or f"fig_{i}").replace(" ", "").replace(".", "")
        out = os.path.join(out_dir, f"p{f['page']}_{lab}.png")
        render_figure(pdf, [f["page"], *f["bbox"]], out, dpi=dpi)
        flag = "" if f["checks"]["ok"] else "  ⚠ verify"
        print(f"    -> {out}{flag}")
    return figs


def _main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    a = argv[2:]
    flags = {}
    pos = []
    i = 0
    while i < len(a):
        if a[i] == "--dpi":
            flags["dpi"] = int(a[i + 1]); i += 2
        elif a[i] == "--frac":
            flags["frac"] = True; i += 1
        elif a[i] == "--min-px":
            flags["min_px"] = int(a[i + 1]); i += 2
        else:
            pos.append(a[i]); i += 1
    if cmd == "info":
        info(pos[0])
    elif cmd == "page":
        render_page(pos[0], int(pos[1]), pos[2], dpi=flags.get("dpi", 300))
    elif cmd == "crop":
        coords = list(map(float, pos[3:7]))
        crop_region(pos[0], int(pos[1]), pos[2], *coords,
                    dpi=flags.get("dpi", 300), frac=flags.get("frac", False))
    elif cmd == "images":
        extract_images(pos[0], int(pos[1]), pos[2], min_px=flags.get("min_px", 120))
    elif cmd == "figures":                       # auto-detect figures (optionally one page)
        _print_figures(pos[0], int(pos[1]) if len(pos) > 1 else None)
    elif cmd == "figure":                        # render detected figure #idx -> out.png
        figs = find_figures(pos[0])
        idx = int(pos[1])
        if idx < 0 or idx >= len(figs):
            print(f"index {idx} out of range (found {len(figs)} figures); run `figures` first")
            return 1
        f = figs[idx]
        render_figure(pos[0], [f["page"], *f["bbox"]], pos[2], dpi=flags.get("dpi", 300))
    elif cmd == "autofig":                        # render ALL detected figures to a dir
        _autofig(pos[0], pos[1], dpi=flags.get("dpi", 300))
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
