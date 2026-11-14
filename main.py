#!/usr/bin/env python3
"""Food Picture 01 - Steaming Tonkotsu Ramen.

An original procedural painting, written from scratch in pure Python
(standard library only).  A speckled blue-grey bowl of tonkotsu ramen on
a dark wooden table in a warm izakaya mood: creamy broth with glossy oil
droplets, a mound of wavy noodles, a lifted noodle pull held by wooden
chopsticks, fanned chashu slices, a halved ajitama egg with a jammy
amber yolk, a nori sheet, scallions, sesame and gentle rising steam.

The renderer paints into a float framebuffer with soft discs, gradient
ellipses, scanline polygons and stamped wavy strokes, then encodes the
result with a hand-written PNG writer (zlib + struct).  Everything is
driven by one fixed seed, so two runs produce a byte-identical image.

Output: entry.png in $ENTRY_OUT, else $MAKEFUN_OUTPUT_DIR, else /output.
"""

import math
import os
import random
import struct
import time
import zlib
from array import array

W = 800
H = 800
SEED = 20261114


# --------------------------------------------------------------------------
# PNG encoder (RGBA not needed; we write 8-bit RGB, filter 0 per scanline)
# --------------------------------------------------------------------------

def write_png(path, width, height, pix):
    """pix: array('f') of width*height*3 floats in 0..255."""
    raw = bytearray()
    row = bytearray(width * 3)
    for y in range(height):
        base = y * width * 3
        for x in range(width):
            i = base + x * 3
            o = x * 3
            r = pix[i]
            g = pix[i + 1]
            b = pix[i + 2]
            row[o] = 0 if r < 0 else (255 if r > 255 else int(r))
            row[o + 1] = 0 if g < 0 else (255 if g > 255 else int(g))
            row[o + 2] = 0 if b < 0 else (255 if b > 255 else int(b))
        raw.append(0)
        raw += row

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


# --------------------------------------------------------------------------
# Canvas: float framebuffer + painterly primitives
# --------------------------------------------------------------------------

class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.pix = array("f", [0.0]) * (w * h * 3)

    def blend(self, x, y, col, a):
        if 0 <= x < self.w and 0 <= y < self.h and a > 0.0:
            i = (y * self.w + x) * 3
            p = self.pix
            ia = 1.0 - a
            p[i] = p[i] * ia + col[0] * a
            p[i + 1] = p[i + 1] * ia + col[1] * a
            p[i + 2] = p[i + 2] * ia + col[2] * a

    def fill_vertical_gradient(self, top, bottom):
        """Full-canvas vertical gradient."""
        p = self.pix
        w, h = self.w, self.h
        for y in range(h):
            t = y / (h - 1)
            r = top[0] + (bottom[0] - top[0]) * t
            g = top[1] + (bottom[1] - top[1]) * t
            b = top[2] + (bottom[2] - top[2]) * t
            base = y * w * 3
            for x in range(w):
                i = base + x * 3
                p[i] = r
                p[i + 1] = g
                p[i + 2] = b

    def soft_disc(self, cx, cy, r, col, a):
        """Radial-falloff disc (quadratic falloff), alpha-blended."""
        p = self.pix
        w, h = self.w, self.h
        x0 = max(0, int(cx - r))
        x1 = min(w - 1, int(cx + r))
        y0 = max(0, int(cy - r))
        y1 = min(h - 1, int(cy + r))
        r2 = r * r
        cr, cg, cb = col
        for y in range(y0, y1 + 1):
            dy = y - cy
            base = y * w * 3
            for x in range(x0, x1 + 1):
                dx = x - cx
                d2 = dx * dx + dy * dy
                if d2 < r2:
                    t = 1.0 - math.sqrt(d2) / r
                    al = a * t * t
                    if al > 0.003:
                        i = base + x * 3
                        ia = 1.0 - al
                        p[i] = p[i] * ia + cr * al
                        p[i + 1] = p[i + 1] * ia + cg * al
                        p[i + 2] = p[i + 2] * ia + cb * al

    def ellipse(self, cx, cy, rx, ry, col, a=1.0, soft=0.0,
                grad=None, grad_c=None, rot=0.0):
        """Filled ellipse, optionally rotated, with an optional radial
        gradient from grad_c (centre colour) to col (edge colour).
        soft>0 feather the edge over that many pixels."""
        p = self.pix
        w, h = self.w, self.h
        ext = max(rx, ry) + soft + 2
        x0 = max(0, int(cx - ext))
        x1 = min(w - 1, int(cx + ext))
        y0 = max(0, int(cy - ext))
        y1 = min(h - 1, int(cy + ext))
        ca = math.cos(rot)
        sa = math.sin(rot)
        cr, cg, cb = col
        if grad_c is None:
            grad_c = col
        gr, gg, gb = grad_c
        for y in range(y0, y1 + 1):
            dy = y - cy
            base = y * w * 3
            for x in range(x0, x1 + 1):
                dx = x - cx
                u = (dx * ca + dy * sa) / rx
                v = (-dx * sa + dy * ca) / ry
                q = u * u + v * v
                if q <= 1.0:
                    i = base + x * 3
                    if grad is None:
                        al = a
                        p[i] = p[i] * (1 - al) + cr * al
                        p[i + 1] = p[i + 1] * (1 - al) + cg * al
                        p[i + 2] = p[i + 2] * (1 - al) + cb * al
                    else:
                        t = math.sqrt(q)
                        rr = gr + (cr - gr) * t
                        gg2 = gg + (cg - gg) * t
                        bb = gb + (cb - gb) * t
                        p[i] = p[i] * (1 - a) + rr * a
                        p[i + 1] = p[i + 1] * (1 - a) + gg2 * a
                        p[i + 2] = p[i + 2] * (1 - a) + bb * a
                elif soft > 0.0:
                    d = math.sqrt(q)
                    over = (d - 1.0) * min(rx, ry)
                    if over < soft:
                        al = a * (1.0 - over / soft)
                        i = base + x * 3
                        ia = 1.0 - al
                        p[i] = p[i] * ia + cr * al
                        p[i + 1] = p[i + 1] * ia + cg * al
                        p[i + 2] = p[i + 2] * ia + cb * al

    def polygon(self, pts, col, a=1.0):
        """Scanline-filled polygon, alpha-blended."""
        p = self.pix
        w, h = self.w, self.h
        ys = [pt[1] for pt in pts]
        y0 = max(0, int(min(ys)))
        y1 = min(h - 1, int(max(ys)) + 1)
        n = len(pts)
        cr, cg, cb = col
        ia = 1.0 - a
        for y in range(y0, y1 + 1):
            yc = y + 0.5
            xs = []
            for k in range(n):
                xa, ya = pts[k]
                xb, yb = pts[(k + 1) % n]
                if (ya <= yc < yb) or (yb <= yc < ya):
                    xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
            if len(xs) < 2:
                continue
            xs.sort()
            base = y * w * 3
            for k in range(0, len(xs) - 1, 2):
                xa = max(0, int(xs[k]))
                xb = min(w - 1, int(xs[k + 1]))
                for x in range(xa, xb + 1):
                    i = base + x * 3
                    p[i] = p[i] * ia + cr * a
                    p[i + 1] = p[i + 1] * ia + cg * a
                    p[i + 2] = p[i + 2] * ia + cb * a

    def stamp(self, cx, cy, r, col, a):
        """Hard-ish small disc used to build up strokes."""
        p = self.pix
        w, h = self.w, self.h
        x0 = max(0, int(cx - r))
        x1 = min(w - 1, int(cx + r))
        y0 = max(0, int(cy - r))
        y1 = min(h - 1, int(cy + r))
        r2 = r * r
        cr, cg, cb = col
        ia = 1.0 - a
        for y in range(y0, y1 + 1):
            dy = y - cy
            base = y * w * 3
            for x in range(x0, x1 + 1):
                dx = x - cx
                if dx * dx + dy * dy <= r2:
                    i = base + x * 3
                    p[i] = p[i] * ia + cr * a
                    p[i + 1] = p[i + 1] * ia + cg * a
                    p[i + 2] = p[i + 2] * ia + cb * a

    def stroke(self, pts, width, col, a=1.0, soft=False):
        """Polyline stroke built from stamps interpolated along segments."""
        r = width / 2.0
        for k in range(len(pts) - 1):
            x0, y0 = pts[k]
            x1, y1 = pts[k + 1]
            dist = math.hypot(x1 - x0, y1 - y0)
            steps = max(1, int(dist / max(1.0, r * 0.6)))
            for s in range(steps + 1):
                t = s / steps
                x = x0 + (x1 - x0) * t
                y = y0 + (y1 - y0) * t
                if soft:
                    self.soft_disc(x, y, r, col, a)
                else:
                    self.stamp(x, y, r, col, a)

    def ring(self, cx, cy, r, width, col, a=1.0, arc=None):
        """Circle outline (optionally an angular arc in radians)."""
        steps = max(24, int(2 * math.pi * r / 3))
        pts = []
        a0, a1 = (0.0, 2 * math.pi) if arc is None else arc
        for s in range(steps + 1):
            t = a0 + (a1 - a0) * s / steps
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
        self.stroke(pts, width, col, a)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def lerp_col(c0, c1, t):
    return (c0[0] + (c1[0] - c0[0]) * t,
            c0[1] + (c1[1] - c0[1]) * t,
            c0[2] + (c1[2] - c0[2]) * t)


def wavy_points(x0, y0, x1, y1, amp, waves, phase, n=40):
    """Points along a line with a sinusoidal sideways wobble."""
    pts = []
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    for i in range(n + 1):
        t = i / n
        off = amp * math.sin(t * waves * 2 * math.pi + phase) * math.sin(t * math.pi)
        pts.append((x0 + dx * t + nx * off, y0 + dy * t + ny * off))
    return pts


# --------------------------------------------------------------------------
# Scene
# --------------------------------------------------------------------------

BCX, BCY = 400, 448          # bowl centre
BRX, BRY = 292, 268          # bowl outer radii (slightly angled view)
IRX, IRY = 252, 212          # broth surface radii
ICY = 420                    # broth surface centre height


def paint_background(cv, rng):
    # Deep warm brown-black backdrop.
    cv.fill_vertical_gradient((38, 26, 20), (16, 11, 9))

    # Soft out-of-focus bokeh lights in the upper corners.
    bokeh = [(70, 60, 46, (255, 190, 110)),
             (150, 34, 26, (255, 170, 95)),
             (716, 52, 52, (255, 196, 120)),
             (640, 26, 24, (255, 176, 100)),
             (758, 130, 30, (250, 160, 90)),
             (36, 150, 26, (240, 160, 95)),
             (420, 22, 20, (255, 205, 140))]
    for (x, y, r, col) in bokeh:
        cv.soft_disc(x, y, r, col, 0.16)
        cv.soft_disc(x, y, r * 0.55, col, 0.20)

    # Dark wooden table: lower band with subtle horizontal grain.
    for y in range(648, H):
        t = (y - 648) / (H - 648)
        col = lerp_col((52, 36, 24), (30, 20, 13), t)
        for x in range(W):
            i = (y * W + x) * 3
            cv.pix[i] = col[0]
            cv.pix[i + 1] = col[1]
            cv.pix[i + 2] = col[2]
    for _ in range(46):
        gy = rng.uniform(656, 792)
        gx = rng.uniform(0, 700)
        gl = rng.uniform(60, 260)
        dark = rng.random() < 0.6
        col = (24, 16, 10) if dark else (74, 52, 33)
        cv.stroke([(gx, gy), (gx + gl, gy + rng.uniform(-2, 2))],
                  rng.uniform(1.0, 2.4), col, 0.18)


def paint_bowl(cv, rng):
    # Soft drop shadow under the bowl.
    cv.ellipse(BCX + 6, BCY + 30, BRX + 26, BRY + 16, (0, 0, 0), 0.42, soft=46)
    cv.soft_disc(BCX, BCY + 96, 250, (0, 0, 0), 0.30)

    # Bowl foot.
    cv.ellipse(BCX, 736, 96, 26, (52, 62, 74), 1.0, grad=1,
               grad_c=(86, 98, 112))
    # Bowl body: speckled blue-grey glaze, lighter toward the top.
    cv.ellipse(BCX, BCY, BRX, BRY, (74, 88, 104), 1.0, grad=1,
               grad_c=(120, 136, 152))
    # Curved shading: darker sweep along the lower body.
    cv.ellipse(BCX, BCY + 96, BRX - 44, BRY - 66, (44, 54, 68), 0.55, soft=60)
    # Gentle sheen on the upper-left body.
    cv.soft_disc(BCX - 150, BCY - 120, 130, (190, 205, 220), 0.13)

    # Rim: thick ring band between body and broth.
    cv.ellipse(BCX, ICY, IRX + 26, IRY + 24, (96, 110, 126), 1.0, grad=1,
               grad_c=(140, 154, 168))
    cv.ellipse(BCX, ICY, IRX + 8, IRY + 7, (82, 95, 110), 1.0, grad=1,
               grad_c=(118, 132, 146))
    # Rim highlight arc, upper left.
    cv.ring(BCX, ICY, 0, 1, (0, 0, 0), 0.0)  # no-op keeps API warm
    pts = []
    for s in range(61):
        t = math.pi * (1.05 + 0.75 * s / 60)
        pts.append((BCX + (IRX + 17) * math.cos(t), ICY + (IRY + 15) * math.sin(t)))
    cv.stroke(pts, 7, (196, 210, 224), 0.35)

    # Glaze speckles on rim and body.
    for _ in range(900):
        ang = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.86, 1.0)
        x = BCX + BRX * rr * math.cos(ang)
        y = BCY + BRY * rr * math.sin(ang)
        if rng.random() < 0.5:
            cv.stamp(x, y, rng.uniform(0.7, 1.6), (38, 46, 58), 0.5)
        else:
            cv.stamp(x, y, rng.uniform(0.6, 1.3), (168, 182, 196), 0.4)


def paint_broth(cv, rng):
    # Creamy tonkotsu surface.
    cv.ellipse(BCX, ICY, IRX, IRY, (196, 156, 102), 1.0, grad=1,
               grad_c=(226, 190, 132))
    # Warm depth patches.
    cv.soft_disc(BCX - 90, ICY + 40, 150, (168, 124, 74), 0.25)
    cv.soft_disc(BCX + 120, ICY - 50, 130, (238, 205, 150), 0.25)

    # Chili-oil sheen spots (orange-red, translucent).
    for _ in range(9):
        ang = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.25, 0.85)
        x = BCX + IRX * rr * math.cos(ang)
        y = ICY + IRY * rr * math.sin(ang)
        cv.ellipse(x, y, rng.uniform(14, 30), rng.uniform(8, 16),
                   (206, 92, 40), 0.28, soft=6, rot=rng.uniform(0, 3))

    # Glossy oil droplets with bright specular ticks.
    for _ in range(46):
        ang = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.random()) * 0.92
        x = BCX + IRX * rr * math.cos(ang)
        y = ICY + IRY * rr * math.sin(ang)
        r = rng.uniform(3.5, 9.5)
        cv.ellipse(x, y, r, r * 0.72, (222, 168, 96), 0.55, soft=1.5)
        cv.ellipse(x - r * 0.3, y - r * 0.3, r * 0.34, r * 0.22,
                   (255, 240, 205), 0.85, soft=1.0)


def paint_nori(cv, rng):
    # Dark-green nori sheet standing at the back-left of the bowl.
    pts = [(172, 218), (322, 240), (306, 386), (168, 372)]
    cv.polygon(pts, (26, 44, 30), 1.0)
    inner = [(186, 236), (308, 256), (296, 368), (182, 356)]
    cv.polygon(inner, (34, 56, 36), 0.85)
    # Rough seaweed texture speckles.
    for _ in range(260):
        t = rng.random()
        s = rng.random()
        x = (172 + (322 - 172) * t) * (1 - s) + (168 + (306 - 168) * t) * s
        y = (218 + (240 - 218) * t) * (1 - s) + (372 + (386 - 372) * t) * s
        col = (52, 78, 44) if rng.random() < 0.5 else (16, 30, 20)
        cv.stamp(x, y, rng.uniform(0.8, 2.0), col, 0.5)
    # Top edge highlight.
    cv.stroke([(172, 218), (322, 240)], 3.5, (86, 118, 70), 0.5)


def paint_noodle_mound(cv, rng):
    # Generous mound of wavy strands resting in the broth.
    base = (238, 168, 96)
    dark = (196, 128, 62)
    lite = (252, 216, 140)
    # Soft noodle mass underneath, so the mound reads as a dense heap
    # rather than individual scribbles on bare broth.
    for _ in range(26):
        ang = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.random()) * 0.62
        x = BCX + IRX * rr * math.cos(ang)
        y = ICY + IRY * rr * math.sin(ang)
        cv.soft_disc(x, y, rng.uniform(34, 58), (228, 156, 88), 0.30)
    for i in range(170):
        ang = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.random()) * 0.68
        cx = BCX + IRX * rr * math.cos(ang)
        cy = ICY + IRY * rr * math.sin(ang)
        a2 = rng.uniform(0, 2 * math.pi)
        ln = rng.uniform(48, 100)
        x1 = cx + ln * math.cos(a2)
        y1 = cy + ln * math.sin(a2) * 0.8
        pts = wavy_points(cx, cy, x1, y1, rng.uniform(3, 7),
                          rng.uniform(1.6, 3.0), rng.uniform(0, 6.28), 26)
        cv.stroke(pts, rng.uniform(7.2, 8.8), dark, 0.85)
        pts2 = [(x, y - 2.0) for (x, y) in pts]
        cv.stroke(pts2, rng.uniform(5.4, 6.8), base, 0.95)
        if i % 3 == 0:
            pts3 = [(x, y - 3.4) for (x, y) in pts]
            cv.stroke(pts3, 1.8, lite, 0.8)


def paint_chashu(cv, rng):
    # 3-4 slices fanned across the front of the bowl.
    slices = [(268, 566, 96, 62, -0.5),
              (368, 592, 102, 66, -0.16),
              (474, 590, 102, 66, 0.14),
              (566, 556, 92, 58, 0.48)]
    for (cx, cy, rx, ry, rot) in slices:
        # Soft contact shadow.
        cv.ellipse(cx + 4, cy + 8, rx, ry, (90, 58, 30), 0.35, soft=8, rot=rot)
        # Seared brown rim.
        cv.ellipse(cx, cy, rx, ry, (122, 74, 46), 1.0, rot=rot, grad=1,
                   grad_c=(146, 94, 58))
        # Pink-tan meat face.
        cv.ellipse(cx, cy, rx - 11, ry - 10, (206, 156, 128), 1.0, rot=rot,
                   grad=1, grad_c=(224, 178, 148))
        # Creamy fat marbling: soft blotches + one gentle fat streak.
        for k in range(3):
            ox = rng.uniform(-rx * 0.38, rx * 0.38)
            oy = rng.uniform(-ry * 0.32, ry * 0.32)
            cv.ellipse(cx + ox, cy + oy, rng.uniform(12, 20),
                       rng.uniform(6, 10), (244, 218, 182), 0.32,
                       soft=5, rot=rot + k)
        sw = []
        for s in range(21):
            t = s / 20
            ang = t * 2.6 + 0.8
            rad = 8 + 20 * t
            lx = rad * math.cos(ang) * 0.9
            ly = rad * math.sin(ang) * 0.5
            ca, sa = math.cos(rot), math.sin(rot)
            sw.append((cx + lx * ca - ly * sa, cy + lx * sa + ly * ca))
        cv.stroke(sw, 2.6, (246, 222, 188), 0.45)
        # Seared edge ticks + gloss.
        cv.ellipse(cx - rx * 0.3, cy - ry * 0.42, rx * 0.4, ry * 0.2,
                   (255, 226, 190), 0.30, soft=6, rot=rot)


def paint_egg_and_garnish(cv, rng):
    # Ajitama half on the right: smooth white + jammy amber yolk.
    ex, ey = 614, 486
    cv.ellipse(ex + 3, ey + 6, 66, 56, (120, 84, 44), 0.35, soft=6, rot=-0.3)
    cv.ellipse(ex, ey, 66, 56, (246, 238, 224), 1.0, rot=-0.3, grad=1,
               grad_c=(255, 250, 240))
    cv.ellipse(ex - 2, ey + 1, 40, 34, (238, 138, 44), 1.0, rot=-0.3, grad=1,
               grad_c=(250, 172, 66))
    cv.ellipse(ex - 4, ey - 2, 26, 21, (244, 120, 30), 0.85, rot=-0.3, grad=1,
               grad_c=(252, 158, 52))
    # Jammy drip + bright specular.
    cv.ellipse(ex - 16, ey + 16, 9, 6, (250, 150, 48), 0.8, soft=2)
    cv.ellipse(ex - 12, ey - 10, 8, 5.5, (255, 244, 214), 0.95, soft=1.5)
    cv.stamp(ex + 8, ey + 4, 2.4, (255, 250, 230), 0.9)

    # Scallion pile, centre-left.
    for _ in range(64):
        ang = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.random())
        x = 292 + 52 * rr * math.cos(ang)
        y = 428 + 30 * rr * math.sin(ang)
        r = rng.uniform(3.2, 5.6)
        cv.ring(x, y, r, 2.2, (74, 158, 66), 0.95)
        cv.stamp(x, y, r * 0.45, (168, 220, 130), 0.9)
    # Sesame sprinkle near the scallions and over the broth.
    for _ in range(70):
        ang = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.random()) * 0.5
        x = 330 + IRX * rr * math.cos(ang) * 0.8
        y = 420 + IRY * rr * math.sin(ang) * 0.8
        cv.ellipse(x, y, rng.uniform(2.2, 3.4), rng.uniform(1.1, 1.7),
                   (240, 224, 188), 0.9, rot=rng.uniform(0, 3))


def paint_lifted_noodles(cv, rng):
    # The noodle pull: strands rising from the bowl centre to the
    # chopstick grip at the upper right.
    gx, gy = 556, 176          # grip point under the sticks
    base = (240, 170, 98)
    dark = (198, 130, 64)
    lite = (254, 220, 146)
    strands = 26
    for i in range(strands):
        t = i / (strands - 1)
        sx = 330 + 130 * t + rng.uniform(-8, 8)
        sy = 402 + 26 * math.sin(t * math.pi) + rng.uniform(-6, 6)
        top_x = gx - 26 + 52 * t
        top_y = gy + rng.uniform(-4, 10)
        mid_x = (sx + top_x) / 2 + 34 + rng.uniform(-10, 10)
        mid_y = (sy + top_y) / 2
        pts = []
        for s in range(31):
            u = s / 30
            # quadratic bezier from bowl to grip
            x = (1 - u) ** 2 * sx + 2 * (1 - u) * u * mid_x + u * u * top_x
            y = (1 - u) ** 2 * sy + 2 * (1 - u) * u * mid_y + u * u * top_y
            x += 3.2 * math.sin(u * 9 + i * 1.7)
            pts.append((x, y))
        cv.stroke(pts, 5.4, dark, 0.9)
        cv.stroke([(x - 1.2, y) for (x, y) in pts], 3.8, base, 0.95)
        if i % 3 == 0:
            cv.stroke([(x - 2.0, y) for (x, y) in pts], 1.5, lite, 0.85)
    # A couple of strands droop back down beside the bundle.
    for i in range(4):
        sx = gx - 14 + i * 12
        pts = wavy_points(sx, gy + 8, sx - 30 - i * 9, gy + 128,
                          5, 2.2, i * 1.9, 26)
        cv.stroke(pts, 4.6, dark, 0.9)
        cv.stroke([(x - 1.0, y) for (x, y) in pts], 3.2, base, 0.95)


def paint_chopsticks(cv, rng):
    # Two tapered wooden sticks entering from the top-right corner,
    # tips meeting at the noodle grip.
    def stick(tip, tail, w_tip, w_tail, col, hi):
        dx, dy = tail[0] - tip[0], tail[1] - tip[1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        pts = [(tip[0] + nx * w_tip, tip[1] + ny * w_tip),
               (tail[0] + nx * w_tail, tail[1] + ny * w_tail),
               (tail[0] - nx * w_tail, tail[1] - ny * w_tail),
               (tip[0] - nx * w_tip, tip[1] - ny * w_tip)]
        cv.polygon(pts, col, 1.0)
        # Wood highlight line along the upper edge.
        cv.stroke([(tip[0] + nx * w_tip * 0.4, tip[1] + ny * w_tip * 0.4),
                   (tail[0] + nx * w_tail * 0.4, tail[1] + ny * w_tail * 0.4)],
                  2.2, hi, 0.55)
        # Subtle grain streaks.
        for k in range(3):
            off = (k - 1) * w_tail * 0.34
            cv.stroke([(tip[0] + nx * off * 0.4, tip[1] + ny * off * 0.4),
                       (tail[0] + nx * off, tail[1] + ny * off)],
                      1.1, (120, 78, 42), 0.35)

    stick((548, 168), (806, 44), 3.4, 8.5, (178, 124, 72), (232, 186, 128))
    stick((568, 190), (812, 108), 3.4, 8.5, (158, 108, 60), (214, 168, 112))
    # Grip shadow where fingers of noodle meet wood.
    cv.soft_disc(556, 178, 17, (120, 74, 34), 0.35)


def paint_steam(cv, rng):
    # Gentle translucent wisps rising from broth and lifted noodles.
    # Drawn strongly enough to read clearly against the dark backdrop.
    wisps = [(300, 370, 218, 1.1), (392, 344, 168, 1.5), (486, 356, 214, 0.8),
             (556, 168, 84, 1.9), (612, 312, 176, 1.3), (238, 392, 240, 2.2),
             (448, 380, 250, 2.7), (342, 330, 150, 0.4)]
    for (bx, by, top, ph) in wisps:
        pts = []
        steps = 30
        for s in range(steps + 1):
            t = s / steps
            y = by - (by - top) * t
            x = bx + 22 * math.sin(t * 4.2 + ph) * t + 9 * t
            pts.append((x, y))
        for (x, y) in pts[::2]:
            cv.soft_disc(x, y, 30, (245, 248, 250), 0.105)
        for (x, y) in pts[::3]:
            cv.soft_disc(x, y, 15, (250, 252, 253), 0.13)


def paint_lighting(cv, rng):
    # Warm radial glow from above + gentle vignette, one combined pass.
    p = cv.pix
    gx, gy = 400, 120
    for y in range(H):
        for x in range(W):
            i = (y * W + x) * 3
            d_glow = math.hypot(x - gx, y - gy) / 620.0
            glow = max(0.0, 1.0 - d_glow) ** 2 * 26.0
            d_vig = math.hypot(x - 400, y - 400) / 560.0
            vig = 1.0 - 0.26 * max(0.0, d_vig - 0.35) ** 2
            p[i] = p[i] * vig + glow
            p[i + 1] = p[i + 1] * vig + glow * 0.88
            p[i + 2] = p[i + 2] * vig + glow * 0.70


def render():
    rng = random.Random(SEED)
    cv = Canvas(W, H)
    paint_background(cv, rng)
    paint_bowl(cv, rng)
    paint_broth(cv, rng)
    paint_noodle_mound(cv, rng)
    paint_nori(cv, rng)
    paint_chashu(cv, rng)
    paint_egg_and_garnish(cv, rng)
    paint_lifted_noodles(cv, rng)
    paint_chopsticks(cv, rng)
    paint_steam(cv, rng)
    paint_lighting(cv, rng)
    return cv


def main():
    t0 = time.time()
    out_dir = os.environ.get("ENTRY_OUT") or os.environ.get(
        "MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    cv = render()
    path = os.path.join(out_dir, "entry.png")
    write_png(path, W, H, cv.pix)
    print("wrote %s (%d bytes) in %.1fs" % (
        path, os.path.getsize(path), time.time() - t0))


if __name__ == "__main__":
    main()
