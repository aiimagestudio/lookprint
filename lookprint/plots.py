from __future__ import annotations

from pathlib import Path

import numpy as np


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


# 图表内文字按语言生成：分析时对 zh / en 各渲染一套
PLOT_TEXT = {
    "zh": {
        "set_mean": "集合平均",
        "shadow_band": "阴影 <0.15",
        "highlight_band": "高光 >0.85",
        "luma_x": "亮度 Y (Rec.709)",
        "pixel_frac": "像素占比",
        "luma_title": "亮度色阶叠加",
        "channel_x": "通道值",
        "rgb_title": "整集平均 RGB 色阶",
        "shadow_mean": "每图阴影均值",
        "highlight_mean": "每图高光均值",
        "a_axis": "a*  (绿 ← → 品红)",
        "b_axis": "b*  (蓝 ← → 黄)",
        "vec_title": "Lab 矢量示波器",
        "no_split": "无分色线",
        "sh_b": "阴影 b*",
        "hl_b": "高光 b*",
        "split_title": "分色：对角线上方 = 高光更暖",
        "contrast_cb": "对比度 std(Y)",
        "lc_x": "局部对比度",
        "sat_y": "平均饱和度 S",
        "cs_title": "光影强度 × 色彩浓度",
        "maha_cb": "Mahalanobis 距离",
        "cluster": "簇 {k}  n={n}",
        "pca_title": "风格特征 PCA",
        "box_title": "关键指标分布",
        "rank_cut": "{p:g} 分位 = {cut:.2f}",
        "rank_x": "按风格距离排序",
        "rank_title": "风格一致性曲线",
    },
    "en": {
        "set_mean": "set mean",
        "shadow_band": "shadows <0.15",
        "highlight_band": "highlights >0.85",
        "luma_x": "Luma Y (Rec.709)",
        "pixel_frac": "pixel share",
        "luma_title": "Luma histogram overlay",
        "channel_x": "channel value",
        "rgb_title": "Set-average RGB histogram",
        "shadow_mean": "per-image shadow mean",
        "highlight_mean": "per-image highlight mean",
        "a_axis": "a*  (green ← → magenta)",
        "b_axis": "b*  (blue ← → yellow)",
        "vec_title": "Lab vectorscope",
        "no_split": "no split line",
        "sh_b": "shadow b*",
        "hl_b": "highlight b*",
        "split_title": "Split tone: above diagonal = warmer highlights",
        "contrast_cb": "contrast std(Y)",
        "lc_x": "local contrast",
        "sat_y": "mean saturation S",
        "cs_title": "Light × saturation",
        "maha_cb": "Mahalanobis distance",
        "cluster": "cluster {k}  n={n}",
        "pca_title": "Style PCA",
        "box_title": "Key metric distributions",
        "rank_cut": "p{p:g} = {cut:.2f}",
        "rank_x": "sorted by style distance",
        "rank_title": "Style consistency curve",
    },
}


def _t(lang: str, key: str, **kw) -> str:
    texts = PLOT_TEXT.get(lang) or PLOT_TEXT["zh"]
    return texts[key].format(**kw)


def plot_luma_overlay(plt, rows, out: Path, lang: str = "zh"):
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    bins = np.linspace(0, 1, 65)
    centers = 0.5 * (bins[:-1] + bins[1:])
    acc = np.zeros(64, dtype=np.float64)
    for row in rows:
        h = row["_hist_y"]
        h = h / (h.sum() + 1e-12)
        acc += h
        ax.plot(centers, h, color="#c4b8a4", alpha=0.12, lw=0.8)
    mean = acc / max(len(rows), 1)
    ax.plot(centers, mean, color="#f0c060", lw=2.4, label=_t(lang, "set_mean"))
    ax.axvspan(0, 0.15, color="#3a5a8c", alpha=0.12, label=_t(lang, "shadow_band"))
    ax.axvspan(0.85, 1, color="#c06040", alpha=0.12, label=_t(lang, "highlight_band"))
    ax.set_xlim(0, 1)
    ax.set_xlabel(_t(lang, "luma_x"))
    ax.set_ylabel(_t(lang, "pixel_frac"))
    ax.set_title(_t(lang, "luma_title"))
    ax.grid(True, axis="y")
    ax.legend(frameon=False, loc="upper right")
    savefig(plt, fig, out)
    return mean.tolist()


def plot_rgb_mean(plt, rows, out: Path, lang: str = "zh"):
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
    ax.set_xlabel(_t(lang, "channel_x"))
    ax.set_ylabel(_t(lang, "pixel_frac"))
    ax.set_title(_t(lang, "rgb_title"))
    ax.grid(True, axis="y")
    ax.legend(frameon=False)
    savefig(plt, fig, out)
    return {"r": hr.tolist(), "g": hg.tolist(), "b": hb.tolist()}


def plot_vectorscope(plt, rows, out: Path, lang: str = "zh"):
    fig, ax = plt.subplots(figsize=(7.2, 7.0))
    rng = np.random.default_rng(1)
    a_all, b_all = [], []
    for row in rows:
        n = row["_sample_a"].size
        pick = rng.choice(n, size=min(80, n), replace=False)
        a_all.append(row["_sample_a"][pick])
        b_all.append(row["_sample_b"][pick])
    a_all = np.concatenate(a_all)
    b_all = np.concatenate(b_all)
    ax.hexbin(a_all, b_all, gridsize=42, cmap="inferno", mincnt=2, linewidths=0)
    sa = [r["shadow_a"] for r in rows]
    sb = [r["shadow_b"] for r in rows]
    ha = [r["highlight_a"] for r in rows]
    hb = [r["highlight_b"] for r in rows]
    ax.scatter(sa, sb, s=18, c="#4aa3ff", alpha=0.75, label=_t(lang, "shadow_mean"), zorder=3)
    ax.scatter(ha, hb, s=18, c="#ffb14a", alpha=0.75, label=_t(lang, "highlight_mean"), zorder=3)
    ax.axhline(0, color="#666", lw=0.6)
    ax.axvline(0, color="#666", lw=0.6)
    ax.set_xlabel(_t(lang, "a_axis"))
    ax.set_ylabel(_t(lang, "b_axis"))
    ax.set_title(_t(lang, "vec_title"))
    ax.set_aspect("equal", adjustable="box")
    ax.legend(frameon=False, loc="upper left")
    savefig(plt, fig, out)


def plot_split_tone(plt, rows, out: Path, lang: str = "zh"):
    fig, ax = plt.subplots(figsize=(8.2, 6.4))
    xs = [r["shadow_b"] for r in rows]
    ys = [r["highlight_b"] for r in rows]
    cs = [r["std_y"] for r in rows]
    sc = ax.scatter(xs, ys, c=cs, cmap="cividis", s=36, alpha=0.9, edgecolors="none")
    lo, hi = min(xs + ys), max(xs + ys)
    ax.plot([lo, hi], [lo, hi], color="#666", ls="--", lw=1, label=_t(lang, "no_split"))
    ax.set_xlabel(_t(lang, "sh_b"))
    ax.set_ylabel(_t(lang, "hl_b"))
    ax.set_title(_t(lang, "split_title"))
    cb = fig.colorbar(sc, ax=ax, fraction=0.046)
    cb.set_label(_t(lang, "contrast_cb"))
    ax.legend(frameon=False)
    ax.grid(True)
    savefig(plt, fig, out)


def plot_contrast_sat(plt, rows, maha, out: Path, lang: str = "zh"):
    fig, ax = plt.subplots(figsize=(8.4, 6.2))
    xs = [r["local_contrast"] for r in rows]
    ys = [r["sat_mean"] for r in rows]
    sc = ax.scatter(xs, ys, c=maha, cmap="magma", s=38, alpha=0.9, edgecolors="none")
    ax.set_xlabel(_t(lang, "lc_x"))
    ax.set_ylabel(_t(lang, "sat_y"))
    ax.set_title(_t(lang, "cs_title"))
    cb = fig.colorbar(sc, ax=ax, fraction=0.046)
    cb.set_label(_t(lang, "maha_cb"))
    ax.grid(True)
    savefig(plt, fig, out)


def plot_pca(plt, fp, names, out: Path, lang: str = "zh"):
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
            label=_t(lang, "cluster", k=int(k) + 1, n=int(m.sum())),
            edgecolors="none",
        )
    order = np.argsort(-maha)
    for i in order[:8]:
        ax.annotate(
            Path(names[i]).stem[-4:],
            (xy[i, 0], xy[i, 1]),
            textcoords="offset points",
            xytext=(5, 4),
            fontsize=7,
            color="#f2e8d8",
        )
    ev = fp["explained"]
    ax.set_xlabel(f"PC1  {ev[0]*100:.1f}%")
    ax.set_ylabel(f"PC2  {ev[1]*100:.1f}%")
    ax.set_title(_t(lang, "pca_title"))
    ax.legend(frameon=False)
    ax.grid(True)
    savefig(plt, fig, out)


def plot_boxplots(plt, rows, keys, out: Path, lang: str = "zh"):
    from lookprint.constants import METRIC_LABELS

    fig, axes = plt.subplots(3, 4, figsize=(12.5, 8.4))
    axes = axes.ravel()
    for ax, key in zip(axes, keys):
        meta = METRIC_LABELS.get(key) or {}
        label = meta.get(lang) or key
        vals = [r[key] for r in rows]
        bp = ax.boxplot(
            vals,
            vert=True,
            widths=0.55,
            patch_artist=True,
            medianprops=dict(color="#f0c060", lw=2),
            whiskerprops=dict(color="#aaa"),
            capprops=dict(color="#aaa"),
            flierprops=dict(
                marker="o", markersize=3, markerfacecolor="#e07070", markeredgecolor="none"
            ),
        )
        bp["boxes"][0].set_facecolor("#2a3344")
        bp["boxes"][0].set_edgecolor("#889")
        ax.set_title(label, fontsize=10)
        ax.set_xticks([])
        ax.grid(True, axis="y")
    fig.suptitle(_t(lang, "box_title"), fontsize=13)
    savefig(plt, fig, out)


def plot_rank(plt, maha, out: Path, lang: str = "zh", percentile: float = 90):
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    order = np.argsort(maha)
    y = maha[order]
    ax.plot(np.arange(len(y)), y, color="#f0c060", lw=1.8)
    ax.fill_between(np.arange(len(y)), y, color="#f0c060", alpha=0.15)
    cut = float(np.percentile(maha, percentile))
    ax.axhline(cut, color="#e07070", ls="--", lw=1, label=_t(lang, "rank_cut", p=percentile, cut=cut))
    ax.set_xlabel(_t(lang, "rank_x"))
    ax.set_ylabel(_t(lang, "maha_cb"))
    ax.set_title(_t(lang, "rank_title"))
    ax.legend(frameon=False)
    ax.grid(True, axis="y")
    savefig(plt, fig, out)
