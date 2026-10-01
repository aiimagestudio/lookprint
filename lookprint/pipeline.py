from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from lookprint.constants import FINGERPRINT_KEYS, METRIC_META
from lookprint.fingerprint import (
    fit_fingerprint,
    load_model,
    matrix_from_rows,
    project_pca,
    save_model,
    score_matrix,
    summarize_rows,
)
from lookprint.metrics import analyze_image, list_images, load_rgb, public_metrics
from lookprint.plots import (
    plot_boxplots,
    plot_contrast_sat,
    plot_luma_overlay,
    plot_pca,
    plot_rank,
    plot_rgb_mean,
    plot_split_tone,
    plot_vectorscope,
    setup_mpl,
)
from lookprint.store import load_json, load_project, project_dir, save_json, save_project, utc_now, write_metrics_csv

ProgressCb = Callable[[int, int, str], None]


def analyze_folder(folder: Path, recursive: bool, progress: ProgressCb | None = None) -> tuple[list[Path], list[dict]]:
    images = list_images(folder, recursive=recursive)
    rows: list[dict] = []
    n = len(images)
    for i, p in enumerate(images, 1):
        if progress:
            progress(i, n, p.name)
        rows.append(analyze_image(load_rgb(p)))
    return images, rows


def build_gold(project_id: str | None = None, progress: ProgressCb | None = None) -> dict:
    proj = load_project(project_id)
    gold = Path(proj["gold_path"])
    if not gold.is_dir():
        raise FileNotFoundError(f"金标准文件夹不存在: {gold}")
    d = project_dir(proj["id"])
    old_fp = load_json(d / "fingerprint.json", None)

    images, rows = analyze_folder(gold, recursive=False, progress=progress)
    if len(rows) < 8:
        raise ValueError(f"图片太少（{len(rows)}），至少需要 8 张才能建指纹")

    X = matrix_from_rows(rows)
    fp = fit_fingerprint(X)
    maha = fp["maha"]
    labels = fp["labels"]
    names = [p.name for p in images]
    paths = [str(p) for p in images]

    extra = {
        "file": names,
        "path": paths,
        "cluster": [int(x) for x in labels],
        "mahalanobis": [float(x) for x in maha],
        "cluster_distance": [float(x) for x in fp["comp_d"]],
        "pc1": [float(x) for x in fp["xy"][:, 0]],
        "pc2": [float(x) for x in fp["xy"][:, 1]],
    }
    write_metrics_csv(d / "metrics.csv", rows, extra)
    save_model(fp, d / "fingerprint.pkl")

    stats = summarize_rows(rows, FINGERPRINT_KEYS + ["mean_r", "mean_g", "mean_b"])
    p90 = float(np.percentile(maha, proj.get("threshold_percentile", 90)))
    p95 = float(np.percentile(maha, 95))

    plots_dir = d / "plots"
    plots_dir.mkdir(exist_ok=True)
    plt = setup_mpl()
    mean_y = plot_luma_overlay(plt, rows, plots_dir / "01_luma_hist_overlay.png")
    rgb_mean = plot_rgb_mean(plt, rows, plots_dir / "02_rgb_hist_mean.png")
    plot_vectorscope(plt, rows, plots_dir / "03_vectorscope_lab.png")
    plot_split_tone(plt, rows, plots_dir / "04_split_tone.png")
    plot_contrast_sat(plt, rows, maha, plots_dir / "05_contrast_vs_sat.png")
    plot_pca(plt, fp, names, plots_dir / "06_pca.png")
    plot_boxplots(plt, rows, [(k, label) for k, label, *_rest in METRIC_META[:12]], plots_dir / "07_metric_boxplots.png")
    plot_rank(plt, maha, plots_dir / "08_consistency_curve.png")

    order_typ = np.argsort(maha)
    order_out = np.argsort(-maha)

    fingerprint = {
        "n_images": len(rows),
        "n_gmm_components": fp["n_components"],
        "gmm_bics": fp["bics"],
        "pca_explained": fp["explained"],
        "maha_median": float(np.median(maha)),
        "maha_p90": p90,
        "maha_p95": p95,
        "metrics": stats,
        "fingerprint_keys": FINGERPRINT_KEYS,
        "mean_hist_y": mean_y,
        "mean_hist_rgb": rgb_mean,
        "typical": [names[i] for i in order_typ[:9]],
        "outliers": [names[i] for i in order_out[:9]],
        "gold_path": str(gold),
        "analyzed_at": utc_now(),
    }
    save_json(d / "fingerprint.json", fingerprint)

    # 换了金标准路径：旧的剔除标记属于上一个数据集，按文件名留着会错配，清空。
    # 只在分析成功后清，分析失败不影响旧数据。
    decisions_reset = bool(old_fp and old_fp.get("gold_path") and old_fp["gold_path"] != str(gold))
    if decisions_reset:
        save_json(d / "decisions.json", {})

    proj["n_images"] = len(rows)
    proj["last_analyzed_at"] = fingerprint["analyzed_at"]
    save_project(proj)
    return fingerprint


def score_candidates(
    folder: Path,
    recursive: bool = False,
    project_id: str | None = None,
    progress: ProgressCb | None = None,
) -> dict:
    proj = load_project(project_id)
    d = project_dir(proj["id"])
    model_path = d / "fingerprint.pkl"
    if not model_path.exists():
        raise FileNotFoundError("还没有金标准指纹，请先分析数据集")
    model = load_model(model_path)
    images, rows = analyze_folder(folder, recursive=recursive, progress=progress)
    if not rows:
        return {
            "folder": str(folder),
            "recursive": recursive,
            "n": 0,
            "threshold": None,
            "items": [],
            "scanned_at": utc_now(),
        }

    X = matrix_from_rows(rows, model["keys"])
    maha = score_matrix(X, model)
    xy = project_pca(X, model)
    meta = load_json(d / "fingerprint.json", {})
    percentile = float(proj.get("threshold_percentile", 90))
    threshold = float(meta.get("maha_p90") or 7.57)

    items = []
    for i, p in enumerate(images):
        pub = public_metrics(rows[i])
        items.append(
            {
                "file": p.name,
                "path": str(p),
                "mahalanobis": float(maha[i]),
                "pass": bool(float(maha[i]) <= threshold),
                "pc1": float(xy[i, 0]),
                "pc2": float(xy[i, 1]),
                **pub,
            }
        )
    items.sort(key=lambda r: r["mahalanobis"])
    result = {
        "folder": str(folder),
        "recursive": recursive,
        "n": len(items),
        "n_pass": sum(1 for it in items if it["pass"]),
        "threshold": threshold,
        "threshold_percentile": percentile,
        "items": items,
        "scanned_at": utc_now(),
        "project_id": proj["id"],
    }
    stamp = result["scanned_at"].replace(":", "").replace("-", "")[:15]
    save_json(d / "scans" / f"{stamp}.json", result)
    save_json(d / "last_scan.json", result)
    return result
