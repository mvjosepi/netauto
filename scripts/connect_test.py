from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result

nr = InitNornir(
    inventory={
        "plugin": "SimpleInventory",
        "options": {
            "host_file": "inventory/hosts.yml",
            "group_file": "inventory/groups.yml",
            "defaults_file": "inventory/defaults.yml",
        },
    }
)

print("\n>>> Running show version on all devices...\n")

result = nr.run(
    task=netmiko_send_command,
    command_string="show version"
)

print_result(result)
