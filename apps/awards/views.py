from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core.permissions import IsCommitteeHead
from apps.core.tenancy import is_platform_operator

from .models import Award, HallOfExcellenceEntry
from .serializers import AwardSerializer, HallOfExcellenceEntrySerializer, ceremony_year


class AwardViewSet(viewsets.ModelViewSet):
    serializer_class = AwardSerializer
    permission_classes = [permissions.IsAuthenticated, IsCommitteeHead]

    def get_queryset(self):
        user = self.request.user
        qs = Award.objects.select_related("winner_club", "cycle")
        if user.institution_id and not is_platform_operator(user):
            return qs.filter(
                Q(winner_club__institution_id=user.institution_id) | Q(winner_club__isnull=True)
            ).distinct()
        return qs

    def _write_hall(self, award, year: str):
        if not award.winner_club_id:
            return None
        citation = (award.description or "").strip()
        existing = award.hall_of_excellence_entries.filter(club=award.winner_club).first()
        if existing and existing.citation:
            citation = existing.citation
        entry, _ = HallOfExcellenceEntry.objects.update_or_create(
            award=award,
            club=award.winner_club,
            defaults={
                "academic_year": ceremony_year(year),
                "citation": citation,
            },
        )
        return entry

    @action(detail=True, methods=["post"])
    def reveal(self, request, pk=None):
        award = self.get_object()
        award.is_revealed = True
        award.revealed_at = timezone.now()
        award.finalized_by = request.user
        award.save(update_fields=["is_revealed", "revealed_at", "finalized_by", "updated_at"])
        return Response(AwardSerializer(award).data)

    @action(detail=False, methods=["post"], url_path="publish-ceremony")
    def publish_ceremony(self, request):
        """Publish CCEA winners and standing to the Hall of Excellence for the campus."""
        year = request.data.get("year")
        if not year and request.user.institution_id:
            year = request.user.institution.current_ceremony_year()
        year = ceremony_year(year or timezone.now().year)
        published = []
        for award in self.get_queryset().filter(winner_club__isnull=False):
            if request.user.institution_id and award.winner_club.institution_id != request.user.institution_id:
                continue
            award.is_revealed = True
            award.revealed_at = timezone.now()
            award.finalized_by = request.user
            award.save(update_fields=["is_revealed", "revealed_at", "finalized_by", "updated_at"])
            self._write_hall(award, year)
            published.append(AwardSerializer(award).data)
        return Response({"year": year, "published": published, "count": len(published)}, status=status.HTTP_200_OK)


class HallOfExcellenceEntryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = HallOfExcellenceEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = HallOfExcellenceEntry.objects.select_related("club", "award").filter(award__is_revealed=True)
        if user.institution_id and not is_platform_operator(user):
            return qs.filter(club__institution_id=user.institution_id)
        return qs
