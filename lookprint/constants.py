from __future__ import annotations

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
LONG_EDGE = 640
PIXEL_SAMPLE = 2500
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

METRIC_META = [
    ("std_y", "全局对比", "std(Y)", "整图像素亮度的标准差，衡量整体明暗对比强度"),
    ("local_contrast", "局部对比", "high-pass std", "去掉低频后的对比，测光斑和明暗交界"),
    ("dynamic_range", "动态范围", "p95−p05", "去掉两端极值后的跨度"),
    ("bimodality", "双峰性", "BC", ">0.555 表示明暗分离（chiaroscuro）"),
    ("sat_mean", "平均饱和", "HSV S", "整图平均饱和度"),
    ("colorfulness", "色彩浓度", "Hasler", "比单纯饱和度更接近观感的浓郁程度"),
    ("warmth", "暖度", "R−B", "正值偏暖，负值偏冷"),
    ("split_b", "分色 Δb*", "HL b* − SH b*", "高光相对阴影更黄/暖"),
    ("shadow_frac", "阴影占比", "Y<0.15", "暗部面积"),
    ("clip_white", "死白占比", "Y>0.98", "接近纯白的像素占比，过高说明高光被硬裁切"),
    ("lab_b", "整图 b*", "Lab b*", "正黄负蓝"),
    ("skin_frac", "肤色占比", "Lab blob", "粗略肤色像素比例，不是人脸检测"),
    ("mean_y", "平均亮度", "Y", "整图 Rec.709 亮度"),
    ("grain_std", "颗粒感", "HF residual", "双边滤波后的高频残差"),
]

# METRIC_META 的英文版（label, hint），供双语 UI 取用；unit 保持原样
METRIC_EN = {
    "std_y": ("global contrast", "std of pixel luma; overall light-and-shadow contrast"),
    "local_contrast": ("local contrast", "high-pass std; measures light pools and chiaroscuro edges"),
    "dynamic_range": ("dynamic range", "p95−p05 span without the extreme ends"),
    "bimodality": ("bimodality", "BC > 0.555 means separated light/shadow (chiaroscuro)"),
    "sat_mean": ("mean saturation", "whole-image mean HSV saturation"),
    "colorfulness": ("colorfulness", "Hasler metric; closer to perceived richness than plain saturation"),
    "warmth": ("warmth", "R−B; positive is warm, negative is cool"),
    "split_b": ("split tone Δb*", "HL b* − SH b*; highlights warmer/yellower than shadows"),
    "shadow_frac": ("shadow fraction", "area of Y < 0.15"),
    "clip_white": ("clipped white", "share of near-white pixels; high means hard-clipped highlights"),
    "lab_b": ("global b*", "Lab b*; positive yellow, negative blue"),
    "skin_frac": ("skin fraction", "coarse Lab skin-pixel ratio, not face detection"),
    "mean_y": ("mean luma", "whole-image Rec.709 luma"),
    "grain_std": ("grain", "high-frequency residual after bilateral filtering"),
}

DECISION_KEEP = "keep"
DECISION_DROP = "drop"
DECISION_MAYBE = "maybe"
VALID_DECISIONS = {DECISION_KEEP, DECISION_DROP, DECISION_MAYBE, ""}

# 离群诊断的指标分组：同样都是「超出 IQR 栅栏」，含义完全不同——
# 调色偏离是风格本身变了（该剔/复核）；光影·题材偏离是布光变体（建议保留）；
# 技术偏离更像重压缩/锐化残留（需复核）。顺序即判定优先级。
# 条目为 (key, 中文标签, 英文标签)，前端按语言取用。
METRIC_FAMILIES = {
    "tone": [
        ("sat_mean", "平均饱和", "mean saturation"),
        ("sat_shadow", "阴影饱和", "shadow saturation"),
        ("sat_mid", "中间调饱和", "midtone saturation"),
        ("sat_highlight", "高光饱和", "highlight saturation"),
        ("chroma_mean", "Lab 色度", "Lab chroma"),
        ("colorfulness", "色彩浓度", "colorfulness"),
        ("warmth", "暖度", "warmth"),
        ("lab_a", "整图 a*", "global a*"),
        ("lab_b", "整图 b*", "global b*"),
        ("shadow_a", "阴影 a*", "shadow a*"),
        ("shadow_b", "阴影 b*", "shadow b*"),
        ("highlight_a", "高光 a*", "highlight a*"),
        ("highlight_b", "高光 b*", "highlight b*"),
        ("split_a", "分色 Δa*", "split tone Δa*"),
        ("split_b", "分色 Δb*", "split tone Δb*"),
        ("rg_mean", "R−G", "R−G"),
        ("rb_mean", "R−B", "R−B"),
    ],
    "light": [
        ("mean_y", "平均亮度", "mean luma"),
        ("std_y", "全局对比", "global contrast"),
        ("dynamic_range", "动态范围", "dynamic range"),
        ("p05_y", "暗部 p05", "shadow p05"),
        ("p50_y", "中位亮度", "median luma"),
        ("p95_y", "亮部 p95", "highlight p95"),
        ("shadow_frac", "阴影占比", "shadow fraction"),
        ("highlight_frac", "高光占比", "highlight fraction"),
        ("clip_black", "死黑", "crushed black"),
        ("clip_white", "死白", "clipped white"),
        ("hist_entropy", "直方图熵", "histogram entropy"),
        ("bimodality", "双峰性", "bimodality"),
        ("local_contrast", "局部对比", "local contrast"),
        ("skin_frac", "肤色占比", "skin fraction"),
        ("grad_mean", "梯度均值", "gradient energy"),
        ("grad_anisotropy", "梯度方向性", "gradient anisotropy"),
    ],
    "tech": [
        ("grain_std", "颗粒", "grain"),
        ("laplacian_var", "高频/锐度", "HF energy / sharpness"),
    ],
}

METRIC_FAMILIES_ORDER = list(METRIC_FAMILIES.keys())

# 全量指标的中英文标签（供诊断显示用），由 METRIC_FAMILIES 汇总
METRIC_LABELS = {}
for _fam in METRIC_FAMILIES.values():
    for _key, _zh, _en in _fam:
        METRIC_LABELS[_key] = {"zh": _zh, "en": _en}
