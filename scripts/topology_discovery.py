import re
import sys
import json
import os
import yaml
import networkx as nx
from datetime import datetime
from yed_export import export_yed

TOPO_DIR = "topologies"
SKIP = {"iosxrv"}  # ssh-dss not supported by Paramiko 4.x
IF_PREFIX = (("TenGigabitEthernet", "Te"), ("GigabitEthernet", "Gi"),
             ("FastEthernet", "Fa"), ("Ethernet", "Eth"), ("Loopback", "Lo"))
CMDS = (("cdp", "show cdp neighbors detail"), ("lldp", "show lldp neighbors detail"))


def norm_intf(name):
    """GigabitEthernet2 / Gi2 -> Gi2 ; Ethernet1/3 / Eth1/3 -> Eth1/3"""
    name = name.strip()
    for long, abbr in IF_PREFIX:
        if name.startswith(long):
            return abbr + name[len(long):]
    return re.sub(r"^Et(?=\d)", "Eth", name)


ROLES = {}  # host -> 'router' | 'switch', filled by load_inventory from data.role


def load_inventory(inv_dir="inventory"):
    with open(f"{inv_dir}/hosts.yml") as f:
        data = yaml.safe_load(f)
    ROLES.clear()
    for n, h in data.items():
        role = str((h.get("data") or {}).get("role", "")).strip().lower()
        if n not in SKIP and role in ("router", "switch"):
            ROLES[n] = role
    return {n: h["hostname"] for n, h in data.items() if n not in SKIP}


def parse_cdp_detail(output):
    links = []
    for block in re.split(r"-{10,}", output):
        dev = re.search(r"Device ID:\s*(\S+)", block)
        intf = re.search(
            r"Interface:\s*([^,\n]+),\s*Port ID \(outgoing port\):\s*(\S+)", block)
        if not dev or not intf:
            continue
        sysname = re.search(r"System Name:\s*(\S+)", block)
        ip = re.search(r"(?:IP address|IPv4 Address):\s*(\S+)", block)
        plat = re.search(r"Platform:\s*([^,\n]+)", block)
        name = sysname.group(1) if sysname else dev.group(1).split("(")[0]
        links.append({
            "proto": "cdp",
            "remote_name": name.split(".")[0],
            "remote_ip": ip.group(1) if ip else "",
            "platform": plat.group(1).strip() if plat else "",
            "local_intf": norm_intf(intf.group(1)),
            "remote_intf": norm_intf(intf.group(2)),
        })
    return links


def parse_lldp_detail(output):
    """UNVALIDATED against real devices: written from known IOS XE / NX-OS formats."""
    links = []
    blocks = []
    for chunk in re.split(r"-{10,}", output):
        # NX-OS prints entries back to back, each starting at 'Chassis id:'
        blocks += re.split(r"(?=^\s*Chassis id:)", chunk, flags=re.M) \
            if chunk.count("Chassis id:") > 1 else [chunk]
    for block in blocks:
        local = re.search(r"^\s*(?:Local Intf|Local Port id):\s*(\S+)", block, re.M)
        remote = re.search(r"^\s*Port id:\s*(\S+)", block, re.M)
        if not local or not remote:
            continue
        sysname = re.search(r"^\s*System Name:\s*(\S+)", block, re.M)
        chassis = re.search(r"^\s*Chassis id:\s*(\S+)", block, re.M)
        ip = re.search(r"(?:Management Address(?:es)?:\s*(?:\n\s*IP:)?|^\s*IP:)\s*(\d+\.\d+\.\d+\.\d+)",
                       block, re.M)
        name = sysname.group(1) if sysname else (chassis.group(1) if chassis else "unknown")
        links.append({
            "proto": "lldp",
            "remote_name": name.split(".")[0],
            "remote_ip": ip.group(1) if ip else "",
            "platform": "",
            "local_intf": norm_intf(local.group(1)),
            "remote_intf": norm_intf(remote.group(1)),
        })
    return links


def proto_status(output):
    if not output or not output.strip():
        return "empty"
    if "Invalid command" in output or "not enabled" in output.lower() or output.startswith("ERROR:"):
        return "unavailable"
    return "ok"


def resolve_neighbor(link, inventory):
    ip_to_name = {ip: n for n, ip in inventory.items()}
    if link["remote_ip"] in ip_to_name:
        return ip_to_name[link["remote_ip"]]
    if link["remote_name"] in inventory:
        return link["remote_name"]
    by_lower = {n.lower(): n for n in inventory}
    return by_lower.get(link["remote_name"].lower(), link["remote_name"])  # else boundary node


def build_graph(raw, inventory):
    g = nx.MultiGraph()
    g.graph["self_links_ignored"] = 0
    for host, ip in inventory.items():
        g.add_node(host, ip=ip, boundary="false", role=ROLES.get(host, ""))

    for host, protos in raw.items():
        if host not in inventory:
            continue
        parsed = {"cdp": [], "lldp": []}
        status = {}
        for proto, text in protos.items():
            status[proto] = proto_status(text)
            if status[proto] == "ok":
                parsed[proto] = (parse_cdp_detail if proto == "cdp"
                                 else parse_lldp_detail)(text)
        print(f"  {host:<10} cdp: {status.get('cdp', '-'):<12}"
              f"({len(parsed['cdp'])} entries)  lldp: {status.get('lldp', '-'):<12}"
              f"({len(parsed['lldp'])} entries)")

        for link in parsed["cdp"] + parsed["lldp"]:
            remote = resolve_neighbor(link, inventory)
            if remote == host:  # virtual-chassis artifact, not a real link
                g.graph["self_links_ignored"] += 1
                continue
            if remote not in g:
                g.add_node(remote, ip=link["remote_ip"],
                           platform=link["platform"], boundary="true")
            a, b = sorted([host, remote])
            src, dst = ((link["local_intf"], link["remote_intf"]) if host == a
                        else (link["remote_intf"], link["local_intf"]))
            key = f"{a}:{src}|{b}:{dst}"
            if g.has_edge(a, b, key):  # same link already seen (other end / other protocol)
                seen = g[a][b][key]["seen_by"].split(",")
                if link["proto"] not in seen:
                    g[a][b][key]["seen_by"] = ",".join(seen + [link["proto"]])
            else:
                g.add_edge(a, b, key=key, src_intf=src, dst_intf=dst,
                           seen_by=link["proto"])
    return g


def collapse_segments(g):
    """An interface that sees >1 neighbor sits on a shared (multi-access) segment.
    Replace those pairwise links with one inferred 'segment' node."""
    def ends(u, v, d):
        a, b = sorted((u, v))
        return (a, d["src_intf"]), (b, d["dst_intf"])

    count = {}
    for u, v, k, d in g.edges(keys=True, data=True):
        for end in ends(u, v, d):
            count[end] = count.get(end, 0) + 1
    shared = {e for e, n in count.items() if n > 1}

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    seg_edges = []
    for u, v, k, d in list(g.edges(keys=True, data=True)):
        e1, e2 = ends(u, v, d)
        if e1 in shared or e2 in shared:
            parent[find(e1)] = find(e2)
            seg_edges.append((u, v, k, e1, e2))
    for u, v, k, _, _ in seg_edges:
        g.remove_edge(u, v, key=k)

    groups = {}
    for _, _, _, e1, e2 in seg_edges:
        for end in (e1, e2):
            groups.setdefault(find(end), set()).add(end)
    for i, members in enumerate(sorted(groups.values(), key=sorted), 1):
        seg = f"segment-{i}"
        g.add_node(seg, kind="segment", boundary="false", ip="", platform="shared segment")
        for dev, intf in sorted(members):
            a, b = sorted((dev, seg))
            src, dst = (intf, "") if dev == a else ("", intf)
            g.add_edge(a, b, key=f"{a}:{src}|{b}:{dst}",
                       src_intf=src, dst_intf=dst, seen_by="inferred")
    return g


def save_outputs(g):
    hist = f"{TOPO_DIR}/history"
    os.makedirs(hist, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    data = nx.node_link_data(g, edges="links")
    graphml = f"{TOPO_DIR}/topology_latest.graphml"
    export_yed(g, graphml)
    with open(f"{TOPO_DIR}/topology_latest.json", "w") as f:
        json.dump(data, f, indent=2)
    snap = f"{hist}/topology_{ts}.json"
    with open(snap, "w") as f:
        json.dump(data, f, indent=2)
    return graphml, snap


CONN_ERRORS = ("NetmikoTimeoutException", "NetmikoAuthenticationException",
               "ConnectionException", "SSHException")


def _explain(e):
    """(short reason, is_connection_error). Nornir wraps the real exception in a subtask error."""
    inner = None
    res = getattr(e, "result", None)
    if res is not None:
        for item in (res if isinstance(res, list) else [res]):
            if getattr(item, "exception", None):
                inner = item.exception
                break
    err = inner or e
    name = type(err).__name__
    text = " ".join(str(err).split())[:100]
    # OSError covers refused / unreachable / DNS failures (Telnet raises these directly)
    return f"{name}: {text}", name in CONN_ERRORS or isinstance(err, OSError)


def collect_live(inventory, inv_dir="inventory", workers=5, timeout=20):
    from nornir import InitNornir
    from nornir.core.inventory import ConnectionOptions
    from nornir_netmiko.tasks import netmiko_send_command
    import logging
    logging.getLogger("nornir").setLevel(logging.CRITICAL)  # failures are reported by this script

    def get_neighbors(task):
        out = {}
        for proto, cmd in CMDS:
            try:
                out[proto] = task.run(task=netmiko_send_command, command_string=cmd,
                                      read_timeout=timeout)[0].result
            except Exception as e:
                reason, conn = _explain(e)
                out[proto] = f"ERROR: {reason}"
                if conn:  # unreachable / bad credentials: do not try the next command
                    for p, _ in CMDS:
                        out.setdefault(p, f"ERROR: {reason}")
                    break
        return out

    nr = InitNornir(
        inventory={"plugin": "SimpleInventory", "options": {
            "host_file": f"{inv_dir}/hosts.yml",
            "group_file": f"{inv_dir}/groups.yml",
            "defaults_file": f"{inv_dir}/defaults.yml"}},
        runner={"plugin": "threaded", "options": {"num_workers": workers}},
    )
    nr = nr.filter(filter_func=lambda h: h.name in inventory)
    for h in nr.inventory.hosts.values():  # connection timeouts, keeping any extras already set
        extras = dict(h.get_connection_parameters("netmiko").extras or {})
        for k in ("conn_timeout", "auth_timeout", "banner_timeout"):
            extras.setdefault(k, timeout)
        opts = h.connection_options.get("netmiko")
        if opts is None:
            opts = ConnectionOptions(extras={})
            h.connection_options["netmiko"] = opts
        opts.extras = extras
    res = nr.run(task=get_neighbors)
    raw = {}
    for host, r in res.items():
        if r[0].failed:
            raw[host] = {p: f"ERROR: {type(r[0].exception).__name__}: {r[0].exception}"[:140]
                         for p, _ in CMDS}
        else:
            raw[host] = r[0].result
    return raw


def collect_offline(inventory, sdir):
    raw = {}
    for host in inventory:
        for proto, _ in CMDS:
            path = f"{sdir}/{host}_{proto}.txt"
            if os.path.exists(path):
                raw.setdefault(host, {})[proto] = open(path).read()
    return raw


def _opt(flag, default, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


def collection_failures(raw, inventory):
    """host -> reason, for devices that returned nothing usable (unreachable, auth, no data)."""
    failed = {}
    for host in inventory:
        protos = raw.get(host)
        if not protos:
            failed[host] = "no data collected"
            continue
        errs = [v for v in protos.values() if isinstance(v, str) and v.startswith("ERROR:")]
        if len(errs) == len(protos):
            failed[host] = errs[0][len("ERROR:"):].strip()
    return failed


if __name__ == "__main__":
    offline = "--offline" in sys.argv
    sdir = _opt("--samples", "samples")
    inv_dir = _opt("--inventory", "inventory")
    workers = _opt("--workers", 5, int)
    timeout = _opt("--timeout", 20, int)
    inventory = load_inventory(inv_dir)
    print(f"\n🔍 Topology discovery ({'offline: ' + sdir if offline else 'live'})\n")
    raw = (collect_offline(inventory, sdir) if offline
           else collect_live(inventory, inv_dir, workers, timeout))
    g = collapse_segments(build_graph(raw, inventory))
    failed = collection_failures(raw, inventory)
    g.graph["failed"] = failed
    for host in failed:
        if host in g:
            g.nodes[host]["collected"] = "false"
    graphml, snap = save_outputs(g)
    boundary = [n for n, d in g.nodes(data=True) if d.get("boundary") == "true"]
    print(f"\n  Nodes: {g.number_of_nodes()}  Links: {g.number_of_edges()}")
    print(f"  Boundary nodes: {boundary or 'none'}")
    print(f"  Self-links ignored: {g.graph['self_links_ignored']}")
    for a, b, d in g.edges(data=True):
        print(f"  {a} [{d['src_intf']}] <-> [{d['dst_intf']}] {b}   ({d['seen_by']})")
    if failed:
        print(f"\n  ⚠️  Collection FAILED for {len(failed)} device(s):")
        for host, why in sorted(failed.items()):
            print(f"     {host}: {why}")
        print("     Links seen only by these devices are missing from the map.")
    print(f"  💾 {graphml}\n  💾 {snap}")
    if failed and not offline:
        sys.exit(3)  # partial collection (0 = ok)
