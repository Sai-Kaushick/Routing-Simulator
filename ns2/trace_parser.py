"""
NS2 trace file parser.

parse_trace()          — aggregate metrics over the whole trace window
parse_failure_trace()  — splits the trace at failure_time and measures
                         throughput/delay/loss in each phase PLUS the
                         actual recovery time (first received packet after
                         the gap caused by the link failure).
"""

from pathlib import Path


# ── helpers ───────────────────────────────────────────────────────────────────


# Only count actual data packets — exclude NS2 routing control traffic.
# p[4] in the trace is the packet-type field.
# rtProtoDV / rtProtoLS packets flood the trace during reconvergence and
# would cause received_packets > sent_packets if not filtered out.
_DATA_PACKET_TYPES = {"cbr", "udp", "tcp", "ack", "ftp", "telnet", "exp", "pareto"}


def _read_events(trace_path):
    """
    Yield (event, time, size, packet_id) for every NS2 data-plane trace line.
    Routing control packets (rtProtoDV, rtProtoLS, …) are silently skipped
    so they cannot inflate sent/received counts.
    """
    with Path(trace_path).open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.split()
            if len(p) < 12 or p[0] not in {"+", "-", "r", "d"}:
                continue
            # p[4] is the packet type — skip routing control packets
            if p[4].lower() not in _DATA_PACKET_TYPES:
                continue
            try:
                yield p[0], float(p[1]), int(p[5]), p[11]
            except (ValueError, IndexError):
                continue


# ── public API ────────────────────────────────────────────────────────────────

def parse_trace(trace_path, sim_end=None):
    """
    Aggregate performance metrics from a NS2 .tr file.

    Tracks end-to-end delivery:
      - sent_packets: unique data packets dispatched by source
      - received_packets: unique data packets reaching final sink
      - avg_delay_ms: true end-to-end latency across all network hops
    """
    sent_ids = set()
    first_send = {}  # pid -> (t, size)
    final_recv = {}  # pid -> (t, size)
    drop_events = 0
    trace_first = trace_last = None

    for event, t, size, pid in _read_events(trace_path):
        if trace_first is None:
            trace_first = t
        trace_last = max(trace_last or t, t)

        if event == "+":
            if pid not in first_send:
                first_send[pid] = (t, size)
                sent_ids.add(pid)
        elif event == "r":
            # Update to latest receive event (the final hop/sink)
            final_recv[pid] = (t, size)
        elif event == "d":
            drop_events += 1

    received_ids = {p for p in sent_ids if p in final_recv}
    recv_bytes = sum(final_recv[p][1] for p in received_ids)
    lost = max(0, len(sent_ids) - len(received_ids))
    t0 = trace_first or 0.0
    window = max(0.001, (float(sim_end) if sim_end is not None else (trace_last or 0.0)) - t0)
    delays = [
        final_recv[p][0] - first_send[p][0]
        for p in received_ids
        if final_recv[p][0] >= first_send[p][0]
    ]

    return {
        "sent_packets":      len(sent_ids),
        "received_packets":  len(received_ids),
        "lost_packets":      lost,
        "drop_events":       drop_events,
        "pdr_percent":       100.0 * len(received_ids) / len(sent_ids) if sent_ids else 0.0,
        "throughput_kbps":   recv_bytes * 8.0 / window / 1000.0,
        "avg_delay_ms":      sum(delays) * 1000.0 / len(delays) if delays else 0.0,
        "measurement_window_s": window,
    }


def parse_failure_trace(trace_path, failure_time, sim_end=None):
    """
    Parse a single continuous NS2 failure trace using packet cohort tracking.

    Packets are assigned to 'before' or 'after' phases based on their initial
    transmission time at the source router.

    This prevents in-flight boundary packets from being counted as received
    without being sent, mathematically guaranteeing:
      - received_packets <= sent_packets (PDR <= 100%)
      - No spurious 'lost' packets due to pipeline transit delay
      - True end-to-end recovery time measurement
    """
    events = list(_read_events(trace_path))
    trace_last = max((e[1] for e in events), default=0.0)
    t_end = float(sim_end) if sim_end is not None else trace_last

    first_send = {}   # pid -> (t, size)
    final_recv = {}   # pid -> (t, size)
    drop_events = {"before": 0, "after": 0}

    for ev, t, size, pid in events:
        phase = "before" if t < failure_time else "after"
        if ev == "+":
            if pid not in first_send:
                first_send[pid] = (t, size)
        elif ev == "r":
            final_recv[pid] = (t, size)
        elif ev == "d":
            drop_events[phase] += 1

    def _summarize(pids, window_start, window_end, phase):
        sent_pids = set(pids)
        recv_pids = {p for p in sent_pids if p in final_recv}
        recv_bytes = sum(final_recv[p][1] for p in recv_pids)
        lost = len(sent_pids) - len(recv_pids)
        window = max(0.001, window_end - window_start)
        delays = [
            final_recv[p][0] - first_send[p][0]
            for p in recv_pids
            if final_recv[p][0] >= first_send[p][0]
        ]
        return {
            "sent_packets":     len(sent_pids),
            "received_packets": len(recv_pids),
            "lost_packets":     lost,
            "drop_events":      drop_events[phase],
            "pdr_percent":      100.0 * len(recv_pids) / len(sent_pids) if sent_pids else 0.0,
            "throughput_kbps":  recv_bytes * 8.0 / window / 1000.0,
            "avg_delay_ms":     (sum(delays) * 1000.0 / len(delays)) if delays else 0.0,
            "measurement_window_s": window,
        }

    before_pids = [p for p, (t, _) in first_send.items() if t < failure_time]
    after_pids  = [p for p, (t, _) in first_send.items() if t >= failure_time]

    before_metrics = _summarize(before_pids, 0.0,          failure_time, "before")
    after_metrics  = _summarize(after_pids,  failure_time, t_end,        "after")

    # Recovery time: delay from failure until the first post-failure packet is received
    recvd_after_sent = [
        final_recv[p][0] for p in after_pids if p in final_recv
    ]
    recovery_time_s = None
    if recvd_after_sent:
        recovery_time_s = round(min(recvd_after_sent) - failure_time, 4)

    return {
        "before":            before_metrics,
        "after":             after_metrics,
        "recovery_time_s":   recovery_time_s,
        "last_recv_before":  max((final_recv[p][0] for p in before_pids if p in final_recv), default=None),
        "first_recv_after":  min(recvd_after_sent, default=None),
    }


def measure_recovery_time(failure_time, first_success_after_failure):
    """Recovery = first successful post-failure reception minus failure timestamp."""
    if first_success_after_failure is None:
        return None
    if first_success_after_failure < failure_time:
        raise ValueError("Recovery reception cannot precede the failure.")
    return float(first_success_after_failure) - float(failure_time)
