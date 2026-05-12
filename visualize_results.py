"""Generate visualizations from the three evaluation CSVs.

Reads:
    extensibility_results.csv
    effort_comparison.csv
    interoperability_results.csv

Produces 10 PNG charts plus a summary dashboard, saved to ``charts/``.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless environments
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
CHARTS_DIR = ROOT / "charts"
CHARTS_DIR.mkdir(exist_ok=True)

# --- Style ---
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "-",
    "figure.dpi": 150,
})

# Consistent color palette
COLORS = {
    "framework": "#1B4F72",
    "native":    "#C0392B",
    "existing":  "#5499C7",
    "new":       "#27AE60",
    "native_impl": "#2E86C1",
    "compensatory": "#E67E22",
    "pass": "#27AE60",
    "partial": "#F1C40F",
    "fail": "#C0392B",
    "skip": "#95A5A6",
    "saved": "#27AE60",
    "lost":  "#C0392B",
}


def save(fig, name: str) -> Path:
    out = CHARTS_DIR / name
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# =====================================================================
# 1. EXTENSIBILITY: LOC per adapter
# =====================================================================

def chart_extensibility_loc() -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    adapters = ["coding_rider.py", "codrone_edu.py", "wizwing.py", "simdrone_adapter.py\n(NEW)"]
    locs = [93, 103, 145, 200]
    colors = [COLORS["existing"]] * 3 + [COLORS["new"]]

    bars = ax.bar(adapters, locs, color=colors, edgecolor="black", linewidth=0.5)
    avg = np.mean(locs[:3])
    ax.axhline(avg, color="gray", linestyle="--", linewidth=1, label=f"Average existing: {avg:.0f} LOC")

    for bar, loc in zip(bars, locs):
        ax.text(bar.get_x() + bar.get_width() / 2, loc + 4, str(loc),
                ha="center", fontweight="bold", fontsize=10)

    ax.set_ylabel("Lines of code (logic only)")
    ax.set_title("Adapter size comparison: new SimDrone vs existing adapters")
    ax.legend(loc="upper left")
    ax.set_ylim(0, max(locs) * 1.18)
    return save(fig, "fig01_extensibility_loc.png")


# =====================================================================
# 2. EXTENSIBILITY: Compliance checklist
# =====================================================================

def chart_extensibility_compliance() -> Path:
    fig, ax = plt.subplots(figsize=(9, 5))
    checks = [
        "Files modified",
        "Subclass of DroneAdapter",
        "Abstract methods implemented",
        "Registry contains 'simdrone'",
        "Factory creates correct type",
        "All 4 drones respond to broadcast",
        "Original 3-drone workflow",
        "Originals intact",
    ]
    values = [0, 1, 10, 4, 1, 4, 1, 1]      # actuals
    targets = [0, 1, 10, 4, 1, 4, 1, 1]     # expected
    pass_flags = [v == t for v, t in zip(values, targets)]

    y = np.arange(len(checks))
    bar_color = [COLORS["pass"] if ok else COLORS["fail"] for ok in pass_flags]
    ax.barh(y, [1] * len(checks), color=bar_color, edgecolor="black", linewidth=0.5)

    for i, (chk, val, tgt, ok) in enumerate(zip(checks, values, targets, pass_flags)):
        symbol = "PASS" if ok else "FAIL"
        ax.text(0.5, i, f"{symbol}   ({val} / {tgt} expected)" if tgt != 0
                else f"{symbol}   ({val} files modified)",
                va="center", ha="center",
                color="white", fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(checks)
    ax.invert_yaxis()
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.grid(False)
    ax.set_title("Extensibility evaluation: compliance checks")
    return save(fig, "fig02_extensibility_compliance.png")


# =====================================================================
# 3. EXTENSIBILITY: Effort comparison
# =====================================================================

def chart_extensibility_effort() -> Path:
    fig, ax = plt.subplots(figsize=(7, 5))
    labels = ["Extensible\n(framework)", "Non-extensible\n(hypothetical)"]
    hours = [8.00, 12.80]
    colors = [COLORS["framework"], COLORS["native"]]

    bars = ax.bar(labels, hours, color=colors, edgecolor="black", linewidth=0.5, width=0.5)
    for bar, h in zip(bars, hours):
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.2, f"{h:.1f} h",
                ha="center", fontweight="bold")

    ax.annotate("4.80 h saved\n(37.5%)",
                xy=(0.5, 9.5), xytext=(0.5, 11.0),
                ha="center", fontsize=11, fontweight="bold",
                color=COLORS["saved"],
                arrowprops=dict(arrowstyle="->", color=COLORS["saved"], lw=2))

    ax.set_ylabel("Developer-hours")
    ax.set_title("Effort to add a new drone platform")
    ax.set_ylim(0, max(hours) * 1.25)
    return save(fig, "fig03_extensibility_effort.png")


# =====================================================================
# 4. EFFORT: side-by-side metrics
# =====================================================================

def chart_effort_metrics() -> Path:
    rows = read_csv(ROOT / "effort_comparison.csv")
    metric_map = {r["metric"]: r for r in rows}
    metrics = [
        ("Lines of code\n(logic only)", "lines_of_code"),
        ("Import\nstatements", "import_statements"),
        ("Distinct\nAPI calls", "distinct_api_calls"),
        ("Drone-object\nvariables", "drone_object_variables"),
        ("If/elif\nblocks", "if_blocks"),
        ("Try/except\nblocks", "try_except_blocks"),
    ]
    labels = [m[0] for m in metrics]
    a_vals = [int(metric_map[m[1]]["version_a_framework"]) for m in metrics]
    b_vals = [int(metric_map[m[1]]["version_b_native"]) for m in metrics]

    x = np.arange(len(labels))
    width = 0.38

    fig, ax = plt.subplots(figsize=(11, 5.5))
    bars_a = ax.bar(x - width / 2, a_vals, width,
                    label="Version A (framework)", color=COLORS["framework"],
                    edgecolor="black", linewidth=0.5)
    bars_b = ax.bar(x + width / 2, b_vals, width,
                    label="Version B (native)", color=COLORS["native"],
                    edgecolor="black", linewidth=0.5)

    for bars, vals in [(bars_a, a_vals), (bars_b, b_vals)]:
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                    str(v), ha="center", fontweight="bold", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Count")
    ax.set_title("Development effort metrics: framework vs native implementation")
    ax.legend(loc="upper left")
    ax.set_ylim(0, max(b_vals) * 1.18)
    return save(fig, "fig04_effort_metrics.png")


# =====================================================================
# 5. EFFORT: Reduction %
# =====================================================================

def chart_effort_reduction() -> Path:
    rows = read_csv(ROOT / "effort_comparison.csv")
    metric_labels = {
        "lines_of_code": "Lines of code",
        "import_statements": "Imports",
        "distinct_api_calls": "Distinct API calls",
        "drone_object_variables": "Drone variables",
        "if_blocks": "If/elif blocks",
        "try_except_blocks": "Try/except blocks",
    }
    reductions = []
    labels = []
    for r in rows:
        if r["metric"] not in metric_labels:
            continue
        red_str = r["reduction"].rstrip("%").strip()
        try:
            val = float(red_str.lstrip("+"))
        except ValueError:
            continue
        labels.append(metric_labels[r["metric"]])
        reductions.append(val)

    fig, ax = plt.subplots(figsize=(9, 5))
    y = np.arange(len(labels))
    bars = ax.barh(y, reductions, color=COLORS["framework"],
                   edgecolor="black", linewidth=0.5)
    for bar, val in zip(bars, reductions):
        ax.text(val + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}%", va="center", fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Reduction in Version A vs Version B (%)")
    ax.set_title("Framework's reduction of complexity per metric")
    ax.set_xlim(0, max(reductions) * 1.12)
    return save(fig, "fig05_effort_reduction.png")


# =====================================================================
# 6. EFFORT: Reusable code
# =====================================================================

def chart_effort_reusability() -> Path:
    a_pct = 96.8
    b_pct = 27.9

    fig, ax = plt.subplots(figsize=(9, 4))
    versions = ["Version A\n(framework)", "Version B\n(native)"]
    reusable = [a_pct, b_pct]
    platform_specific = [100 - a_pct, 100 - b_pct]

    y = np.arange(len(versions))
    ax.barh(y, reusable, color=COLORS["framework"], edgecolor="black",
            linewidth=0.5, label="Reusable across platforms")
    ax.barh(y, platform_specific, left=reusable, color=COLORS["native"],
            edgecolor="black", linewidth=0.5, label="Platform-specific")

    for i, (r, ps) in enumerate(zip(reusable, platform_specific)):
        ax.text(r / 2, i, f"{r:.1f}%", va="center", ha="center",
                color="white", fontweight="bold")
        ax.text(r + ps / 2, i, f"{ps:.1f}%", va="center", ha="center",
                color="white", fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(versions)
    ax.set_xlabel("Percentage of code")
    ax.set_xlim(0, 100)
    ax.set_title("Code reusability across drone platforms")
    ax.legend(loc="lower right", framealpha=0.95)
    return save(fig, "fig06_effort_reusability.png")


# =====================================================================
# 7. INTEROPERABILITY: verdicts per platform
# =====================================================================

def chart_interop_verdicts() -> Path:
    rows = read_csv(ROOT / "interoperability_results.csv")
    platforms = sorted({r["platform"] for r in rows})
    verdicts = ["PASS", "PARTIAL", "FAIL", "FRAMEWORK_LIMIT"]
    counts = {p: {v: 0 for v in verdicts} for p in platforms}
    for r in rows:
        counts[r["platform"]][r["result"]] += 1

    x = np.arange(len(platforms))
    bottom = np.zeros(len(platforms))
    color_map = {
        "PASS": COLORS["pass"],
        "PARTIAL": COLORS["partial"],
        "FAIL": COLORS["fail"],
        "FRAMEWORK_LIMIT": COLORS["skip"],
    }
    label_map = {
        "PASS": "PASS",
        "PARTIAL": "PARTIAL",
        "FAIL": "FAIL",
        "FRAMEWORK_LIMIT": "SKIP (not in interface)",
    }

    fig, ax = plt.subplots(figsize=(9, 5))
    for v in verdicts:
        vals = [counts[p][v] for p in platforms]
        bars = ax.bar(x, vals, bottom=bottom, color=color_map[v],
                      edgecolor="black", linewidth=0.4, label=label_map[v])
        for bar, val, b in zip(bars, vals, bottom):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, b + val / 2,
                        str(val), ha="center", va="center",
                        color="white", fontweight="bold")
        bottom += np.array(vals)

    ax.set_xticks(x)
    ax.set_xticklabels(platforms)
    ax.set_ylabel("Number of commands")
    ax.set_title("Per-command verdicts by platform")
    ax.legend(loc="upper right")
    return save(fig, "fig07_interop_verdicts.png")


# =====================================================================
# 8. INTEROPERABILITY: NATIVE vs COMPENSATORY
# =====================================================================

def chart_interop_implementation() -> Path:
    rows = read_csv(ROOT / "interoperability_results.csv")
    platforms = sorted({r["platform"] for r in rows})
    impl_counts = {p: {"NATIVE": 0, "COMPENSATORY": 0, "N/A": 0} for p in platforms}
    for r in rows:
        impl_counts[r["platform"]][r["implementation"]] += 1

    x = np.arange(len(platforms))
    width = 0.32
    natives = [impl_counts[p]["NATIVE"] for p in platforms]
    comps = [impl_counts[p]["COMPENSATORY"] for p in platforms]
    nas = [impl_counts[p]["N/A"] for p in platforms]

    fig, ax = plt.subplots(figsize=(9, 5))
    b1 = ax.bar(x - width, natives, width, label="NATIVE",
                color=COLORS["native_impl"], edgecolor="black", linewidth=0.4)
    b2 = ax.bar(x, comps, width, label="COMPENSATORY",
                color=COLORS["compensatory"], edgecolor="black", linewidth=0.4)
    b3 = ax.bar(x + width, nas, width, label="N/A (framework limit)",
                color=COLORS["skip"], edgecolor="black", linewidth=0.4)
    for bars, vals in [(b1, natives), (b2, comps), (b3, nas)]:
        for bar, v in zip(bars, vals):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, v + 0.2,
                        str(v), ha="center", fontweight="bold", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(platforms)
    ax.set_ylabel("Number of commands")
    ax.set_title("Implementation type per platform: native vs compensatory")
    ax.legend(loc="upper right")
    ax.set_ylim(0, 12)
    return save(fig, "fig08_interop_implementation.png")


# =====================================================================
# 9. INTEROPERABILITY: timing per command per platform (heatmap)
# =====================================================================

def chart_interop_timing() -> Path:
    rows = read_csv(ROOT / "interoperability_results.csv")
    platforms = sorted({r["platform"] for r in rows})
    commands_seen: List[str] = []
    for r in rows:
        if r["command"] not in commands_seen:
            commands_seen.append(r["command"])

    matrix = np.zeros((len(platforms), len(commands_seen)))
    for r in rows:
        i = platforms.index(r["platform"])
        j = commands_seen.index(r["command"])
        try:
            matrix[i, j] = float(r["elapsed_ms"])
        except ValueError:
            matrix[i, j] = 0.0

    fig, ax = plt.subplots(figsize=(13, 4.2))
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")

    ax.set_xticks(np.arange(len(commands_seen)))
    ax.set_xticklabels(commands_seen, rotation=40, ha="right")
    ax.set_yticks(np.arange(len(platforms)))
    ax.set_yticklabels(platforms)

    for i in range(len(platforms)):
        for j in range(len(commands_seen)):
            v = matrix[i, j]
            txt_color = "white" if v > matrix.max() * 0.55 else "black"
            ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                    color=txt_color, fontsize=8)

    fig.colorbar(im, ax=ax, label="elapsed time (ms)", shrink=0.8)
    ax.set_title("Per-command execution time (ms) — heat map by platform")
    ax.grid(False)
    return save(fig, "fig09_interop_timing.png")


# =====================================================================
# 10. INTEROPERABILITY: verdict matrix
# =====================================================================

def chart_interop_matrix() -> Path:
    rows = read_csv(ROOT / "interoperability_results.csv")
    platforms = sorted({r["platform"] for r in rows})
    commands_seen: List[str] = []
    for r in rows:
        if r["command"] not in commands_seen:
            commands_seen.append(r["command"])

    code_map = {"PASS": 3, "PARTIAL": 2, "FAIL": 0, "FRAMEWORK_LIMIT": 1}
    label_map = {3: "PASS", 2: "PART", 1: "SKIP", 0: "FAIL"}
    matrix = np.zeros((len(platforms), len(commands_seen)))
    for r in rows:
        i = platforms.index(r["platform"])
        j = commands_seen.index(r["command"])
        matrix[i, j] = code_map.get(r["result"], 0)

    cmap = matplotlib.colors.ListedColormap([
        COLORS["fail"], COLORS["skip"], COLORS["partial"], COLORS["pass"]
    ])

    fig, ax = plt.subplots(figsize=(13, 4.2))
    ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=3)

    ax.set_xticks(np.arange(len(commands_seen)))
    ax.set_xticklabels(commands_seen, rotation=40, ha="right")
    ax.set_yticks(np.arange(len(platforms)))
    ax.set_yticklabels(platforms)

    for i in range(len(platforms)):
        for j in range(len(commands_seen)):
            ax.text(j, i, label_map[int(matrix[i, j])],
                    ha="center", va="center",
                    color="white", fontweight="bold", fontsize=9)

    # Custom legend
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=COLORS["pass"], label="PASS"),
        plt.Rectangle((0, 0), 1, 1, color=COLORS["partial"], label="PARTIAL"),
        plt.Rectangle((0, 0), 1, 1, color=COLORS["skip"], label="SKIP (not in interface)"),
        plt.Rectangle((0, 0), 1, 1, color=COLORS["fail"], label="FAIL"),
    ]
    ax.legend(handles=legend_handles, loc="upper left",
              bbox_to_anchor=(1.0, 1.0), framealpha=1)
    ax.set_title("Per-command verdict matrix")
    ax.grid(False)
    return save(fig, "fig10_interop_matrix.png")


# =====================================================================
# Summary dashboard (4-panel)
# =====================================================================

def chart_dashboard() -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("Unified Drone Framework — Evaluation Dashboard",
                 fontsize=16, fontweight="bold", y=1.00)

    # Panel 1: Effort metrics
    ax = axes[0, 0]
    rows = read_csv(ROOT / "effort_comparison.csv")
    metric_map = {r["metric"]: r for r in rows}
    short_metrics = [
        ("LOC", "lines_of_code"),
        ("Imports", "import_statements"),
        ("API calls", "distinct_api_calls"),
        ("Drone vars", "drone_object_variables"),
        ("If blocks", "if_blocks"),
        ("Try/except", "try_except_blocks"),
    ]
    labels = [m[0] for m in short_metrics]
    a_vals = [int(metric_map[m[1]]["version_a_framework"]) for m in short_metrics]
    b_vals = [int(metric_map[m[1]]["version_b_native"]) for m in short_metrics]
    x = np.arange(len(labels))
    width = 0.38
    ax.bar(x - width / 2, a_vals, width, label="Framework",
           color=COLORS["framework"], edgecolor="black", linewidth=0.4)
    ax.bar(x + width / 2, b_vals, width, label="Native",
           color=COLORS["native"], edgecolor="black", linewidth=0.4)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20)
    ax.set_title("Effort metrics (framework vs native)")
    ax.legend()

    # Panel 2: Verdicts per platform
    ax = axes[0, 1]
    rows = read_csv(ROOT / "interoperability_results.csv")
    platforms = sorted({r["platform"] for r in rows})
    verdicts = ["PASS", "PARTIAL", "FRAMEWORK_LIMIT", "FAIL"]
    counts = {p: {v: 0 for v in verdicts} for p in platforms}
    for r in rows:
        counts[r["platform"]][r["result"]] += 1
    x = np.arange(len(platforms))
    bottom = np.zeros(len(platforms))
    cmap_v = {"PASS": COLORS["pass"], "PARTIAL": COLORS["partial"],
              "FRAMEWORK_LIMIT": COLORS["skip"], "FAIL": COLORS["fail"]}
    for v in verdicts:
        vals = [counts[p][v] for p in platforms]
        ax.bar(x, vals, bottom=bottom, label=v, color=cmap_v[v],
               edgecolor="black", linewidth=0.4)
        bottom += np.array(vals)
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace("mock_", "") for p in platforms], rotation=15)
    ax.set_title("Interoperability verdicts (mock mode)")
    ax.set_ylabel("commands")
    ax.legend(fontsize=8, loc="lower right")

    # Panel 3: NATIVE vs COMPENSATORY
    ax = axes[1, 0]
    impl_counts = {p: {"NATIVE": 0, "COMPENSATORY": 0, "N/A": 0} for p in platforms}
    for r in rows:
        impl_counts[r["platform"]][r["implementation"]] += 1
    x = np.arange(len(platforms))
    width = 0.32
    natives = [impl_counts[p]["NATIVE"] for p in platforms]
    comps = [impl_counts[p]["COMPENSATORY"] for p in platforms]
    nas = [impl_counts[p]["N/A"] for p in platforms]
    ax.bar(x - width, natives, width, label="NATIVE",
           color=COLORS["native_impl"], edgecolor="black", linewidth=0.4)
    ax.bar(x, comps, width, label="COMPENSATORY",
           color=COLORS["compensatory"], edgecolor="black", linewidth=0.4)
    ax.bar(x + width, nas, width, label="N/A",
           color=COLORS["skip"], edgecolor="black", linewidth=0.4)
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace("mock_", "") for p in platforms], rotation=15)
    ax.set_title("Implementation type per platform")
    ax.legend(fontsize=8)

    # Panel 4: Extensibility hours
    ax = axes[1, 1]
    labels = ["Extensible\n(framework)", "Non-extensible\n(hypothetical)"]
    hours = [8.00, 12.80]
    bars = ax.bar(labels, hours, color=[COLORS["framework"], COLORS["native"]],
                  edgecolor="black", linewidth=0.4, width=0.5)
    for bar, h in zip(bars, hours):
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.2, f"{h:.1f} h",
                ha="center", fontweight="bold")
    ax.set_title("Effort to add a new drone platform")
    ax.set_ylabel("developer-hours")
    ax.set_ylim(0, 15)

    fig.tight_layout()
    return save(fig, "fig00_dashboard.png")


# =====================================================================
# Entry point
# =====================================================================


def main() -> None:
    print("Generating charts...")
    funcs = [
        chart_dashboard,
        chart_extensibility_loc,
        chart_extensibility_compliance,
        chart_extensibility_effort,
        chart_effort_metrics,
        chart_effort_reduction,
        chart_effort_reusability,
        chart_interop_verdicts,
        chart_interop_implementation,
        chart_interop_timing,
        chart_interop_matrix,
    ]
    paths = []
    for fn in funcs:
        try:
            p = fn()
            paths.append(p)
            print(f"  + {p.name}")
        except Exception as e:
            print(f"  ! {fn.__name__} failed: {e}")
    print(f"\n{len(paths)} charts written to {CHARTS_DIR}/")


if __name__ == "__main__":
    main()
