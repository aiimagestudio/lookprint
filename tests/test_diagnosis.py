import pytest

from lookprint.diagnosis import add_diagnosis, diagnose_row

KEYS = {
    "tone": ["sat_mean", "warmth", "lab_b", "split_b"],
    "light": ["std_y", "shadow_frac", "mean_y", "bimodality"],
    "tech": ["grain_std", "laplacian_var"],
}


def make_stats(centers, half_iqr=0.5, std=1.0):
    """centers: {key: value}。栅栏偏移 = half_iqr + 1.5×2×half_iqr = 距中心 2.0。"""
    stats = {}
    for fam_keys in KEYS.values():
        for k in fam_keys:
            c = centers.get(k, 0.0)
            q1, q3 = c - half_iqr, c + half_iqr
            stats[k] = {
                "mean": c,
                "std": std,
                "q1": q1,
                "q3": q3,
                "iqr": q3 - q1,
                "median": c,
            }
    return stats


def base_row(**overrides):
    row = {k: 0.0 for fam_keys in KEYS.values() for k in fam_keys}
    row["mahalanobis"] = 5.0
    row.update(overrides)
    return row


def test_tone_drift_above_threshold():
    stats = make_stats({"sat_mean": 0.3})
    row = base_row(sat_mean=0.3 + 2.2, mahalanobis=9.0)  # 超出 q3+1.5IQR（距中心 2.0）
    dg = diagnose_row(row, stats, threshold=7.5)
    assert dg["kind"] == "tone"
    assert dg["near"] is False
    assert dg["families"][0]["key"] == "tone"
    hit = next(h for h in dg["families"][0]["hits"] if h["key"] == "sat_mean")
    assert hit["dir"] == "high"


def test_tone_drift_near_threshold_downgrades():
    stats = make_stats({"sat_mean": 0.3})
    row = base_row(sat_mean=0.3 + 2.1, mahalanobis=5.0)  # 刚越栅栏但整体距离在风格内
    dg = diagnose_row(row, stats, threshold=7.5)
    assert dg["kind"] == "tone"
    assert dg["near"] is True


def test_tech_only_is_tech_kind():
    stats = make_stats({"grain_std": 0.01, "laplacian_var": 0.1})
    row = base_row(grain_std=0.01 + 2.2, laplacian_var=0.1 + 2.2, mahalanobis=9.0)
    dg = diagnose_row(row, stats, threshold=7.5)
    assert dg["kind"] == "tech"
    fam_keys = {f["key"] for f in dg["families"]}
    assert fam_keys == {"tech"}


def test_tech_plus_light_is_multi():
    stats = make_stats({"grain_std": 0.01, "std_y": 0.25})
    row = base_row(grain_std=0.01 + 2.2, std_y=0.25 - 2.2, mahalanobis=8.0)
    dg = diagnose_row(row, stats, threshold=7.5)
    assert dg["kind"] == "multi"


def test_composite_drift_when_no_single_out_of_range():
    stats = make_stats({})
    # 所有个体都在栅栏内（< 2.0 偏移），但组合起来推高马氏距离
    row = base_row(mean_y=1.4, bimodality=1.3, mahalanobis=8.5)
    dg = diagnose_row(row, stats, threshold=7.5)
    assert dg["kind"] == "combo"
    combo = dg["families"][0]
    assert combo["key"] == "combo"
    zs = [h["z"] for h in combo["hits"]]
    assert zs == sorted(zs, reverse=True)  # |z| 大的在前


def test_in_style_when_near_and_no_hits():
    stats = make_stats({})
    row = base_row(mahalanobis=4.0)
    dg = diagnose_row(row, stats, threshold=7.5)
    assert dg["kind"] == "in"
    assert dg["families"] == []


def test_add_diagnosis_mutates_items():
    stats = make_stats({})
    rows = [base_row(mahalanobis=4.0), base_row(mahalanobis=9.0)]
    add_diagnosis(rows, stats, threshold=7.5)
    assert rows[0]["diagnosis"]["kind"] == "in"
    assert rows[1]["diagnosis"]["kind"] == "combo"
