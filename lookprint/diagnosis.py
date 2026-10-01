from __future__ import annotations

from lookprint.constants import FINGERPRINT_KEYS, METRIC_FAMILIES

FENCE = 1.5  # Tukey 栅栏：q1/q3 ± 1.5×IQR 之外算越界

LABELS = {key: label for fam in METRIC_FAMILIES.values() for key, label in fam}


def _hits(row: dict, stats: dict, keys) -> list[str]:
    out = []
    for key, label in keys:
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
            out.append(f"{label}偏低")
        elif v > hi:
            out.append(f"{label}偏高")
    return out


def _top_z(row: dict, stats: dict, n: int = 3) -> list[str]:
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
        z = (v - st["mean"]) / sd
        zs.append((abs(z), key, z))
    zs.sort(reverse=True)
    return [f"{LABELS.get(key, key)} {z:+.1f}σ" for _abs, key, z in zs[:n]]


def diagnose_row(row: dict, stats: dict, threshold: float | None = None) -> dict:
    """把越界指标按家族归类，并按家族含义给处置建议。

    判定优先级：调色 > 技术×光影 > 技术 > 光影·题材。调色偏离最要紧，
    因为它说明调色家族离开了这批；光影/题材偏离通常是布光变体，该留。

    threshold 是马氏距离阈值（如 maha_p90）：整体距离仍在风格内的图
    即使有个别指标越过 IQR 栅栏，也属轻微偏移，建议降级为「先保留」。
    """
    families = []
    for fam in METRIC_FAMILIES:
        hits = _hits(row, stats, METRIC_FAMILIES[fam])
        if hits:
            families.append({"family": fam, "hits": hits})
    present = {f["family"] for f in families}

    near = False
    if threshold is not None:
        try:
            near = float(row.get("mahalanobis") or 0) <= threshold
        except (TypeError, ValueError):
            near = False

    if "调色" in present:
        if near:
            verdict, advice, kind = "调色轻微偏离", "幅度小、整体距离仍在风格内，可先保留", "tone"
        else:
            verdict, advice, kind = "调色家族偏离", "该剔或复核：调色是风格本身", "tone"
    elif "技术" in present and "光影·题材" in present:
        if near:
            verdict, advice, kind = "多维轻微偏离", "整体距离仍在风格内，可先保留", "multi"
        else:
            verdict, advice, kind = "多维偏离", "建议复核", "multi"
    elif "技术" in present:
        if near:
            verdict, advice, kind = "轻微技术偏离", "整体距离仍在风格内，可忽略", "tech"
        else:
            verdict, advice, kind = "疑似技术噪声", "复核：可能重压缩/锐化残留，非风格问题", "tech"
    elif "光影·题材" in present:
        verdict, advice, kind = "布光变体", "建议保留：题材性偏移，对泛化有用", "light"
    elif not near and threshold is not None:
        # 已过距离阈值但没有任何单项越界：偏离是组合性的
        # （多项温和偏高互相叠加，马氏距离计入协方差所以单项查不出）
        verdict, advice, kind = "组合偏离", "单项未越栅栏，距离由多项温和偏离共同推高，请人工判断", "combo"
        families = [{"family": "偏离贡献", "hits": _top_z(row, stats)}]
    else:
        verdict, advice, kind = "风格内", "", "in"

    return {"families": families, "verdict": verdict, "advice": advice, "kind": kind}


def add_diagnosis(items: list[dict], stats: dict, threshold: float | None = None) -> None:
    for r in items:
        r["diagnosis"] = diagnose_row(r, stats, threshold)
