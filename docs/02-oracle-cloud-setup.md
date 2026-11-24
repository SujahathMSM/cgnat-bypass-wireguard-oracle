# 2. Oracle Cloud setup

The hub is an Oracle Cloud **Always Free** VM in the **India South (Hyderabad)** region, picked because it's close to Sri Lanka. Hyderabad has a single availability domain (AD-1), which matters later.

## 2.1 Account safety first

Before creating anything:

1. **Enable MFA** on the console login (Profile → My profile → Multi-factor authentication).
2. **Create a budget alert.** The free trial gives SGD 400 of credits (about US$300) for 30 days. I set a *custom, non-recurring* budget covering exactly the trial window, with alerts at 50% and 90%.

   A monthly budget would reset on the 1st of the month and lose track of spending from the trial's first week, because the trial ran from 23 Nov to 22 Dec. After the trial, the plan is to switch to a budget of SGD 1 so any real charge triggers an email.

Always Free resources show up as **$0** in cost analysis, so the free VM never triggers the budget.

## 2.2 Networking: use the VCN wizard

**Networking → Virtual cloud networks → Start VCN Wizard → "Create VCN with Internet Connectivity"**

| Setting | Value |
|---|---|
| Name | `dev-01` |
| VCN CIDR | `10.0.0.0/16` |
| Public subnet | `10.0.0.0/24` |
| Private subnet | `10.0.1.0/24` |

The wizard creates the VCN, both subnets, an internet gateway, a NAT gateway, a service gateway, route tables and a default security list with SSH (TCP 22) open.

I first tried the manual "Create VCN" form, which only creates an empty VCN, and then tried creating the network inside the instance form, where the public IPv4 toggle stayed locked. The wizard avoided both problems (see [troubleshooting, issues 3 and 4](06-troubleshooting-journal.md#3-public-ipv4-toggle-locked-in-the-instance-form)).

## 2.3 SSH key

On Windows (PowerShell), I made a dedicated key with a label and filename:

```powershell
ssh-keygen -t ed25519 -C "oracle" -f $env:USERPROFILE\.ssh\oracle_ed25519
type $env:USERPROFILE\.ssh\oracle_ed25519.pub   # paste this into Oracle
```

`-C` sets a comment inside the key. `-f` sets the filename so it doesn't overwrite the default `id_ed25519`.

## 2.4 The instance

**Compute → Instances → Create instance**

| Section | Choice | Why |
|---|---|---|
| Image | Canonical Ubuntu 24.04 (not Minimal) | Matches my other machines; Minimal strips useful tools |
| Shape (first attempt) | `VM.Standard.A1.Flex`, 4 OCPU / 24 GB | Picked from older guides. Oracle's current docs put the Always Free A1 allowance at **2 OCPU / 12 GB** (1,500 OCPU hours and 9,000 GB hours a month), so anything above that would be billed |
| Shape (what I actually got) | `VM.Standard.E2.1.Micro` (1/8 OCPU burstable, 1 GB) | A1 was out of capacity in AD-1 |
| Capacity type | On-demand | Preemptible can be reclaimed at any time |
| Shielded / confidential | Off | Not supported for these shapes; the warning is harmless |
| Network | VCN `dev-01`, **public** subnet, assign public IPv4 = **on** | Without the public IP the whole project is pointless |
| SSH key | Paste `oracle_ed25519.pub` | |
| Boot volume | 50 GB on the micro, leaving room for an A1 later | Always Free allows 200 GB total |

I saved the A1 configuration with **Save as stack** (Resource Manager, Terraform). Retrying it later at off-peak hours is one click: open the stack, then **Apply**.

## 2.5 First login

```powershell
ssh -i "$env:USERPROFILE\.ssh\oracle_ed25519" ubuntu@<ORACLE_PUBLIC_IP>
```

The quotes matter because my Windows username contains spaces.

On a 1 GB VM, add swap before running anything heavy:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo apt update && sudo apt upgrade -y
```

## 2.6 The Oracle firewall gotcha

Oracle's Ubuntu image ships with its own iptables rules. They allow SSH, ICMP and established traffic, and then **REJECT everything else** in both the `INPUT` and `FORWARD` chains:

```
5    ACCEPT  tcp  --  0.0.0.0/0  0.0.0.0/0  state NEW tcp dpt:22
6    REJECT  all  --  0.0.0.0/0  0.0.0.0/0  reject-with icmp-host-prohibited
```

So every port needs to be opened **twice**: once in the cloud Security List and once in the VM's iptables, above that REJECT line. See [configs/oracle-cloud/security-list-ingress.md](../configs/oracle-cloud/security-list-ingress.md).

Next: [3. WireGuard tunnel](03-wireguard-tunnel.md)
