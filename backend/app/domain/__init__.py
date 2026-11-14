"""Pure business rules (spec section 5). No database, no HTTP, no clock, no randomness.

The generator, the detectors and the API all call these functions, so each rule exists exactly once.
Rows are plain dicts keyed by column name; money is integer paise.
"""
