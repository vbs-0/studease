# Thin wrapper: every target runs `python scripts/dev.py <target>`, which works on Windows, macOS and Linux.
# On Windows without make, run the same commands directly:  python scripts/dev.py db-up
PY ?= python
TARGETS := install db-init db-up db-down db-reset migrate schema-sql test lint api web data validate repro load reconcile docs all help

.PHONY: $(TARGETS)
$(TARGETS):
	$(PY) scripts/dev.py $@
