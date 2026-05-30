from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
import os
from datetime import datetime

BACKUP_DIR = "backups"

def backup_config(task):
    if "nxos" in str(task.host.groups):
        cmd = "show running-config"
    else:
        cmd = "show running-config"

    result = task.run(
        task=netmiko_send_command,
        command_string=cmd
    )
    return result[0].result

def save_backup(host, config):
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

    print("\n🚀 Starting Config Backup...")
    print(f"   Devices: {list(nr.inventory.hosts.keys())}")
    print(f"   Output : ./{BACKUP_DIR}/\n")

    result = nr.run(task=backup_config)

    for host, multi_result in result.items():
        config = multi_result[0].result
        if config:
            filename = save_backup(host, config)
            lines = len(config.splitlines())
            print(f"  ✅ {host.upper():<12} → {filename} ({lines} lines)")
        else:
            print(f"  ❌ {host.upper():<12} → No output received")

    print("\n✅ Backup complete.")
