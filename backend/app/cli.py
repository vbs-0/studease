"""Command line: python -m app.cli <command> [--scale starter|full] [--seed N].

generate   write the dataset (CSV, plus JSON and SQL for starter) with a manifest
validate   run the nine validation checks on the written files, write validation_summary.json
repro      generate twice with the same seed and compare row counts and checksums, write repro.json
all        generate, validate and repro (the database steps are separate: load, reconcile)
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


def cmd_all(a) -> int:
    return max(cmd_generate(a), cmd_validate(a), cmd_repro(a))


COMMANDS = {"generate": cmd_generate, "validate": cmd_validate, "repro": cmd_repro, "all": cmd_all}


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
