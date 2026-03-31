"""
Run regular and enhanced M5-style pipelines on the same satellite graph.

This script is designed for reproducible methods reporting:
- common graph input for regular and enhanced runs
- explicit autonomy config logging
- CSV exports for paper assembly
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

import networkx as nx
import numpy as np
import pandas as pd
from community import community_louvain

# This script lives under satellite-rerun-ssc26/src/, while m5_autonomy.py is
# at the workspace root. We add the root path explicitly for portable execution.
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from m5_autonomy import AutonomyConfig, run_autonomy_protocol


def load_graph_from_processed(metadata_path: Path) -> nx.Graph:
    """Rebuild graph from processed CSV artifacts."""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    nodes_csv = Path(metadata["nodes_csv"])
    edges_csv = Path(metadata["edges_csv"])

    graph = nx.Graph()

    nodes_df = pd.read_csv(nodes_csv)
    for _, row in nodes_df.iterrows():
        idx = int(row["node_index"])
        graph.add_node(
            idx,
            norad_cat_id=row["norad_cat_id"],
            object_id=row["object_id"],
            object_name=row["object_name"],
            source_file=row["source_file"],
            epoch=row["epoch"],
        )

    edges_df = pd.read_csv(edges_csv)
    for _, row in edges_df.iterrows():
        u = int(row["u"])
        v = int(row["v"])
        w = float(row["weight"])
        d = float(row["distance"])
        graph.add_edge(u, v, weight=w, distance=d)

    return graph


def _top_fraction(items: List[Tuple[object, float]], fraction: float) -> List[object]:
    count = max(1, int(math.ceil(len(items) * fraction)))
    return [item for item, _ in sorted(items, key=lambda kv: kv[1], reverse=True)[:count]]


def run_stage1_diagnostics(graph: nx.Graph, betweenness_samples: int = 200) -> Dict[str, object]:
    """Compute Stage 1 metrics and derive critical nodes/significant edges."""
    if graph.number_of_nodes() == 0:
        raise ValueError("Graph is empty; Stage 1 cannot run.")

    # Human-friendly note:
    # For large graphs, exact betweenness is expensive. Sampling keeps runtime practical.
    sample_k = min(betweenness_samples, max(1, graph.number_of_nodes() - 1))
    weighted_degree = {n: float(sum(d.get("weight", 1.0) for _, _, d in graph.edges(n, data=True))) for n in graph.nodes()}
    betweenness = nx.betweenness_centrality(graph, k=sample_k, normalized=True, seed=42, weight="distance")
    eigenvector = nx.eigenvector_centrality_numpy(graph, weight="weight")
    clustering = nx.clustering(graph, weight="weight")
    edge_betweenness = nx.edge_betweenness_centrality(graph, normalized=True, weight="distance")

    critical_nodes = _top_fraction(list(betweenness.items()), fraction=0.10)
    significant_edges = _top_fraction(list(edge_betweenness.items()), fraction=0.05)

    return {
        "localized_metrics": {
            "weighted_degree": weighted_degree,
            "betweenness": betweenness,
            "eigenvector": eigenvector,
            "clustering": clustering,
            "edge_betweenness": edge_betweenness,
        },
        "critical_nodes": critical_nodes,
        "significant_edges": significant_edges,
    }


def _compress_with_preservation(graph: nx.Graph, critical_nodes: Iterable[int]) -> Dict[str, object]:
    """Stage 2 compression via Louvain with critical-node singleton preservation."""
    if graph.number_of_nodes() == 0:
        raise ValueError("Graph is empty; Stage 2 cannot run.")

    partition = community_louvain.best_partition(graph, weight="weight", random_state=42)
    critical_set: Set[int] = set(int(n) for n in critical_nodes)

    # Keep critical nodes visible by mapping each to a singleton super-node.
    group_map: Dict[int, object] = {}
    for node, comm in partition.items():
        if node in critical_set:
            group_map[node] = ("critical", int(node))
        else:
            group_map[node] = ("community", int(comm))

    compressed = nx.Graph()
    for node in graph.nodes():
        grp = group_map[node]
        if grp not in compressed:
            compressed.add_node(grp)

    for u, v, attrs in graph.edges(data=True):
        gu = group_map[u]
        gv = group_map[v]
        if gu == gv:
            continue
        weight = float(attrs.get("weight", 1.0))
        if compressed.has_edge(gu, gv):
            compressed[gu][gv]["weight"] += weight
        else:
            compressed.add_edge(gu, gv, weight=weight)

    return {
        "partition": partition,
        "compressed_graph": compressed,
        "communities_count": len(set(partition.values())),
        "compression_ratio": graph.number_of_nodes() / max(1, compressed.number_of_nodes()),
        "original_nodes": graph.number_of_nodes(),
        "compressed_nodes": compressed.number_of_nodes(),
    }


def _average_path_length_safe(graph: nx.Graph) -> float:
    """Return finite avg path length for connected graph, else inf."""
    if graph.number_of_nodes() <= 1:
        return 0.0
    if nx.is_connected(graph):
        return float(nx.average_shortest_path_length(graph, weight=None))
    return float("inf")


def _lcc_fraction(graph: nx.Graph) -> float:
    """Largest connected component fraction."""
    if graph.number_of_nodes() == 0:
        return 0.0
    largest = max(nx.connected_components(graph), key=len)
    return len(largest) / graph.number_of_nodes()


def run_stage3_metrics(graph: nx.Graph, compressed_graph: nx.Graph, partition: Dict[int, int]) -> Dict[str, float]:
    """Compute full vs compressed metrics used in results tables."""
    modularity = community_louvain.modularity(partition, graph, weight="weight")
    full_eff = nx.global_efficiency(graph)
    comp_eff = nx.global_efficiency(compressed_graph) if compressed_graph.number_of_nodes() > 0 else 0.0

    return {
        "full_global_efficiency": float(full_eff),
        "compressed_global_efficiency": float(comp_eff),
        "full_avg_path_length": float(_average_path_length_safe(graph)),
        "compressed_avg_path_length": float(_average_path_length_safe(compressed_graph)),
        "full_modularity": float(modularity),
        "full_lcc_fraction": float(_lcc_fraction(graph)),
    }


def execute_regular_pipeline(graph: nx.Graph, betweenness_samples: int) -> Dict[str, object]:
    stage1 = run_stage1_diagnostics(graph, betweenness_samples=betweenness_samples)
    stage2 = _compress_with_preservation(graph, stage1["critical_nodes"])
    stage3 = run_stage3_metrics(graph, stage2["compressed_graph"], stage2["partition"])
    return {"stage1": stage1, "stage2": stage2, "stage3": stage3}


def execute_enhanced_pipeline(
    graph: nx.Graph, betweenness_samples: int, config: AutonomyConfig
) -> Dict[str, object]:
    stage1 = run_stage1_diagnostics(graph, betweenness_samples=betweenness_samples)
    autonomy = run_autonomy_protocol(graph, stage1_results=stage1, config=config)
    stage2 = _compress_with_preservation(graph, stage1["critical_nodes"])
    stage3 = run_stage3_metrics(graph, stage2["compressed_graph"], stage2["partition"])
    return {"stage1": stage1, "autonomy": autonomy, "stage2": stage2, "stage3": stage3}


def _write_csv(path: Path, headers: List[str], rows: List[List[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def export_results(
    results_dir: Path,
    regular: Dict[str, object],
    enhanced: Dict[str, object],
    config: AutonomyConfig,
    runtime_seconds: float,
) -> None:
    """Export required paper artifacts and run config."""
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = results_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    regular_m = regular["stage3"]
    enhanced_m = enhanced["stage3"]

    metrics_rows = [
        ["global_efficiency_full", regular_m["full_global_efficiency"], enhanced_m["full_global_efficiency"]],
        ["avg_path_length_full", regular_m["full_avg_path_length"], enhanced_m["full_avg_path_length"]],
        ["modularity_full", regular_m["full_modularity"], enhanced_m["full_modularity"]],
        ["lcc_fraction_full", regular_m["full_lcc_fraction"], enhanced_m["full_lcc_fraction"]],
        ["compression_ratio", regular["stage2"]["compression_ratio"], enhanced["stage2"]["compression_ratio"]],
    ]
    _write_csv(
        results_dir / "regular_vs_enhanced_metrics.csv",
        ["metric", "regular", "enhanced"],
        metrics_rows,
    )

    auto = enhanced["autonomy"]
    autonomy_rows = [
        ["converged", auto["converged"]],
        ["decision", auto["decision"]],
        ["rounds", auto["rounds"]],
        ["rho_mean", float(np.mean(auto["rho"]))],
        ["rho_min", float(np.min(auto["rho"]))],
        ["rho_max", float(np.max(auto["rho"]))],
        ["q_mean", float(np.mean(auto["q"]))],
        ["x_mean", float(np.mean(auto["x_final"]))],
        ["x_std", float(np.std(auto["x_final"]))],
    ]
    _write_csv(
        results_dir / "autonomy_convergence_summary.csv",
        ["field", "value"],
        autonomy_rows,
    )

    fidelity_rows = [
        ["global_efficiency", regular_m["full_global_efficiency"], regular_m["compressed_global_efficiency"]],
        ["avg_path_length", regular_m["full_avg_path_length"], regular_m["compressed_avg_path_length"]],
        ["modularity", regular_m["full_modularity"], ""],
        ["lcc_fraction", regular_m["full_lcc_fraction"], ""],
        ["compression_ratio", regular["stage2"]["compression_ratio"], ""],
    ]
    _write_csv(
        results_dir / "compression_fidelity_table.csv",
        ["metric", "full_network", "compressed_network"],
        fidelity_rows,
    )

    config_payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "autonomy_config": {
            "alpha": config.alpha,
            "theta_var": config.theta_var,
            "theta_agree": config.theta_agree,
            "K_stable": config.K_stable,
            "theta_high": config.theta_high,
            "theta_low": config.theta_low,
            "use_synergy_gate": config.use_synergy_gate,
            "max_steps": config.max_steps,
        },
        "runtime_seconds": runtime_seconds,
        "notes": "Regular and Enhanced run on same graph for parity.",
    }
    config_hash = hashlib.sha256(
        json.dumps(config_payload["autonomy_config"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    config_payload["autonomy_config_hash_sha256"] = config_hash
    (results_dir / "run_config.json").write_text(json.dumps(config_payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run satellite regular/enhanced M5 rerun.")
    parser.add_argument(
        "--graph-metadata",
        default="satellite-rerun-ssc26/data_processed/graph_metadata.json",
        help="Path to graph metadata generated by build_graph.py",
    )
    parser.add_argument(
        "--results-dir",
        default="satellite-rerun-ssc26/results",
        help="Directory for output CSV and JSON artifacts",
    )
    parser.add_argument("--betweenness-samples", type=int, default=200)
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--theta-var", type=float, default=0.01)
    parser.add_argument("--theta-agree", type=float, default=0.8)
    parser.add_argument("--k-stable", type=int, default=5)
    parser.add_argument("--max-steps", type=int, default=200)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph = load_graph_from_processed(Path(args.graph_metadata))

    config = AutonomyConfig(
        alpha=args.alpha,
        theta_var=args.theta_var,
        theta_agree=args.theta_agree,
        K_stable=args.k_stable,
        max_steps=args.max_steps,
    )

    start = time.time()
    regular = execute_regular_pipeline(graph, betweenness_samples=args.betweenness_samples)
    enhanced = execute_enhanced_pipeline(graph, betweenness_samples=args.betweenness_samples, config=config)
    runtime = time.time() - start

    export_results(Path(args.results_dir), regular, enhanced, config=config, runtime_seconds=runtime)

    print("RERUN_STATUS: PASS")
    print(f"runtime_seconds: {runtime:.2f}")
    print(f"regular_metrics: {Path(args.results_dir) / 'regular_vs_enhanced_metrics.csv'}")
    print(f"autonomy_summary: {Path(args.results_dir) / 'autonomy_convergence_summary.csv'}")
    print(f"compression_fidelity: {Path(args.results_dir) / 'compression_fidelity_table.csv'}")
    print(f"run_config: {Path(args.results_dir) / 'run_config.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

