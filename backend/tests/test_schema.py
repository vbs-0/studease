from app import ids, schema


def test_every_table_has_a_primary_key():
    for name, t in schema.TABLES.items():
        assert list(t.primary_key.columns), name


def test_every_column_is_documented():
    for name, t in schema.TABLES.items():
        for c in t.columns:
            assert c.info.get("desc"), f"{name}.{c.name} has no description"


def test_allowed_values_have_a_check_constraint():
    for name, t in schema.TABLES.items():
        checks = {c.name for c in t.constraints if c.name}
        for c in t.columns:
            if c.info.get("allowed"):
                assert f"ck_{t.name}_{c.name}_allowed" in checks or f"{c.name}_allowed" in checks, (name, c.name)


def test_every_primary_key_table_has_an_id_pattern():
    for name, t in schema.TABLES.items():
        if len(list(t.primary_key.columns)) == 1:
            assert name in ids.PATTERNS, name


def test_input_tables_carry_no_label_columns():
    for name in schema.DATA_TABLES:
        for c in schema.columns(name):
            assert not any(w in c for w in schema.LEAK_WORDS), (name, c)
            assert not c.startswith(schema.LEAK_PREFIXES), (name, c)


def test_ground_truth_lives_in_its_own_schema():
    assert schema.ground_truth.schema == "gt"
    assert "ground_truth" not in schema.DATA_TABLES


def test_data_tables_are_parent_first():
    seen = set()
    for name in schema.DATA_TABLES:
        for fk in schema.TABLES[name].foreign_keys:
            parent = fk.column.table.name
            assert parent in seen or parent == name, f"{name} before its parent {parent}"
        seen.add(name)


def test_all_data_tables_listed():
    operational = set(schema.OPERATIONAL_TABLES) | {"ground_truth"}
    assert set(schema.TABLES) == set(schema.DATA_TABLES) | operational


def test_money_columns_are_integers():
    for name, t in schema.TABLES.items():
        for c in t.columns:
            if c.name.endswith("_paise"):
                assert c.type.__class__.__name__ == "BigInteger", (name, c.name)
