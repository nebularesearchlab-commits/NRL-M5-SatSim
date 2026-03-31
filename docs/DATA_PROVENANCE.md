# Data Provenance

This document tracks origin, retrieval context, and data handling for the
Nebula SSC26 satellite rerun package.

## Ownership statement

- Current rerun work is independent Nebula Research Lab work.
- CAS 502 assets are historical baseline and method reference only.

## Input datasets currently in package

| File | Current path | Observed format | Label |
|------|--------------|-----------------|-------|
| Iridium Next.json | `data/raw/Iridium Next.json` | JSON array of orbital-element records | Empirical orbital catalog data snapshot |
| OneWeb.json | `data/raw/OneWeb.json` | JSON array of orbital-element records | Empirical orbital catalog data snapshot |
| Starlink.json | `data/raw/Starlink.json` | JSON array of orbital-element records | Empirical orbital catalog data snapshot |

## Retrieval/source metadata

The current rerun package uses CelesTrak GP element sets as the upstream catalog
source for all three constellation snapshots. The exact local retrieval UTC used
to generate the archived JSON files was not preserved in the current artifact
set. To avoid fabricating provenance, the table below records the confirmed
upstream source endpoints and the source-platform status observed during this
review.

| File | Source URL | Retrieval UTC | License/usage notes |
|------|------------|---------------|---------------------|
| Iridium Next.json | `https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-NEXT&FORMAT=json` | Exact local retrieval UTC not preserved in current artifact set. Source platform page observed "Current as of 2026 Mar 30 12:22:26 UTC" during provenance review. | CelesTrak redistributes current GP element sets. Final submission should cite CelesTrak as source platform and verify any additional reuse/attribution language required at time of submission. |
| OneWeb.json | `https://celestrak.org/NORAD/elements/gp.php?GROUP=oneweb&FORMAT=json` | Exact local retrieval UTC not preserved in current artifact set. Source platform page observed "Current as of 2026 Mar 30 12:22:26 UTC" during provenance review. | CelesTrak redistributes current GP element sets. Final submission should cite CelesTrak as source platform and verify any additional reuse/attribution language required at time of submission. |
| Starlink.json | `https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=json` | Exact local retrieval UTC not preserved in current artifact set. Source platform page observed "Current as of 2026 Mar 30 12:22:26 UTC" during provenance review. | CelesTrak redistributes current GP element sets. Final submission should cite CelesTrak as source platform and verify any additional reuse/attribution language required at time of submission. |

## Temporal interpretation used in graph construction

- The processed graph preserves record-level `EPOCH` values for each object.
- The current build artifacts do **not** document propagation of all objects to a
  single common epoch.
- Therefore, the defensible interpretation for the present rerun is:
  **native catalog epochs were preserved as provided in the source snapshots,
  and graph construction operated on those record-level orbital fields without a
  separately archived common-epoch propagation step.**
- This interpretation is consistent with `graph_nodes.csv`, which stores one
  `epoch` value per node, and with the current graph-building implementation,
  which copies `EPOCH` from each validated record into node metadata.

## Graph-construction logic trace (implementation-derived)

The following summary is derived directly from
`satellite-rerun-ssc26/src/validate_dataset.py` and
`satellite-rerun-ssc26/src/build_graph.py` so the manuscript can describe the
actual v1 graph rule without relying on memory.

### Validation stage

- Required keys enforced before copying to `data_raw/`:
  `OBJECT_NAME`, `OBJECT_ID`, `EPOCH`, `MEAN_MOTION`, `INCLINATION`,
  `NORAD_CAT_ID`
- Files must be:
  - non-empty
  - valid JSON
  - list-structured
  - free of non-dictionary rows
  - free of rows missing required keys

### Deterministic graph rule (v1)

Pseudo-logic:

1. Load all `*.json` files from the input directory in sorted filename order.
2. Append `_source_file = path.name` to each record.
3. Deterministically sort all records by:
   - `NORAD_CAT_ID`
   - `OBJECT_ID`
   - `OBJECT_NAME`
4. Deduplicate by `NORAD_CAT_ID`, keeping the **first** record after sorting.
5. Truncate to `max_nodes = 3000` after deduplication.
6. Build a feature matrix from:
   - `MEAN_MOTION`
   - `INCLINATION`
   - `RA_OF_ASC_NODE`
   - `MEAN_ANOMALY`
   - `ECCENTRICITY`
7. Apply **global z-score normalization across the merged record set**:
   - `mean = matrix.mean(axis=0)`
   - `std = matrix.std(axis=0)`
   - any zero standard deviation is replaced with `1.0`
8. Query a `cKDTree` for `k + 1` neighbors per node (self included at rank 0),
   with `k_neighbors = 6`.
9. Build an undirected graph by symmetrizing neighbor pairs:
   - sort node pair as `(a, b)`
   - if the pair appears more than once, keep the **minimum** distance
10. Assign edge weights as:
    - `weight = 1 / (1 + distance)`

### Placeholder status resolved from code

- Z-score normalization scope:
  **global across the merged catalog**, not separately by source file.
- Tie-breaking rule:
  no explicit secondary manuscript-level tie-break is implemented beyond the
  `cKDTree` neighbor query and the deterministic "keep minimum distance for the
  undirected pair" rule during symmetrization.
- Inclusion/exclusion rule for the 3000-node graph:
  deterministic load -> sort -> dedupe by `NORAD_CAT_ID` -> truncate to first
  3000 records.
- Row dropping:
  no additional row drop stage is applied inside `build_graph.py`; rows are
  excluded earlier only if they fail validation, are duplicate `NORAD_CAT_ID`
  entries removed by deterministic deduplication, or fall beyond the
  `max_nodes = 3000` cutoff.

## Environment traceability

- Reproducibility guide baseline:
  - Python: `3.9+`
  - Install command: `pip install -r requirements.txt`
- Current dependency specification in `requirements.txt`:
  - `numpy>=1.20,<3`
  - `pandas>=1.3,<3`
  - `networkx>=3.0,<4`
  - `python-louvain>=0.16`
  - `scipy>=1.7,<2`
  - `matplotlib>=3.4,<4`
  - `seaborn>=0.11,<1`
- Exact installed package versions for the archived rerun were **not** exported
  into the current artifact bundle.
- No pinned lockfile, container digest, or archival package identifier is
  currently recorded in this file set.

## Reference / provenance note for manuscript

Recommended source-platform reference anchor for the paper:

- CelesTrak, "Current GP Element Sets," `https://celestrak.org/NORAD/elements/`
  with constellation-specific JSON endpoints used for `Iridium NEXT`,
  `OneWeb`, and `Starlink`.
- GitHub repository archive for this reproducibility package:
  `https://github.com/nebularesearchlab-commits/NRL-M5-SatSim`
- Graphical visual database outputs are generated into:
  `results/figures/*.png`

## Handling policy

1. Keep raw inputs immutable in `data/raw/`.
2. Perform all transformations via scripts only (no manual record edits).
3. Save deterministic processed outputs to `data/processed/`.
4. Record any data refresh in this file with new UTC timestamp and source.

## Integrity checks required per run

- Non-zero file size
- Valid JSON parse
- Record count > 0
- Required fields present:
  `OBJECT_NAME`, `OBJECT_ID`, `EPOCH`, `MEAN_MOTION`, `INCLINATION`,
  `NORAD_CAT_ID`

