# Lookprint

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](requirements.txt)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

**LoRA 训练集的视觉风格指纹。** 把一批已经肉眼选稳的图当成金标准，压成一组可解释的摄影指标；新图用马氏距离打分——离这套 look 有多近？金标准是什么风格，工具就测什么风格：胶片模拟、电影级调色、干净数码、插画渲染，皆可。

完全本地运行的小型 Web UI（FastAPI，端口 8788）：色阶/示波器、灯箱离群筛选、候选文件夹扫描。「剔除」只写标记，金标准原图永远不动。

English | [简体中文](README.zh-CN.md) | [设计说明](notes/DESIGN.md)

<!-- 截图：把 2–3 张 PNG 放进 docs/screenshots/ 并取消注释
<p align="center">
  <img src="docs/screenshots/overview.png" width="45%" />
  <img src="docs/screenshots/outlier-diagnosis.png" width="45%" />
</p>
-->

## 为什么做这个

现有数据集策展工具大多用黑盒语义分（CLIP/DINO）或单一美学分，回答的是「这是不是好照片」，而不是风格 LoRA 训练者真正的问题：

> **这张图和我这套 look 是不是同一家族——同样的调色、同样的光？**

Lookprint 用可解释的摄影指标回答：分色调（split tone）、明暗双峰性、高光滚降、颗粒残差、梯度方向。每个数字都对应你能据此行动的摄影语言——你策展的金标准定义风格，工具负责测量。并且有一个明确的设计立场：**距离大不等于该删**——大面积蓝天或雪地常常是布光变体，对 LoRA 泛化有用；真正该复核的是**调色家族**已经离开这批的图。

## 功能

- **指纹** — 每张图约 35 个可解释指标 → 集合的均值/协方差 = 风格指纹；GMM（BIC 选簇）+ PCA 投影
- **离群筛选** — 按马氏距离排序；每张图带**诊断**：越界指标按家族分组（调色 / 光影·题材 / 技术 / 组合）并给处置建议；灯箱快捷键保留/待定/剔除
- **候选扫描** — 任意文件夹按 p90 阈值打分：符合 / 需复核；标记后连 caption 一起复制到新目录
- **caption 同步导出** — 导出时图片与同名 `.txt` caption 一起复制（重名改名跟随），导出即可训练
- **完全本地** — 无云、无遥测；剔除是逻辑标记，不动原图、不写 sidecar

## 快速开始

```powershell
# Windows
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.ps1            # 或 run.bat
```

```bash
# macOS / Linux
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./run.sh
```

浏览器打开 http://127.0.0.1:8788 进入**概览**。首次使用：到**项目**页设置金标准文件夹，点**重新分析金标准**。界面支持中/EN 切换（右上角按钮）。

需要 Python 3.12+。数据集文件夹建议是图片 + 同名 `.txt` caption 的组合（caption 可选）。

## 四个页面

- **概览** — 指纹数字、最典型/最远各 9 张、色阶、矢量示波器、光影×饱和散点
- **离群筛选** — 距离滑杆列出偏离图；卡片下方是诊断；保留/待定/剔除（灯箱快捷键 1/2/3）；导出剩余或已剔除
- **候选扫描** — 对任意文件夹打分，≤ 阈值标「符合」；标记后复制（含 caption）到新目录
- **项目** — 项目名、金标准路径、离群分位（默认 90）

## 命令行

```bash
python -m lookprint analyze                      # 从金标准建指纹
python -m lookprint scan "D:/new_picks"          # 给文件夹打分
python -m lookprint scan "D:/new_picks" --recursive
```

`--project` 指定项目 id（默认取第一个已有项目）。

## 原理

每张图长边缩到 640，压成约 35 个指标：亮度分位/熵/双峰性、阴影 vs 高光的分色 a*/b*、Hasler 色彩浓度、结构张量各向异性、双边滤波颗粒残差等。集合在这些指标上的均值/协方差即指纹；新图按马氏距离打分。

**离群诊断**逐指标过 Tukey 栅栏（q ± 1.5·IQR），再按家族归类——因为同样是「越界」，含义完全不同：

| 家族 | 含义 | 建议 |
|---|---|---|
| 调色 | 调色家族离开了这批——风格本身变了 | 复核 / 剔除 |
| 光影·题材 | 题材导致（天空/雪/夜景） | 保留——利于泛化 |
| 技术 | 颗粒/锐度残差——重压缩或过锐 | 复核 |
| 组合 | 单项都没越界，多项温和偏离叠加推高距离 | 人工判断 |

整体距离仍在阈值内的越界会标注为「轻微偏离」，建议先保留。

## 项目数据

运行时数据在 `data/`（git 忽略）：

```
data/projects/<id>/
  project.json              金标准路径与分位
  fingerprint.json          可读摘要
  fingerprint.pkl           scaler / 协方差 / GMM / PCA
  metrics.csv               每张图的指标与距离
  plots/                    分析图表（图内标签为中文）
  decisions.json            离群筛选：keep / maybe / drop
  marked_candidates.json    扫描标记
  scans/ + last_scan.json   扫描历史
```

换一个不同风格的数据集作基准并重新分析后，所有统计（指纹、距离、阈值、诊断栅栏、图表）都从新图集重算——没有写死的风格数值。旧数据集的剔除标记会在分析成功后自动清空；扫描历史保留，但其中的分数是按旧指纹打的。

## 开发

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

## 参与贡献

欢迎 Issue 和 PR。值得探索的方向：按文件格式（PNG/JPEG）分组统计、在摄影指标之外加语义层（CLIP/DINOv2）、多项目管理 UI。

## 许可

[MIT](LICENSE)
