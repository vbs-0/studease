import copy

import pytest

from app.datagen.generator import DEFAULT_SEED, generate


@pytest.fixture(scope="session")
def baseline():
    """The clean starter dataset: no anomalies injected."""
    return generate("starter", DEFAULT_SEED, inject=False)[0]


@pytest.fixture(scope="session")
def injected():
    """The starter dataset with the five labelled anomalies, plus its ground truth."""
    return generate("starter", DEFAULT_SEED, inject=True)


@pytest.fixture
def clean(baseline):
    """A private copy a test may modify."""
    return copy.deepcopy(baseline)
