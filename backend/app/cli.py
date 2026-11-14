"""Command line: python -m app.cli <command> [--scale starter|full] [--seed N].

generate   write the dataset (CSV, plus JSON and SQL for starter) with a manifest
validate   run the nine validation checks on the written files, write validation_summary.json
repro      generate twice with the same seed and compare row counts and checksums, write repro.json
reconcile  run the detectors on the written files and score them against ground truth, write evaluation.json
load       bulk-load the written files and the detected exceptions into PostgreSQL (DATABASE_URL)
all        generate, validate, repro and reconcile (no database needed; `load` is separate)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.datagen import repro as repro_mod
from app.datagen import validate as validate_mod
from app.datagen import writer
from app.datagen.generator import DEFAULT_SEED, generate
from app.datagen.scale import SCALES
from app.engine import detect, evaluate, loader

ROOT = Path(__file__).resolve().parents[2]


def paths(scale: str) -> dict[str, Path]:
    return {"data": ROOT / "data" / scale, "reports": ROOT / "reports" / scale, "seed": ROOT / "database" / "seed"}


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")


def cmd_generate(a) -> int:
    ds, gt = generate(a.scale, a.seed)
    p = paths(a.scale)
    full = a.scale == "full"
    m = writer.write(ds, gt, p["data"], a.scale, a.seed, ("csv",) if full else ("csv", "json", "sql"), gz=full,
                     sql_dir=None if full else p["seed"])
    print(f"wrote {m['totals']['rows']} rows in {len(m['tables'])} tables, {m['totals']['ground_truth_rows']} "
          f"ground-truth rows -> {p['data']}")
    return 0


def cmd_validate(a) -> int:
    ds, gt = writer.read(paths(a.scale)["data"])
    res = validate_mod.run(ds, gt, SCALES[a.scale])
    write_json(paths(a.scale)["reports"] / "validation_summary.json", res)
    for c in res["checks"]:
        print(f"{c['id']} {c['name']:<42} rows={c['rows_checked']:>8} violations={c['violations']:>4} "
              f"expected={c['expected']:>4} unexpected={c['unexpected']}")
    print("VALIDATION", "PASSED" if res["ok"] else "FAILED", f"({res['labels']} labelled cases, "
          f"{len(res['labels_without_violation'])} not observed)")
    return 0 if res["ok"] else 1


def cmd_repro(a) -> int:
    res = repro_mod.check(a.scale, a.seed, paths(a.scale)["data"] / "manifest.json")
    write_json(paths(a.scale)["reports"] / "repro.json", res)
    print("REPRODUCIBLE" if res["identical"] else "NOT REPRODUCIBLE", f"({res['total_rows']} rows, "
          f"{sum(t['match'] for t in res['tables'].values())}/{len(res['tables'])} tables identical)")
    if "matches_committed_manifest" in res:
        print("matches the committed manifest:", res["matches_committed_manifest"])
    return 0 if res["identical"] else 1


def cmd_reconcile(a) -> int:
    ds, gt = writer.read(paths(a.scale)["data"])
    exceptions = detect.run(ds)                      # detectors never receive the ground truth
    res = evaluate.run(exceptions, gt, ds)
    write_json(paths(a.scale)["reports"] / "evaluation.json", res)
    write_json(paths(a.scale)["reports"] / "exceptions.json", exceptions)
    d = res["detection"]
    for kind, t in d["per_type"].items():
        print(f"{kind:<30} labelled={t['labelled']:>4} reported={t['reported']:>4} precision={t['precision']} "
              f"recall={t['recall']} f1={t['f1']}")
    o = d["overall"]
    print(f"OVERALL precision={o['precision']} recall={o['recall']} f1={o['f1']} macro_f1={d['macro_f1']}")
    b = res["business"]
    print(f"collection_rate={b['collection_rate']} reconciliation_rate={b['reconciliation_rate']} "
          f"late_fee_incidence={b['late_fee_incidence']}")
    return 0 if o["false_positives"] == 0 and o["false_negatives"] == 0 else 1


def cmd_load(a) -> int:
    import time

    from app.db import engine
    ds, gt = writer.read(paths(a.scale)["data"])
    started = time.perf_counter()
    counts = loader.load(engine, ds, gt, detect.run(ds))
    print(f"loaded {sum(counts.values())} rows into {len(counts)} tables in {time.perf_counter() - started:.1f}s")
    return 0


def cmd_all(a) -> int:
    return max(cmd_generate(a), cmd_validate(a), cmd_repro(a), cmd_reconcile(a))


COMMANDS = {"generate": cmd_generate, "validate": cmd_validate, "repro": cmd_repro, "reconcile": cmd_reconcile,
            "load": cmd_load, "all": cmd_all}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("--scale", choices=sorted(SCALES), default="starter")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    a = ap.parse_args(argv)
    return COMMANDS[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
