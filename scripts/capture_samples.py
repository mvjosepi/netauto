import os
import yaml
from netmiko import ConnectHandler

TYPES = {"cisco_iosxe": "cisco_ios", "cisco_nxos": "cisco_nxos"}

with open("inventory/hosts.yml") as f:
    hosts = yaml.safe_load(f)

os.makedirs("samples", exist_ok=True)

for name, h in hosts.items():
    dtype = next((TYPES[g] for g in h.get("groups", []) if g in TYPES), None)
    if not dtype:
        print(f"⏭️  {name}: skipped (no supported group)")
        continue
    try:
        conn = ConnectHandler(device_type=dtype, host=h["hostname"],
                              username=h["username"], password=h["password"],
                              timeout=20)
    except Exception as e:
        print(f"❌ {name}: {str(e).splitlines()[0]}")
        continue
    for proto, cmd in (("cdp", "show cdp neighbors detail"),
                       ("lldp", "show lldp neighbors detail")):
        try:
            out = conn.send_command(cmd)
        except Exception as e:
            out = f"ERROR: {e}"
        with open(f"samples/{name}_{proto}.txt", "w") as f:
            f.write(out)
        print(f"✅ {name}: {proto} -> samples/{name}_{proto}.txt ({len(out.splitlines())} lines)")
    conn.disconnect()
