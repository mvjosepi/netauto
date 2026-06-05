# Changelog

All notable changes to NetAuto will be documented in this file.

---

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
