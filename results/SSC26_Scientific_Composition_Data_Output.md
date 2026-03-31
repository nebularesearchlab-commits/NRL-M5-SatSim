# SSC26 Scientific Composition of Data Outputs

## Abstract

This document composes the scientific meaning of four rerun artifacts: `regular_vs_enhanced_metrics.csv`, `autonomy_convergence_summary.csv`, `compression_fidelity_table.csv`, and `run_config.json`. The run applies a regular M5 pipeline and an enhanced M5 pipeline (with autonomy layer) to the same satellite-derived graph, under fixed autonomy settings and bounded rounds. The main result is structural parity between regular and enhanced outputs on full-network metrics, paired with autonomy non-convergence at the configured round budget. This pattern supports a calibration interpretation: the structural diagnostics/compression/measurement stack is stable under parity conditions, while local decision dynamics remain sensitive to bounded-horizon constraints and current parameterization.

## Run Configuration and Reproducibility Record

Source: `satellite-rerun-ssc26/results/run_config.json`

- Generated UTC: `2026-03-27T20:30:30.334810+00:00`
- Runtime: `145.3887689113617 s`
- Autonomy settings:
  - `alpha = 0.1`
  - `theta_var = 0.01`
  - `theta_agree = 0.8`
  - `K_stable = 5`
  - `theta_high = 0.9`
  - `theta_low = 0.5`
  - `use_synergy_gate = false`
  - `max_steps = 200`
- Config hash: `330e040ec900889345eea2b714f8d5b345a3f68c5d18c548c159ae17a6c2f1f3`
- Parity note: regular and enhanced were run on the same graph.

## Primary Comparative Result (Regular vs Enhanced)

Source: `satellite-rerun-ssc26/results/regular_vs_enhanced_metrics.csv`

| Metric | Regular | Enhanced | Match |
|---|---:|---:|---|
| Global efficiency (full) | 0.09760562769808517 | 0.09760562769808517 | Yes |
| Avg path length (full) | inf | inf | Yes |
| Modularity (full) | 0.9022723827569561 | 0.9022723827569561 | Yes |
| LCC fraction (full) | 0.9753333333333334 | 0.9753333333333334 | Yes |
| Compression ratio | 9.23076923076923 | 9.23076923076923 | Yes |

### Interpretation

Under strict parity conditions, downstream structural metrics are identical between regular and enhanced runs. This supports the claim that adding the autonomy layer did not alter Stage 2/3 structural outputs in this configuration.

## Autonomy-Layer Outcome

Source: `satellite-rerun-ssc26/results/autonomy_convergence_summary.csv`

| Field | Value |
|---|---:|
| Converged | False |
| Decision | None |
| Rounds | 200 |
| rho_mean | 0.9160213675213675 |
| rho_min | 0.125 |
| rho_max | 1.0 |
| q_mean | 0.02078585837410737 |
| x_mean | 0.020232075554788852 |
| x_std | 0.16331761170233827 |

### Interpretation

The autonomy layer did not reach convergence within the configured horizon (`max_steps = 200`). Agreement statistics are high on average (`rho_mean ≈ 0.916`), but this did not satisfy global convergence conditions. This is scientifically reportable as a bounded-round non-convergence outcome, not an execution failure.

## Compression and Fidelity Context

Source: `satellite-rerun-ssc26/results/compression_fidelity_table.csv`

| Metric | Full network | Compressed network |
|---|---:|---:|
| Global efficiency | 0.09760562769808517 | 0.2846139148915677 |
| Avg path length | inf | inf |
| Modularity | 0.9022723827569561 | N/A |
| LCC fraction | 0.9753333333333334 | N/A |
| Compression ratio | 9.23076923076923 | N/A |

### Interpretation

The run reports substantial compression (`~9.23x`) with changed efficiency values between full and compressed representations. This reinforces that compression performance should be interpreted as approximation behavior rather than strict metric invariance across all measures.

## Scientific Integrity Statement

1. Results are presented exactly as exported by the run artifacts.
2. Non-convergence is reported explicitly and retained as evidence.
3. Structural parity is reported without claiming autonomy success.
4. Claims remain method-level (calibration and evaluation), not flight validation.

## Conclusion

This rerun provides a coherent calibration result for satellite-relevant network methodology: the regular and enhanced pipelines are structurally consistent under parity testing, while autonomy dynamics remain non-convergent under the current bounded-horizon settings. The data support a next-step research trajectory focused on convergence criteria, coupling/weight behavior, and horizon sensitivity analyses rather than structural pipeline redesign.

