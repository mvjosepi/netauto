# Changelog

All notable changes to NetAuto will be documented in this file.

---

## [v1.2.0] - Upcoming
### Planned
- NETCONF script — XML-based configuration and state retrieval via ncclient
- Completes the automation trilogy: SSH → RESTCONF → NETCONF

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
