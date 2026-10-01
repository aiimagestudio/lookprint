#!/usr/bin/env python3
"""Quantify a LoRA style set: film/slide color, contrast, lighting.

Treats the folder as the gold-standard look. Each image becomes a vector of
interpretable photo metrics. The set centroid / GMM is the fingerprint.
New images can be scored by Mahalanobis distance to that fingerprint.

Usage:
    python analyze_style.py
    python analyze_style.py --dataset "F:\\path\\to\\images"
    python analyze_style.py --candidates "F:\\path\\to\\new_picks"
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.covariance import EmpiricalCovariance

# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
LONG_EDGE = 640
PIXEL_SAMPLE = 2500

# Metrics used for the statistical fingerprint (not every diagnostic column).
FINGERPRINT_KEYS = [
    "mean_y",
    "std_y",
    "p05_y",
    "p50_y",
    "p95_y",
    "dynamic_range",
    "shadow_frac",
    "highlight_frac",
    "clip_black",
    "clip_white",
    "hist_entropy",
    "bimodality",
    "local_contrast",
    "laplacian_var",
    "grad_mean",
    "grad_anisotropy",
    "sat_mean",
    "sat_shadow",
    "sat_mid",
    "sat_highlight",
    "chroma_mean",
    "colorfulness",
    "warmth",
    "lab_a",
    "lab_b",
    "shadow_a",
    "shadow_b",
    "highlight_a",
    "highlight_b",
    "split_b",
    "split_a",
    "rg_mean",
    "rb_mean",
    "skin_frac",
    "grain_std",
]


def list_images(folder: Path) -> list[Path]:
    files = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS and not p.name.startswith(".")
    ]
    return sorted(files, key=lambda p: p.name.lower())


def load_rgb(path: Path, long_edge: int = LONG_EDGE) -> np.ndarray:
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (0, 0, 0))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    w, h = im.size
    scale = long_edge / max(w, h)
    if scale < 1:
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    arr = np.asarray(im, dtype=np.float32) / 255.0
    return arr


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def rec709_y(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def to_lab(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    bgr_u8 = (np.clip(rgb[..., ::-1], 0, 1) * 255).astype(np.uint8)
    lab = cv2.cvtColor(bgr_u8, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[..., 0] * (100.0 / 255.0)
    a = lab[..., 1] - 128.0
    b = lab[..., 2] - 128.0
    return L, a, b


def to_hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    bgr_u8 = (np.clip(rgb[..., ::-1], 0, 1) * 255).astype(np.uint8)
    hsv = cv2.cvtColor(bgr_u8, cv2.COLOR_BGR2HSV).astype(np.float32)
    return hsv[..., 0], hsv[..., 1] / 255.0, hsv[..., 2] / 255.0


def shannon_entropy(hist: np.ndarray) -> float:
    p = hist.astype(np.float64)
    p = p / (p.sum() + 1e-12)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def bimodality_coefficient(x: np.ndarray) -> float:
    """SAS bimodality coefficient. ~0.555+ suggests a bimodal (chiaroscuro) hist."""
    x = x.reshape(-1).astype(np.float64)
    n = x.size
    if n < 8:
        return 0.0
    m = x.mean()
    s = x.std()
    if s < 1e-8:
        return 0.0
    z = (x - m) / s
    skew = (z ** 3).mean()
    kurt = (z ** 4).mean()  # Pearson, not excess
    # excess kurtosis = kurt - 3; BC uses sample-adjusted excess
    excess = ((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * kurt - 3 * (n - 1)) if n > 3 else kurt - 3
    denom = excess + 3.0 * ((n - 1) ** 2) / ((n - 2) * (n - 3) + 1e-12)
    return float((skew ** 2 + 1.0) / (denom + 1e-12))


def colorfulness_hasler(rgb: np.ndarray) -> float:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    rg = r - g
    yb = 0.5 * (r + g) - b
    std_rg, std_yb = float(rg.std()), float(yb.std())
    mean_rg, mean_yb = float(rg.mean()), float(yb.mean())
    return math.sqrt(std_rg ** 2 + std_yb ** 2) + 0.3 * math.sqrt(mean_rg ** 2 + mean_yb ** 2)


def structure_anisotropy(y: np.ndarray) -> tuple[float, float]:
    """Mean gradient magnitude and anisotropy of the structure tensor (directional light)."""
    gx = cv2.Sobel(y, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(y, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    ixx = (gx * gx).mean()
    iyy = (gy * gy).mean()
    ixy = (gx * gy).mean()
    # eigenvalues of [[ixx, ixy], [ixy, iyy]]
    tmp = math.sqrt(max((ixx - iyy) ** 2 + 4 * ixy * ixy, 0.0))
    l1 = 0.5 * (ixx + iyy + tmp)
    l2 = 0.5 * (ixx + iyy - tmp)
    aniso = (l1 - l2) / (l1 + l2 + 1e-12)
    return float(mag.mean()), float(aniso)


def grain_std(y: np.ndarray) -> float:
    """High-frequency residual after a mild bilateral; proxy for grain vs plastic smoothness."""
    y8 = np.clip(y * 255, 0, 255).astype(np.uint8)
    sm = cv2.bilateralFilter(y8, d=5, sigmaColor=25, sigmaSpace=5).astype(np.float32) / 255.0
    return float(np.abs(y - sm).std())


def skin_fraction(rgb: np.ndarray, a: np.ndarray, b: np.ndarray, y: np.ndarray) -> float:
    """Rough skin-like chroma blob in Lab. Not a face detector; a color occupancy proxy."""
    # Typical film-portrait skin sits around a* > 5, b* > 5, mid luminance.
    mask = (a > 6) & (b > 4) & (y > 0.18) & (y < 0.92)
    r, g, bl = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    # drop strongly green/blue pixels that sneak into the Lab box
    mask &= (r > g * 0.9) & (r > bl)
    return float(mask.mean())


def local_contrast(y: np.ndarray) -> float:
    sigma = max(y.shape) / 40.0
    blur = cv2.GaussianBlur(y, (0, 0), sigmaX=sigma)
    return float((y - blur).std())


def laplacian_var(y: np.ndarray) -> float:
    return float(cv2.Laplacian(y, cv2.CV_32F, ksize=3).var())


# ---------------------------------------------------------------------------
# Per-image feature
# ---------------------------------------------------------------------------

def analyze_image(rgb: np.ndarray) -> dict:
    y = rec709_y(rgb)
    L, a, b = to_lab(rgb)
    h, s, v = to_hsv(rgb)
    r, g, bl = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    ys = y.reshape(-1)
    p01, p05, p25, p50, p75, p95, p99 = np.percentile(ys, [1, 5, 25, 50, 75, 95, 99])
    hist, _ = np.histogram(ys, bins=64, range=(0, 1))

    shadow = y < p25
    highlight = y > p75
    mid = (y >= p25) & (y <= p75)
    # avoid empty slices
    def mmean(x, m):
        return float(x[m].mean()) if m.any() else float(x.mean())

    grad_mean, grad_aniso = structure_anisotropy(y)

    feat = {
        "width": int(rgb.shape[1]),
        "height": int(rgb.shape[0]),
        "aspect": float(rgb.shape[1] / rgb.shape[0]),
        "mean_y": float(ys.mean()),
        "std_y": float(ys.std()),
        "p01_y": float(p01),
        "p05_y": float(p05),
        "p25_y": float(p25),
        "p50_y": float(p50),
        "p75_y": float(p75),
        "p95_y": float(p95),
        "p99_y": float(p99),
        "dynamic_range": float(p95 - p05),
        "shadow_frac": float((y < 0.15).mean()),
        "highlight_frac": float((y > 0.85).mean()),
        "clip_black": float((y < 0.02).mean()),
        "clip_white": float((y > 0.98).mean()),
        "midtone_frac": float(((y > 0.30) & (y < 0.70)).mean()),
        "hist_entropy": shannon_entropy(hist),
        "bimodality": bimodality_coefficient(ys[::4]),  # subsample for speed
        "local_contrast": local_contrast(y),
        "laplacian_var": laplacian_var(y),
        "grad_mean": grad_mean,
        "grad_anisotropy": grad_aniso,
        "sat_mean": float(s.mean()),
        "sat_shadow": mmean(s, shadow),
        "sat_mid": mmean(s, mid),
        "sat_highlight": mmean(s, highlight),
        "chroma_mean": float(np.sqrt(a * a + b * b).mean()),
        "colorfulness": colorfulness_hasler(rgb),
        "warmth": float((r - bl).mean()),
        "lab_a": float(a.mean()),
        "lab_b": float(b.mean()),
        "shadow_a": mmean(a, shadow),
        "shadow_b": mmean(b, shadow),
        "highlight_a": mmean(a, highlight),
        "highlight_b": mmean(b, highlight),
        "split_b": mmean(b, highlight) - mmean(b, shadow),
        "split_a": mmean(a, highlight) - mmean(a, shadow),
        "rg_mean": float((r - g).mean()),
        "rb_mean": float((r - bl).mean()),
        "mean_r": float(r.mean()),
        "mean_g": float(g.mean()),
        "mean_b": float(bl.mean()),
        "skin_frac": skin_fraction(rgb, a, b, y),
        "grain_std": grain_std(y),
        "hue_mean": float(h.mean()),
    }

    # 64-bin luma hist + 32-bin RGB hists for set-level overlay plots
    feat["_hist_y"] = hist.astype(np.float32)
    hr, _ = np.histogram(r, bins=32, range=(0, 1))
    hg, _ = np.histogram(g, bins=32, range=(0, 1))
    hb, _ = np.histogram(bl, bins=32, range=(0, 1))
    feat["_hist_r"] = hr.astype(np.float32)
    feat["_hist_g"] = hg.astype(np.float32)
    feat["_hist_b"] = hb.astype(np.float32)

    # subsampled Lab for vectorscope
    n = y.size
    rng = np.random.default_rng(0)
    idx = rng.choice(n, size=min(PIXEL_SAMPLE, n), replace=False)
    feat["_sample_a"] = a.reshape(-1)[idx].astype(np.float32)
    feat["_sample_b"] = b.reshape(-1)[idx].astype(np.float32)
    feat["_sample_y"] = y.reshape(-1)[idx].astype(np.float32)
    return feat


# ---------------------------------------------------------------------------
# Stats / fingerprint
# ---------------------------------------------------------------------------

def robust_stats(xs: np.ndarray) -> dict:
    q1, med, q3 = np.percentile(xs, [25, 50, 75])
    iqr = q3 - q1
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
        "iqr": float(iqr),
    }


def matrix_from_rows(rows: list[dict], keys: list[str]) -> np.ndarray:
    return np.array([[row[k] for k in keys] for row in rows], dtype=np.float64)


def fit_fingerprint(X: np.ndarray) -> dict:
    scaler = StandardScaler()
    Z = scaler.fit_transform(X)
    # GMM with BIC-selected components (1-4). Lighting modes often split into 2.
    bics = []
    models = []
    n_max = min(4, max(1, X.shape[0] // 20))
    for n in range(1, n_max + 1):
        gmm = GaussianMixture(
            n_components=n, covariance_type="full", random_state=0, n_init=5, max_iter=300
        )
        gmm.fit(Z)
        models.append(gmm)
        bics.append(gmm.bic(Z))
    best = int(np.argmin(bics))
    gmm = models[best]

    # empirical covariance of the whole set for a single Mahalanobis
    cov = EmpiricalCovariance().fit(Z)
    maha = np.sqrt(np.clip(cov.mahalanobis(Z), 0, None))
    labels = gmm.predict(Z)
    # distance to nearest component (in std units, using component cov)
    comp_d = []
    for i, z in enumerate(Z):
        k = labels[i]
        mean = gmm.means_[k]
        # precision is inverse cov
        prec = gmm.precisions_[k]
        d = z - mean
        comp_d.append(float(np.sqrt(max(d @ prec @ d, 0.0))))
    comp_d = np.array(comp_d)

    pca = PCA(n_components=2, random_state=0)
    xy = pca.fit_transform(Z)
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
        "explained": pca.explained_variance_ratio_.tolist(),
    }


def score_rows(rows: list[dict], keys: list[str], fp: dict) -> np.ndarray:
    X = matrix_from_rows(rows, keys)
    Z = fp["scaler"].transform(X)
    maha = np.sqrt(np.clip(fp["cov"].mahalanobis(Z), 0, None))
    return maha


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def setup_mpl():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = "Microsoft YaHei"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams.update(
        {
            "figure.facecolor": "#101014",
            "axes.facecolor": "#16161c",
            "axes.edgecolor": "#3a3a46",
            "axes.labelcolor": "#d8d4cc",
            "xtick.color": "#a8a49c",
            "ytick.color": "#a8a49c",
            "text.color": "#ece8e0",
            "grid.color": "#2a2a34",
            "grid.alpha": 0.8,
            "axes.titleweight": "bold",
            "font.size": 10,
            "axes.titlesize": 13,
            "savefig.facecolor": "#101014",
            "savefig.dpi": 140,
        }
    )
    return plt


def savefig(plt, fig, path: Path):
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_luma_overlay(plt, rows, out: Path):
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    bins = np.linspace(0, 1, 65)
    centers = 0.5 * (bins[:-1] + bins[1:])
    acc = np.zeros(64, dtype=np.float64)
    for row in rows:
        h = row["_hist_y"]
        h = h / (h.sum() + 1e-12)
        acc += h
        ax.plot(centers, h, color="#c4b8a4", alpha=0.12, lw=0.8)
    mean = acc / len(rows)
    ax.plot(centers, mean, color="#f0c060", lw=2.4, label="集合平均")
    ax.axvspan(0, 0.15, color="#3a5a8c", alpha=0.12, label="阴影 <0.15")
    ax.axvspan(0.85, 1, color="#c06040", alpha=0.12, label="高光 >0.85")
    ax.set_xlim(0, 1)
    ax.set_xlabel("亮度 Y (Rec.709)")
    ax.set_ylabel("像素占比")
    ax.set_title("亮度色阶叠加 — 每条细线一张图，黄线是整集指纹")
    ax.grid(True, axis="y")
    ax.legend(frameon=False, loc="upper right")
    savefig(plt, fig, out)


def plot_rgb_mean(plt, rows, out: Path):
    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    bins = np.linspace(0, 1, 33)
    centers = 0.5 * (bins[:-1] + bins[1:])
    hr = np.mean([r["_hist_r"] / (r["_hist_r"].sum() + 1e-12) for r in rows], axis=0)
    hg = np.mean([r["_hist_g"] / (r["_hist_g"].sum() + 1e-12) for r in rows], axis=0)
    hb = np.mean([r["_hist_b"] / (r["_hist_b"].sum() + 1e-12) for r in rows], axis=0)
    ax.plot(centers, hr, color="#e06060", lw=2, label="R")
    ax.plot(centers, hg, color="#50c070", lw=2, label="G")
    ax.plot(centers, hb, color="#5090e0", lw=2, label="B")
    ax.fill_between(centers, hr, color="#e06060", alpha=0.15)
    ax.fill_between(centers, hg, color="#50c070", alpha=0.12)
    ax.fill_between(centers, hb, color="#5090e0", alpha=0.12)
    ax.set_xlim(0, 1)
    ax.set_xlabel("通道值")
    ax.set_ylabel("像素占比")
    ax.set_title("整集平均 RGB 色阶 — 反转片常见：红通道偏暖高光，蓝通道在阴影更密")
    ax.grid(True, axis="y")
    ax.legend(frameon=False)
    savefig(plt, fig, out)


def plot_vectorscope(plt, rows, out: Path):
    fig, ax = plt.subplots(figsize=(7.2, 7.0))
    rng = np.random.default_rng(1)
    # density from a subsample of all images
    a_all, b_all = [], []
    for row in rows:
        pick = rng.choice(row["_sample_a"].size, size=80, replace=False)
        a_all.append(row["_sample_a"][pick])
        b_all.append(row["_sample_b"][pick])
    a_all = np.concatenate(a_all)
    b_all = np.concatenate(b_all)
    ax.hexbin(a_all, b_all, gridsize=42, cmap="inferno", mincnt=2, linewidths=0)
    # per-image shadow / highlight means
    sa = [r["shadow_a"] for r in rows]
    sb = [r["shadow_b"] for r in rows]
    ha = [r["highlight_a"] for r in rows]
    hb = [r["highlight_b"] for r in rows]
    ax.scatter(sa, sb, s=18, c="#4aa3ff", alpha=0.75, label="每图阴影均值", zorder=3)
    ax.scatter(ha, hb, s=18, c="#ffb14a", alpha=0.75, label="每图高光均值", zorder=3)
    ax.axhline(0, color="#666", lw=0.6)
    ax.axvline(0, color="#666", lw=0.6)
    ax.set_xlabel("a*  (绿 ← → 品红)")
    ax.set_ylabel("b*  (蓝 ← → 黄)")
    ax.set_title("Lab 矢量示波器 — 阴影 vs 高光分色（split tone）")
    ax.set_aspect("equal", adjustable="box")
    ax.legend(frameon=False, loc="upper left")
    savefig(plt, fig, out)


def plot_split_tone(plt, rows, out: Path):
    fig, ax = plt.subplots(figsize=(8.2, 6.4))
    xs = [r["shadow_b"] for r in rows]
    ys = [r["highlight_b"] for r in rows]
    cs = [r["std_y"] for r in rows]
    sc = ax.scatter(xs, ys, c=cs, cmap="cividis", s=36, alpha=0.9, edgecolors="none")
    lo, hi = min(xs + ys), max(xs + ys)
    ax.plot([lo, hi], [lo, hi], color="#666", ls="--", lw=1, label="无分色线")
    ax.set_xlabel("阴影 b*（越大越暖/黄）")
    ax.set_ylabel("高光 b*（越大越暖/黄）")
    ax.set_title("分色：点在对角线上 = 高光比阴影更暖（反转片/日光常见）")
    cb = fig.colorbar(sc, ax=ax, fraction=0.046)
    cb.set_label("对比度 std(Y)")
    ax.legend(frameon=False)
    ax.grid(True)
    savefig(plt, fig, out)


def plot_contrast_sat(plt, rows, maha, out: Path):
    fig, ax = plt.subplots(figsize=(8.4, 6.2))
    xs = [r["local_contrast"] for r in rows]
    ys = [r["sat_mean"] for r in rows]
    sc = ax.scatter(xs, ys, c=maha, cmap="magma", s=38, alpha=0.9, edgecolors="none")
    ax.set_xlabel("局部对比度（去低频后的 std）")
    ax.set_ylabel("平均饱和度 S")
    ax.set_title("光影强度 × 色彩浓度 — 颜色越亮离集合中心越远")
    cb = fig.colorbar(sc, ax=ax, fraction=0.046)
    cb.set_label("Mahalanobis 距离")
    ax.grid(True)
    savefig(plt, fig, out)


def plot_pca(plt, fp, names, out: Path):
    fig, ax = plt.subplots(figsize=(8.6, 6.4))
    xy = fp["xy"]
    labels = fp["labels"]
    maha = fp["maha"]
    colors = ["#e8b060", "#6aa6e8", "#7dce9a", "#e07a7a"]
    for k in np.unique(labels):
        m = labels == k
        ax.scatter(
            xy[m, 0],
            xy[m, 1],
            c=colors[int(k) % 4],
            s=42,
            alpha=0.88,
            label=f"簇 {int(k)+1}  n={int(m.sum())}",
            edgecolors="none",
        )
    # mark top outliers
    order = np.argsort(-maha)
    for i in order[:8]:
        ax.annotate(
            Path(names[i]).stem.replace("RCV_LoRA_", ""),
            (xy[i, 0], xy[i, 1]),
            textcoords="offset points",
            xytext=(5, 4),
            fontsize=7,
            color="#f2e8d8",
        )
    ev = fp["explained"]
    ax.set_xlabel(f"PC1  {ev[0]*100:.1f}%")
    ax.set_ylabel(f"PC2  {ev[1]*100:.1f}%")
    ax.set_title("风格特征 PCA — 同簇=光影/色彩模式接近，标注的是离群图")
    ax.legend(frameon=False)
    ax.grid(True)
    savefig(plt, fig, out)


def plot_boxplots(plt, rows, keys_cn, out: Path):
    fig, axes = plt.subplots(3, 4, figsize=(12.5, 8.4))
    axes = axes.ravel()
    for ax, (key, label) in zip(axes, keys_cn):
        vals = [r[key] for r in rows]
        bp = ax.boxplot(
            vals,
            vert=True,
            widths=0.55,
            patch_artist=True,
            medianprops=dict(color="#f0c060", lw=2),
            whiskerprops=dict(color="#aaa"),
            capprops=dict(color="#aaa"),
            flierprops=dict(marker="o", markersize=3, markerfacecolor="#e07070", markeredgecolor="none"),
        )
        bp["boxes"][0].set_facecolor("#2a3344")
        bp["boxes"][0].set_edgecolor("#889")
        ax.set_title(label, fontsize=10)
        ax.set_xticks([])
        ax.grid(True, axis="y")
    fig.suptitle("关键指标分布 — 箱子是这批图的“正常范围”，红点是该指标上的离群片", fontsize=13)
    savefig(plt, fig, out)


def plot_rank(plt, names, maha, out: Path):
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    order = np.argsort(maha)
    y = maha[order]
    ax.plot(np.arange(len(y)), y, color="#f0c060", lw=1.8)
    ax.fill_between(np.arange(len(y)), y, color="#f0c060", alpha=0.15)
    # 95th percentile cut
    cut = float(np.percentile(maha, 90))
    ax.axhline(cut, color="#e07070", ls="--", lw=1, label=f"90 分位 = {cut:.2f}")
    ax.set_xlabel("按风格距离排序后的图片（左=最像集合，右=最不像）")
    ax.set_ylabel("Mahalanobis 距离")
    ax.set_title("风格一致性曲线 — 右端陡升的图值得用肉眼复核")
    ax.legend(frameon=False)
    ax.grid(True, axis="y")
    savefig(plt, fig, out)


def make_contact_sheet(paths: list[Path], labels: list[str], out: Path, cols=3, cell=280):
    n = len(paths)
    rows_n = math.ceil(n / cols)
    pad = 8
    header = 28
    W = cols * cell + (cols + 1) * pad
    H = rows_n * (cell + header) + (rows_n + 1) * pad
    canvas = Image.new("RGB", (W, H), (16, 16, 20))
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 14)
    except Exception:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)
    for i, (p, lab) in enumerate(zip(paths, labels)):
        r, c = divmod(i, cols)
        x = pad + c * (cell + pad)
        y = pad + r * (cell + header + pad)
        try:
            im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        except Exception:
            im = Image.new("RGB", (cell, cell), (40, 0, 0))
        im.thumbnail((cell, cell), Image.Resampling.LANCZOS)
        ox = x + (cell - im.width) // 2
        oy = y + (cell - im.height) // 2
        canvas.paste(im, (ox, oy))
        draw.text((x + 2, y + cell + 4), lab, fill=(232, 220, 196), font=font)
    canvas.save(out, quality=92)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict], extra: dict[str, list]):
    skip = {k for k in rows[0] if k.startswith("_")}
    fieldnames = [k for k in rows[0] if k not in skip]
    for k in extra:
        if k not in fieldnames:
            fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["file"] + fieldnames)
        w.writeheader()
        for i, row in enumerate(rows):
            rec = {"file": extra["file"][i]}
            for k in fieldnames:
                if k in extra:
                    rec[k] = extra[k][i]
                elif k in row:
                    rec[k] = row[k]
            w.writerow(rec)


def summarize(rows, keys) -> dict:
    out = {}
    for k in keys:
        xs = np.array([r[k] for r in rows], dtype=np.float64)
        out[k] = robust_stats(xs)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dataset: Path, out_dir: Path, candidates: Path | None):
    out_dir.mkdir(parents=True, exist_ok=True)
    images = list_images(dataset)
    if not images:
        raise SystemExit(f"No images in {dataset}")

    print(f"Analyzing {len(images)} images from {dataset}")
    rows = []
    names = []
    for i, p in enumerate(images, 1):
        rgb = load_rgb(p)
        feat = analyze_image(rgb)
        rows.append(feat)
        names.append(p.name)
        if i % 20 == 0 or i == len(images):
            print(f"  {i}/{len(images)}  {p.name}")

    X = matrix_from_rows(rows, FINGERPRINT_KEYS)
    fp = fit_fingerprint(X)
    maha = fp["maha"]
    labels = fp["labels"]

    # persistence without sklearn objects
    stats = summarize(rows, FINGERPRINT_KEYS + ["mean_r", "mean_g", "mean_b", "clip_black", "clip_white"])
    fingerprint_json = {
        "n_images": len(rows),
        "n_gmm_components": fp["n_components"],
        "gmm_bics": fp["bics"],
        "pca_explained": fp["explained"],
        "maha_median": float(np.median(maha)),
        "maha_p90": float(np.percentile(maha, 90)),
        "maha_p95": float(np.percentile(maha, 95)),
        "metrics": stats,
        "fingerprint_keys": FINGERPRINT_KEYS,
    }
    (out_dir / "fingerprint.json").write_text(
        json.dumps(fingerprint_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    extra = {
        "file": names,
        "cluster": [int(x) for x in labels],
        "mahalanobis": [float(x) for x in maha],
        "cluster_distance": [float(x) for x in fp["comp_d"]],
        "pc1": [float(x) for x in fp["xy"][:, 0]],
        "pc2": [float(x) for x in fp["xy"][:, 1]],
    }
    write_csv(out_dir / "metrics.csv", rows, extra)

    plt = setup_mpl()
    plot_luma_overlay(plt, rows, out_dir / "01_luma_hist_overlay.png")
    plot_rgb_mean(plt, rows, out_dir / "02_rgb_hist_mean.png")
    plot_vectorscope(plt, rows, out_dir / "03_vectorscope_lab.png")
    plot_split_tone(plt, rows, out_dir / "04_split_tone.png")
    plot_contrast_sat(plt, rows, maha, out_dir / "05_contrast_vs_sat.png")
    plot_pca(plt, fp, names, out_dir / "06_pca.png")
    plot_boxplots(
        plt,
        rows,
        [
            ("std_y", "全局对比 std(Y)"),
            ("local_contrast", "局部对比"),
            ("dynamic_range", "动态范围 p95-p05"),
            ("bimodality", "直方图双峰性"),
            ("sat_mean", "平均饱和度"),
            ("colorfulness", "Colorfulness"),
            ("warmth", "暖度 R−B"),
            ("split_b", "分色 Δb* 高光−阴影"),
            ("shadow_frac", "阴影占比 Y<0.15"),
            ("clip_white", "死白占比 Y>0.98"),
            ("lab_b", "整图 b*"),
            ("skin_frac", "肤色像素占比"),
        ],
        out_dir / "07_metric_boxplots.png",
    )
    plot_rank(plt, names, maha, out_dir / "08_consistency_curve.png")

    order_typ = np.argsort(maha)
    order_out = np.argsort(-maha)
    ds = dataset

    def sheet(indices, tag, fname):
        paths, labs = [], []
        for i in indices:
            paths.append(ds / names[i])
            labs.append(f"{names[i]}  d={maha[i]:.2f}  c{int(labels[i])+1}")
        make_contact_sheet(paths, labs, out_dir / fname, cols=3, cell=300)
        print(f"  {tag}: " + ", ".join(names[i] for i in indices))

    sheet(order_typ[:9], "most typical", "09_typical_grid.jpg")
    sheet(order_out[:9], "most outlier", "10_outlier_grid.jpg")

    # cluster exemplars
    for k in np.unique(labels):
        idx = np.where(labels == k)[0]
        local = idx[np.argsort(fp["comp_d"][idx])[:6]]
        sheet(local, f"cluster {int(k)+1} exemplars", f"11_cluster{int(k)+1}_grid.jpg")

    # candidates
    if candidates is not None:
        c_imgs = list_images(candidates)
        if not c_imgs:
            print(f"No candidate images in {candidates}")
        else:
            c_rows, c_names = [], []
            for p in c_imgs:
                c_rows.append(analyze_image(load_rgb(p)))
                c_names.append(p.name)
            c_maha = score_rows(c_rows, FINGERPRINT_KEYS, fp)
            cut = float(np.percentile(maha, 90))
            recs = []
            for n, d in zip(c_names, c_maha):
                recs.append({"file": n, "mahalanobis": float(d), "pass_p90": bool(d <= cut)})
            recs.sort(key=lambda r: r["mahalanobis"])
            (out_dir / "candidates.json").write_text(
                json.dumps({"threshold_p90": cut, "items": recs}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print("Candidate scores (lower = closer to this set):")
            for r in recs:
                flag = "PASS" if r["pass_p90"] else "REVIEW"
                print(f"  {flag:6}  {r['mahalanobis']:.3f}  {r['file']}")

    # stdout briefing
    print("\n======== 集合指纹 ========")
    print(f"images          {len(rows)}")
    print(f"GMM clusters    {fp['n_components']}   BIC={fp['bics']}")
    print(f"PCA var         {fp['explained']}")
    print(f"maha median/p90/p95  {np.median(maha):.3f} / {np.percentile(maha,90):.3f} / {np.percentile(maha,95):.3f}")
    for key, label in [
        ("std_y", "contrast std(Y)"),
        ("local_contrast", "local contrast"),
        ("sat_mean", "saturation"),
        ("colorfulness", "colorfulness"),
        ("warmth", "warmth R-B"),
        ("split_b", "split Δb*"),
        ("shadow_frac", "shadow fraction"),
        ("clip_white", "clipped white"),
        ("bimodality", "bimodality"),
        ("lab_b", "mean b*"),
    ]:
        s = stats[key]
        print(
            f"  {label:20}  med={s['median']:.4f}  IQR=[{s['q1']:.4f},{s['q3']:.4f}]  p05/p95={s['p05']:.4f}/{s['p95']:.4f}"
        )
    print(f"\nWrote {out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output folder, default <dataset>/_style_analysis",
    )
    ap.add_argument("--candidates", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or (args.dataset / "_style_analysis")
    run(args.dataset, out, args.candidates)


if __name__ == "__main__":
    main()
