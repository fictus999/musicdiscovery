"""Empty on purpose. Its only job is to exist at the repo root: pytest's
default (prepend) import mode adds a conftest.py's own directory to
sys.path when that directory has no __init__.py, which is what makes
`jobs.musicbrainz_ingest.*` (and any other repo-root-level package)
importable from test modules.

Without this, `python -m pytest` happens to work anyway (the `-m` flag
itself prepends the current directory to sys.path), which is exactly how
this gap stayed hidden through local development — every local run used
`python3 -m pytest`. Plain `pytest` (no `-m`), which is what CI's
`pytest tests/ -q` step runs, does not get that for free and failed with
`ModuleNotFoundError: No module named 'jobs'` until this file existed.
"""
