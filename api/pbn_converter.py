#!/usr/bin/env python3
"""
HUE & HUSH — Paint-by-Numbers Converter (v2, clean-boundary)
============================================================
Turns any source image into a complete paint-by-numbers kit:

  1. <name>_preview.png   — the colour-reduced "finished art" (box / website image)
  2. <name>_template.png  — the printable numbered canvas (outlines + numbers)
  3. <name>_legend.png    — colour swatches mapped to numbers + paint names
  4. <name>_paints.csv    — the paint spec (number, hex, RGB, suggested paint name)

Clean-boundary pipeline:
  • cluster colours in LAB (perceptual) so shades map the way the eye sees them
  • keep the SOURCE edges sharp (no pre-blur that smears boundaries)
  • clean up by MAJORITY-VOTE smoothing the label map -> smooth contours that
    follow the real image, instead of wandering geometric fills
  • dissolve leftover specks into the dominant neighbouring colour

Usage:
    python3 pbn_converter.py INPUT.jpg --difficulty beginner --name "Sakura Pagoda"
    python3 pbn_converter.py --demo
"""

import argparse, csv, os, colorsys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from sklearn.cluster import KMeans
from scipy import ndimage
from skimage import segmentation, color as skcolor, measure, graph as skgraph
try:
    from pykuwahara import kuwahara as _kuwahara
    _HAS_KUWAHARA = True
except Exception:
    _HAS_KUWAHARA = False
try:
    import cairosvg as _cairosvg
    _HAS_CAIROSVG = True
except Exception:
    _HAS_CAIROSVG = False

# ----------------------------------------------------------------------
# Difficulty presets
#   colors        : palette size
#   min_region    : smallest paintable region (fraction of total pixels)
#   smooth_size   : majority-vote window — BIGGER = cleaner/calmer boundaries
#   smooth_passes : how many smoothing passes
#   number_min    : smallest region that gets a printed number
# ----------------------------------------------------------------------
#   colors      : palette size
#   scale       : felzenszwalb region scale — BIGGER = larger, simpler regions
#   fz_min      : felzenszwalb minimum segment size (px) before palette mapping
#   n_segments / compactness / rag_thresh : SLIC + RAG hierarchical merge params
#                 (the DEFAULT segmentation — A/B-tested better than felzenszwalb:
#                 equal ΔE/SSIM/edge, far better region thickness / paintability)
#   min_region  : smallest paintable region kept after mapping (frac of pixels)
#   number_min  : region size above which EXTRA repeat numbers are added
#                 (every facet always gets at least one number regardless)
PRESETS = {
    "beginner":     dict(colors=20, scale=240, fz_min=140, n_segments=900,  compactness=14, rag_thresh=22, min_region=0.00110, number_min=0.0020, kuwahara=4, max_facets=130),
    "intermediate": dict(colors=27, scale=170, fz_min=90,  n_segments=1600, compactness=13, rag_thresh=17, min_region=0.00060, number_min=0.0012, kuwahara=3, max_facets=200),
    "signature":    dict(colors=30, scale=95,  fz_min=48,  n_segments=2400, compactness=12, rag_thresh=14, min_region=0.00045, number_min=0.0009, kuwahara=3, max_facets=260),
    "advanced":     dict(colors=40, scale=85,  fz_min=38,  n_segments=3600, compactness=10, rag_thresh=11, min_region=0.00028, number_min=0.0007, kuwahara=2, max_facets=450),
}
DEFAULT_DIFFICULTY = "signature"   # ~30 colours: faithful but paintable

TARGET_LONG_EDGE = 1000
KMEANS_SAMPLE = 45000


# ----------------------------------------------------------------------
# Paint naming
# ----------------------------------------------------------------------
HUE_NAMES = [(15,"Red"),(40,"Amber"),(65,"Gold"),(95,"Olive"),(150,"Green"),
             (185,"Teal"),(215,"Blue"),(260,"Indigo"),(290,"Violet"),(330,"Rose"),(360,"Red")]
def paint_name(rgb):
    r,g,b = [c/255.0 for c in rgb]
    h,s,v = colorsys.rgb_to_hsv(r,g,b); hue=h*360
    if s < 0.10:
        return ("Ink Black" if v<0.18 else "Charcoal" if v<0.40 else
                "Stone Grey" if v<0.65 else "Soft Linen" if v<0.88 else "Canvas White")
    base = next(name for limit,name in HUE_NAMES if hue<=limit)
    if v<0.35: tone="Deep "
    elif v>0.85 and s<0.45: tone="Pale "
    elif s>0.70 and v>0.7: tone="Bright "
    elif s<0.40: tone="Muted "
    else: tone="Warm " if hue<70 or hue>320 else "Soft "
    return tone+base


# ----------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------
def load_and_prep(path, kuwahara_radius=3):
    img = Image.open(path).convert("RGB")
    w,h = img.size
    scale = TARGET_LONG_EDGE/max(w,h)
    if scale < 1:
        img = img.resize((round(w*scale), round(h*scale)), Image.LANCZOS)
    # Anisotropic (gaussian) Kuwahara abstraction — flattens texture ALONG feature
    # directions while keeping edges crisp (Kyprianidis 2009). Measurably better
    # structure (SSIM) than a plain median/bilateral. Falls back gracefully.
    if _HAS_KUWAHARA and kuwahara_radius and kuwahara_radius > 0:
        arr = np.clip(_kuwahara(np.asarray(img), method="gaussian", radius=int(kuwahara_radius)), 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
    else:
        img = img.filter(ImageFilter.MedianFilter(size=3))
    return img


def load_resized_gray(path):
    """Original (pre-abstraction) at working resolution, as float grayscale —
    used for detail-line extraction so we catch the FULL fine detail."""
    img = Image.open(path).convert("RGB"); w,h = img.size
    s = TARGET_LONG_EDGE/max(w,h)
    if s < 1: img = img.resize((round(w*s), round(h*s)), Image.LANCZOS)
    return skcolor.rgb2gray(np.asarray(img))


def xdog_lines(gray, sigma=0.9, k=1.6, tau=0.985, phi=200.0, eps=0.0):
    """eXtended Difference-of-Gaussians line extraction (Winnemöller 2011).
    Returns a 0..1 map: ~1 = flat area, <1 = structural ink line. This recovers
    the thin dark detail (branches, lattice, railings) that flat fills lose."""
    from scipy.ndimage import gaussian_filter
    g1 = gaussian_filter(gray, sigma); g2 = gaussian_filter(gray, sigma*k)
    d = g1 - tau*g2
    return np.where(d >= eps, 1.0, 1.0 + np.tanh(phi*(d - eps)))


def apply_detail(rgb_arr, u, floor):
    """Multiply-darken an image by the XDoG map (clamped so lines are grey→black
    but never pure black); floor sets how dark the lines get."""
    return (rgb_arr.astype(np.float32) * np.clip(u, floor, 1.0)[..., None]).astype(np.uint8)


def segment_quantize(img, n_colors, scale, fz_min):
    """Edge-respecting segmentation, THEN colour.

    1. Felzenszwalb groups neighbouring pixels that belong to the same shape
       into coherent regions whose borders follow the real edges in the image.
    2. Each region's average colour is clustered (area-weighted) into the
       palette, and the whole region is painted that single colour.

    Result: clean, closed, paintable regions that look like the original —
    instead of pixel-level colour blobs that ignore the picture's shapes."""
    arr = np.asarray(img)
    seg = segmentation.felzenszwalb(arr, scale=scale, sigma=0.6, min_size=fz_min)
    nseg = int(seg.max()) + 1
    lab = skcolor.rgb2lab(arr)
    mean_lab = np.stack([ndimage.mean(lab[:, :, c], seg, range(nseg)) for c in range(3)], axis=1)
    sizes = np.bincount(seg.ravel(), minlength=nseg).astype(float)
    # Accent weighting: weight by sqrt(area), not area, so small but important
    # high-contrast regions (highlights, dark accents, spire) keep a palette slot
    # instead of being averaged into the dominant colours.
    weight = sizes ** 0.5
    n = min(n_colors, nseg)
    km = KMeans(n_clusters=n, n_init=4, random_state=42).fit(mean_lab, sample_weight=weight)
    labels = km.predict(mean_lab)[seg]          # per-pixel palette index, regions follow edges
    return labels


def _palette_map(arr, seg, n_colors):
    """Shared colour step: mean LAB per segment -> area-weighted KMeans ->
    per-pixel palette index (regions keep their segmentation borders)."""
    nseg = int(seg.max()) + 1
    lab = skcolor.rgb2lab(arr)
    mean_lab = np.stack([ndimage.mean(lab[:, :, c], seg, range(nseg)) for c in range(3)], axis=1)
    sizes = np.bincount(seg.ravel(), minlength=nseg).astype(float)
    weight = sizes ** 0.5                        # accent weighting (see segment_quantize)
    n = min(n_colors, nseg)
    km = KMeans(n_clusters=n, n_init=4, random_state=42).fit(mean_lab, sample_weight=weight)
    return km.predict(mean_lab)[seg]


def segment_quantize_slic(img, n_colors, n_segments, compactness, rag_thresh):
    """DEFAULT segmentation: SLIC superpixels -> Region-Adjacency-Graph
    hierarchical merging (mean-colour) -> palette mapping.

    A/B-tested vs felzenszwalb on the 4 kit images (signature preset):
    equal-or-better ΔE/SSIM/edge, and much better paintability — SLIC's
    compactness prior gives rounder, more uniform regions (worst inscribed
    radius 5.0px vs 1.0px; zero facets thinner than 5px)."""
    arr = np.asarray(img)
    sp = segmentation.slic(arr, n_segments=n_segments, compactness=compactness,
                           sigma=0.8, start_label=0, channel_axis=-1)
    g = skgraph.rag_mean_color(arr, sp)

    def _merge_mean(g_, src, dst):
        g_.nodes[dst]['total color'] += g_.nodes[src]['total color']
        g_.nodes[dst]['pixel count'] += g_.nodes[src]['pixel count']
        g_.nodes[dst]['mean color'] = g_.nodes[dst]['total color'] / g_.nodes[dst]['pixel count']

    def _weight_mean(g_, src, dst, n):
        return {'weight': float(np.linalg.norm(g_.nodes[dst]['mean color'] - g_.nodes[n]['mean color']))}

    merged = skgraph.merge_hierarchical(sp, g, thresh=rag_thresh, rag_copy=False,
                                        in_place_merge=True,
                                        merge_func=_merge_mean, weight_func=_weight_mean)
    merged = np.unique(merged, return_inverse=True)[1].reshape(merged.shape)
    return _palette_map(arr, merged, n_colors)


def dissolve_specks(labels, n, min_area):
    """Any connected region below min_area is merged into its dominant
    neighbouring colour, following the actual boundary."""
    labels = labels.copy()
    for _ in range(2):
        changed = 0
        for k in range(n):
            mask = labels==k
            if not mask.any(): continue
            comp, nc = ndimage.label(mask)
            if nc==0: continue
            sizes = np.bincount(comp.ravel())
            slices = ndimage.find_objects(comp)
            for ci in range(1, nc+1):
                if sizes[ci] >= min_area: continue
                sl = slices[ci-1]
                pad = (slice(max(0,sl[0].start-1), sl[0].stop+1),
                       slice(max(0,sl[1].start-1), sl[1].stop+1))
                region = comp[pad]==ci
                local = labels[pad]
                ring = ndimage.binary_dilation(region) & ~region
                neigh = local[ring]; neigh = neigh[neigh!=k]
                if neigh.size:
                    labels[pad][region] = np.bincount(neigh).argmax()
                    changed += 1
        if not changed: break
    return labels


def clean_facets(labels, n, min_area, min_thick=2.2, max_facets=None):
    """Facet cleanup (à la the reference generator):
      • dissolve facets smaller than `min_area`
      • dissolve NARROW strips — facets whose max inscribed radius < `min_thick`
        (these are the single-pixel slivers in water/foliage that are impossible
        to paint), merging each into its dominant neighbour
      • optionally cap total facet count by raising the size floor
    Iterated until NO facet violates the floor/thickness constraints (with a
    safety cap) — a merge can expose new slivers, so exiting after a fixed
    number of passes used to let 1px slivers survive."""
    labels = labels.copy()
    floor = min_area
    for it in range(14):
        changed = 0
        for k in range(n):
            mask = labels == k
            if not mask.any(): continue
            comp, nc = ndimage.label(mask)
            if nc == 0: continue
            sizes = np.bincount(comp.ravel()); slices = ndimage.find_objects(comp)
            for ci in range(1, nc+1):
                sl = slices[ci-1]; sub = comp[sl] == ci
                area = sizes[ci]
                # pad before EDT: an unpadded mask that fills its bbox has no
                # background pixels, so EDT returns nonsense (inflated) values —
                # this let 1px slivers masquerade as thick and survive cleanup
                thick = ndimage.distance_transform_edt(np.pad(sub, 1)).max() if area else 0
                if area >= floor and thick >= min_thick: continue
                pad = (slice(max(0,sl[0].start-1), sl[0].stop+1),
                       slice(max(0,sl[1].start-1), sl[1].stop+1))
                region = comp[pad] == ci; local = labels[pad]
                ring = ndimage.binary_dilation(region) & ~region
                neigh = local[ring]; neigh = neigh[neigh != k]
                if neigh.size:
                    labels[pad][region] = np.bincount(neigh).argmax(); changed += 1
        # enforce a max facet budget by gradually raising the floor
        if max_facets is not None:
            nfac = sum(int(ndimage.label(labels==k)[1]) for k in range(n))
            if nfac > max_facets:
                floor = int(floor * 1.5); changed += 1
        if not changed: break
    return labels


def trace_facets(labels):
    """Vectorise: trace every facet's boundary into simplified polygons
    (marching squares + Douglas–Peucker). Returns [(label, [poly,...])] where
    each poly is an (N,2) array of (x,y) points."""
    facets = []
    for k in range(int(labels.max())+1):
        mask = labels == k
        if not mask.any(): continue
        comp, nc = ndimage.label(mask)
        slices = ndimage.find_objects(comp)
        for ci in range(1, nc+1):
            sl = slices[ci-1]
            y0, x0 = sl[0].start, sl[1].start
            sub = np.pad((comp[sl] == ci).astype(float), 1)
            polys = []
            for c in measure.find_contours(sub, 0.5):
                c = measure.approximate_polygon(c, tolerance=1.0)   # smooth/simplify
                if len(c) >= 3:
                    polys.append(np.column_stack([c[:,1]-1+x0, c[:,0]-1+y0]))  # ->(x,y)
            if polys:
                facets.append((k, polys))
    return facets


def make_svg(labels, palette, placements, filled):
    """Return a scalable-vector string. filled=True -> finished-art; filled=False
    -> numbered template (border strokes + numbers)."""
    h, w = labels.shape
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}" shape-rendering="geometricPrecision">',
           f'<rect width="{w}" height="{h}" fill="#ffffff"/>']
    for k, polys in trace_facets(labels):
        d = ""
        for poly in polys:
            d += "M" + " L".join(f"{x:.1f},{y:.1f}" for x,y in poly) + " Z "
        if filled:
            col = "#%02X%02X%02X" % tuple(int(v) for v in palette[k])
            out.append(f'<path d="{d}" fill="{col}" fill-rule="evenodd" stroke="{col}" stroke-width="0.6"/>')
        else:
            out.append(f'<path d="{d}" fill="none" stroke="#5a5a5a" stroke-width="0.8" stroke-linejoin="round"/>')
    if not filled:
        for x, y, num, clr, leader in placements:
            if leader is not None:
                tx, ty = leader
                # shorten the line so it stops at the label's edge, not under the digits
                dx, dy = tx-x, ty-y; L = math.hypot(dx, dy) or 1.0
                sx, sy = x + dx/L*5.5, y + dy/L*5.5
                out.append(f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" '
                           f'stroke="#5a5a5a" stroke-width="0.6"/>')
                fs = 7.5                              # fixed legible size for leader labels
            else:
                fs = max(6.0, min(15, clr*1.15))      # sized to the region, never illegible
            out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="Helvetica,Arial,sans-serif" '
                       f'font-size="{fs:.1f}" fill="#333333" text-anchor="middle" '
                       f'dominant-baseline="central">{num}</text>')
    out.append("</svg>")
    return "\n".join(out)


def compact_and_palette(labels, rgb, n):
    """Drop empty labels, relabel 0..M-1, and compute a faithful RGB palette
    (mean of the original pixels in each region)."""
    present = [k for k in range(n) if (labels==k).any()]
    remap = {k:i for i,k in enumerate(present)}
    new = np.zeros_like(labels)
    palette = []
    for k in present:
        m = labels==k
        new[m] = remap[k]
        palette.append(rgb[m].mean(axis=0))
    return new, np.array(palette).astype(np.uint8)


def order_by_lightness(labels, palette):
    lum = palette.astype(float) @ np.array([0.299,0.587,0.114])
    order = np.argsort(lum)
    remap = np.zeros(len(palette), int)
    for new_i, old_i in enumerate(order): remap[old_i]=new_i
    return remap[labels], palette[order]


_FONT_CACHE={}
def _font(fp,size):
    key=(fp,size)
    if key not in _FONT_CACHE:
        try: _FONT_CACHE[key]=ImageFont.truetype(fp,size)
        except Exception: _FONT_CACHE[key]=ImageFont.load_default()
    return _FONT_CACHE[key]


def fit_number(draw, text, clr, font_path, max_fs, min_fs=6):
    """Largest font whose rendered digits fit inside the inscribed circle of
    radius `clr` (so the number never crosses the region border). Returns
    (font, width, height, bbox) or None if even the smallest legible size
    won't fit — i.e. the region is too thin to be numbered."""
    hi = int(min(max_fs, clr*2.4))
    for fs in range(hi, min_fs-1, -1):
        f = _font(font_path, fs)
        tb = draw.textbbox((0,0), text, font=f)
        w, h = tb[2]-tb[0], tb[3]-tb[1]
        if 0.5*math.hypot(w, h) <= clr*0.90:      # half-diagonal fits in the circle
            return f, w, h, tb
    return None


def outline_mask(labels):
    h,w = labels.shape
    diff = np.zeros((h,w),bool)
    diff[:,:-1] |= labels[:,:-1]!=labels[:,1:]
    diff[:-1,:] |= labels[:-1,:]!=labels[1:,:]
    return diff


LEGIBLE_CLR = 4.5   # inscribed radius (px @ working res) needed to hold a legible in-region digit

def number_placements(labels, palette, repeat_area):
    """Return ([(x, y, paint_no, clearance, leader)], qa) in label-grid coords.

    GUARANTEE: every connected facet gets exactly ONE primary number — no size
    gate. Facets whose inscribed radius can't hold a legible digit get a
    LEADER LINE: the number sits just outside with a thin line pointing to the
    facet (standard in commercial PBN). `leader` is None for in-region numbers
    or (tx, ty) — the facet anchor the line points to. Large regions get a few
    well-spaced repeat numbers. A QA assertion (#facets == #primaries) runs on
    every call so a preset/image change can never silently drop numbers again."""
    h, w = labels.shape
    free = ndimage.distance_transform_edt(~outline_mask(labels))  # room anywhere on canvas
    placements = []
    occupied = []   # (x, y, r) of every placed label, for collision avoidance

    def collides(x, y, r):
        return any((x-px)**2 + (y-py)**2 < (r+pr)**2 for px, py, pr in occupied)

    facets = primaries = leaders = 0
    for k in range(len(palette)):
        mask = labels == k
        if not mask.any(): continue
        comp, nc = ndimage.label(mask)
        if nc == 0: continue
        sizes = np.bincount(comp.ravel()); slices = ndimage.find_objects(comp)
        for ci in range(1, nc+1):
            facets += 1
            area = sizes[ci]
            sl = slices[ci-1]; sub = comp[sl] == ci
            dist = ndimage.distance_transform_edt(np.pad(sub, 1))[1:-1, 1:-1]  # padded EDT (see clean_facets)
            y0, x0 = sl[0].start, sl[1].start
            ly, lx = np.unravel_index(dist.argmax(), dist.shape); rmax = float(dist[ly, lx])
            gx, gy = x0+lx, y0+ly                    # most-interior point of the facet
            if rmax >= LEGIBLE_CLR:
                placements.append((gx, gy, k+1, rmax, None)); primaries += 1
                occupied.append((gx, gy, max(rmax, 6.0)))
                if area > 16*repeat_area and rmax >= 5:   # repeats only in big regions
                    pts = [(lx, ly)]
                    step = max(12, int(rmax*1.6)); cands = []
                    for yy in range(0, sub.shape[0], step):
                        for xx in range(0, sub.shape[1], step):
                            d = float(dist[yy, xx])
                            if d >= max(5, 0.55*rmax): cands.append((xx, yy, d))
                    cands.sort(key=lambda t: -t[2]); minsep = max(rmax*3.0, 30)
                    for xx, yy, d in cands:
                        if all((xx-px)**2 + (yy-py)**2 >= minsep*minsep for px, py in pts):
                            pts.append((xx, yy))
                            placements.append((x0+xx, y0+yy, k+1, d, None))
                            occupied.append((x0+xx, y0+yy, max(d, 6.0)))
                        if len(pts) >= 6: break
            else:
                # too thin for an in-region digit -> leader line
                best = None
                for rad in (9, 13, 18, 24, 31, 40):
                    for ang in range(0, 360, 30):
                        cx = int(round(gx + rad*math.cos(math.radians(ang))))
                        cy = int(round(gy + rad*math.sin(math.radians(ang))))
                        if not (7 <= cx < w-7 and 7 <= cy < h-7): continue
                        c = float(free[cy, cx])
                        if c < 4.0 or collides(cx, cy, 7.0): continue
                        if best is None or c > best[2]:
                            best = (cx, cy, c)
                    if best is not None and best[2] >= 5.0: break
                if best is None:                     # crowded corner — place on top anyway
                    best = (min(max(gx, 8), w-8), min(max(gy, 8), h-8), 4.0)
                placements.append((best[0], best[1], k+1, 5.0, (gx, gy)))
                occupied.append((best[0], best[1], 8.0))
                primaries += 1; leaders += 1
    qa = dict(facets=facets, primaries=primaries, leaders=leaders,
              repeats=len(placements)-primaries)
    if qa["facets"] != qa["primaries"]:
        raise RuntimeError(f"NUMBERING QA FAILED: {qa['facets']} facets but "
                           f"{qa['primaries']} primary numbers")
    return placements, qa


def build_template(labels, palette, number_min_area, font_path, line=(90,90,90), detail_u=None):
    """Screen-resolution numbered template, with optional faint XDoG detail lines
    (printed on the canvas to guide fine detail like branches/lattice)."""
    h,w = labels.shape
    arr = np.full((h,w,3),255,np.uint8); arr[outline_mask(labels)]=line
    if detail_u is not None:
        arr = apply_detail(arr, detail_u, floor=0.55)     # faint grey guide lines
        arr[outline_mask(labels)] = line                  # keep region borders crisp
    canvas = Image.fromarray(arr); draw = ImageDraw.Draw(canvas)
    W,H = canvas.size
    placements,qa = number_placements(labels, palette, number_min_area)
    for x,y,num,clr,leader in placements:
        t=str(num)
        if leader is not None:                        # leader-line label (tiny facet)
            tx,ty=leader
            dx,dy=tx-x,ty-y; L=math.hypot(dx,dy) or 1.0
            draw.line([(x+dx/L*5.5, y+dy/L*5.5),(tx,ty)], fill=(90,90,90), width=1)
            f=_font(font_path,8); tb=draw.textbbox((0,0),t,font=f); w,h=tb[2]-tb[0],tb[3]-tb[1]
            draw.rectangle([x-w/2-1,y-h/2-1,x+w/2+1,y+h/2+1], fill=(255,255,255))  # halo
        else:
            fit=fit_number(draw, t, clr, font_path, max_fs=16, min_fs=6)
            if fit is None:                           # shouldn't happen (LEGIBLE_CLR gate)
                f=_font(font_path,6); tb=draw.textbbox((0,0),t,font=f); w,h=tb[2]-tb[0],tb[3]-tb[1]
            else:
                f,w,h,tb=fit
        px=min(max(x-w/2-tb[0], 2), W-w-2)            # centre, then clamp inside canvas
        py=min(max(y-h/2-tb[1], 2), H-h-2)
        draw.text((px,py), t, fill=(35,35,35), font=f)   # dark for clear visibility
    return canvas, qa, placements


def build_legend(palette, font_path, cols=5):
    n=len(palette); rows=(n+cols-1)//cols
    cw,ch,pad=232,72,18
    W=cols*cw+pad; H=rows*ch+pad+64
    img=Image.new("RGB",(W,H),(251,248,241)); d=ImageDraw.Draw(img)
    tf=_font(font_path,26); f=_font(font_path,16); s=_font(font_path,12)
    d.text((pad,20),"Colour key — Hue & Hush",fill=(43,40,35),font=tf)
    for i,rgb in enumerate(palette):
        r,c=divmod(i,cols)
        x=pad+c*cw; y=64+r*ch
        d.rectangle([x,y,x+46,y+46],fill=tuple(int(v) for v in rgb),outline=(210,200,185))
        d.text((x+58,y+4),f"#{i+1}  {paint_name(rgb)}",fill=(43,40,35),font=f)
        d.text((x+58,y+27),"#%02X%02X%02X"%tuple(int(v) for v in rgb),fill=(110,102,92),font=s)
    return img


def build_print_sheet(labels, palette, placements, name, long_cm, dpi, font_path):
    """Production-ready printable canvas: high-DPI numbered outline at the true
    physical size, brand header, colour legend along the bottom border, and crop
    marks. Returned as a PIL image ready to save as PDF/PNG."""
    h,w = labels.shape
    # physical canvas pixels (preserve aspect; long_cm is the LONGER edge)
    if w >= h:
        cw = round(long_cm/2.54*dpi); ch = round(cw*h/w)
    else:
        ch = round(long_cm/2.54*dpi); cw = round(ch*w/h)

    # upscale label map (nearest) -> crisp outlines at print resolution
    lab_img = Image.fromarray(labels.astype(np.uint16)).resize((cw,ch), Image.NEAREST)
    big = np.asarray(lab_img).astype(np.int32)
    diff = outline_mask(big)
    line_w = max(2, round(dpi/170))                 # ~0.4 mm lines
    if line_w > 1:
        diff = ndimage.binary_dilation(diff, iterations=line_w-1)
    canvas = np.full((ch,cw,3),255,np.uint8); canvas[diff]=(70,70,70)
    tmpl = Image.fromarray(canvas); d=ImageDraw.Draw(tmpl)

    sx, sy = cw/w, ch/h
    for x,y,num,clr,leader in placements:
        t=str(num)
        if leader is not None:                        # leader-line label at print scale
            tx,ty=leader
            dx,dy=tx-x,ty-y; L=math.hypot(dx,dy) or 1.0
            d.line([((x+dx/L*5.5)*sx,(y+dy/L*5.5)*sy),(tx*sx,ty*sy)],
                   fill=(90,90,90), width=max(1,line_w-1))
            f=_font(font_path,max(8,int(dpi*0.026))); tb=d.textbbox((0,0),t,font=f)
            tw,th=tb[2]-tb[0],tb[3]-tb[1]
            d.rectangle([x*sx-tw/2-2,y*sy-th/2-2,x*sx+tw/2+2,y*sy+th/2+2], fill=(255,255,255))
        else:
            fit=fit_number(d, t, clr*sx, font_path, max_fs=int(dpi*0.08), min_fs=int(dpi*0.018))
            if fit is None:
                f=_font(font_path,max(6,int(dpi*0.018))); tb=d.textbbox((0,0),t,font=f); tw,th=tb[2]-tb[0],tb[3]-tb[1]
            else:
                f,tw,th,tb=fit
        d.text((x*sx-tw/2-tb[0], y*sy-th/2-tb[1]), t, fill=(60,60,60), font=f)

    # page = canvas + margins for header, legend, crop marks
    m = round(0.06*cw)
    legend_rows = (len(palette)+7)//8
    legend_h = legend_rows*round(0.05*cw) + round(0.02*cw)
    PW, PH = cw+2*m, ch+2*m+legend_h+round(0.05*cw)
    page = Image.new("RGB",(PW,PH),(255,255,255)); pd=ImageDraw.Draw(page)
    ox, oy = m, m+round(0.05*cw)
    page.paste(tmpl,(ox,oy))

    # header
    hf=_font(font_path,round(0.028*cw)); sf=_font(font_path,round(0.014*cw))
    pd.text((m,round(0.012*cw)), f"HUE & HUSH  ·  {name}", fill=(43,40,35), font=hf)
    pd.text((m,round(0.012*cw)+round(0.032*cw)),
            f"{len(palette)} colours · {long_cm:.0f} cm long edge · paint-by-numbers template",
            fill=(120,112,100), font=sf)

    # crop marks
    cl=round(0.025*cw)
    for (cx,cy) in [(ox,oy),(ox+cw,oy),(ox,oy+ch),(ox+cw,oy+ch)]:
        pd.line([(cx-cl,cy),(cx+cl,cy)], fill=(0,0,0), width=2)
        pd.line([(cx,cy-cl),(cx,cy+cl)], fill=(0,0,0), width=2)

    # legend strip along the bottom border
    ly0 = oy+ch+round(0.03*cw); sw=round(0.032*cw); col_w=cw//8
    lf=_font(font_path,round(0.012*cw))
    for i,rgb in enumerate(palette):
        r,c=divmod(i,8); x=m+c*col_w; y=ly0+r*round(0.05*cw)
        pd.rectangle([x,y,x+sw,y+sw],fill=tuple(int(v) for v in rgb),outline=(180,170,155))
        pd.text((x+sw+round(0.008*cw), y+sw*0.12), f"{i+1}", fill=(43,40,35), font=lf)
    return page


def write_csv(path, palette, counts):
    total=counts.sum()
    with open(path,"w",newline="") as fh:
        wr=csv.writer(fh); wr.writerow(["paint_no","suggested_name","hex","R","G","B","coverage_%"])
        for i,rgb in enumerate(palette):
            r,g,b=(int(v) for v in rgb)
            wr.writerow([i+1,paint_name(rgb),"#%02X%02X%02X"%(r,g,b),r,g,b,round(100*counts[i]/total,2)])


def convert(input_path, out_dir, name, difficulty, font_path, print_ready=False, size_cm=50, dpi=300, all_outputs=False, seg="slic"):
    p=PRESETS[difficulty]
    base=os.path.join(out_dir,f"{name}_{difficulty}".replace(" ","_"))
    img=load_and_prep(input_path, kuwahara_radius=p.get("kuwahara",3))
    rgb=np.asarray(img)
    npix=rgb.shape[0]*rgb.shape[1]
    min_area=max(60,int(npix*p["min_region"]))
    number_min=max(120,int(npix*p["number_min"]))   # threshold for EXTRA repeats only

    if seg=="slic":
        labels=segment_quantize_slic(img,p["colors"],p["n_segments"],p["compactness"],p["rag_thresh"])
    else:
        labels=segment_quantize(img,p["colors"],p["scale"],p["fz_min"])
    labels=clean_facets(labels,p["colors"],min_area,min_thick=3.2,max_facets=p.get("max_facets"))
    labels,palette=compact_and_palette(labels,rgb,p["colors"])
    labels,palette=order_by_lightness(labels,palette)
    counts=np.bincount(labels.ravel(),minlength=len(palette))

    # XDoG detail-line layer from the ORIGINAL (recovers thin dark structure)
    detail_u=None
    if p.get("detail",True):
        xp=p.get("xdog",{})
        detail_u=xdog_lines(load_resized_gray(input_path), **xp)

    tmpl,qa,placements=build_template(labels,palette,number_min,font_path,detail_u=None)

    # ---- ESSENTIALS (always) ----
    prev=palette[labels].astype(np.uint8)
    if detail_u is not None:
        prev=apply_detail(prev, detail_u, floor=0.18)     # finished-art with detail lines
    Image.fromarray(prev).save(base+"_preview.png")       # 1. finished-art / product image
    build_legend(palette,font_path).save(base+"_legend.png")   # 2. colour key
    write_csv(base+"_paints.csv",palette,counts)          # 3. paint spec
    template_svg = make_svg(labels, palette, placements, filled=False)
    if _HAS_CAIROSVG:                                     # 4. clean vector print PDF (the canvas)
        _cairosvg.svg2pdf(bytestring=template_svg.encode(), write_to=base+"_template.pdf")
    else:
        with open(base+"_template.svg","w") as f: f.write(template_svg)

    # ---- EXTRAS (only with --all) ----
    if all_outputs:
        tmpl.save(base+"_template.png")
        with open(base+"_template.svg","w") as f: f.write(template_svg)
        with open(base+"_preview.svg","w") as f: f.write(make_svg(labels,palette,placements,filled=True))
        if print_ready:
            sheet=build_print_sheet(labels,palette,placements,name,size_cm,dpi,font_path)
            sheet.save(base+"_PRINT_sheet.pdf","PDF",resolution=float(dpi))

    print(f"  [{difficulty:>12}] {len(palette)} colours · {qa['facets']} pieces · "
          f"QA {qa['facets']}/{qa['primaries']} numbered "
          f"({qa['leaders']} leader-lined, {qa['repeats']} repeats) OK · {os.path.basename(base)}_*")
    return base


# ----------------------------------------------------------------------
def make_demo_image(path):
    W,H=1000,800; img=Image.new("RGB",(W,H)); px=img.load()
    for y in range(H):
        t=y/H; top=(250,214,160); mid=(224,138,120); bot=(94,75,102)
        c=(tuple(int(top[i]+(mid[i]-top[i])*(t/0.5)) for i in range(3)) if t<0.5
           else tuple(int(mid[i]+(bot[i]-mid[i])*((t-0.5)/0.5)) for i in range(3)))
        for x in range(W): px[x,y]=c
    d=ImageDraw.Draw(img,"RGBA"); d.ellipse([620,120,800,300],fill=(255,236,180,220))
    d.ellipse([650,150,770,270],fill=(255,246,210,255))
    for cx,cy,s,col in [(250,600,120,(90,130,95)),(500,660,150,(70,110,85)),(760,610,110,(95,135,100))]:
        d.ellipse([cx-s,cy-s//3,cx+s,cy+s//3],fill=col+(255,))
    img=img.filter(ImageFilter.GaussianBlur(2)); img.save(path); return path

def find_font():
    for c in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(c): return c
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input",nargs="?"); ap.add_argument("--difficulty",choices=list(PRESETS),default=DEFAULT_DIFFICULTY)
    ap.add_argument("--name",default="design"); ap.add_argument("--out",default="."); ap.add_argument("--demo",action="store_true")
    ap.add_argument("--all",dest="all_outputs",action="store_true",help="also export extras (PNG template, SVGs, branded print sheet)")
    ap.add_argument("--print",dest="print_ready",action="store_true",help="with --all, include the branded 300 DPI print sheet")
    ap.add_argument("--size-cm",type=float,default=50,help="long edge of the physical canvas in cm")
    ap.add_argument("--dpi",type=int,default=300)
    ap.add_argument("--batch",help="folder of images; each becomes its own subfolder of kit files")
    ap.add_argument("--seg",choices=["slic","felz"],default="slic",help="segmentation backend (slic = SLIC+RAG, default; felz = legacy felzenszwalb)")
    a=ap.parse_args(); os.makedirs(a.out,exist_ok=True); font=find_font()
    if a.demo:
        demo=os.path.join(a.out,"_sample_source.png"); make_demo_image(demo)
        for d in PRESETS: convert(demo,a.out,"Lotus at Dawn",d,font)
        return
    if a.batch:
        import glob
        exts=(".png",".jpg",".jpeg",".webp")
        imgs=sorted(f for f in glob.glob(os.path.join(a.batch,"*")) if f.lower().endswith(exts))
        if not imgs: ap.error(f"no images found in {a.batch}")
        print(f"Batch: {len(imgs)} image(s) -> {a.out}/<name>/")
        for f in imgs:
            stem=os.path.splitext(os.path.basename(f))[0]
            name=stem.replace("_"," ").replace("-"," ").title()
            sub=os.path.join(a.out, stem); os.makedirs(sub, exist_ok=True)
            convert(f, sub, name, a.difficulty, font,
                    print_ready=a.print_ready, size_cm=a.size_cm, dpi=a.dpi, all_outputs=a.all_outputs, seg=a.seg)
        print("Batch done.")
        return
    if not a.input: ap.error("provide an input image, --batch <folder>, or --demo")
    convert(a.input,a.out,a.name,a.difficulty,font,
            print_ready=a.print_ready,size_cm=a.size_cm,dpi=a.dpi,all_outputs=a.all_outputs,seg=a.seg); print("Done.")

if __name__=="__main__": main()
