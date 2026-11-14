"""One entry point for every scale: valid baseline first, then labelled anomalies."""
from app import schema
from app.datagen import anomalies
from app.datagen.plan import build_world
from app.datagen.scale import SCALES, Scale
from app.datagen.simulate import build_dataset

Dataset = dict[str, list[dict]]
DEFAULT_SEED = 20261022


def generate(scale: str | Scale, seed: int = DEFAULT_SEED, inject: bool = True) -> tuple[Dataset, list[dict]]:
    """Return (tables, ground_truth). With inject=False the data is the clean baseline and ground truth is empty.

    Derived values (totals, balances, statuses, dates) come from the simulation, never from separate draws."""
    sc = SCALES[scale] if isinstance(scale, str) else scale
    ds = build_dataset(build_world(sc, seed), sc, seed)
    truth = anomalies.inject(ds, sc, seed) if inject else []
    for name in schema.DATA_TABLES:           # a row must carry exactly the columns of its table
        cols = set(schema.columns(name))
        for row in ds[name][:1]:
            assert set(row) == cols, f"{name}: {set(row) ^ cols}"
    return ds, truth
