from django.conf import settings
from django.db import models

from apps.core.models import BaseModel, SoftDeleteModel


class Club(SoftDeleteModel):
    """
    The persistent Digital Club Passport.

    This record survives leadership changes and academic years.
    Leadership history is tracked separately through LeadershipTerm
    so historical information is never overwritten.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Recognition"
        RECOGNIZED = "recognized", "Recognized"
        SUSPENDED = "suspended", "Suspended"
        DORMANT = "dormant", "Dormant"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)

    logo = models.ImageField(
        upload_to="club_logos/",
        null=True,
        blank=True,
    )

    category = models.CharField(max_length=100)

    description = models.TextField(blank=True)
    mission = models.TextField(blank=True)
    vision = models.TextField(blank=True)
    objectives = models.TextField(blank=True)

    established_date = models.DateField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    institution = models.ForeignKey(
        "accounts.Institution",
        on_delete=models.PROTECT,
        related_name="clubs",
        null=True,
        blank=True,
    )

    charter_statement = models.TextField(
        blank=True,
        help_text="Why this club should be recognised at the institution.",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_clubs",
    )

    public_contact_email = models.EmailField(blank=True)

    public_contact_channels = models.JSONField(
        default=dict,
        blank=True,
    )

    # Private handover information.
    # This must never be exposed by public serializers.
    handover_notes_private = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["institution", "slug"], name="unique_club_slug_per_institution"),
            models.UniqueConstraint(fields=["institution", "name"], name="unique_club_name_per_institution"),
        ]

    def __str__(self):
        return self.name

    @property
    def leaders(self):
        """
        Return the users who are currently active leaders of this club.

        Leadership is derived from ClubMembership rather than being stored
        as a simple flag on the User model.
        """
        from apps.accounts.models import User

        leader_ids = self.memberships.filter(
            role=ClubMembership.MembershipRole.LEADER,
            is_active=True,
        ).values_list("user_id", flat=True)

        return User.objects.filter(id__in=leader_ids)


class StaffAdvisor(SoftDeleteModel):
    """
    Staff member responsible for advising a club.
    """

    club = models.OneToOneField(
        Club,
        on_delete=models.CASCADE,
        related_name="staff_advisor",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="advises_clubs",
    )

    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.club.name} - {self.user.get_full_name() or self.user.username}"


class ClubMembership(SoftDeleteModel):
    """
    Represents a user's membership and role within a club.
    """

    class MembershipRole(models.TextChoices):
        MEMBER = "member", "Member"
        LEADER = "leader", "Leader"
        OFFICER = "officer", "Officer"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        LEFT = "left", "Left"

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="club_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=MembershipRole.choices,
        default=MembershipRole.MEMBER,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )

    is_active = models.BooleanField(default=True)

    joined_at = models.DateField(
        null=True,
        blank=True,
    )

    left_at = models.DateField(
        null=True,
        blank=True,
    )

    class Source(models.TextChoices):
        JOIN = "join", "Join request"
        CENSUS = "census", "Membership census"
        OFFICE = "office", "Office / handover"

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.JOIN,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["club", "user"],
                name="unique_club_membership",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.club} ({self.role})"


class ClubConceptNote(BaseModel):
    """Club leader asks the Committee Head to release part of this year's shared grant."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        WITHDRAWN = "withdrawn", "Withdrawn"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="concept_notes")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="club_concept_notes",
    )
    academic_year = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    purpose = models.TextField()
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    committee_comment = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="concept_notes_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.club.name}: {self.title} ({self.status})"


class ClubBudgetSpend(BaseModel):
    """Money actually used from a club's share-weighted grant. Updates every ledger instantly."""

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="budget_spends")
    concept_note = models.ForeignKey(
        ClubConceptNote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spends",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="club_budget_spends",
    )
    academic_year = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    comment = models.TextField()
    spent_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.club.name} spent {self.amount}"


class LeadershipTerm(SoftDeleteModel):
    """
    Historical leadership record.

    Leadership changes create new terms rather than overwriting previous
    leadership, preserving institutional memory across academic years.
    """

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="leadership_terms",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leadership_terms",
    )

    position_title = models.CharField(
        max_length=100,
        default="President",
    )

    academic_year = models.CharField(
        max_length=9,
        help_text="e.g. 2026-2027",
    )

    start_date = models.DateField()

    end_date = models.DateField(
        null=True,
        blank=True,
    )

    achievements_summary = models.TextField(blank=True)

    lessons_learned = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return (
            f"{self.club.name} - "
            f"{self.position_title} - "
            f"{self.academic_year}"
        )


class LeadershipHandover(BaseModel):
    """Outgoing club leader submits the full committee slate to the Committee Head."""

    class Status(models.TextChoices):
        NOMINATED = "nominated", "Submitted to committee head"
        ACCEPTED = "accepted", "Accepted"
        CONFIRMED = "confirmed", "Confirmed by committee"
        DECLINED = "declined", "Declined"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="handovers")
    outgoing = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="handovers_outgoing",
    )
    incoming = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="handovers_incoming",
    )
    incoming_email = models.EmailField()
    outgoing_committee = models.JSONField(
        default=list,
        blank=True,
        help_text="[{name, email, position}, ...] as submitted by the outgoing club leader.",
    )
    incoming_committee = models.JSONField(
        default=list,
        blank=True,
        help_text="[{name, email, position}, ...] who take office when the Committee Head confirms.",
    )
    academic_year = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    achievements_summary = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOMINATED)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handovers_confirmed",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.club.name} handover ({self.status})"


class ClubHealthSnapshot(BaseModel):
    """
    Historical health snapshot for a club.

    Health status is a support/early-intervention signal. It is deliberately
    separate from the formal evaluation/scoring system and must never
    automatically change a club's evaluation score.

    A new snapshot can be generated for each club each day.
    """

    class Status(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        NEEDS_ATTENTION = "needs_attention", "Needs Attention"
        AT_RISK = "at_risk", "At Risk"

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="health_snapshots",
    )

    computed_for_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )

    # Stores the raw indicators used to determine the health status.
    #
    # Example:
    # {
    #     "days_since_last_activity": 42,
    #     "report_completion_rate": 0.5,
    #     "attendance_trend": -0.12,
    #     "evidence_completeness": 0.8
    # }
    indicators = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["club", "computed_for_date"],
                name="unique_health_snapshot_per_day",
            )
        ]

        ordering = ["-computed_for_date"]

    def __str__(self):
        return (
            f"{self.club.name} - "
            f"{self.computed_for_date} - "
            f"{self.get_status_display()}"
        )
