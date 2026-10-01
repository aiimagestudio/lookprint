from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROJECTS = DATA / "projects"

# 金标准路径不预设：首次启动由用户在「项目」页设置自己的数据集
DEFAULT_PROJECT_ID = "default"
CAPTION_EXTS = (".txt", ".caption")  # 数据集是图片 + caption 的组合；caption 与图片同名只差扩展名


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_pid() -> str:
    """默认项目：优先 'default'；否则（兼容老数据）取已有项目目录中的第一个。"""
    if (PROJECTS / DEFAULT_PROJECT_ID).is_dir():
        return DEFAULT_PROJECT_ID
    if PROJECTS.is_dir():
        dirs = sorted(p.name for p in PROJECTS.iterdir() if p.is_dir())
        if dirs:
            return dirs[0]
    return DEFAULT_PROJECT_ID


def project_dir(project_id: str | None = None) -> Path:
    d = PROJECTS / (project_id or _default_pid())
    d.mkdir(parents=True, exist_ok=True)
    (d / "plots").mkdir(exist_ok=True)
    (d / "scans").mkdir(exist_ok=True)
    return d


def default_project() -> dict:
    return {
        "id": DEFAULT_PROJECT_ID,
        "name": "My Style",
        "gold_path": "",
        "threshold_percentile": 90,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "last_analyzed_at": None,
        "n_images": 0,
    }


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_project(project_id: str | None = None) -> dict:
    d = project_dir(project_id)
    path = d / "project.json"
    if not path.exists():
        proj = default_project()
        proj["id"] = d.name
        save_json(path, proj)
        save_json(d / "decisions.json", {})
        save_json(d / "marked_candidates.json", {"items": []})
        return proj
    return load_json(path, default_project())


def save_project(proj: dict) -> dict:
    proj["updated_at"] = utc_now()
    save_json(project_dir(proj["id"]) / "project.json", proj)
    return proj


def decisions_path(project_id: str | None = None) -> Path:
    return project_dir(project_id) / "decisions.json"


def load_decisions(project_id: str | None = None) -> dict:
    return load_json(decisions_path(project_id), {})


def save_decisions(decisions: dict, project_id: str | None = None) -> dict:
    save_json(decisions_path(project_id), decisions)
    return decisions


def write_metrics_csv(path: Path, rows: list[dict], extra: dict[str, list]) -> None:
    skip = {k for k in rows[0] if k.startswith("_")} if rows else set()
    fieldnames = [k for k in (rows[0] if rows else {}) if k not in skip]
    for k in extra:
        if k not in fieldnames:
            fieldnames.append(k)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["file", "path"] + fieldnames)
        w.writeheader()
        for i, row in enumerate(rows):
            rec = {"file": extra["file"][i], "path": extra["path"][i]}
            for k in fieldnames:
                if k in extra:
                    rec[k] = extra[k][i]
                elif k in row:
                    rec[k] = row[k]
            w.writerow(rec)


def read_metrics_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        item = {}
        for k, v in r.items():
            if k in ("file", "path"):
                item[k] = v
            elif k == "cluster":
                try:
                    item[k] = int(float(v))
                except (TypeError, ValueError):
                    item[k] = v
            else:
                try:
                    item[k] = float(v)
                except (TypeError, ValueError):
                    item[k] = v
        out.append(item)
    return out


def copy_files(paths: list[Path], dest: Path) -> list[str]:
    """Copy files (and their same-stem caption files) into dest. Never deletes originals."""
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for src in paths:
        src = Path(src)
        if not src.is_file():
            continue
        target = dest / src.name
        if target.exists():
            stem = f"{src.stem}__{abs(hash(str(src))) % 10**8}"
            target = dest / f"{stem}{src.suffix}"
        else:
            stem = src.stem
        shutil.copy2(src, target)
        written.append(str(target))
        for ext in CAPTION_EXTS:
            cap = src.with_suffix(ext)
            if cap.is_file():
                cap_target = dest / f"{stem}{ext}"
                shutil.copy2(cap, cap_target)
                written.append(str(cap_target))
                break
    return written


def collect_export_paths(
    kind: str,
    rows: list[dict],
    decisions: dict,
    marked_items: list[dict],
    extra_paths: list[str] | None = None,
) -> list[Path]:
    """Pick source files to copy. Never deletes gold-standard originals."""
    if kind == "dropped":
        names = extra_paths if extra_paths else [k for k, v in decisions.items() if v == "drop"]
        by_file = {r["file"]: r for r in rows}
        paths = []
        for name in names:
            rec = by_file.get(Path(name).name) or by_file.get(name)
            if rec and rec.get("path"):
                paths.append(Path(rec["path"]))
        return paths
    if kind == "remaining":
        dropped = {k for k, v in decisions.items() if v == "drop"}
        return [Path(r["path"]) for r in rows if r.get("path") and r.get("file") not in dropped]
    if extra_paths:
        return [Path(p) for p in extra_paths]
    return [Path(it["path"]) for it in marked_items if it.get("path")]
