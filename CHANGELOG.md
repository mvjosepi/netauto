# Changelog

All notable changes to NetAuto will be documented in this file.

---

## [v1.5.0] - 2026-11-22
### Added
- `topology_discovery.py` — read-only topology discovery via CDP + LLDP (IOS XE, NX-OS)
  - Builds a networkx MultiGraph: parallel links preserved, CDP/LLDP duplicates merged
  - Neighbors not in the inventory are kept as boundary nodes
  - Shared segments (an interface seeing several neighbors) are inferred and drawn as a `segment-N` node
  - Exports yEd-native GraphML (`topologies/topology_latest.graphml`) plus JSON snapshots in `topologies/history/`
  - `--offline --samples DIR` runs from saved CLI output, no lab needed
- `topology_diff.py` — compares two snapshots: new/gone devices, new/missing links, new/gone boundary nodes
  - Exit codes: 0 no change, 1 changes, 2 different labs
- `capture_samples.py` — saves raw `show cdp/lldp neighbors detail` per device
- `yed_export.py` — circular layout, interface labels on every link, boundary nodes in gray dashed
- `samples/iol_xe/` — real IOS XE captures (CML IOL); `inventory_cml.example/` — template inventory

### Validated
- IOS XE: CML IOL lab (2 routers, 2 switches), CDP + LLDP
- NX-OS: virtual-chassis samples only

### Not included (planned)
- Recursive discovery, Draw.io export, Linux host discovery

---

## [v1.4.0] - 2026-06-29
### Added
- `dashboard.py` — HTML dashboard with light theme
  - Device info (version, uptime, serial, last backup)
  - Interface UP/DOWN summary with color-coded badges
  - Routing summary per device
  - Change history from pre/post snapshots
  - Responsive 2-column grid layout
  - Auto-saved to reports/dashboard.html

## [v1.3.0] - 2026-06-05
### Added
- `pre_check.py` — captures pre-change snapshots per device
- `post_check.py` — captures post-change snapshots and validates against pre
- `commands/general.yml` — general validation command set
- `commands/upgrade.yml` — upgrade validation command set
- `commands/routing.yml` — routing change validation command set
- Noise filtering via `ignore_patterns` in command YAML files
- LAB PASSED / LAB FAILED result per device and overall
- Timestamped validation reports saved to snapshots/

---

## [v1.2.0] - 2026-05-30
### Added
- `netconf_query.py` — NETCONF support via ncclient + YANG
  - GET hostname, software version, boot time
  - GET all interfaces with type and enabled status
  - EDIT-CONFIG interface description write operation
  - 275+ YANG models discovered
- `ncclient` added to dependencies
- Completes the automation trilogy: SSH > RESTCONF > NETCONF

---

## [v1.1.0] - 2026-05-30
### Added
- `restconf_interfaces.py` — RESTCONF support via HTTP+JSON+YANG
  - GET hostname, interfaces, static routes
  - GET single interface detail with IPv4
  - PATCH interface description via REST API (HTTP 204)
- `requests` added to dependencies

---

## [v1.0.0] - 2026-05-30
### Added
- Initial release
- `monitor.py` — real-time interface monitoring (IOS XE + NX-OS)
- `config_backup.py` — automated timestamped config backup
- `change_detect.py` — diff-based change detection with color output
- `push_change.py` — config push via SSH
- `inventory_report.py` — full inventory report with routing and CDP
- Nornir + Netmiko multi-vendor inventory (IOS XE, NX-OS)
- DevNet Sandbox lab environment support
