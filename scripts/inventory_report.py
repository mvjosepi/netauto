from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from datetime import datetime
import os

REPORT_DIR = "reports"

def get_device_info(task):
    results = {}

    # Show version
    r = task.run(task=netmiko_send_command, command_string="show version")
    results["version"] = r[0].result

    # Show interfaces
    if "nxos" in str(task.host.groups):
        r = task.run(task=netmiko_send_command, command_string="show interface brief")
    else:
        r = task.run(task=netmiko_send_command, command_string="show ip interface brief")
    results["interfaces"] = r[0].result

    # Show CDP/LLDP neighbors
    if "nxos" in str(task.host.groups):
        r = task.run(task=netmiko_send_command, command_string="show cdp neighbors")
    else:
        r = task.run(task=netmiko_send_command, command_string="show cdp neighbors")
    results["neighbors"] = r[0].result

    # Show routing table summary
    if "nxos" in str(task.host.groups):
        r = task.run(task=netmiko_send_command, command_string="show ip route summary")
    else:
        r = task.run(task=netmiko_send_command, command_string="show ip route summary")
    results["routes"] = r[0].result

    return results

def parse_version(output, platform):
    """Extract key version info"""
    info = {}
    for line in output.splitlines():
        if "Cisco IOS XE Software" in line or "NXOS:" in line:
            info["software"] = line.strip()
        if "cisco C8000" in line or "cisco Nexus" in line:
            info["hardware"] = line.strip()
        if "uptime is" in line or "Kernel uptime" in line:
            info["uptime"] = line.strip()
        if "Processor Board ID" in line:
            info["serial"] = line.strip()
    return info

def parse_interfaces_iosxe(output):
    up, down = [], []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0] != "Interface":
            intf, ip, status, proto = parts[0], parts[1], parts[4], parts[5]
            if status == "up" and proto == "up":
                up.append((intf, ip))
            else:
                down.append((intf, ip))
    return up, down

def parse_interfaces_nxos(output):
    up, down = [], []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3 and (
            parts[0].startswith("Eth") or parts[0].startswith("mgmt")
        ):
            intf = parts[0]
            status = parts[2] if parts[0].startswith("mgmt") else parts[4]
            if status == "up":
                up.append((intf, ""))
            else:
                down.append((intf, ""))
    return up, down

def generate_report(all_results, nr):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("=" * 70)
    lines.append(f"  NETWORK INVENTORY REPORT")
    lines.append(f"  Generated : {timestamp}")
    lines.append(f"  Devices   : {len(all_results)}")
    lines.append("=" * 70)

    for host, multi_result in all_results.items():
        data = multi_result[0].result
        if not data:
            continue

        is_nxos = "nxos" in str(nr.inventory.hosts[host].groups)
        version_info = parse_version(data["version"], host)

        if is_nxos:
            up, down = parse_interfaces_nxos(data["interfaces"])
        else:
            up, down = parse_interfaces_iosxe(data["interfaces"])

        lines.append(f"\n┌{'─'*68}")
        lines.append(f"│  DEVICE   : {host.upper()}")
        lines.append(f"│  PLATFORM : {'NX-OS' if is_nxos else 'IOS XE'}")

        for k, v in version_info.items():
            lines.append(f"│  {k.upper():<10}: {v}")

        lines.append(f"│")
        lines.append(f"│  INTERFACES")
        lines.append(f"│  UP   ({len(up)})")
        for intf, ip in up:
            ip_str = f"  {ip}" if ip and ip != "unassigned" else ""
            lines.append(f"│    ✅ {intf:<30}{ip_str}")

        lines.append(f"│  DOWN ({len(down)})")
        for intf, ip in down[:5]:
            lines.append(f"│    ❌ {intf}")
        if len(down) > 5:
            lines.append(f"│    ... and {len(down)-5} more")

        lines.append(f"│")
        lines.append(f"│  ROUTING SUMMARY")
        for line in data["routes"].splitlines():
            if line.strip() and not line.startswith("IP"):
                lines.append(f"│    {line.strip()}")

        lines.append(f"│")
        lines.append(f"│  CDP NEIGHBORS")
        neighbor_lines = [
            l for l in data["neighbors"].splitlines()
            if l.strip() and "Capability" not in l
            and "Device" not in l and "---" not in l
            and "Total" not in l and "cdp" not in l.lower()
        ]
        if neighbor_lines:
            for l in neighbor_lines[:5]:
                lines.append(f"│    {l.strip()}")
        else:
            lines.append(f"│    No neighbors found")

        lines.append(f"└{'─'*68}")

    lines.append(f"\n{'='*70}")
    lines.append(f"  END OF REPORT")
    lines.append(f"{'='*70}\n")

    return "\n".join(lines)

if __name__ == "__main__":
    nr = InitNornir(
        inventory={
            "plugin": "SimpleInventory",
            "options": {
                "host_file": "inventory/hosts.yml",
                "group_file": "inventory/groups.yml",
                "defaults_file": "inventory/defaults.yml",
            },
        },
        runner={
            "plugin": "threaded",
            "options": {"num_workers": 5}
        }
    )

    nr = nr.filter(filter_func=lambda h: h.name != "iosxrv")

    print("\n📋 Generating Inventory Report...")
    print(f"   Devices: {list(nr.inventory.hosts.keys())}\n")

    result = nr.run(task=get_device_info)

    report = generate_report(result, nr)

    # Print to screen
    print(report)

    # Save to file
    os.makedirs(REPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{REPORT_DIR}/inventory_{timestamp}.txt"
    with open(filename, "w") as f:
        f.write(report)

    print(f"💾 Report saved to: {filename}")
