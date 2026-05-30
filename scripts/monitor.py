from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
import time
from datetime import datetime

def parse_iosxe(output):
    up, down = [], []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0] != "Interface":
            intf = parts[0]
            ip = parts[1]
            status = parts[4]
            proto = parts[5]
            if status == "up" and proto == "up":
                up.append(f"  ✅ {intf:<25} {ip}")
            elif "down" in status or "down" in proto:
                down.append(f"  ❌ {intf:<25} {ip}")
    return up, down

def parse_nxos(output):
    up, down = [], []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4 and (
            parts[0].startswith("Eth") or parts[0].startswith("mgmt")
        ):
            intf = parts[0]
            status = parts[2] if parts[0].startswith("mgmt") else parts[4]
            if status == "up":
                up.append(f"  ✅ {intf}")
            elif status == "down":
                down.append(f"  ❌ {intf}")
    return up, down

def get_interfaces(task):
    if "nxos" in str(task.host.groups):
        cmd = "show interface brief"
    else:
        cmd = "show ip interface brief"
    result = task.run(
        task=netmiko_send_command,
        command_string=cmd
    )
    return result[0].result

def monitor_loop(nr, interval=30, cycles=3):
    for cycle in range(1, cycles + 1):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'='*60}")
        print(f"  NETWORK MONITOR — Cycle {cycle}/{cycles} — {timestamp}")
        print(f"{'='*60}")

        result = nr.run(task=get_interfaces)

        for host, multi_result in result.items():
            output = multi_result[0].result
            print(f"\n┌─ {host.upper()}")

            if not output:
                print("│  No output received")
                continue

            if "nxos" in str(nr.inventory.hosts[host].groups):
                up, down = parse_nxos(output)
            else:
                up, down = parse_iosxe(output)

            print(f"│  UP   ({len(up)})")
            for i in up:
                print(f"│ {i}")
            print(f"│  DOWN ({len(down)})")
            for i in down[:5]:  # limit to first 5 down
                print(f"│ {i}")
            if len(down) > 5:
                print(f"│   ... and {len(down)-5} more down")
            print(f"└{'─'*40}")

        if cycle < cycles:
            print(f"\n⏳ Next check in {interval}s... (Ctrl+C to stop)")
            time.sleep(interval)

    print("\n✅ Monitoring complete.")

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

    print("\n🚀 Starting Network Monitor...")
    print(f"   Devices : {list(nr.inventory.hosts.keys())}")
    print(f"   Interval: {30}s | Cycles: 3")

    try:
        monitor_loop(nr, interval=30, cycles=3)
    except KeyboardInterrupt:
        print("\n\n⛔ Monitor stopped by user.")
