import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.tests.factories import ClubFactory, ClubLeaderFactory, InstitutionFactory, UserFactory
from apps.notifications.dispatch import looks_like_email, mail_address, notify, notify_people
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db

EMAIL = override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    NOTIFICATION_CHANNELS=["in_app", "email"],
    PUBLIC_APP_URL="http://127.0.0.1:5173",
    DEFAULT_FROM_EMAIL="ClubConnect <noreply@clubconnect.local>",
)


def test_looks_like_email_rejects_empty_and_junk():
    assert looks_like_email("sarah.leader@alustudent.com")
    assert not looks_like_email("")
    assert not looks_like_email("not-an-email")
    assert not looks_like_email("missing-domain@")


@EMAIL
def test_notify_emails_licensed_account_and_skips_blank():
    inst = InstitutionFactory()
    person = UserFactory(institution=inst, email="leader@student.test-university.edu", first_name="Sara")
    blank = UserFactory(institution=inst, email="", username="no-mail")
    notify(
        recipient=person,
        category=Notification.Category.SYSTEM,
        title="Membership request: Robotics",
        body="Alex asked to join Robotics.",
        link_url="/club-leader-dashboard",
    )
    notify(
        recipient=blank,
        category=Notification.Category.SYSTEM,
        title="Should stay in-app only",
        body="No address on this account.",
    )
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == ["leader@student.test-university.edu"]
    assert "Robotics" in sent.subject
    assert "http://127.0.0.1:5173/club-leader-dashboard" in sent.body
    assert Notification.objects.filter(recipient=blank).exists()


@EMAIL
def test_notify_people_skips_the_actor():
    inst = InstitutionFactory()
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=inst, email="elena@staff.edu")
    leader = UserFactory(role=User.Role.CLUB_LEADER, institution=inst, email="sarah@student.edu")
    notify_people(
        [head, leader, head],
        exclude=head,
        category=Notification.Category.SYSTEM,
        title="Concept note approved",
        body="Approved.",
    )
    assert [m.to for m in mail.outbox] == [["sarah@student.edu"]]


@EMAIL
def test_join_request_emails_club_leader_not_the_student():
    club = ClubFactory(status="recognized", name="Robotics")
    leader, _ = ClubLeaderFactory.create(club=club, email="sarah.leader@alustudent.com", first_name="Sarah")
    head = UserFactory(
        role=User.Role.COMMITTEE_HEAD,
        institution=club.institution,
        email="dr.elena.head@alueducation.com",
        first_name="Elena",
    )
    student = UserFactory(
        role=User.Role.STUDENT,
        institution=club.institution,
        email="alex.student@alustudent.com",
        first_name="Alex",
    )
    client = APIClient()
    client.force_authenticate(head)
    window = client.patch("/api/membership-census/window/", {"open": True}, format="json")
    assert window.status_code == 200
    mail.outbox.clear()
    client.force_authenticate(student)
    res = client.post("/api/club-memberships/", {"club": str(club.id)}, format="json")
    assert res.status_code == 201, res.data
    recipients = [addr for msg in mail.outbox for addr in msg.to]
    assert recipients.count("sarah.leader@alustudent.com") == 1
    assert recipients.count("dr.elena.head@alueducation.com") == 1
    assert "alex.student@alustudent.com" not in recipients

    mail.outbox.clear()
    client.force_authenticate(leader)
    ok = client.post(f"/api/club-memberships/{res.data['id']}/approve/")
    assert ok.status_code == 200, ok.data
    assert [m.to for m in mail.outbox] == [["alex.student@alustudent.com"]]
    assert "You are in Robotics" in mail.outbox[0].subject


@EMAIL
def test_licence_inquiry_mails_the_contact_they_typed():
    UserFactory(role=User.Role.SYSTEM_ADMIN, email="admin@alche.ac.mu", institution=None)
    client = APIClient()
    res = client.post(
        "/api/licence-inquiries/",
        {
            "institution_name": "Harbour College",
            "country": "Mauritius",
            "kind": "university",
            "contact_name": "Priya Shah",
            "contact_role": "Dean of Students",
            "contact_email": "priya.shah@harbour.ac.mu",
            "student_email_domain": "student.harbour.ac.mu",
            "staff_email_domain": "harbour.ac.mu",
        },
        format="json",
    )
    assert res.status_code == 201, res.data
    tos = [tuple(m.to) for m in mail.outbox]
    assert tos.count(("priya.shah@harbour.ac.mu",)) == 1
    assert tos.count(("admin@alche.ac.mu",)) == 1


@EMAIL
def test_mail_address_does_not_invent_recipients():
    mail_address("", subject="Nope", body="Nope")
    mail_address("not-valid", subject="Nope", body="Nope")
    assert mail.outbox == []


@EMAIL
def test_saving_a_membership_row_emails_without_a_send_button():
    club = ClubFactory(status="recognized", name="Drama")
    leader, _ = ClubLeaderFactory.create(club=club, email="sarah.leader@alustudent.com")
    student = UserFactory(
        institution=club.institution,
        email="alex.student@alustudent.com",
        first_name="Alex",
    )
    mail.outbox.clear()
    from apps.clubs.models import ClubMembership

    membership = ClubMembership.objects.create(
        club=club,
        user=student,
        status=ClubMembership.Status.REQUESTED,
        role=ClubMembership.MembershipRole.MEMBER,
    )
    recipients = [addr for msg in mail.outbox for addr in msg.to]
    assert recipients.count("sarah.leader@alustudent.com") == 1
    assert "alex.student@alustudent.com" not in recipients
    mail.outbox.clear()
    membership.status = ClubMembership.Status.APPROVED
    membership.save(update_fields=["status", "updated_at"])
    assert [m.to for m in mail.outbox] == [["alex.student@alustudent.com"]]


@EMAIL
def test_deadline_reminder_mails_the_club_leader_once():
    from datetime import date

    from apps.notifications.reminders import send_deadline_reminders

    inst = InstitutionFactory(report_deadline_day=3)
    club = ClubFactory(institution=inst, status="recognized", name="Robotics")
    ClubLeaderFactory.create(club=club, email="sarah.leader@alustudent.com")
    mail.outbox.clear()
    first = send_deadline_reminders(today=date(2026, 10, 3))
    assert first == 1
    assert mail.outbox[0].to == ["sarah.leader@alustudent.com"]
    assert send_deadline_reminders(today=date(2026, 10, 3)) == 0


def test_sqlite_backup_writes_a_file(tmp_path, settings):
    import sqlite3

    from django.core.management import call_command

    db = tmp_path / "app.sqlite3"
    sqlite3.connect(db).close()
    dest = tmp_path / "backups"
    original = settings.DATABASES["default"].copy()
    settings.DATABASES["default"] = {
        **original,
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(db),
    }
    settings.BACKUP_DIR = str(dest)
    try:
        call_command("backup_data")
        files = list(dest.glob("clubconnect-*.sqlite3"))
        assert len(files) == 1
    finally:
        settings.DATABASES["default"] = original
