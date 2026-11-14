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
        a = 0.56 * (1.0 - d) * (1.0 - d)
        return (0, 0, 0, a)
    ellipse(cx, cy, rx, ry, fn, blend=True)


def draw_warm_glow():
    """Very subtle warm radial light centred on the platter."""
    def fn(u, v, d):
        a = 0.14 * (1.0 - d) * (1.0 - d)
        return (255, 206, 148, a)
    ellipse(400, 402, 372, 352, fn, blend=True)


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

    ellipse(400, 402, 364, 346, face)
    ellipse(400, 402, 364, 346, rim)
    # Thin bright arc along the top rim to suggest a glazed edge.
    def arc(u, v, d):
        if v < -0.86 and 0.965 < d <= 1.0:
            return (110, 118, 130, 0.35)
        return None
    ellipse(400, 402, 364, 346, arc, blend=True)


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


def sheen(nx, ny):
    """Soft diagonal wet-sheen band across a topping, 0..1."""
    s = (nx - ny - 0.15) / 0.9
    v = 1.0 - s * s
    return v if v > 0.0 else 0.0


def _lcg(seed):
    """Deterministic linear congruential generator of floats in 0..1."""
    state = (seed * 2654435761 + 97) & 0x7FFFFFFF
    while True:
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        yield state / 2147483648.0


def _grain_stamp(gx, gy, ang, light):
    """One small elongated rice grain centred near (gx, gy)."""
    ca = math.cos(ang)
    sa = math.sin(ang)
    if light:
        col = (255, 253, 245)
        a = 0.62
    else:
        col = (196, 188, 164)
        a = 0.55
    for t in (-2.0, -1.0, 0.0, 1.0, 2.0):
        px = int(round(gx + ca * t))
        py = int(round(gy + sa * t))
        blend_px(px, py, col[0], col[1], col[2], a)
        if -1.0 <= t <= 1.0:
            blend_px(int(round(gx - sa + ca * t)),
                     int(round(gy + ca + sa * t)),
                     col[0], col[1], col[2], a * 0.55)


def rice_grains_rrect(cx, cy, hw, hh, rad, rot, seed):
    """Scatter fine grain speckle over a rotated rounded-rect rice block."""
    rnd = _lcg(seed)
    rot_r = math.radians(rot)
    cs = math.cos(rot_r)
    sn = math.sin(rot_r)
    for _ in range(170):
        lx = (next(rnd) * 2.0 - 1.0) * (hw - 4)
        ly = (next(rnd) * 2.0 - 1.0) * (hh - 3)
        ix = abs(lx) - (hw - rad)
        iy = abs(ly) - (hh - rad)
        if ix > 0 and iy > 0 and ix * ix + iy * iy > rad * rad:
            continue
        gx = cx + lx * cs - ly * sn
        gy = cy + lx * sn + ly * cs
        _grain_stamp(gx, gy, next(rnd) * math.pi, next(rnd) < 0.55)


def rice_grains_ring(cx, cy, r, seed):
    """Scatter fine grain speckle over a maki rice ring (annulus)."""
    rnd = _lcg(seed)
    for _ in range(105):
        theta = next(rnd) * 2.0 * math.pi
        fr = 0.53 + next(rnd) * 0.24
        gx = cx + math.cos(theta) * fr * r
        gy = cy + math.sin(theta) * fr * r * 0.92
        _grain_stamp(gx, gy, theta + 1.1 + (next(rnd) - 0.5) * 0.7,
                     next(rnd) < 0.55)


# ---------------------------------------------------------------- nigiri

def draw_rice(cx, cy, rot):
    """The white rice block under a nigiri topping."""
    def fn(nx, ny, lx, ly):
        # plump shading: bright centre-top, darker rim
        shade = 1.0 - 0.16 * (nx * nx) - 0.10 * (ny * ny)
        grain = (hash2(int(lx * 3 + 500), int(ly * 3 + 500)) - 0.5) * 14.0
        base = 238.0 * shade + grain
        return (base, base * 0.985, base * 0.94)
    rrect(cx, cy, 99, 52, 38, rot, fn)
    # Fine elongated grain speckle over the whole block; the topping
    # covers the middle, so the texture reads on the exposed rim.
    rice_grains_rrect(cx, cy, 99, 52, 38, rot, int(cx) * 131 + int(cy))


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
        g = gloss(nx, ny, -0.25, -0.35, 0.80, 0.88)
        sh = sheen(nx, ny) * 36.0
        return (base[0] * edge + 255 * g + sh,
                base[1] * edge + 255 * g + sh,
                base[2] * edge + 245 * g + sh * 0.9)
    rrect(cx, cy, 95, 47, 34, rot, fn)


def draw_tuna(cx, cy, rot):
    def fn(nx, ny, lx, ly):
        base = mix((148, 18, 38), (186, 34, 54), 0.5 - 0.5 * ny)
        # faint flesh grain lines
        if (int(lx * 0.5 + ly * 0.16) % 9) == 0:
            base = mix(base, (205, 70, 84), 0.25)
        edge = 1.0 - 0.15 * (nx * nx + ny * ny)
        g = gloss(nx, ny, -0.22, -0.38, 0.72, 1.0)
        sh = sheen(nx, ny) * 32.0
        return (base[0] * edge + 255 * g + sh,
                base[1] * edge + 250 * g + sh,
                base[2] * edge + 245 * g + sh * 0.9)
    rrect(cx, cy, 95, 47, 34, rot, fn)


def draw_tamago(cx, cy, rot):
    def fn(nx, ny, lx, ly):
        base = mix((240, 178, 44), (252, 205, 84), 0.5 - 0.5 * ny)
        edge = 1.0 - 0.12 * (nx * nx + ny * ny)
        g = gloss(nx, ny, -0.25, -0.35, 0.7, 0.65)
        sh = sheen(nx, ny) * 24.0
        return (base[0] * edge + 255 * g + sh,
                base[1] * edge + 255 * g + sh,
                base[2] * edge + 240 * g + sh * 0.85)
    rrect(cx, cy, 95, 49, 30, rot, fn)
    # Dark nori band wrapped across the middle.
    def band(nx, ny, lx, ly):
        shade = 1.0 - 0.25 * abs(ny)
        g = gloss(nx, ny, 0.0, -0.4, 0.5, 0.35)
        return (22 * shade + 200 * g, 34 * shade + 200 * g, 30 * shade + 190 * g)
    rrect(cx, cy, 17, 54, 8, rot, band)


def draw_nigiri(cx, cy, rot, kind):
    soft_shadow(cx + 8, cy + 14, 110, 62)
    draw_rice(cx, cy + 6, rot)
    garnish_seed = int(cx) * 71 + int(cy) * 13 + 7
    if kind == "salmon":
        draw_salmon(cx, cy - 5, rot)
        draw_scallion_rings(cx, cy - 5, rot, garnish_seed)
    elif kind == "tuna":
        draw_tuna(cx, cy - 5, rot)
        draw_scallion_rings(cx, cy - 5, rot, garnish_seed)
    else:
        draw_tamago(cx, cy - 5, rot)
        draw_sesame(cx, cy - 5, rot, garnish_seed)


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
    rice_grains_ring(cx, cy, r, int(cx) * 57 + int(cy) * 3 + 11)

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


# ---------------------------------------------------------------- gunkan

def draw_gunkan(cx, cy, r):
    """Ikura gunkan: a nori cup of rice crowned with glossy salmon roe."""
    soft_shadow(cx + 6, cy + 11, r + 9, r * 0.96 + 7)

    # Nori cup wall: tall dark cylinder seen from above, shaded low side.
    def wall(u, v, d):
        n = (hash2(int(u * 90 + 300), int(v * 90 + 300)) - 0.5) * 10.0
        shade = 1.0 - 0.34 * max(0.0, v)
        return ((17 + n) * shade + 5, (27 + n) * shade + 7,
                (23 + n) * shade + 5)
    ellipse(cx, cy + r * 0.07, r, r * 0.97, wall)

    # Rice bed just inside the rim.
    def rice(u, v, d):
        if d > 0.88:
            return None
        grain = (hash2(int(u * 170 + 700), int(v * 170 + 700)) - 0.5) * 15.0
        base = 238.0 - 22.0 * d + grain
        return (base, base * 0.985, base * 0.94)
    ellipse(cx, cy - r * 0.05, r * 0.94, r * 0.89, rice)

    # Salmon-roe pearls on a triangular lattice, each with its own
    # specular dot and a slight per-pearl orange gradient. A touch of
    # deterministic jitter in position and size keeps the mound from
    # looking machine-stamped.
    pr = r * 0.185
    step = pr * 1.72
    tones = _lcg(int(cx) * 31 + int(cy) * 7 + 5)
    jit = _lcg(int(cx) * 17 + int(cy) * 13 + 3)
    row = 0
    yy = -r * 0.56
    while yy <= r * 0.56:
        xx = -r * 0.60 + (step * 0.5 if row % 2 else 0.0)
        while xx <= r * 0.60:
            # Elliptical containment, matching the cup's top face.
            q = (xx / (r * 0.72)) ** 2 + ((yy - r * 0.02) / (r * 0.66)) ** 2
            if q <= 1.0:
                tone = next(tones)
                pcx = cx + xx + (next(jit) - 0.5) * 3.0
                pcy = cy - r * 0.02 + yy + (next(jit) - 0.5) * 3.0
                ppr = pr * (0.92 + next(jit) * 0.16)

                def pearl(u, v, d, tone=tone):
                    base = mix((228, 78, 26), (252, 138, 58), tone)
                    base = mix(base, (255, 172, 96), (0.5 - 0.5 * v) * 0.55)
                    edge = 1.0 - 0.20 * d * d
                    g = gloss(u, v, -0.34, -0.40, 0.52, 1.0)
                    return (base[0] * edge + 255 * g,
                            base[1] * edge + 255 * g,
                            base[2] * edge + 250 * g)
                ellipse(pcx, pcy, ppr, ppr * 0.94, pearl)
            xx += step
        yy += step * 0.88
        row += 1


# ---------------------------------------------------------------- garnish

def _local_to_world(cx, cy, rot, lx, ly):
    """Convert topping-local coords to world coords for a rotated piece."""
    rot_r = math.radians(rot)
    cs = math.cos(rot_r)
    sn = math.sin(rot_r)
    return (cx + lx * cs - ly * sn, cy + lx * sn + ly * cs)


def draw_scallion_rings(cx, cy, rot, seed, count=5):
    """Tiny sliced scallion rings scattered over a nigiri topping.

    Each ring is a small circle: dark green skin, brighter green wall,
    pale hollow centre. Positions are deterministic, from the piece seed.
    """
    rnd = _lcg(seed)
    for _ in range(count):
        lx = (next(rnd) * 2.0 - 1.0) * 56.0
        ly = (next(rnd) * 2.0 - 1.0) * 23.0
        wx, wy = _local_to_world(cx, cy, rot, lx, ly)
        r = 7.4 + next(rnd) * 1.8

        def ring(u, v, d):
            if d > 0.80:  # dark outer skin
                return (30, 88, 28)
            if d > 0.48:  # green tube wall
                return mix((84, 166, 58), (112, 192, 80), 0.5 - 0.5 * v)
            return (216, 238, 182)  # pale hollow centre
        ellipse(wx, wy, r, r * 0.92, ring)


def draw_sesame(cx, cy, rot, seed, count=14):
    """Sparse pale sesame seeds over the tamago, avoiding the nori band."""
    rnd = _lcg(seed)
    placed = 0
    while placed < count:
        lx = (next(rnd) * 2.0 - 1.0) * 78.0
        ly = (next(rnd) * 2.0 - 1.0) * 29.0
        if abs(lx) < 29.0:  # keep off the dark nori band in the middle
            continue
        wx, wy = _local_to_world(cx, cy, rot, lx, ly)
        tall = next(rnd) < 0.30
        rx, ry = (2.3, 4.6) if tall else (4.6, 2.3)

        def seed_fn(u, v, d):
            base = mix((250, 240, 204), (228, 208, 158), d)
            return base
        ellipse(wx, wy, rx, ry, seed_fn)
        placed += 1


def draw_wasabi(cx, cy):
    soft_shadow(cx + 5, cy + 7, 40, 26)

    def fn(u, v, d):
        base = mix((74, 148, 52), (116, 186, 78), 1.0 - d)
        bump = (hash2(int(u * 40 + 100), int(v * 40 + 100)) - 0.5) * 18.0
        return (base[0] + bump, base[1] + bump, base[2] + bump)
    ellipse(cx, cy, 36, 27, fn)
    ellipse(cx - 10, cy - 12, 20, 14, fn)


def draw_ginger(cx, cy):
    """A compact mound of overlapping thin pickled-ginger petals."""
    soft_shadow(cx + 4, cy + 8, 54, 36)
    # Layered ellipses, back ring first, crown last: soft pink petals
    # with paler rims, packed tightly so the pile reads as one mound.
    petals = [(-27, -9, 25, 14), (25, -11, 24, 13), (0, -18, 26, 14),
              (-31, 8, 23, 13), (29, 7, 23, 13), (-9, -3, 25, 14),
              (13, -4, 22, 12), (-17, 13, 21, 12), (11, 13, 21, 12),
              (0, 3, 19, 11)]
    for i, (dx, dy, rx, ry) in enumerate(petals):
        tone = (i % 3) * 0.10

        def fn(u, v, d, tone=tone):
            base = mix((238, 152, 163), (250, 199, 207),
                       (0.5 - 0.5 * v) * 0.65 + tone)
            if d > 0.80:  # paler petal edge
                base = mix(base, (253, 226, 231), (d - 0.80) / 0.20 * 0.85)
            edge = 1.0 - 0.08 * d * d
            g = gloss(u, v, -0.25, -0.35, 0.75, 0.38)
            return (base[0] * edge + 255 * g,
                    base[1] * edge + 255 * g,
                    base[2] * edge + 250 * g)
        ellipse(cx + dx, cy + dy, rx, ry, fn)


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


def draw_lemon(cx, cy, r):
    """A lemon half: yellow rind around pale segmented flesh."""
    soft_shadow(cx + 4, cy + 6, r + 5, r * 0.92 + 4)

    def rind(u, v, d):
        return mix((192, 172, 56), (228, 206, 94), 0.5 - 0.5 * v)
    ellipse(cx, cy, r, r * 0.92, rind)

    def flesh(u, v, d):
        if d > 0.84:
            return None
        base = mix((238, 218, 124), (250, 236, 168), 1.0 - d)
        ang = math.atan2(v, u)
        if abs(math.sin(ang * 4.0)) < 0.16 and d > 0.12:
            base = mix(base, (252, 246, 205), 0.75)  # pith between segments
        if d < 0.10:
            base = mix(base, (252, 246, 205), 0.8)
        g = gloss(u, v, -0.3, -0.35, 0.7, 0.4)
        return (base[0] + 240 * g, base[1] + 240 * g, base[2] + 235 * g)
    ellipse(cx, cy, r, r * 0.92, flesh)


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
        g = gloss(u, v, -0.35, -0.45, 0.42, 0.9)
        if g <= 0.0:
            return None
        return (255, 250, 240, g)
    ellipse(cx, cy, 60, 46, shine, blend=True)


def draw_sparkles(buf, W, H):
    """Six tiny four-point star sparkles on the glossiest spots.

    A thin white diamond-cross (horizontal and vertical arms with a
    soft alpha falloff and a bright core), stamped at fixed positions:
    two on the salmon nigiri tops, two on the ikura gunkan mounds, one
    on the tuna, one on the soy dish. ``buf`` is the framebuffer the
    arms are blended into (kept explicit for clarity; the pixel
    helpers already bounds-check against W and H).
    """
    spots = [(190, 180, 9), (578, 183, 9),    # salmon nigiri tops
             (642, 326, 8), (259, 649, 8),    # ikura gunkan mounds
             (386, 166, 8),                   # tuna nigiri top
             (579, 649, 7)]                   # soy dish shine
    for cx, cy, r in spots:
        for t in range(-r, r + 1):
            a = 0.80 * (1.0 - abs(t) / (r + 1.0)) ** 1.5
            blend_px(cx + t, cy, 255, 255, 255, a)
            blend_px(cx, cy + t, 255, 255, 255, a)
        blend_px(cx, cy, 255, 255, 255, 0.95)
        blend_px(cx - 1, cy, 255, 255, 255, 0.55)
        blend_px(cx + 1, cy, 255, 255, 255, 0.55)
        blend_px(cx, cy - 1, 255, 255, 255, 0.55)
        blend_px(cx, cy + 1, 255, 255, 255, 0.55)


# ---------------------------------------------------------------- compose

def compose():
    draw_background()
    draw_platter()
    draw_warm_glow()

    draw_shiso(122, 292, -28)

    # Back row of nigiri, then front row with a gunkan.
    draw_nigiri(208, 198, -11, "salmon")
    draw_nigiri(402, 182, 5, "tuna")
    draw_nigiri(596, 200, 13, "salmon")
    draw_nigiri(238, 350, -5, "tuna")
    draw_nigiri(450, 352, 8, "tamago")
    draw_gunkan(656, 342, 60)

    # Row of maki rolls along the front of the platter.
    draw_maki(192, 542, 55)
    draw_maki(297, 552, 56)
    draw_maki(402, 556, 56)
    draw_maki(507, 552, 56)
    draw_maki(612, 542, 55)

    draw_wasabi(688, 466)
    draw_ginger(168, 448)
    draw_lemon(548, 450, 30)
    draw_gunkan(272, 664, 56)
    draw_soy_dish(598, 668)

    # Final touch: star sparkles on the glossiest spots.
    draw_sparkles(FB, W, H)


def main():
    compose()
    outdir = (os.environ.get("ENTRY_OUT")
              or os.environ.get("MAKEFUN_OUTPUT_DIR")
              or "/output")
    os.makedirs(outdir, exist_ok=True)
    write_png(os.path.join(outdir, "entry.png"))


if __name__ == "__main__":
    main()
