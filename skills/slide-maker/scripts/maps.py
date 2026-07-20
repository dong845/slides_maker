#!/usr/bin/env python3
"""maps — value-shaded CHOROPLETH base maps for data decks (per-country / per-province).

The high-payoff form the skill was missing: colour a map of Europe / the World / China's provinces by
a value per region (unemployment, revenue, adoption, …). Built on REAL public-domain geometry — nothing
is fabricated — rendered with matplotlib (no geopandas) to a crisp PNG you place with deckkit.picture().

GEOMETRY (permissive, fetched once and cached like icons):
  world / europe  — Natural Earth 110m admin-0 countries  (PUBLIC DOMAIN)
  china           — DataV.GeoAtlas province boundaries      (free)

KEYING your data to regions:
  world / europe  — key by ISO-3166 alpha-2 ("DE","FR"), alpha-3 ("DEU"), or country name ("Germany").
  china           — key by province name ("广东省" or "广东") or adcode (440000).
Unmatched regions render in the neutral no-data colour; unknown data keys are reported.

    from maps import choropleth_png
    p = choropleth_png("out.png", {"DE": 3.1, "FR": 7.3, "ES": 12.8}, mapname="europe",
                       accent="#1F5FA8", title="Unemployment rate (%)")
    deckkit.picture(slide, p, x, y, w, h)          # or deckkit.choropleth() which also draws a legend

See references/data-viz.md (choropleth) and form-selection.md ("a value per geographic region").
"""
import json
import os
import sys
import math
import tempfile
import urllib.request

# ---- geometry sources (pinned) -------------------------------------------------------------------
_NE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
       "ne_110m_admin_0_countries.geojson")
_CN = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"

# Natural Earth 110m leaves ISO_A2 = '-99' for a handful of countries — patch by name so ISO keying works.
_ISO_FIX = {"France": ("FR", "FRA"), "Norway": ("NO", "NOR"), "Kosovo": ("XK", "XKX"),
            "Somaliland": ("", ""), "N. Cyprus": ("", "")}


def _cache_dir():
    """Same host-agnostic cache used by icons (SLIDE_MAKER_CACHE override), under a maps/ subdir."""
    env = os.environ.get("SLIDE_MAKER_CACHE")
    if env:
        base = env
    elif sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
        base = os.path.join(base, "slide-maker")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~/Library/Caches"), "slide-maker")
    else:
        base = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "slide-maker")
    return os.path.join(base, "maps")


_CACHE = _cache_dir()
try:
    os.makedirs(_CACHE, exist_ok=True)
except OSError:
    _CACHE = os.path.join(tempfile.gettempdir(), "slide-maker-maps")
    os.makedirs(_CACHE, exist_ok=True)


def _load_geojson(url, cache_name):
    """Fetch a GeoJSON once and cache it on disk (atomic write). Returns the parsed dict."""
    cache = os.path.join(_CACHE, cache_name)
    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        try:
            return json.load(open(cache, encoding="utf-8"))
        except Exception:
            pass
    req = urllib.request.Request(url, headers={"User-Agent": "slide-maker/maps"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except Exception as e:
        raise RuntimeError(f"maps: could not fetch base geometry from {url} ({e}). "
                           "Needs network on first use; it is cached afterward.") from e
    gj = json.loads(raw)
    fd, tmp = tempfile.mkstemp(dir=_CACHE, suffix=".json")
    with os.fdopen(fd, "wb") as fh:
        fh.write(raw)
    os.replace(tmp, cache)
    return gj


# ---- projections (closed-form, no pyproj) --------------------------------------------------------
def _proj_equirect(lon, lat, lat0=0.0):
    """Equirectangular — plate carrée with a cos(lat0) x-scale so the aspect isn't stretched."""
    k = math.cos(math.radians(lat0))
    return lon * k, lat


def _albers(lon, lat, lon0, lat0, p1, p2):
    """Albers equal-area conic — the clean look for a regional map (Europe, China)."""
    lon, lat, lon0, lat0, p1, p2 = map(math.radians, (lon, lat, lon0, lat0, p1, p2))
    n = 0.5 * (math.sin(p1) + math.sin(p2))
    if abs(n) < 1e-9:
        n = 1e-9
    C = math.cos(p1) ** 2 + 2 * n * math.sin(p1)
    rho = math.sqrt(max(0.0, C - 2 * n * math.sin(lat))) / n
    rho0 = math.sqrt(max(0.0, C - 2 * n * math.sin(lat0))) / n
    theta = n * (lon - lon0)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


# ---- map registry --------------------------------------------------------------------------------
MAPS = {
    "world":  {"src": ("ne", _NE), "proj": ("equirect", {"lat0": 0}),
               "view": dict(lon=(-168, 190), lat=(-56, 84)), "filter": None},
    "europe": {"src": ("ne", _NE), "proj": ("albers", dict(lon0=10, lat0=52, p1=43, p2=62)),
               "view": dict(lon=(-26, 45), lat=(33, 72)),
               "filter": lambda p: p.get("CONTINENT") == "Europe"},
    "china":  {"src": ("cn", _CN), "proj": ("albers", dict(lon0=105, lat0=35, p1=25, p2=47)),
               "view": None, "filter": None},
}


def _project_fn(spec):
    kind, kw = spec
    if kind == "albers":
        return lambda lon, lat: _albers(lon, lat, **kw)
    return lambda lon, lat: _proj_equirect(lon, lat, **kw)


def _norm(s):
    return "".join(str(s).lower().split()).replace("省", "").replace("市", "").replace("自治区", "")\
        .replace("特别行政区", "").replace("壮族", "").replace("回族", "").replace("维吾尔", "")


def _region_keys(props, src):
    """Every key a user might use for a region → matched against the data dict (case/space-insensitive)."""
    if src == "cn":
        name = props.get("name", "")
        return {k for k in {_norm(name), str(props.get("adcode", ""))} if k}
    name = props.get("NAME") or props.get("ADMIN") or ""
    a2 = props.get("ISO_A2"); a3 = props.get("ISO_A3")
    if (a2 in (None, "-99", "")) and name in _ISO_FIX:
        a2, a3 = _ISO_FIX[name]
    ks = {_norm(name), _norm(props.get("ADMIN", "")), _norm(props.get("NAME_LONG", ""))}
    if a2 and a2 != "-99":
        ks.add(a2.lower())
    if a3 and a3 != "-99":
        ks.add(a3.lower())
    return {k for k in ks if k}


# ---- colour ramp ---------------------------------------------------------------------------------
def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _div_poles(accent, accent2=None):
    """The two DISTINCT poles of a diverging ramp: (negative-pole, positive-pole=accent). ``accent2``
    overrides the negative pole; the default is a colour-blind-safe contrast to the accent (a warm red
    pole when the accent is cool, a cool blue pole when it's warm) — so div is never two-of-the-same."""
    if accent2:
        neg = accent2.lstrip("#")
    else:
        a = _hex(accent)
        neg = "B2182B" if a[2] >= a[0] else "2166AC"        # accent cool → red pole; warm → blue pole
    return "#" + neg, "#" + accent.lstrip("#")


def _ramp(accent, scale, dark, accent2=None):
    """Build a matplotlib colormap. seq: light→accent. div: negative-pole ← near-white → accent."""
    from matplotlib.colors import LinearSegmentedColormap
    if scale == "div":
        neg, pos = _div_poles(accent, accent2)
        return LinearSegmentedColormap.from_list("sm_div", [_hex(neg), (0.96, 0.96, 0.97), _hex(pos)])
    a = _hex(accent)
    light = tuple(1 - (1 - ch) * (0.12 if not dark else 0.22) for ch in a)   # very light tint of accent
    return LinearSegmentedColormap.from_list("sm_seq", [light, a])


def choropleth_png(out_png, data, mapname="europe", *, accent="#1F5FA8", accent2=None, scale="seq",
                   vmin=None, vmax=None, no_data="#E7E9F0", border="#FFFFFF", border_w=0.6,
                   title=None, legend=True, legend_label=None, dark=False, font=None,
                   width_px=1600, pad=0.02):
    """Render a value-shaded choropleth PNG. Returns out_png.

    data     — {region_key: number}. Keys per map: ISO-a2/a3/name (world·europe) or province name/adcode (china).
    mapname  — 'europe' | 'world' | 'china'.
    accent   — base hex for the sequential ramp (light→accent) or one pole of a diverging ramp.
    scale    — 'seq' (default) or 'div'. vmin/vmax fix the range (else data min/max).
    Returns the PNG path; unknown data keys are printed as a notice (not silently dropped)."""
    import matplotlib
    matplotlib.use("Agg")
    import designed_charts as _dc
    _dc._mpl(dark, font)                    # CJK-capable font stack (any-language labels, no tofu)
    import matplotlib.pyplot as plt
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    from matplotlib.collections import PatchCollection
    from matplotlib.colors import Normalize

    if mapname not in MAPS:
        raise ValueError(f"maps: unknown map {mapname!r}; use one of {sorted(MAPS)}")
    cfg = MAPS[mapname]
    src_kind, src_url = cfg["src"]
    gj = _load_geojson(src_url, {"ne": "ne_110m_countries.geojson", "cn": "cn_provinces.geojson"}[src_kind])
    project = _project_fn(cfg["proj"])

    # normalize the user's data keys once. An ASCII 2-3 letter key is an ISO code (lowercased);
    # anything else (incl. a 3-char CJK province name like '广东省') goes through _norm.
    def _dk(k):
        if isinstance(k, str) and k.isascii() and k.isalpha() and len(k) <= 3:
            return k.lower()
        return _norm(k)
    dn = {_dk(k): v for k, v in data.items()}
    orig = {_dk(k): k for k in data}                    # normalized → original key (for the notice)
    vals = [v for v in data.values() if isinstance(v, (int, float)) and math.isfinite(v)]
    lo = vmin if vmin is not None else (min(vals) if vals else 0.0)
    hi = vmax if vmax is not None else (max(vals) if vals else 1.0)
    if scale == "div" and vmin is None and vmax is None:   # zero-centre so the neutral colour == 0
        m = max(abs(lo), abs(hi), 1e-9); lo, hi = -m, m
    if hi <= lo:
        hi = lo + 1.0
    norm = Normalize(lo, hi)
    cmap = _ramp(accent, scale, dark, accent2)

    feats = [f for f in gj["features"] if (cfg["filter"] is None or cfg["filter"](f.get("properties", {})))]
    matched = set()
    patches, colors, dash_segs = [], [], []

    def rings_to_path(coords_polys):
        verts, codes = [], []
        for poly in coords_polys:                         # each poly = [exterior, hole1, ...]
            for ring in poly:
                pts = [project(pt[0], pt[1]) for pt in ring]
                if len(pts) < 3:
                    continue
                verts.extend(pts + [pts[0]])
                codes.extend([Path.MOVETO] + [Path.LINETO] * (len(pts) - 1) + [Path.CLOSEPOLY])
        return Path(verts, codes) if verts else None

    for f in feats:
        props = f.get("properties", {})
        geom = f.get("geometry") or {}
        gt, gc = geom.get("type"), geom.get("coordinates")
        if gt == "Polygon":
            polys = [gc]
        elif gt == "MultiPolygon":
            polys = gc
        else:
            continue
        # china's nine-dash-line feature (adcode '…_JD' / no name) is not a region — draw it as dashed
        # lines (the conventional cartographic element) rather than a filled, invisible no-data sliver.
        if src_kind == "cn" and (str(props.get("adcode", "")).endswith("_JD") or not props.get("name")):
            for poly in polys:
                for ring in poly:
                    if len(ring) >= 2:
                        dash_segs.append([project(p[0], p[1]) for p in ring])
            continue
        path = rings_to_path(polys)
        if path is None:
            continue
        keys = _region_keys(props, src_kind)
        mk = next((k for k in keys if k in dn), None)     # the data key that matches THIS region (if any)
        if mk is not None:
            matched.add(mk)
            v = dn[mk]
            colors.append(cmap(norm(v)) if isinstance(v, (int, float)) and math.isfinite(v) else no_data)
        else:
            colors.append(no_data)                        # region with no datum → neutral no-data fill
        patches.append(PathPatch(path))

    unknown = [orig.get(k, k) for k in dn if k not in matched]   # ORIGINAL keys that matched no region
    if unknown:
        print(f"[maps] {len(unknown)} data key(s) matched no region on '{mapname}': "
              f"{unknown[:6]}{' …' if len(unknown) > 6 else ''} — check the spelling/ISO code")

    # figure — no axes, equal aspect, tight to the geometry (or the map's view bbox)
    W = width_px / 200.0
    fig, ax = plt.subplots(figsize=(W, W * 0.72), dpi=200)
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")
    pc = PatchCollection(patches, facecolors=colors, edgecolors=border, linewidths=border_w, antialiased=True)
    ax.add_collection(pc)
    if dash_segs:                                       # china nine-dash line, as a visible dashed element
        from matplotlib.collections import LineCollection
        ax.add_collection(LineCollection(dash_segs, colors=("#6B7280" if dark else "#9AA0AA"),
                                         linewidths=1.1, linestyles=(0, (4, 2)), antialiased=True))
    ax.set_aspect("equal")
    ax.axis("off")
    if cfg["view"]:
        xs, ys = [], []
        for lon in (cfg["view"]["lon"][0], cfg["view"]["lon"][1]):
            for lat in (cfg["view"]["lat"][0], cfg["view"]["lat"][1]):
                x, y = project(lon, lat); xs.append(x); ys.append(y)
        ax.set_xlim(min(xs) - pad, max(xs) + pad); ax.set_ylim(min(ys) - pad, max(ys) + pad)
    else:
        ax.autoscale_view()
    ink = "#EAECEF" if dark else "#1B2430"
    if title:
        ax.set_title(title, fontsize=15, color=ink, loc="left", pad=8, fontweight="bold")
    if legend:
        _draw_colorbar(fig, ax, cmap, norm, lo, hi, ink, legend_label)
    fig.savefig(out_png, transparent=True, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return out_png


def _draw_colorbar(fig, ax, cmap, norm, lo, hi, ink, label):
    """A slim horizontal gradient bar with lo/mid/hi ticks — reads at a glance, deck-clean."""
    import numpy as np
    cax = fig.add_axes([0.12, 0.06, 0.30, 0.028])
    grad = np.linspace(0, 1, 256).reshape(1, -1)
    cax.imshow(grad, aspect="auto", cmap=cmap, extent=[0, 1, 0, 1])
    cax.set_yticks([])
    for spine in cax.spines.values():
        spine.set_visible(False)
    mid = (lo + hi) / 2
    def fmt(v):
        if not math.isfinite(v):
            return "—"
        return f"{v:.0f}" if abs(v) >= 10 or v == int(v) else f"{v:.1f}"
    cax.set_xticks([0, 0.5, 1]); cax.set_xticklabels([fmt(lo), fmt(mid), fmt(hi)], fontsize=9, color=ink)
    cax.tick_params(length=0, pad=2)
    if label:
        cax.set_title(label, fontsize=9, color=ink, loc="left", pad=3)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Render a choropleth PNG from {region: value} JSON.")
    ap.add_argument("mapname", choices=list(MAPS))
    ap.add_argument("data_json", help="path to a JSON file of {region_key: value}")
    ap.add_argument("out", help="output PNG")
    ap.add_argument("--accent", default="#1F5FA8")
    ap.add_argument("--scale", default="seq", choices=["seq", "div"])
    ap.add_argument("--title", default=None)
    a = ap.parse_args()
    d = json.load(open(a.data_json, encoding="utf-8"))
    print("wrote", choropleth_png(a.out, d, a.mapname, accent=a.accent, scale=a.scale, title=a.title))
