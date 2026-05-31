from ncclient import manager
from ncclient.xml_ import to_ele
import xml.etree.ElementTree as ET
import urllib3
from datetime import datetime
import signal
import sys

urllib3.disable_warnings()

def timeout_handler(signum, frame):
    print("\n\n⛔ Connection timeout — VPN may be down or device unreachable.")
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)

DEVICE = {
    "host": "10.10.20.48",
    "port": 830,
    "username": "developer",
    "password": "C1sco12345",
    "hostkey_verify": False,
    "device_params": {"name": "iosxe"},
    "timeout": 15,
    "manager_params": {"timeout": 15},
}

def get_hostname(conn):
    filter_ele = to_ele("""
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <hostname/>
    </native>
    """)
    response = conn.get(filter=("subtree", filter_ele))
    ns = "http://cisco.com/ns/yang/Cisco-IOS-XE-native"
    root = ET.fromstring(str(response))
    hostname = root.find(f".//{{{ns}}}hostname")
    return hostname.text if hostname is not None else "N/A"

def get_version(conn):
    filter_ele = to_ele("""
    <device-hardware-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-device-hardware-oper">
      <device-hardware>
        <device-system-data>
          <software-version/>
          <boot-time/>
        </device-system-data>
      </device-hardware>
    </device-hardware-data>
    """)
    response = conn.get(filter=("subtree", filter_ele))
    ns = "http://cisco.com/ns/yang/Cisco-IOS-XE-device-hardware-oper"
    root = ET.fromstring(str(response))
    version = root.find(f".//{{{ns}}}software-version")
    boot_time = root.find(f".//{{{ns}}}boot-time")
    reboot = root.find(f".//{{{ns}}}last-reboot-reason")

    # Extract just the version number from the long string
    version_text = "N/A"
    if version is not None and version.text:
        for part in version.text.split(","):
            if "Version" in part:
                version_text = part.strip()
                break

    return {
        "version": version_text,
        "boot_time": boot_time.text if boot_time is not None else "N/A",
        "reboot_reason": reboot.text if reboot is not None else "N/A",
    }

def get_interfaces(conn):
    filter_ele = to_ele("""
    <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
      <interface/>
    </interfaces>
    """)
    response = conn.get(filter=("subtree", filter_ele))
    ns = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
    root = ET.fromstring(str(response))
    interfaces = []
    for intf in root.iter(f"{{{ns}}}interface"):
        name = intf.find(f"{{{ns}}}name")
        enabled = intf.find(f"{{{ns}}}enabled")
        intf_type = intf.find(f"{{{ns}}}type")
        interfaces.append({
            "name": name.text if name is not None else "N/A",
            "enabled": enabled.text if enabled is not None else "N/A",
            "type": intf_type.text.split(":")[-1] if intf_type is not None else "N/A",
        })
    return interfaces

def edit_config_description(conn, interface, description):
    config_xml = f"""
    <config>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface>
          <name>{interface}</name>
          <description>{description}</description>
        </interface>
      </interfaces>
    </config>
    """
    response = conn.edit_config(target="running", config=config_xml)
    return response

def get_capabilities(conn):
    caps = []
    for cap in conn.server_capabilities:
        if "cisco" in cap.lower() or "ietf" in cap.lower():
            model = cap.split("module=")[-1].split("&")[0] if "module=" in cap else cap
            caps.append(model)
    return sorted(caps)

if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*65}")
    print(f"  NETCONF QUERY — CAT8Kv")
    print(f"  {timestamp}")
    print(f"{'='*65}")

    print("\n🔌 Connecting via NETCONF (port 830)...")
    print("   Timeout: 30s\n")

    try:
        with manager.connect(**DEVICE) as conn:
            print("  ✅ NETCONF session established\n")
            signal.alarm(0)

            # 1. Hostname
            print("📍 HOSTNAME")
            try:
                hostname = get_hostname(conn)
                print(f"  {hostname}")
            except Exception as e:
                print(f"  Error: {e}")

            # 2. Version
            print("\n📦 SOFTWARE VERSION")
            try:
                ver = get_version(conn)
                print(f"  IOS XE Version : {ver['version']}")
                print(f"  Boot Time      : {ver['boot_time']}")
                print(f"  Reboot Reason  : {ver['reboot_reason']}")
            except Exception as e:
                print(f"  Error: {e}")

            # 3. Interfaces
            print("\n📡 INTERFACES")
            try:
                interfaces = get_interfaces(conn)
                print(f"\n  {'NAME':<35} {'TYPE':<25} {'ENABLED'}")
                print(f"  {'─'*63}")
                for intf in interfaces:
                    status = "✅ true" if intf["enabled"] == "true" else "❌ false"
                    print(f"  {intf['name']:<35} {intf['type']:<25} {status}")
                print(f"\n  Total: {len(interfaces)} interfaces")
            except Exception as e:
                print(f"  Error: {e}")

            # 4. Edit config
            print("\n✏️  EDIT-CONFIG — Updating Loopback99 description via NETCONF")
            try:
                response = edit_config_description(
                    conn, "Loopback99", "MANAGED-BY-NETCONF"
                )
                if "<ok/>" in str(response):
                    print("  ✅ Loopback99 description updated successfully")
                else:
                    print(f"  Response: {response}")
            except Exception as e:
                print(f"  Error: {e}")

            # 5. YANG capabilities
            print("\n📚 SUPPORTED YANG MODELS (sample)")
            try:
                caps = get_capabilities(conn)
                for cap in caps[:10]:
                    print(f"  • {cap}")
                print(f"  ... and {len(caps)-10} more models supported")
            except Exception as e:
                print(f"  Error: {e}")

    except Exception as e:
        signal.alarm(0)
        print(f"\n❌ Connection failed: {e}")
        print("   Check VPN connection and device reachability.")
        sys.exit(1)

    print(f"\n{'='*65}")
    print(f"  NETCONF QUERY COMPLETE")
    print(f"{'='*65}\n")
