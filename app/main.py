from __future__ import annotations

import os
import sys
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lookprint.constants import METRIC_EN, METRIC_LABELS, METRIC_META, VALID_DECISIONS  # noqa: E402
from lookprint.diagnosis import add_diagnosis  # noqa: E402
from lookprint.pipeline import build_gold, score_candidates  # noqa: E402
from lookprint.store import (  # noqa: E402
    collect_export_paths,
    copy_files,
    load_decisions,
    load_json,
    load_project,
    project_dir,
    read_metrics_csv,
    save_decisions,
    save_json,
    save_project,
)
STATIC = Path(__file__).resolve().parent / "static"
PLOT_NAMES = [
    "01_luma_hist_overlay.png",
    "02_rgb_hist_mean.png",
    "03_vectorscope_lab.png",
    "04_split_tone.png",
    "05_contrast_vs_sat.png",
    "06_pca.png",
    "07_metric_boxplots.png",
    "08_consistency_curve.png",
]

app = FastAPI(title="Lookprint", version="0.1.0")
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


class ProjectUpdate(BaseModel):
    name: str | None = None
    gold_path: str | None = None
    threshold_percentile: float | None = Field(default=None, ge=50, le=99.5)


class DecisionBody(BaseModel):
    file: str
    decision: str


class DecisionBulk(BaseModel):
    items: dict[str, str]


class ScanBody(BaseModel):
    folder: str
    recursive: bool = False


class MarkBody(BaseModel):
    paths: list[str]
    marked: bool = True


class ExportBody(BaseModel):
    dest: str
    paths: list[str] | None = None
    kind: str = "candidates"  # candidates | dropped | remaining
    dry_run: bool = False


def _job(kind: str, fn) -> str:
    jid = uuid.uuid4().hex[:12]
    rec = {
        "id": jid,
        "kind": kind,
        "status": "running",
        "current": 0,
        "total": 0,
        "file": "",
        "error": None,
        "message": "",
    }
    with _jobs_lock:
        _jobs[jid] = rec

    def run():
        try:

            def progress(i, n, name):
                rec["current"] = i
                rec["total"] = n
                rec["file"] = name
                rec["message"] = f"{i}/{n}  {name}"

            fn(progress)
            rec["status"] = "done"
            rec["message"] = "完成"
        except Exception as exc:
            rec["status"] = "error"
            rec["error"] = str(exc)
            rec["message"] = str(exc)
            rec["trace"] = traceback.format_exc()

    threading.Thread(target=run, daemon=True).start()
    return jid


def _metrics(proj=None):
    proj = proj or load_project()
    return read_metrics_csv(project_dir(proj["id"]) / "metrics.csv")


def _fingerprint(proj=None):
    proj = proj or load_project()
    path = project_dir(proj["id"]) / "fingerprint.json"
    return load_json(path, None)


@app.get("/api/health")
def health():
    return {"ok": True, "name": "lookprint"}


@app.get("/api/project")
def get_project():
    proj = load_project()
    fp = _fingerprint(proj)
    return {
        "project": proj,
        "has_fingerprint": fp is not None,
        "fingerprint_summary": None
        if fp is None
        else {
            "n_images": fp.get("n_images"),
            "maha_median": fp.get("maha_median"),
            "maha_p90": fp.get("maha_p90"),
            "maha_p95": fp.get("maha_p95"),
            "n_gmm_components": fp.get("n_gmm_components"),
            "analyzed_at": fp.get("analyzed_at"),
        },
        "metric_meta": [
            {"key": k, "label": lab, "unit": unit, "hint": hint, "label_en": en[0], "hint_en": en[1]}
            for k, lab, unit, hint in METRIC_META
            for en in (METRIC_EN.get(k),)
        ],
        "metric_labels": METRIC_LABELS,
    }


@app.put("/api/project")
def put_project(body: ProjectUpdate):
    proj = load_project()
    if body.name is not None:
        proj["name"] = body.name.strip() or proj["name"]
    if body.gold_path is not None:
        p = Path(body.gold_path)
        if not p.is_dir():
            raise HTTPException(400, f"文件夹不存在: {p}")
        proj["gold_path"] = str(p)
    if body.threshold_percentile is not None:
        proj["threshold_percentile"] = float(body.threshold_percentile)
    return save_project(proj)


@app.post("/api/analyze")
def start_analyze():
    with _jobs_lock:
        running = [j for j in _jobs.values() if j["status"] == "running"]
        if running:
            return running[0]
    jid = _job("analyze", lambda progress: build_gold(progress=progress))
    with _jobs_lock:
        return _jobs[jid]


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    with _jobs_lock:
        rec = _jobs.get(jid)
    if not rec:
        raise HTTPException(404, "job not found")
    return rec


@app.get("/api/overview")
def overview():
    proj = load_project()
    fp = _fingerprint(proj)
    rows = _metrics(proj)
    decisions = load_decisions(proj["id"])
    plots_dir = project_dir(proj["id"]) / "plots"
    plots = [n for n in PLOT_NAMES if (plots_dir / n).exists()]
    cards = []
    if fp and fp.get("metrics"):
        for key, label, unit, hint in METRIC_META[:8]:
            st = fp["metrics"].get(key)
            if not st:
                continue
            cards.append({"key": key, "label": label, "unit": unit, "hint": hint, **st})
    typical, outliers = [], []
    if rows:
        ordered = sorted(rows, key=lambda r: float(r.get("mahalanobis") or 0))
        typical = ordered[:9]
        outliers = list(reversed(ordered[-9:]))
        stats = (fp or {}).get("metrics") or {}
        threshold = (fp or {}).get("maha_p90")
        add_diagnosis(typical, stats, threshold)
        add_diagnosis(outliers, stats, threshold)
    n_drop = sum(1 for v in decisions.values() if v == "drop")
    n_maybe = sum(1 for v in decisions.values() if v == "maybe")
    n_keep = sum(1 for v in decisions.values() if v == "keep")
    return {
        "project": proj,
        "fingerprint": fp,
        "plots": plots,
        "cards": cards,
        "typical": typical,
        "outliers": outliers,
        "n_metrics": len(rows),
        "decisions": {"keep": n_keep, "maybe": n_maybe, "drop": n_drop},
        "scatter": [
            {
                "file": r["file"],
                "path": r.get("path"),
                "x": r.get("local_contrast"),
                "y": r.get("sat_mean"),
                "d": r.get("mahalanobis"),
                "pc1": r.get("pc1"),
                "pc2": r.get("pc2"),
            }
            for r in rows
        ],
    }


@app.get("/api/metrics")
def metrics():
    proj = load_project()
    rows = _metrics(proj)
    decisions = load_decisions(proj["id"])
    for r in rows:
        r["decision"] = decisions.get(r["file"], "")
    return {"items": rows, "n": len(rows)}


@app.get("/api/outliers")
def outliers(min_d: float | None = None):
    proj = load_project()
    fp = _fingerprint(proj) or {}
    rows = _metrics(proj)
    decisions = load_decisions(proj["id"])
    cut = float(min_d) if min_d is not None else float(fp.get("maha_p90") or 7.57)
    items = []
    for r in rows:
        d = float(r.get("mahalanobis") or 0)
        if d >= cut:
            rec = dict(r)
            rec["decision"] = decisions.get(r["file"], "")
            items.append(rec)
    items.sort(key=lambda r: -float(r["mahalanobis"]))
    add_diagnosis(items, (fp or {}).get("metrics") or {}, cut)
    return {"threshold": cut, "n": len(items), "items": items}


@app.put("/api/decisions")
def put_decision(body: DecisionBody):
    if body.decision not in VALID_DECISIONS:
        raise HTTPException(400, "decision must be keep/drop/maybe/empty")
    decisions = load_decisions()
    if body.decision == "":
        decisions.pop(body.file, None)
    else:
        decisions[body.file] = body.decision
    save_decisions(decisions)
    return {"ok": True, "file": body.file, "decision": body.decision}


@app.put("/api/decisions/bulk")
def put_decisions_bulk(body: DecisionBulk):
    decisions = load_decisions()
    for k, v in body.items.items():
        if v not in VALID_DECISIONS:
            continue
        if v == "":
            decisions.pop(k, None)
        else:
            decisions[k] = v
    save_decisions(decisions)
    return {"ok": True, "n": len(body.items)}


@app.post("/api/scan")
def start_scan(body: ScanBody):
    folder = Path(body.folder)
    if not folder.is_dir():
        raise HTTPException(400, f"文件夹不存在: {folder}")
    with _jobs_lock:
        running = [j for j in _jobs.values() if j["status"] == "running"]
        if running:
            return running[0]

    def fn(progress):
        score_candidates(folder, recursive=body.recursive, progress=progress)

    jid = _job("scan", fn)
    with _jobs_lock:
        return _jobs[jid]


@app.get("/api/scan/last")
def last_scan():
    proj = load_project()
    data = load_json(project_dir(proj["id"]) / "last_scan.json", None)
    if data is None:
        return {"items": [], "n": 0}
    marked = {it["path"] for it in load_json(project_dir(proj["id"]) / "marked_candidates.json", {"items": []})["items"]}
    for it in data.get("items", []):
        it["marked"] = it["path"] in marked
    stats = (_fingerprint(proj) or {}).get("metrics") or {}
    threshold = data.get("threshold")
    add_diagnosis(data.get("items", []), stats, float(threshold) if threshold is not None else None)
    return data


@app.put("/api/candidates/mark")
def mark_candidates(body: MarkBody):
    proj = load_project()
    path = project_dir(proj["id"]) / "marked_candidates.json"
    blob = load_json(path, {"items": []})
    by_path = {it["path"]: it for it in blob["items"]}
    last = load_json(project_dir(proj["id"]) / "last_scan.json", {"items": []})
    lookup = {it["path"]: it for it in last.get("items", [])}
    for p in body.paths:
        if body.marked:
            src = lookup.get(p, {"path": p, "file": Path(p).name})
            by_path[p] = {
                "path": p,
                "file": src.get("file") or Path(p).name,
                "mahalanobis": src.get("mahalanobis"),
                "pass": src.get("pass"),
            }
        else:
            by_path.pop(p, None)
    blob = {"items": list(by_path.values())}
    save_json(path, blob)
    return blob


@app.get("/api/candidates/marked")
def get_marked():
    proj = load_project()
    return load_json(project_dir(proj["id"]) / "marked_candidates.json", {"items": []})


@app.post("/api/export")
def export_files(body: ExportBody):
    if body.kind not in {"candidates", "dropped", "remaining"}:
        raise HTTPException(400, "kind must be candidates, dropped, or remaining")
    dest = Path(body.dest).expanduser()
    proj = load_project()
    if not proj.get("gold_path") or not Path(proj["gold_path"]).is_dir():
        raise HTTPException(400, "金标准路径未设置，请先在「项目」页设置")
    gold = Path(proj["gold_path"]).expanduser()
    try:
        if dest.resolve() == gold.resolve():
            raise HTTPException(400, "请另选文件夹，不要写回金标准目录")
    except OSError:
        pass
    rows = _metrics(proj)
    decisions = load_decisions(proj["id"])
    marked = load_json(project_dir(proj["id"]) / "marked_candidates.json", {"items": []})
    paths = collect_export_paths(
        body.kind,
        rows,
        decisions,
        marked.get("items") or [],
        extra_paths=body.paths,
    )
    if body.dry_run:
        existing = [str(p) for p in paths if p.is_file()]
        return {"ok": True, "dry_run": True, "n": len(existing), "dest": str(dest), "files": existing}
    written = copy_files(paths, dest)
    return {"ok": True, "n": len(written), "dest": str(dest), "files": written}


@app.get("/api/browse")
def browse(path: str = ""):
    path = unquote(path or "").strip()
    if not path:
        drives = []
        if hasattr(os, "listdrives"):
            drives = list(os.listdrives())
        else:
            drives = [f"{c}:\\" for c in "CDEFG" if Path(f"{c}:\\").exists()]
        return {"path": "", "parent": None, "dirs": [{"name": d, "path": d} for d in drives], "files": []}
    p = Path(path)
    if not p.exists():
        raise HTTPException(404, "path not found")
    if p.is_file():
        p = p.parent
    dirs, files = [], []
    try:
        for child in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            if child.name.startswith("."):
                continue
            try:
                if child.is_dir():
                    dirs.append({"name": child.name, "path": str(child)})
                elif child.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
                    files.append({"name": child.name, "path": str(child)})
            except OSError:
                continue
    except OSError as exc:
        raise HTTPException(400, str(exc)) from exc
    parent = str(p.parent) if p.parent != p else ""
    return {"path": str(p), "parent": parent, "dirs": dirs, "n_images": len(files), "files": files[:80]}


@app.get("/api/plots/{name}")
def get_plot(name: str):
    if name not in PLOT_NAMES:
        raise HTTPException(404)
    path = project_dir() / "plots" / name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


def _resolved_file(path: str) -> Path:
    p = Path(unquote(path)).expanduser()
    if not p.is_file():
        raise HTTPException(404, "file not found")
    return p


@app.get("/api/raw")
def get_raw(path: str = Query(...)):
    src = _resolved_file(path)
    return FileResponse(src)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
