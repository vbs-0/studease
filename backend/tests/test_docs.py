"""The generated documents must match what the code would generate now (they cannot go stale)."""
from app import docs_gen, schema


def test_committed_generated_docs_are_up_to_date():
    assert docs_gen.check() == [], "run `python scripts/dev.py docs` and commit the result"


def test_data_dictionary_documents_every_table_and_every_field():
    text = docs_gen.data_dictionary()
    for name in docs_gen.ORDER:
        assert f"## {name}\n" in text
        for column in schema.columns(name):
            assert f"| `{column}` |" in text, (name, column)


def test_the_erd_has_a_line_for_every_foreign_key():
    text = docs_gen.erd()
    expected = sum(len(t.foreign_keys) for t in schema.TABLES.values())
    assert sum(1 for line in text.splitlines() if "--" in line and '"' in line) == expected


def test_generation_is_deterministic():
    assert docs_gen.data_dictionary() == docs_gen.data_dictionary() and docs_gen.erd() == docs_gen.erd()
