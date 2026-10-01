from __future__ import annotations

import argparse
from pathlib import Path

from lookprint.pipeline import build_gold, score_candidates


def main():
    ap = argparse.ArgumentParser(prog="lookprint", description="Film-look fingerprint for LoRA sets")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_gold = sub.add_parser("analyze", help="build fingerprint from the gold dataset")
    p_gold.add_argument("--project", default=None)

    p_scan = sub.add_parser("scan", help="score a folder against the gold fingerprint")
    p_scan.add_argument("folder", type=Path)
    p_scan.add_argument("--recursive", action="store_true")
    p_scan.add_argument("--project", default=None)

    args = ap.parse_args()

    def progress(i, n, name):
        print(f"  {i}/{n}  {name}", flush=True)

    if args.cmd == "analyze":
        fp = build_gold(project_id=args.project, progress=progress)
        print(f"n={fp['n_images']}  p90={fp['maha_p90']:.3f}  clusters={fp['n_gmm_components']}")
    elif args.cmd == "scan":
        result = score_candidates(args.folder, recursive=args.recursive, project_id=args.project, progress=progress)
        print(f"pass {result['n_pass']}/{result['n']}  threshold={result['threshold']:.3f}")
        for it in result["items"][:20]:
            flag = "PASS" if it["pass"] else "REVIEW"
            print(f"  {flag:6}  {it['mahalanobis']:.3f}  {it['file']}")


if __name__ == "__main__":
    main()
