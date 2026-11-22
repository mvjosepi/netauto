import math
from xml.sax.saxutils import escape


def short(intf):
    """GigabitEthernet1/0/1 -> Gi1/0/1"""
    for long, abbr in (("TenGigabitEthernet", "Te"), ("GigabitEthernet", "Gi"),
                       ("FastEthernet", "Fa"), ("Ethernet", "Eth"), ("Loopback", "Lo")):
        if intf.startswith(long):
            return abbr + intf[len(long):]
    return intf


def export_yed(g, path):
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
        '<key for="node" id="d0" yfiles.type="nodegraphics"/>',
        '<key for="edge" id="d1" yfiles.type="edgegraphics"/>',
        '<key for="node" id="d2" attr.name="ip" attr.type="string"/>',
        '<key for="node" id="d3" attr.name="platform" attr.type="string"/>',
        '<key for="node" id="d4" attr.name="boundary" attr.type="string"/>',
        '<graph id="G" edgedefault="undirected">',
    ]

    for n, d in g.nodes(data=True):
        segment = d.get("kind") == "segment"
        boundary = d.get("boundary") == "true"
        if segment:
            fill, line, shape, w, h = "#FFF2CC", "dashed", "ellipse", 110.0, 50.0
            label = "shared segment\n(inferred)"
        else:
            fill = "#E0E0E0" if boundary else "#CCE5FF"
            line = "dashed" if boundary else "line"
            shape, w, h = "roundrectangle", 140.0, 50.0
            ip = d.get("ip", "")
            label = n + ("\n" + ip if ip else "")
        x, y = pos[n]
        out += [
            f'<node id="{ids[n]}">',
            f'<data key="d2">{escape(d.get("ip", ""))}</data>',
            f'<data key="d3">{escape(d.get("platform", ""))}</data>',
            f'<data key="d4">{escape(str(d.get("boundary", "false")))}</data>',
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

    out += ['</graph>', '</graphml>']
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
