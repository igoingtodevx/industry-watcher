# Postmortem: industry-watcher silent Vercel deploy failure (2026-07-10)

## Summary
The `industry-watcher` weekly brief was silently not updating on Vercel for
25+ days. The pipeline (scrape + LLM + JSON write) ran successfully every
time, but the Vercel deploy step failed with HTTP 403 and the actual Vercel
error response was never logged.

## Timeline
- **2026-06-15**: Initial Vercel deploy works. Token + secrets fresh.
- **2026-06-15 04:36**: First failure (commit 31cb4aa): `log` logger undefined in
  run_pipeline.py. Fixed.
- **2026-07-06 10:04**: Last successful run. Cron triggered deploy to
  `state=READY`.
- **2026-07-06 10:04 → 2026-07-10 19:26**: 4 days of no scheduled runs. Pipeline
  may have been failing silently in between. **Unclear exactly when the
  token expired / scope changed.**
- **2026-07-10 18:34**: Commit `bd62c2c` — "fix: correct LLM JSON schema key
  + remove placeholder tokens in workflow". This commit:
    1. Fixed a real bug: `executivo_summary` → `executive_summary` typo
       in the SYSTEM_PROMPT (the LLM had been told to write to a non-existent
       field for 25 days).
    2. **Unintentionally removed the only diagnostic line**:
       `echo "::error::Failed to trigger Vercel deploy: $DEPLOY"` →
       `echo "::error::Failed to trigger Vercel deploy"`. The `: $DEPLOY`
       variable expansion looked like a placeholder string to the author.
    3. Changed cron schedule: `0 6 * * 1` (weekly Mon) → `0 6 * * *` (daily).
       Combined with the now-silent failure, this means 4 daily runs all
       failed silently.
- **2026-07-10 19:26**: First visible failure (`gh run view` showed
  `##[error]Failed to trigger Vercel deploy` but no cause).
- **2026-07-10 19:44**: Diagnostic fix pushed. Pipeline runs, deploy returns
  HTTP 403 with the actual error.

## Root Cause
**Vercel API token is scoped to the wrong Vercel team (or has been
de-authorized via SAML SSO rotation).**

Exact Vercel response:
```json
{
  "error": {
    "code": "forbidden",
    "message": "Not authorized: Trying to access resource under scope \"igoingtodevxs-projects\". You must re-authenticate to this scope or use a token with access to this scope.",
    "saml": true,
    "teamId": null,
    "scope": "igoingtodevxs-projects",
    "enforced": false
  }
}
```

The `VERCEL_REPO_ID=1261276095` (numeric GitHub repo ID) was **NOT** the
problem — Vercel was rejecting the request at the auth layer, before it
even validated the body.

## What This Postmortem Adds vs. the Skill's Existing Pitfall
The `expo-vercel-deployment` skill's `vercel-ci-silent-failures.md`
reference listed "`gitSource.repoId` is wrong format" as the likely cause.
**This is incorrect for SAML-protected teams.** When Vercel SAML SSO is
enforced, a stale token fails at the auth layer, never reaches the
`gitSource.repoId` validation, and the error message includes `"saml": true`.

Diagnostic tree (revised):
1. HTTP 401 → token invalid/expired → reissue in Vercel dashboard
2. HTTP 403 + `"saml": true` → token lacks scope on SAML-enforced team
   → re-issue token WITH the target team selected during creation
3. HTTP 403 + `"code": "repo_not_found"` or similar → `gitSource.repoId`
   format is wrong → reconnect Git integration
4. HTTP 400 → malformed body → check JSON syntax, required fields

## Fix Required (manual, on Vercel side)
1. Vercel dashboard → `igoingtodevxs-projects` team → Settings → Tokens →
   Create Token
2. Select the `igoingtodevxs-projects` team explicitly during creation
3. Copy new token
4. GitHub repo `igoingtodevx/industry-watcher` → Settings → Secrets and
   variables → Actions → `VERCEL_TOKEN` → Update value
5. (Optional) Trigger workflow again: `gh workflow run weekly-brief.yml`

## Preventive Measures (in code)
- [x] `echo "::error::Vercel response: $DEPLOY"` is now back in the workflow
- [x] HTTP code + body in error path
- [x] `gitSource.sha` added (defensive — Vercel accepts it as deployment hint)
- [ ] TODO: add post-deploy smoke test step (fetch live URL, verify
  freshness within 24h). Currently not added because the smoke test would
  itself fail during the token outage, blocking the workflow — not desired
  for now.

## Open Questions
- When did the Vercel token's scope change? Between 2026-07-06 10:04
  (last success) and 2026-07-10 19:26 (first visible failure) — possibly
  during a SAML re-auth or token rotation that wasn't synchronized with
  the GH Secret.
- Why was the cron schedule `0 6 * * 1` changed to `0 6 * * *` in the same
  commit that broke debugging? Unrelated but worth reverting if daily runs
  are not actually needed.
