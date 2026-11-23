import math
import re
from xml.sax.saxutils import escape

# Generic, original flat icons (SVG), embedded in the GraphML so the file stays
# self-contained. Set icons=False in export_yed() to fall back to plain shapes.
ICON_SIZE = 64.0

_ROUTER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
    '<circle cx="32" cy="32" r="30" fill="#1F6FB2" stroke="#124A7A" stroke-width="2"/>'
    '<g stroke="#FFFFFF" stroke-width="4" stroke-linecap="round">'
    '<line x1="32" y1="18" x2="32" y2="46"/><line x1="18" y1="32" x2="46" y2="32"/></g>'
    '<g fill="#FFFFFF">'
    '<polygon points="32,8 24,19 40,19"/><polygon points="32,56 24,45 40,45"/>'
    '<polygon points="8,32 19,24 19,40"/><polygon points="56,32 45,24 45,40"/></g>'
    '</svg>'
)

_SWITCH_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
    '<rect x="2" y="12" width="60" height="40" rx="8" fill="#2A7F62" stroke="#1A5640" stroke-width="2"/>'
    '<g stroke="#FFFFFF" stroke-width="4" stroke-linecap="round">'
    '<line x1="14" y1="25" x2="42" y2="25"/><line x1="22" y1="39" x2="50" y2="39"/></g>'
    '<g fill="#FFFFFF">'
    '<polygon points="52,25 41,17 41,33"/><polygon points="12,39 23,31 23,47"/></g>'
    '</svg>'
)

ICONS = {"router": ("1", _ROUTER_SVG), "switch": ("2", _SWITCH_SVG)}


def short(intf):
    """GigabitEthernet1/0/1 -> Gi1/0/1"""
    for long, abbr in (("TenGigabitEthernet", "Te"), ("GigabitEthernet", "Gi"),
                       ("FastEthernet", "Fa"), ("Ethernet", "Eth"), ("Loopback", "Lo")):
        if intf.startswith(long):
            return abbr + intf[len(long):]
    return intf


_SWITCH_NAME = re.compile(r"^(sw|switch)|[-_]sw\d*$", re.I)
_ROUTER_NAME = re.compile(r"^(r\d|rtr|router)|[-_](r\d+|rtr\d*)$", re.I)


def node_role(name, data):
    """'router' | 'switch' | None.

    Priority: explicit `role` attribute (e.g. from the inventory) > name hint.
    CDP/LLDP capabilities are NOT used: IOL/virtual switches advertise
    'Router Switch' (CDP) and 'B,R' (LLDP), so they cannot tell the two apart.
    Boundary nodes and segments get no icon.
    """
    if data.get("kind") == "segment" or data.get("boundary") == "true":
        return None
    role = str(data.get("role", "")).strip().lower()
    if role in ICONS:
        return role
    if _SWITCH_NAME.search(name):
        return "switch"
    if _ROUTER_NAME.search(name):
        return "router"
    return None


def export_yed(g, path, icons=True):
    """Write a yEd-native GraphML: node labels, edge labels, colors, initial layout."""
    nodes = list(g.nodes())
    radius = max(150, 60 * len(nodes))
    pos = {n: (radius * math.cos(2 * math.pi * i / max(len(nodes), 1)),
               radius * math.sin(2 * math.pi * i / max(len(nodes), 1)))
           for i, n in enumerate(nodes)}
    ids = {n: f"n{i}" for i, n in enumerate(nodes)}

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns" '
        'xmlns:y="http://www.yworks.com/xml/graphml">',
        '<key for="graphml" id="d5" yfiles.type="resources"/>',
        '<key for="node" id="d0" yfiles.type="nodegraphics"/>',
        '<key for="edge" id="d1" yfiles.type="edgegraphics"/>',
        '<key for="node" id="d2" attr.name="ip" attr.type="string"/>',
        '<key for="node" id="d3" attr.name="platform" attr.type="string"/>',
        '<key for="node" id="d4" attr.name="boundary" attr.type="string"/>',
        '<key for="node" id="d6" attr.name="role" attr.type="string"/>',
        '<graph id="G" edgedefault="undirected">',
    ]

    used_icons = set()
    for n, d in g.nodes(data=True):
        segment = d.get("kind") == "segment"
        boundary = d.get("boundary") == "true"
        role = node_role(n, d) if icons else None
        ip = d.get("ip", "")
        x, y = pos[n]
        head = [
            f'<node id="{ids[n]}">',
            f'<data key="d2">{escape(ip)}</data>',
            f'<data key="d3">{escape(d.get("platform", ""))}</data>',
            f'<data key="d4">{escape(str(d.get("boundary", "false")))}</data>',
            f'<data key="d6">{escape(role or str(d.get("role", "")))}</data>',
        ]
        if role:
            used_icons.add(role)
            rid = ICONS[role][0]
            label = n + ("\n" + ip if ip else "")
            out += head + [
                '<data key="d0"><y:SVGNode>',
                f'<y:Geometry x="{x:.1f}" y="{y:.1f}" width="{ICON_SIZE}" height="{ICON_SIZE}"/>',
                '<y:Fill color="#FFFFFF" transparent="true"/>',
                '<y:BorderStyle hasColor="false" type="line" width="1.0"/>',
                '<y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" '
                'fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" '
                'modelName="sandwich" modelPosition="s" textColor="#000000" visible="true">'
                f'{escape(label)}</y:NodeLabel>',
                '<y:SVGNodeProperties usingVisualBounds="true"/>',
                f'<y:SVGModel svgBoundsPolicy="0"><y:SVGContent refid="{rid}"/></y:SVGModel>',
                '</y:SVGNode></data>',
                '</node>',
            ]
            continue
        if segment:
            fill, line, shape, w, h = "#FFF2CC", "dashed", "ellipse", 110.0, 50.0
            label = "shared segment\n(inferred)"
        else:
            fill = "#E0E0E0" if boundary else "#CCE5FF"
            line = "dashed" if boundary else "line"
            shape, w, h = "roundrectangle", 140.0, 50.0
            label = n + ("\n" + ip if ip else "")
        out += head + [
            '<data key="d0"><y:ShapeNode>',
            f'<y:Geometry x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}"/>',
            f'<y:Fill color="{fill}" transparent="false"/>',
            f'<y:BorderStyle color="#000000" type="{line}" width="1.5"/>',
            f'<y:NodeLabel>{escape(label)}</y:NodeLabel>',
            f'<y:Shape type="{shape}"/>',
            '</y:ShapeNode></data>',
            '</node>',
        ]

    for i, (u, v, d) in enumerate(g.edges(data=True)):
        a, b = sorted((u, v))  # src_intf belongs to the alphabetically first node

        def end_label(node, intf):
            intf = short(intf)
            if not intf or g.nodes[node].get("kind") == "segment":
                return intf
            return f"{node} {intf}"

        parts = [end_label(a, d.get("src_intf", "")), end_label(b, d.get("dst_intf", ""))]
        label = escape(" — ".join(x for x in parts if x))
        out += [
            f'<edge id="e{i}" source="{ids[a]}" target="{ids[b]}">',
            '<data key="d1"><y:PolyLineEdge>',
            '<y:LineStyle color="#000000" type="line" width="1.5"/>',
            '<y:Arrows source="none" target="none"/>',
            f'<y:EdgeLabel>{label}</y:EdgeLabel>',
            '</y:PolyLineEdge></data>',
            '</edge>',
        ]

    out.append('</graph>')
    if used_icons:
        out.append('<data key="d5"><y:Resources>')
        for role in sorted(used_icons, key=lambda r: ICONS[r][0]):
            rid, svg = ICONS[role]
            out.append(f'<y:Resource id="{rid}">{escape(svg)}</y:Resource>')
        out.append('</y:Resources></data>')
    out.append('</graphml>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
