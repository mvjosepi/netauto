from netmiko import ConnectHandler

device = {
    "device_type": "cisco_ios",
    "host": "10.10.20.48",
    "username": "developer",
    "password": "C1sco12345",
}

# Small safe change — add a loopback with description
commands = [
    "interface Loopback99",
    "description NETAUTO-TEST-CHANGE",
    "ip address 10.99.99.1 255.255.255.255",
]

print("🔧 Pushing config change to CAT8Kv...")
conn = ConnectHandler(**device)
output = conn.send_config_set(commands)
conn.save_config()
conn.disconnect()

print(output)
print("\n✅ Change pushed successfully.")
