from rest_framework import permissions, viewsets

from .models import Award
from .serializers import AwardSerializer


class AwardViewSet(viewsets.ModelViewSet):
    queryset = Award.objects.all()
    serializer_class = AwardSerializer
    permission_classes = [permissions.IsAuthenticated]

from .models import HallOfExcellenceEntry
from .serializers import HallOfExcellenceEntrySerializer

class HallOfExcellenceEntryViewSet(viewsets.ModelViewSet):
    queryset = HallOfExcellenceEntry.objects.all()
    serializer_class = HallOfExcellenceEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
