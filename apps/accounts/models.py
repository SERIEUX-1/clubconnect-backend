from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import BaseModel


class User(AbstractUser, BaseModel):
    """
    Extends Django's battle-tested auth (password hashing, session/JWT
    support) rather than reinventing it — PRS Section 14 explicitly
    recommends Django auth with institutional SSO as a later integration.
    """

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        CLUB_LEADER = "club_leader", "Club Leader"
        COMMITTEE_MEMBER = "committee_member", "Committee Member"
        COMMITTEE_HEAD = "committee_head", "Committee Head"
        DEAN_ADMIN = "dean_admin", "Dean / Institutional Admin"
        SYSTEM_ADMIN = "system_admin", "System Administrator"

    role = models.CharField(max_length=32, choices=Role.choices, default=Role.STUDENT)
    student_id = models.CharField(max_length=32, blank=True, db_index=True)
    phone_number = models.CharField(max_length=32, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    # Populated for Committee Members who are only authorized for specific
    # clubs (PRS Section 4: "Authorized assigned/committee data").
    assigned_clubs = models.ManyToManyField(
        "clubs.Club", blank=True, related_name="assigned_committee_members"
    )

    def assigned_club_ids(self):
        return set(self.assigned_clubs.values_list("id", flat=True))

    def is_leader_of(self, club) -> bool:
        return club.leaders.filter(id=self.id).exists()

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"
