"""Generate diagrams/packet-flow.svg (request path with NAT rewrites per hop)."""
from pathlib import Path

W, H = 1400, 760
FONT = "Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'DejaVu Sans Mono', Menlo, Consolas, monospace"

steps = [
    dict(n=1, title="Visitor sends", where="browser", color="#334155", bg="#f8fafc",
         src="192.0.2.50:51000", dst="203.0.113.10:443", changed=None,
         note="TCP SYN to the public IP\nfrom DuckDNS"),
    dict(n=2, title="Oracle edge", where="Security List + 1:1 NAT", color="#b91c1c", bg="#fef2f2",
         src="192.0.2.50:51000", dst="10.0.0.205:443", changed="dst",
         note="TCP 443 allowed in\narrives on ens3"),
    dict(n=3, title="DNAT", where="nat PREROUTING", color="#c2410c", bg="#fff7ed",
         src="192.0.2.50:51000", dst="10.8.0.2:443", changed="dst",
         note="FORWARD rule 2 lets\nit cross ens3 → wg0"),
    dict(n=4, title="MASQUERADE", where="nat POSTROUTING -o wg0", color="#0f766e", bg="#f0fdfa",
         src="10.8.0.1:40312", dst="10.8.0.2:443", changed="src",
         note="so the reply comes back\nthrough the tunnel"),
    dict(n=5, title="Home server", where="wg0 decrypts → Caddy", color="#4338ca", bg="#eef2ff",
         src="10.8.0.1:40312", dst="10.8.0.2:443", changed=None,
         note="Caddy terminates TLS\nand serves the site"),
]

out = []
a = out.append
a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">')
a('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#334155"/></marker>'
  '<marker id="b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#15803d"/></marker></defs>')
a(f'<rect width="{W}" height="{H}" rx="18" fill="#ffffff"/>')
a(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="18" fill="none" stroke="#e2e8f0"/>')
a('<text x="40" y="52" font-size="26" font-weight="700" fill="#0f172a">One HTTPS request, hop by hop</text>')
a('<text x="40" y="80" font-size="15" fill="#64748b">The packet headers the kernel rewrites on the Oracle VM. Highlighted fields changed at that hop.</text>')

cw, gap, x0, y0 = 240, 26, 40, 120
for i, s in enumerate(steps):
    x = x0 + i * (cw + gap)
    c = s["color"]
    a(f'<rect x="{x}" y="{y0}" width="{cw}" height="400" rx="14" fill="{s["bg"]}" stroke="{c}" stroke-opacity="0.5"/>')
    a(f'<circle cx="{x+28}" cy="{y0+32}" r="15" fill="{c}"/>')
    a(f'<text x="{x+28}" y="{y0+37}" font-size="14" font-weight="700" text-anchor="middle" fill="#fff">{s["n"]}</text>')
    a(f'<text x="{x+54}" y="{y0+30}" font-size="16" font-weight="700" fill="#0f172a">{s["title"]}</text>')
    a(f'<text x="{x+54}" y="{y0+50}" font-size="12" fill="#64748b">{s["where"]}</text>')
    # packet
    px, py = x + 16, y0 + 78
    a(f'<rect x="{px}" y="{py}" width="{cw-32}" height="150" rx="10" fill="#ffffff" stroke="#cbd5e1"/>')
    a(f'<text x="{px+14}" y="{py+24}" font-size="11" font-weight="700" fill="#94a3b8" letter-spacing="1">IP / TCP HEADER</text>')
    for j, (lab, key) in enumerate((("SRC", "src"), ("DST", "dst"))):
        ry = py + 40 + j * 52
        hl = s["changed"] == key
        if hl:
            a(f'<rect x="{px+8}" y="{ry}" width="{cw-48}" height="44" rx="8" fill="{c}" fill-opacity="0.12" stroke="{c}"/>')
        a(f'<text x="{px+16}" y="{ry+17}" font-size="11" font-weight="700" fill="{c if hl else "#64748b"}">{lab}{" · rewritten" if hl else ""}</text>')
        a(f'<text x="{px+16}" y="{ry+36}" font-size="14" fill="#0f172a" font-family="{MONO}">{s[key]}</text>')
    # note
    for k, line in enumerate(s["note"].split("\n")):
        a(f'<text x="{x+cw/2}" y="{y0+262+k*20}" font-size="13" text-anchor="middle" fill="#334155">{line}</text>')
    if i < len(steps) - 1:
        ax = x + cw + 2
        a(f'<path d="M{ax} {y0+150} L{ax+gap-4} {y0+150}" stroke="#334155" stroke-width="2.5" marker-end="url(#a)"/>')

# tunnel box under step 4-5
tx = x0 + 3 * (cw + gap)
a(f'<rect x="{tx+16}" y="{y0+318}" width="{cw*2+gap-32}" height="66" rx="10" fill="#ccfbf1" stroke="#0f766e" stroke-dasharray="6 4"/>')
a(f'<text x="{tx+cw+gap/2}" y="{y0+342}" font-size="13" font-weight="700" text-anchor="middle" fill="#134e4a">between 4 and 5 the packet is encrypted inside WireGuard</text>')
a(f'<text x="{tx+cw+gap/2}" y="{y0+364}" font-size="12.5" text-anchor="middle" fill="#134e4a" font-family="{MONO}">outer: UDP 10.0.0.205:51820 → 198.51.100.23:52265</text>')

# DNS note under step 1
a(f'<rect x="{x0+16}" y="{y0+318}" width="{cw-32}" height="66" rx="10" fill="#fffbeb" stroke="#f59e0b"/>')
a(f'<text x="{x0+cw/2}" y="{y0+342}" font-size="12.5" text-anchor="middle" fill="#92400e">your-subdomain.duckdns.org</text>')
a(f'<text x="{x0+cw/2}" y="{y0+362}" font-size="12.5" text-anchor="middle" fill="#92400e">resolves to 203.0.113.10</text>')

# reply path
ry = 560
a(f'<rect x="40" y="{ry}" width="{W-80}" height="160" rx="14" fill="#f0fdf4" stroke="#86efac"/>')
a(f'<text x="64" y="{ry+34}" font-size="16" font-weight="700" fill="#166534">The reply: conntrack undoes both rewrites</text>')
a(f'<path d="M{W-170} {ry+70} L186 {ry+70}" stroke="#15803d" stroke-width="2.5" marker-end="url(#b)"/>')
reply = [
    ("Caddy answers", "10.8.0.2:443 → 10.8.0.1:40312"),
    ("back through wg0", "encrypted, same tunnel"),
    ("un-MASQUERADE", "dst → 192.0.2.50:51000"),
    ("un-DNAT", "src → 10.0.0.205:443"),
    ("Oracle edge", "src → 203.0.113.10:443"),
]
for i, (t, d) in enumerate(reply):
    x = W - 170 - i * ((W - 340) / 4)
    a(f'<circle cx="{x}" cy="{ry+70}" r="7" fill="#15803d"/>')
    a(f'<text x="{x}" y="{ry+104}" font-size="13" font-weight="700" text-anchor="middle" fill="#166534">{t}</text>')
    a(f'<text x="{x}" y="{ry+126}" font-size="12" text-anchor="middle" fill="#166534" font-family="{MONO}">{d}</text>')
a(f'<text x="64" y="{ry+150}" font-size="12" fill="#4d7c0f">FORWARD rule 1 (RELATED,ESTABLISHED) lets these replies out. The visitor only ever sees 203.0.113.10.</text>')
a('</svg>')

Path(__file__).resolve().parent.parent.joinpath("diagrams/packet-flow.svg").write_text("\n".join(out))
print("wrote diagrams/packet-flow.svg")
