import math

def rip_distances(graph, source, infinity=16):
    """Teaching model of RIP: Bellman-Ford relaxation using hop count."""
    dist = {n: math.inf for n in graph.nodes}
    prev = {n: None for n in graph.nodes}
    dist[source] = 0
    for _ in range(max(0, len(graph.nodes) - 1)):
        changed = False
        for u, v in graph.edges():
            for a, b in ((u, v), (v, u)):
                candidate = dist[a] + 1
                if dist[a] != math.inf and candidate < dist[b] and candidate < infinity:
                    dist[b], prev[b], changed = candidate, a, True
        if not changed:
            break
    return dist, prev

def rip_shortest_path(graph, source, destination):
    dist, prev = rip_distances(graph, source)
    table = {n: {"hops": None if dist[n] == math.inf else dist[n], "next_hop": prev[n]} for n in graph.nodes}
    if dist[destination] == math.inf:
        return [], math.inf, table
    path, cur = [], destination
    while cur is not None:
        path.append(cur)
        if cur == source:
            break
        cur = prev[cur]
    path.reverse()
    return (path, dist[destination], table) if path and path[0] == source else ([], math.inf, table)
