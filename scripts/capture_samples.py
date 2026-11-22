import os
import sys
import yaml
from netmiko import ConnectHandler

SUPPORTED = {"cisco_ios", "cisco_ios_telnet", "cisco_nxos"}


def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


inv = arg("--inventory", "inventory")
out_dir = arg("--out", "samples")

with open(f"{inv}/hosts.yml") as f:
    hosts = yaml.safe_load(f)
with open(f"{inv}/groups.yml") as f:
    groups = yaml.safe_load(f)

os.makedirs(out_dir, exist_ok=True)

for name, h in hosts.items():
    dtype = next((groups[g]["platform"] for g in h.get("groups", [])
                  if g in groups and groups[g].get("platform") in SUPPORTED), None)
    if not dtype:
        print(f"⏭️  {name}: skipped (no supported platform)")
        continue
    params = {"device_type": dtype, "host": h["hostname"],
              "username": h["username"], "password": h["password"], "timeout": 20}
    if h.get("port"):
        params["port"] = h["port"]
    params.update(h.get("connection_options", {}).get("netmiko", {}).get("extras", {}))
    try:
        conn = ConnectHandler(**params)
        if params.get("secret"):
            conn.enable()
    except Exception as e:
        print(f"❌ {name}: {str(e).splitlines()[0]}")
        continue
    for proto, cmd in (("cdp", "show cdp neighbors detail"),
                       ("lldp", "show lldp neighbors detail")):
        try:
            out = conn.send_command(cmd)
        except Exception as e:
            out = f"ERROR: {e}"
        with open(f"{out_dir}/{name}_{proto}.txt", "w") as f:
            f.write(out)
        print(f"✅ {name}: {proto} -> {out_dir}/{name}_{proto}.txt ({len(out.splitlines())} lines)")
    conn.disconnect()
