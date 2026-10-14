def recommend_protocol(metrics, node_count=4):
    """Transparent starter heuristic; tune only after repeatable experiments."""
    delay = float(metrics.get("avg_delay_ms", 0) or 0)
    loss = int(metrics.get("lost_packets", 0) or 0)
    throughput = float(metrics.get("throughput_kbps", 0) or 0)
    if node_count >= 10 or loss > 0 or delay > 100:
        choice = "OSPF"
        why = "larger topology or observed loss/high delay warrants comparing link-state routing."
    else:
        choice = "RIP"
        why = "a small topology is a reasonable low-complexity baseline."
    return f"Suggested protocol: {choice}. {why} Observed throughput={throughput:.2f} kbps, delay={delay:.2f} ms, loss={loss}. This is a heuristic, not a universal ranking."
