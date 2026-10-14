import networkx as nx

def ospf_shortest_path(graph, source, destination):
    """Dijkstra shortest path using configured link cost as the metric."""
    try:
        path = nx.shortest_path(graph, source, destination, weight="cost", method="dijkstra")
        cost = nx.path_weight(graph, path, weight="cost")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return [], float("inf"), {}
    distances = nx.single_source_dijkstra_path_length(graph, source, weight="cost")
    table = {}
    for node in graph.nodes:
        try:
            p = nx.shortest_path(graph, source, node, weight="cost", method="dijkstra")
            nxt = p[1] if len(p) > 1 else None
        except nx.NetworkXNoPath:
            nxt = None
        table[node] = {"cost": distances.get(node, float("inf")), "next_hop": nxt}
    return path, cost, table
