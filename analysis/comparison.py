"""
RIP vs OSPF comparison runner.

run_comparison()         — normal run: one NS2 sim per protocol
run_failure_comparison() — single continuous failure run per protocol
                           using NS2's rtmodel-at; real recovery time measured
"""

from routing.rip import rip_shortest_path
from routing.ospf import ospf_shortest_path
from ns2.tcl_generator import generate_tcl, generate_failure_tcl
from ns2.simulation_runner import run_ns2
from ns2.trace_parser import parse_trace, parse_failure_trace


def run_comparison(graph, graph_config, source, destination,
                   sim_time, packet_size, rate):
    """
    Execute one NS2 simulation per protocol on the same topology.
    NS2 runs DV (RIP) or LS (OSPF) routing natively.

    Returns
    -------
    results : dict[str, dict]   keys "RIP" / "OSPF"
        path, cost, table, metrics
    errors  : dict[str, str]
    """
    results: dict = {}
    errors:  dict = {}

    for proto, route_fn in [("RIP", rip_shortest_path), ("OSPF", ospf_shortest_path)]:
        path, cost, table = route_fn(graph, source, destination)
        if not path:
            errors[proto] = f"No route found for {proto} ({source} → {destination})."
            continue
        try:
            tcl = generate_tcl(
                graph_config, path, sim_time, packet_size, rate, proto,
                f"compare_{proto.lower()}.tr",
                f"compare_{proto.lower()}",
            )
            ns2_result = run_ns2(tcl)
            if not ns2_result["ok"]:
                errors[proto] = ns2_result["message"]
                continue
            metrics = parse_trace(ns2_result["trace_path"], sim_end=sim_time)
            results[proto] = {"path": path, "cost": cost, "table": table,
                              "metrics": metrics}
        except Exception as exc:  # noqa: BLE001
            errors[proto] = str(exc)

    return results, errors


def run_failure_comparison(graph, graph_config, source, destination,
                           sim_time, packet_size, rate,
                           fail_u, fail_v, failure_time):
    """
    Run a single-simulation failure experiment for both RIP and OSPF.

    NS2's rtmodel-at drops the link at failure_time; the routing protocol
    reconverges automatically inside the same simulation.
    parse_failure_trace() splits the trace and measures the real recovery gap.

    Returns
    -------
    results : dict[str, dict]   keys "RIP" / "OSPF"
        before_path, after_path (Python-computed for display),
        before_metrics, after_metrics, recovery_time_s
    errors  : dict[str, str]
    """
    from events.failure_simulator import apply_link_failure

    results: dict = {}
    errors:  dict = {}

    failed_graph = apply_link_failure(graph, fail_u, fail_v)

    for proto, route_fn in [("RIP", rip_shortest_path), ("OSPF", ospf_shortest_path)]:
        before_path, _, _ = route_fn(graph,        source, destination)
        after_path,  _, _ = route_fn(failed_graph, source, destination)

        if not before_path:
            errors[proto] = f"{proto}: no pre-failure route."
            continue
        if not after_path:
            errors[proto] = (
                f"{proto}: no route survives failure of {fail_u}-{fail_v}."
            )
            continue

        try:
            tcl = generate_failure_tcl(
                graph_config,
                src_name=source,
                dst_name=destination,
                sim_time=sim_time,
                packet_size=packet_size,
                rate=rate,
                protocol=proto,
                fail_u=fail_u,
                fail_v=fail_v,
                failure_time=failure_time,
                trace_name=f"failure_{proto.lower()}.tr",
                run_name=f"failure_{proto.lower()}",
            )
            ns2_result = run_ns2(tcl)
            if not ns2_result["ok"]:
                errors[proto] = ns2_result["message"]
                continue

            parsed = parse_failure_trace(
                ns2_result["trace_path"],
                failure_time=failure_time,
                sim_end=sim_time,
            )
            results[proto] = {
                "before_path":     before_path,
                "after_path":      after_path,
                "before_metrics":  parsed["before"],
                "after_metrics":   parsed["after"],
                "recovery_time_s": parsed["recovery_time_s"],
            }
        except Exception as exc:  # noqa: BLE001
            errors[proto] = str(exc)

    return results, errors
