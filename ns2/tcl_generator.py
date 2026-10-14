"""
NS2 Tcl script generator.

generate_tcl()         — normal single-run using NS2 native DV or LS routing
generate_failure_tcl() — single run with an in-simulation link-failure event
                         using $ns rtmodel-at so NS2 reconverges by itself
"""

import re
from pathlib import Path

# Map project protocol names → NS2 rtproto keyword
_NS2_RTPROTO = {
    "RIP":  "DV",   # Distance Vector  (Bellman-Ford, hop/delay metric)
    "OSPF": "LS",   # Link State       (SPF, full topology)
}

_VALID_TRACE = re.compile(r"[A-Za-z0-9_.\-]+")


def _validate(trace_name, sim_time, protocol):
    if not _VALID_TRACE.fullmatch(trace_name):
        raise ValueError(
            "Trace filename may only contain letters, digits, dot, underscore or dash."
        )
    if sim_time <= 2:
        raise ValueError("Simulation duration must exceed 2 seconds.")
    if protocol.upper() not in _NS2_RTPROTO:
        raise ValueError(f"Unknown protocol '{protocol}'. Choose RIP or OSPF.")


def _header(protocol, trace_name, label=""):
    rtproto = _NS2_RTPROTO[protocol.upper()]
    return [
        f"# Intelligent Network Routing Simulator — {label}",
        f"# NS2 rtproto: {rtproto}  (models {protocol})",
        "set ns [new Simulator]",
        f"$ns rtproto {rtproto}",          # ← native NS2 routing protocol
        f'set tracefile [open "{trace_name}" w]',
        "$ns trace-all $tracefile",
    ]


def _build_topology(graph_config):
    """Return Tcl lines for nodes + duplex-links. Also returns node index dict."""
    nodes = graph_config["nodes"]
    idx   = {name: i for i, name in enumerate(nodes)}
    lines = [f"set n{idx[name]} [$ns node]" for name in nodes]
    for e in graph_config["edges"]:
        bw    = e["bandwidth"]
        delay = e["delay"]
        queue = e.get("queue", "DropTail")
        lines.append(
            f"$ns duplex-link $n{idx[e['u']]} $n{idx[e['v']]} {bw} {delay} {queue}"
        )
    return lines, idx


def _traffic(idx, src_name, dst_name, packet_size, rate, start=1.0, stop_offset=0.5):
    """Return Tcl lines for a CBR/UDP flow between two node names."""
    src = idx[src_name]
    dst = idx[dst_name]
    return [
        "set udp  [new Agent/UDP]",
        f"$ns attach-agent $n{src} $udp",
        "set sink [new Agent/Null]",
        f"$ns attach-agent $n{dst} $sink",
        "$ns connect $udp $sink",
        "set app [new Application/Traffic/CBR]",
        f"$app set packetSize_ {int(packet_size)}",
        f"$app set rate_       {rate}",
        "$app attach-agent $udp",
        f'$ns at {start:.3f} "$app start"',
    ], src, dst


def _finish_block(sim_time, stop_time):
    return [
        f'$ns at {stop_time:.3f} "$app stop"',
        f'$ns at {sim_time:.3f}  "finish"',
        "proc finish {} {",
        "    global ns tracefile",
        "    $ns flush-trace",
        "    close $tracefile",
        "    exit 0",
        "}",
        "$ns run",
    ]


def _save(run_name, lines):
    out = Path("results")
    out.mkdir(exist_ok=True)
    target = out / f"{run_name}.tcl"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(target)


# ── public API ────────────────────────────────────────────────────────────────

def generate_tcl(
    graph_config,
    path,                  # kept for API compatibility; ignored — NS2 routes itself
    sim_time=10.0,
    packet_size=512,
    rate="250Kb",
    protocol="RIP",
    trace_name="out.tr",
    run_name="simulation",
):
    """
    Generate a single-phase NS2 Tcl script.

    NS2 runs its own DV (RIP-like) or LS (OSPF-like) routing protocol;
    the `path` argument is used only to identify source and destination nodes.
    Traffic starts at t=1.0 s to give the routing protocol time to converge.
    """
    protocol = protocol.upper()
    _validate(trace_name, sim_time, protocol)

    if len(path) < 2:
        raise ValueError("path must contain at least two routers.")
    nodes = graph_config["nodes"]
    idx_map = {name: i for i, name in enumerate(nodes)}
    if any(n not in idx_map for n in path):
        raise ValueError("Route contains a router absent from the topology.")

    traffic_start = 1.5   # allow routing protocol to converge first
    traffic_stop  = sim_time - 0.5

    lines  = _header(protocol, trace_name, label="single run")
    topo_lines, idx = _build_topology(graph_config)
    lines += topo_lines

    flow_lines, _, _ = _traffic(
        idx, path[0], path[-1], packet_size, rate,
        start=traffic_start, stop_offset=0.5,
    )
    lines += flow_lines
    lines += _finish_block(sim_time, traffic_stop)

    return _save(run_name, lines)


def generate_failure_tcl(
    graph_config,
    src_name,
    dst_name,
    sim_time=15.0,
    packet_size=512,
    rate="250Kb",
    protocol="RIP",
    fail_u=None,
    fail_v=None,
    failure_time=5.0,
    restore_time=None,          # None = do not restore
    trace_name="failure.tr",
    run_name="failure_run",
):
    """
    Generate a single continuous NS2 Tcl script with an in-simulation
    link failure at `failure_time` seconds.

    NS2's rtmodel-at brings the link down; the routing protocol (DV or LS)
    reconverges automatically — no two-phase hack needed.
    The trace file captures the full picture: normal traffic, outage, recovery.
    """
    protocol = protocol.upper()
    _validate(trace_name, sim_time, protocol)

    if fail_u is None or fail_v is None:
        raise ValueError("fail_u and fail_v must be provided.")
    if failure_time <= 1.5 or failure_time >= sim_time - 1.0:
        raise ValueError("failure_time must be > 1.5 s and < sim_time - 1.0 s.")

    nodes = graph_config["nodes"]
    idx_map = {name: i for i, name in enumerate(nodes)}
    if src_name not in idx_map or dst_name not in idx_map:
        raise ValueError("src_name or dst_name not in topology.")
    if fail_u not in idx_map or fail_v not in idx_map:
        raise ValueError("fail_u or fail_v not in topology.")

    traffic_start = 1.5
    traffic_stop  = sim_time - 0.5

    lines  = _header(protocol, trace_name, label="failure run")
    topo_lines, idx = _build_topology(graph_config)
    lines += topo_lines

    flow_lines, _, _ = _traffic(
        idx, src_name, dst_name, packet_size, rate, start=traffic_start,
    )
    lines += flow_lines

    # ── link failure event ────────────────────────────────────────────────────
    fu, fv = idx[fail_u], idx[fail_v]
    lines.append(f'$ns rtmodel-at {failure_time:.3f} down $n{fu} $n{fv}')
    lines.append(f'$ns rtmodel-at {failure_time:.3f} down $n{fv} $n{fu}')
    if restore_time is not None and restore_time < sim_time:
        lines.append(f'$ns rtmodel-at {restore_time:.3f} up $n{fu} $n{fv}')
        lines.append(f'$ns rtmodel-at {restore_time:.3f} up $n{fv} $n{fu}')

    lines += _finish_block(sim_time, traffic_stop)
    return _save(run_name, lines)
