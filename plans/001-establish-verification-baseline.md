# Plan 001: Establish a verification baseline

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected result before moving on. If a STOP condition occurs, stop and report instead of improvising.
>
> **Drift check (run first)**: `git diff --stat 77d9390..HEAD -- README.md requirements.txt main.py generator.py tts_engine.py frontend/index.html frontend/script.js frontend/style.css`
> If any in-scope file changed since this plan was written, compare the excerpts below against the live code before proceeding.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests, dx
- **Planned at**: commit `77d9390`, 2026-07-04

## Why this matters

The repo currently has no one-command verification path, which makes every security, generation, or frontend change harder to review safely. The Python files parse, but there are no tests for the API boundary, URL scraping, JSON parsing, audio timing, or static frontend contract. This plan adds a small, fast baseline so later plans have a reliable gate.

## Current state

- `requirements.txt` lists runtime packages only; no test dependencies are present.
- `README.md:39-43` documents only `uvicorn main:app --reload --port 7860`.
- There is no `tests/` directory, no `pytest` script, and no lint/typecheck config.
- `main.py:134-187` contains the primary POST endpoint.
- `generator.py:77-118` contains pure JSON extraction/parsing helpers that are good first unit-test targets.
- `tts_engine.py:114-186` contains timing logic that should be covered before refactors.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Parse Python | `python3 - <<'PY'\nimport ast, pathlib\nfor path in pathlib.Path('.').glob('*.py'):\n    ast.parse(path.read_text())\nprint('python syntax ok')\nPY` | prints `python syntax ok`, exit 0 |
| Install | `python3 -m pip install -r requirements.txt` | exit 0 |
| Tests | `python3 -m pytest` | all tests pass |

## Scope

**In scope**
- `requirements.txt`
- `README.md`
- new `tests/` files
- optionally `pytest.ini` or `pyproject.toml` if needed for pytest config

**Out of scope**
- Changing production behavior in `main.py`, `generator.py`, or `tts_engine.py`
- Adding heavyweight CI, formatting, or type-checking tools beyond a small pytest baseline

## Git workflow

- Branch: `codex/001-verification-baseline`
- Commit message style: use conventional commits, matching the existing history, e.g. `test: add baseline verification suite`.

## Steps

### Step 1: Add pytest as a development dependency

Add `pytest` and `httpx` to dependency management in the smallest style this repo supports. Because the repo currently has only `requirements.txt`, either append clearly marked test dependencies there or create a `requirements-dev.txt` and document it. Prefer `requirements-dev.txt` if you want runtime Docker installs to stay lean.

**Verify**: `python3 -m pip install -r requirements.txt` and, if created, `python3 -m pip install -r requirements-dev.txt` both exit 0.

### Step 2: Add pure helper tests

Create tests for `generator._extract_json` and `generator._parse_script` covering direct JSON, fenced JSON, leading/trailing prose with a JSON object, invalid JSON, empty dialogue, and trimming of dialogue text.

**Verify**: `python3 -m pytest tests/test_generator.py` passes.

### Step 3: Add API helper tests

Create tests for `main._detect_input_type` and a FastAPI health-check smoke test. Use FastAPI's `TestClient` or `httpx` as appropriate for the installed FastAPI version. Do not call real network, HF, or TTS backends.

**Verify**: `python3 -m pytest tests/test_main.py` passes.

### Step 4: Document the verification workflow

Update `README.md` with a short local development section that includes Python 3.10+, optional virtualenv creation, installing runtime and dev/test dependencies, running `python3 -m pytest`, and starting the server.

**Verify**: `rg -n "pytest|requirements-dev|uvicorn" README.md` shows the new commands.

## Test plan

- Add unit tests for pure helpers first.
- Add API smoke tests that avoid model and audio generation.
- The full verification command is `python3 -m pytest`.

## Done criteria

- [ ] `python3 -m pytest` exits 0.
- [ ] The README documents how to run tests.
- [ ] No production behavior changes are included.
- [ ] `git status --short` shows only the planned docs/test/dependency files.
- [ ] `plans/README.md` status row updated.

## STOP conditions

- Dependency installation fails because of platform-specific audio/model packages.
- Testing the app imports Kokoro or downloads models before any endpoint is called.
- You need to modify production code to make the baseline tests import.

## Maintenance notes

Later security and correctness plans should add regression tests to this suite. Keep the first baseline deliberately small and fast; model integration tests can be added later behind explicit markers.
