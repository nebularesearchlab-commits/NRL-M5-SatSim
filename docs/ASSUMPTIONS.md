# Assumptions and Modeling Rules

This file defines how orbital-element JSON is converted into a graph for M5 and
Enhanced M5 reruns.

## Ownership and claim scope

- This is a Nebula methods calibration workflow.
- It does not claim mission-specific or flight-validated ISL behavior.

## Data labeling convention

- Raw orbital records (`Dataset/*.json`): **empirical snapshot inputs**
- Constructed graph edges: **notional coordination topology**
- Rerun metrics/autonomy outcomes: **simulated protocol outputs**

## Node definition

- One node per unique `NORAD_CAT_ID`.
- Node attributes include:
  `OBJECT_NAME`, `OBJECT_ID`, `EPOCH`, `MEAN_MOTION`, `ECCENTRICITY`,
  `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`.

## Edge definition (v1 frozen model)

Primary model for v1:

- **k-nearest-neighbors (kNN)** in normalized orbital feature space.
- Feature vector:
  `[MEAN_MOTION, INCLINATION, RA_OF_ASC_NODE, MEAN_ANOMALY, ECCENTRICITY]`
- Distance metric: Euclidean distance after z-score normalization.
- Directed kNN links are symmetrized into an undirected graph.
- Default `k = 6` (configurable and logged in metadata).

## Edge weights

- Weight formula: `1 / (1 + distance)`
- Weights are deterministic from feature vectors and kNN outputs.

## Determinism and reproducibility

- Records are sorted by `NORAD_CAT_ID` before graph construction.
- Fixed feature ordering is used.
- kNN and symmetrization are deterministic for fixed inputs.
- All rule parameters are written to graph metadata.

## Comparability constraints

- Regular and Enhanced runs use the same constructed graph.
- Enhanced autonomy config is fixed unless a documented parameter sweep is
  explicitly declared and logged.

