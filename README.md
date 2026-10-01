# Lookprint

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](requirements.txt)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

**A visual style fingerprint for LoRA training sets.** Take a dataset you have already hand-curated to a stable look — treat it as the gold standard — and compress it into a set of interpretable photographic metrics. New images are scored by Mahalanobis distance: how close do they sit to *that* look?

Runs fully local as a small web UI (FastAPI, port 8788): histograms and scopes, outlier review with a lightbox, candidate folder scanning. Dropping an image only writes a marker — gold-standard originals are never touched.

English | [简体中文](README.zh-CN.md) | [设计说明 / Design notes](notes/DESIGN.md)

<!-- Screenshots: drop 2–3 PNGs into docs/screenshots/ and uncomment
<p align="center">
  <img src="docs/screenshots/overview.png" width="45%" />
  <img src="docs/screenshots/outlier-diagnosis.png" width="45%" />
</p>
-->

## Why

Dataset curation tools usually score images with black-box embeddings (CLIP/DINO) or single aesthetic numbers. That answers *"is this a good photo?"* but not the question a style-LoRA trainer actually has:

> **Is this image the same *look* as my curated set — same color family, same light?**

Lookprint answers that with interpretable photographic metrics instead: split toning, chiaroscuro bimodality, highlight roll-off, grain residual, gradient direction. Every number maps to photographic language you can act on. The gold set defines the look — film emulation, cinematic color grading, clean digital, or any rendering style you curate. And a key design stance: **a large distance does not mean "delete it"** — a big blue sky or a snowfield is often a lighting variant that helps LoRA generalization. What deserves review is an image whose *toning family* has left the batch.

## Features

- **Fingerprint** — ~35 interpretable metrics per image → mean/covariance of the set = the style fingerprint; GMM (BIC-selected) clusters, PCA projection
- **Outlier review** — sort by Mahalanobis distance; per-image **diagnosis** groups out-of-range metrics into families (toning / light & subject / technical / composite) with a suggested action; keep / maybe / drop with lightbox hotkeys
- **Candidate scan** — score any folder against the fingerprint; pass/review by the p90 threshold; mark and copy winners to a new folder
- **Caption-aware export** — exports copy images *and* their same-stem `.txt` captions together (renames follow collisions), so the output is a ready-to-train image+caption pair
- **Fully local** — no cloud, no telemetry; dropping is logical, originals untouched, no sidecar files next to your dataset

## Quick start

```bash
# Windows
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.ps1            # or: run.bat

# macOS / Linux
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./run.sh
```

Open http://127.0.0.1:8788 — you land on **Overview**. First run: go to the **Project** tab, set your gold-standard folder, then click **Re-analyze gold set**. The UI is bilingual (中/EN toggle in the header).

Requires Python 3.12+. The dataset folder should contain images with same-stem `.txt` captions (optional but recommended).

## The four tabs

- **Overview** — fingerprint stats, 9 most-typical / 9 most-distant images, luma & RGB histograms, vectorscope, light×saturation scatter
- **Outliers** — images above a distance cut (slider); diagnosis under each card; keep/maybe/drop (`1`/`2`/`3` in the lightbox); export remaining or dropped
- **Scan** — score a candidate folder; ≤ cut = pass, else review; mark and copy marked files (with captions) to a new folder
- **Project** — project name, gold path, outlier percentile (default 90)

## Command line

```bash
python -m lookprint analyze                      # build fingerprint from the gold set
python -m lookprint scan "D:/new_picks"          # score a folder
python -m lookprint scan "D:/new_picks" --recursive
```

`--project` selects a project id (defaults to the first existing project).

## How it works

Each image is resized to 640 on the long edge and reduced to ~35 metrics: luma percentiles/entropy/bimodality, split-tone a*/b* in shadows vs highlights, Hasler colorfulness, structure-tensor anisotropy, bilateral-filter grain residual, etc. The set's mean/covariance over these metrics defines the fingerprint; a new image's Mahalanobis distance scores it.

**Outlier diagnosis** walks the Tukey fences (q ± 1.5·IQR) per metric, then groups breaches by family — because identical "out of range" numbers mean different things:

| Family | Meaning | Suggested action |
|---|---|---|
| Toning | the color family left the batch — the style itself changed | review / drop |
| Light & subject | subject-driven shift (sky, snow, night) | keep — good for generalization |
| Technical | grain/sharpness residual — recompression or over-sharpening | review |
| Composite | no single breach; mild drifts stack up to push the distance | judge manually |

If the whole distance is still below the cut, breaches are reported as *mild* — keep for now.

## Project data

Runtime data lives in `data/` (git-ignored):

```
data/projects/<id>/
  project.json              gold path & percentile
  fingerprint.json          human-readable summary
  fingerprint.pkl           scaler / covariance / GMM / PCA
  metrics.csv               per-image metrics + distances
  plots/                    analysis charts (labels in Chinese)
  decisions.json            outlier review: keep / maybe / drop
  marked_candidates.json    scan marks
  scans/ + last_scan.json   scan history
```

Re-analyzing after pointing the gold path at a *different* dataset recomputes everything (fingerprint, distances, thresholds, diagnosis fences, charts) — there are no hard-coded style values. Old drop decisions belong to the previous dataset and are cleared on a successful re-analysis; scan history is kept but its scores refer to the old fingerprint.

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

## Contributing

Issues and PRs welcome. Ideas worth exploring: per-format (PNG/JPEG) statistic groups, a semantic layer (CLIP/DINOv2) alongside the photographic layer, multi-project UI.

## License

[MIT](LICENSE)
