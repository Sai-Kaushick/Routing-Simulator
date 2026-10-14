def make_failure_event(link_u, link_v, time_seconds):
    if time_seconds < 0:
        raise ValueError("Failure time must be non-negative.")
    if link_u == link_v:
        raise ValueError("A link must connect two different routers.")
    return {"type": "link_failure", "u": link_u, "v": link_v, "time": float(time_seconds)}

def apply_link_failure(graph, link_u, link_v):
    """Return a modified copy of the graph with the selected link removed."""
    if not graph.has_edge(link_u, link_v):
        raise ValueError(f"No link exists between {link_u} and {link_v}.")
    updated = graph.copy()
    updated.remove_edge(link_u, link_v)
    return updated
