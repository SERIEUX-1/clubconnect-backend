"""
$0 local reasoner for ClubConnect Copilot.

Scores a question against playbooks with phrases, synonym bags, and
short follow-ups. No cloud API. No invented screens.
"""
from __future__ import annotations

import re

_STOP = frozenset(
    """
    a an the to of for in on at is am are was were be do does did can could
    would should i me my you your we our this that it how what who why when
    which please plz just want need like somehow
    """.split()
)

_FOLLOW_UP = (
    "where",
    "where is that",
    "where do i go",
    "which page",
    "which screen",
    "what button",
    "and then",
    "then what",
    "next step",
    "next",
    "the form",
    "that one",
    "same page",
    "ok and then",
)

# Extra words beyond the phrase list in copilot.py — messy human wording.
_WORD_BAGS = {
    "help_ticket": {
        "ticket",
        "tickets",
        "support",
        "bug",
        "issue",
        "complaint",
        "helpdesk",
        "broken",
        "error",
        "glitch",
        "feedback",
        "problem",
        "complain",
        "helpdesk",
    },
    "join": {"join", "enrol", "enroll", "membership", "member"},
    "register_club": {"charter", "found", "launch", "start"},
    "report": {"report", "reports", "monthly"},
    "checkin": {"qr", "checkin", "attendance", "scan", "token"},
    "publish": {"publish", "video", "film", "watch"},
    "hall": {"hall", "excellence", "honour", "honor"},
    "evidence": {"evidence", "proof", "artefact", "artifact", "verify"},
    "collab": {"collab", "collaboration", "partner", "partnership"},
    "awards": {"ccea", "award", "awards", "ceremony", "reveal"},
    "licence": {"licence", "license", "licensed", "gmail", "domain"},
    "notice": {"broadcast", "notice", "circular", "announcement"},
    "signin": {"login", "password", "signin", "locked", "access"},
    "evaluation": {"lacking", "lackings", "health", "scan", "evaluation", "score"},
    "role": {"permissions", "allowed", "role"},
    "briefing": {"briefing", "urgent", "catchup", "away"},
    "identity": {"copilot", "chatgpt", "bot", "model"},
    "publish": {"publish", "video", "film"},
}

_PHRASE_EXTRA = {
    "help_ticket": (
        "report a problem",
        "report a bug",
        "something is broken",
        "page is broken",
        "does not work",
        "doesn't work",
        "doesnt work",
        "not working",
        "contact it",
        "contact support",
        "send feedback",
        "i have a complaint",
        "talk to support",
    ),
    "join": (
        "become a member",
        "sign up for a club",
        "enrol in a club",
        "enroll in a club",
        "how do i join",
    ),
    "report": (
        "submit a report",
        "file the report",
        "this month's report",
        "this months report",
    ),
    "signin": (
        "forgot password",
        "cannot log in",
        "cant log in",
        "locked out",
        "wrong password",
        "cannot sign in",
    ),
    "licence": (
        "another campus",
        "university of rwanda",
        "want clubconnect",
        "personal gmail",
    ),
}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9@./]+", " ", (text or "").lower()).strip()


def tokens(msg_l: str) -> set[str]:
    return {part for part in msg_l.split() if part and part not in _STOP}


def question_shape(msg_l: str) -> str:
    padded = f" {msg_l} "
    if any(p in padded for p in (" where ", " which page ", " which screen ", " what page ")):
        return "where"
    if msg_l.startswith("where"):
        return "where"
    if any(p in msg_l for p in ("can i ", "am i allowed", "do i have permission", "able to ")):
        return "can"
    if padded.startswith(" why ") or " why " in padded:
        return "why"
    if any(p in msg_l for p in ("who can", "who is allowed", "whose job")):
        return "who"
    return "how"


def is_follow_up(msg_l: str) -> bool:
    if msg_l in _FOLLOW_UP or any(msg_l == p or msg_l.startswith(p + " ") for p in _FOLLOW_UP):
        return True
    toks = tokens(msg_l)
    if 0 < len(toks) <= 4 and toks <= {
        "where",
        "that",
        "it",
        "this",
        "page",
        "button",
        "form",
        "next",
        "then",
        "and",
        "there",
        "go",
        "open",
        "screen",
    }:
        return True
    return False


def classify(msg_l: str, phrase_playbooks, generic_cues, previous_topic=None):
    """
    phrase_playbooks: iterable of (id, label, phrases)
    Returns (topic_id, label, hits, followed_up)
    """
    if previous_topic and is_follow_up(msg_l):
        label = next((lab for tid, lab, _ in phrase_playbooks if tid == previous_topic), previous_topic)
        return previous_topic, label, ["follow-up"], True

    ranked = []
    toks = tokens(msg_l)
    for topic_id, label, phrases in phrase_playbooks:
        extra = _PHRASE_EXTRA.get(topic_id, ())
        all_phrases = tuple(phrases) + tuple(extra)
        phrase_hits = [p for p in all_phrases if p in msg_l]
        bag = _WORD_BAGS.get(topic_id, set())
        word_hits = (bag & toks) | {w for w in bag if len(w) > 5 and w in msg_l}
        if not phrase_hits and not word_hits:
            continue
        best_phrase = max((len(p) for p in phrase_hits), default=0)
        generic = 1 if (phrase_hits and max(phrase_hits, key=len) in generic_cues) else 0
        score = best_phrase * 4 + len(word_hits) * 5 - generic * 8
        ranked.append((score, best_phrase, topic_id, label, phrase_hits or sorted(word_hits)))
    if not ranked:
        return None, "No matching playbook", [], False
    ranked.sort(reverse=True)
    score, _best, topic_id, label, hits = ranked[0]
    if score < 5:
        return None, "No matching playbook", [], False
    return topic_id, label, hits, False


def _first_name(raw: str) -> str:
    name = (raw or "").strip().split(" ")[0]
    if not name or name.lower() in {"there", "guest", "user"}:
        return ""
    return name


def local_phrase(question: str, payload: dict) -> dict:
    """Speak the playbook like a person. Adds no new facts."""
    analysis = list(payload.get("analysis") or [])
    msg_l = norm(question)
    shape = question_shape(msg_l)
    steps = payload.get("steps") or []
    reply = (payload.get("reply") or "").strip()
    name = _first_name(payload.get("user_name") or "")
    hello = f"{name}, " if name and not reply.startswith(name) else ""

    if shape == "where" and steps:
        where = steps[0].rstrip(".")
        spoken = f"{hello}you'll find that on **{where}**."
        if reply and where.lower() not in reply.lower():
            spoken = f"{spoken} {reply}"
        elif reply:
            spoken = f"{hello}{reply}"
        payload["reply"] = spoken
    if hello and reply:
        keep_cap = reply.startswith(("I ", "I'm", "I’ve", "**"))
        rest = reply if keep_cap else reply[0].lower() + reply[1:]
        payload["reply"] = f"{hello}{rest}"
    analysis.append(f"Spoke it as a {shape} answer. $0 local voice, no cloud model.")
    payload["analysis"] = analysis
    payload["uses_model"] = False
    payload["engine"] = "clubconnect-copilot-v2"
    return payload
