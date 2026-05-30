import paramiko
from paramiko import DSSKey
from netmiko import ConnectHandler

# Register ssh-dss in Paramiko's key info table
paramiko.Transport._key_info["ssh-dss"] = DSSKey
paramiko.Transport._preferred_keys = (
    "ssh-dss",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
)

device = {
    "device_type": "cisco_xr",
    "host": "10.10.20.35",
    "username": "developer",
    "password": "C1sco12345",
}

print("Connecting to IOS XRv...")
conn = ConnectHandler(**device)
output = conn.send_command("show version")
print(output)
conn.disconnect()
