#!/usr/bin/env bash
# Health check for the Oracle VM hub. Walks the same layers used while
# debugging: tunnel -> routing -> NAT -> filter -> backend.
#
# Usage:  sudo ./verify-hub.sh
set -uo pipefail

HOME_IP="${HOME_IP:-10.8.0.2}"
WG_PORT="${WG_PORT:-51820}"
pass=0; fail=0

ok()   { printf '  \033[32mPASS\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  \033[31mFAIL\033[0m %s\n       hint: %s\n' "$1" "$2"; fail=$((fail+1)); }

if [[ $EUID -ne 0 ]]; then echo "Run as root (sudo)." >&2; exit 1; fi

echo "1. WireGuard interface"
if wg show wg0 >/dev/null 2>&1; then ok "wg0 is up"; else bad "wg0 is down" "systemctl status wg-quick@wg0"; fi

echo "2. Handshake with the home server"
hs=$(wg show wg0 latest-handshakes 2>/dev/null | awk '{print $2; exit}')
if [[ -n "${hs:-}" && "$hs" != "0" ]]; then
  age=$(( $(date +%s) - hs ))
  if (( age < 180 )); then ok "last handshake ${age}s ago"
  else bad "last handshake ${age}s ago (stale)" "is the home side up? PersistentKeepalive set?"; fi
else
  bad "no handshake yet" "Security List UDP $WG_PORT? run: tcpdump -ni any udp port $WG_PORT"
fi

echo "3. Firewall: UDP $WG_PORT allowed in INPUT"
if iptables -C INPUT -p udp --dport "$WG_PORT" -j ACCEPT 2>/dev/null; then ok "INPUT rule present"
else bad "INPUT rule missing" "iptables -I INPUT -p udp --dport $WG_PORT -j ACCEPT && netfilter-persistent save"; fi

echo "4. IPv4 forwarding"
if [[ "$(cat /proc/sys/net/ipv4/ip_forward)" == "1" ]]; then ok "ip_forward = 1"
else bad "ip_forward = 0" "sysctl --system (check /etc/sysctl.d/99-wireguard-forwarding.conf)"; fi

echo "5. NAT rules (from PostUp)"
if iptables -t nat -S PREROUTING | grep -q -- "--to-destination $HOME_IP"; then ok "DNAT -> $HOME_IP present"
else bad "DNAT rule missing" "PostUp not loaded: grep -c PostUp /etc/wireguard/wg0.conf, then restart wg-quick@wg0"; fi
if iptables -t nat -S POSTROUTING | grep -q -- "-o wg0 -j MASQUERADE"; then ok "MASQUERADE on wg0 present"
else bad "MASQUERADE missing" "restart wg-quick@wg0"; fi

echo "6. FORWARD chain order (ACCEPT must be above REJECT)"
first_reject=$(iptables -L FORWARD --line-numbers -n | awk '$2=="REJECT"{print $1; exit}')
last_accept=$(iptables -L FORWARD --line-numbers -n | awk '$2=="ACCEPT"{n=$1} END{print n}')
if [[ -n "${last_accept:-}" && ( -z "${first_reject:-}" || "$last_accept" -lt "$first_reject" ) ]]; then
  ok "ACCEPT rules sit above REJECT"
else
  bad "forwarded traffic will be rejected" "rules must be inserted with -I FORWARD 1"
fi

echo "7. Backend reachable through the tunnel"
if ping -c 2 -W 2 "$HOME_IP" >/dev/null 2>&1; then ok "ping $HOME_IP"; else bad "ping $HOME_IP failed" "check the home side: sudo wg"; fi
code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://$HOME_IP" || true)
if [[ "$code" != "000" ]]; then ok "HTTP on $HOME_IP answered ($code)"
else bad "nothing answering on $HOME_IP:80" "is Caddy running on the home server? ufw?"; fi

echo
echo "Result: $pass passed, $fail failed"
exit $(( fail > 0 ))
