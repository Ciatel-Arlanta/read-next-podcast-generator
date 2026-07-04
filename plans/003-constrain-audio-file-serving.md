# Plan 003: Constrain generated audio file serving

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected result before moving on. If a STOP condition occurs, stop and report instead of improvising.
>
> **Drift check (run first)**: `git diff --stat 77d9390..HEAD -- main.py tts_engine.py tests`
> If any in-scope file changed since this plan was written, compare the excerpts below against the live code before proceeding.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: `plans/001-establish-verification-baseline.md`
- **Category**: security
- **Planned at**: commit `77d9390`, 2026-07-04

## Why this matters

The audio endpoint joins request path parameters into a filesystem path and serves it if it exists. Even if the current router rejects ordinary slashes in `filename`, the code has no explicit allowlist or path containment check. A small validation layer makes the endpoint safe against route-decoding changes and accidental future expansion.

## Current state

- `main.py:194-204` serves `AUDIO_CACHE_DIR / session_id / filename` with `FileResponse`.
- `main.py:186` returns only `/api/audio/{session_id}/podcast.mp3`.
- `tts_engine.py:129-135` generates a 12-character hex session id when none is supplied.
- `tts_engine.py:175-176` exports the final file as `podcast.mp3`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Tests | `python3 -m pytest` | all tests pass |
| Targeted tests | `python3 -m pytest tests/test_main.py` | audio route tests pass |

## Scope

**In scope**
- `main.py`
- `tests/test_main.py` or equivalent API test file

**Out of scope**
- Changing audio generation output paths
- Adding authentication or expiring signed URLs
- Serving arbitrary generated artifacts

## Git workflow

- Branch: `codex/003-constrain-audio-serving`
- Commit message style: `security: constrain generated audio serving`.

## Steps

### Step 1: Validate path parameters explicitly

Update `serve_audio` so `session_id` must match `^[a-f0-9]{12}$` and `filename` must equal `podcast.mp3`. Return 404 for invalid values to avoid exposing filesystem rules.

**Verify**: `python3 -m pytest tests/test_main.py` passes.

### Step 2: Add a containment check

Resolve both `AUDIO_CACHE_DIR` and the candidate file path, and confirm the candidate is inside the expected session directory before returning `FileResponse`.

**Verify**: `python3 -m pytest tests/test_main.py` passes.

### Step 3: Add route tests

Add tests for:
- valid-looking missing audio returns 404
- invalid session id returns 404
- wrong filename returns 404
- traversal-looking filename does not serve a file

Use a temporary audio cache directory or monkeypatch `main.AUDIO_CACHE_DIR` so tests do not touch `/tmp/podcast_audio`.

**Verify**: `python3 -m pytest tests/test_main.py` passes.

## Test plan

- Cover invalid values and one successful temporary-file response if simple.
- Run the full suite with `python3 -m pytest`.

## Done criteria

- [ ] Only 12-char lowercase hex session ids are accepted.
- [ ] Only `podcast.mp3` is served by this endpoint.
- [ ] Resolved paths must remain inside `AUDIO_CACHE_DIR/session_id`.
- [ ] `python3 -m pytest` exits 0.
- [ ] `plans/README.md` status row updated.

## STOP conditions

- Product requirements need multiple downloadable filenames.
- The router behavior makes a planned test impossible without an integration server.

## Maintenance notes

If future work adds transcripts, waveforms, or alternate audio formats, add them as explicit allowlist entries rather than relaxing this endpoint into arbitrary file serving.
