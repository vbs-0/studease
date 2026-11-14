"""Reproducibility check (spec step 10): generate twice with the same seed and compare row counts and checksums."""
from __future__ import annotations

import json
from pathlib import Path

from app.datagen import writer
from app.datagen.generator import generate


def check(scale: str, seed: int, committed: Path | None = None) -> dict:
    """Two fresh generations must agree table by table. If a manifest is already committed, it is compared too."""
    first, second = (writer.fingerprint(*generate(scale, seed)) for _ in range(2))
    same = first == second
    result = {"scale": scale, "seed": seed, "identical": same,
              "tables": {n: {"rows": first[n]["rows"], "sha256_run1": first[n]["sha256"],
                             "sha256_run2": second[n]["sha256"], "match": first[n] == second[n]} for n in first},
              "total_rows": sum(t["rows"] for n, t in first.items() if n != writer.GT)}
    if committed and committed.exists():
        on_disk = json.loads(committed.read_text(encoding="utf-8"))
        want = {**on_disk["tables"], writer.GT: on_disk["ground_truth"]}
        result["matches_committed_manifest"] = want == first
    return result
