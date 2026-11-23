#!/usr/bin/env bash
# Set up the home Ubuntu server as a WireGuard spoke that dials out to the hub.
#
# Usage:
#   sudo HUB_PUBKEY='<hub public key>' HUB_ENDPOINT='<oracle-public-ip>:51820' ./setup-home.sh
#
# Optional environment variables:
#   HOME_ADDR   home tunnel address    (default: 10.8.0.2/24)
#   TUNNEL_NET  networks routed to hub (default: 10.8.0.0/24)
set -euo pipefail

: "${HUB_PUBKEY:?set HUB_PUBKEY to the hub (Oracle VM) public key}"
: "${HUB_ENDPOINT:?set HUB_ENDPOINT, e.g. 203.0.113.10:51820}"
HOME_ADDR="${HOME_ADDR:-10.8.0.2/24}"
TUNNEL_NET="${TUNNEL_NET:-10.8.0.0/24}"
CONF=/etc/wireguard/wg0.conf

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

echo "==> 1/4 Installing WireGuard"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq wireguard >/dev/null

echo "==> 2/4 Home key pair"
umask 077
if [[ ! -s /etc/wireguard/home.key ]]; then
  wg genkey | tee /etc/wireguard/home.key | wg pubkey > /etc/wireguard/home.pub
fi

echo "==> 3/4 Writing $CONF"
if [[ -f "$CONF" ]]; then
  cp "$CONF" "$CONF.bak.$(date +%s)"
fi
cat > "$CONF" <<EOF
[Interface]
Address = $HOME_ADDR
PrivateKey = $(cat /etc/wireguard/home.key)

[Peer]
# oracle-hub
PublicKey = $HUB_PUBKEY
Endpoint = $HUB_ENDPOINT
AllowedIPs = $TUNNEL_NET
PersistentKeepalive = 25
EOF
chmod 600 "$CONF"

echo "==> 4/4 Starting wg-quick@wg0"
systemctl enable wg-quick@wg0 >/dev/null 2>&1
systemctl restart wg-quick@wg0

echo
echo "Home side is up. Give this public key to the hub:"
cat /etc/wireguard/home.pub
echo
echo "Test with: ping -c 4 10.8.0.1 && sudo wg"
