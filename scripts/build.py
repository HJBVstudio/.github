"""Builds every SVG asset for the HJBV Studio org profile.

All 3D is computed here (real perspective projection, backface culling,
per-face lighting) and baked into SMIL/CSS animations, so the SVGs run
inside GitHub's <img> sandbox without JS, filters or external fonts.

run: python scripts/build.py   (needs fonttools + the two OFL fonts in fonts/:
  Unbounded[wght].ttf and JetBrainsMono[wght].ttf from github.com/google/fonts, saved
  as fonts/Unbounded.ttf and fonts/JetBrainsMono.ttf)
"""
import math
import os

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "profile", "assets")
FONTS = os.path.join(ROOT, "fonts")

BG = "#0A0A0B"
PANEL = "#0E0F11"
LINE = "#1E2024"
GRID = "#34373E"
BONE = "#ECE8E1"
MUTED = "#7C7F87"
LIME = "#C6FF3D"

W = 1200


def n(v):
    s = f"{v:.1f}"
    if s.endswith(".0"):
        s = s[:-2]
    return "0" if s == "-0" else s


# ---------------------------------------------------------------- fonts
class Font:
    def __init__(self, file, wght):
        f = TTFont(os.path.join(FONTS, file))
        f = instantiateVariableFont(f, {"wght": wght})
        self.gs = f.getGlyphSet()
        self.cmap = f.getBestCmap()
        self.upm = f["head"].unitsPerEm
        self.hmtx = f["hmtx"]

    def glyphs(self, text, size, x, y, tracking=0.0, anchor="start"):
        s = size / self.upm
        names = [self.cmap[ord(c)] for c in text]
        width = sum(self.hmtx[g][0] * s for g in names) + tracking * (len(text) - 1)
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        out, cx = [], x
        for c, g in zip(text, names):
            pen = SVGPathPen(self.gs, ntos=n)
            self.gs[g].draw(TransformPen(pen, (s, 0, 0, -s, cx, y)))
            adv = self.hmtx[g][0] * s
            out.append((c, pen.getCommands(), cx, adv))
            cx += adv + tracking
        return out, width

    def path(self, text, size, x, y, tracking=0.0, anchor="start"):
        gl, width = self.glyphs(text, size, x, y, tracking, anchor)
        return "".join(g[1] for g in gl), width


DISPLAY = Font("Unbounded.ttf", 700)
DISPLAY_MED = Font("Unbounded.ttf", 500)
MONO = Font("JetBrainsMono.ttf", 500)
MONO_REG = Font("JetBrainsMono.ttf", 400)


def mono(text, size, x, y, fill=MUTED, tracking=None, anchor="start", op=1, cls=""):
    tr = size * 0.18 if tracking is None else tracking
    d, _ = MONO.path(text, size, x, y, tr, anchor)
    c = f' class="{cls}"' if cls else ""
    o = f' opacity="{op}"' if op != 1 else ""
    return f'<path{c} d="{d}" fill="{fill}"{o}/>'


# ---------------------------------------------------------------- 3D math
def rot(p, yaw, pitch, roll=0.0):
    x, y, z = p
    c, s = math.cos(yaw), math.sin(yaw)
    x, z = x * c + z * s, -x * s + z * c
    c, s = math.cos(pitch), math.sin(pitch)
    y, z = y * c - z * s, y * s + z * c
    if roll:
        c, s = math.cos(roll), math.sin(roll)
        x, y = x * c - y * s, x * s + y * c
    return (x, y, z)


def norm(v):
    l = math.sqrt(sum(a * a for a in v))
    return tuple(a / l for a in v)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def lerp_hex(a, b, t):
    t = max(0.0, min(1.0, t))
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


# notched cube: [-1,1]^3 with the [0,1]^3 corner removed (the HJBV mark)
def L(axis):
    pts2 = [(-1, -1), (1, -1), (1, 0), (0, 0), (0, 1), (-1, 1)]
    out = []
    for u, v in pts2:
        p = [0, 0, 0]
        others = [i for i in range(3) if i != axis]
        p[axis] = 1
        p[others[0]], p[others[1]] = u, v
        out.append(tuple(p))
    return out


def square(axis, val, lo, hi):
    others = [i for i in range(3) if i != axis]
    out = []
    for u, v in [(lo, lo), (hi, lo), (hi, hi), (lo, hi)]:
        p = [0, 0, 0]
        p[axis] = val
        p[others[0]], p[others[1]] = u, v
        out.append(tuple(p))
    return out


def unit(axis, sign):
    v = [0, 0, 0]
    v[axis] = sign
    return tuple(v)


INNER = [(square(a, 0, 0, 1), unit(a, 1)) for a in range(3)]
OUTER = [(L(a), unit(a, 1)) for a in range(3)] + [(square(a, -1, -1, 1), unit(a, -1)) for a in range(3)]
# draw order: inner notch walls first, hull faces after (correct for any view)
FACES = [("in", p, nm) for p, nm in INNER] + [("out", p, nm) for p, nm in OUTER]

ISO_YAW = math.radians(135)
ISO_PITCH = -math.atan(1 / math.sqrt(2))


# ---------------------------------------------------------------- logo
def mark_polys(size, cx, cy, yaw=ISO_YAW, pitch=ISO_PITCH):
    """flat isometric mark: returns [(points, color)] in draw order"""
    light = norm((-0.35, 0.9, -0.55))
    out_cols = ["#2B2D33", "#8F929A", BONE]
    in_cols = ["#5E8A0A", "#93C91C", LIME]
    s = size / 2 / 1.732
    res = []
    for kind, pts, nm in FACES:
        nr = rot(nm, yaw, pitch)
        if nr[2] >= -1e-6:
            continue
        lit = dot(nr, light)
        cols = in_cols if kind == "in" else out_cols
        col = cols[0] if lit < 0.15 else cols[1] if lit < 0.6 else cols[2]
        pp = []
        for p in pts:
            r = rot(p, yaw, pitch)
            pp.append((cx + r[0] * s, cy - r[1] * s))
        res.append((pp, col))
    return res


def mark_svg(size, cx, cy, stroke=None):
    o = []
    for pp, col in mark_polys(size, cx, cy):
        d = "M" + " ".join(f"{n(x)} {n(y)}" for x, y in pp) + "Z"
        st = f' stroke="{stroke}" stroke-width="1" stroke-linejoin="round"' if stroke else f' stroke="{col}" stroke-width="0.6" stroke-linejoin="round"'
        o.append(f'<path d="{d}" fill="{col}"{st}/>')
    return "".join(o)


def build_logo():
    # square mark (avatar source)
    S = 1000
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S}" height="{S}">'
           f'<rect width="{S}" height="{S}" fill="{BG}"/>'
           f'{mark_svg(800, S / 2, S / 2)}</svg>')
    write("logo-mark.svg", svg)

    # transparent mark
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">'
           f'{mark_svg(170, 100, 100)}</svg>')
    write("mark.svg", svg)

    # horizontal lockup
    H = 200
    word, ww = DISPLAY.path("HJBV", 92, 230, 128, 2)
    sub, _ = MONO.path("STUDIO", 22, 236, 166, 12)
    wid = int(230 + ww + 40)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {wid} {H}" width="{wid}" height="{H}">'
           f'<rect width="{wid}" height="{H}" fill="{BG}"/>'
           f'{mark_svg(150, 112, 100)}'
           f'<path d="{word}" fill="{BONE}"/><path d="{sub}" fill="{LIME}"/></svg>')
    write("logo.svg", svg)


# ---------------------------------------------------------------- hero
def build_hero():
    H = 500
    F = 850.0
    CX, CY = 600.0, 250.0
    CUBE = (-2.95, 0.05, 9.4)
    FLOOR = -1.85
    N = 120
    DUR = 22
    light = norm((-0.45, 0.85, -0.55))

    def proj(p):
        return CX + F * p[0] / p[2], CY - F * p[1] / p[2]

    # ---- cube frames
    face_d = [[] for _ in FACES]
    face_vis = [[] for _ in FACES]
    face_fill = [[] for _ in FACES]
    for i in range(N + 1):
        t = i / N * 2 * math.pi
        yaw = ISO_YAW + t
        pitch = -0.42 + 0.12 * math.sin(t)
        roll = 0.05 * math.sin(2 * t)
        bob = 0.10 * math.sin(2 * t)
        for fi, (kind, pts, nm) in enumerate(FACES):
            cp = []
            for p in pts:
                r = rot(p, yaw, pitch, roll)
                cp.append((r[0] + CUBE[0], r[1] + CUBE[1] + bob, r[2] + CUBE[2]))
            nr = rot(nm, yaw, pitch, roll)
            vis = dot(nr, cp[0]) < 0
            lit = max(0.0, dot(nr, light))
            if kind == "in":
                col = lerp_hex("#2C4204", LIME, 0.25 + 0.85 * lit)
            else:
                col = lerp_hex("#121316", "#F2EEE7", 0.10 + 0.92 * lit ** 1.15)
            sp = [proj(p) for p in cp]
            face_d[fi].append("M" + " ".join(f"{n(x)} {n(y)}" for x, y in sp) + "Z")
            if i < N:
                face_vis[fi].append(1 if vis else 0)
                face_fill[fi].append(col)
    face_fill = [f + [f[0]] for f in face_fill]

    def discrete(vals, attr):
        if all(v == vals[0] for v in vals):
            return None, vals[0]
        kt, vv = [], []
        for i, v in enumerate(vals):
            if i == 0 or v != vals[i - 1]:
                kt.append(f"{i / N:.4f}".rstrip("0").rstrip(".") or "0")
                vv.append(str(v))
        return (f'<animate attributeName="{attr}" dur="{DUR}s" repeatCount="indefinite" calcMode="discrete" '
                f'keyTimes="{";".join(kt)}" values="{";".join(vv)}"/>'), vals[0]

    cube = []
    for fi, (kind, _, _) in enumerate(FACES):
        anim_o, o0 = discrete(face_vis[fi], "opacity")
        if anim_o is None and o0 == 0:
            continue
        stroke = "#9BD11F" if kind == "in" else "#F2EEE7"
        sop = "0.55" if kind == "in" else "0.22"
        cube.append(
            f'<path d="{face_d[fi][0]}" fill="{face_fill[fi][0]}" opacity="{o0}" stroke="{stroke}" '
            f'stroke-opacity="{sop}" stroke-width="1" stroke-linejoin="round">'
            f'<animate attributeName="d" dur="{DUR}s" repeatCount="indefinite" values="{";".join(face_d[fi])}"/>'
            f'<animate attributeName="fill" dur="{DUR}s" repeatCount="indefinite" values="{";".join(face_fill[fi])}"/>'
            f'{anim_o or ""}</path>')

    ccx, ccy = proj(CUBE)

    # ---- floor grid (lines travel toward the camera)
    SP, ZMIN, NL, GN, GDUR = 1.3, 3.0, 28, 12, 2.6
    floor_y = lambda z: CY - F * FLOOR / z
    hl = []
    for k in range(NL):
        vals = []
        for j in range(GN + 1):
            z = ZMIN + k * SP - SP * j / GN
            y = floor_y(z) if z > 0.4 else H + 50
            vals.append(f"M0 {n(min(y, H + 50))}H{W}")
        hl.append(f'<path d="{vals[0]}"><animate attributeName="d" dur="{GDUR}s" repeatCount="indefinite" values="{";".join(vals)}"/></path>')
    vl = []
    x = -26.0
    while x <= 26.01:
        x1, y1 = CX + F * x / 2.2, floor_y(2.2)
        x2, y2 = CX + F * x / 90, floor_y(90)
        vl.append(f"M{n(x1)} {n(y1)}L{n(x2)} {n(y2)}")
        x += SP
    shadow_y = floor_y(CUBE[2])

    # ---- orbit ring (front/back split around the cube)
    ORX, ORY, OROT = 196, 42, -9
    ring = f"M{n(ccx - ORX)} {n(ccy)}A{ORX} {ORY} 0 1 1 {n(ccx + ORX)} {n(ccy)}A{ORX} {ORY} 0 1 1 {n(ccx - ORX)} {n(ccy)}"
    dots = []
    ND, ODUR = 22, 16
    for k in range(ND):
        r = 2.4 if k % 4 else 3.2
        col = LIME if k % 7 == 0 else BONE
        dots.append(f'<circle r="{r}" fill="{col}"><animateMotion dur="{ODUR}s" repeatCount="indefinite" '
                    f'begin="-{ODUR * k / ND:.3f}s" path="{ring}"/></circle>')
    ring2 = f"M{n(ccx - ORX - 34)} {n(ccy)}A{ORX + 34} {ORY + 9} 0 1 1 {n(ccx + ORX + 34)} {n(ccy)}A{ORX + 34} {ORY + 9} 0 1 1 {n(ccx - ORX - 34)} {n(ccy)}"
    for k in range(6):
        dots.append(f'<rect x="-2" y="-2" width="4" height="4" fill="{LIME}"><animateMotion dur="{ODUR * 1.6}s" repeatCount="indefinite" '
                    f'begin="-{ODUR * 1.6 * k / 6:.3f}s" path="{ring2}"/></rect>')

    # ---- wordmark
    WX, WY = 652, 262
    letters, ww = DISPLAY.glyphs("HJBV", 128, WX, WY, 4)
    word = []
    for i, (_, d, _, _) in enumerate(letters):
        word.append(f'<path class="ltr" style="animation-delay:{0.15 + i * 0.09:.2f}s" d="{d}"/>')
    studio, sw = MONO.path("STUDIO", 25, WX + 4, WY + 52, 15)
    tag1, _ = MONO_REG.path("independent design & engineering studio.", 15, WX + 4, WY + 100, 1.2)
    tag2, _ = MONO_REG.path("websites, saas products and apps, built to last.", 15, WX + 4, WY + 124, 1.2)

    hud = []
    br = 18
    for (x0, y0, dx, dy) in [(24, 24, 1, 1), (W - 24, 24, -1, 1), (24, H - 24, 1, -1), (W - 24, H - 24, -1, -1)]:
        hud.append(f"M{x0} {y0 + dy * br}V{y0}H{x0 + dx * br}")
    hud_txt = (mono("HJBV STUDIO / 001", 11, 52, 46, BONE, op=0.85)
               + mono("41.99N 21.43E  SKOPJE, MK", 11, W - 52, 46, MUTED, anchor="end")
               + mono("WEB / SAAS / MOBILE / BRAND", 11, 52, H - 38, MUTED)
               + mono("REALTIME 3D / NO JS", 11, W - 52, H - 38, MUTED, anchor="end"))

    css = f"""
.ltr{{fill:url(#sheen);animation:rise 1.1s cubic-bezier(.2,.8,.2,1) both}}
@keyframes rise{{from{{transform:translateY(150px)}}to{{transform:translateY(0)}}}}
.fade{{animation:fade 1.4s ease-out .7s both}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
.bar{{transform-box:fill-box;transform-origin:left;animation:grow 1.2s cubic-bezier(.2,.8,.2,1) .5s both}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
.cur{{animation:blink 1.1s steps(1) infinite}}
@keyframes blink{{50%{{opacity:0}}}}
.scan{{animation:scan 7s linear infinite}}
@keyframes scan{{from{{transform:translateY(-60px)}}to{{transform:translateY({H + 60}px)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs>
<style>{css}</style>
<radialGradient id="vig" cx="0.32" cy="0.48" r="0.85"><stop offset="0" stop-color="#16181C"/><stop offset="1" stop-color="{BG}"/></radialGradient>
<linearGradient id="hz" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="{BG}" stop-opacity="0"/></linearGradient>
<linearGradient id="btm" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG}" stop-opacity="0"/><stop offset="1" stop-color="{BG}"/></linearGradient>
<radialGradient id="glow"><stop offset="0" stop-color="{LIME}" stop-opacity=".16"/><stop offset="1" stop-color="{LIME}" stop-opacity="0"/></radialGradient>
<radialGradient id="shd"><stop offset="0" stop-color="#000" stop-opacity=".85"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
<linearGradient id="sheen" gradientUnits="userSpaceOnUse" x1="{WX - 400}" y1="0" x2="{WX}" y2="0">
<stop offset="0" stop-color="{BONE}"/><stop offset=".45" stop-color="{BONE}"/><stop offset=".5" stop-color="#FFFFFF"/><stop offset=".53" stop-color="{LIME}"/><stop offset=".58" stop-color="{BONE}"/><stop offset="1" stop-color="{BONE}"/>
<animateTransform attributeName="gradientTransform" type="translate" values="0 0;{int(ww) + 800} 0;{int(ww) + 800} 0" keyTimes="0;.45;1" dur="6s" repeatCount="indefinite"/>
</linearGradient>
<linearGradient id="scanG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{LIME}" stop-opacity="0"/><stop offset="1" stop-color="{LIME}" stop-opacity=".05"/></linearGradient>
<clipPath id="panel"><rect width="{W}" height="{H}"/></clipPath>
<clipPath id="back"><rect x="-400" y="-400" width="{W + 800}" height="{400 + ccy}"/></clipPath>
<clipPath id="front"><rect x="-400" y="{ccy}" width="{W + 800}" height="{H + 400}"/></clipPath>
<g id="ring"><path d="{ring}" fill="none" stroke="{BONE}" stroke-opacity=".16" stroke-dasharray="2 6"/><path d="{ring2}" fill="none" stroke="{LIME}" stroke-opacity=".12"/>{"".join(dots)}</g>
</defs>
<g clip-path="url(#panel)">
<rect width="{W}" height="{H}" fill="url(#vig)"/>
<g stroke="{GRID}" stroke-width="1" fill="none">{"".join(hl)}<path d="{"".join(vl)}"/></g>
<rect y="{CY - 2}" width="{W}" height="120" fill="url(#hz)"/>
<rect y="{H - 70}" width="{W}" height="70" fill="url(#btm)"/>
<path d="M0 {CY}H{W}" stroke="{LIME}" stroke-opacity=".22"/>
<ellipse cx="{n(ccx)}" cy="{n(shadow_y)}" rx="170" ry="30" fill="url(#glow)"/>
<ellipse cx="{n(ccx)}" cy="{n(shadow_y)}" rx="100" ry="13" fill="url(#shd)">
<animate attributeName="rx" dur="{DUR / 2}s" repeatCount="indefinite" values="100;88;100;112;100" calcMode="spline" keySplines=".4 0 .6 1;.4 0 .6 1;.4 0 .6 1;.4 0 .6 1"/></ellipse>
<g transform="rotate({OROT} {n(ccx)} {n(ccy)})"><use href="#ring" clip-path="url(#back)" opacity=".45"/></g>
<g>{"".join(cube)}</g>
<g transform="rotate({OROT} {n(ccx)} {n(ccy)})"><use href="#ring" clip-path="url(#front)"/></g>
<rect class="scan" x="0" y="0" width="{W}" height="60" fill="url(#scanG)"/>
<g clip-path="url(#wclip)">{"".join(word)}</g>
<clipPath id="wclip"><rect x="{WX - 20}" y="{WY - 130}" width="{int(ww) + 60}" height="160"/></clipPath>
<rect class="bar" x="{WX + 4}" y="{WY + 22}" width="{int(ww)}" height="2" fill="{LIME}"/>
<g class="fade">
<path d="{studio}" fill="{LIME}"/>
<rect class="cur" x="{n(WX + 4 + sw + 14)}" y="{WY + 33}" width="13" height="22" fill="{LIME}"/>
<path d="{tag1}" fill="{MUTED}"/><path d="{tag2}" fill="{MUTED}"/>
</g>
<path d="{"".join(hud)}" fill="none" stroke="{BONE}" stroke-opacity=".4"/>
{hud_txt}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" fill="none" stroke="{LINE}"/>
</svg>'''
    write("hero.svg", svg)


# ---------------------------------------------------------------- wireframes
def circle_pts(r, y=0.0, k=32, axis="y"):
    pts = []
    for i in range(k + 1):
        a = 2 * math.pi * i / k
        if axis == "y":
            pts.append((r * math.cos(a), y, r * math.sin(a)))
        else:
            pts.append((r * math.cos(a), r * math.sin(a), y))
    return pts


def globe():
    lines = []
    for lat in (-60, -30, 0, 30, 60):
        r = math.cos(math.radians(lat))
        lines.append(circle_pts(r, math.sin(math.radians(lat)), 36))
    for m in range(12):
        lon = 2 * math.pi * m / 12
        pts = []
        for i in range(19):
            a = -math.pi / 2 + math.pi * i / 18
            pts.append((math.cos(a) * math.cos(lon), math.sin(a), math.cos(a) * math.sin(lon)))
        lines.append(pts)
    return lines, 2 * math.pi / 12


def layers():
    lines = []
    for y in (-0.62, 0, 0.62):
        s = 0.95
        lines.append([(-s, y, -s), (s, y, -s), (s, y, s), (-s, y, s), (-s, y, -s)])
        s2 = 0.55
        lines.append([(-s2, y, -s2), (s2, y, -s2), (s2, y, s2), (-s2, y, s2), (-s2, y, -s2)])
    for x, z in ((-0.95, -0.95), (0.95, -0.95), (0.95, 0.95), (-0.95, 0.95)):
        lines.append([(x, -0.62, z), (x, 0.62, z)])
    return lines, math.pi / 2


def phone():
    w, h, d = 0.62, 1.2, 0.08
    c = [(x, y, z) for x in (-w, w) for y in (-h, h) for z in (-d, d)]
    edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    lines = [[c[a], c[b]] for a, b in edges]
    sw, sh, z = 0.52, 1.06, -d - 0.001
    lines.append([(-sw, -sh, z), (sw, -sh, z), (sw, sh, z), (-sw, sh, z), (-sw, -sh, z)])
    lines.append([(-0.14, sh - 0.07, z), (0.14, sh - 0.07, z)])
    for i in range(4):
        y = 0.6 - i * 0.34
        lines.append([(-0.4, y, z), (0.4 - (i % 2) * 0.25, y, z)])
    return lines, None


def torus():
    R, r = 0.78, 0.3
    lines = []
    for k in range(14):
        a = 2 * math.pi * k / 14
        pts = []
        for i in range(17):
            b = 2 * math.pi * i / 16
            rr = R + r * math.cos(b)
            pts.append((rr * math.cos(a), r * math.sin(b), rr * math.sin(a)))
        lines.append(pts)
    for b in (0, math.pi / 2, math.pi, -math.pi / 2):
        rr = R + r * math.cos(b)
        lines.append(circle_pts(rr, r * math.sin(b), 40))
    return lines, 2 * math.pi / 14


def octa():
    v = [(1, 0, 0), (-1, 0, 0), (0, 1.2, 0), (0, -1.2, 0), (0, 0, 1), (0, 0, -1)]
    e = [(0, 2), (0, 3), (0, 4), (0, 5), (1, 2), (1, 3), (1, 4), (1, 5), (2, 4), (4, 3), (3, 5), (5, 2)]
    return [[v[a], v[b]] for a, b in e], math.pi / 2


def wire_anim(shape, cx, cy, scale, full_dur, pitch=-0.38, frames=14, swing=False, dist=5.5, stroke=BONE,
              width=1.1, op=0.85, accent=()):
    lines, period = shape
    if swing:
        period, frames = 2 * math.pi, 48
    dur = full_dur * period / (2 * math.pi)
    groups = [[i for i in range(len(lines)) if i not in accent], list(accent)]
    vals = [[], []]
    for i in range(frames + 1):
        t = period * i / frames
        yaw = 0.75 * math.sin(t) if swing else t
        for gi, idx in enumerate(groups):
            parts = []
            for li in idx:
                pp = []
                for p in lines[li]:
                    x, y, z = rot(p, yaw, pitch)
                    z += dist
                    pp.append((cx + scale * dist * x / z, cy - scale * dist * y / z))
                parts.append("M" + "L".join(f"{n(a)} {n(b)}" for a, b in pp))
            vals[gi].append("".join(parts))
    out = ""
    for gi, (col, w, o) in enumerate([(stroke, width, op), (LIME, width + 0.4, 1)]):
        if not groups[gi]:
            continue
        v = vals[gi]
        out += (f'<path d="{v[0]}" fill="none" stroke="{col}" stroke-width="{w}" stroke-opacity="{o}" '
                f'stroke-linejoin="round"><animate attributeName="d" dur="{dur:.3f}s" repeatCount="indefinite" '
                f'values="{";".join(v)}"/></path>')
    return out


# ---------------------------------------------------------------- sections
def build_header(num, title, label, fname, delay=0):
    H = 104
    t, tw = DISPLAY_MED.path(title, 30, 70, 62, 1.5)
    css = """
.pulse{animation:pulse 5s cubic-bezier(.6,0,.4,1) infinite}
@keyframes pulse{from{transform:translateX(-220px)}to{transform:translateX(1420px)}}
.in{animation:in 1s cubic-bezier(.2,.8,.2,1) both}
@keyframes in{from{opacity:0;transform:translateX(-24px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""
    obj = wire_anim(octa(), W - 52, 52, 22, 9, pitch=-0.3, frames=16, stroke=LIME, width=1.2, op=0.9)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><style>{css}</style>
<linearGradient id="pg" x1="0" x2="1"><stop offset="0" stop-color="{LIME}" stop-opacity="0"/><stop offset="1" stop-color="{LIME}"/></linearGradient></defs>
<rect width="{W}" height="{H}" fill="{BG}"/>
<g class="in">
{mono(num, 13, 24, 60, LIME)}
<path d="{t}" fill="{BONE}"/>
{mono(label, 11, W - 96, 60, MUTED, anchor="end")}
</g>
{obj}
<path d="M0 {H - 1}H{W}" stroke="{LINE}" stroke-width="2"/>
<rect class="pulse" style="animation-delay:{delay}s" x="0" y="{H - 2}" width="220" height="2" fill="url(#pg)"/>
<rect x="0" y="{H - 6}" width="6" height="6" fill="{LIME}"/>
</svg>'''
    write(fname, svg)


def build_services():
    H = 360
    GAP = 16
    CW = (W - 3 * GAP) / 4
    items = [
        ("01", "WEB", ["marketing sites, web apps", "and dashboards. fast, seo", "ready, edge deployed."], globe(), False),
        ("02", "SAAS", ["multi tenant products,", "auth, billing and apis", "from mvp to scale."], layers(), False),
        ("03", "MOBILE", ["ios and android apps", "that feel native and", "ship on schedule."], phone(), True),
        ("04", "BRAND", ["identity, ui systems", "and motion that make", "products memorable."], torus(), False),
    ]
    css = """
.tick{animation:tick 8s ease-in-out infinite;opacity:0}
@keyframes tick{0%,4%{opacity:0;transform:scaleX(0)}8%,22%{opacity:1;transform:scaleX(1)}30%,100%{opacity:0;transform:scaleX(1)}}
.tick{transform-box:fill-box;transform-origin:left}
.card{animation:card 1s cubic-bezier(.2,.8,.2,1) both}
@keyframes card{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}.tick{opacity:1}}
"""
    ACCENTS = [(2,), (2, 3), (12,), (14,)]
    cards = []
    for i, (num, title, desc, shape, swing) in enumerate(items):
        x = i * (CW + GAP)
        cx = x + CW / 2
        obj = wire_anim(shape, cx, 128, 64, 16 + i * 2, swing=swing, frames=14, accent=ACCENTS[i])
        t, _ = DISPLAY_MED.path(title, 24, x + 22, 254, 1.5)
        lines = "".join(mono(l, 12.5, x + 22, 284 + j * 20, MUTED, tracking=0.6) for j, l in enumerate(desc))
        cards.append(f'''<g class="card" style="animation-delay:{0.1 + i * 0.12:.2f}s">
<rect x="{n(x + .5)}" y=".5" width="{n(CW - 1)}" height="{H - 1}" fill="{PANEL}" stroke="{LINE}"/>
<rect class="tick" style="animation-delay:{i * 2}s" x="{n(x)}" y="0" width="{n(CW)}" height="2" fill="{LIME}"/>
{mono(num, 11, x + 22, 34, LIME)}{mono("/ SERVICE", 11, x + 50, 34, MUTED)}
<ellipse cx="{n(cx)}" cy="208" rx="70" ry="6" fill="#000" opacity=".5"/>
{obj}
<path d="M{n(x + 22)} 222H{n(x + CW - 22)}" stroke="{LINE}"/>
<path d="{t}" fill="{BONE}"/>
{lines}
<path d="M{n(x + CW - 30)} {H - 18}H{n(x + CW - 18)}V{H - 30}" fill="none" stroke="{LIME}" stroke-opacity=".7"/>
</g>''')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><style>{css}</style></defs>
<rect width="{W}" height="{H}" fill="{BG}"/>
{"".join(cards)}
</svg>'''
    write("services.svg", svg)


def build_stack():
    H = 76
    items = ["NEXT.JS", "REACT", "TYPESCRIPT", "JAVA", "SPRING BOOT", "PYTHON", "FASTAPI",
             "POSTGRESQL", "CLOUDFLARE", "DOCKER", "TAILWIND", "GITHUB ACTIONS"]
    parts, x = [], 0.0
    for it in items:
        d, w = MONO.path(it, 15, x, 44, 3)
        parts.append(f'<path d="{d}" fill="{BONE}"/>')
        x += w + 26
        parts.append(f'<rect x="{n(x)}" y="32" width="8" height="8" fill="{LIME}"/>')
        x += 8 + 26
    seg = x
    css = f"""
.mq{{animation:mq {seg / 45:.1f}s linear infinite}}
@keyframes mq{{from{{transform:translateX(0)}}to{{transform:translateX(-{n(seg)}px)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""
    row = "".join(parts)
    copies = "".join(f'<g transform="translate({n(seg * k)} 0)">{row}</g>' for k in range(int(W / seg) + 2))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><style>{css}</style>
<linearGradient id="fl" x1="0" x2="1"><stop offset="0" stop-color="{PANEL}"/><stop offset="1" stop-color="{PANEL}" stop-opacity="0"/></linearGradient>
<linearGradient id="fr" x1="0" x2="1"><stop offset="0" stop-color="{PANEL}" stop-opacity="0"/><stop offset="1" stop-color="{PANEL}"/></linearGradient></defs>
<rect width="{W}" height="{H}" fill="{PANEL}"/>
<g class="mq" transform="translate(24 0)">{copies}</g>
<rect width="140" height="{H}" fill="url(#fl)"/><rect x="{W - 140}" width="140" height="{H}" fill="url(#fr)"/>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" fill="none" stroke="{LINE}"/>
</svg>'''
    write("stack.svg", svg)


def build_process():
    H = 210
    steps = [("DISCOVER", "scope, goals, constraints"), ("DESIGN", "flows, ui, prototypes"),
             ("BUILD", "typed, tested, reviewed"), ("SHIP", "deploy, measure, iterate")]
    X0, X1, Y = 110, W - 110, 92
    DUR = 8
    seg = (X1 - X0) / (len(steps) - 1)
    css = f"""
.run{{animation:run {DUR}s cubic-bezier(.65,0,.35,1) infinite}}
@keyframes run{{0%{{transform:translateX(0)}}80%,100%{{transform:translateX({X1 - X0}px)}}}}
.trail{{transform-box:fill-box;transform-origin:left;animation:trail {DUR}s cubic-bezier(.65,0,.35,1) infinite}}
@keyframes trail{{0%{{transform:scaleX(0);opacity:1}}80%{{transform:scaleX(1);opacity:1}}95%,100%{{transform:scaleX(1);opacity:0}}}}
.ring{{transform-box:fill-box;transform-origin:center;opacity:0}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""
    out, kf = [], []
    for i, (t, d) in enumerate(steps):
        x = X0 + i * seg
        # time the pulse reaches this node (eased path approximated)
        frac = i / (len(steps) - 1)
        # inverse of cubic-bezier(.65,0,.35,1) is close to symmetric; approximate
        p = _ease_inv(frac) * 80
        a, b = max(p - 0.01, 0), p + 0.6
        kf.append(f"@keyframes n{i}{{0%,{a:.2f}%{{fill:{BG};stroke:{GRID}}}{b:.2f}%,88%{{fill:{LIME};stroke:{LIME}}}96%,100%{{fill:{BG};stroke:{GRID}}}}}"
                  f"@keyframes r{i}{{0%,{a:.2f}%{{opacity:0;transform:scale(.4)}}{b:.2f}%{{opacity:.9;transform:scale(.5)}}{p + 12:.2f}%,100%{{opacity:0;transform:scale(2.8)}}}}")
        out.append(f'<rect style="animation:n{i} {DUR}s linear infinite" x="{n(x - 7)}" y="{Y - 7}" width="14" height="14" fill="{BG}" stroke="{GRID}" stroke-width="1.5"/>')
        out.append(f'<rect class="ring" style="animation:r{i} {DUR}s ease-out infinite" x="{n(x - 7)}" y="{Y - 7}" width="14" height="14" fill="none" stroke="{LIME}"/>')
        out.append(mono(f"0{i + 1}", 11, x, Y - 30, LIME, anchor="middle"))
        tp, _ = DISPLAY_MED.path(t, 17, x, Y + 50, 1.2, "middle")
        out.append(f'<path d="{tp}" fill="{BONE}"/>')
        out.append(mono(d, 11.5, x, Y + 76, MUTED, tracking=0.5, anchor="middle"))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><style>{css}{"".join(kf)}</style>
<linearGradient id="tg" x1="0" x2="1"><stop offset="0" stop-color="{LIME}" stop-opacity=".05"/><stop offset="1" stop-color="{LIME}" stop-opacity=".9"/></linearGradient></defs>
<rect width="{W}" height="{H}" fill="{PANEL}"/>
<path d="M{X0} {Y}H{X1}" stroke="{GRID}" stroke-dasharray="3 5"/>
<rect class="trail" x="{X0}" y="{Y - 1}" width="{X1 - X0}" height="2" fill="url(#tg)"/>
<g class="run"><rect x="{X0 - 3}" y="{Y - 3}" width="6" height="6" fill="#fff"/><rect x="{X0 - 20}" y="{Y - 0.5}" width="20" height="1" fill="#fff" opacity=".6"/></g>
{"".join(out)}
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" fill="none" stroke="{LINE}"/>
</svg>'''
    write("process.svg", svg)


def _ease_inv(y):
    # numeric inverse of cubic-bezier(.65,0,.35,1)
    def bez(t, a, b):
        return 3 * (1 - t) ** 2 * t * a + 3 * (1 - t) * t ** 2 * b + t ** 3
    lo, hi = 0.0, 1.0
    for _ in range(40):
        m = (lo + hi) / 2
        # find x for bezier param m and y
        if bez(m, 0, 1) < y:
            lo = m
        else:
            hi = m
    p = (lo + hi) / 2
    return bez(p, .65, .35)


def build_footer():
    H = 260
    F, CX, CY = 700.0, 600.0, 96.0
    FLOOR = -1.0
    SP, ZMIN, NL, GN, GDUR = 0.9, 1.6, 34, 10, 1.8
    fy = lambda z: CY - F * FLOOR / z
    hl = []
    for k in range(NL):
        vals = []
        for j in range(GN + 1):
            z = ZMIN + k * SP - SP * j / GN
            y = fy(z) if z > 0.3 else H + 40
            vals.append(f"M0 {n(min(y, H + 40))}H{W}")
        hl.append(f'<path d="{vals[0]}"><animate attributeName="d" dur="{GDUR}s" repeatCount="indefinite" values="{";".join(vals)}"/></path>')
    vl = []
    x = -30.0
    while x <= 30.01:
        vl.append(f"M{n(CX + F * x / 1.2)} {n(fy(1.2))}L{n(CX + F * x / 80)} {n(fy(80))}")
        x += SP
    word, _ = DISPLAY.path("HJBV STUDIO", 26, W / 2 + 22, 58, 3, "middle")
    css = """
.sweep{animation:sweep 6s ease-in-out infinite}
@keyframes sweep{0%{transform:translateX(-700px)}60%,100%{transform:translateX(700px)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""
    _, ww = DISPLAY.path("HJBV STUDIO", 26, 0, 0, 3)
    mx = W / 2 - ww / 2 - 4
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><style>{css}</style>
<linearGradient id="hz" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="{BG}" stop-opacity="0"/></linearGradient>
<linearGradient id="sw" x1="0" x2="1"><stop offset="0" stop-color="{LIME}" stop-opacity="0"/><stop offset=".5" stop-color="{LIME}"/><stop offset="1" stop-color="{LIME}" stop-opacity="0"/></linearGradient>
<radialGradient id="hg" cx=".5" cy="0" r=".6"><stop offset="0" stop-color="{LIME}" stop-opacity=".12"/><stop offset="1" stop-color="{LIME}" stop-opacity="0"/></radialGradient>
<clipPath id="c"><rect width="{W}" height="{H}"/></clipPath></defs>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="{BG}"/>
<g stroke="{GRID}" fill="none">{"".join(hl)}<path d="{"".join(vl)}"/></g>
<rect y="{CY}" width="{W}" height="70" fill="url(#hz)"/>
<rect y="{CY}" width="{W}" height="{H - CY}" fill="url(#hg)"/>
<path d="M0 {CY}H{W}" stroke="{LIME}" stroke-opacity=".3"/>
<rect class="sweep" x="{W / 2 - 160}" y="{CY - 1}" width="320" height="2" fill="url(#sw)"/>
<rect width="{W}" height="{CY}" fill="{BG}"/>
<g transform="translate({n(mx - 26)} 44)">{mark_svg(42, 0, 0)}</g>
<path d="{word}" fill="{BONE}"/>
{mono("SKOPJE, MK  /  DESIGN + ENGINEERING", 11, W / 2, 84, MUTED, anchor="middle")}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" fill="none" stroke="{LINE}"/>
</svg>'''
    write("footer.svg", svg)


def write(name, svg):
    svg = "\n".join(l.strip() for l in svg.splitlines() if l.strip())
    with open(os.path.join(ASSETS, name), "w") as f:
        f.write(svg)
    print(f"{name:16s} {len(svg) / 1024:7.1f} KB")


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    build_logo()
    build_hero()
    build_header("01", "WHAT WE DO", "SERVICES", "h-services.svg", 0)
    build_services()
    build_header("02", "HOW WE WORK", "PROCESS", "h-process.svg", 1.2)
    build_process()
    build_header("03", "STACK", "TOOLS WE SHIP WITH", "h-stack.svg", 2.4)
    build_stack()
    build_footer()
