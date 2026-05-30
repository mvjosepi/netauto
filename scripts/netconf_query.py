from ncclient import manager
from ncclient.xml_ import to_ele
import xml.dom.minidom
import urllib3
from datetime import datetime

urllib3.disable_warnings()

DEVICE = {
    "host": "10.10.20.48",
    "port": 830,
    "username": "developer",
    "password": "C1sco12345",
    "hostkey_verify": False,
    "device_params": {"name": "iosxe"},
}

def pretty_xml(xml_str):
    """Format XML output for readability"""
    try:
        return xml.dom.minidom.parseString(xml_str).toprettyxml(indent="  ")
    except Exception:
        return xml_str

def get_interfaces(conn):
    filter_xml = """
    <filter>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface/>
      </interfaces>
    </filter>
    """
    response = conn.get(filter_xml)
    return response

def parse_interfaces(response):
    from xml.etree import ElementTree as ET
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

def get_hostname(conn):
    filter_xml = """
    <filter>
      <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <hostname/>
      </native>
    </filter>
    """
    response = conn.get(filter_xml)
    from xml.etree import ElementTree as ET
    ns = "http://cisco.com/ns/yang/Cisco-IOS-XE-native"
    root = ET.fromstring(str(response))
    hostname = root.find(f".//{{{ns}}}hostname")
    return hostname.text if hostname is not None else "N/A"

def get_version(conn):
    filter_xml = """
    <filter>
      <device-hardware-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-device-hardware-oper">
        <device-hardware>
          <device-system-data>
            <ios-xe-version/>
            <rommon-version/>
            <boot-time/>
          </device-system-data>
        </device-hardware>
      </device-hardware-data>
    </filter>
    """
    response = conn.get(filter_xml)
    from xml.etree import ElementTree as ET
    ns = "http://cisco.com/ns/yang/Cisco-IOS-XE-device-hardware-oper"
    root = ET.fromstring(str(response))
    version = root.find(f".//{{{ns}}}ios-xe-version")
    boot_time = root.find(f".//{{{ns}}}boot-time")
    return {
        "version": version.text if version is not None else "N/A",
        "boot_time": boot_time.text if boot_time is not None else "N/A",
    }

def edit_config_description(conn, interface, description):
    """Edit interface description via NETCONF edit-config"""
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
    """List supported YANG models"""
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

    with manager.connect(**DEVICE) as conn:
        print("  ✅ NETCONF session established\n")

        # 1. Hostname
        print("📍 HOSTNAME")
        try:
            hostname = get_hostname(conn)
            print(f"  {hostname}")
        except Exception as e:
            print(f"  Error: {e}")

        # 2. Version info
        print("\n📦 SOFTWARE VERSION")
        try:
            ver = get_version(conn)
            print(f"  IOS XE Version : {ver['version']}")
            print(f"  Boot Time      : {ver['boot_time']}")
        except Exception as e:
            print(f"  Error: {e}")

        # 3. Interfaces
        print("\n📡 INTERFACES")
        try:
            response = get_interfaces(conn)
            interfaces = parse_interfaces(response)
            print(f"\n  {'NAME':<35} {'TYPE':<25} {'ENABLED'}")
            print(f"  {'─'*63}")
            for intf in interfaces:
                status = "✅ true" if intf["enabled"] == "true" else "❌ false"
                print(f"  {intf['name']:<35} {intf['type']:<25} {status}")
            print(f"\n  Total: {len(interfaces)} interfaces")
        except Exception as e:
            print(f"  Error: {e}")

        # 4. Edit config via NETCONF
        print("\n✏️  EDIT-CONFIG — Updating Loopback99 description via NETCONF")
        try:
            response = edit_config_description(
                conn,
                "Loopback99",
                "MANAGED-BY-NETCONF"
            )
            if "<ok/>" in str(response):
                print("  ✅ Loopback99 description updated successfully")
            else:
                print(f"  Response: {response}")
        except Exception as e:
            print(f"  Error: {e}")

        # 5. YANG capabilities (first 10)
        print("\n📚 SUPPORTED YANG MODELS (sample)")
        try:
            caps = get_capabilities(conn)
            for cap in caps[:10]:
                print(f"  • {cap}")
            print(f"  ... and {len(caps)-10} more models supported")
        except Exception as e:
            print(f"  Error: {e}")

    print(f"\n{'='*65}")
    print(f"  NETCONF QUERY COMPLETE")
    print(f"{'='*65}\n")
