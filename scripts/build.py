"""Builds every SVG asset for the HJBV Studio org profile.

All 3D is computed here (real perspective projection, backface culling,
per-face lighting) and baked into SMIL/CSS animations, so the SVGs run
inside GitHub's <img> sandbox without JS, filters or external fonts.

run: python scripts/build.py   (needs fonttools + three OFL fonts in fonts/:
  Unbounded[wght].ttf, JetBrainsMono[wght].ttf and Inter[opsz,wght].ttf from
  github.com/google/fonts, saved as fonts/Unbounded.ttf, fonts/JetBrainsMono.ttf
  and fonts/Inter.ttf)
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
        axes = {a.axisTag for a in f["fvar"].axes}
        loc = {"wght": wght}
        if "opsz" in axes:
            loc["opsz"] = 14
        f = instantiateVariableFont(f, loc)
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
SANS = Font("Inter.ttf", 450)
SANS_B = Font("Inter.ttf", 650)
SANS_X = Font("Inter.ttf", 750)


def sans(text, size, x, y, fill=BONE, font=None, anchor="start", tracking=0.0, extra=""):
    d, _ = (font or SANS).path(text, size, x, y, tracking, anchor)
    return f'<path d="{d}" fill="{fill}"{extra}/>'


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

    # ---- lime light spilling out of the notch (strongest when the notch faces us)
    gx, gy, go = [], [], []
    diag = norm((1, 1, 1))
    for i in range(N + 1):
        t = i / N * 2 * math.pi
        yaw, pitch, roll = ISO_YAW + t, -0.42 + 0.12 * math.sin(t), 0.05 * math.sin(2 * t)
        bob = 0.10 * math.sin(2 * t)
        c = rot((0.55, 0.55, 0.55), yaw, pitch, roll)
        c = (c[0] + CUBE[0], c[1] + CUBE[1] + bob, c[2] + CUBE[2])
        x, y = proj(c)
        facing = -dot(rot(diag, yaw, pitch, roll), norm(c))
        gx.append(n(x))
        gy.append(n(y))
        go.append(f"{max(0.0, min(1.0, facing * 1.6)):.2f}")
    A = f'dur="{DUR}s" repeatCount="indefinite"'
    notch_glow = (f'<ellipse cx="{gx[0]}" cy="{gy[0]}" rx="95" ry="80" fill="url(#ng)" opacity="{go[0]}">'
                  f'<animate attributeName="cx" values="{";".join(gx)}" {A}/><animate attributeName="cy" values="{";".join(gy)}" {A}/>'
                  f'<animate attributeName="opacity" values="{";".join(go)}" {A}/></ellipse>')

    # ---- small tumbling cubes at different depths
    def mini_cube(pos, s, k, base, hi, edge):
        faces = []
        for ax in range(3):
            for sg in (1, -1):
                pts = square(ax, sg * s, -s, s)
                faces.append((pts, unit(ax, sg)))
        ds = [[] for _ in faces]
        vs = [[] for _ in faces]
        cs = [[] for _ in faces]
        for i in range(N + 1):
            t = i / N * 2 * math.pi
            yaw, pitch, roll = k[0] * t, k[1] * t + 0.6, k[2] * t
            dy = 0.18 * math.sin(t * k[3] + pos[0])
            for fi, (pts, nm) in enumerate(faces):
                cp = [tuple(a + b for a, b in zip(rot(p, yaw, pitch, roll), (pos[0], pos[1] + dy, pos[2]))) for p in pts]
                nr = rot(nm, yaw, pitch, roll)
                ds[fi].append("M" + " ".join(f"{n(x)} {n(y)}" for x, y in map(proj, cp)) + "Z")
                if i < N:
                    vs[fi].append(1 if dot(nr, cp[0]) < 0 else 0)
                    cs[fi].append(lerp_hex(base, hi, 0.15 + 0.85 * max(0.0, dot(nr, light))))
        out = ""
        for fi in range(len(faces)):
            ao, o0 = discrete(vs[fi], "opacity")
            out += (f'<path d="{ds[fi][0]}" fill="{cs[fi][0]}" opacity="{o0}" stroke="{edge}" stroke-opacity=".35" stroke-linejoin="round">'
                    f'<animate attributeName="d" values="{";".join(ds[fi])}" {A}/>'
                    f'<animate attributeName="fill" values="{";".join(cs[fi] + [cs[fi][0]])}" {A}/>{ao or ""}</path>')
        return out

    minis_back = (mini_cube((-5.6, 1.5, 12.5), 0.26, (1, 2, 0, 2), "#2C4204", LIME, LIME)
                  + mini_cube((-0.4, 1.9, 12.0), 0.18, (-2, 1, 1, 3), "#121316", "#F2EEE7", "#F2EEE7"))
    minis_front = (mini_cube((-4.2, -1.3, 7.9), 0.18, (2, -1, 1, 2), "#121316", "#F2EEE7", "#F2EEE7")
                   + mini_cube((-0.75, -0.95, 7.9), 0.13, (-1, 3, 0, 3), "#2C4204", LIME, LIME))

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
<radialGradient id="ng"><stop offset="0" stop-color="{LIME}" stop-opacity=".38"/><stop offset=".45" stop-color="{LIME}" stop-opacity=".12"/><stop offset="1" stop-color="{LIME}" stop-opacity="0"/></radialGradient>
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
{minis_back}
<g>{"".join(cube)}</g>
{notch_glow}
<g transform="rotate({OROT} {n(ccx)} {n(ccy)})"><use href="#ring" clip-path="url(#front)"/></g>
{minis_front}
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


# ---------------------------------------------------------------- iPhones
# Same build as the phone in vanniworksv2 src/fx/three/devices.js (1 unit = 380 px):
# titanium slab, glass, screen, Dynamic Island, side keys, frosted back with the
# camera plateau. Each phone is drawn as stacked depth layers mapped through a
# per-frame affine (translate * rotate * scale * skewY) taken from a real
# perspective projection, so its live SVG app screen rides along in 3D.
PU = 380
PW, PH, PD, PR = 0.395 * PU, 0.82 * PU, 0.046 * PU, 0.074 * PU
GLW, GLH, GLR = PW - 0.012 * PU, PH - 0.012 * PU, PR - 0.006 * PU
SCW, SCH, SCR = PW - 0.034 * PU, PH - 0.034 * PU, PR - 0.02 * PU
FINISH = {"black": ("#3a3936", "#1b1b1c"), "natural": ("#9a968f", "#b9b5ae"), "desert": ("#b08f6e", "#c7a98a")}
P_LIGHT = norm((-0.55, 0.5, -0.65))


def rrect(w, h, r, cx=0.0, cy=0.0):
    x0, y0 = cx - w / 2, cy - h / 2
    r = min(r, w / 2, h / 2)
    a = f"A{n(r)} {n(r)} 0 0 1"
    return (f"M{n(x0 + r)} {n(y0)}H{n(x0 + w - r)}{a} {n(x0 + w)} {n(y0 + r)}V{n(y0 + h - r)}"
            f"{a} {n(x0 + w - r)} {n(y0 + h)}H{n(x0 + r)}{a} {n(x0)} {n(y0 + h - r)}V{n(y0 + r)}{a} {n(x0 + r)} {n(y0)}Z")


def body_path():
    d = rrect(PW, PH, PR)
    for ln, side, yu in ((0.04, -1, 0.24), (0.07, -1, 0.15), (0.07, -1, 0.06), (0.11, 1, 0.13)):
        d += rrect(2.6, ln * PU, 1.2, cx=side * (PW / 2 + 0.5), cy=-yu * PU)
    return d


def star(cx, cy, r, fill):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append(f"{n(cx + rr * math.cos(a))} {n(cy + rr * math.sin(a))}")
    return f'<path d="M{"L".join(pts)}Z" fill="{fill}"/>'


def phone_track(pose, N, F, CX, CY):
    fr = []
    for i in range(N + 1):
        X, Y, Z, yaw, pitch, roll = pose(i / N)
        P = (X, Y, Z)

        def R(v):
            return rot(v, yaw, pitch, roll)

        def J(v):
            return (F / Z * (v[0] - X / Z * v[2]), -F / Z * (v[1] - Y / Z * v[2]))

        a, b = J(R((1, 0, 0)))
        c, d = J(R((0, -1, 0)))
        th = math.atan2(-c, d)
        sy = math.hypot(c, d)
        sx = math.cos(th) * a + math.sin(th) * b
        k = -math.sin(th) * a + math.cos(th) * b
        ox, oy = J(R((0, 0, 1)))
        ex = R((1, 0, 0))
        side = ex if dot(ex, P) < 0 else tuple(-v for v in ex)
        fr.append(dict(e=CX + F * X / Z, f=CY - F * Y / Z, th=math.degrees(th), sx=sx, sy=sy,
                       psi=math.degrees(math.atan(k / sy)), ox=ox, oy=oy, yaw=yaw,
                       front=dot(R((0, 0, -1)), P) < 0, lit=max(0.0, dot(side, P_LIGHT)),
                       face=max(0.0, dot(R((0, 0, -1)), P_LIGHT)), back=max(0.0, dot(R((0, 0, 1)), P_LIGHT))))
    return fr


def _a(dur):
    return f'dur="{dur}s" repeatCount="indefinite"'


def aff(fr, dur):
    f0 = fr[0]
    tf = (f'translate({n(f0["e"])} {n(f0["f"])}) rotate({f0["th"]:.2f}) '
          f'scale({f0["sx"]:.4f} {f0["sy"]:.4f}) skewY({f0["psi"]:.2f})')
    A = _a(dur)
    anims = (
        f'<animateTransform attributeName="transform" type="translate" values="{";".join(n(x["e"]) + " " + n(x["f"]) for x in fr)}" {A}/>'
        f'<animateTransform attributeName="transform" type="rotate" additive="sum" values="{";".join(f"{x["th"]:.2f}" for x in fr)}" {A}/>'
        f'<animateTransform attributeName="transform" type="scale" additive="sum" values="{";".join(f"{x["sx"]:.4f} {x["sy"]:.4f}" for x in fr)}" {A}/>'
        f'<animateTransform attributeName="transform" type="skewY" additive="sum" values="{";".join(f"{x["psi"]:.2f}" for x in fr)}" {A}/>')
    return tf, anims


def discrete_anim(vals, attr, dur):
    N = len(vals)
    if all(v == vals[0] for v in vals):
        return "", vals[0]
    kt, vv = [], []
    for i, v in enumerate(vals):
        if i == 0 or v != vals[i - 1]:
            kt.append(f"{i / N:.4f}")
            vv.append(str(v))
    return (f'<animate attributeName="{attr}" calcMode="discrete" keyTimes="{";".join(kt)}" '
            f'values="{";".join(vv)}" {_a(dur)}/>'), vals[0]


def iphone(uid, fr, dur, finish, screen, defs):
    metal, backc = FINISH[finish]
    A = _a(dur)
    tf, anims = aff(fr, dur)
    defs.append(f'<g id="{uid}b" transform="{tf}">{anims}<path d="{body_path()}"/></g>')
    defs.append(f'<clipPath id="{uid}c"><path d="{rrect(SCW, SCH, SCR)}"/></clipPath>')
    defs.append(f'<linearGradient id="{uid}g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
                f'<stop offset=".48" stop-color="#fff" stop-opacity=".0"/><stop offset=".5" stop-color="#fff" stop-opacity=".11"/>'
                f'<stop offset=".62" stop-color="#fff" stop-opacity=".03"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    defs.append(f'<linearGradient id="{uid}k" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{lerp_hex(backc, "#ffffff", .12)}"/>'
                f'<stop offset="1" stop-color="{lerp_hex(backc, "#000000", .25)}"/></linearGradient>')

    def layer(z, fill_vals, inner=None):
        offs = ";".join(f"{n(x['ox'] * z)} {n(x['oy'] * z)}" for x in fr)
        fa = f'<animate attributeName="fill" values="{";".join(fill_vals)}" {A}/>' if fill_vals else ""
        body = inner if inner is not None else f'<use href="#{uid}b"/>'
        return (f'<g fill="{fill_vals[0] if fill_vals else "none"}" transform="translate({n(fr[0]["ox"] * z)} {n(fr[0]["oy"] * z)})">'
                f'<animateTransform attributeName="transform" type="translate" values="{offs}" {A}/>{fa}{body}</g>')

    dark, light = lerp_hex(metal, "#000000", .55), lerp_hex(metal, "#ffffff", .45)
    band = [lerp_hex(dark, light, 0.1 + 0.9 * x["lit"] ** 1.3) for x in fr]
    rim = [lerp_hex(metal, "#ffffff", 0.05 + 0.4 * x["face"] ** 2) for x in fr]
    K = 7
    zs = [PD * k / K for k in range(K, 0, -1)]

    # sheen slides across the glass against the rotation
    sh = ";".join(f"{n(-math.degrees(x['yaw']) * 5.5)} 0" for x in fr)
    sheen = (f'<g><animateTransform attributeName="transform" type="translate" values="{sh}" {A}/>'
             f'<rect x="{n(-PW * 1.6)}" y="{n(-PH / 2)}" width="{n(PW * 3.2)}" height="{n(PH)}" fill="url(#{uid}g)"/></g>')
    island = f'<path d="{rrect(0.1 * PU, 0.03 * PU, 0.015 * PU, 0, -(PH / 2 - 0.054 * PU))}" fill="#000"/>'
    front_face = (f'<g transform="{tf}">{anims}'
                  f'<path d="{rrect(GLW, GLH, GLR)}" fill="#050505"/>'
                  f'<g clip-path="url(#{uid}c)"><g transform="translate({n(-SCW / 2)} {n(-SCH / 2)})">{screen}</g>{sheen}</g>'
                  f'{island}</g>')
    front = "".join(layer(z, band) for z in zs) + layer(0, rim) + front_face

    # back: frosted glass, camera plateau top left (seen from behind), the HJBV mark
    pxp, pyp = PW / 2 - 0.105 * PU, -(PH / 2 - 0.105 * PU)
    lenses = ""
    for dx, dy in ((-0.036, 0.036), (-0.036, -0.036), (0.036, 0)):
        lx, ly = pxp + dx * PU, pyp - dy * PU
        lenses += (f'<circle cx="{n(lx)}" cy="{n(ly)}" r="{n(0.033 * PU)}" fill="{lerp_hex(metal, "#000000", .3)}"/>'
                   f'<circle cx="{n(lx)}" cy="{n(ly)}" r="{n(0.026 * PU)}" fill="#0a0d14" stroke="{light}" stroke-opacity=".5" stroke-width=".8"/>'
                   f'<circle cx="{n(lx)}" cy="{n(ly)}" r="{n(0.012 * PU)}" fill="#1a2340"/>'
                   f'<circle cx="{n(lx - 2.5)}" cy="{n(ly - 2.5)}" r="1.6" fill="#fff" opacity=".55"/>')
    lenses += f'<circle cx="{n(pxp + 0.04 * PU)}" cy="{n(pyp - 0.05 * PU)}" r="{n(0.011 * PU)}" fill="#f3e7cf"/>'
    mark = f'<g transform="scale(-1 1)">{mark_svg(46, 0, 8)}</g>'
    back_plate = (f'<g transform="{tf}">{anims}<path d="{rrect(GLW, GLH, GLR)}" fill="url(#{uid}k)"/>{mark}'
                  f'<path d="{rrect(0.17 * PU, 0.17 * PU, 0.045 * PU, pxp, pyp)}" fill="{lerp_hex(backc, "#000000", .18)}"/></g>')
    plate_hi = (f'<g transform="{tf}">{anims}<path d="{rrect(0.17 * PU, 0.17 * PU, 0.045 * PU, pxp, pyp)}" '
                f'fill="{lerp_hex(backc, "#ffffff", .1)}"/>{lenses}</g>')
    back = ("".join(layer(z, band) for z in reversed(zs))
            + layer(PD, None, back_plate) + layer(PD + 4, None, plate_hi))

    va, v0 = discrete_anim([1 if x["front"] else 0 for x in fr[:-1]], "opacity", dur)
    out = f'<g opacity="{v0}">{va}{front}</g>'
    if not all(x["front"] for x in fr):
        vb, b0 = discrete_anim([0 if x["front"] else 1 for x in fr[:-1]], "opacity", dur)
        out = f'<g opacity="{b0}">{vb}{back}</g>' + out
    return out


# ---------------------------------------------------------------- app screens
def status_bar(dark_text=False):
    c = "#000" if dark_text else "#F5F3F1"
    x1 = SCW - 16
    bars = "".join(f'<rect x="{n(x1 - 27 + i * 2.6)}" y="{n(15.6 - i * 1.1)}" width="1.8" height="{n(1.8 + i * 1.1)}" rx=".4" fill="{c}"/>' for i in range(4))
    wifi = f'<path d="M{n(x1 - 13.5)} 13.4a5 5 0 0 1 6.4 0M{n(x1 - 12.4)} 14.9a3 3 0 0 1 4.2 0" stroke="{c}" stroke-width="1.1" fill="none" stroke-linecap="round"/><circle cx="{n(x1 - 10.3)}" cy="16.3" r=".8" fill="{c}"/>'
    bat = f'<rect x="{n(x1 - 5)}" y="12.3" width="8.6" height="4.6" rx="1.3" fill="none" stroke="{c}" stroke-opacity=".5" stroke-width=".7"/><rect x="{n(x1 - 4.2)}" y="13.1" width="6" height="3" rx=".7" fill="{c}"/>'
    return sans("9:41", 7.4, 17, 17.2, c, SANS_B) + bars + wifi + bat


def tab_bar(on):
    y = SCH - 21
    out = f'<rect y="{n(SCH - 30)}" width="{n(SCW)}" height="30" fill="#0b0b0b"/><path d="M0 {n(SCH - 30)}H{n(SCW)}" stroke="#1c1c1e"/>'
    for k in range(4):
        x = SCW * (k + 0.5) / 4
        col = LIME if k == on else "#5a5a5f"
        out += f'<path d="{rrect(9, 9, 2.6, x, y)}" fill="none" stroke="{col}" stroke-width="1.3"/>'
        if k == on:
            out += f'<circle cx="{n(x)}" cy="{n(y + 9)}" r="1" fill="{LIME}"/>'
    out += f'<path d="{rrect(44, 2.6, 1.3, SCW / 2, SCH - 4)}" fill="#F5F3F1" opacity=".85"/>'
    return out


def app_stays(u):
    pics = {
        "a": ('<linearGradient id="{u}a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f5d25d"/><stop offset=".44" stop-color="#9bc22f"/>'
              '<stop offset=".46" stop-color="#1d2b3a"/><stop offset="1" stop-color="#0e1a26"/></linearGradient>', '<circle cx="{cx}" cy="{cy}" r="9" fill="#fff6d6" opacity=".9"/>'),
        "b": ('<linearGradient id="{u}b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2b1b14"/><stop offset=".55" stop-color="#6a5a2a"/>'
              '<stop offset="1" stop-color="#d9c95a"/></linearGradient>', ''),
        "c": ('<linearGradient id="{u}c" x1="0" y1="0" x2=".4" y2="1"><stop offset="0" stop-color="#24382b"/><stop offset=".6" stop-color="#10201a"/>'
              '<stop offset="1" stop-color="#0a120e"/></linearGradient>', '<circle cx="{cx}" cy="{cy}" r="6" fill="#fff3d6" opacity=".8"/>'),
        "d": ('<linearGradient id="{u}d" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e8ff8a"/><stop offset=".3" stop-color="#C6FF3D"/>'
              '<stop offset=".52" stop-color="#3a6e8a"/><stop offset="1" stop-color="#16384c"/></linearGradient>', '<circle cx="{cx}" cy="{cy}" r="7" fill="#fffbe0" opacity=".9"/>'),
    }
    stays = [("lake house", "ohrid", 64, "4.9", "a"), ("old town loft", "skopje", 48, "4.8", "b"),
             ("cabin, pines", "mavrovo", 72, "5.0", "c"), ("sea view room", "durres", 58, "4.7", "d")]
    defs = "".join(v[0].replace("{u}", u) for v in pics.values())
    pad = 11
    cw = SCW - 2 * pad
    card = []
    step = 100
    for i, (t, where, price, rate, art) in enumerate(stays + stays):
        y0 = i * step
        sun = pics[art][1].replace("{cx}", n(pad + cw * 0.72)).replace("{cy}", n(y0 + 18))
        win = ""
        if art == "b":
            win = "".join(f'<rect x="{n(pad + cw * f)}" y="{n(y0)}" width="{n(cw * 0.05)}" height="64" fill="#000" opacity=".3"/>' for f in (0.3, 0.62))
        card.append(
            f'<g><path d="{rrect(cw, 64, 9, pad + cw / 2, y0 + 32)}" fill="url(#{u}{art})"/>{sun}{win}'
            f'<circle cx="{n(pad + cw - 10)}" cy="{n(y0 + 10)}" r="5" fill="#000" opacity=".35"/>'
            f'<path d="M{n(pad + cw - 10)} {n(y0 + 12.6)}l-2.6-2.6a1.5 1.5 0 0 1 2.6-1.6a1.5 1.5 0 0 1 2.6 1.6z" fill="#fff"/>'
            f'<circle cx="{n(pad + cw / 2 - 5)}" cy="{n(y0 + 58)}" r="1.1" fill="#fff"/><circle cx="{n(pad + cw / 2)}" cy="{n(y0 + 58)}" r="1.1" fill="#fff" opacity=".5"/><circle cx="{n(pad + cw / 2 + 5)}" cy="{n(y0 + 58)}" r="1.1" fill="#fff" opacity=".5"/>'
            + sans(t, 7, pad + 1, y0 + 76, "#F5F3F1", SANS_B)
            + star(pad + cw - 17, y0 + 73.6, 3, "#F5F3F1") + sans(rate, 6.4, pad + cw, y0 + 76, "#F5F3F1", anchor="end")
            + sans(where, 6.2, pad + 1, y0 + 86, "#8e8e93")
            + sans(f"EUR {price} / night", 6.2, pad + cw, y0 + 86, "#c7c7cc", anchor="end") + '</g>')
    chips, x = [], pad
    for j, c in enumerate(("all", "lake", "city", "mountain")):
        _, w = SANS.path(c, 6.3, 0, 0)
        on = j == 0
        chips.append(f'<path d="{rrect(w + 12, 12.5, 6.25, x + (w + 12) / 2, 95)}" fill="{LIME if on else "#1c1c1e"}"/>'
                     + sans(c, 6.3, x + 6, 97.3, "#000" if on else "#c7c7cc", SANS_B if on else SANS))
        x += w + 16
    css = (f".{u}f{{animation:{u}f 16s cubic-bezier(.65,0,.35,1) infinite}}"
           f"@keyframes {u}f{{0%,18%{{transform:translateY(0)}}25%,43%{{transform:translateY(-{step}px)}}50%,68%{{transform:translateY(-{2 * step}px)}}"
           f"75%,93%{{transform:translateY(-{3 * step}px)}}100%{{transform:translateY(-{4 * step}px)}}}}"
           f".{u}t{{animation:{u}t 16s cubic-bezier(.2,.8,.2,1) infinite;transform:translateY(60px)}}"
           f"@keyframes {u}t{{0%,52%{{transform:translateY(60px)}}56%,68%{{transform:translateY(0)}}72%,100%{{transform:translateY(60px)}}}}")
    fy0 = 108
    s = (f'<rect width="{n(SCW)}" height="{n(SCH)}" fill="#0b0b0b"/>'
         + status_bar()
         + sans("good evening", 6.4, pad, 38, "#8e8e93")
         + sans("find a stay", 14.5, pad, 55, "#F5F3F1", SANS_X, tracking=-0.3)
         + f'<path d="{rrect(cw, 19, 9.5, SCW / 2, 72)}" fill="#1c1c1e"/><circle cx="{pad + 10}" cy="72" r="3" fill="none" stroke="#8e8e93" stroke-width="1.1"/>'
         + sans("where to?", 6.4, pad + 18, 74.3, "#8e8e93") + sans("3 nights", 6.4, pad + cw - 8, 74.3, LIME, anchor="end")
         + "".join(chips)
         + f'<g clip-path="url(#{u}fc)"><g transform="translate(0 {fy0})"><g class="{u}f">{"".join(card)}</g></g></g>'
         + f'<rect y="{fy0}" width="{n(SCW)}" height="10" fill="url(#{u}fade)"/>'
         + f'<g class="{u}t"><path d="{rrect(cw, 26, 9, SCW / 2, SCH - 48)}" fill="#1c1c1e" stroke="#2c2c2e" stroke-width=".6"/>'
         + f'<circle cx="{pad + 13}" cy="{n(SCH - 48)}" r="6" fill="{LIME}"/><path d="M{pad + 10.3} {n(SCH - 48)}l2 2 3.6-4" stroke="#000" stroke-width="1.3" fill="none"/>'
         + sans("booked", 6.6, pad + 24, SCH - 49.5, "#F5F3F1", SANS_B) + sans("3 nights, lake house", 5.8, pad + 24, SCH - 41.5, "#8e8e93") + '</g>'
         + tab_bar(0))
    defs += (f'<clipPath id="{u}fc"><rect y="{fy0}" width="{n(SCW)}" height="{n(SCH - fy0 - 30)}"/></clipPath>'
             f'<linearGradient id="{u}fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b0b0b"/><stop offset="1" stop-color="#0b0b0b" stop-opacity="0"/></linearGradient>')
    return defs, css, s


def app_folio(u):
    pad = 11
    cw = SCW - 2 * pad
    LINE_ = [(0, 40), (8, 37), (15, 39), (22, 33), (30, 35), (37, 28), (45, 30), (52, 24), (60, 26), (67, 19), (74, 22), (82, 14), (89, 16), (100, 8)]
    cx0, cy0, chw, chh = pad, 88, cw, 66
    pts = [(cx0 + x / 100 * chw, cy0 + y / 50 * chh) for x, y in LINE_]
    line = "M" + "L".join(f"{n(x)} {n(y)}" for x, y in pts)
    area = line + f"L{n(cx0 + chw)} {n(cy0 + chh)}L{n(cx0)} {n(cy0 + chh)}Z"
    grid = "".join(f"M{n(cx0)} {n(cy0 + chh * f)}H{n(cx0 + chw)}" for f in (0.25, 0.5, 0.75))
    ex, ey = pts[-1]
    hold = [("w", "world etf", "+0.8%", LIME), ("g", "gold", "+0.3%", "#FFD23A"), ("b", "bonds", "-0.1%", "#F0402A"), ("c", "cash", "0.0%", "#fff1c2")]
    rows = ""
    for i, (k, name, chg, col) in enumerate(hold):
        y = 196 + i * 18
        rows += (f'<circle cx="{pad + 6}" cy="{y}" r="6" fill="{col}"/>' + sans(k, 6.4, pad + 6, y + 2.3, "#000", SANS_B, anchor="middle")
                 + sans(name, 6.6, pad + 17, y + 2.3, "#F5F3F1")
                 + sans(chg, 6.6, pad + cw, y + 2.3, LIME if chg.startswith("+") else "#8e8e93", SANS_B, anchor="end")
                 + (f'<path d="M{pad + 17} {y + 9}H{n(pad + cw)}" stroke="#1c1c1e" stroke-width=".6"/>' if i < 3 else ""))
    rng = ""
    labels = ("1d", "1w", "1m", "1y", "all")
    for i, l in enumerate(labels):
        x = pad + cw * (i + 0.5) / 5
        rng += sans(l, 6.2, x, 174.3, "#8e8e93", SANS_B, anchor="middle")
    pill_w = cw / 5
    css = (f".{u}l{{stroke-dasharray:1;stroke-dashoffset:1;animation:{u}l 8s cubic-bezier(.65,0,.35,1) infinite}}"
           f"@keyframes {u}l{{0%{{stroke-dashoffset:1}}45%,88%{{stroke-dashoffset:0}}100%{{stroke-dashoffset:0;opacity:0}}}}"
           f".{u}a{{animation:{u}a 8s ease infinite}}@keyframes {u}a{{0%,30%{{opacity:0}}50%,88%{{opacity:1}}100%{{opacity:0}}}}"
           f".{u}p{{animation:{u}p 8s cubic-bezier(.65,0,.35,1) infinite}}"
           f"@keyframes {u}p{{0%,20%{{transform:translateX({n(pill_w * 2)}px)}}28%,100%{{transform:translateX({n(pill_w * 3)}px)}}}}"
           f".{u}r{{transform-box:fill-box;transform-origin:center;animation:{u}r 1.6s ease-out infinite}}"
           f"@keyframes {u}r{{from{{transform:scale(.6);opacity:.9}}to{{transform:scale(2.4);opacity:0}}}}")
    defs = (f'<linearGradient id="{u}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{LIME}" stop-opacity=".45"/>'
            f'<stop offset="1" stop-color="{LIME}" stop-opacity="0"/></linearGradient>')
    s = (f'<rect width="{n(SCW)}" height="{n(SCH)}" fill="#0b0b0b"/>' + status_bar()
         + sans("portfolio", 6.4, pad, 38, "#8e8e93")
         + sans("EUR 24,806", 15, pad, 56, "#F5F3F1", SANS_X, tracking=-0.3)
         + sans(".12", 9, pad + SANS_X.path("EUR 24,806", 15, 0, 0, -0.3)[1] + 1, 56, "#8e8e93", SANS_B)
         + f'<path d="{rrect(62, 11, 5.5, pad + 31, 68)}" fill="{LIME}" fill-opacity=".14"/>'
         + sans("+12.4% this year", 5.8, pad + 31, 70.1, LIME, SANS_B, anchor="middle")
         + f'<path d="{grid}" stroke="#1c1c1e" stroke-width=".7"/>'
         + f'<path class="{u}a" d="{area}" fill="url(#{u}g)"/>'
         + f'<path class="{u}l" d="{line}" pathLength="1" fill="none" stroke="{LIME}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>'
         + f'<circle cx="{n(ex)}" cy="{n(ey)}" r="2.2" fill="{LIME}"/><circle class="{u}r" cx="{n(ex)}" cy="{n(ey)}" r="2.2" fill="none" stroke="{LIME}"/>'
         + f'<g class="{u}p"><path d="{rrect(pill_w - 4, 11, 5.5, pad + pill_w / 2, 172)}" fill="#1c1c1e"/></g>' + rng
         + rows + tab_bar(1))
    return defs, css, s


def app_ride(u):
    ROUTE = [(18, 150), (30, 120, 22, 104, 44, 92), (66, 80, 78, 86, 80, 64), (82, 42, 70, 30, 96, 22), (122, 14, 130, 26, 134, 10)]
    sx, sy = SCW / 150, 205 / 160

    def P(x, y):
        return f"{n(x * sx)} {n(y * sy)}"

    route = f"M{P(*ROUTE[0])}" + "".join(f"C{P(c[0], c[1])} {P(c[2], c[3])} {P(c[4], c[5])}" for c in ROUTE[1:])
    blocks = "".join(f"M0 {n(y * sy)}H{n(SCW)}" for y in (40, 82, 124)) + "".join(f"M{n(x * sx)} 0V205" for x in (30, 66, 108))
    blocks += f"M0 {n(10 * sy)}L{n(SCW)} {n(120 * sy)}M{n(40 * sx)} 205L{n(SCW)} {n(60 * sy)}"
    water = f"M{P(110, 160)}C{P(118, 130)} {P(140, 128)} {P(150, 110)}V205H{n(110 * sx)}Z"
    speeds = [84, 87, 91, 96, 88, 79, 83, 90, 84]
    sheet_y = 192
    col = "".join(sans(str(v), 24, 0, i * 26, "#F5F3F1", SANS_X) for i, v in enumerate(speeds))
    nsp = len(speeds) - 1
    kf = "".join(f"{i * 100 / nsp:.2f}%{{transform:translateY({-i * 26}px)}}" for i in range(nsp + 1))
    css = (f".{u}l{{stroke-dasharray:1;stroke-dashoffset:1;animation:{u}l 9s linear infinite}}"
           f"@keyframes {u}l{{to{{stroke-dashoffset:0}}}}"
           f".{u}n{{animation:{u}n 9s steps(1) infinite}}@keyframes {u}n{{{kf}}}"
           f".{u}b{{animation:{u}b 1.2s steps(1) infinite}}@keyframes {u}b{{50%{{opacity:.25}}}}")
    stats = ""
    for i, (v, l) in enumerate((("42.6", "km"), ("38" + chr(176), "lean"), ("1:04", "moving"))):
        x = 11 + i * 40
        stats += sans(v, 9.5, x, sheet_y + 60, "#F5F3F1", SANS_X) + sans(l, 5.6, x, sheet_y + 69, "#8e8e93")
    s = (f'<rect width="{n(SCW)}" height="{n(SCH)}" fill="#0d0f12"/>'
         f'<path d="{blocks}" stroke="#1b2028" stroke-width="2.4"/>'
         f'<path d="{water}" fill="#0f2534"/>'
         f'<path d="{route}" stroke="#262b33" stroke-width="6" fill="none" stroke-linecap="round"/>'
         f'<path class="{u}l" d="{route}" pathLength="1" stroke="{LIME}" stroke-width="2.6" fill="none" stroke-linecap="round"/>'
         f'<g><animateMotion dur="9s" repeatCount="indefinite" path="{route}"/>'
         f'<circle r="9" fill="{LIME}" opacity=".18"/><circle r="4" fill="#fff"/><circle r="2.6" fill="{LIME}"/></g>'
         + status_bar()
         + f'<path d="{rrect(30, 13, 6.5, 26, 36)}" fill="#141416" fill-opacity=".9"/><circle class="{u}b" cx="17" cy="36" r="2.2" fill="#F0402A"/>'
         + sans("rec", 6, 22, 38.2, "#F5F3F1", SANS_B)
         + f'<path d="{rrect(40, 13, 6.5, SCW - 31, 36)}" fill="#141416" fill-opacity=".9"/>' + sans("00:42:18", 6, SCW - 31, 38.2, "#F5F3F1", SANS_B, anchor="middle")
         + f'<path d="{rrect(SCW, 140, 16, SCW / 2, sheet_y + 70)}" fill="#161618" fill-opacity=".97"/>'
         + f'<path d="{rrect(22, 2.4, 1.2, SCW / 2, sheet_y + 6)}" fill="#3a3a3c"/>'
         + f'<clipPath id="{u}nc"><rect x="10" y="{sheet_y + 18}" width="60" height="26"/></clipPath>'
         + f'<g clip-path="url(#{u}nc)"><g transform="translate(11 {sheet_y + 40})"><g class="{u}n">{col}</g></g></g>'
         + sans("km/h", 6.4, 50, sheet_y + 40, "#8e8e93", SANS_B)
         + stats
         + f'<path d="{rrect(SCW - 22, 18, 9, SCW / 2, sheet_y + 86)}" fill="#F5F3F1"/>'
         + f'<rect x="{n(SCW / 2 - 22)}" y="{sheet_y + 83}" width="6" height="6" rx="1" fill="#F0402A"/>'
         + sans("end ride", 7, SCW / 2 + 4, sheet_y + 88.6, "#000", SANS_B, anchor="middle")
         + f'<path d="{rrect(44, 2.6, 1.3, SCW / 2, SCH - 4)}" fill="#F5F3F1" opacity=".85"/>')
    return "", css, s


def ease_io(x):
    return x * x * (3 - 2 * x)


def build_apps():
    H = 640
    F, CX, CY = 1500.0, 600.0, 292.0
    DUR = 16
    TAU = 2 * math.pi

    def left(t):
        return (-300, 8 * math.sin(TAU * t), 1600, math.radians(-26 + 7 * math.sin(TAU * t)),
                math.radians(-6 + 2.5 * math.sin(TAU * t + 1.3)), math.radians(1.5 * math.sin(TAU * t)))

    def right(t):
        return (300, 8 * math.sin(TAU * t + 2), 1600, math.radians(26 + 7 * math.sin(TAU * t + 2)),
                math.radians(-6 + 2.5 * math.sin(TAU * t + 3)), math.radians(-1.5 * math.sin(TAU * t + 2)))

    def center(t):
        spin = 0.0
        if 0.58 < t < 0.86:
            spin = TAU * ease_io((t - 0.58) / 0.28)
        elif t >= 0.86:
            spin = TAU
        return (0, 12 + 10 * math.sin(TAU * t * 2), 1330, math.radians(11 * math.sin(TAU * t)) + spin,
                math.radians(-5 + 3 * math.sin(TAU * t * 2)), math.radians(1.2 * math.sin(TAU * t)))

    defs, css, body = [], [], []
    scenes = [("pl", left, 96, "natural", app_stays), ("pr", right, 96, "desert", app_ride), ("pc", center, 224, "black", app_folio)]
    phones = []
    centers = []
    for uid, pose, N, fin, app in scenes:
        d, c, s = app(uid + "x")
        defs.append(d)
        css.append(c)
        fr = phone_track(pose, N, F, CX, CY)
        phones.append(iphone(uid, fr, DUR, fin, s, defs))
        centers.append((fr, pose))

    # floor, shadows, glow
    FLOOR = -230.0
    fy = lambda z: CY - F * FLOOR / z
    SP, ZMIN, NL, GN, GDUR = 110.0, 600.0, 26, 10, 3.0
    hl = []
    for k in range(NL):
        vals = []
        for j in range(GN + 1):
            z = ZMIN + k * SP - SP * j / GN
            vals.append(f"M0 {n(min(fy(z), H + 40))}H{W}")
        hl.append(f'<path d="{vals[0]}"><animate attributeName="d" values="{";".join(vals)}" dur="{GDUR}s" repeatCount="indefinite"/></path>')
    vl = ""
    x = -3000.0
    while x <= 3000:
        vl += f"M{n(CX + F * x / 500)} {n(fy(500))}L{n(CX + F * x / 9000)} {n(fy(9000))}"
        x += SP * 1.2
    horizon = fy(9000)
    shadows = ""
    for (fr, pose), sc in zip(centers, (1, 1, 1.15)):
        X, Y, Z = pose(0)[:3]
        sx_, sy_ = CX + F * X / Z, fy(Z)
        shadows += (f'<ellipse cx="{n(sx_)}" cy="{n(sy_)}" rx="{n(120 * sc)}" ry="{n(14 * sc)}" fill="url(#pglow)"/>'
                    f'<ellipse cx="{n(sx_)}" cy="{n(sy_)}" rx="{n(80 * sc)}" ry="{n(8 * sc)}" fill="url(#pshd)"/>')
    ghost, gw = DISPLAY.path("MOBILE", 250, 0, 0, 10)
    labels = ""
    for (fr, pose), (num, a, b) in zip(centers, (("01", "STAYS", "BOOKING"), ("03", "RIDE", "TRACKING"), ("02", "PORTFOLIO", "FINTECH"))):
        X, _, Z = pose(0)[:3]
        lx = CX + F * X / Z
        labels += (mono(num, 10.5, lx - 4, H - 40, LIME, anchor="end") + mono(f"{a} / {b}", 10.5, lx + 4, H - 40, BONE, op=.8))
    allcss = (
        ".ghost{animation:gh 30s linear infinite}@keyframes gh{from{transform:translateX(0)}to{transform:translateX(-" + n(gw + 120) + "px)}}"
        ".ph{animation:phin 1.4s cubic-bezier(.2,.8,.2,1) both}@keyframes phin{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:none}}"
        + "".join(css) + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
    ghost_row = "".join(f'<path transform="translate({n(k * (gw + 120))} 0)" d="{ghost}"/>' for k in range(3))
    br = 18
    hud = "".join(f"M{x0} {y0 + dy * br}V{y0}H{x0 + dx * br}" for x0, y0, dx, dy in
                  ((24, 24, 1, 1), (W - 24, 24, -1, 1), (24, H - 24, 1, -1), (W - 24, H - 24, -1, -1)))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><style>{allcss}</style>
<radialGradient id="pbg" cx=".5" cy=".42" r=".6"><stop offset="0" stop-color="#1a1d14"/><stop offset=".55" stop-color="#0e0f10"/><stop offset="1" stop-color="{BG}"/></radialGradient>
<radialGradient id="pglow"><stop offset="0" stop-color="{LIME}" stop-opacity=".22"/><stop offset="1" stop-color="{LIME}" stop-opacity="0"/></radialGradient>
<radialGradient id="pshd"><stop offset="0" stop-color="#000" stop-opacity=".9"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
<linearGradient id="phz" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="{BG}" stop-opacity="0"/></linearGradient>
<linearGradient id="pbt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG}" stop-opacity="0"/><stop offset="1" stop-color="{BG}"/></linearGradient>
<clipPath id="pclip"><rect width="{W}" height="{H}"/></clipPath>
{"".join(defs)}</defs>
<g clip-path="url(#pclip)">
<rect width="{W}" height="{H}" fill="url(#pbg)"/>
<g transform="translate(40 330)" fill="none" stroke="{BONE}" stroke-opacity=".06" stroke-width="1.5"><g class="ghost">{ghost_row}</g></g>
<g stroke="{GRID}" fill="none">{"".join(hl)}<path d="{vl}"/></g>
<rect y="{n(horizon - 2)}" width="{W}" height="110" fill="url(#phz)"/>
<rect y="{H - 90}" width="{W}" height="90" fill="url(#pbt)"/>
<path d="M0 {n(horizon)}H{W}" stroke="{LIME}" stroke-opacity=".18"/>
{shadows}
<g class="ph" style="animation-delay:.1s">{phones[0]}</g>
<g class="ph" style="animation-delay:.25s">{phones[1]}</g>
<g class="ph">{phones[2]}</g>
<path d="{hud}" fill="none" stroke="{BONE}" stroke-opacity=".4"/>
{mono("MOBILE / IOS + ANDROID", 11, 52, 46, BONE, op=.85)}
{mono("LIVE SCREENS / NO VIDEO", 11, W - 52, 46, MUTED, anchor="end")}
{labels}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" fill="none" stroke="{LINE}"/>
</svg>'''
    write("apps.svg", svg)


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
    build_apps()
    build_header("02", "APPS WE SHIP", "MOBILE", "h-apps.svg", 0.6)
    build_header("03", "HOW WE WORK", "PROCESS", "h-process.svg", 1.2)
    build_process()
    build_header("04", "STACK", "TOOLS WE SHIP WITH", "h-stack.svg", 2.4)
    build_stack()
    build_footer()
