from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
import os
import json
import glob
from datetime import datetime
import signal
import sys

REPORT_DIR = "reports"
BACKUP_DIR = "backups"
SNAPSHOT_DIR = "snapshots"

def timeout_handler(signum, frame):
    print("\n\n⛔ Timeout — check VPN and device reachability.")
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(120)

def get_device_data(task):
    results = {}

    # Version
    r = task.run(task=netmiko_send_command, command_string="show version")
    results["version"] = r[0].result

    # Interfaces
    if "nxos" in str(task.host.groups):
        r = task.run(task=netmiko_send_command, command_string="show interface brief")
    else:
        r = task.run(task=netmiko_send_command, command_string="show ip interface brief")
    results["interfaces"] = r[0].result

    # Routing
    r = task.run(task=netmiko_send_command, command_string="show ip route summary")
    results["routes"] = r[0].result

    # CDP
    r = task.run(task=netmiko_send_command, command_string="show cdp neighbors")
    results["cdp"] = r[0].result

    return results

def parse_version_iosxe(output):
    info = {"hostname": "N/A", "version": "N/A", "uptime": "N/A", "serial": "N/A", "platform": "IOS XE"}
    for line in output.splitlines():
        if "Version" in line and "IOS XE" in line:
            info["version"] = line.strip()
        if "uptime is" in line:
            info["uptime"] = line.strip()
        if "Processor Board ID" in line:
            info["serial"] = line.split()[-1]
        if "cisco C8000" in line:
            info["platform"] = line.strip()
    return info

def parse_version_nxos(output):
    info = {"hostname": "N/A", "version": "N/A", "uptime": "N/A", "serial": "N/A", "platform": "NX-OS"}
    for line in output.splitlines():
        if "NXOS:" in line:
            info["version"] = line.strip()
        if "Kernel uptime" in line:
            info["uptime"] = line.strip()
        if "Processor Board ID" in line:
            info["serial"] = line.split()[-1]
        if "cisco Nexus" in line:
            info["platform"] = line.strip()
    return info

def parse_interfaces_iosxe(output):
    up, down = [], []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0] != "Interface":
            intf, ip, status, proto = parts[0], parts[1], parts[4], parts[5]
            if status == "up" and proto == "up":
                up.append({"name": intf, "ip": ip})
            else:
                down.append({"name": intf, "ip": ip, "status": status})
    return up, down

def parse_interfaces_nxos(output):
    up, down = [], []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3 and (parts[0].startswith("Eth") or parts[0].startswith("mgmt")):
            intf = parts[0]
            status = parts[2] if parts[0].startswith("mgmt") else parts[4]
            if status == "up":
                up.append({"name": intf, "ip": ""})
            else:
                down.append({"name": intf, "ip": "", "status": status})
    return up, down

def parse_routes(output, is_nxos):
    lines = []
    for line in output.splitlines():
        if line.strip() and not line.startswith("IP") and not line.startswith("Route"):
            lines.append(line.strip())
    return lines[:8]

def get_last_backup(host):
    files = sorted(glob.glob(f"{BACKUP_DIR}/{host}_*.cfg"))
    if files:
        basename = os.path.basename(files[-1])
        # Format: hostname_YYYYMMDD_HHMMSS.cfg
        parts = basename.replace(".cfg", "").split("_")
        try:
            date_part = parts[-2]
            time_part = parts[-1]
            dt = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S"), files[-1]
        except:
            return basename, files[-1]
    return "No backup found", ""

def get_change_history(host):
    reports = sorted(glob.glob(f"{SNAPSHOT_DIR}/*_{host}_report.txt"), reverse=True)
    history = []
    for r in reports[:5]:
        change_id = os.path.basename(r).split("_")[0]
        with open(r) as f:
            content = f.read()
            result = "PASSED" if "PASSED" in content else "FAILED"
            timestamp = ""
            for line in content.splitlines():
                if "Timestamp" in line:
                    # Handle HH:MM:SS format correctly
                    parts = line.split(":", 1)
                    timestamp = parts[1].strip() if len(parts) > 1 else ""
                    break
            history.append({
                "change_id": change_id,
                "result": result,
                "timestamp": timestamp
            })
    return history

def generate_html(all_data, nr, timestamp):
    devices_html = ""

    for host, data in all_data.items():
        is_nxos = "nxos" in str(nr.inventory.hosts[host].groups)

        if is_nxos:
            ver_info = parse_version_nxos(data["version"])
            up, down = parse_interfaces_nxos(data["interfaces"])
        else:
            ver_info = parse_version_iosxe(data["version"])
            up, down = parse_interfaces_iosxe(data["interfaces"])

        routes = parse_routes(data["routes"], is_nxos)
        last_backup, _ = get_last_backup(host)
        change_history = get_change_history(host)

        # Interface rows
        intf_rows = ""
        for i in up:
            intf_rows += f"""
            <tr>
                <td>{i['name']}</td>
                <td>{i.get('ip', '')}</td>
                <td><span class="badge badge-up">UP</span></td>
            </tr>"""
        for i in down[:5]:
            intf_rows += f"""
            <tr>
                <td>{i['name']}</td>
                <td>{i.get('ip', '')}</td>
                <td><span class="badge badge-down">DOWN</span></td>
            </tr>"""
        if len(down) > 5:
            intf_rows += f"""
            <tr>
                <td colspan="3" style="color:#999;font-style:italic;">
                    ... and {len(down)-5} more down interfaces
                </td>
            </tr>"""

        # Route rows
        route_rows = ""
        for r in routes:
            route_rows += f"<tr><td>{r}</td></tr>"

        # Change history rows
        history_rows = ""
        if change_history:
            for ch in change_history:
                badge_class = "badge-up" if ch["result"] == "PASSED" else "badge-down"
                history_rows += f"""
                <tr>
                    <td>{ch['change_id']}</td>
                    <td>{ch['timestamp']}</td>
                    <td><span class="badge {badge_class}">{ch['result']}</span></td>
                </tr>"""
        else:
            history_rows = "<tr><td colspan='3' style='color:#999'>No change history found</td></tr>"

        devices_html += f"""
        <div class="device-card">
            <div class="device-header">
                <div class="device-title">{host.upper()}</div>
                <div class="device-platform">{ver_info['platform']}</div>
            </div>

            <div class="device-grid">
                <!-- Device Info -->
                <div class="section">
                    <div class="section-title">📍 Device Info</div>
                    <table class="info-table">
                        <tr><td class="label">Version</td><td>{ver_info['version']}</td></tr>
                        <tr><td class="label">Uptime</td><td>{ver_info['uptime']}</td></tr>
                        <tr><td class="label">Serial</td><td>{ver_info['serial']}</td></tr>
                        <tr><td class="label">Last Backup</td><td>{last_backup}</td></tr>
                    </table>
                </div>

                <!-- Interface Summary -->
                <div class="section">
                    <div class="section-title">📡 Interfaces</div>
                    <div class="intf-summary">
                        <div class="intf-count up-count">
                            <div class="count-number">{len(up)}</div>
                            <div class="count-label">UP</div>
                        </div>
                        <div class="intf-count down-count">
                            <div class="count-number">{len(down)}</div>
                            <div class="count-label">DOWN</div>
                        </div>
                    </div>
                    <table class="data-table">
                        <thead>
                            <tr><th>Interface</th><th>IP</th><th>Status</th></tr>
                        </thead>
                        <tbody>{intf_rows}</tbody>
                    </table>
                </div>

                <!-- Routing Summary -->
                <div class="section">
                    <div class="section-title">🗺️ Routing Summary</div>
                    <table class="data-table">
                        <tbody>{route_rows}</tbody>
                    </table>
                </div>

                <!-- Change History -->
                <div class="section">
                    <div class="section-title">🔄 Change History</div>
                    <table class="data-table">
                        <thead>
                            <tr><th>Change ID</th><th>Timestamp</th><th>Result</th></tr>
                        </thead>
                        <tbody>{history_rows}</tbody>
                    </table>
                </div>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetAuto Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f4f6f9;
            color: #2d3748;
            font-size: 14px;
        }}

        .header {{
            background: #1a56db;
            color: white;
            padding: 20px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}

        .header-title {{
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        .header-sub {{
            font-size: 13px;
            opacity: 0.85;
            margin-top: 4px;
        }}

        .header-meta {{
            text-align: right;
            font-size: 13px;
            opacity: 0.85;
        }}

        .summary-bar {{
            background: white;
            padding: 16px 32px;
            display: flex;
            gap: 32px;
            border-bottom: 1px solid #e2e8f0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        .summary-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: #4a5568;
        }}

        .summary-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }}

        .dot-blue {{ background: #1a56db; }}
        .dot-green {{ background: #38a169; }}
        .dot-red {{ background: #e53e3e; }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px 32px;
        }}

        .device-card {{
            background: white;
            border-radius: 10px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            margin-bottom: 24px;
            overflow: hidden;
            border: 1px solid #e2e8f0;
        }}

        .device-header {{
            background: #1a56db;
            color: white;
            padding: 14px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .device-title {{
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 1px;
        }}

        .device-platform {{
            font-size: 12px;
            background: rgba(255,255,255,0.2);
            padding: 3px 10px;
            border-radius: 20px;
        }}

        .device-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0;
        }}

        .section {{
            padding: 16px 20px;
            border-right: 1px solid #e2e8f0;
            border-bottom: 1px solid #e2e8f0;
        }}

        .section:nth-child(even) {{
            border-right: none;
        }}

        .section-title {{
            font-size: 13px;
            font-weight: 600;
            color: #1a56db;
            margin-bottom: 12px;
            padding-bottom: 6px;
            border-bottom: 1px solid #e2e8f0;
        }}

        .info-table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .info-table td {{
            padding: 5px 0;
            vertical-align: top;
        }}

        .info-table .label {{
            color: #718096;
            width: 100px;
            font-size: 12px;
            font-weight: 500;
        }}

        .intf-summary {{
            display: flex;
            gap: 16px;
            margin-bottom: 12px;
        }}

        .intf-count {{
            flex: 1;
            text-align: center;
            padding: 10px;
            border-radius: 8px;
        }}

        .up-count {{
            background: #f0fff4;
            border: 1px solid #9ae6b4;
        }}

        .down-count {{
            background: #fff5f5;
            border: 1px solid #feb2b2;
        }}

        .count-number {{
            font-size: 28px;
            font-weight: 700;
        }}

        .up-count .count-number {{ color: #38a169; }}
        .down-count .count-number {{ color: #e53e3e; }}

        .count-label {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #718096;
        }}

        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}

        .data-table th {{
            background: #f7fafc;
            color: #4a5568;
            font-weight: 600;
            padding: 6px 8px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .data-table td {{
            padding: 5px 8px;
            border-bottom: 1px solid #f0f0f0;
            color: #4a5568;
        }}

        .data-table tr:last-child td {{
            border-bottom: none;
        }}

        .data-table tr:hover td {{
            background: #f7fafc;
        }}

        .badge {{
            padding: 2px 8px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .badge-up {{
            background: #f0fff4;
            color: #276749;
            border: 1px solid #9ae6b4;
        }}

        .badge-down {{
            background: #fff5f5;
            color: #c53030;
            border: 1px solid #feb2b2;
        }}

        .footer {{
            text-align: center;
            padding: 20px;
            color: #a0aec0;
            font-size: 12px;
            border-top: 1px solid #e2e8f0;
            margin-top: 8px;
        }}

        @media (max-width: 768px) {{
            .device-grid {{ grid-template-columns: 1fr; }}
            .section {{ border-right: none; }}
        }}
    </style>
</head>
<body>

<div class="header">
    <div>
        <div class="header-title">🌐 NetAuto Dashboard</div>
        <div class="header-sub">Multi-Vendor Network Automation — Pure Python</div>
    </div>
    <div class="header-meta">
        Generated: {timestamp}<br>
        Devices: {len(all_data)}
    </div>
</div>

<div class="summary-bar">
    <div class="summary-item">
        <div class="summary-dot dot-blue"></div>
        <span>{len(all_data)} devices monitored</span>
    </div>
    <div class="summary-item">
        <div class="summary-dot dot-green"></div>
        <span>IOS XE 17.12 + NX-OS 9.3</span>
    </div>
    <div class="summary-item">
        <div class="summary-dot dot-blue"></div>
        <span>Cisco DevNet Sandbox</span>
    </div>
</div>

<div class="container">
    {devices_html}
</div>

<div class="footer">
    NetAuto v1.4.0 — github.com/mvjosepi/netauto — Generated {timestamp}
</div>

</body>
</html>"""

if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*65}")
    print(f"  NETAUTO DASHBOARD GENERATOR")
    print(f"  {timestamp}")
    print(f"{'='*65}\n")

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

    print(f"  Devices  : {list(nr.inventory.hosts.keys())}")
    print(f"  Fetching data from all devices...\n")

    result = nr.run(task=get_device_data)

    all_data = {}
    for host, multi_result in result.items():
        if not multi_result[0].exception:
            all_data[host] = multi_result[0].result
            print(f"  ✅ {host.upper()} data collected")
        else:
            print(f"  ❌ {host.upper()} failed: {multi_result[0].exception}")

    os.makedirs(REPORT_DIR, exist_ok=True)
    filename = f"{REPORT_DIR}/dashboard.html"

    html = generate_html(all_data, nr, timestamp)

    with open(filename, "w") as f:
        f.write(html)

    signal.alarm(0)

    print(f"\n{'='*65}")
    print(f"  ✅ Dashboard generated → {filename}")
    print(f"  Open in browser: file://$(pwd)/{filename}")
    print(f"{'='*65}\n")
