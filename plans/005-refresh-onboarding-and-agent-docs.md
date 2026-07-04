# Plan 005: Refresh onboarding and agent documentation

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected result before moving on. If a STOP condition occurs, stop and report instead of improvising.
>
> **Drift check (run first)**: `git diff --stat 77d9390..HEAD -- README.md Dockerfile requirements.txt .github/workflows/deploy.yml AGENTS.md .env.example`
> If any in-scope file changed since this plan was written, compare the excerpts below against the live code before proceeding.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: `plans/001-establish-verification-baseline.md`
- **Category**: docs, dx
- **Planned at**: commit `77d9390`, 2026-07-04

## Why this matters

The README is short and approachable, but it omits important operational details and contains at least one stale hint: it mentions Gemini fallback even though the code only supports Hugging Face API and local GGUF. This is an agentic AI repo, so a compact `AGENTS.md` will also reduce future agent mistakes around model downloads, tests, and deployment.

## Current state

- `README.md:15-18` describes Gemma, Kokoro, and pydub/FFmpeg.
- `README.md:34` says "Set your Hugging Face and/or Gemini keys", but code only reads `HF_TOKEN` and `LOCAL_MODEL_PATH` in `generator.py:190-214`.
- `README.md:39-43` documents starting the server, but not tests, env vars, audio cache, model cache, or common failure modes.
- There is no `.env.example`.
- There is no `AGENTS.md`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Docs sanity | `rg -n "Gemini|HF_TOKEN|LOCAL_MODEL_PATH|AUDIO_CACHE_DIR|KOKORO_MODEL_DIR|pytest|uvicorn" README.md AGENTS.md .env.example` | expected terms present; no stale Gemini setup unless code now supports it |
| Tests | `python3 -m pytest` | all tests pass |

## Scope

**In scope**
- `README.md`
- new `.env.example`
- new `AGENTS.md`

**Out of scope**
- Changing app behavior
- Adding a large architecture document
- Documenting unsupported Gemini functionality unless implementation is added in a separate plan

## Git workflow

- Branch: `codex/005-refresh-docs`
- Commit message style: `docs: refresh onboarding for agents and local dev`.

## Steps

### Step 1: Correct stale setup language

Update README setup to mention `HF_TOKEN` and `LOCAL_MODEL_PATH` only. Remove or clearly mark Gemini as unsupported unless code support has been added separately.

**Verify**: `rg -n "Gemini" README.md` returns no stale setup claim.

### Step 2: Document environment variables

Add a `.env.example` with commented placeholders for:
- `HF_TOKEN`
- `LOCAL_MODEL_PATH`
- `AUDIO_CACHE_DIR`
- `KOKORO_MODEL_DIR`

Update README with a small table explaining what each variable does and whether it is required.

**Verify**: `rg -n "HF_TOKEN|LOCAL_MODEL_PATH|AUDIO_CACHE_DIR|KOKORO_MODEL_DIR" README.md .env.example` finds each variable.

### Step 3: Add an AGENTS.md

Create `AGENTS.md` with concise instructions for future coding agents:
- project purpose and architecture
- test command from plan 001
- do not run real HF/Kokoro generation in ordinary tests
- mock network/model calls
- preserve static frontend and FastAPI route contract
- deployment notes for Hugging Face Spaces and Docker

**Verify**: `rg -n "pytest|mock|Hugging Face|FastAPI|Kokoro" AGENTS.md` finds the relevant guidance.

### Step 4: Add troubleshooting notes

Add brief README troubleshooting for missing `ffmpeg`, missing `HF_TOKEN`/`LOCAL_MODEL_PATH`, Kokoro model downloads, and audio cache cleanup.

**Verify**: `rg -n "ffmpeg|No generation backend|model_cache|podcast_audio" README.md` finds the notes.

## Test plan

- Documentation-only changes should not change runtime behavior.
- Run `python3 -m pytest` after docs changes once plan 001 exists.

## Done criteria

- [ ] README no longer claims a Gemini fallback that the code does not implement.
- [ ] README documents local setup, tests, env vars, and troubleshooting.
- [ ] `.env.example` exists and contains no real secrets.
- [ ] `AGENTS.md` exists with repo-specific instructions for future agents.
- [ ] `python3 -m pytest` exits 0.
- [ ] `plans/README.md` status row updated.

## STOP conditions

- The code has been changed to add Gemini support before this plan runs; update the docs plan instead of removing Gemini references.
- Plan 001 has not landed and no test command exists; document that limitation in the final note.

## Maintenance notes

Keep `AGENTS.md` short. It should tell future agents what to preserve and how to verify, not become a duplicate README.
