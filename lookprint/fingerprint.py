from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
from sklearn.covariance import EmpiricalCovariance
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from lookprint.constants import FINGERPRINT_KEYS


def robust_stats(xs: np.ndarray) -> dict:
    q1, med, q3 = np.percentile(xs, [25, 50, 75])
    return {
        "mean": float(xs.mean()),
        "std": float(xs.std()),
        "min": float(xs.min()),
        "p05": float(np.percentile(xs, 5)),
        "q1": float(q1),
        "median": float(med),
        "q3": float(q3),
        "p95": float(np.percentile(xs, 95)),
        "max": float(xs.max()),
        "iqr": float(q3 - q1),
    }


def matrix_from_rows(rows: list[dict], keys: list[str] | None = None) -> np.ndarray:
    keys = keys or FINGERPRINT_KEYS
    return np.array([[row[k] for k in keys] for row in rows], dtype=np.float64)


def fit_fingerprint(X: np.ndarray) -> dict:
    scaler = StandardScaler()
    Z = scaler.fit_transform(X)
    bics = []
    models = []
    n_max = min(4, max(1, X.shape[0] // 20))
    for n in range(1, n_max + 1):
        gmm = GaussianMixture(
            n_components=n, covariance_type="full", random_state=0, n_init=5, max_iter=300
        )
        gmm.fit(Z)
        models.append(gmm)
        bics.append(float(gmm.bic(Z)))
    best = int(np.argmin(bics))
    gmm = models[best]

    cov = EmpiricalCovariance().fit(Z)
    maha = np.sqrt(np.clip(cov.mahalanobis(Z), 0, None))
    labels = gmm.predict(Z)
    comp_d = []
    for i, z in enumerate(Z):
        k = labels[i]
        d = z - gmm.means_[k]
        prec = gmm.precisions_[k]
        comp_d.append(float(np.sqrt(max(d @ prec @ d, 0.0))))
    comp_d = np.array(comp_d)

    n_pca = min(2, Z.shape[1], Z.shape[0])
    pca = PCA(n_components=n_pca, random_state=0)
    xy = pca.fit_transform(Z)
    if xy.shape[1] == 1:
        xy = np.column_stack([xy[:, 0], np.zeros(len(xy))])
        explained = pca.explained_variance_ratio_.tolist() + [0.0]
    else:
        explained = pca.explained_variance_ratio_.tolist()

    return {
        "scaler": scaler,
        "gmm": gmm,
        "cov": cov,
        "Z": Z,
        "maha": maha,
        "comp_d": comp_d,
        "labels": labels,
        "n_components": best + 1,
        "bics": bics,
        "pca": pca,
        "xy": xy,
        "explained": explained,
        "keys": FINGERPRINT_KEYS,
    }


def score_matrix(X: np.ndarray, fp: dict) -> np.ndarray:
    Z = fp["scaler"].transform(X)
    return np.sqrt(np.clip(fp["cov"].mahalanobis(Z), 0, None))


def project_pca(X: np.ndarray, fp: dict) -> np.ndarray:
    Z = fp["scaler"].transform(X)
    xy = fp["pca"].transform(Z)
    if xy.shape[1] == 1:
        xy = np.column_stack([xy[:, 0], np.zeros(len(xy))])
    return xy


def save_model(fp: dict, path: Path) -> None:
    blob = {
        "scaler": fp["scaler"],
        "gmm": fp["gmm"],
        "cov": fp["cov"],
        "pca": fp["pca"],
        "keys": fp["keys"],
        "n_components": fp["n_components"],
        "bics": fp["bics"],
        "explained": fp["explained"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(blob, protocol=4))


def load_model(path: Path) -> dict:
    return pickle.loads(path.read_bytes())


def summarize_rows(rows: list[dict], keys: list[str]) -> dict:
    out = {}
    for k in keys:
        xs = np.array([r[k] for r in rows], dtype=np.float64)
        out[k] = robust_stats(xs)
    return out
