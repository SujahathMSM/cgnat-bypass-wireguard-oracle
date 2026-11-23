# Oracle Cloud Security List: ingress rules

Path in the console: **Networking → Virtual cloud networks → `<your-vcn>` → Security → Default Security List for `<your-vcn>` → Security rules → Add Ingress Rules**

The VM sits in the **public** subnet, so the rules go on the security list attached to that subnet. The VCN wizard creates a second list for the private subnet; adding rules there does nothing for this VM.

| # | Stateless | Source CIDR | Protocol | Source port | Destination port | Purpose |
|---|-----------|-------------|----------|-------------|------------------|---------|
| 1 | No | `0.0.0.0/0` | TCP | All | `22` | SSH to the VM (created by default) |
| 2 | No | `0.0.0.0/0` | ICMP | n/a | type 3, code 4 | Path MTU discovery (default) |
| 3 | No | `10.0.0.0/16` | ICMP | n/a | type 3 | VCN-internal (default) |
| 4 | No | `0.0.0.0/0` | **UDP** | All | **`51820`** | WireGuard handshake + tunnel |
| 5 | No | `0.0.0.0/0` | TCP | All | **`80`** | HTTP → forwarded to home server |
| 6 | No | `0.0.0.0/0` | TCP | All | **`443`** | HTTPS → forwarded to home server |

## Things that went wrong here

- **Missing UDP 51820 rule.** The home server sent handshakes but the VM never saw them. `tcpdump` on the VM was silent, which points to the cloud firewall. See [troubleshooting, issue 6](../../docs/06-troubleshooting-journal.md#6-wireguard-no-handshake-home-sends-vm-never-receives).
- **Typo in the port field** (`40,443` instead of `80,443`). Making one rule per port is clearer and avoids typos like this.
- **Port in the wrong box.** The port goes in **Destination** Port Range. Leave Source Port Range empty, because clients use random source ports.

## Stateful vs stateless

Keep **Stateless = No**. A stateful rule automatically allows the reply packets back out. With a stateless rule you would also need matching egress rules.

## Two firewalls, not one

Traffic to the VM passes **two** firewalls, and both must allow it:

1. The **Oracle Security List**, at the cloud network edge.
2. The VM's own **iptables**, which on Oracle's Ubuntu image REJECTs everything except SSH by default.

Forwarded web traffic (80/443) goes through the iptables **FORWARD** chain, not INPUT. That's why the WireGuard config inserts FORWARD rules, and why no INPUT rules are needed for 80/443.
