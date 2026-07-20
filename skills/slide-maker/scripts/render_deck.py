#!/usr/bin/env python3
"""Render a .pptx to one PNG per slide, so you can SEE each slide and catch
overflow / contrast / glyph problems before handing the deck back.

Cross-platform: works on macOS, Linux, WSL, and NATIVE Windows (PowerShell / cmd) —
no shell required. The .sh wrapper just delegates here.

Usage:
    python render_deck.py /path/to/deck.pptx [out_dir]
    # Windows:  python scripts\\render_deck.py C:\\path\\deck.pptx
Output: <out_dir>/slide01.png, slide02.png, ...   (default out_dir: ./render)

Requires: LibreOffice + pymupdf (python -m pip install pymupdf). One-time installs.
Override LibreOffice discovery with the SOFFICE env var (full path to the binary).
"""
import json
import os
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path


def find_soffice():
    """Locate the LibreOffice binary across macOS / Linux / WSL / native Windows.

    Order: $SOFFICE override -> anything on PATH -> known install locations.
    On Windows, prefer the sibling ``soffice.com`` (the console front-end that
    blocks until conversion finishes) over ``soffice.exe`` (which can detach and
    leave the PDF half-written).
    """
    def prefer_com(path):
        if path and path.lower().endswith("soffice.exe"):
            com = path[:-4] + ".com"
            if os.path.isfile(com):
                return com
        return path

    env = os.environ.get("SOFFICE")
    if env and os.path.isfile(env):
        return prefer_com(env)

    for cmd in ("soffice", "libreoffice", "soffice.com", "soffice.exe"):
        found = shutil.which(cmd)
        if found:
            return prefer_com(found)

    candidates = [
        # macOS
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        # Linux
        "/usr/bin/soffice", "/usr/bin/libreoffice", "/usr/local/bin/soffice",
        "/snap/bin/libreoffice", "/opt/libreoffice/program/soffice",
        # native Windows (default installer locations)
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        # Windows install reached from WSL via the /mnt/c mount
        "/mnt/c/Program Files/LibreOffice/program/soffice.exe",
    ]
    # %ProgramFiles% may point somewhere non-default on Windows.
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(var)
        if base:
            candidates.append(os.path.join(base, "LibreOffice", "program", "soffice.exe"))

    for path in candidates:
        if os.path.isfile(path):
            return prefer_com(path)
    return None


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def _tail(text, limit=4000):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return "...<truncated>...\n" + text[-limit:]


def _slide_fingerprints(pptx):
    """One content hash per slide, in deck order.

    Covers the slide's own XML, its rels, and the BYTES of every media part it references —
    so a re-cropped photo or a swapped plate counts as a change even when the XML is identical.
    Returns (list_of_hashes, uses_slidenum_field).
    """
    import hashlib
    import re
    import zipfile
    with zipfile.ZipFile(pptx) as z:
        names = set(z.namelist())
        # DECK-GLOBAL digest, mixed into EVERY slide hash. A change to the slide size, theme,
        # master or a layout re-renders every slide while touching no slide's own XML — without
        # this, --fast would report "no slide changed" and leave a deck's worth of stale PNGs
        # (verified: flipping 16:9 -> 4:3 slipped through before this was added).
        # docProps/* is excluded on purpose: core.xml carries a modified-timestamp that changes on
        # every save, which would force a full render every time and delete the feature.
        # ppt/media and ppt/notesSlides are excluded too — media is already covered per-slide via
        # each slide's rels, and notes never reach a rendered pixel.
        gh = hashlib.sha256()
        for n in sorted(names):
            if not n.startswith("ppt/"):
                continue
            if n.startswith(("ppt/slides/", "ppt/media/", "ppt/notesSlides/")):
                continue
            gh.update(n.encode())
            gh.update(z.read(n))
        global_digest = gh.digest()
        # deck order comes from presentation.xml + its rels, not from filename sorting
        pres = z.read("ppt/presentation.xml").decode("utf-8", "replace")
        rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf-8", "replace")
        rid_to_target = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
        order = [rid_to_target.get(r, "") for r in re.findall(r'<p:sldId[^>]*r:id="([^"]+)"', pres)]
        order = ["ppt/" + t.replace("../", "") for t in order if t]

        fps, slidenum = [], False
        for sname in order:
            h = hashlib.sha256()
            h.update(global_digest)
            body = z.read(sname) if sname in names else b""
            h.update(body)
            if b'type="slidenum"' in body:
                slidenum = True
            rname = sname.replace("slides/", "slides/_rels/") + ".rels"
            rel_xml = z.read(rname).decode("utf-8", "replace") if rname in names else ""
            h.update(rel_xml.encode())
            for tgt in re.findall(r'Target="([^"]+)"', rel_xml):
                if "media/" not in tgt:
                    continue
                media = "ppt/" + tgt.replace("../", "")
                if media in names:
                    h.update(z.read(media))
            fps.append(h.hexdigest())
    return fps, slidenum


def _subset_pptx(src, keep_idx, dest):
    """Copy `src` keeping ONLY the 0-indexed slides in `keep_idx` (order preserved).

    Deleting sldId entries is safe and cheap; the orphaned parts stay in the package and
    LibreOffice ignores them. Verified pixel-identical to the same slide rendered from the
    full deck, which is what makes the fast path trustworthy rather than merely fast.
    """
    import shutil
    from pptx import Presentation
    shutil.copy(src, dest)
    prs = Presentation(dest)
    lst = prs.slides._sldIdLst
    for i, sid in enumerate(list(lst)):
        if i not in keep_idx:
            lst.remove(sid)
    prs.save(dest)
    return dest


def _render_pdf(soffice, src, outdir):
    """pptx -> pdf via a throwaway LibreOffice profile. Returns (pdf_path, result, cmd)."""
    profile = tempfile.mkdtemp(prefix="lo_render_")
    try:
        cmd = [soffice, "-env:UserInstallation=" + Path(profile).as_uri(),
               "--headless", "--convert-to", "pdf", "--outdir", outdir, src]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=300)
        except subprocess.TimeoutExpired:
            die("LibreOffice render exceeded 300s and was killed — the .pptx may be malformed or "
                "hostile (e.g. a decompression bomb). Nothing was produced from {}.".format(src))
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return (os.path.join(outdir, os.path.splitext(os.path.basename(src))[0] + ".pdf"), result, cmd)


def main(argv):
    # --deliverables (alias --final): ALSO park the PDF beside the .pptx and write viewer.html.
    # OFF by default: while a deck is still being iterated, those two are pure churn — they are
    # regenerated every round, clutter the deck root, and go stale the moment the user hand-edits
    # the .pptx. They are produced once, at hand-off, when the user says the deck is final.
    deliverables = False
    # --fast: re-render ONLY the slides whose content changed since the last render.
    # Measured on a real 18-slide deck: full = 9.1s LibreOffice + 24.4s rasterize; one changed
    # slide = 2.5s + 0.7s. Rasterization, not the PDF export, is the dominant cost — so the win
    # comes from rasterizing one page, and subsetting the pptx makes the export cheap too.
    fast = False
    argv = list(argv)
    while "--fast" in argv:
        argv.remove("--fast")
        fast = True
    for flag in ("--deliverables", "--final"):
        while flag in argv:
            argv.remove(flag)
            deliverables = True
    if not argv:
        die("usage: python render_deck.py /path/to/deck.pptx [out_dir] [--fast] [--deliverables]")
    pptx = argv[0]
    out = argv[1] if len(argv) > 1 else "./render"

    if not os.path.isfile(pptx):
        die("no such file: " + pptx)

    soffice = find_soffice()
    if not soffice:
        die(
            "LibreOffice not found — needed to render slides for the verify + critic loop.\n"
            "  macOS:         brew install --cask libreoffice\n"
            "  Debian/Ubuntu: sudo apt install libreoffice\n"
            "  Windows:       winget install TheDocumentFoundation.LibreOffice\n"
            "                 (or choco install libreoffice-fresh)\n"
            "  other:         https://www.libreoffice.org/download\n"
            "  (or set the SOFFICE env var to the full path of the soffice binary)"
        )

    # Decide full vs incremental BEFORE spending anything on LibreOffice.
    cache_path = os.path.join(out, ".render-cache.json")
    fps, has_slidenum = _slide_fingerprints(pptx)
    changed, skip_reason = None, None
    if fast:
        prev = None
        try:
            with open(cache_path, encoding="utf-8") as f:
                prev = json.load(f).get("fingerprints")
        except (OSError, ValueError):
            prev = None
        if has_slidenum:
            # An auto slide-number FIELD renumbers itself in a subset, so a subset render would
            # print the wrong page number. Correctness beats speed: fall back to a full render.
            skip_reason = "deck uses auto slide-number fields"
        elif not prev:
            skip_reason = "no previous render cache"
        elif len(prev) != len(fps):
            # Slides inserted or deleted shifts every index after the edit; PNG filenames would
            # silently point at the wrong slides.
            skip_reason = "slide count changed ({} -> {})".format(len(prev), len(fps))
        else:
            changed = [i for i, h in enumerate(fps) if h != prev[i]]
            missing = [i for i in range(len(fps))
                       if not os.path.isfile(os.path.join(out, "slide{:02d}.png".format(i + 1)))]
            changed = sorted(set(changed) | set(missing))

    incremental = fast and changed is not None and 0 < len(changed) < len(fps)
    if fast and changed is not None and len(changed) == len(fps) and len(fps):
        # Every slide changed (a rebuild that touched everything, or a deck-global edit such as a
        # theme/canvas change). A subset of "all slides" is just a full render with extra steps.
        skip_reason = "every slide changed"
    if fast and changed is not None and not changed:
        print("no slide changed since the last render — nothing to re-render")
        print("next: python3 {} {} --renders {}".format(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "lint_deck.py"), pptx, out))
        return 0


    # Wiping the render dir BEFORE deciding is what made --fast a no-op: every PNG looked
    # "missing", so every slide looked changed. An incremental run keeps the existing PNGs and
    # overwrites only the ones it re-renders.
    if os.path.isdir(out) and not incremental:
        entries = os.listdir(out)
        own_pdf = os.path.splitext(os.path.basename(pptx))[0] + ".pdf"
        render_only = all(
            (e.startswith(("slide", "thumb_")) and e.endswith(".png"))
            or e == "viewer.html" or e == own_pdf          # only THIS deck's fallback pdf is ours
            or e in (".DS_Store", "Thumbs.db", ".render-cache.json")   # OS junk + our own cache only
            for e in entries)                              # make the dir look deletable
        if render_only:
            shutil.rmtree(out, ignore_errors=True)
        else:
            # out holds files that are NOT ours (worst case: the user passed "." — the pptx's own
            # directory). NEVER rmtree it; clear only our previous render products.
            for e in entries:
                if (e.startswith(("slide", "thumb_")) and e.endswith(".png")) or e == "viewer.html":
                    try:
                        os.remove(os.path.join(out, e))
                    except OSError:
                        pass
    os.makedirs(out, exist_ok=True)

    # Give this invocation its OWN LibreOffice profile: lets parallel renders (the
    # large-deck section fan-out) run at once without fighting a shared profile lock,
    # and lets the render work even while the user has the LibreOffice GUI open.
    # Without this, concurrent/coexisting soffice calls silently produce no PDF.
    src_pptx, keep = pptx, None
    tmp_subset = None
    if incremental:
        keep = changed
        tmp_subset = os.path.join(tempfile.mkdtemp(prefix="lo_subset_"), "subset.pptx")
        _subset_pptx(pptx, set(keep), tmp_subset)
        src_pptx = tmp_subset

    pdf, result, cmd = _render_pdf(soffice, src_pptx, out)
    if not os.path.isfile(pdf):
        detail = [
            "LibreOffice produced no PDF from {}.".format(pptx),
            "Command: " + " ".join(cmd),
            "Exit code: {}".format(result.returncode),
        ]
        stdout = _tail(result.stdout)
        stderr = _tail(result.stderr)
        if stdout:
            detail.append("stdout:\n" + stdout)
        if stderr:
            detail.append("stderr:\n" + stderr)
        detail.append(
            "Check that the file opens, close any open copy, and in sandboxed runtimes "
            "rerun the render with the permissions needed for LibreOffice."
        )
        die("\n".join(detail))

    try:
        import fitz  # pymupdf
    except ImportError:
        die("pymupdf not installed — run: {} -m pip install pymupdf".format(
            os.path.basename(sys.executable) or "python"))

    doc = fitz.open(pdf)
    if incremental:
        # PDF page k corresponds to deck slide keep[k] — write ONLY those PNGs and leave the
        # rest of render/ untouched.
        if doc.page_count != len(keep):
            die("incremental render produced {} page(s) for {} changed slide(s) — refusing to "
                "write PNGs that may be mismatched; re-run without --fast".format(
                    doc.page_count, len(keep)))
        for k, page in enumerate(doc):
            page.get_pixmap(matrix=fitz.Matrix(2, 2)).save(
                os.path.join(out, "slide{:02d}.png".format(keep[k] + 1)))
        # thumbnails only matter when a bookend slide moved
        for name, idx in (("thumb_first", 0), ("thumb_last", len(fps) - 1)):
            if idx in keep:
                page = doc[keep.index(idx)]
                zoom = 240.0 / max(1.0, page.rect.width)
                page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(os.path.join(out, name + ".png"))
        n_pages = len(fps)
    else:
        pages = list(enumerate(doc, 1))
        for i, page in pages:
            page.get_pixmap(matrix=fitz.Matrix(2, 2)).save(
                os.path.join(out, "slide{:02d}.png".format(i)))
        # bookend thumbnails (~240px wide) for the critic's poster test — first + last slide small,
        # the scale at which a cover either survives or dies. Same PyMuPDF path, no new deps.
        if pages:
            for name, (_, page) in (("thumb_first", pages[0]), ("thumb_last", pages[-1])):
                zoom = 240.0 / max(1.0, page.rect.width)
                page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(os.path.join(out, name + ".png"))
        n_pages = doc.page_count
    doc.close()
    if tmp_subset:
        shutil.rmtree(os.path.dirname(tmp_subset), ignore_errors=True)
        try:                                   # the subset PDF is not the deck's PDF — never keep it
            os.remove(pdf)
        except OSError:
            pass
        pdf = None

    # Record fingerprints so the NEXT run can diff against them. Written only after the PNGs
    # actually landed, so a crashed render never leaves a cache claiming work that did not happen.
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"fingerprints": fps}, f)
    except OSError:
        pass

    # The PDF is an INTERMEDIATE of this render (pptx -> PDF -> PNG), so it always exists. Whether
    # it is promoted to a deliverable beside the .pptx is the user's call at hand-off.
    pdf_dest = pdf
    if deliverables and pdf is None:
        die("--deliverables needs a full-deck render; re-run without --fast")
    if deliverables:
        pdf_dest = os.path.join(os.path.dirname(os.path.abspath(pptx)) or ".",
                                os.path.splitext(os.path.basename(pptx))[0] + ".pdf")
        try:
            if os.path.abspath(pdf_dest) != os.path.abspath(pdf):
                os.replace(pdf, pdf_dest)
        except OSError:
            pdf_dest = pdf                 # couldn't move (odd mount/permissions) — it stays in out/

    # Self-contained flip-through viewer — parked BESIDE the .pptx (deck root), same as the PDF, so
    # the user finds it without digging into render/. It references the PNGs through the render subdir
    # (relative to the viewer's own location), so a plain double-click works. One file:// link, any
    # browser, any OS (arrow keys / click / thumbnail strip). Zero dependencies, zero network.
    deck_dir = os.path.dirname(os.path.abspath(pptx)) or "."
    viewer = None
    if deliverables:
        rel = os.path.relpath(os.path.abspath(out), deck_dir)
        pref = "" if rel in (".", "") else rel.replace(os.sep, "/").rstrip("/") + "/"
        slides = [pref + "slide{:02d}.png".format(i) for i in range(1, n_pages + 1)]
        viewer = os.path.join(deck_dir, "viewer.html")
        try:
            with open(viewer, "w", encoding="utf-8") as f:
                f.write(_viewer_html(os.path.splitext(os.path.basename(pptx))[0], slides))
        except OSError:
            viewer = None
    # sweep a stale viewer.html left inside the render dir by an older build (it now lives at root)
    stale = os.path.join(out, "viewer.html")
    if viewer and os.path.abspath(stale) != os.path.abspath(viewer) and os.path.exists(stale):
        try: os.remove(stale)
        except OSError: pass
    if incremental:
        print("fast render: {} of {} slides re-rendered ({}) -> {}".format(
            len(keep), len(fps), ", ".join(str(i + 1) for i in keep), out))
    else:
        print("rendered {} slides -> {}".format(n_pages, out))
        if fast and skip_reason:
            print("(--fast fell back to a full render: {})".format(skip_reason))
    if not deliverables:
        print("pdf/viewer: not generated (deck still in progress) — at hand-off, once the user "
              "confirms the deck is final, re-run with --deliverables")
    else:
        print("pdf: {}".format(pdf_dest))
    if viewer:
        print("preview: {}  (open in a browser; arrow keys flip)".format(
            Path(viewer).resolve().as_uri()))
    print("next: python3 {} {} --renders {}  # render-time lint, then the actor-critic loop".format(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "lint_deck.py"), pptx, out))


def _viewer_html(title, slides):
    """Single-file dark flip-through viewer: big slide + thumbnail rail + keyboard/click nav."""
    import json
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — preview</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ margin: 0; box-sizing: border-box; }}
  body {{ background: #17191f; color: #cfd4de; font: 13px/1.4 system-ui, sans-serif;
         height: 100vh; display: flex; flex-direction: column; user-select: none; }}
  header {{ padding: 8px 14px; display: flex; align-items: center; gap: 12px; }}
  header b {{ color: #fff; font-weight: 600; }}
  #stage {{ flex: 1; display: flex; align-items: center; justify-content: center;
            min-height: 0; padding: 0 12px; cursor: pointer; }}
  #main {{ max-width: 100%; max-height: 100%; box-shadow: 0 6px 30px rgba(0,0,0,.5);
           border-radius: 4px; }}
  #rail {{ display: flex; gap: 6px; overflow-x: auto; padding: 10px 14px; flex: none; }}
  #rail img {{ height: 62px; border-radius: 3px; opacity: .45; cursor: pointer;
               border: 2px solid transparent; }}
  #rail img.on {{ opacity: 1; border-color: #5b8def; }}
  #num {{ margin-left: auto; font-variant-numeric: tabular-nums; color: #8a93a6; }}
  kbd {{ background:#2a2e38; border-radius:3px; padding:1px 5px; font-size:11px; color:#9aa3b2; }}
</style></head><body>
<header><b>{title}</b><span>&larr;/&rarr; or click to flip &nbsp;<kbd>F</kbd> fullscreen</span><span id="num"></span></header>
<div id="stage"><img id="main" alt="slide"></div>
<div id="rail"></div>
<script>
const S = {slides}; let i = 0;
const main = document.getElementById('main'), rail = document.getElementById('rail'),
      num = document.getElementById('num');
S.forEach((src, k) => {{ const t = document.createElement('img'); t.src = src; t.loading = 'lazy';
  t.onclick = () => go(k); rail.appendChild(t); }});
function go(k) {{ i = (k + S.length) % S.length; main.src = S[i];
  num.textContent = (i + 1) + ' / ' + S.length;
  [...rail.children].forEach((t, k2) => t.classList.toggle('on', k2 === i));
  rail.children[i].scrollIntoView({{ inline: 'center', block: 'nearest', behavior: 'smooth' }});
  if (i + 1 < S.length) (new Image()).src = S[i + 1]; }}
document.getElementById('stage').onclick = () => go(i + 1);
addEventListener('keydown', e => {{
  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') go(i + 1);
  else if (e.key === 'ArrowLeft' || e.key === 'PageUp') go(i - 1);
  else if (e.key === 'Home') go(0); else if (e.key === 'End') go(S.length - 1);
  else if (e.key.toLowerCase() === 'f') document.documentElement.requestFullscreen?.(); }});
go(0);
</script></body></html>
""".format(title=title.replace("&", "&amp;").replace("<", "&lt;"), slides=json.dumps(slides))


if __name__ == "__main__":
    main(sys.argv[1:])
