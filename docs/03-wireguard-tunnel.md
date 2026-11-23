# 3. The WireGuard tunnel

I built the tunnel by hand with plain WireGuard instead of Tailscale, to learn what the managed tools do for you. The work was split into small phases so each one could be tested before the next.

| Machine | Role | Tunnel IP | Interface |
|---|---|---|---|
| Oracle VM | Hub, has the public IP, listens on UDP 51820 | `10.8.0.1` | `wg0` |
| Home Ubuntu server | Spoke behind CGNAT, dials out | `10.8.0.2` | `wg0` |

## 3.1 How WireGuard authenticates

Each machine has a key pair, much like SSH:

- The **private key** stays on the machine and proves its identity.
- The **public key** is derived from the private key (one way only) and is given to the other peer.

Each config contains *its own* private key and *the other side's* public key. No matching key means no handshake. There's no password to guess, and WireGuard doesn't even reply to packets from unknown keys, so a port scan can't see it.

## 3.2 Generate keys on both machines

```bash
sudo apt update && sudo apt install -y wireguard
sudo -i
cd /etc/wireguard
umask 077                                                # new files: root-only
wg genkey | tee server.key | wg pubkey > server.pub     # on the home box: home.key / home.pub
cat server.pub
exit
```

| Command | What it does |
|---|---|
| `apt install wireguard` | Installs the user-space tools (`wg`, `wg-quick`). The WireGuard engine is already in the Linux kernel. |
| `sudo -i` | Root shell, because `/etc/wireguard` belongs to root |
| `umask 077` | Any file created in this shell is readable only by root, which protects the private key |
| `wg genkey` | Prints a random private key |
| `tee server.key` | Saves it to a file *and* passes it along the pipe |
| `wg pubkey` | Derives the public key from the private key |

Only the `.pub` files ever leave the machine. [`scripts/gen-keys.sh`](../scripts/gen-keys.sh) does the same thing.

## 3.3 Hub config (phase 1, tunnel only)

```bash
sudo -i
umask 077
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = 10.8.0.1/24
ListenPort = 51820
PrivateKey = $(cat /etc/wireguard/server.key)

[Peer]
# home-ubuntu
PublicKey = <HOME_PUBLIC_KEY>
AllowedIPs = 10.8.0.2/32
EOF
exit
```

- `cat > file <<EOF ... EOF` is a heredoc: everything between the markers becomes the file.
- `$(cat /etc/wireguard/server.key)` inserts the private key without it ever being copied or pasted.
- `AllowedIPs = 10.8.0.2/32` means this peer may use exactly one IP. It's a routing rule and a security filter in one line.

Open the port in the VM's firewall (above Oracle's REJECT rule) and save it:

```bash
sudo iptables -I INPUT -p udp --dport 51820 -j ACCEPT
sudo netfilter-persistent save
```

Then add the matching **UDP 51820** ingress rule in the Oracle Security List. Forgetting this was the first real bug (see below).

## 3.4 Home config

```ini
[Interface]
Address = 10.8.0.2/24
PrivateKey = <from /etc/wireguard/home.key>

[Peer]
# oracle-hub
PublicKey = <HUB_PUBLIC_KEY>
Endpoint = <ORACLE_PUBLIC_IP>:51820
AllowedIPs = 10.8.0.0/24
PersistentKeepalive = 25
```

| Line | Why |
|---|---|
| no `ListenPort` | The home box only dials out; CGNAT would block anything dialing in |
| `Endpoint` | Where to dial: the hub's public IP and port |
| `AllowedIPs = 10.8.0.0/24` | Route the whole tunnel network through the hub, so more peers (laptop, phone) can be added later |
| `PersistentKeepalive = 25` | A small packet every 25 s keeps the CGNAT mapping alive. Without it the tunnel goes quiet after an idle minute or two |

## 3.5 Start and test

```bash
sudo systemctl enable --now wg-quick@wg0   # both machines; enable = start on every boot
ping -c 4 10.8.0.1                         # from home
sudo wg                                    # look for "latest handshake"
```

## 3.6 The first failure

The first ping lost 100% of packets. `sudo wg` on the home side showed `0 B received, 1.16 KiB sent`, and the hub showed **no `endpoint:` line** for the peer, meaning it had never received one valid packet.

`tcpdump` on the hub showed nothing arriving at all, which ruled out the VM and pointed at the cloud firewall. The Oracle Security List had no UDP 51820 rule. After adding it:

```
16:00:13 IP <home-cgnat-ip>.52265 > 10.0.0.205.51820: UDP, length 148   <- handshake initiation
16:00:13 IP 10.0.0.205.51820 > <home-cgnat-ip>.52265: UDP, length 92    <- handshake response
16:00:13 IP <home-cgnat-ip>.52265 > 10.0.0.205.51820: UDP, length 32    <- confirmation
16:00:25 IP <home-cgnat-ip>.52265 > 10.0.0.205.51820: UDP, length 128   <- encrypted ping
16:00:25 IP 10.0.0.205.51820 > <home-cgnat-ip>.52265: UDP, length 128   <- encrypted reply
```

The packet sizes tell the story: 148/92/32 bytes is the WireGuard handshake, and the 128-byte pairs once per second are the pings, encrypted. `tcpdump` on the hub can't see what's inside them. The full write-up is in [troubleshooting, issue 6](06-troubleshooting-journal.md#6-wireguard-no-handshake-home-sends-vm-never-receives).

Next: [4. Port forwarding](04-port-forwarding.md)
