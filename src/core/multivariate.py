"""Multivariate community analysis for coralX (Fase 3, Lapis 3).

All functions require can_run_multivariate(project).ok == True before use.
Functions are pure (no PyQt, no side effects).

Default biotic_only=True and TWS always excluded so abiotic substrate codes
don't dominate Bray-Curtis distances.
"""
# pylint: disable=invalid-name,too-many-locals

from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import linkage as _scipy_linkage
from scipy.spatial.distance import pdist, squareform


# Substrate / artefact codes excluded when biotic_only=True
_ABIOTIC_CODES: frozenset[str] = frozenset(
    {"S", "R", "RK", "SI", "SD", "RB", "TWS", "OT"}
)


def composition_matrix(
    project: object,
    biotic_only: bool = True,
    exclude_codes: set[str] | None = None,
    transform: str = "none",
) -> tuple[list[str], list[str], np.ndarray]:
    """Build a site × species composition matrix (proportions).

    Rows = stations, columns = codes, cells = proportion of labeled points.

    Args:
        project:       Project instance.
        biotic_only:   Drop known abiotic/substrate codes (default True).
        exclude_codes: Additional codes to drop. TWS is always dropped.
        transform:     'none' | 'sqrt' | 'fourth_root' — applied element-wise
                       to balance dominant categories before ordination.

    Returns:
        (sample_names, code_names, matrix)  — matrix shape (n_stations, n_codes).
    """
    always_exclude = {"TWS"}
    drop = always_exclude | (exclude_codes or set())
    if biotic_only:
        drop |= _ABIOTIC_CODES

    stations = getattr(project, "stations", [])
    sample_names: list[str] = []
    raw_counts: list[dict[str, int]] = []

    for st in stations:
        counts: dict[str, int] = {}
        for ann in getattr(st, "annotations", []):
            for p in getattr(ann, "points", []):
                lbl = getattr(p, "label", None)
                if lbl and lbl not in drop:
                    counts[lbl] = counts.get(lbl, 0) + 1
        sample_names.append(st.name)
        raw_counts.append(counts)

    # Union of all codes across stations (sorted for reproducibility)
    all_codes = sorted({code for c in raw_counts for code in c})

    # Build proportion matrix
    matrix = np.zeros((len(sample_names), len(all_codes)), dtype=float)
    for i, counts in enumerate(raw_counts):
        total = sum(counts.values())
        if total > 0:
            for j, code in enumerate(all_codes):
                matrix[i, j] = counts.get(code, 0) / total

    # Optional Hellinger-like transforms
    if transform == "sqrt":
        matrix = np.sqrt(matrix)
    elif transform == "fourth_root":
        matrix = np.power(matrix, 0.25)

    return sample_names, all_codes, matrix


def bray_curtis_matrix(matrix: np.ndarray) -> np.ndarray:
    """Bray-Curtis dissimilarity matrix (n_samples × n_samples), range 0..1.

    Uses scipy pdist with metric='braycurtis' then squareform.
    """
    return squareform(pdist(matrix, metric="braycurtis"))


def pcoa(distance_matrix: np.ndarray, n_axes: int = 2) -> dict:
    """Principal Coordinates Analysis (classical MDS) using NumPy only.

    Steps:
      1. Square the distance matrix.
      2. Double-center: A = -0.5 * D², then G = H @ A @ H  (H = centering matrix).
      3. Eigen-decompose G → keep n_axes with largest positive eigenvalues.

    Args:
        distance_matrix: symmetric (n × n) dissimilarity matrix.
        n_axes:          number of PCoA axes to return (default 2).

    Returns:
        {
          'coords':            np.ndarray (n × n_axes),
          'eigenvalues':       np.ndarray (n_axes,),
          'variance_explained': list[float]  — proportion per axis,
        }
    """
    n = distance_matrix.shape[0]
    D2 = distance_matrix ** 2
    # Centering matrix H = I - (1/n) 11^T
    H = np.eye(n) - np.ones((n, n)) / n
    G = -0.5 * H @ D2 @ H

    eigenvalues, eigenvectors = np.linalg.eigh(G)
    # eigh returns ascending order — reverse to descending
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # Keep only positive eigenvalues for coordinates
    pos_mask = eigenvalues > 1e-10
    pos_evals = eigenvalues[pos_mask]
    pos_evecs = eigenvectors[:, pos_mask]

    k = min(n_axes, pos_evecs.shape[1])
    coords = pos_evecs[:, :k] * np.sqrt(pos_evals[:k])

    total_var = float(pos_evals.sum()) if pos_evals.size > 0 else 1.0
    variance_explained = [
        round(float(pos_evals[i]) / total_var, 4) if i < len(pos_evals) else 0.0
        for i in range(k)
    ]

    return {
        "coords": coords,
        "eigenvalues": eigenvalues[:k],
        "variance_explained": variance_explained,
    }


def hierarchical_clusters(
    distance_matrix: np.ndarray,
    method: str = "average",
) -> dict:
    """Hierarchical clustering from a Bray-Curtis distance matrix.

    Uses UPGMA ('average') by default — standard in community ecology.
    The condensed distance vector required by scipy is derived via squareform.

    Args:
        distance_matrix: symmetric (n × n) dissimilarity matrix.
        method:          linkage method ('average', 'ward', 'complete', etc.).

    Returns:
        {'linkage': np.ndarray, 'method': str}
        (linkage array is in scipy format; pass to scipy.cluster.hierarchy.dendrogram)
    """
    condensed = squareform(distance_matrix)
    Z = _scipy_linkage(condensed, method=method)  # type: ignore[arg-type]
    return {"linkage": Z, "method": method}


def permanova(
    distance_matrix: np.ndarray,
    group_labels: list[str],
    permutations: int = 999,
    seed: int | None = 42,
) -> dict:
    """PERMANOVA (Anderson 2001) — permutation-based multivariate ANOVA.

    Tests whether community composition differs significantly between groups
    using a pseudo-F statistic and permutation-derived p-value.

    Pseudo-F = (SS_between / (a-1)) / (SS_within / (N-a))
    where SS is computed from squared distances.

    Args:
        distance_matrix: symmetric (n × n) dissimilarity matrix.
        group_labels:    list of group assignments, one per sample (length n).
        permutations:    number of permutations for p-value (default 999).
        seed:            RNG seed for reproducibility.

    Returns:
        {'pseudo_F': float, 'p_value': float, 'permutations': int, 'significant': bool}
        or {'error': str} when requirements not met.
    """
    n = distance_matrix.shape[0]
    groups = list(set(group_labels))
    a = len(groups)
    if a < 2:
        return {"error": f"Need >=2 groups; got {a}."}
    for g in groups:
        if group_labels.count(g) < 2:
            return {"error": f"Group '{g}' has only 1 sample; need >=2 per group."}

    labels_arr = np.array(group_labels)

    def _pseudo_f(lbls: np.ndarray) -> float:
        D2 = distance_matrix ** 2
        grp_names = list(set(lbls.tolist()))
        a_val = len(grp_names)
        # Total SS
        ss_total = float(D2.sum()) / (2 * n)
        # Within-group SS
        ss_within = 0.0
        for g in grp_names:
            idx = np.where(lbls == g)[0]
            ng = len(idx)
            if ng < 2:
                continue
            sub = D2[np.ix_(idx, idx)]
            ss_within += float(sub.sum()) / (2 * ng)
        ss_between = ss_total - ss_within
        if n - a_val == 0:
            return 0.0
        denom = ss_within / (n - a_val)
        # All sites identical → F undefined (0/0) → treat as 0 (no difference)
        if ss_between == 0.0 and denom == 0.0:
            return 0.0
        # Within-group variation is zero but between-group is not → F → ∞
        if denom == 0.0:
            return float("inf")
        return (ss_between / (a_val - 1)) / denom

    observed_f = _pseudo_f(labels_arr)

    rng = np.random.default_rng(seed)
    count_ge = 0
    for _ in range(permutations):
        perm = rng.permutation(labels_arr)
        if _pseudo_f(perm) >= observed_f:
            count_ge += 1

    p_value = (count_ge + 1) / (permutations + 1)
    return {
        "pseudo_F": round(float(observed_f), 4),
        "p_value": round(float(p_value), 4),
        "permutations": permutations,
        "significant": bool(p_value < 0.05),
    }


def simper(
    matrix: np.ndarray,
    code_names: list[str],
    group_labels: list[str],
    group_a: str,
    group_b: str,
) -> list[dict]:
    """SIMPER — species contributions to average Bray-Curtis dissimilarity.

    Decomposes mean Bray-Curtis dissimilarity between two groups into
    per-code contributions, sorted from largest to smallest.

    Args:
        matrix:       site × species proportion matrix (from composition_matrix).
        code_names:   list of species/code names (columns of matrix).
        group_labels: group assignment per sample (one per row of matrix).
        group_a:      name of the first group.
        group_b:      name of the second group.

    Returns:
        list[{'code': str, 'avg_contribution': float,
              'pct_contribution': float, 'cumulative_pct': float}]
        sorted by avg_contribution descending.
    """
    idx_a = [i for i, g in enumerate(group_labels) if g == group_a]
    idx_b = [i for i, g in enumerate(group_labels) if g == group_b]

    if not idx_a or not idx_b:
        return []

    mat_a = matrix[idx_a, :]
    mat_b = matrix[idx_b, :]

    n_codes = len(code_names)
    contributions = np.zeros(n_codes)

    n_pairs = len(idx_a) * len(idx_b)
    for i in range(len(idx_a)):
        for j in range(len(idx_b)):
            diff = np.abs(mat_a[i] - mat_b[j])
            denom = mat_a[i].sum() + mat_b[j].sum()
            if denom > 0:
                contributions += diff / denom

    contributions /= n_pairs

    total = contributions.sum()
    order = np.argsort(contributions)[::-1]
    cumulative = 0.0
    rows: list[dict] = []
    for idx in order:
        contrib = float(contributions[idx])
        pct = round(contrib / total * 100, 2) if total > 0 else 0.0
        cumulative += pct
        rows.append({
            "code": code_names[idx],
            "avg_contribution": round(contrib, 6),
            "pct_contribution": pct,
            "cumulative_pct": round(cumulative, 2),
        })
    return rows
