// Lookprint bilingual string table.
// t(key, vars) does {placeholder} substitution; lang stored in localStorage.
window.LOOKPRINT_I18N = {
  zh: {
    tagline: "视觉风格指纹",
    nav_overview: "概览", nav_review: "离群筛选", nav_scan: "候选扫描", nav_settings: "项目",

    n_images: "图片数", gold_sub: "金标准",
    median_dist: "距离中位数", median_dist_sub: "数值越小，越接近这套风格",
    p90: "90 分位", p90_sub: "默认离群阈值",
    clusters: "GMM 簇", clusters_sub: "1 = 风格单簇",
    go_setup: "去「项目」页设置金标准数据集",
    go_setup_desc: "在「项目」页选择作为风格基准的数据集文件夹并分析，概览即会显示这套风格的指纹。",

    typical9: "典型 9 张", typical9_sub: "离集合中心最近",
    farthest9: "最远 9 张", farthest9_sub: "先看这些",
    hists: "色阶与示波器", light_sat: "光影 × 饱和",
    chart_label: "局部对比 × 饱和", axis_x: "局部对比", axis_y: "饱和度",

    cut: "距离阈值",
    f_all: "全部", f_open: "未标", f_keep: "保留", f_maybe: "待定", f_drop: "剔除",
    f_pass: "符合", f_review: "需复核", f_marked: "已标记",
    export_remaining: "导出清理后剩余…", export_dropped: "导出已剔除…", export_marked: "复制已标记到文件夹…",
    review_hint: "剔除只写入标记，金标准原图不动。诊断分色：红＝调色（风格本身，建议复核/剔除）、蓝＝光影·题材（布光变体，建议保留）、紫＝多维偏离、黄＝技术（重压缩/锐化噪声）、灰＝组合偏离（单项未越界但多项温和偏高叠加，见「偏离贡献」）。距离仅决定排序，去留请结合诊断与人工判断。",
    review_count: "{a} / {b} 张离群 · 剩余 {c}/{d} 张",
    empty_cut: "该阈值下没有离群图",

    keep: "保留", maybe: "待定", drop: "剔除",
    k_keep: "1 保留", k_maybe: "2 待定", k_drop: "3 剔除",
    mark: "标记候选", marked: "已标记", unmark: "取消标记",
    b_pass: "符合", b_review: "需复核",

    scan_ph: "候选图片文件夹路径", browse: "选择文件夹", recursive: "含子文件夹", scan_btn: "扫描",
    scan_summary: "{p} 符合 / {n} 张 · 阈值 {t}",
    mark_pass: "标记全部符合项",
    empty_scan: "选择一个文件夹开始扫描", no_match: "没有匹配的图片",
    no_pass: "无符合项可标记",

    gold_title: "金标准数据集",
    gold_desc: "这批图定义了目标风格：指纹由此计算得出，其余图像均按与这套风格的距离评分。",
    project_name: "项目名", gold_path: "金标准路径",
    percentile: "离群分位（默认 90）",
    save: "保存", reanalyze: "重新分析金标准",
    saved: "已保存", toast_saved: "项目已保存",

    select_folder: "选择文件夹", export_to: "导出到文件夹",
    use_this: "使用此文件夹", export_here: "导出到此文件夹",
    close: "关闭", pick_drive: "选择磁盘", n_images_fmt: "{n} 张图",
    enter_folder: "请先进入一个文件夹", empty_list: "（空）", up_level: "上一级",

    done: "完成", marked_n: "已标记 {n} 张",
    copied: "已复制 {n} 个文件至 {d}，原图未改动",

    v_tone: "调色家族偏离", v_tone_near: "调色轻微偏离",
    v_multi: "多维偏离", v_multi_near: "多维轻微偏离",
    v_tech: "疑似技术噪声", v_tech_near: "轻微技术偏离",
    v_light: "布光变体", v_combo: "组合偏离", v_in: "仍在风格内",
    a_tone: "调色已脱离这一批的整体水准，属于风格本身的偏离，建议复核或剔除",
    a_tone_near: "偏离幅度较小，整体距离仍在风格范围内，建议暂保留",
    a_multi: "多项指标同时偏离，建议复核",
    a_multi_near: "整体距离仍在风格范围内，建议暂保留",
    a_tech: "疑似重压缩或过度锐化所致，非风格问题，建议复核",
    a_tech_near: "整体距离仍在风格范围内，可忽略",
    a_light: "由题材引起的偏离，有助于泛化，建议保留",
    a_combo: "单项均未越界，距离由多项轻微偏离叠加推高，需人工判断",
    f_tone: "调色", f_light: "光影·题材", f_tech: "技术", f_combo: "偏离贡献",
    dir_high: "偏高", dir_low: "偏低",
  },

  en: {
    tagline: "Visual style fingerprint",
    nav_overview: "Overview", nav_review: "Outliers", nav_scan: "Scan", nav_settings: "Project",

    n_images: "Images", gold_sub: "gold set",
    median_dist: "Median dist", median_dist_sub: "smaller = closer to set",
    p90: "P90", p90_sub: "default outlier cut",
    clusters: "GMM clusters", clusters_sub: "1 = single style cluster",
    go_setup: "Set up a gold-standard dataset in the Project tab",
    go_setup_desc: "Pick the dataset folder that defines your style in the Project tab and analyze it — this overview will then show the fingerprint.",

    typical9: "Typical 9", typical9_sub: "closest to set center",
    farthest9: "Farthest 9", farthest9_sub: "review these first",
    hists: "Histograms & scopes", light_sat: "Light × Saturation",
    chart_label: "local contrast × saturation", axis_x: "local contrast", axis_y: "saturation",

    cut: "Distance cut",
    f_all: "All", f_open: "Unmarked", f_keep: "Keep", f_maybe: "Maybe", f_drop: "Drop",
    f_pass: "Pass", f_review: "Review", f_marked: "Marked",
    export_remaining: "Export remaining…", export_dropped: "Export dropped…", export_marked: "Copy marked to folder…",
    review_hint: "Dropping only writes a marker; gold-standard files are never touched. Diagnosis colors: red = toning (the style itself; review/drop), blue = light & subject (a lighting variant; keep), purple = multi-dimension drift, yellow = technical (recompression/over-sharpening), gray = composite drift (no single out-of-range metric; see top contributors). Distance only sorts; judge by diagnosis and your eyes.",
    review_count: "{a} / {b} outliers · remaining {c}/{d}",
    empty_cut: "No images at this cut",

    keep: "Keep", maybe: "Maybe", drop: "Drop",
    k_keep: "1 Keep", k_maybe: "2 Maybe", k_drop: "3 Drop",
    mark: "Mark", marked: "Marked", unmark: "Unmark",
    b_pass: "Pass", b_review: "Review",

    scan_ph: "Path to candidate folder", browse: "Browse…", recursive: "Include subfolders", scan_btn: "Scan",
    scan_summary: "{p} pass / {n} · cut {t}",
    mark_pass: "Mark all passing",
    empty_scan: "Pick a folder and scan", no_match: "No matching images",
    no_pass: "No passing items",

    gold_title: "Gold-standard dataset",
    gold_desc: "These images define the style. The fingerprint is computed from them; new images are scored by Mahalanobis distance.",
    project_name: "Project name", gold_path: "Gold path",
    percentile: "Outlier percentile (default 90)",
    save: "Save", reanalyze: "Re-analyze gold set",
    saved: "Saved", toast_saved: "Project saved",

    select_folder: "Pick a folder", export_to: "Export to folder",
    use_this: "Use this folder", export_here: "Export here",
    close: "Close", pick_drive: "Pick a drive", n_images_fmt: "{n} images",
    enter_folder: "Enter a folder first", empty_list: "Empty", up_level: ".. up",

    done: "Done", marked_n: "Marked {n}",
    copied: "Copied {n} files to {d} (originals untouched)",

    v_tone: "Toning family drift", v_tone_near: "Mild toning drift",
    v_multi: "Multi-dimension drift", v_multi_near: "Mild multi-dimension drift",
    v_tech: "Likely technical noise", v_tech_near: "Mild technical drift",
    v_light: "Light & subject variant", v_combo: "Composite drift", v_in: "In style",
    a_tone: "Drop or review: toning is the style itself",
    a_tone_near: "Small drift; distance still in-style; keep for now",
    a_multi: "Review recommended",
    a_multi_near: "Distance still in-style; keep for now",
    a_tech: "Review: possible recompression/over-sharpening, not a style issue",
    a_tech_near: "Distance still in-style; ignore",
    a_light: "Keep: subject-driven shift, useful for generalization",
    a_combo: "No single metric out of range; distance is a composite of mild drifts — judge manually",
    f_tone: "Toning", f_light: "Light & subject", f_tech: "Technical", f_combo: "Top contributors",
    dir_high: "high", dir_low: "low",
  },
};

// 可用语言：新增语言时在此加一项，并在上方 I18N 里补全对应字典即可
window.LOOKPRINT_LANGUAGES = [
  { code: "zh", name: "中文" },
  { code: "en", name: "English" },
];

window.t = function t(key, vars) {
  const lang = (window.LOOKPRINT_LANG || "zh");
  let s = (window.LOOKPRINT_I18N[lang] && window.LOOKPRINT_I18N[lang][key]) || window.LOOKPRINT_I18N.zh[key] || key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
};
