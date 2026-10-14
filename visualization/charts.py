"""
Chart helpers for RIP vs OSPF comparison visualisations.
All functions return (fig, ax) — call plt.close(fig) after st.pyplot(fig).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# ── colour palette ───────────────────────────────────────────────────────────
_COLOURS = {"RIP": "#4C72B0", "OSPF": "#DD8452"}


def _bar_pair(ax, labels, rip_vals, ospf_vals, ylabel, title, fmt="{:.2f}"):
    """Draw a grouped bar chart for two protocols side-by-side."""
    x = np.arange(len(labels))
    w = 0.35
    b1 = ax.bar(x - w / 2, rip_vals,  w, label="RIP",  color=_COLOURS["RIP"],  zorder=3)
    b2 = ax.bar(x + w / 2, ospf_vals, w, label="OSPF", color=_COLOURS["OSPF"], zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.yaxis.grid(True, linestyle="--", alpha=0.6, zorder=0)
    ax.set_axisbelow(True)
    for bar in [*b1, *b2]:
        h = bar.get_height()
        ax.annotate(
            fmt.format(h),
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )


def plot_metrics_comparison(rip_metrics: dict, ospf_metrics: dict):
    """
    Four-panel figure: throughput, delay, PDR, lost packets.
    Suitable for a normal (non-failure) single-path comparison.
    """
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    fig.suptitle("RIP vs OSPF — Performance Comparison", fontsize=13, fontweight="bold")

    _bar_pair(
        axes[0, 0],
        ["Result"],
        [rip_metrics.get("throughput_kbps", 0)],
        [ospf_metrics.get("throughput_kbps", 0)],
        "kbps",
        "Throughput",
    )
    _bar_pair(
        axes[0, 1],
        ["Result"],
        [rip_metrics.get("avg_delay_ms", 0)],
        [ospf_metrics.get("avg_delay_ms", 0)],
        "ms",
        "Average End-to-End Delay",
    )
    _bar_pair(
        axes[1, 0],
        ["Result"],
        [rip_metrics.get("pdr_percent", 0)],
        [ospf_metrics.get("pdr_percent", 0)],
        "%",
        "Packet Delivery Ratio",
        fmt="{:.1f}",
    )
    _bar_pair(
        axes[1, 1],
        ["Result"],
        [rip_metrics.get("lost_packets", 0)],
        [ospf_metrics.get("lost_packets", 0)],
        "packets",
        "Lost Packets",
        fmt="{:.0f}",
    )

    fig.tight_layout()
    return fig


def plot_failure_comparison(rip_result: dict, ospf_result: dict):
    """
    Six-panel figure comparing before/after failure for RIP and OSPF.

    Each entry must have keys: before_metrics, after_metrics.
    """
    metrics_keys = [
        ("throughput_kbps", "Throughput (kbps)", "{:.1f}"),
        ("avg_delay_ms",    "Avg Delay (ms)",    "{:.2f}"),
        ("lost_packets",    "Lost Packets",       "{:.0f}"),
    ]
    phases = ["Before failure", "After failure"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    fig.suptitle("RIP vs OSPF — Failure Recovery Comparison", fontsize=13, fontweight="bold")

    for ax, (key, label, fmt) in zip(axes, metrics_keys):
        rip_vals  = [rip_result["before_metrics"].get(key, 0),
                     rip_result["after_metrics"].get(key, 0)]
        ospf_vals = [ospf_result["before_metrics"].get(key, 0),
                     ospf_result["after_metrics"].get(key, 0)]
        _bar_pair(ax, phases, rip_vals, ospf_vals, label, label, fmt)

    fig.tight_layout()
    return fig


def plot_routing_table_heatmap(rip_table: dict, ospf_table: dict, metric_key="hops"):
    """
    Side-by-side heatmaps of routing table metrics for each protocol.
    metric_key: 'hops' for RIP table, 'cost' for OSPF table.
    """
    nodes = sorted(set(rip_table) | set(ospf_table))

    def _extract(table, key):
        return [
            (table[n].get(key) if table[n].get(key) is not None else float("nan"))
            for n in nodes
        ]

    rip_vals  = np.array(_extract(rip_table,  "hops"), dtype=float).reshape(-1, 1)
    ospf_vals = np.array(_extract(ospf_table, "cost"), dtype=float).reshape(-1, 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6, max(3, len(nodes))))
    fig.suptitle("Routing Table Metrics", fontsize=12, fontweight="bold")

    for ax, vals, title, cmap in [
        (ax1, rip_vals,  "RIP — hop count",  "Blues"),
        (ax2, ospf_vals, "OSPF — link cost", "Oranges"),
    ]:
        im = ax.imshow(vals, aspect="auto", cmap=cmap)
        ax.set_yticks(range(len(nodes)))
        ax.set_yticklabels(nodes)
        ax.set_xticks([])
        ax.set_title(title)
        for i, v in enumerate(vals.flatten()):
            ax.text(0, i, "∞" if np.isnan(v) else f"{v:.0f}",
                    ha="center", va="center", color="black", fontsize=11)
        fig.colorbar(im, ax=ax, shrink=0.7)

    fig.tight_layout()
    return fig

