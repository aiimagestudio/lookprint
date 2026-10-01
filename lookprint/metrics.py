from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from lookprint.constants import IMAGE_EXTS, LONG_EDGE, PIXEL_SAMPLE


def list_images(folder: Path, recursive: bool = False) -> list[Path]:
    folder = Path(folder)
    if not folder.is_dir():
        return []
    if recursive:
        files = [
            p
            for p in folder.rglob("*")
            if p.is_file()
            and p.suffix.lower() in IMAGE_EXTS
            and not p.name.startswith(".")
            and "_lookprint_dropped" not in p.parts
            and "_style_analysis" not in p.parts
        ]
    else:
        files = [
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS and not p.name.startswith(".")
        ]
    return sorted(files, key=lambda p: str(p).lower())


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
    return np.asarray(im, dtype=np.float32) / 255.0


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
    kurt = (z ** 4).mean()
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
    gx = cv2.Sobel(y, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(y, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    ixx = (gx * gx).mean()
    iyy = (gy * gy).mean()
    ixy = (gx * gy).mean()
    tmp = math.sqrt(max((ixx - iyy) ** 2 + 4 * ixy * ixy, 0.0))
    l1 = 0.5 * (ixx + iyy + tmp)
    l2 = 0.5 * (ixx + iyy - tmp)
    aniso = (l1 - l2) / (l1 + l2 + 1e-12)
    return float(mag.mean()), float(aniso)


def grain_std(y: np.ndarray) -> float:
    y8 = np.clip(y * 255, 0, 255).astype(np.uint8)
    sm = cv2.bilateralFilter(y8, d=5, sigmaColor=25, sigmaSpace=5).astype(np.float32) / 255.0
    return float(np.abs(y - sm).std())


def skin_fraction(rgb: np.ndarray, a: np.ndarray, b: np.ndarray, y: np.ndarray) -> float:
    mask = (a > 6) & (b > 4) & (y > 0.18) & (y < 0.92)
    r, g, bl = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mask &= (r > g * 0.9) & (r > bl)
    return float(mask.mean())


def local_contrast(y: np.ndarray) -> float:
    sigma = max(y.shape) / 40.0
    blur = cv2.GaussianBlur(y, (0, 0), sigmaX=sigma)
    return float((y - blur).std())


def laplacian_var(y: np.ndarray) -> float:
    return float(cv2.Laplacian(y, cv2.CV_32F, ksize=3).var())


def _mmean(x: np.ndarray, m: np.ndarray) -> float:
    return float(x[m].mean()) if m.any() else float(x.mean())


def analyze_image(rgb: np.ndarray) -> dict:
    y = rec709_y(rgb)
    _L, a, b = to_lab(rgb)
    h, s, _v = to_hsv(rgb)
    r, g, bl = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    ys = y.reshape(-1)
    p01, p05, p25, p50, p75, p95, p99 = np.percentile(ys, [1, 5, 25, 50, 75, 95, 99])
    hist, _ = np.histogram(ys, bins=64, range=(0, 1))

    shadow = y < p25
    highlight = y > p75
    mid = (y >= p25) & (y <= p75)
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
        "bimodality": bimodality_coefficient(ys[::4]),
        "local_contrast": local_contrast(y),
        "laplacian_var": laplacian_var(y),
        "grad_mean": grad_mean,
        "grad_anisotropy": grad_aniso,
        "sat_mean": float(s.mean()),
        "sat_shadow": _mmean(s, shadow),
        "sat_mid": _mmean(s, mid),
        "sat_highlight": _mmean(s, highlight),
        "chroma_mean": float(np.sqrt(a * a + b * b).mean()),
        "colorfulness": colorfulness_hasler(rgb),
        "warmth": float((r - bl).mean()),
        "lab_a": float(a.mean()),
        "lab_b": float(b.mean()),
        "shadow_a": _mmean(a, shadow),
        "shadow_b": _mmean(b, shadow),
        "highlight_a": _mmean(a, highlight),
        "highlight_b": _mmean(b, highlight),
        "split_b": _mmean(b, highlight) - _mmean(b, shadow),
        "split_a": _mmean(a, highlight) - _mmean(a, shadow),
        "rg_mean": float((r - g).mean()),
        "rb_mean": float((r - bl).mean()),
        "mean_r": float(r.mean()),
        "mean_g": float(g.mean()),
        "mean_b": float(bl.mean()),
        "skin_frac": skin_fraction(rgb, a, b, y),
        "grain_std": grain_std(y),
        "hue_mean": float(h.mean()),
    }

    feat["_hist_y"] = hist.astype(np.float32)
    hr, _ = np.histogram(r, bins=32, range=(0, 1))
    hg, _ = np.histogram(g, bins=32, range=(0, 1))
    hb, _ = np.histogram(bl, bins=32, range=(0, 1))
    feat["_hist_r"] = hr.astype(np.float32)
    feat["_hist_g"] = hg.astype(np.float32)
    feat["_hist_b"] = hb.astype(np.float32)

    n = y.size
    rng = np.random.default_rng(0)
    idx = rng.choice(n, size=min(PIXEL_SAMPLE, n), replace=False)
    feat["_sample_a"] = a.reshape(-1)[idx].astype(np.float32)
    feat["_sample_b"] = b.reshape(-1)[idx].astype(np.float32)
    feat["_sample_y"] = y.reshape(-1)[idx].astype(np.float32)
    return feat


def public_metrics(feat: dict) -> dict:
    return {k: v for k, v in feat.items() if not k.startswith("_")}
