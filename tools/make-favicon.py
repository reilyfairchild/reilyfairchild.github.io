#!/usr/bin/env python3
"""Build the site favicon set from one of the orb designs.

    python3 tools/make-favicon.py abyss       # rebuild with a different orb
    python3 tools/make-favicon.py --list

Writes assets/images/favicon/: the chosen orb as favicon.svg, PNGs at
16/32/180, and favicon.ico. Every orb is also written out as its own
<name>.svg so the alternates stay available. Pure stdlib - no Pillow,
no ImageMagick, no browser.
"""
import math, os, struct, sys, zlib

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'assets', 'images', 'favicon')

# viewBox is 32x32; the disc is r=14 at (16,16), so its bbox is 28x28 at (2,2).
# Gradient cx/cy/r below are fractions of that bbox, matching SVG's
# objectBoundingBox units, so the PNGs and the SVG render identically.
R_DISC, CENTER, BBOX, BBOX_ORIGIN = 14.0, 16.0, 28.0, 2.0

ORBS = {
 'abyss':     dict(cx=.50, cy=.50, r=.58, stops=[(0,'#7FE6F0'),(.13,'#2C9BB8'),(.40,'#17517E'),(1,'#0C1A2C')],
                   desc='small intense cyan core in a very dark body'),
 'baseline':  dict(cx=.50, cy=.50, r=.62, stops=[(0,'#CFEAFB'),(.22,'#6DB4E2'),(.55,'#2A6FA4'),(1,'#16253C')],
                   desc='the original inner-light orb, pure site blue'),
 'deepwater': dict(cx=.50, cy=.42, r=.66, stops=[(0,'#A6E3EC'),(.24,'#43A0BC'),(.56,'#1F6398'),(1,'#101F33')],
                   desc='light from above the surface, darker falloff'),
 'seaglass':  dict(cx=.50, cy=.50, r=.62, stops=[(0,'#EAF5F2'),(.24,'#A8D0D2'),(.55,'#548AA2'),(1,'#243F5C')],
                   desc='desaturated, frosted, slightly green'),
}

def hex2rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def sample(orb, t):
    """colour at gradient position t (0 = centre, 1 = outer edge)"""
    stops = orb['stops']
    if t <= stops[0][0]: return hex2rgb(stops[0][1])
    if t >= stops[-1][0]: return hex2rgb(stops[-1][1])
    for (o0, c0), (o1, c1) in zip(stops, stops[1:]):
        if o0 <= t <= o1:
            f = 0 if o1 == o0 else (t - o0) / (o1 - o0)
            a, b = hex2rgb(c0), hex2rgb(c1)
            return tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(3))
    return hex2rgb(stops[-1][1])

def render(orb, size, bg=None, ss=4):
    """RGBA rows; bg=(r,g,b) makes it opaque (for the Apple touch icon)"""
    gx = BBOX_ORIGIN + orb['cx'] * BBOX
    gy = BBOX_ORIGIN + orb['cy'] * BBOX
    gr = orb['r'] * BBOX
    scale = size / 32.0
    rows, step = [], 1.0 / ss
    for py in range(size):
        row = bytearray()
        for px in range(size):
            acc_r = acc_g = acc_b = acc_a = 0.0
            for sy in range(ss):
                for sx in range(ss):
                    vx = (px + (sx + 0.5) * step) / scale
                    vy = (py + (sy + 0.5) * step) / scale
                    if math.hypot(vx - CENTER, vy - CENTER) <= R_DISC:
                        t = math.hypot(vx - gx, vy - gy) / gr
                        r, g, b = sample(orb, min(t, 1.0))
                        acc_r += r; acc_g += g; acc_b += b; acc_a += 1.0
            n = ss * ss
            cov = acc_a / n
            if cov > 0:
                r, g, b = acc_r / acc_a, acc_g / acc_a, acc_b / acc_a
            else:
                r = g = b = 0.0
            if bg:                       # composite onto an opaque background
                r = r * cov + bg[0] * (1 - cov)
                g = g * cov + bg[1] * (1 - cov)
                b = b * cov + bg[2] * (1 - cov)
                cov = 1.0
            row += bytes((round(r), round(g), round(b), round(cov * 255)))
        rows.append(bytes(row))
    return rows

def png(size, rows):
    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))
    raw = b''.join(b'\x00' + r for r in rows)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))

def ico(pngs):
    """ICO holding PNG payloads (every browser since IE11 reads these)"""
    head = struct.pack('<HHH', 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, blobs = b'', b''
    for size, data in pngs:
        entries += struct.pack('<BBBBHHII', size & 0xFF, size & 0xFF, 0, 0,
                               1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return head + entries + blobs

def svg(orb, name):
    stops = ''.join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in orb['stops'])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32" '
            f'role="img" aria-label="Orb">\n'
            f'  <defs>\n'
            f'    <radialGradient id="{name}" cx="{orb["cx"]*100:g}%" cy="{orb["cy"]*100:g}%" r="{orb["r"]*100:g}%">'
            f'{stops}</radialGradient>\n'
            f'  </defs>\n'
            f'  <circle cx="16" cy="16" r="14" fill="url(#{name})"/>\n'
            f'</svg>\n')

def main():
    if '--list' in sys.argv:
        for n, o in ORBS.items():
            print(f'  {n:10s} {o["desc"]}')
        return
    choice = next((a for a in sys.argv[1:] if not a.startswith('-')), 'abyss')
    if choice not in ORBS:
        sys.exit(f'unknown orb {choice!r}; try --list')
    os.makedirs(OUT, exist_ok=True)

    # keep every design on disk so swapping later needs no redesign
    for name, orb in ORBS.items():
        with open(os.path.join(OUT, f'{name}.svg'), 'w') as f:
            f.write(svg(orb, name))

    orb = ORBS[choice]
    with open(os.path.join(OUT, 'favicon.svg'), 'w') as f:
        f.write(svg(orb, choice))

    sized = {}
    for size in (16, 32, 48, 180):
        bg = (255, 255, 255) if size == 180 else None   # iOS ignores transparency
        sized[size] = png(size, render(orb, size, bg=bg))
    for size in (16, 32):
        open(os.path.join(OUT, f'favicon-{size}.png'), 'wb').write(sized[size])
    open(os.path.join(OUT, 'apple-touch-icon.png'), 'wb').write(sized[180])
    open(os.path.join(OUT, 'favicon.ico'), 'wb').write(
        ico([(s, sized[s]) for s in (16, 32, 48)]))

    print(f'built favicon set from "{choice}" ({orb["desc"]}) in {OUT}')
    for f in sorted(os.listdir(OUT)):
        print(f'  {f:24s} {os.path.getsize(os.path.join(OUT, f)):>7,} bytes')

if __name__ == '__main__':
    main()
