# Design: Federated Leaderboard Submissions

**Status:** draft — not yet implemented.

## Goal

Let someone who self-hosts LLM Control Plane push their model leaderboard
results (benchmark scores + live traffic stats) to a central instance of the
same codebase, attributed to their GitHub account, so the central site can
show a public cross-user leaderboard — similar in spirit to open
leaderboard sites (LMSYS Arena, HF Open LLM Leaderboard), but sourced from
real self-hosted deployments instead of a single evaluator.

## Current state (why this needs new plumbing)

The existing leaderboard (`backend/app/api/v1/leaderboard.py`) is
**single-tenant**: every request resolves to exactly one `Project` via its
API key (`ProjectDep`, `backend/app/api/deps.py:88-92`), and all metrics are
scoped to `project.id`. There is no `User`/account concept anywhere in the
backend — auth identifies a *project* via a hashed API key
(`backend/app/models/tenancy.py`), not a person
(confirmed: zero matches for `User`/`oauth`/`github`/`jwt` in the backend).
`Settings.environment` (`backend/app/core/config.py:27`) only distinguishes
`dev`/`test`/`prod`, not "self-hosted instance" vs "central instance."

So this feature needs: real per-human accounts, a way for a self-hosted
instance to authenticate *as that human* when pushing data (not as its own
project), a place to store submissions from many different instances, and a
public, unauthenticated read view that aggregates across them.

## Design

### 1. Deployment mode flag

Add `deployment_mode: Literal["self-hosted", "central"] = "self-hosted"` to
`Settings`. One codebase, two postures:

- **self-hosted** (default, current behavior): single project, bootstrap
  token flow, no GitHub OAuth, no public leaderboard routes mounted. Nothing
  changes for existing users unless they opt in.
- **central**: mounts the GitHub OAuth + submission + public-leaderboard
  routes; the bootstrap-key flow and gateway/model-routing pieces aren't
  needed here (the central site never proxies model traffic itself, it just
  collects reports) — pairs with `docker-compose.cloud.yml`'s existing
  `local-only` profile trick to also drop `gateway`/`workers` on a
  central deployment.

### 2. New data model (Alembic migration `0003_...`)

- **`user`** — `id`, `github_id` (unique), `github_login`, `avatar_url`,
  `created_at`, `last_login_at`. Populated on first GitHub OAuth login.
- **`submission_token`** — same shape as the existing `APIKey`
  (`key_prefix`, `key_hash` via the existing `generate_api_key`/argon2id
  helpers in `repositories/tenancy.py`), but FK'd to `user_id` instead of
  `project_id`, scope fixed to `submit`. Issued from an account page,
  shown once, like a GitHub personal access token.
- **`leaderboard_submission`** — `id`, `user_id` FK, `source_label` (free
  text the user sets, e.g. "anuj-homelab"), `submitted_at`.
- **`leaderboard_submission_entry`** — `submission_id` FK, and the same
  fields as the existing `LeaderboardEntry` schema (`model_id`,
  `avg_cost_usd`, `avg_latency_ms`, `reliability_pct`, `request_count`,
  `avg_judge_score`, `hallucination_rate`). One row per model per push.

Reuses the existing `LeaderboardEntry` shape end-to-end — a self-hosted
instance's own `GET /api/v1/leaderboard` response *is* the submission
payload, just POSTed somewhere else.

### 3. Auth flows

- **Browser login (central instance only):** `GET /api/v1/auth/github/login`
  → GitHub OAuth authorize redirect → `GET /api/v1/auth/github/callback`
  exchanges the code, upserts `User`, sets a session cookie. Used only for
  the account page (viewing/rotating submission tokens, seeing your own
  submission history) — not for the submission API call itself.
- **Machine push (self-hosted → central):** the self-hosted instance
  authenticates with a **submission token**, not GitHub OAuth — same
  bearer-token pattern as today's API keys
  (`Authorization: Bearer <submission-token>`), resolved by a new
  `SubmissionTokenRepository.resolve()` mirroring
  `APIKeyRepository.resolve()` (`repositories/tenancy.py:44-59`).

### 4. New endpoints (central instance)

- `POST /api/v1/public-leaderboard/submissions` — auth'd via submission
  token. Body: `{source_label, entries: LeaderboardEntry[]}`. Validates,
  stores as a new `leaderboard_submission` + child rows.
- `GET /api/v1/public-leaderboard` — public, no auth. Aggregates the
  **latest submission per (user, model_id)**, applies a staleness cutoff
  (exclude submissions older than N days — configurable), and reuses the
  existing `_sort()` null-safe ranking logic from `leaderboard.py`. Each row
  carries `github_login`/`avatar_url`/`source_label`/`submitted_at` for
  attribution.

### 5. Self-hosted push mechanism

Opt-in only (this ships real usage/cost data off the user's machine — must
never be silent default behavior):

- New settings: `LEADERBOARD_SUBMIT_ENABLED=false` (default),
  `CENTRAL_LEADERBOARD_URL`, `CENTRAL_SUBMISSION_TOKEN`.
- A small push step (Celery beat task if `scheduler` is running locally, or
  a one-off `scripts/push_leaderboard.py` for a manual/cron push) calls the
  instance's own `GET /api/v1/leaderboard` and POSTs the result to
  `CENTRAL_LEADERBOARD_URL`.

### 6. Trust & abuse — explicitly a v1 limitation

Submitted numbers are self-reported; nothing here cryptographically proves
they came from real traffic. Mitigations for v1: per-token rate limiting
(reuse `APIKey.rate_limit_rpm` concept), a minimum `request_count` threshold
before an entry is eligible to rank, and a staleness cutoff. A "verified"
badge for spot-checked submissions is a reasonable v2, not in scope now.

## Rollout phases

1. Migration `0003`: `user`, `submission_token`, `leaderboard_submission`,
   `leaderboard_submission_entry` tables.
2. GitHub OAuth login + account page (issue/revoke submission tokens).
3. `POST /api/v1/public-leaderboard/submissions` + push script/task on the
   self-hosted side, off by default.
4. `GET /api/v1/public-leaderboard` (public) + a frontend page for it.
5. Polish: staleness filtering, rate limits, admin moderation/removal of a
   bad submission.

## Open questions before implementation starts

- Should the push be scheduled (Celery beat, e.g. daily) or manual-only
  (a button/CLI command) for v1? Scheduled is more "leaderboard-like" but is
  a bigger privacy commitment to ask self-hosters to opt into first.
- Staleness window for the public leaderboard (7 days? 30?).
- Does an admin need a way to remove/ban a submission or user (spam,
  clearly fabricated numbers) in v1, or is that acceptable to defer?
