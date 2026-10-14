import streamlit as st
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import json

from topology.graph_manager import (
    default_topology,
    mesh_6node_topology,
    backbone_8node_topology,
    create_custom_topology,
    graph_to_config,
    topology_to_json,
    json_to_topology,
    compute_layout,
    get_preset_topologies,
)
from routing.rip import rip_shortest_path
from routing.ospf import ospf_shortest_path
from ns2.tcl_generator import generate_tcl, generate_failure_tcl
from ns2.simulation_runner import run_ns2
from ns2.trace_parser import parse_trace, parse_failure_trace
from events.failure_simulator import apply_link_failure
from analysis.recommendation import recommend_protocol
from analysis.experiment import write_experiment_results
from analysis.comparison import run_comparison, run_failure_comparison
from visualization.charts import (
    plot_metrics_comparison,
    plot_failure_comparison,
    plot_routing_table_heatmap,
)

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Intelligent Network Routing Simulator", layout="wide")
st.title("Intelligent Network Routing Simulator")
st.caption("NS2 measures packet traffic · Python computes routes (Bellman-Ford / Dijkstra)")
st.warning(
    "Python computes route choices; NS2 measures packet traffic. "
    "This is not native standards-compliant RIP/OSPF control-plane execution."
)

# ── Session State for Custom Topology ─────────────────────────────────────────
if "custom_nodes" not in st.session_state:
    st.session_state.custom_nodes = ["R0", "R1", "R2", "R3", "R4"]
if "custom_edges" not in st.session_state:
    st.session_state.custom_edges = [
        {"u": "R0", "v": "R1", "cost": 1, "bandwidth": "2Mb", "delay": "10ms", "queue": "DropTail"},
        {"u": "R1", "v": "R2", "cost": 1, "bandwidth": "2Mb", "delay": "10ms", "queue": "DropTail"},
        {"u": "R2", "v": "R4", "cost": 1, "bandwidth": "2Mb", "delay": "10ms", "queue": "DropTail"},
        {"u": "R0", "v": "R3", "cost": 4, "bandwidth": "1Mb", "delay": "25ms", "queue": "DropTail"},
        {"u": "R3", "v": "R4", "cost": 4, "bandwidth": "1Mb", "delay": "25ms", "queue": "DropTail"},
        {"u": "R1", "v": "R3", "cost": 2, "bandwidth": "1Mb", "delay": "15ms", "queue": "DropTail"},
    ]


# ── Topology Selection & Construction ─────────────────────────────────────────
presets = get_preset_topologies()
topo_options = list(presets.keys()) + ["Custom Topology (Interactive Builder)"]

with st.sidebar:
    st.header("1. Network Topology")
    topo_choice = st.selectbox("Select Topology Preset", topo_options, index=0)

if topo_choice in presets:
    g = presets[topo_choice]()
else:
    # Build from session state
    g = create_custom_topology(st.session_state.custom_nodes, st.session_state.custom_edges)

# Fallback in case custom topology has no nodes
if len(g.nodes) < 2:
    st.error("Topology must have at least 2 connected routers.")
    g = default_topology()

graph_config = graph_to_config(g)
node_list = sorted(g.nodes)
pos = compute_layout(g, topo_choice)


# ── Custom Topology Interactive Builder UI ───────────────────────────────────
if topo_choice == "Custom Topology (Interactive Builder)":
    with st.expander("🛠️ Custom Topology Builder & Editor", expanded=True):
        col_nodes, col_links = st.columns([1, 2])
        
        with col_nodes:
            st.markdown("##### 1. Define Routers")
            nodes_input = st.text_input(
                "Router list (comma-separated)",
                value=", ".join(st.session_state.custom_nodes),
                help="E.g.: R0, R1, R2, R3, R4, R5"
            )
            parsed_nodes = [n.strip() for n in nodes_input.split(",") if n.strip()]
            if parsed_nodes != st.session_state.custom_nodes and len(parsed_nodes) >= 2:
                st.session_state.custom_nodes = parsed_nodes
                # Remove edges referencing nonexistent nodes
                st.session_state.custom_edges = [
                    e for e in st.session_state.custom_edges
                    if e["u"] in parsed_nodes and e["v"] in parsed_nodes
                ]
                st.rerun()

            st.caption(f"Total Routers: {len(parsed_nodes)}")

        with col_links:
            st.markdown("##### 2. Add New Link")
            r_opts = st.session_state.custom_nodes
            l_col1, l_col2, l_col3, l_col4, l_col5 = st.columns(5)
            
            with l_col1:
                u_node = st.selectbox("From", r_opts, index=0, key="new_u")
            with l_col2:
                v_node = st.selectbox("To", r_opts, index=min(1, len(r_opts)-1), key="new_v")
            with l_col3:
                link_cost = st.number_input("Cost (Metric)", min_value=1, max_value=100, value=1, key="new_cost")
            with l_col4:
                link_bw = st.selectbox("Bandwidth", ["250Kb", "500Kb", "1Mb", "2Mb", "5Mb", "10Mb"], index=3, key="new_bw")
            with l_col5:
                link_delay = st.selectbox("Delay", ["5ms", "10ms", "15ms", "20ms", "30ms", "50ms"], index=1, key="new_delay")

            if st.button("➕ Add Link", type="secondary"):
                if u_node == v_node:
                    st.warning("Cannot link a router to itself.")
                else:
                    # Check if link already exists
                    existing = any(
                        (e["u"] == u_node and e["v"] == v_node) or (e["u"] == v_node and e["v"] == u_node)
                        for e in st.session_state.custom_edges
                    )
                    if existing:
                        st.warning(f"Link between {u_node} and {v_node} already exists!")
                    else:
                        st.session_state.custom_edges.append({
                            "u": u_node, "v": v_node, "cost": int(link_cost),
                            "bandwidth": link_bw, "delay": link_delay, "queue": "DropTail"
                        })
                        st.rerun()

        # Existing Links Table & Removal
        if st.session_state.custom_edges:
            st.markdown("##### Current Links")
            edge_df = pd.DataFrame(st.session_state.custom_edges)
            e_col1, e_col2 = st.columns([3, 1])
            with e_col1:
                st.dataframe(edge_df[["u", "v", "cost", "bandwidth", "delay"]], width="stretch", hide_index=True)
            with e_col2:
                link_to_del = st.selectbox(
                    "Delete a link",
                    [f"{e['u']} - {e['v']}" for e in st.session_state.custom_edges],
                    key="del_link_select"
                )
                if st.button("🗑️ Remove Link"):
                    du, dv = link_to_del.split(" - ")
                    st.session_state.custom_edges = [
                        e for e in st.session_state.custom_edges
                        if not ((e["u"] == du and e["v"] == dv) or (e["u"] == dv and e["v"] == du))
                    ]
                    st.rerun()

        # JSON Import / Export
        with st.expander("JSON Import / Export"):
            json_str = topology_to_json(g)
            st.text_area("Current Topology JSON (copy to save)", value=json_str, height=120)
            json_import = st.text_area("Paste Topology JSON to load", height=100, key="json_paste")
            if st.button("Load from JSON"):
                try:
                    loaded_g = json_to_topology(json_import)
                    if len(loaded_g.nodes) >= 2:
                        st.session_state.custom_nodes = list(loaded_g.nodes)
                        st.session_state.custom_edges = [
                            {"u": u, "v": v, **attrs} for u, v, attrs in loaded_g.edges(data=True)
                        ]
                        st.success("Topology imported successfully!")
                        st.rerun()
                    else:
                        st.error("Imported JSON must have at least 2 nodes.")
                except Exception as exc:
                    st.error(f"Invalid JSON: {exc}")


# ── Topology Drawing Helper ───────────────────────────────────────────────────
def _draw_topology(graph, pos_dict, highlight_path=None, ax=None):
    """Draw network topology with edge costs, bandwidths, and optional path highlighting."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 3.5))
    else:
        fig = ax.get_figure()

    node_list = list(graph.nodes)
    node_colors = [
        "#ffcc66" if (highlight_path and n in highlight_path) else "#d8e9ff"
        for n in node_list
    ]
    nx.draw_networkx(
        graph, pos=pos_dict,
        ax=ax, node_size=1200, node_color=node_colors,
        font_size=9, font_weight="bold"
    )
    edge_labels = {
        (u, v): f"c={d.get('cost', 1)}\n{d.get('bandwidth', '')}"
        for u, v, d in graph.edges(data=True)
    }
    nx.draw_networkx_edge_labels(
        graph, pos=pos_dict,
        edge_labels=edge_labels, ax=ax, font_size=7,
    )
    ax.axis("off")
    return fig


# ── Sidebar Simulation Controls (Dynamic) ────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.header("2. Simulation Controls")
    
    # Source & Destination routers dynamically populated from active graph
    source_idx = 0
    dest_idx = max(0, len(node_list) - 1)
    
    source = st.selectbox("Source router", node_list, index=source_idx)
    destination = st.selectbox("Destination router", node_list, index=dest_idx)
    
    sim_time    = st.slider("Simulation duration (s)", 6, 30, 12)
    packet_size = st.selectbox("Packet size (bytes)", [256, 512, 1000], index=1)
    rate        = st.selectbox("Traffic rate", ["100Kb", "250Kb", "500Kb", "1Mb"], index=1)

    st.markdown("---")
    st.subheader("3. Failure Experiment")
    do_failure = st.checkbox("Enable link-failure experiment")
    
    # Link options dynamically populated from active graph edges
    edge_options = [f"{u}-{v}" for u, v in sorted(g.edges())]
    if edge_options:
        fail_link = st.selectbox("Link to fail", edge_options)
    else:
        fail_link = None
        st.warning("No links available in topology.")

    failure_time = (
        st.slider("Failure time (s)", 2.0, float(sim_time - 2), 5.0, 0.5)
        if sim_time >= 6 else 2.0
    )


# ── Active Topology View ──────────────────────────────────────────────────────
st.subheader(f"Active Network Topology ({topo_choice})")
fig_topo = _draw_topology(g, pos)
st.pyplot(fig_topo)
plt.close(fig_topo)

if source == destination:
    st.warning("Choose different source and destination routers in the sidebar to proceed.")
    st.stop()


# ── Tabs: Single Run & Protocol Comparison ────────────────────────────────────
tab_single, tab_compare = st.tabs(["Single Protocol Run", "RIP vs OSPF Comparison"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — SINGLE PROTOCOL RUN
# ════════════════════════════════════════════════════════════════════════════
with tab_single:
    protocol  = st.selectbox("Routing protocol", ["RIP", "OSPF"])
    run_btn   = st.button("▶ Run experiment", type="primary", width="stretch",
                          key="btn_single")

    route_fn = rip_shortest_path if protocol == "RIP" else ospf_shortest_path
    path, cost, table = route_fn(g, source, destination)

    c1, c2, c3 = st.columns(3)
    c1.metric("Protocol", protocol)
    c2.metric("Path", " → ".join(path) if path else "No route")
    c3.metric("Path metric", str(cost))

    with st.expander("Routing table"):
        st.json(table)

    if do_failure:
        st.caption(
            "NS2 runs a single continuous simulation. Link is cut at "
            f"t={failure_time:.1f}s via `$ns rtmodel-at`. The protocol reconverges automatically."
        )

    if run_btn:
        if not path:
            st.error("No route exists.")
        elif not do_failure:
            # ── simple single run ────────────────────────────────────────────
            tcl = generate_tcl(graph_config, path, sim_time, packet_size,
                               rate, protocol, "out.tr", "single_run")
            result = run_ns2(tcl)
            if not result["ok"]:
                st.error(result["message"])
            else:
                metrics = parse_trace(result["trace_path"], sim_end=sim_time)
                st.subheader("Performance Metrics")
                cols = st.columns(4)
                cols[0].metric("Throughput",    f"{metrics['throughput_kbps']:.2f} kbps")
                cols[1].metric("Avg delay",     f"{metrics['avg_delay_ms']:.2f} ms")
                cols[2].metric("Lost packets",  metrics["lost_packets"])
                cols[3].metric("PDR",           f"{metrics['pdr_percent']:.2f}%")
                with st.expander("Raw metrics"):
                    st.json(metrics)
                st.subheader("Recommendation")
                st.write(recommend_protocol(metrics, g.number_of_nodes()))
        else:
            # ── failure experiment (single continuous NS2 simulation) ──────────
            if not fail_link:
                st.error("No link selected to fail.")
            else:
                lu, lv = fail_link.split("-")
                if not g.has_edge(lu, lv):
                    st.error("Selected link does not exist.")
                else:
                    failed_graph = apply_link_failure(g, lu, lv)
                    after_path, after_cost, after_table = route_fn(failed_graph, source, destination)
                    if not after_path:
                        st.error("No route remains after this link failure.")
                    elif failure_time <= 1.5 or failure_time >= sim_time - 1.0:
                        st.error("Choose a failure time > 1.5 s and at least 1 s before simulation end.")
                    else:
                        st.write(f"Before failure: `{' → '.join(path)}` (metric {cost})")
                        st.write(f"After  failure: `{' → '.join(after_path)}` (metric {after_cost})")
                        st.info(
                            f"NS2 will run a single continuous simulation. "
                            f"Link `{lu}-{lv}` is cut at t={failure_time:.1f} s via `$ns rtmodel-at`. "
                            f"The {protocol} routing protocol reconverges automatically."
                        )

                        tcl = generate_failure_tcl(
                            graph_config,
                            src_name=source, dst_name=destination,
                            sim_time=sim_time, packet_size=packet_size, rate=rate,
                            protocol=protocol,
                            fail_u=lu, fail_v=lv, failure_time=failure_time,
                            trace_name="failure_single.tr", run_name="failure_single",
                        )
                        with st.expander("Generated Tcl script"):
                            st.code(open(tcl, encoding="utf-8").read(), language="tcl")

                        result = run_ns2(tcl)
                        if not result["ok"]:
                            st.error(result["message"])
                        else:
                            parsed = parse_failure_trace(
                                result["trace_path"],
                                failure_time=failure_time,
                                sim_end=sim_time,
                            )
                            m1       = parsed["before"]
                            m2       = parsed["after"]
                            recovery = parsed["recovery_time_s"]

                            rows = [
                                {"phase": "before_failure", "protocol": protocol, **m1},
                                {"phase": "after_failure",  "protocol": protocol, **m2},
                            ]
                            csv_path, json_path = write_experiment_results(
                                "results", rows,
                                {"protocol": protocol, "failed_link": [lu, lv],
                                 "failure_time_s": failure_time,
                                 "before_path": path, "after_path": after_path,
                                 "recovery_model": "ns2_rtmodel_at_single_sim",
                                 "recovery_time_s": recovery},
                            )
                            st.subheader("Results")
                            st.dataframe(pd.DataFrame(rows), width="stretch")
                            rec_label = (
                                f"{recovery:.3f} s"
                                if recovery is not None
                                else "No post-failure packets received"
                            )
                            st.metric(
                                "Measured recovery gap",
                                rec_label,
                                help="Time between last pre-failure receive and first post-failure receive in the NS2 trace.",
                            )
                            st.success(f"Saved to {csv_path}")
                            st.subheader("Recommendation")
                            st.write(recommend_protocol(m2, failed_graph.number_of_nodes()))


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — RIP vs OSPF COMPARISON
# ════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.markdown(
        "Runs **both** RIP and OSPF on the same topology and parameters, "
        "then plots side-by-side performance charts from NS2 trace files."
    )

    if not do_failure:
        # ── normal comparison ────────────────────────────────────────────────
        compare_btn = st.button("▶ Compare RIP vs OSPF", type="primary",
                                width="stretch", key="btn_compare")

        # ── always show routing paths side-by-side ───────────────────────────
        rip_path,  rip_cost,  rip_table  = rip_shortest_path(g, source, destination)
        ospf_path, ospf_cost, ospf_table = ospf_shortest_path(g, source, destination)

        st.subheader("Routing Paths")
        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown("**RIP** (Bellman-Ford, hop count)")
            st.metric("Path",   " → ".join(rip_path)  if rip_path  else "No route")
            st.metric("Metric (hops)", str(rip_cost))
            fig_rip = _draw_topology(g, pos, highlight_path=rip_path)
            st.pyplot(fig_rip);  plt.close(fig_rip)
            with st.expander("RIP routing table"):
                st.json(rip_table)

        with pc2:
            st.markdown("**OSPF** (Dijkstra, link cost)")
            st.metric("Path",   " → ".join(ospf_path) if ospf_path else "No route")
            st.metric("Metric (cost)",  str(ospf_cost))
            fig_ospf = _draw_topology(g, pos, highlight_path=ospf_path)
            st.pyplot(fig_ospf); plt.close(fig_ospf)
            with st.expander("OSPF routing table"):
                st.json(ospf_table)

        st.subheader("Routing Table Heatmap")
        fig_heat = plot_routing_table_heatmap(rip_table, ospf_table)
        st.pyplot(fig_heat); plt.close(fig_heat)

        if compare_btn:
            with st.spinner("Running NS2 for RIP and OSPF…"):
                results, errors = run_comparison(
                    g, graph_config, source, destination, sim_time, packet_size, rate
                )

            for proto, msg in errors.items():
                st.error(f"{proto}: {msg}")

            if "RIP" in results and "OSPF" in results:
                rm = results["RIP"]["metrics"]
                om = results["OSPF"]["metrics"]

                st.subheader("Performance Comparison (NS2 measurements)")

                # ── summary table ────────────────────────────────────────────
                summary = pd.DataFrame(
                    {
                        "Metric": [
                            "Throughput (kbps)",
                            "Avg delay (ms)",
                            "PDR (%)",
                            "Lost packets",
                            "Sent packets",
                            "Received packets",
                        ],
                        "RIP": [
                            f"{rm['throughput_kbps']:.2f}",
                            f"{rm['avg_delay_ms']:.2f}",
                            f"{rm['pdr_percent']:.2f}",
                            f"{rm['lost_packets']}",
                            f"{rm['sent_packets']}",
                            f"{rm['received_packets']}",
                        ],
                        "OSPF": [
                            f"{om['throughput_kbps']:.2f}",
                            f"{om['avg_delay_ms']:.2f}",
                            f"{om['pdr_percent']:.2f}",
                            f"{om['lost_packets']}",
                            f"{om['sent_packets']}",
                            f"{om['received_packets']}",
                        ],
                    }
                )
                st.dataframe(summary, width="stretch", hide_index=True)

                # ── charts ───────────────────────────────────────────────────
                st.subheader("Comparison Charts")
                fig_cmp = plot_metrics_comparison(rm, om)
                st.pyplot(fig_cmp); plt.close(fig_cmp)

                # ── recommendation ────────────────────────────────────────────
                st.subheader("Recommendation")
                col_r, col_o = st.columns(2)
                with col_r:
                    st.markdown("**RIP Assessment**")
                    st.info(recommend_protocol(rm, g.number_of_nodes()))
                with col_o:
                    st.markdown("**OSPF Assessment**")
                    st.info(recommend_protocol(om, g.number_of_nodes()))

                # ── save comparison results ───────────────────────────────────
                rows = [
                    {"phase": "comparison", "protocol": "RIP",  **rm},
                    {"phase": "comparison", "protocol": "OSPF", **om},
                ]
                csv_path, json_path = write_experiment_results(
                    "results", rows,
                    {"experiment": "protocol_comparison",
                     "source": source, "destination": destination,
                     "sim_time_s": sim_time, "packet_size": packet_size,
                     "rate": rate, "rip_path": rip_path, "ospf_path": ospf_path},
                )
                st.success(f"Comparison results saved to {csv_path}")

    else:
        # ── failure comparison ───────────────────────────────────────────────
        if not fail_link:
            st.error("No link selected to fail.")
        else:
            st.markdown(
                "Compares how **RIP** and **OSPF** each survive a link failure "
                f"(`{fail_link}` at t={failure_time:.1f} s)."
            )
            fail_compare_btn = st.button("▶ Compare failure recovery",
                                         type="primary", width="stretch",
                                         key="btn_fail_compare")

            lu, lv = fail_link.split("-")
            if not g.has_edge(lu, lv):
                st.error("Selected link does not exist in topology.")
            elif failure_time <= 1.5 or failure_time >= sim_time - 1.0:
                st.error("Choose a failure time > 1.5 s and at least 1 s before simulation end.")
            else:
                failed_graph = apply_link_failure(g, lu, lv)

                # show both post-failure paths before running
                rip_path,  _, _ = rip_shortest_path(g, source, destination)
                ospf_path, _, _ = ospf_shortest_path(g, source, destination)
                rip_after,  _, _ = rip_shortest_path(failed_graph, source, destination)
                ospf_after, _, _ = ospf_shortest_path(failed_graph, source, destination)

                pc1, pc2 = st.columns(2)
                with pc1:
                    st.markdown("**RIP**")
                    st.write(f"Before: `{' → '.join(rip_path)}`")
                    st.write(f"After:  `{' → '.join(rip_after) if rip_after else 'No route'}`")
                with pc2:
                    st.markdown("**OSPF**")
                    st.write(f"Before: `{' → '.join(ospf_path)}`")
                    st.write(f"After:  `{' → '.join(ospf_after) if ospf_after else 'No route'}`")

                if fail_compare_btn:
                    with st.spinner("Running NS2 failure comparison (2 continuous simulations)…"):
                        fc_results, fc_errors = run_failure_comparison(
                            g, graph_config, source, destination,
                            sim_time, packet_size, rate,
                            lu, lv, failure_time,
                        )

                    for proto, msg in fc_errors.items():
                        st.error(f"{proto}: {msg}")

                    if "RIP" in fc_results and "OSPF" in fc_results:
                        st.subheader("Failure Recovery Charts")
                        fig_fc = plot_failure_comparison(fc_results["RIP"], fc_results["OSPF"])
                        st.pyplot(fig_fc); plt.close(fig_fc)

                        st.subheader("Detailed Metrics")
                        rows = []
                        for proto, data in fc_results.items():
                            rows.append({"phase": "before_failure", "protocol": proto,
                                         **data["before_metrics"]})
                            rows.append({"phase": "after_failure",  "protocol": proto,
                                         **data["after_metrics"]})
                        st.dataframe(pd.DataFrame(rows), width="stretch")

                        csv_path, json_path = write_experiment_results(
                            "results", rows,
                            {"experiment": "failure_comparison",
                             "failed_link": [lu, lv], "failure_time_s": failure_time,
                             "source": source, "destination": destination},
                        )
                        st.success(f"Results saved to {csv_path}")
