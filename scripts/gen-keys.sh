#!/usr/bin/env bash
# Generate a WireGuard key pair in /etc/wireguard.
#
# Usage:  sudo ./gen-keys.sh <name>      e.g.  sudo ./gen-keys.sh server
# Result: /etc/wireguard/<name>.key  (private, root-only)
#         /etc/wireguard/<name>.pub  (public, safe to share)
set -euo pipefail

name="${1:?usage: sudo $0 <name>   (e.g. server or home)}"
dir=/etc/wireguard

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0 $name" >&2
  exit 1
fi

command -v wg >/dev/null || { echo "wireguard-tools not installed: apt install -y wireguard" >&2; exit 1; }

mkdir -p "$dir"
# New files readable by root only, so the private key never leaks to other users.
umask 077

if [[ -s "$dir/$name.key" ]]; then
  echo "Key $dir/$name.key already exists, not overwriting."
else
  # genkey -> private key; pubkey derives the public key from it (one-way).
  wg genkey | tee "$dir/$name.key" | wg pubkey > "$dir/$name.pub"
  echo "Created $dir/$name.key and $dir/$name.pub"
fi

echo
echo "Public key for '$name' (give this to the other peer):"
cat "$dir/$name.pub"
