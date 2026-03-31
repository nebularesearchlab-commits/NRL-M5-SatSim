"""
Autonomy Update Module — neural decision dynamics + wisdom-of-crowd fusion.
Integrates with M5 Protocol: Stage 1 → weights; runs until collective convergence.
"""
import numpy as np
import networkx as nx
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class AutonomyConfig:
    """Configuration for the Autonomy Update Module."""
    alpha: float = 0.1       # step size: (1-α)x + α*update
    theta_var: float = 0.01  # variance threshold: settled when var(x) < this
    theta_agree: float = 0.8 # min agreement (ρ) across nodes to consider converged
    K_stable: int = 5        # same decision for K consecutive rounds
    theta_high: float = 0.9  # synergy gate: high agreement → trust collective
    theta_low: float = 0.5   # synergy gate: low agreement → don't commit
    use_synergy_gate: bool = False
    max_steps: int = 200     # cap on autonomy rounds


def get_default_autonomy_config() -> AutonomyConfig:
    """Return the default autonomy configuration."""
    return AutonomyConfig()


def autonomy_update_node(
    i: int,
    x: np.ndarray,
    I: np.ndarray,
    W_adj: Dict[Tuple[int, int], float],
    neighbors_i: List[int],
    alpha: float,
    noise: float = 0.0,
) -> Tuple[float, int, float, float]:
    """Per-node update: neural dynamics → wisdom-of-crowd → agreement & fusion quality."""
    # Step A: neural dynamics — coupling from neighbors, Euler step
    sum_j = 0.0
    for j in neighbors_i:
        w_ij = W_adj.get((i, j), W_adj.get((j, i), 0.0))
        sum_j += w_ij * np.tanh(x[j])
    x_i_new = (1 - alpha) * x[i] + alpha * (I[i] + sum_j) + noise

    # Step B: wisdom-of-crowd — local average over self + neighbors
    x_sum = x_i_new + sum(x[j] for j in neighbors_i)
    n_neighbors = len(neighbors_i)
    denom = 1 + n_neighbors
    x_avg_i = x_sum / denom
    y_hat_i = int(np.sign(x_avg_i))  # binary: -1, 0, or 1

    # Step C: agreement (ρ) and fusion quality (q)
    # ρ (rho) = fraction of neighbors whose sign matches this node's local crowd decision y_hat_i
    if n_neighbors == 0:
        rho_i = 1.0  # isolated node: trivially in full agreement
    else:
        agree_count = sum(
            1 for j in neighbors_i
            if np.sign(x[j]) == y_hat_i or (y_hat_i == 0 and x[j] == 0)
        )
        rho_i = agree_count / n_neighbors
    # q = confidence in the local average (magnitude of x_avg_i)
    q_i = abs(x_avg_i)

    return (x_i_new, y_hat_i, rho_i, q_i)


def check_autonomy_converged(
    x: np.ndarray,
    agree: np.ndarray,
    K_history: List[str],
    theta_var: float,
    theta_agree: float,
    K_stable: int,
) -> Tuple[bool, Optional[str]]:
    """Global convergence: all nodes settled, agree, and decision stable for K rounds."""
    if len(x) == 0:
        return (False, None)
    if np.var(x) >= theta_var:  # states still dispersing
        return (False, None)
    if np.min(agree) < theta_agree:  # at least one node disagrees with local crowd
        return (False, None)
    if len(K_history) < K_stable:  # need more history before we can declare stability
        return (False, None)
    last_K = K_history[-K_stable:]
    # Require the same decision string (e.g. "A" or "B") for the last K_stable rounds
    if len(set(last_K)) != 1:  # decision flipped recently
        return (False, None)
    return (True, last_K[-1])


def execute_autonomy_round(
    G: nx.Graph,
    x: np.ndarray,
    I: np.ndarray,
    W_adj: Dict[Tuple[int, int], float],
    config: AutonomyConfig,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """One synchronous round: update all nodes, return (x_new, y_hat, rho, q)."""
    nodes = list(G.nodes())
    n = len(nodes)
    node_to_idx = {node: i for i, node in enumerate(nodes)}  # graph node id → array idx

    x_new = np.copy(x)
    y_hat = np.zeros(n, dtype=int)
    rho = np.zeros(n)
    q = np.zeros(n)

    for i in range(n):
        neighbors = list(G.neighbors(nodes[i]))
        neighbors_i = [node_to_idx[j] for j in neighbors if j in node_to_idx]
        xi_new, yh, rh, qi = autonomy_update_node(
            i, x, I, W_adj, neighbors_i, config.alpha, noise=0.0
        )
        x_new[i] = xi_new
        y_hat[i] = yh
        rho[i] = rh
        q[i] = qi

    return (x_new, y_hat, rho, q)


def build_weights_from_stage1(
    stage1_results: dict,
    G: nx.Graph,
) -> Dict[Tuple[int, int], float]:
    """
    Map Stage 1 metrics to edge weights W_adj.
    betweenness → weighted_degree → degree; normalize to [0, 1].
    """
    nodes = list(G.nodes())
    node_to_idx = {node: i for i, node in enumerate(nodes)}
    metrics = stage1_results.get("localized_metrics", {})

    # fallback chain: betweenness preferred, else degree-based
    if "betweenness" in metrics:
        centrality = metrics["betweenness"]
    elif "weighted_degree" in metrics:
        centrality = metrics["weighted_degree"]
    else:
        centrality = dict(G.degree())

    # edge weight = avg centrality of endpoints; key by integer indices (i, j) to match array indexing in autonomy
    W_adj = {}
    for u, v in G.edges():
        i, j = node_to_idx.get(u), node_to_idx.get(v)
        if i is None or j is None:
            continue
        c_u = centrality.get(u, 0.0)
        c_v = centrality.get(v, 0.0)
        w = (c_u + c_v) / 2.0
        W_adj[(i, j)] = w
        if not G.is_directed():
            W_adj[(j, i)] = w

    # normalize to max 1.0
    if W_adj:
        max_w = max(W_adj.values())
        if max_w > 0:
            W_adj = {k: v / max_w for k, v in W_adj.items()}

    return W_adj


def run_autonomy_protocol(
    G: nx.Graph,
    I: Optional[np.ndarray] = None,
    W_adj: Optional[Dict[Tuple[int, int], float]] = None,
    config: Optional[AutonomyConfig] = None,
    x_init: Optional[np.ndarray] = None,
    stage1_results: Optional[dict] = None,
) -> dict:
    """
    Orchestrate autonomy loop: init → rounds → check convergence.
    Returns dict with converged, decision, x_final, y_hat, rho, q, rounds.
    """
    config = config or get_default_autonomy_config()
    n = G.number_of_nodes()

    # init: local input I, edge weights W_adj, node state x
    if I is None:
        I = np.zeros(n)
    elif len(I) != n:
        raise ValueError(f"I length {len(I)} != graph size {n}")

    if W_adj is None:
        if stage1_results is None:
            raise ValueError("Either W_adj or stage1_results must be provided")
        W_adj = build_weights_from_stage1(stage1_results, G)

    if x_init is not None:
        x = np.asarray(x_init, dtype=float).copy()
        if len(x) != n:
            raise ValueError(f"x_init length {len(x)} != graph size {n}")
    else:
        np.random.seed(42)
        x = np.random.uniform(-0.1, 0.1, n)  # small random start

    # loop: each round updates all nodes, then we record a global decision for stability check
    # K_history stores the last K_stable decisions so we only declare converged when the same decision repeats
    K_history = []
    for round_idx in range(config.max_steps):
        x, y_hat, rho, q = execute_autonomy_round(G, x, I, W_adj, config)
        global_sign = np.sign(np.mean(x))
        decision_str = "A" if global_sign > 0 else ("B" if global_sign < 0 else "A")
        K_history.append(decision_str)

        converged, final_decision = check_autonomy_converged(
            x, rho, K_history,
            config.theta_var, config.theta_agree, config.K_stable,
        )
        if converged:
            return {
                "converged": True,
                "decision": final_decision,
                "x_final": x.copy(),
                "y_hat": y_hat.copy(),
                "rho": rho.copy(),
                "q": q.copy(),
                "rounds": round_idx + 1,
            }

    # hit max_steps without converging
    return {
        "converged": False,
        "decision": None,
        "x_final": x.copy(),
        "y_hat": y_hat.copy(),
        "rho": rho.copy(),
        "q": q.copy(),
        "rounds": config.max_steps,
    }
