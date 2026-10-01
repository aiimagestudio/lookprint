import numpy as np

from lookprint.metrics import (
    analyze_image,
    bimodality_coefficient,
    colorfulness_hasler,
    rec709_y,
    shannon_entropy,
    structure_anisotropy,
)


def test_rec709_y_luma_weights():
    rgb = np.zeros((4, 4, 3), dtype=np.float32)
    rgb[..., 0] = 1.0  # pure red: Rec.709 luma = 0.2126
    y = rec709_y(rgb)
    assert float(y.mean()) == np.float32(0.2126)


def test_gray_image_has_zero_saturation_and_colorfulness():
    rgb = np.full((32, 32, 3), 0.5, dtype=np.float32)
    feat = analyze_image(rgb)
    assert feat["sat_mean"] == 0.0
    assert feat["colorfulness"] == 0.0


def test_shannon_entropy_bounds():
    uniform = np.ones(64)  # uniform 64-bin histogram → 6 bits
    assert abs(shannon_entropy(uniform) - 6.0) < 1e-9
    assert shannon_entropy(np.zeros(64)) == 0.0


def test_bimodality_detects_separated_clusters():
    rng = np.random.default_rng(0)
    xs = np.concatenate([rng.normal(0.1, 0.02, 500), rng.normal(0.9, 0.02, 500)])
    assert bimodality_coefficient(xs) > 0.7
    # 单峰正态不应被误判为双峰
    single = rng.normal(0.5, 0.1, 1000)
    assert bimodality_coefficient(single) < 0.555


def test_structure_anisotropy_detects_orientation():
    # 垂直条纹（周期 4）→ 梯度全部在 x 方向 → 各向异性接近 1
    y = np.tile(np.array([0, 0, 1, 1] * 8, dtype=np.float32), (32, 1))
    _mag, aniso = structure_anisotropy(y)
    assert aniso > 0.9


def test_analyze_image_returns_all_fingerprint_metrics():
    from lookprint.metrics import public_metrics

    rng = np.random.default_rng(1)
    rgb = rng.random((64, 48, 3), dtype=np.float32)
    feat = public_metrics(analyze_image(rgb))
    for key in ("std_y", "sat_mean", "grain_std", "split_b", "bimodality"):
        assert key in feat
    assert feat["width"] == 48 and feat["height"] == 64
    assert all(not k.startswith("_") for k in feat)
