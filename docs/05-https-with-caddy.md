# 5. A domain and HTTPS with Caddy

## 5.1 Free domain with DuckDNS

1. Sign in at [duckdns.org](https://www.duckdns.org).
2. Create a subdomain (`your-subdomain.duckdns.org`).
3. Set its IP to the **Oracle VM's public IP** (not the home IP) and click *update ip*.

```bash
nslookup your-subdomain.duckdns.org   # should return the Oracle public IP
```

The DuckDNS page shows an account **token** that can change where every one of your subdomains points. I accidentally included it in a screenshot and regenerated it ("recreate token"). Treat it like a password.

## 5.2 Caddy on the home server

Caddy is a web server that gets and renews Let's Encrypt certificates on its own.

```bash
sudo apt update && sudo apt install -y caddy

sudo tee /etc/caddy/Caddyfile <<'EOF'
your-subdomain.duckdns.org {
    respond "Hello over HTTPS from my home box via WireGuard + Oracle!"
}
EOF
sudo systemctl reload caddy
sudo journalctl -u caddy -f     # watch for "certificate obtained successfully"
```

- A site block named after a real domain makes Caddy request a certificate automatically.
- `respond` returns a fixed string, which is enough to test the chain end to end.
- `<<'EOF'` with quotes writes the text exactly as typed, with no shell expansion.

## 5.3 Why certificate issuance works through the tunnel

Let's Encrypt checks domain ownership by connecting to the domain on port 80 (HTTP-01) or 443 (TLS-ALPN-01). That request takes the same route as any visitor:

```
Let's Encrypt -> DNS -> Oracle public IP -> DNAT -> WireGuard -> Caddy on the home box
```

Caddy answers the challenge, gets the certificate, and stores it locally. This only works because both 80 and 443 are forwarded.

## 5.4 Result

`https://your-subdomain.duckdns.org` loads with a valid certificate, served from a machine at home that has no public IP of its own.

## 5.5 Next: real apps

Replace the `respond` line with a reverse proxy to a local service:

```
your-subdomain.duckdns.org {
    reverse_proxy localhost:8080
}
```

Anything published this way is on the open internet, so it needs its own authentication. See [7. Security notes](07-security-notes.md).

Next: [6. Troubleshooting journal](06-troubleshooting-journal.md)
