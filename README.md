# NetAuto - Multi-Vendor Network Automation Toolkit

![Version](https://img.shields.io/badge/version-v1.3.0-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-IOS%20XE%20%7C%20NX--OS-lightgrey)

A Python-based network automation toolkit for monitoring, backup, change detection,
and inventory reporting across multi-vendor Cisco environments.

Built with **Nornir** and **Netmiko** — no Ansible, no YAML playbooks, pure Python.

---

## Stack

| Tool | Purpose |
|---|---|
| Python 3.11 | Core language |
| Nornir 3.x | Multi-device orchestration |
| Netmiko 4.x | SSH connectivity |
| uv | Package management |
| requests | RESTCONF API calls |
| ncclient | NETCONF sessions |

---

## Supported Platforms

| Device | OS | Status |
|---|---|---|
| Cisco Nexus 9000v | NX-OS 9.x | ✅ Full support |
| Cisco IOS XRv | IOS XR | ⚠️ ssh-dss limitation |
| Cisco Catalyst 8000v | IOS XE 17.x | ✅ Full support (SSH + RESTCONF) |

---

## Project Structure

```
netauto/
├── inventory/
│   ├── hosts.yml
│   ├── groups.yml
│   └── defaults.yml
├── commands/
│   ├── general.yml             ✅ general validation command set
│   ├── upgrade.yml             ✅ upgrade validation command set
│   └── routing.yml             ✅ routing change validation command set
├── scripts/
│   ├── monitor.py              ✅ real-time interface monitoring
│   ├── config_backup.py        ✅ automated config backup
│   ├── change_detect.py        ✅ diff-based change detection
│   ├── push_change.py          ✅ config push
│   ├── inventory_report.py     ✅ full inventory report
│   └── restconf_interfaces.py  ✅ RESTCONF GET + PATCH via API
│   └── netconf_query.py        ✅ NETCONF GET + EDIT-CONFIG via XML/YANG
│   ├── pre_check.py            ✅ pre-change snapshot
│   └── post_check.py           ✅ post-change validation + report
├── snapshots/                  ✅ pre/post snapshots and reports
├── backups/                    ✅ timestamped config snapshots
└── reports/                    ✅ timestamped inventory reports
```

---

## Getting Started

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and set up the environment

```bash
git clone https://github.com/mvjosepi/netauto.git
cd netauto

uv venv --python 3.11 --seed
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

uv pip install "setuptools==69.5.1"
uv pip install netmiko
uv pip install nornir nornir-netmiko nornir-utils
uv pip install requests
uv pip install ncclient
uv pip install pyyaml
```

### 3. Configure your inventory

Edit `inventory/hosts.yml` with your device credentials:

```yaml
cat8kv:
  hostname: "10.10.20.48"
  port: 22
  username: "developer"
  password: "C1sco12345"
  groups:
    - cisco_iosxe

nexus9k:
  hostname: "10.10.20.40"
  port: 22
  username: "admin"
  password: "your-password"
  groups:
    - cisco_nxos
```

### 4. Run the scripts

```bash
# Real-time interface monitoring (3 cycles, 30s interval)
python scripts/monitor.py

# Backup running configs from all devices
python scripts/config_backup.py

# Detect config changes since last backup
python scripts/change_detect.py

# Generate full inventory report
python scripts/inventory_report.py

# Queries the Catalyst 8000v directly via RESTCONF API (HTTP+JSON)
python scripts/restconf_interfaces.py

# Connects to the Catalyst 8000v via NETCONF (port 830) using XML-based
python scripts/netconf_query.py

# Before the change begins
python scripts/pre_check.py commands/general.yml CHG001

# After the change ended
python scripts/post_check.py commands/general.yml CHG001
```

---

## Script Details

### monitor.py
Polls all devices every 30 seconds and displays a clean UP/DOWN
interface summary per device. Runs in parallel using Nornir threads.

```
┌─ CAT8KV
│  UP   (6)
│   ✅ GigabitEthernet1          10.10.20.48
│   ✅ Loopback0                 10.0.0.1
│   ✅ Loopback10                unassigned
│   ✅ Loopback109               10.255.255.9
│   ✅ VirtualPortGroup0         192.168.1.1
│   ✅ Loopback99                10.99.99.1
│  DOWN (2)
│   ❌ GigabitEthernet2          unassigned
│   ❌ GigabitEthernet3          unassigned
└────────────────────────────────────────
```


### config_backup.py
Fetches running-config from all devices and saves them as
timestamped `.cfg` files under `backups/`.

```
✅ CAT8KV   > backups/cat8kv_20260530_150134.cfg (246 lines)
✅ NEXUS9K  > backups/nexus9k_20260530_150134.cfg (255 lines)
```

### change_detect.py
Compares current running-config against the latest backup using
unified diff. Highlights added lines in green and removed lines
in red. Saves a new backup when changes are found.

```
⚠️  CHANGES DETECTED — +4 lines / -0 lines
+interface Loopback99

description NETAUTO-TEST-CHANGE
ip address 10.99.99.1 255.255.255.255
```

### inventory_report.py
Generates a full structured report per device including:
- Software version and hardware platform
- System uptime and serial number
- Interface UP/DOWN summary with IP addresses
- Routing table summary
- CDP neighbor table

Report is printed to screen and saved to `reports/`.


### restconf_interfaces.py
Queries the Catalyst 8000v directly via RESTCONF API (HTTP+JSON)
using YANG data models - no SSH required. Demonstrates the modern
API-first approach to network automation.

Covers:
- GET hostname
- GET all interfaces with type and status
- GET single interface detail with IPv4 address
- GET static routing table
- PATCH interface description - write operation via REST API

```
=================================================================
  RESTCONF QUERY — CAT8Kv
  2026-05-30 18:14:10
=================================================================
📍 HOSTNAME
  cat8000v
📡 INTERFACES
─────────────────────────────────────────────────────────────────
  NAME                                TYPE                 STATUS
─────────────────────────────────────────────────────────────────
  GigabitEthernet1                    ethernetCsmacd       ✅ enabled
  GigabitEthernet2                    ethernetCsmacd       ❌ disabled
  Loopback99                          softwareLoopback     ✅ enabled
─────────────────────────────────────────────────────────────────
  Total: 8 interfaces
🗺️  STATIC ROUTES
─────────────────────────────────────────────────────────────────
  PREFIX               MASK                 NEXT-HOP
─────────────────────────────────────────────────────────────────
  0.0.0.0              0.0.0.0              10.10.20.254
─────────────────────────────────────────────────────────────────
✏️  PATCH — Updating Loopback99 description via RESTCONF API
  ✅ Loopback99 description updated successfully (HTTP 204)
=================================================================
  RESTCONF QUERY COMPLETE
=================================================================
```

### netconf_query.py
Connects to the Catalyst 8000v via NETCONF (port 830) using XML-based
YANG data models through ncclient. Completes the automation trilogy
alongside SSH/CLI and RESTCONF.

Covers:
- GET hostname
- GET software version and boot time
- GET all interfaces with type and enabled status
- EDIT-CONFIG interface description — write operation via NETCONF
- Discovery of 275+ supported YANG models

```
=================================================================
  NETCONF QUERY — CAT8Kv
  2026-05-30 20:59:24
=================================================================
🔌 Connecting via NETCONF (port 830)...
   Timeout: 30s
  ✅ NETCONF session established
📍 HOSTNAME
  cat8000v
📦 SOFTWARE VERSION
  IOS XE Version : Version 17.12.2
  Boot Time      : 2026-05-30T12:39:08+00:00
📡 INTERFACES
  NAME                                TYPE                      ENABLED
  ───────────────────────────────────────────────────────────────
  GigabitEthernet1                    ethernetCsmacd            ✅ true
  GigabitEthernet2                    ethernetCsmacd            ❌ false
  Loopback99                          softwareLoopback          ✅ true
  Total: 8 interfaces
✏️  EDIT-CONFIG — Loopback99 description updated successfully
📚 SUPPORTED YANG MODELS — 275+ models supported
=================================================================
  NETCONF QUERY COMPLETE
=================================================================
```

### pre_check.py + post_check.py
ITSM-style pre/post change validation - captures device state before
and after a change, compares automatically and produces a LAB PASSED
or LAB FAILED result per device.

Supports customizable command sets per change type with noise filtering
via `ignore_patterns` to suppress expected fluctuations like uptime
counters and CDP holdtimers.

```
# Before the change
python scripts/pre_check.py commands/general.yml CHG001

# After the change
python scripts/post_check.py commands/general.yml CHG001
```

```
┌───────────────────────────────────────────────────────────────
│  DEVICE    : CAT8KV
│  CHANGE ID : CHG001
│  PRE TIME  : 2026-06-05 16:44:30
│  POST TIME : 2026-06-05 16:45:56
│
│  ⚠️  COMMAND: show ip interface brief
│     MISSING LINES:
│       - Loopback99   unassigned   YES unset  up                    up
│     NEW LINES:
│       + Loopback99   unassigned   YES unset  administratively down down
│
│  ❌ LAB FAILED — Review differences above
└───────────────────────────────────────────────────────────────
=================================================================
  🏆 OVERALL RESULT : ALL DEVICES PASSED
=================================================================
```

---

## Lab Environment

Scripts were developed and tested against the
**Cisco DevNet Sandbox** (reservable lab):

- Catalyst 8000v — IOS XE 17.12.2
- Nexus 9000v — NX-OS 9.3(5)

Access requires Cisco DevNet account and VPN connection
via OpenConnect or Cisco AnyConnect.

- [devnetsandbox.cisco.com](https://devnetsandbox.cisco.com)

---

## Author

**Marcus** - Senior Network & Security Engineer
> Building automation tools for multi-vendor environments.
> Focused on network operations, cybersecurity, and Python-based infrastructure tooling.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue)](https://linkedin.com/in/mborile)

---

## License
MIT

