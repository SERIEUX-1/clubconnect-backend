import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.tests.factories import InstitutionFactory, UserFactory

pytestmark = pytest.mark.django_db


def _chat(user, message):
    client = APIClient()
    client.force_authenticate(user)
    return client.post("/api/copilot/chat/", {"message": message}, format="json")


def test_student_ticket_question_stays_on_help_center():
    inst = InstitutionFactory(short_name="ALCHE")
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    res = _chat(student, "how can i submit a ticket?")
    assert res.status_code == 200
    reply = res.data["reply"].lower()
    assert "help center" in reply
    assert "submit a ticket" in reply or "submit ticket" in reply
    assert "you can:" not in reply
    assert "browse every recognised club" not in reply
    analysis = " ".join(res.data["analysis"]).lower()
    assert "help center ticket" in analysis
    assert any(btn["path"] == "/help" for btn in res.data["action_buttons"])


def test_unknown_question_does_not_dump_role_manual():
    inst = InstitutionFactory(short_name="ALCHE")
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    res = _chat(student, "what is the weather on campus?")
    assert res.status_code == 200
    reply = res.data["reply"].lower()
    assert "do not have a playbook" in reply or "don't have a playbook" in reply
    assert "you can:" not in reply
    assert "student dashboard" not in reply


def test_student_monthly_report_still_points_to_leader():
    inst = InstitutionFactory(short_name="ALCHE")
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    res = _chat(student, "How do I submit a monthly report?")
    assert res.status_code == 200
    assert "Club Leader" in res.data["reply"]
    assert res.data["engine"] == "clubconnect-copilot-v2"


def test_copilot_says_it_is_not_a_generative_model():
    inst = InstitutionFactory(short_name="ALCHE")
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    res = _chat(student, "are you AI or ChatGPT?")
    assert res.status_code == 200
    reply = res.data["reply"].lower()
    assert "playbook" in reply
    assert res.data.get("uses_model") is False


def test_messy_wording_still_finds_help_center():
    inst = InstitutionFactory(short_name="ALCHE")
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    res = _chat(student, "the page is broken and I need to complain")
    assert res.status_code == 200
    assert "help center" in res.data["reply"].lower()
    assert res.data.get("topic") == "help_ticket"


def test_follow_up_stays_on_previous_playbook():
    inst = InstitutionFactory(short_name="ALCHE")
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    client = APIClient()
    client.force_authenticate(student)
    first = client.post("/api/copilot/chat/", {"message": "how can i submit a ticket?"}, format="json")
    assert first.data["topic"] == "help_ticket"
    res = client.post(
        "/api/copilot/chat/",
        {"message": "where?", "context": {"last_topic": first.data["topic"]}},
        format="json",
    )
    assert res.status_code == 200
    assert res.data["topic"] == "help_ticket"
    assert "help center" in res.data["reply"].lower() or "go here" in res.data["reply"].lower()


def test_language_model_phrases_playbook_without_inventing_buttons(monkeypatch):
    from apps.ai_assistant import copilot as copilot_mod
    from apps.ai_assistant.providers import ChatGuideResponse, RuleBasedProvider

    class FakeModel(RuleBasedProvider):
        uses_language_model = True

        def map_topic(self, question, catalog):
            return None

        def guide_chat(self, request):
            assert "Help Center" in request.playbook_reply
            return ChatGuideResponse(
                reply="Use Help Center and click Submit ticket. That is the only ticket path.",
                steps=["Open Help Center.", "Submit ticket."],
                suggestions=["Where do I see my tickets?"],
                model_name="fake-copilot-model",
            )

    monkeypatch.setattr(copilot_mod, "get_provider", lambda: FakeModel())
    inst = InstitutionFactory(short_name="ALCHE")
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    res = _chat(student, "how can i submit a ticket?")
    assert res.status_code == 200
    assert res.data["uses_model"] is True
    assert "Submit ticket" in res.data["reply"]
    assert "browse every recognised club" not in res.data["reply"].lower()
    assert any(btn["path"] == "/help" for btn in res.data["action_buttons"])
    assert res.data["engine"].startswith("clubconnect-copilot-model:")
