# Plan 002: Harden URL fetching against SSRF

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected result before moving on. If a STOP condition occurs, stop and report instead of improvising.
>
> **Drift check (run first)**: `git diff --stat 77d9390..HEAD -- main.py tests README.md requirements.txt requirements-dev.txt`
> If any in-scope file changed since this plan was written, compare the excerpts below against the live code before proceeding.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: `plans/001-establish-verification-baseline.md`
- **Category**: security
- **Planned at**: commit `77d9390`, 2026-07-04

## Why this matters

The public API fetches arbitrary user-supplied URLs from the server. Without host and address validation, a deployed Hugging Face Space can be used to request localhost, private-network, metadata, or internal service URLs. The fix should keep normal article URLs working while rejecting local/private destinations and unsafe redirects.

## Current state

- `main.py:76-90` calls `requests.get(url, headers=headers, timeout=15)` directly.
- `main.py:118-127` detects URLs with a regex that accepts only the initial URL shape; it does not validate resolved hosts or redirects.
- `main.py:153-155` calls `_scrape_url(req.source.strip())` for `input_type == "url"`.
- `README.md` documents accepting article URLs as a normal input mode.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Tests | `python3 -m pytest` | all tests pass |
| Targeted tests | `python3 -m pytest tests/test_main.py` | URL validation tests pass |

## Scope

**In scope**
- `main.py`
- `tests/test_main.py` or equivalent test file
- README note if behavior changes user-facing errors

**Out of scope**
- Changing the script generation model
- Replacing BeautifulSoup extraction
- Adding browser rendering or paid scraping services

## Git workflow

- Branch: `codex/002-harden-url-fetching`
- Commit message style: `security: harden article URL fetching`.

## Steps

### Step 1: Add URL validation helpers

In `main.py`, add helpers that parse URLs with `urllib.parse.urlparse`, require `http` or `https`, require a hostname, reject embedded credentials, resolve hostnames with `socket.getaddrinfo`, and reject loopback, private, link-local, multicast, reserved, unspecified, and localhost-style hosts using `ipaddress`.

Do not log secret-bearing full URLs with credentials. Prefer logging scheme + hostname.

**Verify**: `python3 -m pytest tests/test_main.py` passes if plan 001 exists; otherwise the Python AST parse command from plan 001 exits 0.

### Step 2: Apply validation before fetching and after redirects

Update `_scrape_url` so it validates before the request and prevents unsafe redirects. One acceptable shape is to use `allow_redirects=False`, inspect redirect `Location` headers up to a small limit, resolve relative redirects with `urllib.parse.urljoin`, validate each destination, then fetch the final response.

Keep the existing 15-second timeout or tighten it with a tuple timeout such as `(5, 15)`.

**Verify**: `python3 -m pytest tests/test_main.py` passes.

### Step 3: Add regression tests

Add tests that reject:
- `file://...`
- `http://localhost:8000`
- `http://127.0.0.1`
- `http://10.0.0.1`
- URLs with embedded credentials

Add one test that a normal public HTTP/HTTPS URL passes validation without making a real network request. Mock DNS resolution and `requests.get` rather than touching the network.

**Verify**: `python3 -m pytest tests/test_main.py` passes.

## Test plan

- Unit-test validation helpers with mocked DNS.
- Unit-test redirect handling by mocking `requests.get`.
- Run full `python3 -m pytest` after targeted tests pass.

## Done criteria

- [ ] Private, loopback, link-local, reserved, and non-HTTP(S) URLs are rejected before server-side fetch.
- [ ] Redirects to blocked destinations are rejected.
- [ ] Existing successful scrape behavior remains covered by tests with mocked responses.
- [ ] `python3 -m pytest` exits 0.
- [ ] `plans/README.md` status row updated.

## STOP conditions

- You cannot reliably mock DNS and HTTP without adding a large testing dependency.
- A required deployment target depends on fetching private URLs.
- The fix changes the request/response schema.

## Maintenance notes

Future URL ingestion features should reuse the same validation helper. Reviewers should check IPv6, DNS aliases, and redirect behavior carefully; these are the usual places SSRF fixes accidentally stay porous.
