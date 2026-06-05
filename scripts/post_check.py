from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
import yaml
import json
import os
import sys
import signal
from datetime import datetime

SNAPSHOT_DIR = "snapshots"

def timeout_handler(signum, frame):
    print("\n\n⛔ Timeout — check VPN and device reachability.")
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(60)

def load_commands(command_file):
    with open(command_file) as f:
        data = yaml.safe_load(f)
    return data

def run_commands(task, commands):
    results = {}
    for cmd in commands:
        r = task.run(
            task=netmiko_send_command,
            command_string=cmd
        )
        results[cmd] = r[0].result
    return results

def load_pre_snapshot(host, change_id):
    filename = f"{SNAPSHOT_DIR}/{change_id}_{host}_pre.json"
    if not os.path.exists(filename):
        return None
    with open(filename) as f:
        return json.load(f)

def save_snapshot(host, results, change_id):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    filename = f"{SNAPSHOT_DIR}/{change_id}_{host}_post.json"
    with open(filename, "w") as f:
        json.dump({
            "host": host,
            "phase": "post",
            "change_id": change_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": results
        }, f, indent=2)
    return filename

def filter_lines(lines, ignore_patterns):
    """Remove lines matching ignore patterns"""
    filtered = set()
    for line in lines:
        if any(pattern.lower() in line.lower() for pattern in ignore_patterns):
            continue
        filtered.add(line)
    return filtered

def compare_results(host, pre_data, post_results, ignore_patterns=None):
    """Compare pre and post results line by line"""
    if ignore_patterns is None:
        ignore_patterns = []

    issues = []
    matches = []

    for cmd, post_output in post_results.items():
        pre_output = pre_data["results"].get(cmd, "")

        pre_lines = filter_lines(pre_output.splitlines(), ignore_patterns)
        post_lines = filter_lines(post_output.splitlines(), ignore_patterns)

        missing = pre_lines - post_lines
        added = post_lines - pre_lines

        if missing or added:
            issues.append({
                "command": cmd,
                "missing": list(missing)[:5],
                "added": list(added)[:5]
            })
        else:
            matches.append(cmd)

    return matches, issues

def print_report(host, pre_data, matches, issues, change_id):
    print(f"\n┌{'─'*63}")
    print(f"│  DEVICE    : {host.upper()}")
    print(f"│  CHANGE ID : {change_id}")
    print(f"│  PRE TIME  : {pre_data['timestamp']}")
    print(f"│  POST TIME : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"│")

    if not issues:
        print(f"│  ✅ ALL CHECKS PASSED — {len(matches)} commands matched")
        print(f"│  🏆 LAB PASSED")
    else:
        print(f"│  ✅ PASSED : {len(matches)} commands")
        print(f"│  ⚠️  ISSUES : {len(issues)} commands with differences")
        print(f"│")
        for issue in issues:
            print(f"│  ⚠️  COMMAND: {issue['command']}")
            if issue["missing"]:
                print(f"│     MISSING LINES:")
                for line in issue["missing"]:
                    if line.strip():
                        print(f"│       \033[31m- {line}\033[0m")
            if issue["added"]:
                print(f"│     NEW LINES:")
                for line in issue["added"]:
                    if line.strip():
                        print(f"│       \033[32m+ {line}\033[0m")
        print(f"│")
        print(f"│  ❌ LAB FAILED — Review differences above")

    print(f"└{'─'*63}")

def save_report(host, change_id, matches, issues):
    """Save validation report to file"""
    filename = f"{SNAPSHOT_DIR}/{change_id}_{host}_report.txt"
    with open(filename, "w") as f:
        f.write(f"CHANGE VALIDATION REPORT\n")
        f.write(f"{'='*50}\n")
        f.write(f"Host      : {host}\n")
        f.write(f"Change ID : {change_id}\n")
        f.write(f"Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Result    : {'PASSED' if not issues else 'FAILED'}\n")
        f.write(f"{'='*50}\n\n")
        f.write(f"Passed commands ({len(matches)}):\n")
        for m in matches:
            f.write(f"  ✅ {m}\n")
        if issues:
            f.write(f"\nFailed commands ({len(issues)}):\n")
            for issue in issues:
                f.write(f"  ⚠️  {issue['command']}\n")
                for line in issue.get("missing", []):
                    if line.strip():
                        f.write(f"     - {line}\n")
                for line in issue.get("added", []):
                    if line.strip():
                        f.write(f"     + {line}\n")
    return filename

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("\nUsage: python scripts/post_check.py <command_file> <change_id>")
        print("Example: python scripts/post_check.py commands/upgrade.yml CHG001")
        sys.exit(1)

    command_file = sys.argv[1]
    change_id = sys.argv[2]

    cmd_data = load_commands(command_file)
    commands = cmd_data["commands"]
    description = cmd_data.get("description", "")

    print(f"\n{'='*65}")
    print(f"  POST-CHECK VALIDATION")
    print(f"  Change ID   : {change_id}")
    print(f"  Description : {description}")
    print(f"  Commands    : {len(commands)}")
    print(f"  Timestamp   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")

    nr = InitNornir(
        inventory={
            "plugin": "SimpleInventory",
            "options": {
                "host_file": "inventory/hosts.yml",
                "group_file": "inventory/groups.yml",
                "defaults_file": "inventory/defaults.yml",
            },
        },
        runner={
            "plugin": "threaded",
            "options": {"num_workers": 5}
        }
    )

    nr = nr.filter(filter_func=lambda h: h.name != "iosxrv")

    print(f"\n  Devices: {list(nr.inventory.hosts.keys())}")
    print(f"\n  Running {len(commands)} commands per device...\n")

    result = nr.run(
        task=run_commands,
        commands=commands
    )

    overall_passed = True

    for host, multi_result in result.items():
        post_results = multi_result[0].result

        # Save post snapshot
        save_snapshot(host, post_results, change_id)

        # Load pre snapshot
        pre_data = load_pre_snapshot(host, change_id)
        if not pre_data:
            print(f"  ❌ {host.upper()} — No pre-check snapshot found for {change_id}")
            print(f"     Run pre_check.py first!")
            continue

        # Compare
        ignore_patterns = cmd_data.get("ignore_patterns", [])
        matches, issues = compare_results(host, pre_data, post_results, ignore_patterns)

        # Print report
        print_report(host, pre_data, matches, issues, change_id)

        # Save report to file
        report_file = save_report(host, change_id, matches, issues)
        print(f"\n  💾 Report saved: {report_file}")

        if issues:
            overall_passed = False

    signal.alarm(0)

    print(f"\n{'='*65}")
    if overall_passed:
        print(f"  🏆 OVERALL RESULT : ALL DEVICES PASSED")
    else:
        print(f"  ❌ OVERALL RESULT : ISSUES DETECTED — Review report above")
    print(f"{'='*65}\n")
