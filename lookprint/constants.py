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
    ("std_y", "全局对比", "std(Y)", "整图像素亮度的标准差，反转片强光比通常在 0.22–0.29"),
    ("local_contrast", "局部对比", "high-pass std", "去掉低频后的对比，测光斑和明暗交界"),
    ("dynamic_range", "动态范围", "p95−p05", "去掉两端极值后的跨度"),
    ("bimodality", "双峰性", "BC", ">0.555 表示明暗分离（chiaroscuro）"),
    ("sat_mean", "平均饱和", "HSV S", "整图平均饱和度"),
    ("colorfulness", "色彩浓度", "Hasler", "比单纯饱和度更接近观感的浓郁程度"),
    ("warmth", "暖度", "R−B", "正值偏暖，负值偏冷"),
    ("split_b", "分色 Δb*", "HL b* − SH b*", "高光相对阴影更黄/暖"),
    ("shadow_frac", "阴影占比", "Y<0.15", "暗部面积"),
    ("clip_white", "死白占比", "Y>0.98", "胶片滚降时应该很低"),
    ("lab_b", "整图 b*", "Lab b*", "正黄负蓝"),
    ("skin_frac", "肤色占比", "Lab blob", "粗略肤色像素比例，不是人脸检测"),
    ("mean_y", "平均亮度", "Y", "整图 Rec.709 亮度"),
    ("grain_std", "颗粒感", "HF residual", "双边滤波后的高频残差"),
]

DECISION_KEEP = "keep"
DECISION_DROP = "drop"
DECISION_MAYBE = "maybe"
VALID_DECISIONS = {DECISION_KEEP, DECISION_DROP, DECISION_MAYBE, ""}

# 离群诊断的指标分组：同样都是「超出 IQR 栅栏」，含义完全不同——
# 调色偏离是风格本身变了（该剔/复核）；光影·题材偏离是布光变体（建议保留）；
# 技术偏离更像重压缩/锐化残留（需复核）。顺序即判定优先级。
METRIC_FAMILIES = {
    "调色": [
        ("sat_mean", "平均饱和"), ("sat_shadow", "阴影饱和"), ("sat_mid", "中间调饱和"),
        ("sat_highlight", "高光饱和"), ("chroma_mean", "Lab 色度"), ("colorfulness", "色彩浓度"),
        ("warmth", "暖度"), ("lab_a", "整图 a*"), ("lab_b", "整图 b*"),
        ("shadow_a", "阴影 a*"), ("shadow_b", "阴影 b*"),
        ("highlight_a", "高光 a*"), ("highlight_b", "高光 b*"),
        ("split_a", "分色 Δa*"), ("split_b", "分色 Δb*"),
        ("rg_mean", "R−G"), ("rb_mean", "R−B"),
    ],
    "光影·题材": [
        ("mean_y", "平均亮度"), ("std_y", "全局对比"), ("dynamic_range", "动态范围"),
        ("p05_y", "暗部 p05"), ("p50_y", "中位亮度"), ("p95_y", "亮部 p95"),
        ("shadow_frac", "阴影占比"), ("highlight_frac", "高光占比"),
        ("clip_black", "死黑"), ("clip_white", "死白"),
        ("hist_entropy", "直方图熵"), ("bimodality", "双峰性"), ("local_contrast", "局部对比"),
        ("skin_frac", "肤色占比"), ("grad_mean", "梯度均值"), ("grad_anisotropy", "梯度方向性"),
    ],
    "技术": [
        ("grain_std", "颗粒"), ("laplacian_var", "高频/锐度"),
    ],
}
