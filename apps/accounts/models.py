from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import BaseModel


class Institution(BaseModel):
    """
    A university, high school, or organisation licensed to use ClubConnect.
    Access is granted by setting is_active=True and listing the email
    domains members must use to sign in.
    """

    class Kind(models.TextChoices):
        UNIVERSITY = "university", "University / College"
        HIGH_SCHOOL = "high_school", "High School"
        ORGANIZATION = "organization", "Organisation"

    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=40)
    slug = models.SlugField(max_length=80, unique=True)
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.UNIVERSITY)
    country = models.CharField(max_length=80, blank=True)
    city = models.CharField(max_length=80, blank=True)
    allowed_email_domains = models.JSONField(
        default=list,
        help_text="Legacy combined list. Prefer student_email_domains and staff_email_domains.",
    )
    student_email_domains = models.JSONField(
        default=list,
        help_text='Student school mail, e.g. ["alustudent.com"]',
    )
    staff_email_domains = models.JSONField(
        default=list,
        help_text='Staff and lecturer mail, e.g. ["alueducation.com"]',
    )
    awards_enabled = models.BooleanField(default=True)
    awards_program_name = models.CharField(
        max_length=160,
        default="Campus Clubs Excellence Awards",
    )
    academic_year_start_month = models.PositiveSmallIntegerField(
        default=8,
        help_text="Month the campus academic year begins (1-12). Display and reports follow this campus, not a hardcoded calendar.",
    )
    academic_year_label = models.CharField(
        max_length=20,
        blank=True,
        help_text="Optional override, e.g. 2025-2026. If empty, ClubConnect derives the year from academic_year_start_month.",
    )
    report_deadline_day = models.PositiveSmallIntegerField(
        default=5,
        help_text="Day of month leaders should file the monthly report.",
    )
    privacy_contact_email = models.EmailField(
        blank=True,
        help_text="Campus data-protection contact. Shown on the Trust page for this institution after sign-in.",
    )
    membership_census_open = models.BooleanField(
        default=False,
        help_text="When on, students may declare or request the clubs they belong to. Committee Head toggles this.",
    )
    membership_census_opened_at = models.DateTimeField(null=True, blank=True)
    membership_census_opened_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opened_membership_windows",
    )
    member_grant_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=7,
        help_text="Grant per unique student per academic year. Split evenly across the clubs that student belongs to.",
    )
    member_grant_currency = models.CharField(
        max_length=8,
        default="USD",
        help_text="ISO currency for the per-member grant (USD, RWF, EUR, …).",
    )
    logo_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Campus mark shown after sign-in (never on the public ClubConnect landing).",
    )
    is_active = models.BooleanField(default=True)
    primary_color = models.CharField(max_length=16, default="#0284c7")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.short_name or self.name

    def _domain_list(self, *groups):
        found = []
        for group in groups:
            for item in group or []:
                value = str(item).lower().strip().lstrip("@")
                if value and value not in found:
                    found.append(value)
        return found

    def licensed_email_domains(self):
        return self._domain_list(
            self.student_email_domains,
            self.staff_email_domains,
            self.allowed_email_domains,
        )

    def audience_for_email(self, email: str):
        """Return 'staff', 'student', or None. Staff domains are checked first."""
        if not email or "@" not in email:
            return None
        domain = email.rsplit("@", 1)[1].lower().strip()
        staff = self._domain_list(self.staff_email_domains)
        students = self._domain_list(self.student_email_domains)
        legacy = self._domain_list(self.allowed_email_domains)
        if domain in staff:
            return "staff"
        if domain in students:
            return "student"
        if domain in legacy:
            return "staff" if domain in staff else "student"
        return None

    def accepts_email(self, email: str) -> bool:
        return self.audience_for_email(email) is not None

    def role_for_new_account(self, email: str) -> str:
        if self.audience_for_email(email) == "staff":
            return "staff"
        return "student"

    def current_academic_year(self, today=None):
        if self.academic_year_label:
            return self.academic_year_label
        from django.utils import timezone as dj_tz

        day = today or dj_tz.now().date()
        start = int(self.academic_year_start_month or 8)
        start = min(12, max(1, start))
        if day.month >= start:
            return f"{day.year}-{day.year + 1}"
        return f"{day.year - 1}-{day.year}"

    def current_ceremony_year(self, today=None):
        label = self.current_academic_year(today=today)
        if "-" in label:
            return label.split("-")[0]
        return label[:4]


def institution_for_email(email: str):
    if not email or "@" not in email:
        return None
    for institution in Institution.objects.filter(is_active=True):
        if institution.accepts_email(email):
            return institution
    return None


class LicenceInquiry(BaseModel):
    """A campus that found ClubConnect and asked to be licensed."""

    class Kind(models.TextChoices):
        UNIVERSITY = "university", "University / College"
        HIGH_SCHOOL = "high_school", "High School"
        ORGANIZATION = "organization", "Organisation"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        LICENSED = "licensed", "Licensed"
        DECLINED = "declined", "Declined"

    institution_name = models.CharField(max_length=255)
    country = models.CharField(max_length=80, blank=True)
    city = models.CharField(max_length=80, blank=True)
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.UNIVERSITY)
    contact_name = models.CharField(max_length=160)
    contact_role = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=40, blank=True)
    student_email_domain = models.CharField(max_length=120, blank=True)
    staff_email_domain = models.CharField(max_length=120, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    operator_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.institution_name} ({self.contact_email})"


class SupportTicket(BaseModel):
    """A Help Center issue from a guest or a signed-in campus member."""

    class Category(models.TextChoices):
        ACCOUNT = "account", "Account & sign-in"
        CLUBS = "clubs", "Clubs & membership"
        TECHNICAL = "technical", "Technical problem"
        LICENCE = "licence", "Campus licence"
        OTHER = "other", "Something else"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PENDING = "pending", "In progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    name = models.CharField(max_length=160)
    email = models.EmailField()
    category = models.CharField(max_length=24, choices=Category.choices, default=Category.OTHER)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    language = models.CharField(max_length=12, default="en")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    operator_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} ({self.email})"


class CampusCommitteeHandover(BaseModel):
    """Outgoing Committee Head submits the campus C&S committee to the campus administrator."""

    class Status(models.TextChoices):
        NOMINATED = "nominated", "Submitted to campus administrator"
        CONFIRMED = "confirmed", "Confirmed"
        DECLINED = "declined", "Declined"

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="committee_handovers",
    )
    outgoing = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="campus_handovers_outgoing",
    )
    incoming = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="campus_handovers_incoming",
    )
    incoming_email = models.EmailField()
    outgoing_committee = models.JSONField(default=list, blank=True)
    incoming_committee = models.JSONField(default=list, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    achievements_summary = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOMINATED)
    confirmed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campus_handovers_confirmed",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.institution.short_name} committee handover ({self.status})"


class User(AbstractUser, BaseModel):
    """
    Extends Django's battle-tested auth (password hashing, session/JWT
    support) rather than reinventing it — PRS Section 14 explicitly
    recommends Django auth with institutional SSO as a later integration.
    """

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        CLUB_LEADER = "club_leader", "Club Leader"
        COMMITTEE_HEAD = "committee_head", "Committee Head"
        STAFF = "staff", "Staff / Lecturer"
        SYSTEM_ADMIN = "system_admin", "System Administrator"

    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        related_name="members",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.STUDENT)
    student_id = models.CharField(max_length=32, blank=True, db_index=True)
    phone_number = models.CharField(max_length=32, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    preferred_language = models.CharField(max_length=12, default="en", blank=True)

    # Populated for Committee Members who are only authorized for specific
    # clubs (PRS Section 4: "Authorized assigned/committee data").
    assigned_clubs = models.ManyToManyField(
        "clubs.Club", blank=True, related_name="assigned_committee_members"
    )

    def led_club_ids(self):
        from apps.clubs.models import ClubMembership

        return list(
            ClubMembership.objects.filter(
                user=self,
                role=ClubMembership.MembershipRole.LEADER,
                status=ClubMembership.Status.APPROVED,
                is_active=True,
            ).values_list("club_id", flat=True)
        )

    def assigned_club_ids(self):
        return set(self.assigned_clubs.values_list("id", flat=True))

    def is_leader_of(self, club) -> bool:
        return club.leaders.filter(id=self.id).exists()

    def public_identity(self) -> dict:
        institution = self.institution
        return {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.get_full_name() or self.username,
            "role": self.role,
            "student_id": self.student_id,
            "assigned_clubs": [str(cid) for cid in self.assigned_club_ids()],
            "led_clubs": [str(cid) for cid in self.led_club_ids()],
            "institution": (
                {
                    "id": str(institution.id),
                    "name": institution.name,
                    "short_name": institution.short_name,
                    "slug": institution.slug,
                    "kind": institution.kind,
                    "awards_enabled": institution.awards_enabled,
                    "awards_program_name": institution.awards_program_name,
                    "student_email_domains": institution.student_email_domains,
                    "staff_email_domains": institution.staff_email_domains,
                    "logo_url": institution.logo_url or "",
                    "primary_color": institution.primary_color,
                    "academic_year": institution.current_academic_year(),
                    "academic_year_start_month": institution.academic_year_start_month,
                    "report_deadline_day": institution.report_deadline_day,
                    "privacy_contact_email": institution.privacy_contact_email or "",
                    "membership_census_open": bool(institution.membership_census_open),
                    "member_grant_amount": str(institution.member_grant_amount),
                    "member_grant_currency": institution.member_grant_currency or "USD",
                }
                if institution
                else None
            ),
            "is_demo_account": self.email.lower().endswith("@alustudent.com")
            or self.email.lower().endswith("@alueducation.com")
            or self.email.lower().endswith("@alche.ac.mu")
            or self.email.lower().endswith("@student.alche.ac.mu")
            or self.email.lower().endswith("@campus.edu"),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "preferred_language": self.preferred_language or "en",
        }

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"
