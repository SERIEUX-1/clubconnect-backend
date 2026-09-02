# CLUBCONNECT — Build Roadmap
### From this scaffold to a production, award-worthy institutional platform

This is the execution plan I'd hand a team if I were the technical lead on
this project. It follows the PRS's own 10-phase roadmap (Section 19) but
turns each phase into concrete engineering tasks, sequenced so nothing gets
built on a foundation that isn't there yet. Where the PRS gives you a
principle ("evidence before claims", "human-governed AI"), I've told you
*how* to actually enforce it in code — most of that enforcement is already
sitting in the scaffold I just built you.

---

## Phase 0 — Discovery (1–2 weeks, before writing more code)

You cannot skip this even though it's tempting to jump straight to screens.

1. **Lock the scoring framework with the Committee.** The 10 criteria and
   weights in PRS §9 are a *proposal* — get the actual Committee Head to
   sign off on final weights before you seed `EvaluationCriterion` rows.
   Changing weights later is just a data edit (that's the whole point of
   the versioned-criteria design), but changing the criteria *keys* after
   clubs have scores against them is a migration headache.
2. **Decide the aggregation rule** (weighted by month vs. simple average)
   — this is a policy decision, not a technical one, and it's a single
   field (`EvaluationCycle.aggregation_method`) once decided.
3. **Get real academic-year dates**: recognition deadlines, CCEA Cycle 1/2
   month boundaries, report due-dates. Feed these into `EvaluationCycle`
   and `MonthlyReport.deadline` as data — never as code.
4. **Privacy sign-off**: confirm exactly what a Committee Member sees vs.
   Committee Head (the PRS says "Assigned/authorized" for members — get a
   concrete definition: assigned by category? by campus? manually?).
5. **Pick your object storage provider** (S3, DigitalOcean Spaces, Cloudinary,
   institutional storage) — this determines `DEFAULT_FILE_STORAGE` and
   whether you need `django-storages`.

**Deliverable:** a signed-off requirements doc + a seeded `EvaluationCycle`
+ `EvaluationCriterion` fixture (I'd write this as a Django data migration
or `manage.py seed_evaluation_framework` command — never hand-edited in
the admin in production, so it's reproducible across environments).

---

## Phase 1 — Foundation (what I just built you)

**Code delivered in `clubconnect_backend_foundation.zip`:**

- Project skeleton, environment-driven settings, PostgreSQL config
- Custom `User` model with the 6 PRS roles
- JWT auth (`/api/auth/token/`) + registration + profile endpoints
- Central RBAC (`apps/core/permissions.py`) used by every viewset
- Audit logging wired via Django signals (append-only, automatic)
- Every model in PRS §13's data model, with real constraints:
  unique attendance, unique membership, versioned criteria, collaboration
  self-reference check
- Scoring engine as an isolated, testable service
- AI provider abstraction with the human-governance boundary hard-coded
  into which endpoints can touch `Score.final_value`
- Full REST API surface (DRF ViewSets + routers) for every module

**What's left in this phase:**

1. **Design system first, screens second.** Before any React component,
   define: color palette, type scale, spacing scale, component library
   choice (I'd recommend **Tailwind CSS + shadcn/ui** for a modern,
   distinctive but maintainable system — not a generic admin template).
   This is what makes the product feel "attractive" rather than "CRUD
   dashboard" per PRS §15 — and it needs to exist before Phase 2 UI work
   starts, or every screen looks inconsistent.
2. **Stand up CI**: GitHub Actions running `pytest`, `ruff`/`black`,
   `manage.py check --deploy` on every PR. Cheap now, painful to retrofit.
3. **Write tests for the scoring engine** (`apps/evaluation/services.py`)
   before you build anything on top of it — it's the highest-stakes logic
   in the whole system and it's already isolated for exactly this reason.
4. **Institutional SSO decision**: if the institution has SSO (Google
   Workspace, Microsoft Entra, Shibboleth), decide now whether Phase 1 or
   a later phase integrates it — swapping auth backends after 500 users
   exist is far more expensive than deciding early.

---

## Phase 2 — Club Core

1. Build the **Discover Clubs** frontend screen against `GET /api/clubs/`
   — this is your first real UI and it sets the visual tone for
   everything else. Use it to prove out the design system: cards, search,
   category filters, empty states.
2. Club registration/recognition workflow: a form that creates a `Club`
   in `PENDING` status, a Committee Head approval screen that flips it to
   `RECOGNIZED`. This is a good first "workflow with state" to get right
   before you build the much higher-stakes evaluation workflow later.
3. Digital Passport screen — read `ClubManageSerializer` for leaders,
   `ClubPublicSerializer` for everyone else. This is where you prove the
   role-aware-serializer pattern works end-to-end in the UI, not just the API.
4. Membership request/approval flow (`ClubMembershipViewSet`).

**Acceptance test to run yourself:** log in as two different students, try
to view another club's `handover_notes_private` — confirm it's simply
absent from the API response, not just hidden in the UI.

---

## Phase 3 — Operations (Activities, Events, Attendance, Collaboration)

1. Activity CRUD screens with the Draft → Submitted → Under Review →
   Verified state machine visible as a clear status badge.
2. Event creation + **QR attendance**: generate the QR from
   `GET /api/events/{id}/reveal_qr/` (leader-only), render it with a
   library like `qrcode.react` on the frontend, and build the student
   scan flow calling `POST /api/events/{id}/check-in/`. Test the
   duplicate-scan rejection and the time-window rejection explicitly —
   these are exactly the edge cases the PRS calls out.
3. Collaboration request/confirm/reject UI — make the "pending" state
   visually obvious on both clubs' dashboards; this is a feature that
   fails silently if the UI doesn't nudge the partner club to respond.

---

## Phase 4 — Evidence

1. Evidence upload with drag-and-drop, file-type/size validation
   **client-side for UX and server-side for security** (the server-side
   check is the one that matters — never trust the client).
2. Evidence review queue for Committee Members — this is a good screen to
   make genuinely pleasant to use, since reviewers will spend real hours
   here. Bulk actions, keyboard shortcuts, side-by-side evidence + activity
   context.
3. Wire evidence into the Club Portfolio's storytelling structure (PRS
   §6: Problem → Objective → What we did → Who participated → Who
   benefited → Evidence → Results → Lessons → Next steps) — this is a
   good differentiator: most club-management tools show a flat file list,
   not a narrative.

---

## Phase 5 — Evaluation

1. Monthly report submission flow with deadline countdown and completeness
   validation (flag missing required fields before submission, not after).
2. Build the **Committee Command Center** — this is the screen that will
   make or break how "outstanding" this platform feels to its actual power
   users. Show: all clubs, health status, pending reviews, evaluation
   progress, at a glance. This is worth spending real design time on.
3. Wire `apps/evaluation/services.py` into a dashboard showing live
   criterion breakdowns (`GET /api/scores/{id}/month_breakdown/`) —
   visualize the weighted contributions as a stacked bar so a reviewer can
   see *why* a score landed where it did.
4. **Club Health** (PRS §17): build this as a scheduled job (Celery +
   Celery Beat, or a simple cron `manage.py` command if you want to defer
   the Celery infrastructure decision) that computes indicators nightly
   and writes a `ClubHealthSnapshot` model (not yet in the scaffold — add
   it as `apps/clubs/health_models.py` following the same `BaseModel`
   pattern). Make indicators configurable via `SystemSetting`, per PRS.

---

## Phase 6 — AI

1. Set `AI_API_KEY` and wire `GenerateRecommendationView` into the
   Committee's review screen: a "Get AI recommendation" button next to
   each unscored criterion.
2. **Upgrade the AI response parsing.** The scaffold's
   `AnthropicProvider._parse_response` is a stub — replace it with a
   structured-output prompt (ask the model to return JSON matching a
   schema: `{recommended_value, explanation, flags}`) and parse that
   directly rather than regex-scraping free text. This is meaningfully
   more reliable and worth doing before this ships to real reviewers.
3. Build the **AI Evaluation Review** screen (PRS §15): evidence on one
   side, AI recommendation + explanation + flags in the middle, a score
   input + required "reason" field, and an Approve button that calls
   `POST /api/scores/{id}/approve/`. Make the "reason is required" a
   frontend nudge too, not just a backend 400 — good UX doesn't make
   people discover validation by failing.
4. **AI Club Coach**: a simple screen per club showing 2–3 sentences of
   generated guidance, refreshed monthly, backed by
   `AIProvider.generate_coach_feedback()`. Cache the output — no need to
   regenerate on every page load.
5. Write the "AI evaluation tests" the PRS asks for explicitly (§20):
   feed the provider known-bad inputs (empty evidence, contradictory
   evidence, duplicate submissions across two clubs) and assert it flags
   rather than confidently invents a high score.

---

## Phase 7 — CCEA

1. `Award`/`HallOfExcellenceEntry` CRUD for the Committee Head.
2. **CCEA Reveal Mode** — this is your chance to build something genuinely
   memorable. Full-screen, projector-optimized, dramatic reveal animation
   per category (I'd build this as a dedicated React route with Framer
   Motion transitions — confetti, category build-up, then the winner).
   Gate it hard: `is_revealed=False` awards must be completely invisible
   to any non-Committee-Head query, not just hidden by frontend routing.
3. Exportable award report (PDF) — methodology + cycle + criteria + final
   scores + winners. This is a good use case for `WeasyPrint` or a
   headless-Chrome PDF render from an HTML template you already have from
   the reveal-mode design.

---

## Phase 8 — Hardening

Run every item in PRS §20 literally as a checklist:

- [ ] Unit tests: scoring calculations, permissions, validation
- [ ] Integration tests: uploads, notifications, AI integration, API flows
- [ ] **Permission tests per role** — for every sensitive endpoint, write a
      test that asserts each *unauthorized* role gets a 403/empty
      queryset, not just that the authorized role works
- [ ] Security: `manage.py check --deploy` clean, dependency audit
      (`pip-audit`), file upload fuzzing (wrong extensions, oversized
      files, path traversal in filenames)
- [ ] Usability tests with real club leaders on actual phones
- [ ] Accessibility: keyboard nav, contrast ratios, screen-reader labels
- [ ] Load test the dashboard queries and the QR check-in endpoint
      specifically (it'll get a burst of traffic at every event)
- [ ] Backup/restore drill — actually restore a backup into a fresh
      environment and verify data integrity, don't just assume the backup
      job succeeding means the backup is good
- [ ] Set every Django deploy-check warning to green: real
      `SECRET_KEY`, `SESSION_COOKIE_SECURE=True`, `SECURE_SSL_REDIRECT=True`,
      `DEBUG=False`

---

## Phase 9 — Launch & Handover

1. Write the two user guides the PRS requires (§24): Administrator/Committee
   Head, and Club Leader. Screenshot-driven, not text walls.
2. Run a pilot with 3–5 real clubs for one full monthly cycle before
   rolling out institution-wide — you will find UX friction points no
   amount of internal testing surfaces.
3. Technical handover doc: architecture diagram, the "why" behind the key
   decisions (most of which are already commented in the scaffold's
   docstrings — pull them into `docs/architecture.md`), and the extension
   points (AI provider swap, notification provider swap, new criteria,
   new award categories) spelled out with a worked example each.

---

## Making it genuinely stand out (not just "complete")

A few things that separate a merely-functional version of this from one
that feels outstanding, based on what the PRS is implicitly asking for:

- **The portfolio storytelling structure is your biggest differentiator.**
  Almost every "club management" tool in this space is a flat CRUD app.
  Leaning hard into portfolio-as-narrative (with real typography and
  pacing, not just a form dump) is what will make club leaders *want* to
  use this rather than tolerate it.
- **Make the Committee Command Center feel like a mission control, not a
  spreadsheet.** This is the screen your most powerful stakeholder (the
  Committee Head) lives in daily — invest disproportionately here.
- **CCEA Reveal Mode is a moment, not a feature.** Treat it like you're
  building a live-event experience, not another CRUD screen.
- **Respect the "development before punishment" principle in the UI, not
  just the copy.** Club Health "At Risk" status should visually read as
  "here's how we can help," not as a red warning triangle that shames a
  struggling club leader.
- **Explain AI, don't just show a number.** Every AI-touched score should
  visibly show its reasoning and flags right next to it — this is both
  the PRS's governance requirement and genuinely better UX; a bare number
  from an AI is not trustworthy, an explained one is.

---

## Tech stack summary (confirmed working in the scaffold)

| Layer | Choice |
|---|---|
| Backend | Django 5 + Django REST Framework |
| Auth | JWT (`simplejwt`) + Django's built-in hashing |
| DB | PostgreSQL |
| AI | Anthropic API via a swappable provider interface |
| Media | Pluggable storage (local for dev, S3-compatible for prod) |
| Frontend (recommended) | React + Tailwind + shadcn/ui + Recharts (for score dashboards) |
| Background jobs | Celery + Celery Beat (Club Health, notification digests) |
| Deployment | Docker containers, staging + production environments |
| CI | GitHub Actions: tests, lint, deploy-check |

Everything in this plan builds directly on the codebase I've handed you —
there's no rewrite step hiding anywhere in this roadmap.
