#!/usr/bin/env python3
"""Food Picture 01 - a top-down sushi platter, drawn procedurally.

Pure Python standard library. Renders an 800x800 RGB PNG (entry.png)
with a hand-written PNG encoder. Fully deterministic.
"""

import math
import os
import struct
import zlib

W = 800
H = 800

# Framebuffer: RGB bytes, row-major.
FB = bytearray(W * H * 3)


def clamp(v):
    if v < 0:
        return 0
    if v > 255:
        return 255
    return int(v)


def set_px(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        FB[i] = clamp(r)
        FB[i + 1] = clamp(g)
        FB[i + 2] = clamp(b)


def blend_px(x, y, r, g, b, a):
    """Alpha-blend colour (r,g,b) over the current pixel with weight a."""
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        if a >= 1.0:
            set_px(x, y, r, g, b)
            return
        i = (y * W + x) * 3
        ia = 1.0 - a
        FB[i] = clamp(FB[i] * ia + r * a)
        FB[i + 1] = clamp(FB[i + 1] * ia + g * a)
        FB[i + 2] = clamp(FB[i + 2] * ia + b * a)


def hash2(x, y):
    """Deterministic 2D hash -> 0..1 (for grain / noise)."""
    n = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFF) / 255.0


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


# ---------------------------------------------------------------- PNG output

def write_png(path):
    raw = bytearray()
    rowlen = W * 3
    for y in range(H):
        raw.append(0)  # filter type 0 for every scanline
        raw += FB[y * rowlen:(y + 1) * rowlen]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------- background

def draw_background():
    """Dark charcoal table: subtle noise plus a soft vignette."""
    cx = W * 0.5
    cy = H * 0.5
    maxd2 = cx * cx + cy * cy
    dx2 = [(x - cx) * (x - cx) for x in range(W)]
    for y in range(H):
        dy = y - cy
        dy2 = dy * dy
        row = y * W * 3
        for x in range(W):
            d2 = (dx2[x] + dy2) / maxd2
            vig = 1.0 - 0.52 * d2
            n = (hash2(x, y) - 0.5) * 11.0
            base = 40.0 * vig + n
            i = row + x * 3
            FB[i] = clamp(base * 0.96)
            FB[i + 1] = clamp(base * 0.99)
            FB[i + 2] = clamp(base * 1.10)


def ellipse(cx, cy, rx, ry, fn, blend=False):
    """Fill an axis-aligned ellipse. fn(u, v, d) -> (r, g, b) or None.

    u, v are normalised coords (-1..1); d is the normalised radius 0..1.
    With blend=True, fn returns (r, g, b, a) and the colour is alpha-blended.
    """
    x0 = max(0, int(cx - rx - 1))
    x1 = min(W - 1, int(cx + rx + 1))
    y0 = max(0, int(cy - ry - 1))
    y1 = min(H - 1, int(cy + ry + 1))
    for y in range(y0, y1 + 1):
        v = (y - cy) / ry
        vv = v * v
        if vv > 1.0:
            continue
        for x in range(x0, x1 + 1):
            u = (x - cx) / rx
            d2 = u * u + vv
            if d2 <= 1.0:
                if blend:
                    c = fn(u, v, math.sqrt(d2))
                    if c is not None:
                        blend_px(x, y, c[0], c[1], c[2], c[3])
                else:
                    c = fn(u, v, math.sqrt(d2))
                    if c is not None:
                        set_px(x, y, c[0], c[1], c[2])


def soft_shadow(cx, cy, rx, ry):
    """A soft dark ellipse used as a drop shadow under a piece of food."""
    def fn(u, v, d):
        a = 0.42 * (1.0 - d) * (1.0 - d)
        return (0, 0, 0, a)
    ellipse(cx, cy, rx, ry, fn, blend=True)


def draw_platter():
    """Big dark slate platter: outer rim, inner face, faint top light."""
    def rim(u, v, d):
        # Outer rim ring slightly lighter than the face.
        if d > 0.965:
            return (47, 51, 59)
        return None

    def face(u, v, d):
        # Gentle radial shading: lighter toward upper middle.
        light = 1.0 - 0.35 * d
        warm = 1.0 - 0.25 * v  # brighter at the top
        base = 60.0 * light * warm
        n = (hash2(int(u * 400 + 900), int(v * 400 + 900)) - 0.5) * 7.0
        return (base + n, base * 1.02 + n, base * 1.14 + n)

    ellipse(400, 415, 348, 330, face)
    ellipse(400, 415, 348, 330, rim)
    # Thin bright arc along the top rim to suggest a glazed edge.
    def arc(u, v, d):
        if v < -0.86 and 0.965 < d <= 1.0:
            return (110, 118, 130, 0.35)
        return None
    ellipse(400, 415, 348, 330, arc, blend=True)


# ---------------------------------------------------------------- shapes

def rrect(cx, cy, hw, hh, rad, rot_deg, fn, blend=False):
    """Fill a rotated rounded rectangle centred at (cx, cy).

    hw/hh are half width/height, rad the corner radius. fn(nx, ny, lx, ly)
    receives normalised coords (-1..1) and local pixel coords, and returns
    (r, g, b) (or (r, g, b, a) when blend=True), or None to skip the pixel.
    """
    rot = math.radians(rot_deg)
    cs = math.cos(rot)
    sn = math.sin(rot)
    ext = math.hypot(hw, hh) + 2
    x0 = max(0, int(cx - ext))
    x1 = min(W - 1, int(cx + ext))
    y0 = max(0, int(cy - ext))
    y1 = min(H - 1, int(cy + ext))
    for y in range(y0, y1 + 1):
        dy = y - cy
        for x in range(x0, x1 + 1):
            dx = x - cx
            lx = dx * cs + dy * sn
            ly = -dx * sn + dy * cs
            ax = abs(lx)
            ay = abs(ly)
            if ax > hw or ay > hh:
                continue
            # Rounded-corner test via the inner rectangle.
            ix = ax - (hw - rad)
            iy = ay - (hh - rad)
            if ix > 0 and iy > 0 and ix * ix + iy * iy > rad * rad:
                continue
            if blend:
                c = fn(lx / hw, ly / hh, lx, ly)
                if c is not None:
                    blend_px(x, y, c[0], c[1], c[2], c[3])
            else:
                c = fn(lx / hw, ly / hh, lx, ly)
                if c is not None:
                    set_px(x, y, c[0], c[1], c[2])


def gloss(nx, ny, gx, gy, gw, strength):
    """Elongated specular highlight value 0..strength at (nx, ny)."""
    dx = (nx - gx) / gw
    dy = (ny - gy) / (gw * 0.45)
    d2 = dx * dx + dy * dy
    if d2 >= 1.0:
        return 0.0
    return strength * (1.0 - d2) * (1.0 - d2)


# ---------------------------------------------------------------- nigiri

def draw_rice(cx, cy, rot):
    """The white rice block under a nigiri topping."""
    def fn(nx, ny, lx, ly):
        # plump shading: bright centre-top, darker rim
        shade = 1.0 - 0.16 * (nx * nx) - 0.10 * (ny * ny)
        grain = (hash2(int(lx * 3 + 500), int(ly * 3 + 500)) - 0.5) * 14.0
        base = 238.0 * shade + grain
        return (base, base * 0.985, base * 0.94)
    rrect(cx, cy, 84, 45, 34, rot, fn)


def draw_salmon(cx, cy, rot):
    def fn(nx, ny, lx, ly):
        # Salmon: orange-pink gradient with pale diagonal fat stripes.
        base = mix((244, 118, 82), (252, 152, 108), 0.5 - 0.5 * ny)
        phase = (lx * 0.045 + ly * 0.028) % 1.0
        if phase < 0.30:
            base = mix(base, (253, 214, 188), 0.75)
        elif phase < 0.38:
            base = mix(base, (253, 190, 160), 0.4)
        edge = 1.0 - 0.13 * (nx * nx + ny * ny)
        g = gloss(nx, ny, -0.25, -0.35, 0.62, 0.55)
        return (base[0] * edge + 255 * g,
                base[1] * edge + 255 * g,
                base[2] * edge + 245 * g)
    rrect(cx, cy, 86, 43, 30, rot, fn)


def draw_tuna(cx, cy, rot):
    def fn(nx, ny, lx, ly):
        base = mix((148, 18, 38), (186, 34, 54), 0.5 - 0.5 * ny)
        # faint flesh grain lines
        if (int(lx * 0.5 + ly * 0.16) % 9) == 0:
            base = mix(base, (205, 70, 84), 0.25)
        edge = 1.0 - 0.15 * (nx * nx + ny * ny)
        g = gloss(nx, ny, -0.22, -0.38, 0.6, 0.6)
        return (base[0] * edge + 255 * g,
                base[1] * edge + 250 * g,
                base[2] * edge + 245 * g)
    rrect(cx, cy, 86, 43, 30, rot, fn)


def draw_tamago(cx, cy, rot):
    def fn(nx, ny, lx, ly):
        base = mix((240, 178, 44), (252, 205, 84), 0.5 - 0.5 * ny)
        edge = 1.0 - 0.12 * (nx * nx + ny * ny)
        g = gloss(nx, ny, -0.25, -0.35, 0.6, 0.4)
        return (base[0] * edge + 255 * g,
                base[1] * edge + 255 * g,
                base[2] * edge + 240 * g)
    rrect(cx, cy, 84, 44, 26, rot, fn)
    # Dark nori band wrapped across the middle.
    def band(nx, ny, lx, ly):
        shade = 1.0 - 0.25 * abs(ny)
        g = gloss(nx, ny, 0.0, -0.4, 0.5, 0.35)
        return (22 * shade + 200 * g, 34 * shade + 200 * g, 30 * shade + 190 * g)
    rrect(cx, cy, 17, 47, 8, rot, band)


def draw_nigiri(cx, cy, rot, kind):
    soft_shadow(cx + 7, cy + 12, 95, 52)
    draw_rice(cx, cy + 5, rot)
    if kind == "salmon":
        draw_salmon(cx, cy - 4, rot)
    elif kind == "tuna":
        draw_tuna(cx, cy - 4, rot)
    else:
        draw_tamago(cx, cy - 4, rot)


# ---------------------------------------------------------------- maki

def draw_maki(cx, cy, r):
    soft_shadow(cx + 5, cy + 8, r + 6, r + 4)

    def nori(u, v, d):
        n = (hash2(int(u * 90 + 300), int(v * 90 + 300)) - 0.5) * 10.0
        return (16 + n, 26 + n, 22 + n)
    ellipse(cx, cy, r, r * 0.92, nori)

    def rice(u, v, d):
        if d > 0.80:
            return None
        grain = (hash2(int(u * 160 + 700), int(v * 160 + 700)) - 0.5) * 16.0
        base = 240.0 - 26.0 * d + grain
        return (base, base * 0.985, base * 0.94)
    ellipse(cx, cy, r, r * 0.92, rice)

    def centre(u, v, d):
        if d > 0.46:
            return None
        base = mix((246, 122, 84), (252, 156, 110), 0.5 - 0.5 * v)
        g = gloss(u, v, -0.3, -0.35, 0.8, 0.4)
        return (base[0] + 230 * g, base[1] + 230 * g, base[2] + 220 * g)
    ellipse(cx, cy, r, r * 0.92, centre)

    def avocado(u, v, d):
        if d > 0.55:
            return None
        return mix((148, 196, 92), (178, 216, 122), 0.5 - 0.5 * v)
    ellipse(cx + r * 0.30, cy + r * 0.26, r * 0.20, r * 0.18, avocado)
    ellipse(cx - r * 0.32, cy + r * 0.24, r * 0.17, r * 0.15, avocado)


# ---------------------------------------------------------------- garnish

def draw_wasabi(cx, cy):
    soft_shadow(cx + 5, cy + 7, 40, 26)

    def fn(u, v, d):
        base = mix((74, 148, 52), (116, 186, 78), 1.0 - d)
        bump = (hash2(int(u * 40 + 100), int(v * 40 + 100)) - 0.5) * 18.0
        return (base[0] + bump, base[1] + bump, base[2] + bump)
    ellipse(cx, cy, 36, 27, fn)
    ellipse(cx - 10, cy - 12, 20, 14, fn)


def draw_ginger(cx, cy):
    """A loose pile of pink pickled-ginger petals."""
    petals = [(-30, 2, 29, 10, -24), (2, -12, 31, 11, 10), (28, 4, 28, 10, 30),
              (-14, 15, 27, 10, 40), (16, 18, 26, 9, -12), (0, 0, 25, 10, 62),
              (-34, 16, 24, 9, 75), (32, -10, 24, 9, -48)]
    for dx, dy, rx, ry, rot in petals:
        soft_shadow(cx + dx + 3, cy + dy + 5, rx, ry)

        def fn(nx, ny, lx, ly, rot=rot):
            base = mix((243, 168, 178), (250, 198, 205), 0.5 - 0.5 * ny)
            edge = 1.0 - 0.10 * (nx * nx + ny * ny)
            g = gloss(nx, ny, -0.2, -0.3, 0.7, 0.3)
            return (base[0] * edge + 255 * g,
                    base[1] * edge + 255 * g,
                    base[2] * edge + 250 * g)
        rrect(cx + dx, cy + dy, rx, ry, ry - 2, rot, fn)


def draw_shiso(cx, cy, rot):
    """A green shiso leaf: pointed ellipse with a darker vein."""
    soft_shadow(cx + 5, cy + 8, 66, 44)

    def fn(nx, ny, lx, ly):
        # Pointed tip toward +x: shrink the allowed height as nx grows.
        taper = 1.0 - 0.55 * max(0.0, nx)
        if abs(ny) > taper:
            return None
        base = mix((38, 116, 52), (66, 152, 74), 0.5 - 0.5 * ny)
        if abs(ly) < 1.6:  # central vein
            base = mix(base, (120, 190, 110), 0.55)
        serr = (hash2(int(lx * 2 + 60), int(ly * 2 + 60)) - 0.5) * 12.0
        return (base[0] + serr, base[1] + serr, base[2] + serr)
    rrect(cx, cy, 64, 42, 40, rot, fn)


def draw_soy_dish(cx, cy):
    soft_shadow(cx + 6, cy + 10, 66, 50)

    def rim(u, v, d):
        base = mix((168, 178, 190), (205, 214, 224), 0.5 - 0.5 * v)
        return (base[0], base[1], base[2])
    ellipse(cx, cy, 60, 46, rim)

    def soy(u, v, d):
        if d > 0.80:
            return None
        base = mix((38, 16, 10), (74, 36, 18), d)
        return base
    ellipse(cx, cy, 60, 46, soy)

    def shine(u, v, d):
        g = gloss(u, v, -0.35, -0.45, 0.42, 0.75)
        if g <= 0.0:
            return None
        return (255, 250, 240, g)
    ellipse(cx, cy, 60, 46, shine, blend=True)


# ---------------------------------------------------------------- compose

def compose():
    draw_background()
    draw_platter()

    draw_shiso(168, 322, -28)

    # Back row of nigiri, then front row.
    draw_nigiri(252, 218, -11, "salmon")
    draw_nigiri(408, 192, 5, "tuna")
    draw_nigiri(560, 222, 13, "salmon")
    draw_nigiri(320, 348, -5, "tuna")
    draw_nigiri(482, 352, 8, "tamago")

    # Row of maki rolls along the front of the platter.
    draw_maki(238, 512, 47)
    draw_maki(330, 532, 49)
    draw_maki(424, 540, 50)
    draw_maki(518, 532, 49)
    draw_maki(608, 512, 47)

    draw_wasabi(648, 392)
    draw_ginger(188, 452)
    draw_soy_dish(626, 618)


def main():
    compose()
    outdir = (os.environ.get("ENTRY_OUT")
              or os.environ.get("MAKEFUN_OUTPUT_DIR")
              or "/output")
    os.makedirs(outdir, exist_ok=True)
    write_png(os.path.join(outdir, "entry.png"))


if __name__ == "__main__":
    main()
