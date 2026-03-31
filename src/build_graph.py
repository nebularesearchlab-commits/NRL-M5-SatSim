"""
Build a deterministic satellite coordination graph from orbital JSON records.

Edge model (v1): k-nearest-neighbors over normalized orbital features.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx
import numpy as np
from scipy.spatial import cKDTree


FEATURE_COLUMNS = [
    "MEAN_MOTION",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "MEAN_ANOMALY",
    "ECCENTRICITY",
]


def _load_records(input_dir: Path) -> List[Dict[str, object]]:
    """Load and concatenate JSON records, then sort for deterministic ordering."""
    records: List[Dict[str, object]] = []
    for path in sorted(input_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        for row in data:
            if isinstance(row, dict):
                row = dict(row)
                row["_source_file"] = path.name
                records.append(row)

    # Deterministic order is critical because graph node indexing depends on it.
    records.sort(
        key=lambda row: (
            str(row.get("NORAD_CAT_ID", "")),
            str(row.get("OBJECT_ID", "")),
            str(row.get("OBJECT_NAME", "")),
        )
    )
    return records


def _dedupe_by_norad(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Keep first record per NORAD_CAT_ID after deterministic sorting."""
    deduped: List[Dict[str, object]] = []
    seen = set()
    for row in records:
        norad = row.get("NORAD_CAT_ID")
        if norad in seen:
            continue
        seen.add(norad)
        deduped.append(row)
    return deduped


def _build_feature_matrix(records: List[Dict[str, object]]) -> np.ndarray:
    """Create normalized numeric matrix used by kNN."""
    matrix = np.array(
        [[float(row[col]) for col in FEATURE_COLUMNS] for row in records],
        dtype=float,
    )
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    std[std == 0] = 1.0
    return (matrix - mean) / std


def _build_graph(records: List[Dict[str, object]], k_neighbors: int) -> Tuple[nx.Graph, Dict[Tuple[int, int], float]]:
    """Construct an undirected weighted kNN graph and return distance map."""
    features = _build_feature_matrix(records)
    n = features.shape[0]
    if n < 2:
        raise ValueError("Need at least 2 records to build a graph.")

    k = min(k_neighbors, n - 1)
    tree = cKDTree(features)
    distances, indices = tree.query(features, k=k + 1)  # includes self at index 0

    graph = nx.Graph()
    for idx, row in enumerate(records):
        graph.add_node(
            idx,
            norad_cat_id=row.get("NORAD_CAT_ID"),
            object_id=row.get("OBJECT_ID"),
            object_name=row.get("OBJECT_NAME"),
            source_file=row.get("_source_file"),
            epoch=row.get("EPOCH"),
        )

    distance_map: Dict[Tuple[int, int], float] = {}
    for i in range(n):
        for rank in range(1, k + 1):
            j = int(indices[i][rank])
            d = float(distances[i][rank])
            if i == j:
                continue
            a, b = sorted((i, j))
            prev = distance_map.get((a, b))
            if prev is None or d < prev:
                distance_map[(a, b)] = d

    for (a, b), distance in sorted(distance_map.items()):
        weight = 1.0 / (1.0 + distance)
        graph.add_edge(a, b, weight=weight, distance=distance)

    return graph, distance_map


def _write_outputs(
    output_dir: Path,
    records: List[Dict[str, object]],
    graph: nx.Graph,
    distance_map: Dict[Tuple[int, int], float],
    k_neighbors: int,
) -> Path:
    """Write deterministic edge/node artifacts and graph metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)
    edges_csv = output_dir / "graph_edges.csv"
    nodes_csv = output_dir / "graph_nodes.csv"
    metadata_path = output_dir / "graph_metadata.json"

    with edges_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["u", "v", "weight", "distance"])
        for u, v, attrs in sorted(graph.edges(data=True), key=lambda item: (item[0], item[1])):
            writer.writerow([u, v, attrs["weight"], attrs["distance"]])

    with nodes_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["node_index", "norad_cat_id", "object_id", "object_name", "source_file", "epoch"])
        for idx, row in enumerate(records):
            writer.writerow(
                [
                    idx,
                    row.get("NORAD_CAT_ID"),
                    row.get("OBJECT_ID"),
                    row.get("OBJECT_NAME"),
                    row.get("_source_file"),
                    row.get("EPOCH"),
                ]
            )

    graph_signature = hashlib.sha256(
        json.dumps(
            {
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "k_neighbors": k_neighbors,
                "feature_columns": FEATURE_COLUMNS,
                "edge_pairs": sorted([list(pair) for pair in distance_map.keys()]),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    metadata = {
        "graph_rule": "kNN normalized orbital feature graph",
        "labeling": {
            "raw_data": "empirical snapshot inputs",
            "edges": "notional coordination topology",
            "outputs": "simulated protocol outputs",
        },
        "feature_columns": FEATURE_COLUMNS,
        "k_neighbors": k_neighbors,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "graph_signature_sha256": graph_signature,
        "nodes_csv": str(nodes_csv),
        "edges_csv": str(edges_csv),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic kNN graph from satellite JSON.")
    parser.add_argument("--input-dir", default="satellite-rerun-ssc26/data_raw")
    parser.add_argument("--output-dir", default="satellite-rerun-ssc26/data_processed")
    parser.add_argument("--k-neighbors", type=int, default=6)
    parser.add_argument("--max-nodes", type=int, default=3000)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    records = _load_records(input_dir)
    if not records:
        print(f"ERROR: no records found in {input_dir}")
        return 1

    deduped = _dedupe_by_norad(records)
    if args.max_nodes > 0:
        deduped = deduped[: args.max_nodes]

    graph, distance_map = _build_graph(deduped, args.k_neighbors)
    metadata_path = _write_outputs(output_dir, deduped, graph, distance_map, args.k_neighbors)

    print(f"records_loaded: {len(records)}")
    print(f"records_deduped: {len(deduped)}")
    print(f"graph_nodes: {graph.number_of_nodes()}")
    print(f"graph_edges: {graph.number_of_edges()}")
    print(f"metadata_written: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

