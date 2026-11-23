#!/usr/bin/env bash
# Set up the Oracle Cloud VM as the WireGuard hub with public port forwarding.
#
# Usage:
#   sudo HOME_PUBKEY='<home server public key>' ./setup-hub.sh
#
# Optional environment variables:
#   WAN_IF       internet-facing interface (default: detected from the default route)
#   HUB_ADDR     hub tunnel address        (default: 10.8.0.1/24)
#   HOME_IP      home server tunnel IP     (default: 10.8.0.2)
#   WG_PORT      WireGuard UDP port        (default: 51820)
#   FWD_PORTS    TCP ports to forward      (default: 80,443)
#
# What it does:
#   1. installs WireGuard (+ iptables-persistent to keep the INPUT rule)
#   2. generates the hub key pair if missing
#   3. enables IPv4 forwarding permanently
#   4. opens UDP $WG_PORT in the VM's own firewall (above Oracle's REJECT rule)
#   5. writes /etc/wireguard/wg0.conf with DNAT/MASQUERADE/FORWARD rules
#   6. starts wg-quick@wg0 now and on every boot
#
# You still need to open UDP $WG_PORT and TCP $FWD_PORTS in the Oracle
# Security List (see configs/oracle-cloud/security-list-ingress.md).
set -euo pipefail

: "${HOME_PUBKEY:?set HOME_PUBKEY to the home server public key}"
WAN_IF="${WAN_IF:-$(ip route show default | awk '{print $5; exit}')}"
HUB_ADDR="${HUB_ADDR:-10.8.0.1/24}"
HOME_IP="${HOME_IP:-10.8.0.2}"
WG_PORT="${WG_PORT:-51820}"
FWD_PORTS="${FWD_PORTS:-80,443}"
CONF=/etc/wireguard/wg0.conf

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi
[[ -n "$WAN_IF" ]] || { echo "Could not detect WAN interface; set WAN_IF" >&2; exit 1; }

echo "==> WAN interface: $WAN_IF | forwarding TCP $FWD_PORTS -> $HOME_IP"

echo "==> 1/6 Installing packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq wireguard iptables-persistent >/dev/null

echo "==> 2/6 Hub key pair"
umask 077
if [[ ! -s /etc/wireguard/server.key ]]; then
  wg genkey | tee /etc/wireguard/server.key | wg pubkey > /etc/wireguard/server.pub
fi

echo "==> 3/6 Enabling IPv4 forwarding"
echo 'net.ipv4.ip_forward = 1' > /etc/sysctl.d/99-wireguard-forwarding.conf
sysctl --system >/dev/null

echo "==> 4/6 Opening UDP $WG_PORT in iptables INPUT"
if ! iptables -C INPUT -p udp --dport "$WG_PORT" -j ACCEPT 2>/dev/null; then
  # -I (insert at top) so it lands above Oracle's catch-all REJECT rule.
  iptables -I INPUT -p udp --dport "$WG_PORT" -j ACCEPT
fi
netfilter-persistent save >/dev/null

echo "==> 5/6 Writing $CONF"
if [[ -f "$CONF" ]]; then
  cp "$CONF" "$CONF.bak.$(date +%s)"
fi
cat > "$CONF" <<EOF
[Interface]
Address = $HUB_ADDR
ListenPort = $WG_PORT
PrivateKey = $(cat /etc/wireguard/server.key)

PostUp = iptables -t nat -A PREROUTING -i $WAN_IF -p tcp -m multiport --dports $FWD_PORTS -j DNAT --to-destination $HOME_IP
PostUp = iptables -t nat -A POSTROUTING -o wg0 -j MASQUERADE
PostUp = iptables -I FORWARD 1 -i $WAN_IF -o wg0 -p tcp -m multiport --dports $FWD_PORTS -j ACCEPT
PostUp = iptables -I FORWARD 1 -i wg0 -o $WAN_IF -m state --state RELATED,ESTABLISHED -j ACCEPT
PostDown = iptables -t nat -D PREROUTING -i $WAN_IF -p tcp -m multiport --dports $FWD_PORTS -j DNAT --to-destination $HOME_IP
PostDown = iptables -t nat -D POSTROUTING -o wg0 -j MASQUERADE
PostDown = iptables -D FORWARD -i $WAN_IF -o wg0 -p tcp -m multiport --dports $FWD_PORTS -j ACCEPT
PostDown = iptables -D FORWARD -i wg0 -o $WAN_IF -m state --state RELATED,ESTABLISHED -j ACCEPT

[Peer]
# home-server
PublicKey = $HOME_PUBKEY
AllowedIPs = $HOME_IP/32
EOF
chmod 600 "$CONF"

echo "==> 6/6 Starting wg-quick@wg0"
systemctl enable wg-quick@wg0 >/dev/null 2>&1
systemctl restart wg-quick@wg0

echo
echo "Hub is up. Give this public key to the home server:"
cat /etc/wireguard/server.pub
echo
echo "Remember the Oracle Security List: UDP $WG_PORT and TCP $FWD_PORTS from 0.0.0.0/0."
