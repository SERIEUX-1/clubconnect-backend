"""
ClubConnect Copilot — a product expert, not a generative model.

Answers are resolved from:
1. The signed-in role's capabilities and hard limits
2. The licensed institution (ALCHE and others)
3. Live monthly evaluation data when the question is about performance

No LLM is called. If the copilot does not know something, it says so.
"""
from __future__ import annotations

import re

from django.utils import timezone

from apps.accounts.models import User
from apps.clubs.models import Club
from apps.evaluation.monthly import evaluate_club_month, evaluate_institution_month
from apps.ai_assistant.providers import ChatGuideRequest, get_provider
from apps.ai_assistant.reasoner import classify as reason_classify
from apps.ai_assistant.reasoner import local_phrase


ROLE_GUIDES = {
    "guest": {
        "can": [
            "Browse recognised clubs at a licensed institution from Discover Clubs (`/`).",
            "Open a club digital passport and read verified activities and impact.",
        ],
        "cannot": [
            "Join a club, check in, or submit reports until you sign in with a school email.",
            "See confidential rankings, pending evidence, or other students' attendance.",
        ],
        "start": "/",
    },
    "student": {
        "can": [
            "Sign in with your student school email (ALCHE: @alustudent.com).",
            "Browse every recognised club at your institution.",
            "Open any club page and watch published activities, project films, and photos.",
            "Request to join a club from its passport page.",
            "Request registration of a new club (charter stays pending until committee/leadership recognises it).",
            "QR check-in at events from the Student Dashboard.",
            "View your own attendance history and memberships.",
            "See public CCEA / awards teasers after they are revealed.",
        ],
        "cannot": [
            "Submit monthly reports, schedule events, or upload evidence (club leaders only).",
            "Approve members, verify evidence, or change scores.",
            "Open Command Center or CCEA Reveal — those stay with the Committee Head until publication.",
            "See another club's confidential scores or another student's attendance.",
            "Join using a personal Gmail/Yahoo address — only licensed school domains are accepted.",
        ],
        "start": "/student-dashboard",
    },
    "club_leader": {
        "can": [
            "Submit the monthly report for your own club.",
            "Schedule events and generate QR check-in tokens.",
            "Upload evidence for committee verification.",
            "Publish videos, photos, and project films so everyone signed in at this campus can watch them on your club page.",
            "Propose collaborations; points count only after the partner club confirms.",
            "Approve or reject students who requested to join your club.",
            "See the Copilot's monthly lackings for your club.",
            "Open your club's campus page to check the published videos and projects everyone can watch.",
        ],
        "cannot": [
            "Edit another club's reports, evidence, or scores.",
            "Finalise CCEA scores or reveal awards.",
            "Grant institutional access to another university.",
            "See Campus Clubs Excellence Awards marks or rankings before the Committee Head publishes them.",
        ],
        "start": "/leader-dashboard",
    },
    "committee_head": {
        "can": [
            "Review every club's evidence and finalise scores (there is no separate committee-member role).",
            "Configure CCEA criteria weights (must total 100%).",
            "Open Command Center after time away and read the catch-up summary (waiting approvals first, then what already moved).",
            "Run Copilot Health Scan and the Committee Head briefing (most urgent → least).",
            "Host CCEA Reveal Mode.",
        ],
        "cannot": [
            "Invent scores without a reasoned human decision — Copilot/rules never write final_value.",
            "See data from another licensed institution.",
        ],
        "start": "/command-center",
    },
    "staff": {
        "can": [
            "Sign in with a staff or lecturer email for this institution (ALCHE: @alueducation.com).",
            "Read campus participation analytics and watch published club films, photos, and projects.",
            "Open any recognised club page and watch the same published films, photos, and projects students see.",
            "Broadcast institutional notices.",
            "Open the Hall of Excellence after the Committee Head publishes the ceremony.",
        ],
        "cannot": [
            "See Campus Clubs Excellence Awards marks, rankings, or scoring before the Committee Head publishes the ceremony.",
            "Impersonate a student to check in for them.",
            "Silently change a score without an audit reason — only the Committee Head finalises CCEA scores.",
            "Onboard a different university (that is a system administrator action).",
        ],
        "start": "/staff-dashboard",
    },
    "student_life": {
        "can": [
            "Open the Student Life desk and work three piles: waiting on you, going quiet, and already fine.",
            "Recognise or return a club charter, and pause or restore a club with a written reason.",
            "Open or close the membership window for the campus.",
            "Read every club's members, events, reports, and evidence on this campus.",
            "Send a notice to leaders or the campus, and download the campus brief.",
        ],
        "cannot": [
            "Type Campus Clubs Excellence Awards scores. That stays with the Committee Head.",
            "Rewrite a club's report, evidence, or ordinary on-campus event.",
            "Check a student into an event.",
            "Manage sign-in domains or other people's accounts.",
        ],
        "start": "/student-life",
    },
    "system_admin": {
        "can": [
            "Run this licensed campus the way a Google Workspace Super Admin or Canvas Account Admin runs one school.",
            "Manage the campus directory: add people, change roles, suspend accounts.",
            "Set which student and staff email domains may sign in.",
            "Turn the campus awards programme on or off, and name it.",
            "Read the campus audit trail and Help Center tickets for this institution only.",
            "Watch published club films like everyone else; open the Hall of Excellence after publication.",
        ],
        "cannot": [
            "See or publish Campus Clubs Excellence Awards marks — that stays with the Committee Head.",
            "Licence another university. That is ClubConnect's platform operator, not this campus's IT admin.",
            "Bypass evidence verification to award CCEA points.",
            "Delete institutional memory — club records are archived, not erased.",
            "See another licensed campus's people or settings.",
        ],
        "start": "/admin-dashboard",
    },
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9@./]+", " ", (text or "").lower()).strip()


# Longest matching phrase wins. Copilot never invents a topic.
_TOPIC_PLAYBOOKS = (
    (
        "help_ticket",
        "Help Center ticket",
        (
            "submit a ticket",
            "submit ticket",
            "file a ticket",
            "open a ticket",
            "create a ticket",
            "send a ticket",
            "raise a ticket",
            "support ticket",
            "help ticket",
            "help center",
            "help centre",
            "contact support",
            "report a bug",
            "something is broken",
            "tickets",
            "ticket",
        ),
    ),
    (
        "identity",
        "What Copilot is",
        (
            "are you ai",
            "are you an ai",
            "chatgpt",
            "openai",
            "large language",
            "generative",
            "who are you",
            "what are you",
            "are you a bot",
            "is this ai",
            "artificial intelligence",
        ),
    ),
    (
        "briefing",
        "Committee catch-up briefing",
        (
            "what needs my attention",
            "what do i need to do",
            "while i was away",
            "waiting on me",
            "waiting for me",
            "catch me up",
            "catch-up",
            "catch up",
            "been away",
            "whats happened",
            "what's happened",
            "what happened",
            "briefing",
            "priorities",
            "priority",
            "urgent",
            "overview",
            "summary",
            "inbox",
        ),
    ),
    (
        "evaluation",
        "Monthly club evaluation",
        (
            "monthly eval",
            "evaluate club",
            "evaluation this month",
            "how do monthly evaluations work",
            "monthly evaluations",
            "why is my club",
            "health this month",
            "what are we missing",
            "health scan",
            "copilot scan",
            "how are clubs doing",
            "club health",
            "lackings",
            "lacking",
            "diagnostic",
        ),
    ),
    (
        "role",
        "Your role on this campus",
        (
            "what can i not",
            "what am i allowed",
            "what can i do",
            "permissions",
            "limitation",
            "my role",
        ),
    ),
    (
        "join",
        "Joining a club",
        (
            "request to join",
            "how to join",
            "join a club",
            "join club",
            "membership",
        ),
    ),
    (
        "register_club",
        "Registering a new club",
        (
            "register a club",
            "create a club",
            "start a club",
            "new club",
            "charter",
        ),
    ),
    (
        "report",
        "Monthly club report",
        (
            "submit report",
            "monthly report",
            "file a report",
            "activity report",
        ),
    ),
    (
        "checkin",
        "QR event check-in",
        (
            "check in",
            "check-in",
            "attendance",
            "scan",
            "qr",
        ),
    ),
    (
        "publish",
        "Publishing club films",
        (
            "club page video",
            "upload video",
            "campus to watch",
            "publish",
        ),
    ),
    (
        "hall",
        "Hall of Excellence",
        (
            "hall of excellence",
            "ccea history",
            "excellence awards",
            "campus awards history",
        ),
    ),
    (
        "evidence",
        "Evidence upload and verification",
        (
            "verify evidence",
            "upload proof",
            "evidence",
        ),
    ),
    (
        "collab",
        "Club collaborations",
        (
            "collab",
            "partner",
            "joint",
        ),
    ),
    (
        "awards",
        "Campus Clubs Excellence Awards",
        (
            "hall of excellence",
            "ccea",
            "award",
            "ceremony",
            "reveal",
        ),
    ),
    (
        "licence",
        "Campus licence",
        (
            "another university",
            "new institution",
            "who can use",
            "school email",
            "licence",
            "license",
            "institution",
            "university",
            "alche",
        ),
    ),
    (
        "notice",
        "Campus notices",
        (
            "broadcast",
            "lecturer",
            "notice",
            "staff",
            "dean",
        ),
    ),
    (
        "signin",
        "Signing in",
        (
            "cannot login",
            "can't log in",
            "cannot sign in",
            "password",
            "sign in",
            "log in",
            "login",
        ),
    ),
)


_GENERIC_CUES = {
    "institution",
    "university",
    "alche",
    "staff",
    "dean",
    "lecturer",
    "inbox",
    "summary",
    "overview",
    "scan",
    "partner",
    "joint",
    "notice",
}


def _classify(msg_l: str, previous_topic=None):
    return reason_classify(msg_l, _TOPIC_PLAYBOOKS, _GENERIC_CUES, previous_topic=previous_topic)


def _phrase_with_model(question: str, payload: dict) -> dict:
    payload.setdefault("uses_model", False)
    analysis = payload.get("analysis") or []
    if any("No playbook matched" in line for line in analysis):
        return payload
    provider = get_provider()
    if not getattr(provider, "uses_language_model", False):
        return payload
    label = "ClubConnect playbook"
    for line in analysis:
        if "Matched playbook:" in line:
            label = line.split("Matched playbook:", 1)[1].split("(cue:", 1)[0].strip(" .")
            break
        if "mapped the question to" in line:
            label = line.split("mapped the question to", 1)[1].strip(" .")
            break
    phrased = provider.guide_chat(
        ChatGuideRequest(
            question=question,
            role=payload.get("role") or "guest",
            institution_name=payload.get("institution") or "your institution",
            playbook_label=label,
            playbook_reply=payload.get("reply") or "",
            playbook_steps=payload.get("steps") or [],
            analysis=analysis,
            action_labels=[btn.get("label") for btn in (payload.get("action_buttons") or []) if btn.get("label")],
        )
    )
    if not phrased:
        analysis.append("Language model did not return a grounded phrase. Showing the playbook answer.")
        payload["analysis"] = analysis
        return payload
    payload["reply"] = phrased.reply
    if phrased.steps:
        payload["steps"] = phrased.steps
    if phrased.suggestions:
        payload["suggestions"] = phrased.suggestions
    payload["uses_model"] = True
    payload["engine"] = f"clubconnect-copilot-model:{phrased.model_name}"
    payload["analysis"] = analysis + [
        f"Phrased by {phrased.model_name} from the playbook only. Buttons and screens were not invented."
    ]
    return payload


def answer(message: str, role: str, user=None, context=None) -> dict:
    payload = _playbook_answer(message, role, user=user, context=context)
    payload = local_phrase(message or "", payload)
    provider = get_provider()
    if not getattr(provider, "uses_language_model", False):
        return payload
    try:
        return _phrase_with_model(message or "", payload)
    except Exception:
        payload["uses_model"] = False
        return payload


def _playbook_answer(message: str, role: str, user=None, context=None) -> dict:
    context = context or {}
    msg = (message or "").strip()
    msg_l = _norm(msg)
    role = role or "guest"
    role_label = role.replace("_", " ")
    user_name = context.get("user_name") or "there"
    institution_name = "your institution"
    awards_name = "Campus Clubs Excellence Awards (CCEA)"
    if user is not None and getattr(user, "is_authenticated", False) and user.institution:
        institution_name = user.institution.short_name
        awards_name = user.institution.awards_program_name or awards_name

    guide = ROLE_GUIDES.get(role, ROLE_GUIDES["student"])
    trail = []
    topic = None
    topic_label = "No matching playbook"
    hits = []

    def pack(reply, steps, actions, suggestions, extra=None):
        payload = {
            "reply": reply,
            "steps": steps,
            "action_buttons": actions,
            "suggestions": suggestions,
            "analysis": list(trail),
            "role": role,
            "institution": institution_name,
            "user_name": user_name,
            "uses_model": False,
            "topic": topic,
            "engine": "clubconnect-copilot-v2",
            "generated_at": timezone.now().isoformat(),
        }
        if extra:
            payload.update(extra)
        return payload

    if role == "committee_head" and not msg_l:
        topic = "briefing"
        trail.append("Empty question from Committee Head — opening the catch-up briefing.")
        return _committee_head_chat(user, user_name, institution_name, pack)

    last_topic = context.get("last_topic")
    topic, topic_label, hits, followed = _classify(msg_l, previous_topic=last_topic)
    if followed:
        trail.append(f"Follow-up of the previous playbook ({topic_label}).")

    cue = hits[0] if hits else None
    trail.append(f"Question: {msg or '(empty)'}")
    if topic:
        trail.append(f"Matched playbook: {topic_label}" + (f' (cue: “{cue}”).' if cue else "."))
        trail.append(f"Role in this answer: {role_label} at {institution_name}. Other roles are ignored unless they change this task.")
    else:
        trail.append("No playbook matched the wording. I will not guess or dump a role manual.")

    if topic == "briefing":
        if role in ("committee_head", "staff", "system_admin"):
            trail.append("This role may open the campus catch-up queue.")
            return _committee_head_chat(user, user_name, institution_name, pack)
        trail.append("This role cannot open the campus-wide Committee Head queue.")
        return pack(
            "That catch-up list is only for the Clubs and Societies Committee Head. I can't open it for your role — try your own dashboard, or ask me about a ticket, joining a club, or QR check-in.",
            ["Ask me a task you can actually do, or open your dashboard."],
            [{"label": "My dashboard", "path": guide["start"]}],
            ["How do I submit a ticket?", "What can I do in my role?"],
        )

    if topic == "help_ticket":
        if role in ("staff", "system_admin"):
            trail.append("Staff and campus admin can file a ticket and also read this campus's Help Center inbox.")
            return pack(
                "Yes. Open **Help Center**, tell us what happened, and click **Submit ticket**. You'll also see **Campus tickets** on that page, and we write back to the email on the ticket.",
                [
                    "Open Help Center.",
                    "Pick a category, write a short subject, and describe what went wrong.",
                    "Submit ticket, then watch Your tickets and Campus tickets.",
                ],
                [{"label": "Open Help Center", "path": "/help"}],
                ["How do I broadcast a campus notice?"],
            )
        trail.append("Any signed-in campus person can file a ticket. They cannot triage the campus inbox.")
        return pack(
            "Yes — open **Help Center** and send it from the form. That's the only way to submit a ticket here. Talking to me isn't a ticket, and it doesn't email a club leader.",
            [
                "Open Help Center.",
                "Your name and school email should already be filled in.",
                "Pick a category, write a subject, describe the problem, then Submit ticket.",
                "We'll keep it and write back to that email. Your tickets on the same page shows what you've already sent.",
            ],
            [{"label": "Open Help Center", "path": "/help"}],
            ["Where do I see my tickets?"],
        )

    if topic == "identity":
        if get_provider().uses_language_model:
            trail.append("A language model phrases the playbook. It still cannot invent screens or scores.")
            return pack(
                "I'm Copilot — I help you use ClubConnect. A language model may phrase what I say, but I still only use this product's playbook. I won't invent screens or scores.",
                [
                    "Ask me one thing you need to do, like a ticket, joining a club, or QR check-in.",
                    "If I don't know it, I'll say so.",
                ],
                [{"label": "Help Center", "path": "/help"}],
                ["How do I submit a ticket?", "What can I do in my role?"],
            )
        trail.append("This is the product playbook. No language-model key is configured, so no LLM is called.")
        return pack(
            "I'm Copilot, the in-app guide for ClubConnect. I stick to this product's playbook so I don't make things up. Ask me what you're trying to do.",
            [
                "A ticket, joining a club, QR check-in, or a monthly report are good places to start.",
                "If I don't know, I'll send you to Help Center rather than guessing.",
            ],
            [{"label": "Help Center", "path": "/help"}],
            ["How do I submit a ticket?", "What can I do in my role?"],
        )

    if topic == "signin":
        trail.append("Sign-in is decided by licensed student vs staff email domains, not by picking a campus.")
        return pack(
            f"Use the school email {institution_name} licensed — from the ClubConnect home page. Students and staff have different domains. Personal Gmail can't open a campus.",
            [
                "ALCHE students: **@alustudent.com**. Staff and lecturers: **@alueducation.com**.",
                "If you already have a campus login, use Sign In, not Create account.",
                "If your university isn't licensed yet, send a licence request from the public home page.",
            ],
            [{"label": "Sign in", "action": "open_auth", "path": "/"}],
            ["How do I submit a ticket?", "How do I request a licence?"],
        )

    if topic == "evaluation":
        return _evaluation_answer(user, role, user_name, institution_name, pack)

    if topic == "role":
        can = "\n".join(f"- {item}" for item in guide["can"])
        cannot = "\n".join(f"- {item}" for item in guide["cannot"])
        return pack(
            f"You're signed in as a **{role.replace('_', ' ')}** at **{institution_name}**. Here's what that actually lets you do.\n\n"
            f"**You can:**\n{can}\n\n**You can't:**\n{cannot}",
            [f"Your home screen is `{guide['start']}`."],
            [{"label": "Open my dashboard", "path": guide["start"]}],
            ["How do I join a club?", "How do monthly evaluations work?", "Who can see CCEA scores?"],
        )

    if topic == "join":
        if role == "student":
            return pack(
                f"You ask — you don't get added on the spot. At {institution_name} the club has to approve you first.",
                [
                    "Open Discover Clubs. You only see recognised clubs at your campus.",
                    "Open a club and click Request to Join Club.",
                    "Wait for the leader. Until then, Student Dashboard shows Requested.",
                ],
                [{"label": "Discover clubs", "path": "/"}],
                ["How do I register a new club?", "How do I check in to an event?"],
            )
        if role == "club_leader":
            return pack(
                "Students send a request. You approve or reject — they can't add themselves.",
                [
                    "Open Leader Dashboard.",
                    "Under Join requests, approve or reject each person.",
                ],
                [{"label": "Leader Dashboard", "path": "/leader-dashboard"}],
                ["How do I submit this month's report?"],
            )
        return pack(
            "Only students send join requests. If a leader is away, committee can approve.",
            ["Students use Discover Clubs. Leaders approve from the Leader Dashboard."],
            [{"label": "Discover clubs", "path": "/"}],
            ["What can I do in my role?"],
        )

    if topic == "register_club":
        if role in ("student", "club_leader"):
            return pack(
                f"Anyone at {institution_name} can ask for a new club. It stays pending until committee or staff recognise it — until then it won't show in Discover.",
                [
                    "Open Student Dashboard and request club registration.",
                    "Give it a name, category, mission, and why it should exist.",
                    "Committee Head or staff review Pending Clubs and click Recognise.",
                    "Once recognised, the proposer becomes Club Leader.",
                ],
                [{"label": "Request a club", "action": "open_request_charter", "path": "/student-dashboard"}],
                ["What can a club leader do after recognition?"],
            )
        if role in ("committee_head", "staff", "system_admin"):
            return pack(
                "Pending charters sit on Command Center. Recognise to publish the club, or reject to archive it.",
                ["Open Command Center → Pending charters.", "Read the charter, then Recognise or Reject."],
                [{"label": "Command Center", "path": "/command-center", "action": "open_pending_clubs"}],
                ["How does monthly evaluation work?"],
            )
        return pack(
            "Students request a new club. Committee or staff recognise it. You don't file a charter for yourself from this role.",
            ["Ask a student to submit the charter, then recognise it from Admin."],
            [{"label": "Admin dashboard", "path": "/admin-dashboard"}],
            ["What can I do in my role?"],
        )

    if topic == "report":
        if role == "club_leader":
            return pack(
                "That's your monthly story — we use it with QR attendance, verified evidence, and confirmed collaborations.",
                [
                    "Go to Leader Dashboard and open Submit Report.",
                    "Write this month's summary, highlights, and challenges.",
                    "Submit. Late is still accepted, but it'll show as late.",
                ],
                [{"label": "Submit report", "action": "open_submit_report", "path": "/leader-dashboard"}],
                ["What lackings will we get if we skip a report?"],
            )
        return pack(
            "Only the **Club Leader** of that club can submit its monthly report. You can read or review — you can't file it.",
            ["If you're in the demo, switch to the Club Leader persona to try it."],
            [{"label": "My dashboard", "path": guide["start"]}],
            ["What can I do in my role?"],
        )

    if topic == "checkin":
        if role == "student":
            return pack(
                "You check in at the event, with the leader's QR, in the time window. That's what counts as attendance.",
                [
                    "Open Student Dashboard and tap Scan QR Check-In.",
                    "Scan the code at the door, or paste the token they showed.",
                    "You can't check in twice, and you can't check in for someone else.",
                ],
                [{"label": "Open QR check-in", "action": "open_qr_checkin", "path": "/student-dashboard"}],
                ["How do I join a club?"],
            )
        if role == "club_leader":
            return pack(
                "You make the QR when you schedule the event. Students scan it. A second scan for the same person is rejected.",
                ["Leader Dashboard → Schedule Event → turn on QR check-in.", "Show the token at the door."],
                [{"label": "Schedule event", "action": "open_schedule_event", "path": "/leader-dashboard"}],
                ["How do I upload evidence?"],
            )
        return pack(
            "Students check in. Leaders make the QR. Committee can see totals — nobody can fake a scan.",
            ["Use the dashboard that matches your role."],
            [{"label": "My dashboard", "path": guide["start"]}],
            ["What can I do in my role?"],
        )

    if topic == "publish":
        if role == "club_leader":
            return pack(
                "You publish from your dashboard or your club page. Anyone signed in at this campus can watch it there.",
                [
                    "Leader Dashboard → Publish to campus.",
                    "Or open your club page and choose Publish for campus to watch.",
                ],
                [{"label": "Publish to campus", "action": "open_publish_watch", "path": "/leader-dashboard"}],
                ["How do I upload committee evidence?"],
            )
        return pack(
            "Leaders publish the films and photos. Open any recognised club to watch what they've shared with this campus.",
            ["Discover Clubs → open a club → Watch."],
            [{"label": "Discover clubs", "path": "/"}],
            ["What is the Hall of Excellence?"],
        )

    if topic == "hall":
        return pack(
            "The Hall of Excellence is this campus's award history — every honour, year by year, after the Committee Head publishes it.",
            ["Open Hall of Excellence from the top navigation."],
            [{"label": "Hall of Excellence", "path": "/hall-of-excellence"}],
            ["What can I do in my role?"],
        )

    if topic == "evidence":
        if role == "committee_head":
            return pack(
                "People verify evidence. A suggested number is only a suggestion — it never writes the final CCEA score.",
                [
                    "Open the Review Queue.",
                    "Look at the file, then Verify or Reject with a comment.",
                ],
                [{"label": "Review queue", "path": "/committee-dashboard"}],
                ["How does monthly evaluation use evidence?"],
            )
        if role == "club_leader":
            return pack(
                "Upload photos, rosters, or minutes against an activity. Until someone verifies it, it doesn't count as proof.",
                ["Leader Dashboard → Upload Evidence."],
                [{"label": "Upload evidence", "action": "open_upload_evidence", "path": "/leader-dashboard"}],
                ["How do I submit a monthly report?"],
            )
        return pack(
            "You don't upload club evidence as a student. Leaders upload; committee verifies. Your QR check-in is your own attendance record.",
            ["If you were there, check in with QR — that's your proof you attended."],
            [{"label": "Student dashboard", "path": "/student-dashboard"}],
            ["What can I do in my role?"],
        )

    if topic == "collab":
        return pack(
            "A collaboration only counts when the partner **confirms**. Typing another club's name isn't enough.",
            [
                "Club Leader → Propose Collaboration.",
                "The other club's leader has to confirm.",
                "That month's evaluation only counts confirmed partnerships.",
            ],
            [{"label": "Propose collaboration", "action": "open_propose_collab", "path": "/leader-dashboard"}],
            ["What lackings appear without a collaboration?"],
        )

    if topic == "awards":
        awards_ok = True
        if user is not None and getattr(user, "is_authenticated", False) and user.institution:
            awards_ok = user.institution.awards_enabled
        if not awards_ok:
            return pack(
                f"{institution_name} has awards turned off right now. Staff or campus admin can switch {awards_name} back on.",
                ["Ask staff or a system administrator to enable awards for this campus."],
                [{"label": "Staff dashboard", "path": "/staff-dashboard"}],
                ["What can I do in my role?"],
            )
        if role == "committee_head":
            return pack(
                f"Only you see {awards_name} marks until you publish them at the ceremony. That's so the night stays a surprise.",
                [
                    "Open CCEA Ceremony.",
                    "When the campus is gathered, publish to the Hall of Excellence.",
                ],
                [{"label": "Publish CCEA", "path": "/ccea-reveal"}],
                ["How are winners chosen?"],
            )
        return pack(
            f"{awards_name} show up in the Hall of Excellence after the Committee Head publishes. Until then, marks stay with them so the ceremony isn't spoiled.",
            ["Open any club to watch published films.", "Open the Hall of Excellence for published honours."],
            [{"label": "Hall of Excellence", "path": "/hall-of-excellence"}],
            ["What can I do in my role?"],
        )

    if topic == "licence":
        return pack(
            "ClubConnect is licensed campus by campus. ALCHE is first; another university asks for its own licence — they don't borrow ALCHE's.\n\n"
            "Students use the **student** email domain. Staff and lecturers use the **staff** domain.",
            [
                "ALCHE students: **@alustudent.com**. Leaders and the Committee Head are students on that domain too.",
                "ALCHE staff: **@alueducation.com** — analytics and notices.",
                "Gmail can't open ALCHE. Another university sends a licence request from the public home page.",
            ],
            [{"label": "Sign in", "action": "open_auth", "path": "/"}],
            ["What can I do as a student?"],
        )

    if topic == "notice":
        if role in ("staff", "system_admin"):
            return pack(
                "You and other staff share the campus workspace: analytics, notices, awards oversight. There's no separate dean login.",
                ["Open Staff Dashboard → Broadcast Notice, or download the executive brief."],
                [{"label": "Staff dashboard", "path": "/staff-dashboard", "action": "open_broadcast_notice"}],
                ["How does monthly evaluation work?"],
            )
        return pack(
            "Campus-wide notices are a staff job (staff email). Students and club leaders can't send a circular from this app.",
            ["Use your own dashboard. If something's wrong, tell your club leader, Committee Head, or send a Help Center ticket."],
            [{"label": "My dashboard", "path": guide["start"]}],
            ["What can I do in my role?"],
        )

    trail.append("I will not list role permissions unless you ask what you can do.")
    return pack(
        "I don't have a playbook for that, so I won't guess. Ask me about a Help Center ticket, joining a club, QR check-in, a monthly report, evidence, or awards — or send a ticket from Help Center if something's broken.",
        ["Open Help Center if this is a problem with the product rather than a how-to."],
        [{"label": "Open Help Center", "path": "/help"}],
        ["How do I submit a ticket?", "How do I join a club?", "What can I do in my role?"],
    )


def _evaluation_answer(user, role, user_name, institution_name, pack):
    if user is None or not getattr(user, "is_authenticated", False):
        return pack(
            "Monthly evaluation is available after you sign in with a school email.",
            ["Sign in, then ask again."],
            [{"label": "Sign in", "action": "open_auth", "path": "/"}],
            ["What can I do in my role?"],
        )
    if role in ("student", "staff", "system_admin"):
        return pack(
            "Campus Clubs Excellence Awards marks and rankings stay with the Committee Head until they publish the ceremony. "
            "You can watch published club films and read the Hall of Excellence after publication.",
            ["Open the Hall of Excellence for published honours.", "Open any club page to watch published films and projects."],
            [{"label": "Hall of Excellence", "path": "/hall-of-excellence"}],
            ["What can I do in my role?"],
        )

    now = timezone.now()
    year, month = now.year, now.month

    if role == "club_leader":
        membership = user.club_memberships.filter(role="leader", status="approved").select_related("club").first()
        if not membership:
            return pack(
                "I could not find a club you lead, so I cannot compute lackings.",
                ["Ask committee to confirm your leadership membership."],
                [{"label": "Leader dashboard", "path": "/leader-dashboard"}],
                ["How do I submit a monthly report?"],
            )
        result = evaluate_club_month(membership.club, year, month)
        lacking_lines = [f"- **{item['title']}** ({item['severity']}): {item['detail']}" for item in result["lackings"]] or ["- No lackings this month."]
        return pack(
            f"{user_name}, here is the **rule-based** monthly evaluation for **{result['club_name']}** "
            f"({year}-{month:02d}) at {institution_name}. Campus rankings stay with the Committee Head until the ceremony.\n\n"
            + "\n".join(lacking_lines),
            result["strengths"] or ["Submit a report, host an event, collect QR attendance, upload evidence."],
            [{"label": "Leader dashboard", "path": "/leader-dashboard"}, {"label": "Submit report", "action": "open_submit_report", "path": "/leader-dashboard"}],
            ["How do I submit a monthly report?", "How do I propose a collaboration?"],
        )

    if not user.institution_id:
        return pack(
            "This account has no institution attached, so campus-wide evaluation cannot run.",
            ["Ask a system administrator to attach your user to ALCHE or another licensed institution."],
            [{"label": "Admin dashboard", "path": "/admin-dashboard"}],
            ["What can I do in my role?"],
        )

    if role == "committee_head" and user is not None:
        return _committee_head_chat(user, user_name, institution_name, pack)

    payload = evaluate_institution_month(user.institution, year, month)
    at_risk = payload["at_risk"]
    watch = payload["needs_attention"]
    summary = (
        f"Monthly evaluation for **{institution_name}** ({year}-{month:02d}) — {payload['club_count']} recognised clubs. "
        f"**{len(at_risk)} at risk**, **{len(watch)} need attention**, **{len(payload['healthy'])} healthy**.\n\n"
        "This is a Copilot Health Scan: reports + QR attendance + confirmed collaborations + evidence. Pending partnership proposals do not count."
    )
    steps = []
    for row in (at_risk + watch)[:5]:
        titles = ", ".join(item["title"] for item in row["lackings"][:3]) or "see dashboard"
        steps.append(f"**{row['club_name']}** ({row['score']}): {titles}")
    if not steps:
        steps = ["Every recognised club is currently in the healthy band for this month."]
    return pack(
        summary,
        steps,
        [{"label": "Command Center", "path": "/command-center", "action": "open_health_scan"}, {"label": "Staff analytics", "path": "/staff-dashboard"}],
        ["What can I do in my role?", "How do CCEA awards work?"],
    )


def coach_brief(user, club=None) -> dict:
    """The coaching voice Copilot uses on dashboards — same engine as chat and health scan."""
    now = timezone.now()
    if user is None or not getattr(user, "is_authenticated", False):
        return {
            "feedback": "Sign in with your school email. Copilot will then explain exactly what you can do in this app.",
            "engine": "clubconnect-copilot-v1",
        }
    if user.role == User.Role.STUDENT:
        return {
            "feedback": (
                "Copilot: at your institution you can discover recognised clubs, request to join, "
                "request a new club charter, and QR check-in at events. You cannot submit monthly reports, "
                "verify evidence, or see confidential club lackings — those belong to leaders and committee."
            ),
            "engine": "clubconnect-copilot-v1",
        }
    if club is None:
        return {
            "feedback": "Copilot has no club in view yet. Open your dashboard after leadership is assigned.",
            "engine": "clubconnect-copilot-v1",
        }
    result = evaluate_club_month(club, now.year, now.month)
    sig = result["signals"]
    parts = [
        f"Copilot scored {result['club_name']} at {result['score']}/100 this month "
        f"({result['band'].replace('_', ' ')})."
    ]
    if result["strengths"]:
        parts.append("What is working: " + "; ".join(result["strengths"][:3]) + ".")
    if result["lackings"]:
        parts.append("Lackings: " + "; ".join(item["title"] for item in result["lackings"][:4]) + ".")
    if sig.get("confirmed_collaborations", 0) == 0:
        parts.append(
            "No confirmed collaboration this month. Propose a joint project and wait for the partner club to confirm — "
            "typing another club's name does not award CCEA collaboration credit."
        )
    else:
        parts.append(
            f"{sig['confirmed_collaborations']} confirmed collaboration(s) are counting toward CCEA. "
            "Pending proposals still do not."
        )
    return {
        "club_id": str(club.id),
        "club_name": club.name,
        "feedback": " ".join(parts),
        "evaluation": result,
        "engine": "clubconnect-copilot-v1",
        "generated_at": timezone.now().isoformat(),
    }


def health_scan(institution, year=None, month=None) -> dict:
    """Campus-wide Copilot Health Scan used by Command Center and Dean."""
    now = timezone.now()
    year = year or now.year
    month = month or now.month
    payload = evaluate_institution_month(institution, year, month)
    roster = []
    for row in payload["clubs"]:
        sig = row["signals"]
        report_ok = sig.get("report_status") in ("submitted", "late")
        roster.append(
            {
                "club": row["club_name"],
                "club_id": row["club_id"],
                "status": row["band"],
                "score": row["score"],
                "days_since_last_activity": 0 if sig.get("events") else 45,
                "report_completion_rate": 1.0 if report_ok else 0.0,
                "confirmed_collaborations": sig.get("confirmed_collaborations", 0),
                "attendance_checkins": sig.get("attendance_checkins", 0),
                "lackings": row["lackings"],
            }
        )
    brief = (
        f"Copilot Health Scan for {payload.get('institution') or 'your institution'} "
        f"({year}-{month:02d}): {payload['club_count']} recognised clubs, "
        f"{len(payload['at_risk'])} at risk, {len(payload['needs_attention'])} need attention, "
        f"{len(payload['healthy'])} healthy. Confirmed collaborations count; pending proposals do not."
    )
    return {
        **payload,
        "health_roster": roster,
        "brief": brief,
        "engine": "clubconnect-copilot-v1",
    }


def _resolve_catch_up_since(user, since_raw):
    from datetime import timedelta

    from django.utils.dateparse import parse_datetime

    now = timezone.now()
    if since_raw:
        parsed = parse_datetime(str(since_raw))
        if parsed is not None:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            return parsed
    if user is not None and getattr(user, "last_login", None):
        if now - user.last_login > timedelta(hours=2):
            return user.last_login
    return now - timedelta(days=14)


def committee_head_briefing(institution, year=None, month=None, user=None, since=None) -> dict:
    """
    Catch-up for a Committee Head who has been away: waiting approvals plus
    everything that moved, ordered most urgent → least urgent.
    """
    from apps.audit.models import AuditLog
    from apps.clubs.models import Club, ClubMembership
    from apps.collaborations.models import Collaboration
    from apps.evaluation.models import Score
    from apps.events.models import Event
    from apps.evidence.models import Evidence
    from apps.reporting.models import MonthlyReport

    now = timezone.now()
    year = year or now.year
    month = month or now.month
    since_dt = _resolve_catch_up_since(user, since)
    days_away = max(0, (now.date() - since_dt.date()).days)
    scan = health_scan(institution, year=year, month=month)
    items = []

    def add(urgency, label, category, title, detail, path, action=None, waiting_on_you=False, owner=""):
        items.append(
            {
                "urgency": urgency,
                "urgency_label": label,
                "category": category,
                "title": title,
                "detail": detail,
                "path": path,
                "action": action,
                "waiting_on_you": waiting_on_you,
                "owner": owner,
            }
        )

    for row in scan.get("at_risk") or []:
        lack = "; ".join(item["title"] for item in row.get("lackings") or []) or "Multiple critical lackings"
        add(
            1,
            "Most urgent",
            "Club at risk",
            f"{row['club_name']} is at risk ({row['score']}/100)",
            lack,
            "/command-center",
            "open_health_scan",
            waiting_on_you=True,
            owner="committee_head",
        )

    pending_charters = list(
        Club.objects.filter(institution=institution, status=Club.Status.PENDING, is_archived=False).order_by("name")
    )
    for club in pending_charters:
        add(
            2,
            "Urgent",
            "Waiting on you",
            f"{club.name} is waiting for your recognition",
            (club.charter_statement or "Student charter submitted.")[:220],
            "/command-center",
            "open_pending_clubs",
            waiting_on_you=True,
            owner="committee_head",
        )

    pending_evidence = (
        Evidence.objects.filter(
            club__institution=institution,
            status__in=(Evidence.Status.SUBMITTED, Evidence.Status.UNDER_REVIEW),
        )
        .select_related("club")
        .order_by("-created_at")[:20]
    )
    by_club = {}
    for ev in pending_evidence:
        by_club.setdefault(ev.club.name, 0)
        by_club[ev.club.name] += 1
    for club_name, count in by_club.items():
        add(
            3,
            "High",
            "Evidence queue",
            f"{count} evidence item(s) awaiting verification — {club_name}",
            "Until a committee member verifies, Copilot cannot treat this as proof for CCEA.",
            "/committee-dashboard",
            waiting_on_you=True,
            owner="committee",
        )

    pending_scores = Score.objects.filter(
        club__institution=institution,
        stage__in=(Score.Stage.AI_RECOMMENDED, Score.Stage.UNDER_REVIEW),
        final_value__isnull=True,
    ).count()
    if pending_scores:
        add(
            3,
            "High",
            "Waiting on you",
            f"{pending_scores} Copilot-recommended score(s) still need a human decision",
            "Copilot never writes the final CCEA value. A committee reviewer must approve with a reason.",
            "/committee-dashboard",
            waiting_on_you=True,
            owner="committee_head",
        )

    for row in scan.get("needs_attention") or []:
        lack = "; ".join(item["title"] for item in row.get("lackings") or []) or "Needs attention this month"
        add(
            4,
            "Watch",
            "Needs attention",
            f"{row['club_name']} needs attention ({row['score']}/100)",
            lack,
            "/command-center",
            "open_health_scan",
        )

    missing_reports = [
        row
        for row in scan.get("clubs") or []
        if row.get("signals", {}).get("report_status") in ("missing", "draft")
    ]
    for row in missing_reports:
        if row.get("band") == "at_risk":
            continue
        add(
            4,
            "Watch",
            "Monthly report",
            f"{row['club_name']} has not submitted this month's report",
            "Copilot cannot complete a fair monthly evaluation without the leader's narrative.",
            "/command-center",
        )

    join_qs = ClubMembership.objects.filter(
        club__institution=institution,
        status=ClubMembership.Status.REQUESTED,
    ).select_related("club", "user")
    join_count = join_qs.count()
    if join_count:
        sample = ", ".join(
            f"{m.user.get_full_name() or m.user.username} → {m.club.name}" for m in join_qs[:4]
        )
        add(
            5,
            "Routine",
            "Membership",
            f"{join_count} student join request(s) awaiting club leadership",
            sample or "Leaders approve from the Leader Dashboard.",
            "/leader-dashboard",
        )

    pending_collabs = Collaboration.objects.filter(
        status=Collaboration.Status.PENDING,
    ).filter(
        models_q_institution(institution)
    ).select_related("initiating_club", "partner_club")
    pending_collab_n = pending_collabs.count()
    if pending_collab_n:
        sample = "; ".join(
            f"{c.initiating_club.name} → {c.partner_club.name}" for c in pending_collabs[:4]
        )
        add(
            5,
            "Routine",
            "Collaborations",
            f"{pending_collab_n} collaboration proposal(s) not yet confirmed",
            f"{sample}. Copilot does not award CCEA collaboration credit until the partner club confirms.",
            "/leader-dashboard",
            owner="club_leader",
        )

    reports_in = MonthlyReport.objects.filter(
        club__institution=institution,
        submitted_at__gte=since_dt,
        status__in=(MonthlyReport.Status.SUBMITTED, MonthlyReport.Status.LATE),
    ).select_related("club")
    if reports_in.exists():
        names = ", ".join(r.club.name for r in reports_in[:6])
        add(
            6,
            "While you were away",
            "What got done",
            f"{reports_in.count()} monthly report(s) were filed",
            f"{names}. Leaders submitted these after your last visit.",
            "/command-center",
        )

    verified_in = Evidence.objects.filter(
        club__institution=institution,
        status=Evidence.Status.VERIFIED,
        updated_at__gte=since_dt,
    ).select_related("club")
    if verified_in.exists():
        add(
            6,
            "While you were away",
            "What got done",
            f"{verified_in.count()} evidence item(s) were verified",
            "Committee members cleared these so Copilot can count them for CCEA.",
            "/committee-dashboard",
        )

    collabs_in = Collaboration.objects.filter(
        models_q_institution(institution),
        status=Collaboration.Status.CONFIRMED,
        confirmed_at__gte=since_dt,
    ).select_related("initiating_club", "partner_club")
    if collabs_in.exists():
        sample = "; ".join(
            f"{c.initiating_club.name} × {c.partner_club.name}" for c in collabs_in[:4]
        )
        add(
            6,
            "While you were away",
            "What got done",
            f"{collabs_in.count()} collaboration(s) were confirmed by the partner club",
            sample,
            "/command-center",
        )

    events_in = Event.objects.filter(club__institution=institution, created_at__gte=since_dt).select_related("club")
    if events_in.exists():
        sample = ", ".join(f"{e.title} ({e.club.name})" for e in events_in[:4])
        add(
            6,
            "While you were away",
            "What got done",
            f"{events_in.count()} event(s) were scheduled",
            sample,
            "/command-center",
        )

    joins_in = ClubMembership.objects.filter(
        club__institution=institution,
        status=ClubMembership.Status.APPROVED,
        updated_at__gte=since_dt,
    ).select_related("club")
    if joins_in.exists():
        add(
            6,
            "While you were away",
            "What got done",
            f"{joins_in.count()} membership(s) were approved by club leaders",
            "Students who requested to join were admitted while you were out.",
            "/command-center",
        )

    audits_qs = AuditLog.objects.filter(created_at__gte=since_dt, actor__institution=institution)
    audit_n = audits_qs.count()
    if audit_n:
        sample = "; ".join(a.action for a in audits_qs[:4])
        add(
            6,
            "While you were away",
            "What got done",
            f"{audit_n} governance action(s) were recorded",
            sample or "Score, evidence, or role decisions left an audit trail.",
            "/command-center",
        )

    confirmed = sum((row.get("signals") or {}).get("confirmed_collaborations", 0) for row in scan.get("clubs") or [])
    if confirmed:
        add(
            6,
            "On track",
            "Collaborations",
            f"{confirmed} confirmed collaboration(s) this month",
            "These are counting. Pending names still are not.",
            "/command-center",
        )

    healthy = scan.get("healthy") or []
    if healthy:
        names = ", ".join(row["club_name"] for row in healthy[:6])
        add(
            7,
            "Least urgent",
            "Healthy clubs",
            f"{len(healthy)} club(s) currently healthy",
            names or "No critical lackings this month.",
            "/command-center",
        )

    items.sort(key=lambda x: (x["urgency"], x["title"]))
    waiting_n = sum(1 for i in items if i.get("waiting_on_you"))
    done_n = sum(1 for i in items if i.get("urgency_label") == "While you were away")
    if days_away >= 2:
        away_label = f"Welcome back. You last used ClubConnect about {days_away} days ago."
    elif days_away == 1:
        away_label = "Welcome back. You last used ClubConnect yesterday."
    else:
        away_label = "Here is the campus catch-up."
    if waiting_n:
        headline = (
            f"{away_label} {waiting_n} item(s) still need Committee Head action. "
            f"{done_n} thing(s) already moved while you were away. "
            "Read top to bottom: most urgent → least urgent."
        )
    else:
        headline = (
            f"{away_label} Nothing is waiting on you right now. "
            f"{done_n} thing(s) already moved. The rest of campus is listed most urgent → least."
        )
    return {
        "headline": headline,
        "away_label": away_label,
        "days_away": days_away,
        "since": since_dt.isoformat(),
        "period_year": year,
        "period_month": month,
        "institution": institution.short_name,
        "items": items,
        "waiting_on_you": [i for i in items if i.get("waiting_on_you")],
        "what_got_done": [i for i in items if i.get("urgency_label") == "While you were away"],
        "counts": {
            "waiting_on_you": waiting_n,
            "what_got_done": done_n,
            "at_risk": len(scan.get("at_risk") or []),
            "needs_attention": len(scan.get("needs_attention") or []),
            "healthy": len(healthy),
            "pending_charters": len(pending_charters),
            "pending_evidence": sum(by_club.values()),
            "pending_join_requests": join_count,
            "pending_collaborations": pending_collab_n,
            "confirmed_collaborations": confirmed,
        },
        "health_scan": scan,
        "engine": "clubconnect-copilot-v1",
        "generated_at": timezone.now().isoformat(),
    }


def models_q_institution(institution):
    from django.db.models import Q

    return Q(initiating_club__institution=institution) | Q(partner_club__institution=institution)


def _committee_head_chat(user, user_name, institution_name, pack):
    if user is None or not getattr(user, "is_authenticated", False):
        return pack(
            "Sign in as Clubs and Societies Committee Head to receive the urgency briefing.",
            ["Use your institutional email."],
            [{"label": "Sign in", "action": "open_auth", "path": "/"}],
            ["What can I do in my role?"],
        )
    if not user.institution_id:
        return pack(
            "This Committee Head account has no institution attached, so Copilot cannot build the briefing.",
            ["Ask a system administrator to attach the account to ALCHE or another licensed campus."],
            [{"label": "Admin dashboard", "path": "/admin-dashboard"}],
            ["What can I do in my role?"],
        )
    briefing = committee_head_briefing(user.institution, user=user)
    lines = []
    for i, item in enumerate(briefing["items"], start=1):
        waiting = " — waiting on you" if item.get("waiting_on_you") else ""
        lines.append(
            f"{i}. **[{item['urgency_label']}] {item['title']}**{waiting} — {item['detail']}"
        )
    if not lines:
        lines = ["You are fully caught up. Nothing is waiting and campus is clear."]
    reply = (
        f"{user_name}, you are the **Clubs and Societies Committee Head** at **{institution_name}**. "
        "Here is everything since you were last here, most urgent first.\n\n"
        f"{briefing['headline']}\n\n"
        "Most urgent → least urgent:\n\n" + "\n".join(lines)
    )
    steps = [f"{item['urgency_label']}: {item['title']}" for item in briefing["items"][:12]]
    return pack(
        reply,
        steps or ["Open Command Center to inspect the live roster."],
        [
            {"label": "Command Center", "path": "/command-center"},
            {"label": "Evidence queue", "path": "/committee-dashboard"},
            {"label": "Run Copilot Health Scan", "path": "/command-center", "action": "open_health_scan"},
        ],
        ["What can I do in my role?", "How do CCEA awards work?", "How do I recognise a pending club?"],
        extra={"briefing": briefing},
    )
