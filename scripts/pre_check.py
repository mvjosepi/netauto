from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
import yaml
import json
import os
import sys
import signal
from datetime import datetime

SNAPSHOT_DIR = "snapshots"

def timeout_handler(signum, frame):
    print("\n\n⛔ Timeout — check VPN and device reachability.")
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(60)

def load_commands(command_file):
    with open(command_file) as f:
        data = yaml.safe_load(f)
    return data

def run_commands(task, commands):
    results = {}
    for cmd in commands:
        r = task.run(
            task=netmiko_send_command,
            command_string=cmd
        )
        results[cmd] = r[0].result
    return results

def save_snapshot(host, results, change_id):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    filename = f"{SNAPSHOT_DIR}/{change_id}_{host}_pre.json"
    with open(filename, "w") as f:
        json.dump({
            "host": host,
            "phase": "pre",
            "change_id": change_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": results
        }, f, indent=2)
    return filename

if __name__ == "__main__":
    # Get command file and change ID
    if len(sys.argv) < 3:
        print("\nUsage: python scripts/pre_check.py <command_file> <change_id>")
        print("Example: python scripts/pre_check.py commands/upgrade.yml CHG001")
        sys.exit(1)

    command_file = sys.argv[1]
    change_id = sys.argv[2]

    # Load commands
    cmd_data = load_commands(command_file)
    commands = cmd_data["commands"]
    description = cmd_data.get("description", "")

    print(f"\n{'='*65}")
    print(f"  PRE-CHECK SNAPSHOT")
    print(f"  Change ID   : {change_id}")
    print(f"  Description : {description}")
    print(f"  Commands    : {len(commands)}")
    print(f"  Timestamp   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")

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

    print(f"\n  Devices: {list(nr.inventory.hosts.keys())}")
    print(f"\n  Running {len(commands)} commands per device...\n")

    result = nr.run(
        task=run_commands,
        commands=commands
    )

    for host, multi_result in result.items():
        cmd_results = multi_result[0].result
        filename = save_snapshot(host, cmd_results, change_id)
        print(f"  ✅ {host.upper():<15} → {filename}")

    signal.alarm(0)
    print(f"\n{'='*65}")
    print(f"  PRE-CHECK COMPLETE — Perform your change now")
    print(f"  When done run: python scripts/post_check.py {command_file} {change_id}")
    print(f"{'='*65}\n")
