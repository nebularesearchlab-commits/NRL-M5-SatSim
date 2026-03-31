# Reproducibility Guide

This guide describes how to reproduce the paper outputs in this minimal bundle.

Repository reference:
`https://github.com/nebularesearchlab-commits/NRL-M5-SatSim`

## Runtime baseline

- Python: 3.9+
- Install dependencies:
  `pip install -r requirements.txt`

## Canonical inputs and artifacts

- Raw inputs: `data/raw/Iridium Next.json`, `data/raw/OneWeb.json`, `data/raw/Starlink.json`
- Processed graph: `data/processed/graph_metadata.json`, `graph_nodes.csv`, `graph_edges.csv`
- Paper-result exports: `results/regular_vs_enhanced_metrics.csv`, `results/autonomy_convergence_summary.csv`, `results/compression_fidelity_table.csv`, `results/run_config.json`

## Fast path (recommended)

Run `notebooks/Satellite_M5_Rerun.ipynb` in default mode to:

1. Load existing CSV artifacts.
2. Regenerate paper-facing figures under `results/figures/`.
3. Verify expected artifact presence.
4. Confirm generated visual outputs in `results/figures/` (`.png` files).

## Full rerun path (optional)

1. Validate raw inputs:
   `python3 src/validate_dataset.py --input-dir data/raw`
2. Build deterministic graph artifacts:
   `python3 src/build_graph.py --input-dir data/raw --output-dir data/processed --k-neighbors 6 --max-nodes 3000`
3. Run regular and enhanced pipelines:
   `python3 src/run_satellite_rerun.py --graph-metadata data/processed/graph_metadata.json --results-dir results --betweenness-samples 200 --alpha 0.1 --theta-var 0.01 --theta-agree 0.8 --k-stable 5 --max-steps 200`

## Integrity notes

- `m5_autonomy.py` seeds initial autonomy state with `np.random.seed(42)` when `x_init` is not provided.
- `run_satellite_rerun.py` logs autonomy config and config hash in `results/run_config.json`.
- Report convergence and non-convergence exactly as observed; no flight-validation claim is implied by this methods package.

