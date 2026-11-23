"""Render demo/explainer.mp4: an animated walkthrough of the project.

Each scene is drawn frame by frame with Pillow and piped straight into ffmpeg
(one encoded file per scene), then the scenes are joined with the concat
demuxer. Run:  python3 tools/make_explainer.py [--preview]
"""
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "out"
OUT.mkdir(parents=True, exist_ok=True)
W, H, FPS = 1280, 720, 30

FD = "/usr/share/fonts/opentype/inter/"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
_fc = {}


def F(size, w="Regular"):
    key = (size, w)
    if key not in _fc:
        path = MONO if w == "Mono" else f"{FD}Inter-{w}.otf"
        _fc[key] = ImageFont.truetype(path, size)
    return _fc[key]


BG = (248, 250, 252)
INK = (15, 23, 42)
MUTED = (100, 116, 139)
LINE = (203, 213, 225)
RED = (185, 28, 28)
REDBG = (254, 242, 242)
ORA = (199, 70, 52)
ORABG = (255, 247, 245)
TEAL = (15, 118, 110)
TEALBG = (204, 251, 241)
INDIGO = (67, 56, 202)
INDBG = (238, 242, 255)
GREEN = (21, 128, 61)
AMBER = (180, 83, 9)


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def ease(v):
    v = clamp(v)
    return v * v * (3 - 2 * v)


def seg(t, a, b):
    """0..1 progress of t through [a, b]."""
    return ease((t - a) / (b - a)) if b > a else float(t >= a)


def mix(c1, c2, k):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3))


def text(d, xy, s, size=20, w="Regular", fill=INK, anchor="la", alpha=1.0, bg=BG):
    d.text(xy, s, font=F(size, w), fill=mix(bg, fill, alpha), anchor=anchor)


def box(d, x, y, w, h, fill, outline, r=16, width=2, dash=False, alpha=1.0, bg=BG):
    f = mix(bg, fill, alpha)
    o = mix(bg, outline, alpha)
    if dash:
        d.rounded_rectangle([x, y, x + w, y + h], r, fill=f)
        dashed_rect(d, x, y, w, h, o, width)
    else:
        d.rounded_rectangle([x, y, x + w, y + h], r, fill=f, outline=o, width=width)


def dashed_rect(d, x, y, w, h, color, width, on=10, off=7):
    for (x1, y1, x2, y2) in ((x, y, x + w, y), (x + w, y, x + w, y + h), (x + w, y + h, x, y + h), (x, y + h, x, y)):
        dashed_line(d, (x1, y1), (x2, y2), color, width, on, off)


def dashed_line(d, p1, p2, color, width=3, on=12, off=8, progress=1.0, phase=0.0):
    x1, y1 = p1
    x2, y2 = p2
    L = math.hypot(x2 - x1, y2 - y1)
    if L == 0:
        return
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    end = L * progress
    pos = -(phase % (on + off))
    while pos < end:
        a = max(pos, 0)
        b = min(pos + on, end)
        if b > a:
            d.line([(x1 + ux * a, y1 + uy * a), (x1 + ux * b, y1 + uy * b)], fill=color, width=width)
        pos += on + off


def arrow(d, p1, p2, color, width=4, head=14, progress=1.0):
    x1, y1 = p1
    x2 = x1 + (p2[0] - x1) * progress
    y2 = y1 + (p2[1] - y1) * progress
    d.line([(x1, y1), (x2, y2)], fill=color, width=width)
    if progress > 0.05:
        ang = math.atan2(y2 - y1, x2 - x1)
        pts = [(x2, y2),
               (x2 - head * math.cos(ang - 0.45), y2 - head * math.sin(ang - 0.45)),
               (x2 - head * math.cos(ang + 0.45), y2 - head * math.sin(ang + 0.45))]
        d.polygon(pts, fill=color)


def dot(d, x, y, color, r=11):
    for k, rr in enumerate((r + 12, r + 7)):
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=mix(BG, color, 0.12 + 0.1 * k))
    d.ellipse([x - r, y - r, x + r, y + r], fill=color)


def path_point(pts, k):
    """Point at fraction k along a polyline."""
    lens = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
    total = sum(lens)
    dist = clamp(k) * total
    for i, L in enumerate(lens):
        if dist <= L or i == len(lens) - 1:
            f = dist / L if L else 0
            return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f)
        dist -= L
    return pts[-1]


def header(d, t, title, sub, start=0.0):
    a = seg(t, start, start + 0.5)
    text(d, (64, 58), title, 38, "Bold", INK, alpha=a)
    text(d, (64, 108), sub, 21, "Regular", MUTED, alpha=a)


def fade_in(img, t, dur=0.35):
    k = clamp(t / dur)
    if k >= 1:
        return img
    return Image.blend(Image.new("RGB", img.size, BG), img, k)


# ---------- shared node layout ----------
VIS = (70, 300, 190, 140)
ORC = (360, 250, 300, 240)
CGN = (735, 270, 190, 200)
HOM = (1000, 250, 230, 240)


def draw_visitor(d, a=1.0):
    x, y, w, h = VIS
    box(d, x, y, w, h, (255, 255, 255), LINE, alpha=a)
    box(d, x + 55, y + 22, 80, 54, (255, 255, 255), (51, 65, 85), r=6, width=3, alpha=a)
    d.rectangle([x + 55, y + 22, x + 135, y + 34], fill=mix(BG, (51, 65, 85), a))
    text(d, (x + w / 2, y + 100), "Visitor", 20, "Bold", INK, "mm", a)
    text(d, (x + w / 2, y + 124), "browser", 15, "Regular", MUTED, "mm", a)


def draw_oracle(d, a=1.0, iptables=False):
    x, y, w, h = ORC
    box(d, x, y, w, h, ORABG, ORA, alpha=a)
    text(d, (x + 20, y + 22), "Oracle Cloud VM", 21, "Bold", (154, 52, 18), alpha=a)
    text(d, (x + 20, y + 52), "public IP 203.0.113.10", 16, "Regular", (154, 52, 18), alpha=a)
    box(d, x + 20, y + 86, 125, 50, (241, 245, 249), (148, 163, 184), r=8, width=2, alpha=a)
    text(d, (x + 82, y + 103), "ens3", 15, "Bold", INK, "mm", a)
    text(d, (x + 82, y + 122), "10.0.0.205", 13, "Regular", MUTED, "mm", a)
    box(d, x + 155, y + 86, 125, 50, TEALBG, TEAL, r=8, width=2, alpha=a)
    text(d, (x + 217, y + 103), "wg0", 15, "Bold", (19, 78, 74), "mm", a)
    text(d, (x + 217, y + 122), "10.8.0.1", 13, "Regular", (19, 78, 74), "mm", a)
    if iptables:
        text(d, (x + 20, y + 158), "DNAT 80,443 → 10.8.0.2", 14, "Mono", (51, 65, 85), alpha=a)
        text(d, (x + 20, y + 182), "MASQUERADE -o wg0", 14, "Mono", (51, 65, 85), alpha=a)
        text(d, (x + 20, y + 206), "FORWARD accept 80,443", 14, "Mono", (51, 65, 85), alpha=a)


def draw_cgnat(d, a=1.0, note=True):
    x, y, w, h = CGN
    box(d, x, y, w, h, (255, 255, 255), (100, 116, 139), dash=True, alpha=a)
    text(d, (x + w / 2, y + 30), "ISP CGNAT", 20, "Bold", (51, 65, 85), "mm", a)
    text(d, (x + w / 2, y + 56), "198.51.100.23", 15, "Regular", MUTED, "mm", a)
    if note:
        text(d, (x + w / 2, y + 100), "inbound: blocked", 15, "SemiBold", RED, "mm", a)
        text(d, (x + w / 2, y + 126), "outbound: allowed", 15, "SemiBold", GREEN, "mm", a)


def draw_home(d, a=1.0, caddy=True, wg=True):
    x, y, w, h = HOM
    box(d, x, y, w, h, INDBG, INDIGO, alpha=a)
    text(d, (x + 20, y + 22), "Home server", 21, "Bold", (49, 46, 129), alpha=a)
    text(d, (x + 20, y + 52), "Ubuntu · no public IP", 16, "Regular", INDIGO, alpha=a)
    if wg:
        box(d, x + 20, y + 86, w - 40, 50, TEALBG, TEAL, r=8, width=2, alpha=a)
        text(d, (x + w / 2, y + 103), "wg0", 15, "Bold", (19, 78, 74), "mm", a)
        text(d, (x + w / 2, y + 122), "10.8.0.2", 13, "Regular", (19, 78, 74), "mm", a)
    else:
        text(d, (x + w / 2, y + 120), "192.168.x.x", 15, "Regular", INDIGO, "mm", a)
    if caddy:
        box(d, x + 20, y + 150, w - 40, 66, (255, 255, 255), (99, 102, 241), r=8, width=2, alpha=a)
        text(d, (x + w / 2, y + 172), "Caddy :443", 16, "Bold", (49, 46, 129), "mm", a)
        text(d, (x + w / 2, y + 196), "Let's Encrypt HTTPS", 13, "Regular", INDIGO, "mm", a)


TUNNEL = [(ORC[0] + 280, ORC[1] + 111), (CGN[0], CGN[1] + 160), (CGN[0] + CGN[2], CGN[1] + 160), (HOM[0] + 20, HOM[1] + 111)]


def draw_tunnel(d, progress=1.0, phase=0.0, a=1.0):
    pts = TUNNEL
    lens = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
    total = sum(lens)
    remaining = progress * total
    for i in range(len(pts) - 1):
        if remaining <= 0:
            break
        p = min(1.0, remaining / lens[i])
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        d.line([(x1, y1), (x1 + (x2 - x1) * p, y1 + (y2 - y1) * p)], fill=mix(BG, (153, 246, 228), a), width=16)
        dashed_line(d, pts[i], pts[i + 1], mix(BG, TEAL, a), 4, progress=p, phase=phase)
        remaining -= lens[i]


# ---------- scenes ----------
def s_title(t, d, img):
    a = seg(t, 0.1, 0.8)
    text(d, (W / 2, 250), "A public IP for a home server", 56, "Bold", INK, "mm", a)
    text(d, (W / 2, 315), "behind CGNAT, for free", 56, "Bold", TEAL, "mm", a)
    b = seg(t, 0.8, 1.5)
    text(d, (W / 2, 400), "Oracle Cloud Always Free  ·  WireGuard  ·  iptables NAT  ·  Caddy HTTPS", 22, "Regular", MUTED, "mm", b)
    c = seg(t, 1.6, 2.2)
    d.line([(W / 2 - 160, 450), (W / 2 + 160, 450)], fill=mix(BG, LINE, c), width=2)
    text(d, (W / 2, 485), "built and debugged by hand, step by step", 18, "Regular", MUTED, "mm", c)


def s_problem(t, d, img):
    header(d, t, "The problem: CGNAT", "My ISP shares one public IPv4 between many homes. Nothing can connect in.")
    draw_visitor(d, seg(t, 0.2, 0.7))
    draw_cgnat(d, seg(t, 0.4, 0.9), note=False)
    draw_home(d, seg(t, 0.6, 1.1), caddy=False, wg=False)
    x0 = VIS[0] + VIS[2]
    y = VIS[1] + 70
    arrow(d, (x0 + 10, y), (CGN[0] - 10, y), RED, 4, progress=seg(t, 1.3, 2.3))
    k = seg(t, 2.3, 3.6)
    if 0 < k < 1:
        px = CGN[0] + 20 + k * (CGN[2] - 40)
        dot(d, px, y, RED)
    if t > 3.6:
        cx, cy = CGN[0] + CGN[2] + 37, y
        s = seg(t, 3.6, 4.0)
        r = 20 * s
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)
        if s > 0.5:
            d.line([(cx - 8, cy - 8), (cx + 8, cy + 8)], fill="white", width=4)
            d.line([(cx + 8, cy - 8), (cx - 8, cy + 8)], fill="white", width=4)
        text(d, (cx, cy + 42), "dropped", 16, "Bold", RED, "mm", s)
        text(d, (CGN[0] + CGN[2] / 2, CGN[1] + 110), "\"which customer", 15, "Regular", RED, "mm", s)
        text(d, (CGN[0] + CGN[2] / 2, CGN[1] + 132), "is this for?\"", 15, "Regular", RED, "mm", s)
    c = seg(t, 5.0, 5.6)
    box(d, 64, 560, 1152, 84, REDBG, (252, 165, 165), alpha=c)
    text(d, (92, 590), "Port forwarding on my router can't help: the router sits behind the ISP's NAT.", 19, "SemiBold", (127, 29, 29), alpha=c)
    text(d, (92, 618), "A static IP from the ISP would cost about Rs. 18,400 a month.", 17, "Regular", (127, 29, 29), alpha=c)


def s_tunnel(t, d, img):
    header(d, t, "The fix: dial out, then come back in", "A free Oracle VM has a real public IP. The home server connects OUT to it over WireGuard.")
    draw_visitor(d, 0.35)
    draw_oracle(d, seg(t, 0.2, 0.8))
    draw_cgnat(d, 1.0)
    draw_home(d, 1.0, caddy=False)
    k = seg(t, 1.2, 3.4)
    if k > 0:
        rev = list(reversed(TUNNEL))
        draw_tunnel(d, 1.0 if k >= 1 else 0.0)
        if k < 1:
            # draw growing line from home toward the hub
            pts = rev
            lens = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
            rem = k * sum(lens)
            for i in range(len(pts) - 1):
                if rem <= 0:
                    break
                p = min(1.0, rem / lens[i])
                x1, y1 = pts[i]
                x2, y2 = pts[i + 1]
                d.line([(x1, y1), (x1 + (x2 - x1) * p, y1 + (y2 - y1) * p)], fill=(153, 246, 228), width=16)
                dashed_line(d, pts[i], pts[i + 1], TEAL, 4, progress=p)
                rem -= lens[i]
            hx, hy = path_point(rev, k)
            dot(d, hx, hy, TEAL, 9)
    if t > 3.4:
        draw_tunnel(d, 1.0, phase=(t - 3.4) * 40)
        a = seg(t, 3.4, 3.9)
        box(d, CGN[0] - 40, CGN[1] + 186, CGN[2] + 80, 64, (240, 253, 250), TEAL, r=12, alpha=a)
        text(d, (CGN[0] + CGN[2] / 2, CGN[1] + 207), "WireGuard tunnel · UDP 51820", 15, "Bold", (19, 78, 74), "mm", a)
        text(d, (CGN[0] + CGN[2] / 2, CGN[1] + 230), "keepalive every 25 s holds it open", 14, "Regular", (19, 78, 74), "mm", a)
        # keepalive pulses
        for n in range(3):
            pk = ((t - 3.6) * 0.5 + n / 3) % 1.0
            if t > 3.6:
                px, py = path_point(list(reversed(TUNNEL)), pk)
                d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=TEAL)
    c = seg(t, 5.2, 5.8)
    box(d, 64, 590, 1152, 64, (240, 253, 250), (153, 246, 228), alpha=c)
    text(d, (92, 622), "Outbound connections are allowed through CGNAT, and replies come back on the same mapping.", 18, "SemiBold", (17, 94, 89), "lm", c)


STAGES = [
    (0.00, "Visitor sends", "192.0.2.50:51000", "203.0.113.10:443", None),
    (0.22, "Oracle edge: 1:1 NAT", "192.0.2.50:51000", "10.0.0.205:443", "dst"),
    (0.34, "DNAT (VM)", "192.0.2.50:51000", "10.8.0.2:443", "dst"),
    (0.44, "MASQUERADE (VM)", "10.8.0.1:40312", "10.8.0.2:443", "src"),
    (0.52, "Inside the tunnel", "10.8.0.1:40312", "10.8.0.2:443", None),
    (0.97, "Caddy receives it", "10.8.0.1:40312", "10.8.0.2:443", None),
]


def s_flow(t, d, img):
    header(d, t, "One HTTPS request, hop by hop", "The VM rewrites the packet headers, then the tunnel carries it home.")
    draw_visitor(d)
    draw_oracle(d, iptables=True)
    draw_cgnat(d, note=False)
    draw_home(d)
    draw_tunnel(d, 1.0, phase=t * 30, a=0.8)
    vy = VIS[1] + 70
    path = [(VIS[0] + VIS[2], vy), (ORC[0], vy), (ORC[0] + 82, ORC[1] + 136), (ORC[0] + 217, ORC[1] + 136)] + TUNNEL[0:] + [(HOM[0] + HOM[2] / 2, HOM[1] + 183)]
    k = seg(t, 0.8, 9.5)
    k = clamp((t - 0.8) / 8.7)
    stage = STAGES[0]
    for st in STAGES:
        if k >= st[0]:
            stage = st
    if t < 9.8:
        px, py = path_point(path, k)
        dot(d, px, py, (234, 88, 12) if k < 0.52 else TEAL)
    # reply
    if t > 10.0:
        rk = clamp((t - 10.0) / 3.0)
        px, py = path_point(list(reversed(path)), rk)
        if rk < 1:
            dot(d, px, py, GREEN)
        stage = ("Reply: conntrack undoes NAT", "203.0.113.10:443", "192.0.2.50:51000", "both") if rk > 0.6 else ("Reply travels back", "10.8.0.2:443", "10.8.0.1:40312", None)
        stage = (1.0,) + stage
    # header card
    cx, cy = 64, 540
    box(d, cx, cy, 1152, 120, (255, 255, 255), LINE, r=14)
    text(d, (cx + 24, cy + 22), stage[1], 21, "Bold", INK)
    text(d, (cx + 24, cy + 52), "IP / TCP HEADER", 13, "SemiBold", (148, 163, 184))
    for j, (lab, key) in enumerate((("SRC", "src"), ("DST", "dst"))):
        bx = cx + 432 + j * 370
        hl = stage[4] == key or stage[4] == "both"
        col = (234, 88, 12) if hl else MUTED
        if hl:
            d.rounded_rectangle([bx - 12, cy + 18, bx + 340, cy + 102], 10, fill=(255, 247, 237), outline=(251, 146, 60), width=2)
        text(d, (bx, cy + 30), lab + ("  · rewritten" if hl else ""), 14, "Bold", col)
        text(d, (bx, cy + 58), stage[2] if key == "src" else stage[3], 26, "Mono", INK)


def s_debug(t, d, img):
    header(d, t, "Two bugs, found one layer at a time", "tcpdump, wg and iptables counters showed exactly which layer was broken.")
    a = seg(t, 0.5, 1.1)
    x, y, w = 64, 160, 560
    box(d, x, y, w, 380, REDBG, (252, 165, 165), alpha=a)
    text(d, (x + 24, y + 26), "Issue 6 · no WireGuard handshake", 21, "Bold", (127, 29, 29), alpha=a)
    lines = [
        ("$ sudo wg", INK, "Mono"),
        ("  transfer: 0 B received, 1.16 KiB sent", RED, "Mono"),
        ("$ sudo tcpdump -ni ens3 udp port 51820", INK, "Mono"),
        ("  (silent: nothing reaches the VM)", RED, "Mono"),
    ]
    for i, (s, c, f) in enumerate(lines):
        la = seg(t, 1.2 + i * 0.5, 1.6 + i * 0.5)
        text(d, (x + 24, y + 76 + i * 34), s, 16, f, c, alpha=la)
    fa = seg(t, 3.6, 4.2)
    box(d, x + 20, y + 230, w - 40, 126, (240, 253, 244), (134, 239, 172), r=10, alpha=fa)
    text(d, (x + 40, y + 254), "Cause: Oracle Security List had no UDP 51820", 17, "Bold", (22, 101, 52), alpha=fa)
    text(d, (x + 40, y + 284), "Fix: ingress rule UDP, dest port 51820", 16, "Regular", (22, 101, 52), alpha=fa)
    text(d, (x + 40, y + 316), "→ handshake: 148 B / 92 B / 32 B", 16, "Mono", (22, 101, 52), alpha=fa)

    x2 = 656
    b = seg(t, 5.0, 5.6)
    box(d, x2, y, w, 380, (255, 247, 237), (253, 186, 116), alpha=b)
    text(d, (x2 + 24, y + 26), "Issue 7 · public port times out", 21, "Bold", (124, 45, 18), alpha=b)
    lines2 = [
        ("$ curl http://10.8.0.2       # works", INK),
        ("$ sudo iptables -t nat -L -n", INK),
        ("  (empty: no DNAT, no MASQUERADE)", RED),
        ("  FORWARD: only Oracle's REJECT", RED),
    ]
    for i, (s, c) in enumerate(lines2):
        la = seg(t, 5.7 + i * 0.5, 6.1 + i * 0.5)
        text(d, (x2 + 24, y + 76 + i * 34), s, 16, "Mono", c, alpha=la)
    fb = seg(t, 8.1, 8.7)
    box(d, x2 + 20, y + 230, w - 40, 126, (240, 253, 244), (134, 239, 172), r=10, alpha=fb)
    text(d, (x2 + 40, y + 254), "Cause: PostUp rules were never loaded", 17, "Bold", (22, 101, 52), alpha=fb)
    text(d, (x2 + 40, y + 284), "Fix: systemctl restart wg-quick@wg0", 16, "Mono", (22, 101, 52), alpha=fb)
    text(d, (x2 + 40, y + 316), "→ DNAT + MASQUERADE present, page loads", 16, "Regular", (22, 101, 52), alpha=fb)
    c = seg(t, 9.4, 10.0)
    text(d, (W / 2, 600), "Lesson: a config file on disk isn't the running config. Check what the kernel has.", 19, "SemiBold", INK, "mm", c)


def s_result(t, d, img):
    a = seg(t, 0.2, 0.8)
    bx, by, bw, bh = 190, 110, 900, 360
    box(d, bx, by, bw, bh, (255, 255, 255), LINE, r=14, alpha=a)
    d.rounded_rectangle([bx, by, bx + bw, by + 56], 14, fill=mix(BG, (241, 245, 249), a))
    for i, c in enumerate(((248, 113, 113), (251, 191, 36), (74, 222, 128))):
        d.ellipse([bx + 22 + i * 24, by + 21, bx + 36 + i * 24, by + 35], fill=mix(BG, c, a))
    d.rounded_rectangle([bx + 110, by + 12, bx + bw - 30, by + 44], 16, fill=mix(BG, (255, 255, 255), a))
    # padlock
    lx, ly = bx + 130, by + 28
    d.rounded_rectangle([lx - 7, ly - 2, lx + 7, ly + 9], 2, fill=mix(BG, GREEN, a))
    d.arc([lx - 5, ly - 11, lx + 5, ly + 1], 180, 360, fill=mix(BG, GREEN, a), width=2)
    text(d, (bx + 148, by + 28), "https://your-subdomain.duckdns.org", 17, "Regular", INK, "lm", a)
    typed = "Hello over HTTPS from my home box via WireGuard + Oracle!"
    k = seg(t, 1.0, 2.6)
    text(d, (bx + 40, by + 110), typed[: int(len(typed) * k)], 20, "Mono", INK)
    c = seg(t, 2.8, 3.4)
    text(d, (W / 2, 540), "Valid certificate. No public IP at home. Survives reboots.", 26, "Bold", TEAL, "mm", c)
    e = seg(t, 3.8, 4.4)
    text(d, (W / 2, 596), "Total cost: $0  ·  Oracle Always Free + DuckDNS + Let's Encrypt", 19, "Regular", MUTED, "mm", e)
    text(d, (W / 2, 640), "docs/ · configs/ · scripts/ · diagrams/ in this repo", 17, "Regular", MUTED, "mm", e)


SCENES = [
    ("01_title", s_title, 3.5),
    ("02_problem", s_problem, 7.5),
    ("03_tunnel", s_tunnel, 7.5),
    ("04_flow", s_flow, 14.0),
    ("05_debug", s_debug, 11.5),
    ("06_result", s_result, 6.5),
]


def frame(fn, t):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fn(t, d, img)
    return fade_in(img, t)


def render_scene(name, fn, dur):
    tmp = OUT / f"{name}.tmp.mp4"
    final = OUT / f"{name}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-r", str(FPS), str(tmp)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(dur * FPS))
    for i in range(n):
        p.stdin.write(frame(fn, i / FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise SystemExit(f"ffmpeg failed on {name}")
    tmp.rename(final)
    return final


def main():
    if "--preview" in sys.argv:
        moments = {"02_problem": 6.0, "03_tunnel": 6.5, "04_flow": 5.0, "05_debug": 11.0, "06_result": 5.5, "01_title": 3.0}
        for name, fn, dur in SCENES:
            frame(fn, moments[name]).save(OUT / f"preview_{name}.png")
        extra = [("04_flow", 2.6), ("04_flow", 12.5), ("03_tunnel", 2.4)]
        for name, tt in extra:
            fn = dict((n, f) for n, f, _ in SCENES)[name]
            frame(fn, tt).save(OUT / f"preview_{name}_{tt}.png")
        print("previews written")
        return
    files = [render_scene(n, f, d) for n, f, d in SCENES]
    lst = OUT / "concat.txt"
    lst.write_text("".join(f"file '{f.name}'\n" for f in files))
    dest = ROOT / "demo" / "explainer.mp4"
    tmp = OUT / "explainer.tmp.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(dest)
    print("wrote", dest)


if __name__ == "__main__":
    main()
