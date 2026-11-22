import re
import sys
import json
import os
import yaml
import networkx as nx
from datetime import datetime

TOPO_DIR = "topologies"
SAMPLES_DIR = "samples"


def load_inventory():
    """Read hosts.yml: returns {name: ip}"""
    with open("inventory/hosts.yml") as f:
        data = yaml.safe_load(f)
    return {name: h["hostname"] for name, h in data.items()}


def parse_cdp_detail(output):
    """Parse 'show cdp neighbors detail' (IOS XE / NX-OS) into a list of links."""
    links = []
    for block in re.split(r"-{10,}", output):
        dev = re.search(r"Device ID:\s*(\S+)", block)
        if not dev:
            continue
        sysname = re.search(r"System Name:\s*(\S+)", block)
        ip = re.search(r"(?:IP address|IPv4 Address):\s*(\S+)", block)
        plat = re.search(r"Platform:\s*([^,\n]+)", block)
        intf = re.search(
            r"Interface:\s*([^,\n]+),\s*Port ID \(outgoing port\):\s*(\S+)", block
        )
        if not intf:
            continue
        # NX-OS Device ID carries the serial, e.g. n9k(9GFWC97W2TQ): prefer System Name
        name = sysname.group(1) if sysname else dev.group(1).split("(")[0]
        links.append({
            "remote_name": name.split(".")[0],
            "remote_ip": ip.group(1) if ip else "",
            "platform": plat.group(1).strip() if plat else "",
            "local_intf": intf.group(1).strip(),
            "remote_intf": intf.group(2).strip(),
        })
    return links


def resolve_neighbor(link, inventory):
    """Match a neighbor to an inventory host by mgmt IP first, then by name."""
    ip_to_name = {ip: name for name, ip in inventory.items()}
    if link["remote_ip"] in ip_to_name:
        return ip_to_name[link["remote_ip"]], False
    for name in inventory:
        if name == link["remote_name"]:
            return name, False
    return link["remote_name"], True  # boundary node


def build_graph(raw_by_host, inventory):
    g = nx.Graph()
    for host, ip in inventory.items():
        g.add_node(host, ip=ip, boundary="false")
    for host, output in raw_by_host.items():
        for link in parse_cdp_detail(output):
            remote, boundary = resolve_neighbor(link, inventory)
            if remote not in g:
                g.add_node(remote, ip=link["remote_ip"],
                           platform=link["platform"], boundary="true")
            a, b = sorted([host, remote])
            if host == a:
                src_i, dst_i = link["local_intf"], link["remote_intf"]
            else:
                src_i, dst_i = link["remote_intf"], link["local_intf"]
            g.add_edge(a, b, src_intf=src_i, dst_intf=dst_i)
    return g


def save_outputs(g):
    os.makedirs(TOPO_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    graphml = f"{TOPO_DIR}/topology_{ts}.graphml"
    snap = f"{TOPO_DIR}/topology_{ts}.json"
    nx.write_graphml(g, graphml)
    with open(snap, "w") as f:
        json.dump(nx.node_link_data(g, edges="links"), f, indent=2)
    return graphml, snap


def collect_live(inventory):
    from nornir import InitNornir
    from nornir_netmiko.tasks import netmiko_send_command
    nr = InitNornir(
        inventory={"plugin": "SimpleInventory", "options": {
            "host_file": "inventory/hosts.yml",
            "group_file": "inventory/groups.yml",
            "defaults_file": "inventory/defaults.yml"}},
        runner={"plugin": "threaded", "options": {"num_workers": 5}},
    )
    nr = nr.filter(filter_func=lambda h: h.name in inventory)
    res = nr.run(task=netmiko_send_command,
                 command_string="show cdp neighbors detail")
    return {h: r[0].result for h, r in res.items() if not r[0].failed}


def collect_offline():
    raw = {}
    for fn in os.listdir(SAMPLES_DIR):
        if fn.endswith("_cdp.txt"):
            with open(f"{SAMPLES_DIR}/{fn}") as f:
                raw[fn.replace("_cdp.txt", "")] = f.read()
    return raw


if __name__ == "__main__":
    offline = "--offline" in sys.argv
    inventory = load_inventory()
    print(f"\n🔍 Topology discovery ({'offline samples' if offline else 'live'})")
    raw = collect_offline() if offline else collect_live(inventory)
    g = build_graph(raw, inventory)
    graphml, snap = save_outputs(g)
    boundary = [n for n, d in g.nodes(data=True) if d.get("boundary") == "true"]
    print(f"  Nodes: {g.number_of_nodes()}  Links: {g.number_of_edges()}")
    print(f"  Boundary nodes: {boundary or 'none'}")
    for a, b, d in g.edges(data=True):
        print(f"  {a} [{d['src_intf']}] <-> [{d['dst_intf']}] {b}")
    print(f"  💾 {graphml}\n  💾 {snap}")
