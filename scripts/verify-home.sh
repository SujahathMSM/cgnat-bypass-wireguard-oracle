#!/usr/bin/env bash
# Health check for the home server (spoke).
#
# Usage:  sudo DOMAIN=your-subdomain.duckdns.org ./verify-home.sh
set -uo pipefail

HUB_IP="${HUB_IP:-10.8.0.1}"
DOMAIN="${DOMAIN:-}"
pass=0; fail=0

ok()  { printf '  \033[32mPASS\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  \033[31mFAIL\033[0m %s\n       hint: %s\n' "$1" "$2"; fail=$((fail+1)); }

if [[ $EUID -ne 0 ]]; then echo "Run as root (sudo)." >&2; exit 1; fi

echo "1. WireGuard interface"
if wg show wg0 >/dev/null 2>&1; then ok "wg0 is up"; else bad "wg0 is down" "systemctl status wg-quick@wg0"; fi

echo "2. Traffic counters"
read -r rx tx < <(wg show wg0 transfer 2>/dev/null | awk '{print $2, $3; exit}')
if [[ "${rx:-0}" -gt 0 ]]; then ok "received ${rx} B / sent ${tx} B"
elif [[ "${tx:-0}" -gt 0 ]]; then bad "sending but receiving nothing" "packets are blocked before the hub: Oracle Security List UDP 51820"
else bad "no traffic at all" "check Endpoint in /etc/wireguard/wg0.conf"; fi

echo "3. Hub reachable through the tunnel"
if ping -c 3 -W 2 "$HUB_IP" >/dev/null 2>&1; then ok "ping $HUB_IP"; else bad "ping $HUB_IP failed" "see step 2"; fi

echo "4. Caddy"
if systemctl is-active --quiet caddy; then ok "caddy is running"; else bad "caddy not running" "systemctl status caddy; journalctl -u caddy -n 50"; fi

if [[ -n "$DOMAIN" ]]; then
  echo "5. Public HTTPS for $DOMAIN"
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 "https://$DOMAIN" || true)
  if [[ "$code" =~ ^[23] ]]; then ok "https://$DOMAIN answered ($code) with a valid certificate"
  else bad "https://$DOMAIN returned '$code'" "DNS points at the hub? 80/443 in Security List? journalctl -u caddy"; fi
fi

echo
echo "Result: $pass passed, $fail failed"
exit $(( fail > 0 ))
