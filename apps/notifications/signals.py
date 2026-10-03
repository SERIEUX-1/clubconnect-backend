"""Email goes out by itself when a concerned record changes. Views do not
need a separate send step; seed data is muted."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.accounts.models import CampusCommitteeHandover, LicenceInquiry, SupportTicket, User
from apps.audit.middleware import get_current_user
from apps.clubs.models import ClubBudgetSpend, ClubConceptNote, ClubMembership, LeadershipHandover
from apps.evidence.models import EvidenceReview
from apps.notifications.dispatch import (
    accounts_for_emails,
    campus_admins,
    committee_heads,
    mail_address,
    notifications_muted,
    notify,
    notify_people,
    person_label,
)
from apps.notifications.models import Notification


def _actor():
    user = get_current_user()
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    return None


def _actor_label():
    user = _actor()
    return person_label(user) if user else "ClubConnect"


def _remember_status(instance):
    if not instance.pk:
        instance._prior_status = None
        return
    old = type(instance).objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    instance._prior_status = old


@receiver(pre_save, sender=ClubMembership)
@receiver(pre_save, sender=ClubConceptNote)
@receiver(pre_save, sender=LeadershipHandover)
@receiver(pre_save, sender=CampusCommitteeHandover)
@receiver(pre_save, sender=LicenceInquiry)
@receiver(pre_save, sender=SupportTicket)
def remember_status(sender, instance, **kwargs):
    if notifications_muted():
        return
    _remember_status(instance)


@receiver(post_save, sender=ClubMembership)
def membership_changed(sender, instance, created, **kwargs):
    if notifications_muted():
        return
    club = instance.club
    prior = getattr(instance, "_prior_status", None)
    actor = _actor()
    label = _actor_label()
    if created and instance.status == ClubMembership.Status.REQUESTED:
        notify_people(
            list(club.leaders) + list(committee_heads(club.institution)),
            exclude=actor or instance.user,
            category=Notification.Category.SYSTEM,
            title=f"Membership request: {club.name}",
            body=f"{person_label(instance.user)} asked to join {club.name}. Confirm or decline it while the membership window is open.",
        )
        return
    if not created and instance.status == ClubMembership.Status.REQUESTED and prior != ClubMembership.Status.REQUESTED:
        notify_people(
            list(club.leaders) + list(committee_heads(club.institution)),
            exclude=actor or instance.user,
            category=Notification.Category.SYSTEM,
            title=f"Membership request: {club.name}",
            body=f"{person_label(instance.user)} asked to join {club.name}. Confirm or decline it while the membership window is open.",
        )
        return
    if not created and instance.status == ClubMembership.Status.APPROVED and prior != ClubMembership.Status.APPROVED:
        notify(
            recipient=instance.user,
            category=Notification.Category.SYSTEM,
            title=f"You are in {club.name}",
            body=f"{label} confirmed your membership of {club.name}.",
            link_url="/student-dashboard",
        )
        return
    if not created and instance.status == ClubMembership.Status.REJECTED and prior != ClubMembership.Status.REJECTED:
        notify(
            recipient=instance.user,
            category=Notification.Category.SYSTEM,
            title=f"Membership not confirmed: {club.name}",
            body=f"{label} did not confirm your membership of {club.name}.",
            link_url="/student-dashboard",
        )


@receiver(post_save, sender=ClubConceptNote)
def concept_note_changed(sender, instance, created, **kwargs):
    if notifications_muted():
        return
    club = instance.club
    institution = club.institution
    currency = institution.member_grant_currency if institution else ""
    actor = _actor()
    if created:
        notify_people(
            committee_heads(institution),
            exclude=actor,
            category=Notification.Category.SYSTEM,
            title="Concept note",
            body=f"{club.name} requested {instance.amount_requested} {currency} — {instance.title}",
            link_url="/membership-ledger",
        )
        return
    prior = getattr(instance, "_prior_status", None)
    if instance.status == prior:
        return
    extra = f" Comment: {instance.committee_comment}" if instance.committee_comment else ""
    if instance.status == ClubConceptNote.Status.APPROVED:
        title = f"Concept note approved: {club.name}"
        body = f'"{instance.title}" was approved.{extra}'
    elif instance.status == ClubConceptNote.Status.DECLINED:
        title = f"Concept note declined: {club.name}"
        body = f'"{instance.title}" was not approved.{extra}'
    else:
        return
    notify_people(
        [instance.submitted_by, *club.leaders],
        exclude=actor,
        category=Notification.Category.SYSTEM,
        title=title,
        body=body,
        link_url="/club-leader-dashboard",
    )


@receiver(post_save, sender=ClubBudgetSpend)
def spend_recorded(sender, instance, created, **kwargs):
    if notifications_muted() or not created:
        return
    club = instance.club
    currency = club.institution.member_grant_currency if club.institution_id else ""
    notify_people(
        club.leaders,
        exclude=_actor(),
        category=Notification.Category.SYSTEM,
        title=f"Grant spend recorded: {club.name}",
        body=f"{instance.amount} {currency} — {instance.comment}",
        link_url="/club-leader-dashboard",
    )


@receiver(post_save, sender=LeadershipHandover)
def club_handover_changed(sender, instance, created, **kwargs):
    if notifications_muted():
        return
    club = instance.club
    actor = _actor()
    label = _actor_label()
    incoming_emails = [seat.get("email") for seat in (instance.incoming_committee or [])]
    if created:
        notify_people(
            committee_heads(club.institution),
            exclude=actor,
            category=Notification.Category.SYSTEM,
            title=f"Committee handover: {club.name}",
            body=(
                f"{label} submitted the outgoing and incoming club committee for {club.name}. "
                "Confirm it to switch offices and permissions."
            ),
            link_url="/committee-dashboard",
        )
        notify_people(
            accounts_for_emails(club.institution, incoming_emails),
            exclude=actor,
            category=Notification.Category.SYSTEM,
            title=f"You are named on the {club.name} committee",
            body=(
                f"{label} named you on the incoming committee for {club.name}. "
                "The Committee Head still has to confirm the handover."
            ),
            link_url="/club-leader-dashboard",
        )
        return
    prior = getattr(instance, "_prior_status", None)
    if instance.status == prior:
        return
    if instance.status == LeadershipHandover.Status.DECLINED:
        notify_people(
            [instance.outgoing, instance.incoming]
            + list(accounts_for_emails(club.institution, [instance.incoming_email]))
            + list(committee_heads(club.institution)),
            exclude=actor,
            category=Notification.Category.SYSTEM,
            title=f"Committee handover declined: {club.name}",
            body=f"{label} declined the committee handover for {club.name}.",
        )
        return
    if instance.status == LeadershipHandover.Status.CONFIRMED:
        notify_people(
            [instance.outgoing, instance.incoming, *accounts_for_emails(club.institution, incoming_emails)],
            exclude=actor,
            category=Notification.Category.SYSTEM,
            title=f"Committee handover confirmed: {club.name}",
            body=(
                f"The Committee Head confirmed the {club.name} committee. "
                "Offices and permissions now follow the incoming slate."
            ),
            link_url="/club-leader-dashboard",
        )


@receiver(post_save, sender=CampusCommitteeHandover)
def campus_handover_changed(sender, instance, created, **kwargs):
    if notifications_muted():
        return
    actor = _actor()
    label = _actor_label()
    institution = instance.institution
    incoming_emails = [seat.get("email") for seat in (instance.incoming_committee or [])]
    if created:
        notify_people(
            campus_admins(institution),
            exclude=actor,
            category=Notification.Category.SYSTEM,
            title="Committee Head handover",
            body=(
                f"{label} submitted the Clubs & Societies committee handover. "
                "Confirm it to switch Committee Head permissions."
            ),
            link_url="/admin-dashboard",
        )
        notify_people(
            accounts_for_emails(institution, incoming_emails),
            exclude=actor,
            category=Notification.Category.SYSTEM,
            title="You are named incoming Committee Head",
            body=(
                f"{label} named you on the incoming Clubs & Societies committee. "
                "The campus administrator still has to confirm the handover."
            ),
            link_url="/committee-dashboard",
        )
        return
    prior = getattr(instance, "_prior_status", None)
    if instance.status == prior:
        return
    if instance.status == CampusCommitteeHandover.Status.DECLINED:
        notify_people(
            [instance.outgoing, instance.incoming]
            + list(campus_admins(institution))
            + list(accounts_for_emails(institution, [instance.incoming_email])),
            exclude=actor,
            category=Notification.Category.SYSTEM,
            title="Committee Head handover declined",
            body=f"{label} declined the Clubs & Societies committee handover.",
        )
        return
    if instance.status == CampusCommitteeHandover.Status.CONFIRMED:
        notify_people(
            [instance.outgoing, instance.incoming, *accounts_for_emails(institution, incoming_emails)],
            exclude=actor,
            category=Notification.Category.SYSTEM,
            title="Committee Head handover confirmed",
            body="The campus administrator confirmed the Clubs & Societies committee handover. Offices now follow the incoming slate.",
        )


@receiver(post_save, sender=EvidenceReview)
def evidence_reviewed(sender, instance, created, **kwargs):
    if notifications_muted() or not created:
        return
    evidence = instance.evidence
    notify_people(
        list(evidence.club.leaders) + [evidence.uploaded_by],
        exclude=_actor(),
        category=Notification.Category.VERIFICATION,
        title=f"Evidence {evidence.get_status_display().lower()}: {evidence.club.name}",
        body=(
            f"{_actor_label()} marked evidence as {evidence.get_status_display()}."
            + (f" {instance.comment}" if instance.comment else "")
        ),
        link_url="/club-leader-dashboard",
    )


@receiver(post_save, sender=LicenceInquiry)
def licence_inquiry_changed(sender, instance, created, **kwargs):
    if notifications_muted():
        return
    if created:
        body = (
            f"{instance.contact_name} ({instance.contact_role or 'campus contact'}) "
            f"at {instance.institution_name} asked to licence ClubConnect.\n"
            f"Email: {instance.contact_email}\n"
            f"Phone: {instance.contact_phone or '—'}\n"
            f"Student domain: {instance.student_email_domain or '—'}\n"
            f"Staff domain: {instance.staff_email_domain or '—'}"
        )
        notify_people(
            User.objects.filter(role=User.Role.SYSTEM_ADMIN, is_active=True, institution__isnull=True),
            category=Notification.Category.SYSTEM,
            title=f"Licence request: {instance.institution_name}",
            body=body,
            link_url="/admin-dashboard",
        )
        mail_address(
            instance.contact_email,
            subject=f"[ClubConnect] We received your licence request for {instance.institution_name}",
            body=(
                f"Hello {instance.contact_name},\n\n"
                "ClubConnect received your request to licence the product for "
                f"{instance.institution_name}. We will write to this same address with next steps.\n\n"
                f"Student domain: {instance.student_email_domain or '—'}\n"
                f"Staff domain: {instance.staff_email_domain or '—'}\n"
            ),
        )
        return
    prior = getattr(instance, "_prior_status", None)
    if instance.status == prior:
        return
    mail_address(
        instance.contact_email,
        subject=f"[ClubConnect] Licence request update — {instance.institution_name}",
        body=(
            f"Hello {instance.contact_name},\n\n"
            f"Your ClubConnect licence request for {instance.institution_name} is now "
            f"{instance.get_status_display()}. We are writing to the address you gave us.\n\n"
            f"{instance.operator_notes or ''}"
        ),
    )


@receiver(post_save, sender=SupportTicket)
def support_ticket_changed(sender, instance, created, **kwargs):
    if notifications_muted():
        return
    if created:
        recipients = list(User.objects.filter(role=User.Role.SYSTEM_ADMIN, is_active=True))
        if instance.institution_id:
            recipients.extend(
                User.objects.filter(
                    institution_id=instance.institution_id,
                    role=User.Role.STAFF,
                    is_active=True,
                )
            )
        notify_people(
            recipients,
            exclude=_actor(),
            category=Notification.Category.SYSTEM,
            title=f"Help Center: {instance.subject}",
            body=f"{instance.name} ({instance.email}) · {instance.get_category_display()}\n{instance.subject}\n\n{instance.body}",
            link_url="/help",
        )
        mail_address(
            instance.email,
            subject=f"[ClubConnect] We received: {instance.subject}",
            body=(
                f"Hello {instance.name},\n\n"
                "Your Help Center message reached ClubConnect. Campus staff will reply to this address.\n\n"
                f"{instance.subject}\n{instance.body}\n"
            ),
        )
        return
    prior = getattr(instance, "_prior_status", None)
    if instance.status == prior:
        return
    if instance.user_id:
        notify(
            recipient=instance.user,
            category=Notification.Category.SYSTEM,
            title=f"Help ticket update: {instance.subject}",
            body=f"Status is now {instance.get_status_display()}.",
            link_url="/help",
        )
    mail_address(
        instance.email,
        subject=f"[ClubConnect] Help ticket update: {instance.subject}",
        body=(
            f"Hello {instance.name},\n\n"
            f"Your Help Center ticket is now {instance.get_status_display()}.\n\n"
            f"{instance.operator_notes or ''}"
        ),
    )
