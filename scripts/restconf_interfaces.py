import requests
import json
import urllib3
from datetime import datetime

# Suppress SSL warnings (self-signed cert on DevNet)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Device connection details
DEVICE = {
    "host": "10.10.20.48",
    "username": "developer",
    "password": "C1sco12345",
}

HEADERS = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}

BASE_URL = f"https://{DEVICE['host']}/restconf/data"

def get(endpoint):
    url = f"{BASE_URL}/{endpoint}"
    response = requests.get(
        url,
        auth=(DEVICE["username"], DEVICE["password"]),
        headers=HEADERS,
        verify=False
    )
    response.raise_for_status()
    return response.json()

def patch(endpoint, payload):
    url = f"{BASE_URL}/{endpoint}"
    response = requests.patch(
        url,
        auth=(DEVICE["username"], DEVICE["password"]),
        headers=HEADERS,
        json=payload,
        verify=False
    )
    return response.status_code, response.text

def print_interfaces(data):
    interfaces = data.get(
        "ietf-interfaces:interfaces", {}
    ).get("interface", [])

    print(f"\n{'─'*65}")
    print(f"  {'NAME':<35} {'TYPE':<20} {'STATUS'}")
    print(f"{'─'*65}")

    for intf in interfaces:
        name = intf.get("name", "N/A")
        intf_type = intf.get("type", "N/A").split(":")[-1]
        enabled = intf.get("enabled", False)
        status = "✅ enabled" if enabled else "❌ disabled"
        print(f"  {name:<35} {intf_type:<20} {status}")

    print(f"{'─'*65}")
    print(f"  Total: {len(interfaces)} interfaces")

def print_interface_detail(data):
    intf = data.get("ietf-interfaces:interface", [{}])
    if isinstance(intf, list):
        intf = intf[0]

    print(f"\n  Name        : {intf.get('name', 'N/A')}")
    print(f"  Description : {intf.get('description', 'N/A')}")
    print(f"  Type        : {intf.get('type', 'N/A').split(':')[-1]}")
    print(f"  Enabled     : {intf.get('enabled', 'N/A')}")

    ipv4 = intf.get("ietf-ip:ipv4", {})
    addresses = ipv4.get("address", [])
    if addresses:
        for addr in addresses:
            print(f"  IPv4        : {addr.get('ip')}/{addr.get('prefix-length')}")
    else:
        print(f"  IPv4        : not configured")

def print_routes(data):
    routes = data.get(
        "Cisco-IOS-XE-native:route", {}
    ).get("ip-route-interface-forwarding-list", [])

    print(f"\n{'─'*65}")
    print(f"  {'PREFIX':<20} {'MASK':<20} {'NEXT-HOP'}")
    print(f"{'─'*65}")

    for route in routes:
        prefix = route.get("prefix", "N/A")
        mask = route.get("mask", "N/A")
        fwd_list = route.get("fwd-list", [])
        for fwd in fwd_list:
            nexthops = fwd.get("interface-next-hop", [])
            for nh in nexthops:
                ip = nh.get("ip-address", "N/A")
                print(f"  {prefix:<20} {mask:<20} {ip}")

    print(f"{'─'*65}")
    print(f"  Total: {len(routes)} static routes")

if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*65}")
    print(f"  RESTCONF QUERY — CAT8Kv")
    print(f"  {timestamp}")
    print(f"{'='*65}")

    # 1. Hostname
    print("\n📍 HOSTNAME")
    try:
        data = get("Cisco-IOS-XE-native:native/hostname")
        print(f"  {data.get('Cisco-IOS-XE-native:hostname', 'N/A')}")
    except Exception as e:
        print(f"  Error: {e}")

    # 2. All interfaces
    print("\n📡 INTERFACES")
    try:
        data = get("ietf-interfaces:interfaces")
        print_interfaces(data)
    except Exception as e:
        print(f"  Error: {e}")

    # 3. GigabitEthernet1 detail
    print("\n🔍 GIGABITETHERNET1 DETAIL")
    try:
        data = get("ietf-interfaces:interfaces/interface=GigabitEthernet1")
        print_interface_detail(data)
    except Exception as e:
        print(f"  Error: {e}")

    # 4. Routing table
    print("\n🗺️  STATIC ROUTES")
    try:
        data = get("Cisco-IOS-XE-native:native/ip/route")
        print_routes(data)
    except Exception as e:
        print(f"  Error: {e}")

    # 5. PATCH — update Loopback99 description via RESTCONF
    print("\n✏️  PATCH — Updating Loopback99 description via RESTCONF API")
    try:
        payload = {
            "ietf-interfaces:interface": {
                "name": "Loopback99",
                "description": "MANAGED-BY-RESTCONF",
                "type": "iana-if-type:softwareLoopback",
                "enabled": True
            }
        }
        status, response = patch(
            "ietf-interfaces:interfaces/interface=Loopback99",
            payload
        )
        if status == 204:
            print(f"  ✅ Loopback99 description updated successfully (HTTP {status})")
        else:
            print(f"  ⚠️  HTTP {status}: {response}")
    except Exception as e:
        print(f"  Error: {e}")

    print(f"\n{'='*65}")
    print(f"  RESTCONF QUERY COMPLETE")
    print(f"{'='*65}\n")
