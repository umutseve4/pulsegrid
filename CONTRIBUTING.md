# Contributing to PulseGrid

PulseGrid is evidence-first: changes should keep claims bounded and pair behavior with executable proof.

## Development baseline

- Use Python 3.12 or newer.
- Create a focused branch; do not commit directly to `main`.
- Keep the standard-library-only core free of unnecessary runtime dependencies.
- Never commit credentials, tokens, personal data, generated databases, or local environment files.

## Validate a change

Run the complete invariant suite:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

If documentation changes, also run:

```bash
python scripts/validate_docs.py
```

Add or update tests for every behavioral change. Keep documentation claims within the evidence proved by tests and hosted CI.

## Pull requests

Describe the problem, the smallest chosen solution, and the commands used to validate it. CI must pass before merge. Changes that add deployment, throughput, scale, concurrency, or production-readiness claims must include directly reproducible evidence for those claims.
