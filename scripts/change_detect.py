from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
import os
import difflib
from datetime import datetime

BACKUP_DIR = "backups"

def get_latest_backup(host):
    """Find the most recent backup file for a host"""
    files = [
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith(host.lower()) and f.endswith(".cfg")
    ]
    if not files:
        return None, None
    files.sort()
    latest = files[-1]
    with open(f"{BACKUP_DIR}/{latest}") as f:
        return latest, f.read()

def get_current_config(task):
    result = task.run(
        task=netmiko_send_command,
        command_string="show running-config"
    )
    return result[0].result

def compare_configs(host, old_config, new_config, old_filename):
    old_lines = [l for l in old_config.splitlines(keepends=True) if not l.startswith("!Time")]
    new_lines = [l for l in new_config.splitlines(keepends=True) if not l.startswith("!Time")]

    diff = list(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"{old_filename}",
        tofile=f"{host}_current",
        lineterm=""
    ))

    return diff

def save_backup(host, config):
    """Save new backup"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{BACKUP_DIR}/{host}_{timestamp}.cfg"
    with open(filename, "w") as f:
        f.write(config)
    return filename

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

    print("\n🔍 Starting Change Detection...")
    print(f"   Devices: {list(nr.inventory.hosts.keys())}\n")

    result = nr.run(task=get_current_config)

    for host, multi_result in result.items():
        current_config = multi_result[0].result
        print(f"┌─ {host.upper()}")

        if not current_config:
            print(f"│  ❌ Could not fetch current config")
            print(f"└{'─'*40}")
            continue

        old_filename, old_config = get_latest_backup(host)

        if not old_config:
            print(f"│  ⚠️  No baseline found — saving current as baseline")
            filename = save_backup(host, current_config)
            print(f"│  💾 Saved: {filename}")
            print(f"└{'─'*40}")
            continue

        diff = compare_configs(host, old_config, current_config, old_filename)

        if not diff:
            print(f"│  ✅ No changes detected")
        else:
            added = [l for l in diff if l.startswith("+") and not l.startswith("+++")]
            removed = [l for l in diff if l.startswith("-") and not l.startswith("---")]
            print(f"│  ⚠️  CHANGES DETECTED — +{len(added)} lines / -{len(removed)} lines")
            print(f"│")
            for line in diff:
                if line.startswith("+") and not line.startswith("+++"):
                    print(f"│  \033[32m{line}\033[0m")  # green
                elif line.startswith("-") and not line.startswith("---"):
                    print(f"│  \033[31m{line}\033[0m")  # red
                elif line.startswith("@@"):
                    print(f"│  \033[36m{line}\033[0m")  # cyan

            # Save new backup after detecting changes
            filename = save_backup(host, current_config)
            print(f"│")
            print(f"│  💾 New backup saved: {filename}")

        print(f"└{'─'*40}")

    print("\n✅ Change detection complete.")
