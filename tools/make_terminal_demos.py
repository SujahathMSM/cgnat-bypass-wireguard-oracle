"""Render terminal replays of the two real debugging sessions.

The command output is what the machines actually printed during the build,
with public IPs, keys and hostnames replaced by placeholders. Lines starting
with '#' are narration added for the demo. Output: demo/*.mp4 and demo/*.gif

Run:  python3 tools/make_terminal_demos.py [--preview]
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "out"
OUT.mkdir(parents=True, exist_ok=True)
W, H, FPS = 1280, 720, 30
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 17)
FONTB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 17)
UI = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 16)
LH = 25
TOP = 62
MAXLINES = (H - TOP - 24) // LH

BG = (13, 17, 23)
FG = (201, 209, 217)
DIM = (110, 118, 129)
GREEN = (63, 185, 80)
BLUE = (88, 166, 255)
YELLOW = (210, 153, 34)
RED = (248, 81, 73)
CYAN = (57, 197, 207)
NOTE = (163, 113, 247)

HOME = "suja@home-ubuntu:~$ "
HUB = "ubuntu@oracle-hub:~$ "


# Script items: ("cmd", prompt, text) | ("out", text, color) | ("note", text) | ("pause", seconds)
TUNNEL = [
    ("note", "# Phase 1: tunnel configured on both sides. Test from home:"),
    ("cmd", HOME, "ping -c 4 10.8.0.1"),
    ("out", "PING 10.8.0.1 (10.8.0.1) 56(84) bytes of data.", FG),
    ("pause", 1.2),
    ("out", "", FG),
    ("out", "--- 10.8.0.1 ping statistics ---", FG),
    ("out", "4 packets transmitted, 0 received, 100% packet loss, time 3089ms", RED),
    ("cmd", HOME, "sudo wg"),
    ("out", "interface: wg0", FG),
    ("out", "  listening port: 52265", FG),
    ("out", "peer: <hub public key>", YELLOW),
    ("out", "  endpoint: <oracle-public-ip>:51820", FG),
    ("out", "  allowed ips: 10.8.0.0/24", FG),
    ("out", "  transfer: 0 B received, 1.16 KiB sent", RED),
    ("out", "  persistent keepalive: every 25 seconds", FG),
    ("note", "# Sending, never receiving. Does anything reach the VM?"),
    ("cmd", HUB, "sudo wg"),
    ("out", "interface: wg0", FG),
    ("out", "  listening port: 51820", FG),
    ("out", "peer: <home public key>", YELLOW),
    ("out", "  allowed ips: 10.8.0.2/32          <- no endpoint: never heard from home", RED),
    ("cmd", HUB, "sudo tcpdump -ni ens3 udp port 51820"),
    ("out", "listening on ens3, link-type EN10MB (Ethernet), snapshot length 262144 bytes", DIM),
    ("pause", 1.6),
    ("note", "# Silent. Blocked before the VM -> Oracle Security List had no UDP 51820."),
    ("note", "# Added ingress rule: UDP, source 0.0.0.0/0, destination port 51820."),
    ("cmd", HUB, "sudo tcpdump -ni ens3 udp port 51820"),
    ("out", "listening on ens3, link-type EN10MB (Ethernet), snapshot length 262144 bytes", DIM),
    ("out", "16:00:13.351306 IP <home-cgnat>.52265 > 10.0.0.205.51820: UDP, length 148", GREEN),
    ("out", "16:00:13.351698 IP 10.0.0.205.51820 > <home-cgnat>.52265: UDP, length 92", GREEN),
    ("out", "16:00:13.433129 IP <home-cgnat>.52265 > 10.0.0.205.51820: UDP, length 32", GREEN),
    ("out", "16:00:25.022313 IP <home-cgnat>.52265 > 10.0.0.205.51820: UDP, length 128", CYAN),
    ("out", "16:00:25.022615 IP 10.0.0.205.51820 > <home-cgnat>.52265: UDP, length 128", CYAN),
    ("out", "16:00:26.022141 IP <home-cgnat>.52265 > 10.0.0.205.51820: UDP, length 128", CYAN),
    ("out", "16:00:26.022319 IP 10.0.0.205.51820 > <home-cgnat>.52265: UDP, length 128", CYAN),
    ("note", "# 148/92/32 B = WireGuard handshake. 128 B pairs = encrypted pings. Tunnel up."),
    ("pause", 2.5),
]

FORWARD = [
    ("note", "# Phase 2: http://<oracle-public-ip> times out in the browser. Check layer by layer."),
    ("cmd", HUB, "curl -m 5 http://10.8.0.2"),
    ("out", "Hello from my home Ubuntu box via Oracle!", GREEN),
    ("note", "# Tunnel + backend OK. Routing?"),
    ("cmd", HUB, "cat /proc/sys/net/ipv4/ip_forward"),
    ("out", "1", GREEN),
    ("cmd", HUB, "sudo iptables -t nat -L -n -v"),
    ("out", "Chain PREROUTING (policy ACCEPT 0 packets, 0 bytes)", FG),
    ("out", " pkts bytes target     prot opt in     out     source     destination", DIM),
    ("out", "Chain POSTROUTING (policy ACCEPT 0 packets, 0 bytes)", FG),
    ("out", " pkts bytes target     prot opt in     out     source     destination", DIM),
    ("note", "# Empty! No DNAT, no MASQUERADE."),
    ("cmd", HUB, "sudo iptables -L FORWARD -n --line-numbers"),
    ("out", "Chain FORWARD (policy ACCEPT)", FG),
    ("out", "num  target   prot opt source      destination", DIM),
    ("out", "1    REJECT   0    --  0.0.0.0/0   0.0.0.0/0   reject-with icmp-host-prohibited", RED),
    ("cmd", HUB, "sudo tcpdump -ni any tcp port 80"),
    ("out", "ens3  In  IP <client>.51688 > 10.0.0.205.80: Flags [S], seq 2172874198 ...", YELLOW),
    ("out", "ens3  In  IP <client>.60842 > 10.0.0.205.80: Flags [S], seq 2378465697 ...", YELLOW),
    ("out", "ens3  In  IP <client>.51688 > 10.0.0.205.80: Flags [S], seq 2172874198 ...", YELLOW),
    ("note", "# SYNs arrive on ens3 but go nowhere: the PostUp rules never loaded."),
    ("note", "# Fix: make sure wg0.conf has the PostUp lines, then reload it."),
    ("cmd", HUB, "sudo systemctl restart wg-quick@wg0"),
    ("note", "# Browser: page loads. Later, after a full reboot test:"),
    ("cmd", HUB, "sudo iptables -t nat -L -n -v"),
    ("out", "Chain PREROUTING (policy ACCEPT 6 packets, 336 bytes)", FG),
    ("out", "    2    93 DNAT       6  --  ens3  *    0.0.0.0/0  0.0.0.0/0  dports 80,443 to:10.8.0.2", GREEN),
    ("out", "Chain POSTROUTING (policy ACCEPT 280 packets, 20807 bytes)", FG),
    ("out", "    3   177 MASQUERADE 0  --  *     wg0  0.0.0.0/0  0.0.0.0/0", GREEN),
    ("cmd", HUB, "sudo iptables -L FORWARD -n --line-numbers"),
    ("out", "1    ACCEPT   0    --  0.0.0.0/0   0.0.0.0/0   state RELATED,ESTABLISHED", GREEN),
    ("out", "2    ACCEPT   6    --  0.0.0.0/0   0.0.0.0/0   multiport dports 80,443", GREEN),
    ("out", "3    REJECT   0    --  0.0.0.0/0   0.0.0.0/0   reject-with icmp-host-prohibited", DIM),
    ("note", "# Rules survive reboot. Public 80/443 now reach the home server."),
    ("pause", 2.5),
]


def build_timeline(script):
    """Turn the script into a list of (time, lines_snapshot) keyframes."""
    t = 0.4
    lines = []  # list of list of (text, color) segments
    frames = []

    def snap(dur):
        nonlocal t
        frames.append((t, [list(l) for l in lines]))
        t += dur

    snap(0.4)
    for item in script:
        kind = item[0]
        if kind == "cmd":
            prompt, cmd = item[1], item[2]
            pcol = GREEN if prompt == HOME else BLUE
            lines.append([(prompt, pcol)])
            snap(0.35)
            for i in range(1, len(cmd) + 1):
                lines[-1] = [(prompt, pcol), (cmd[:i], FG)]
                snap(1 / 32)
            snap(0.35)
        elif kind == "out":
            lines.append([(item[1], item[2])])
            snap(0.06)
        elif kind == "note":
            lines.append([(item[1], NOTE)])
            snap(1.5)
        elif kind == "pause":
            snap(item[1])
    frames.append((t, [list(l) for l in lines]))
    return frames, t


def draw(lines, title, cursor_on):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 40], fill=(22, 27, 34))
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse([18 + i * 22, 14, 30 + i * 22, 26], fill=c)
    d.text((W / 2, 20), title, font=UI, fill=(139, 148, 158), anchor="mm")
    view = lines[-MAXLINES:]
    for row, segs in enumerate(view):
        x = 22
        y = TOP + row * LH
        for s, col in segs:
            f = FONTB if col in (GREEN, BLUE) and s.endswith("$ ") else FONT
            d.text((x, y), s, font=f, fill=col)
            x += d.textlength(s, font=f)
        if row == len(view) - 1 and cursor_on:
            d.rectangle([x + 1, y + 2, x + 10, y + 21], fill=FG)
    return img


def render(script, name, title):
    frames, total = build_timeline(script)
    n = int(total * FPS) + 1
    tmp = OUT / f"{name}.tmp.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    idx = 0
    cache = {}
    for i in range(n):
        t = i / FPS
        while idx + 1 < len(frames) and frames[idx + 1][0] <= t:
            idx += 1
        cur = int(t * 2) % 2 == 0
        key = (idx, cur)
        if key not in cache:
            cache.clear()
            cache[key] = draw(frames[idx][1], title, cur).tobytes()
        p.stdin.write(cache[key])
    p.stdin.close()
    if p.wait() != 0:
        raise SystemExit("ffmpeg failed")
    mp4 = ROOT / "demo" / f"{name}.mp4"
    tmp.replace(mp4)
    gif = ROOT / "demo" / f"{name}.gif"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf",
                    "fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];"
                    "[b][p]paletteuse=dither=none:diff_mode=rectangle", str(gif)], check=True)
    print("wrote", mp4.name, gif.name, f"{total:.1f}s")


def main():
    jobs = [(TUNNEL, "terminal-01-wireguard-handshake", "Debugging the WireGuard handshake (replay of the real session)"),
            (FORWARD, "terminal-02-port-forward", "Debugging the port forward (replay of the real session)")]
    if "--preview" in sys.argv:
        for script, name, title in jobs:
            frames, _ = build_timeline(script)
            draw(frames[-1][1], title, True).save(OUT / f"preview_{name}.png")
        print("previews written")
        return
    for script, name, title in jobs:
        render(script, name, title)


if __name__ == "__main__":
    main()
