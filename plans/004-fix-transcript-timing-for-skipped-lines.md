# Plan 004: Fix transcript timing when blank dialogue lines are skipped

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected result before moving on. If a STOP condition occurs, stop and report instead of improvising.
>
> **Drift check (run first)**: `git diff --stat 77d9390..HEAD -- tts_engine.py frontend/script.js tests`
> If any in-scope file changed since this plan was written, compare the excerpts below against the live code before proceeding.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: MED
- **Depends on**: `plans/001-establish-verification-baseline.md`
- **Category**: bug
- **Planned at**: commit `77d9390`, 2026-07-04

## Why this matters

`generate_podcast_audio` skips blank text lines during synthesis but later indexes timing metadata by the compressed clip list. If any dialogue item is blank, the audio timing points at the wrong transcript text and the frontend click/highlight sync can jump to the wrong line. LLM output is external and imperfect, so this needs a defensive fix.

## Current state

- `tts_engine.py:137-145` skips empty text and appends only generated clip paths.
- `tts_engine.py:157-169` loops over `enumerate(clip_paths)` and reads `dialogue[i]`, assuming no earlier lines were skipped.
- `frontend/script.js:239-263` renders the original dialogue array and seeks with `timing[i]`.
- `frontend/script.js:358-376` highlights transcript lines by index into `currentTiming`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Tests | `python3 -m pytest` | all tests pass |
| Targeted tests | `python3 -m pytest tests/test_tts_engine.py` | timing tests pass |

## Scope

**In scope**
- `tts_engine.py`
- `frontend/script.js` only if needed to consume stable timing indexes
- `tests/test_tts_engine.py`

**Out of scope**
- Changing voices, MP3 export settings, or the public response schema beyond clarifying timing indexes
- Running real Kokoro synthesis in tests

## Git workflow

- Branch: `codex/004-fix-transcript-timing`
- Commit message style: `fix: keep transcript timing aligned`.

## Steps

### Step 1: Preserve original dialogue indexes

Change the synthesis loop to track generated clips alongside their original dialogue index and line data, for example a list of objects or tuples containing `clip_path`, `dialogue_index`, `speaker`, and `text`.

**Verify**: Python AST parse from plan 001 exits 0.

### Step 2: Build timing metadata from tracked line data

When stitching clips, use the stored original dialogue index, speaker, and text rather than `dialogue[i]`. Keep `start_s` and `end_s` behavior unchanged.

**Verify**: Python AST parse from plan 001 exits 0.

### Step 3: Add a no-real-audio regression test

Mock `_synthesize_line` to create small WAV files and avoid loading Kokoro. Pass dialogue with a blank first or middle item and assert timing metadata refers to the nonblank original line indexes and text. If frontend code keeps using array positions, update `frontend/script.js` to map timing by `index` instead of assuming `timing[i]`.

**Verify**: `python3 -m pytest tests/test_tts_engine.py` passes.

## Test plan

- Unit-test blank-line handling without loading models.
- Unit-test the normal no-blank case still returns timing in playback order.
- Run `python3 -m pytest`.

## Done criteria

- [ ] Blank dialogue lines do not shift timing text/speaker metadata.
- [ ] Frontend click-to-seek and active-line highlighting use the intended timing entry.
- [ ] No real model download or TTS inference happens in tests.
- [ ] `python3 -m pytest` exits 0.
- [ ] `plans/README.md` status row updated.

## STOP conditions

- Tests require ffmpeg or pydub behavior unavailable in the executor environment.
- Fixing this requires changing the API response in a way the frontend cannot consume compatibly.

## Maintenance notes

If the API later filters dialogue before returning it, revisit whether timing indexes should mean original script index or rendered transcript index. Document that choice in tests.
