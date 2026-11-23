import glob
import json
import sys

HIST = "topologies/history"


def load(path):
    """Read a snapshot -> (devices, links, failed).

    links: {key: (description, devices involved)}; failed: {device: reason} (v1.5.3+)."""
    with open(path) as f:
        d = json.load(f)
    nodes = {n["id"]: n for n in d["nodes"]}
    links = {}
    for l in d["links"]:
        u, v = l["source"], l["target"]
        seg_u = nodes[u].get("kind") == "segment"
        seg_v = nodes[v].get("kind") == "segment"
        if seg_u or seg_v:
            # Segment names (segment-1, segment-2...) can change between runs:
            # identify the link by the device port instead.
            dev = v if seg_u else u
            intf = l["src_intf"] or l["dst_intf"]
            links[f"{dev}:{intf}|shared-segment"] = (
                f"{dev} [{intf}] on a shared segment", {dev})
        else:
            a, b = sorted((u, v))  # src_intf belongs to the alphabetically first node
            key = f"{a}:{l['src_intf']}|{b}:{l['dst_intf']}"
            links[key] = (f"{a} [{l['src_intf']}] <-> [{l['dst_intf']}] {b}", {a, b})
    devices = {k: v for k, v in nodes.items() if v.get("kind") != "segment"}
    failed = d.get("graph", {}).get("failed", {}) or {}
    return devices, links, failed


def pick_files(argv):
    if len(argv) >= 3:
        return argv[1], argv[2]
    files = sorted(glob.glob(f"{HIST}/topology_*.json"))
    if len(files) < 2:
        sys.exit("Need at least 2 snapshots in topologies/history/ (run discovery twice).")
    return files[-2], files[-1]


if __name__ == "__main__":
    old_path, new_path = pick_files(sys.argv)
    old_nodes, old_links, old_failed = load(old_path)
    new_nodes, new_links, new_failed = load(new_path)
    uncertain = set(old_failed) | set(new_failed)

    print("\n🔄 Topology diff")
    print(f"  OLD: {old_path}\n  NEW: {new_path}\n")

    if not set(old_nodes) & set(new_nodes):
        print("⚠️  No devices in common: these snapshots look like different labs.")
        sys.exit(2)

    if uncertain:
        print("  ⚠️  Not collected (unreachable / no data):")
        for label, f in (("OLD", old_failed), ("NEW", new_failed)):
            if f:
                print(f"     {label}: " + ", ".join(f"{h} ({why})" for h, why in sorted(f.items())))
        print("     Changes that involve them are marked [uncertain].\n")

    def mark(devs):
        hit = sorted(devs & uncertain)
        return f"  [uncertain: {', '.join(hit)} not collected]" if hit else ""

    changes = 0
    for n in sorted(set(new_nodes) - set(old_nodes)):
        tag = "NEW UNKNOWN NEIGHBOR (boundary)" if new_nodes[n].get("boundary") == "true" else "NEW DEVICE"
        print(f"  ➕ {tag}: {n} {new_nodes[n].get('ip', '')}")
        changes += 1
    for n in sorted(set(old_nodes) - set(new_nodes)):
        tag = "UNKNOWN NEIGHBOR GONE" if old_nodes[n].get("boundary") == "true" else "DEVICE GONE"
        print(f"  ❌ {tag}: {n}")
        changes += 1
    for k in sorted(set(new_links) - set(old_links)):
        desc, devs = new_links[k]
        print(f"  ➕ NEW LINK:     {desc}{mark(devs)}")
        changes += 1
    for k in sorted(set(old_links) - set(new_links)):
        desc, devs = old_links[k]
        print(f"  ❌ MISSING LINK: {desc}{mark(devs)}")
        changes += 1

    if changes:
        print(f"\n  ⚠️  {changes} change(s)." + (
            " Check the not-collected devices above before trusting them." if uncertain else ""))
        sys.exit(1)
    print("  ✅ No topology changes" + (" (but some devices were not collected)" if uncertain else ""))
