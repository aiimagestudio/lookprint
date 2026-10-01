from __future__ import annotations

from lookprint.constants import FINGERPRINT_KEYS, METRIC_FAMILIES, METRIC_FAMILIES_ORDER

FENCE = 1.5  # Tukey 栅栏：q1/q3 ± 1.5×IQR 之外算越界


def _hits(row: dict, stats: dict, entries) -> list[dict]:
    out = []
    for key, *_rest in entries:
        st = stats.get(key)
        v = row.get(key)
        if st is None or v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        lo = st["q1"] - FENCE * st["iqr"]
        hi = st["q3"] + FENCE * st["iqr"]
        if v < lo:
            out.append({"key": key, "dir": "low"})
        elif v > hi:
            out.append({"key": key, "dir": "high"})
    return out


def _top_z(row: dict, stats: dict, n: int = 3) -> list[dict]:
    """标准化偏离 |z| 最大的几项。单项没越栅栏时，距离多半由这些
    温和偏离组合推高（马氏距离计入指标间协方差）。"""
    zs = []
    for key in FINGERPRINT_KEYS:
        st = stats.get(key)
        v = row.get(key)
        if st is None or v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        sd = st.get("std") or 0.0
        if sd < 1e-9:
            continue
        zs.append((abs((v - st["mean"]) / sd), key, (v - st["mean"]) / sd))
    zs.sort(reverse=True)
    return [{"key": key, "z": round(z, 1)} for _a, key, z in zs[:n]]


def diagnose_row(row: dict, stats: dict, threshold: float | None = None) -> dict:
    """把越界指标按家族归类（语言无关，前端负责文案）。

    判定优先级：调色 > 技术×光影 > 技术 > 光影·题材 > 组合。调色偏离
    最要紧，因为它说明调色家族离开了这批；光影/题材偏离通常是布光
    变体，该留。

    threshold 是马氏距离阈值（如 maha_p90）：整体距离仍在风格内的图
    即使有个别指标越过 IQR 栅栏也属轻微偏移（near=True，前端降级文案）。
    """
    families = []
    for fam_key in METRIC_FAMILIES_ORDER:
        hits = _hits(row, stats, METRIC_FAMILIES[fam_key])
        if hits:
            families.append({"key": fam_key, "hits": hits})
    present = {f["key"] for f in families}

    near = False
    if threshold is not None:
        try:
            near = float(row.get("mahalanobis") or 0) <= threshold
        except (TypeError, ValueError):
            near = False

    if "tone" in present:
        kind = "tone"
    elif "tech" in present and "light" in present:
        kind = "multi"
    elif "tech" in present:
        kind = "tech"
    elif "light" in present:
        kind = "light"
    elif not near and threshold is not None:
        # 已过距离阈值但没有任何单项越界：偏离是组合性的
        # （多项温和偏高互相叠加，马氏距离计入协方差所以单项查不出）
        kind = "combo"
        families = [{"key": "combo", "hits": _top_z(row, stats)}]
    else:
        kind = "in"

    return {"families": families, "kind": kind, "near": near}


def add_diagnosis(items: list[dict], stats: dict, threshold: float | None = None) -> None:
    for r in items:
        r["diagnosis"] = diagnose_row(r, stats, threshold)
