# Lookprint

LoRA 训练集的视觉风格指纹：把已经肉眼选稳的图当成金标准，压成一组可解释的摄影指标，用马氏距离判断新图是否像这套 **反转片光色 + 强光影**。

本地 Web UI 用来看色阶/示波器、筛离群片、扫描候选文件夹。剔除只写标记，金标准原图不动。

设计思路见 [`notes/DESIGN.md`](notes/DESIGN.md)。

## 启动

已有虚拟环境时：

```powershell
E:\lookprint\run.ps1
```

浏览器打开 http://127.0.0.1:8788

启动后直接进入**概览**，默认金标准：

`F:\ai-toolkit\datasets\qwenimage2_1_radiancechromevoluptuous_v1_0`

（项目 `radiance-chrome`，当前约 166 张，指纹已建好。）

第一次从零搭环境：

```powershell
cd E:\lookprint
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.ps1
```

金标准路径可在「项目」里改，旁边「选择文件夹」是可选操作，启动不会强制弹选择框。改完路径后点「重新分析金标准」才会重算指纹。

「项目」里改金标准路径后点「重新分析金标准」，一切统计都从新图集重算：指纹、马氏距离、p90 阈值、诊断栅栏、所有图表。没有写死的风格数值（`7.57` 之类只是未建指纹时的兜底显示值）。

注意：**换基准路径后重新分析，旧的剔除标记（decisions）会自动清空**——它们属于上一个数据集，按文件名保留会错配。扫描历史和已标记候选是历史记录，保留不清，但其中的分数是按旧指纹打的，换基准后请重新扫描。

## 四个页面

- **概览** — 指纹数字、离中心最近/最远各 9 张、色阶、矢量示波器、光影×饱和散点
- **离群筛选** — 按马氏距离列出本集偏离图；每张卡下方有**离群诊断**：把越界指标按家族分组（红＝调色、蓝＝光影·题材、黄＝技术）并给处置建议——调色偏离是风格本身（该剔/复核），光影·题材偏离多半是布光变体（建议保留），技术偏离更像重压缩/锐化残留（需复核）；整体距离仍在风格内的轻微越界会标注为「轻微偏离」。保留 / 待定 / 剔除（灯箱里快捷键 1 / 2 / 3）
- **候选扫描** — 对任意文件夹打分，≤ 默认阈值标「符合」，其余「需复核」；可标记后复制到新目录
- **项目** — 项目名、金标准路径、离群分位（默认 90）

## 剔除与导出

「剔除」只写入 `data/projects/<id>/decisions.json`，**不删除、不移动金标准文件**，也不在图片旁边写 sidecar。

离群筛选页：

- **导出清理后剩余…** — 复制金标准里所有未剔除的图（保留 / 待定 / 未标都算剩余）到你指定的文件夹，当作下一轮训练集
- **导出已剔除…** — 只复制被标成剔除的图，方便复核

候选扫描页的「复制已标记到文件夹」同样是复制。导出目录不能是金标准目录本身。

导出是**图片 + caption 同步**：如果图片旁边有同名 caption（`同stem.txt`，兼容 `.caption`），会跟着图片一起复制，重名冲突改名时 caption 也跟着改，保证导出目录仍是可直接训练的图片+caption 组合。

距离大不等于该剔：大面积蓝天、沙漠、雪地常常是布光变体，对 LoRA 泛化有用。真正该复核的是调色家族已经离开这批的图。

## 命令行

```powershell
cd E:\lookprint
.\.venv\Scripts\python.exe -m lookprint analyze
.\.venv\Scripts\python.exe -m lookprint scan "D:\new_picks"
.\.venv\Scripts\python.exe -m lookprint scan "D:\new_picks" --recursive
```

`--project` 可省略，默认 `radiance-chrome`。

## 项目数据

运行时写在 `data/`（git 忽略）：

```
data/projects/<id>/
  project.json              金标准路径与分位
  fingerprint.json          可读摘要
  fingerprint.pkl           scaler / 协方差 / GMM / PCA
  metrics.csv               每张图的指标与马氏距离
  plots/                    色阶、示波器、接触印相
  decisions.json            离群筛选：keep / maybe / drop
  marked_candidates.json    扫描标记
  scans/                    历次扫描
  last_scan.json
```

## 布局

```
E:\lookprint\
  lookprint\     指标、指纹、出图
  app\           FastAPI + 静态 UI（:8788）
  notes\         设计说明与原始一次性分析脚本
  data\          运行时项目数据
  requirements.txt
  run.ps1 / run.bat
```

支持 `.jpg` `.jpeg` `.png` `.webp` `.bmp` `.tif` `.tiff`。分析时长边缩到 640。
