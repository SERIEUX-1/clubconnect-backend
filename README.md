# CLUBCONNECT — Backend Foundation

Digital Clubs & Societies Management, Performance & Impact Platform.
This is the **Phase 1 (Foundation) + early Phase 2/3/5/6** backend scaffold
generated from the Developer Product Requirements Specification (Aug 2026).

It is a real, verified Django + DRF project: every model, constraint, and
migration in this repo has been run against a live database (`manage.py
migrate` succeeds with zero errors). It is not a mockup.

## What's implemented

| Module (PRS §5) | Status |
|---|---|
| Authentication & Identity | ✅ custom `User` model, 6 roles, JWT auth, registration API |
| Club Directory / Digital Passport / Portfolio | ✅ models + role-aware serializers + `/portfolio/` endpoint |
| Activities | ✅ full CRUD, status workflow |
| Events & Attendance (QR) | ✅ QR token generation, duplicate-proof check-in, time windows |
| Evidence Vault | ✅ upload + immutable review history |
| Collaborations | ✅ mutual-confirmation workflow enforced server-side |
| Projects & Impact | ✅ model + CRUD |
| Monthly Reporting | ✅ model + CRUD, deadline-aware |
| Performance & Scoring | ✅ versioned criteria, scoring engine service, weight validation |
| AI Evaluation Assistant | ✅ provider-abstracted, human-governance enforced |
| CCEA / Awards / Hall of Excellence | ✅ configurable award categories, reveal workflow |
| Audit & Governance | ✅ signal-based, append-only audit log |
| Notifications, Resources | ✅ models + CRUD (delivery providers are a Phase 6+ extension point) |

## What's intentionally NOT built yet (see the Roadmap doc)

- Frontend (React/Next.js) — Phase 1 also includes standing up the design
  system before any screen is built.
- Club Health scoring job (Phase 5/6) — indicators are configurable per the
  PRS; the aggregation job should be a Celery periodic task.
- CCEA Reveal Mode projector UI (Phase 7).
- SSO integration, multi-campus, PWA offline queue (post-MVP, PRS §18).

## Local setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in DJANGO_SECRET_KEY, DATABASE_URL, AI_API_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Requires PostgreSQL running locally (`DATABASE_URL` in `.env`), or swap in
`sqlite:///db.sqlite3` for quick local exploration only — never for staging
or production.

## Key architectural decisions (why the code is shaped this way)

1. **Scoring engine is a plain-Python service** (`apps/evaluation/services.py`),
   not view logic. It's unit-testable in isolation and callable from the API,
   a management command, or a Celery task without duplication.
2. **AI never writes a final score.** `apps/ai_assistant` can only set
   `Score.ai_recommended_value`. Only `ScoreViewSet.approve()` — an
   authenticated Committee action requiring a written reason — can set
   `Score.final_value`, and it always goes through
   `apply_human_adjustment()`, which writes an immutable `ScoreAdjustment`
   row first. This is the codified version of PRS §11's human-governance
   rule, not just a policy in a document.
3. **RBAC is enforced in `apps/core/permissions.py` and in every
   `get_queryset()`**, never only in the frontend. A Club Leader's queryset
   is filtered to their own club at the database query level.
4. **AI provider abstraction** (`apps/ai_assistant/providers.py`) — swap
   `AI_PROVIDER` in `.env` without touching any calling code.
5. **UUID primary keys + soft-delete** on every club-facing entity, so
   history survives leadership handovers, exports, and future
   multi-campus merges.
6. **Weights, cycles, and award categories are database rows**, not Python
   constants — a future Committee Head can reconfigure the entire
   evaluation framework without a code deployment.

## Next code you'll want to write (in order)

1. `apps/*/tests/` — unit tests for `evaluation/services.py` first (it's
   the highest-stakes logic in the system).
2. `apps/notifications/dispatch.py` — pluggable delivery (email/push),
   mirroring the `ai_assistant/providers.py` abstraction pattern.
3. `apps/clubs/health.py` — Club Health scoring, called by a scheduled task.
4. Frontend: see the Roadmap document, Phase 1.
