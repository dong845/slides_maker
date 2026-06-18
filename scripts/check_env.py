#!/usr/bin/env python3
"""Preflight: verify the slide-maker toolchain. Run once on a new machine:

    python check_env.py            # Windows / anywhere
    bash scripts/check_env.sh      # mac / Linux (delegates here)

Reports what's installed and the exact command to fix anything missing.
Cross-platform: macOS, Linux, WSL, and native Windows (PowerShell / cmd).
"""
import os
import sys

# Reuse the one LibreOffice finder so check + render agree on what counts as "found".
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_deck import find_soffice  # noqa: E402

# A copy-pasteable pip command for THIS interpreter (handles python vs python3 vs py).
PIP = '"{}" -m pip install'.format(sys.executable)


def check_module(mod, label, fix_pkg, optional=False, note=""):
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "")
        print("  [ok]  {} {}".format(label, ver).rstrip())
    except ImportError:
        tag = "[optional]" if optional else "[MISSING] "
        line = "  {} {:<12} ->  {} {}".format(tag, label, PIP, fix_pkg)
        if note:
            line += "   ({})".format(note)
        print(line)


def main():
    print("slide-maker environment check:")
    check_module("pptx", "python-pptx", "python-pptx")
    check_module("fitz", "pymupdf", "pymupdf")
    check_module("matplotlib", "matplotlib", "matplotlib",
                 optional=True, note="only for equation_png")

    soffice = find_soffice()
    if soffice:
        print("  [ok]  LibreOffice ({})".format(soffice))
    else:
        print("  [MISSING]  LibreOffice  ->  "
              "macOS: brew install --cask libreoffice | "
              "Ubuntu: sudo apt install libreoffice | "
              "Windows: winget install TheDocumentFoundation.LibreOffice | "
              "else https://www.libreoffice.org/download")


if __name__ == "__main__":
    main()
