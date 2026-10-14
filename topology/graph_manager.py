"""
Network topology definitions, presets, and custom graph construction helpers.
"""

import networkx as nx
import json


# ── Presets ───────────────────────────────────────────────────────────────────

def default_topology():
    """Classic 4-router diamond network."""
    g = nx.Graph()
    g.add_nodes_from(["R0", "R1", "R2", "R3"])
    g.add_edge("R0", "R1", cost=1, bandwidth="2Mb", delay="10ms", queue="DropTail")
    g.add_edge("R1", "R3", cost=1, bandwidth="2Mb", delay="10ms", queue="DropTail")
    g.add_edge("R0", "R2", cost=2, bandwidth="1Mb", delay="20ms", queue="DropTail")
    g.add_edge("R2", "R3", cost=2, bandwidth="1Mb", delay="20ms", queue="DropTail")
    g.add_edge("R1", "R2", cost=1, bandwidth="1Mb", delay="15ms", queue="DropTail")
    return g


def mesh_6node_topology():
    """
    6-router mesh network.
    Highlights path divergence between hop-count (RIP) and cost/bandwidth (OSPF).
    """
    g = nx.Graph()
    g.add_nodes_from(["R0", "R1", "R2", "R3", "R4", "R5"])
    edges = [
        ("R0", "R1", 1, "2Mb", "10ms"),
        ("R1", "R3", 1, "2Mb", "10ms"),
        ("R3", "R5", 1, "2Mb", "10ms"),
        ("R0", "R2", 5, "500Kb", "30ms"),
        ("R2", "R5", 5, "500Kb", "30ms"),
        ("R1", "R4", 2, "1Mb", "15ms"),
        ("R4", "R5", 2, "1Mb", "15ms"),
        ("R2", "R4", 1, "1Mb", "15ms"),
    ]
    for u, v, cost, bw, d in edges:
        g.add_edge(u, v, cost=cost, bandwidth=bw, delay=d, queue="DropTail")
    return g


def backbone_8node_topology():
    """
    8-router campus backbone network.
    Large network designed to test scalability and trigger OSPF recommendation.
    """
    g = nx.Graph()
    g.add_nodes_from([f"R{i}" for i in range(8)])
    edges = [
        ("R0", "R1", 1, "5Mb", "5ms"),
        ("R1", "R2", 1, "5Mb", "5ms"),
        ("R2", "R3", 1, "5Mb", "5ms"),
        ("R3", "R4", 1, "5Mb", "5ms"),
        ("R4", "R5", 1, "5Mb", "5ms"),
        ("R5", "R6", 1, "5Mb", "5ms"),
        ("R6", "R7", 1, "5Mb", "5ms"),
        ("R7", "R0", 1, "5Mb", "5ms"),
        ("R1", "R6", 3, "2Mb", "15ms"),
        ("R2", "R5", 2, "2Mb", "10ms"),
        ("R0", "R4", 4, "1Mb", "25ms"),
    ]
    for u, v, cost, bw, d in edges:
        g.add_edge(u, v, cost=cost, bandwidth=bw, delay=d, queue="DropTail")
    return g


def create_custom_topology(nodes, edges):
    """
    Build a NetworkX Graph from lists of node names and edge dictionaries.

    edges: list of dicts, each with keys:
        'u', 'v', 'cost' (int), 'bandwidth' (str), 'delay' (str), 'queue' (str)
    """
    g = nx.Graph()
    g.add_nodes_from(nodes)
    for e in edges:
        u, v = e["u"], e["v"]
        if u in g and v in g and u != v:
            g.add_edge(
                u, v,
                cost=int(e.get("cost", 1)),
                bandwidth=str(e.get("bandwidth", "2Mb")),
                delay=str(e.get("delay", "10ms")),
                queue=str(e.get("queue", "DropTail")),
            )
    return g


# ── Serializers ───────────────────────────────────────────────────────────────

def graph_to_config(graph):
    """Convert NetworkX graph into dictionary config consumed by NS2 generator."""
    return {
        "nodes": list(graph.nodes),
        "edges": [
            {"u": u, "v": v, **attrs} for u, v, attrs in graph.edges(data=True)
        ],
    }


def topology_to_json(graph):
    """Serialize graph into a formatted JSON string."""
    cfg = graph_to_config(graph)
    return json.dumps(cfg, indent=2)


def json_to_topology(json_str):
    """Deserialize a JSON string into a NetworkX graph."""
    data = json.loads(json_str)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    return create_custom_topology(nodes, edges)


# ── Presets Registry & Layout Computation ────────────────────────────────────

_PRESET_POSITIONS = {
    "4-Router Diamond (Default)": {
        "R0": (0, 1), "R1": (1, 2), "R2": (1, 0), "R3": (2, 1)
    },
    "6-Router Mesh": {
        "R0": (0, 1), "R1": (1, 2), "R2": (1, 0),
        "R3": (2, 2), "R4": (2, 0), "R5": (3, 1)
    },
    "8-Router Backbone Ring": {
        "R0": (0, 2), "R1": (1, 3), "R2": (2, 3), "R3": (3, 2),
        "R4": (3, 1), "R5": (2, 0), "R6": (1, 0), "R7": (0, 1)
    },
}


def get_preset_topologies():
    """Dictionary mapping preset names to factory functions."""
    return {
        "4-Router Diamond (Default)": default_topology,
        "6-Router Mesh": mesh_6node_topology,
        "8-Router Backbone Ring": backbone_8node_topology,
    }


def compute_layout(graph, preset_name=None):
    """
    Return node positions (x, y). Uses pre-configured layout if matching preset,
    or calculates spring layout for custom topologies.
    """
    if preset_name in _PRESET_POSITIONS:
        pos = _PRESET_POSITIONS[preset_name]
        # Verify all nodes in graph have a coordinate
        if all(n in pos for n in graph.nodes):
            return pos
    # Fallback: compute dynamic layout
    if len(graph.nodes) <= 2:
        return nx.shell_layout(graph)
    try:
        return nx.spring_layout(graph, seed=42)
    except Exception:
        return nx.circular_layout(graph)
