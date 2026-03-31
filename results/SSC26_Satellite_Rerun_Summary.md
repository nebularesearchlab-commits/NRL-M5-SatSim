# SSC26 Satellite Rerun Results Summary

## Run Context

| Field | Value |
|---|---|
| Generated UTC | 2026-03-27T19:47:27.936935+00:00 |
| Runtime (seconds) | 141.6801 |
| Graph rule | kNN normalized orbital feature graph |
| k-neighbors | 6 |
| Node count | 3000 |
| Edge count | 11990 |
| Graph signature (SHA-256) | 379e28fdce5813b977a4ea1ae04873a2f56256b0dd3e13e84cb5d385327ec025 |
| Autonomy config hash (SHA-256) | 330e040ec900889345eea2b714f8d5b345a3f68c5d18c548c159ae17a6c2f1f3 |

## Data Labeling Integrity

| Layer | Label |
|---|---|
| Raw data | empirical snapshot inputs |
| Edges | notional coordination topology |
| Outputs | simulated protocol outputs |

## Regular vs Enhanced (Same Graph)

| Metric | Regular | Enhanced | Match |
|---|---:|---:|---|
| Global efficiency (full) | 0.0976056277 | 0.0976056277 | Yes |
| Avg path length (full) | inf | inf | Yes |
| Modularity (full) | 0.9022723828 | 0.9022723828 | Yes |
| LCC fraction (full) | 0.9753333333 | 0.9753333333 | Yes |
| Compression ratio | 9.2307692308 | 9.2307692308 | Yes |

## Autonomy Outcome (Enhanced)

| Field | Value |
|---|---:|
| Converged | False |
| Decision | None |
| Rounds | 200 |
| rho_mean | 0.9160213675 |
| rho_min | 0.125 |
| rho_max | 1.0 |
| q_mean | 0.0207858584 |
| x_mean | 0.0202320756 |
| x_std | 0.1633176117 |

## Compression / Fidelity Snapshot

| Metric | Full network | Compressed network |
|---|---:|---:|
| Global efficiency | 0.0976056277 | 0.2846139149 |
| Avg path length | inf | inf |
| Modularity | 0.9022723828 | N/A |
| LCC fraction | 0.9753333333 | N/A |
| Compression ratio | 9.2307692308 | N/A |

## Notes for Scholarly Integrity

- Regular and Enhanced were run on the same constructed graph for parity.
- Structural metric parity does not imply autonomy convergence.
- Non-convergence at bounded rounds is reported as an observed calibration result.
- This is a methods calibration study; no mission/flight validation is claimed.

