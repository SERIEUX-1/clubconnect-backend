"""
Wires sensitive model changes into AuditLog automatically. Import this
module's `connect()` from AuditConfig.ready() so it's registered once at
startup — see audit/apps.py.
"""
from django.db.models.signals import post_save

from apps.evaluation.models import ScoreAdjustment
from apps.evidence.models import EvidenceReview

from .middleware import get_current_ip, get_current_user
from .models import AuditLog


def _log_score_adjustment(sender, instance, created, **kwargs):
    if not created:
        return
    AuditLog.objects.create(
        actor=instance.adjusted_by or get_current_user(),
        action="score.adjusted",
        target_model="Score",
        target_id=str(instance.score_id),
        reason=instance.reason,
        metadata={"previous_value": str(instance.previous_value), "new_value": str(instance.new_value)},
        ip_address=get_current_ip(),
    )


def _log_evidence_review(sender, instance, created, **kwargs):
    if not created:
        return
    AuditLog.objects.create(
        actor=instance.reviewer or get_current_user(),
        action="evidence.reviewed",
        target_model="Evidence",
        target_id=str(instance.evidence_id),
        reason=instance.comment,
        metadata={"status": instance.status},
        ip_address=get_current_ip(),
    )


def connect():
    post_save.connect(_log_score_adjustment, sender=ScoreAdjustment, dispatch_uid="audit_score_adjustment")
    post_save.connect(_log_evidence_review, sender=EvidenceReview, dispatch_uid="audit_evidence_review")
