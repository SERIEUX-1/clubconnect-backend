from rest_framework import permissions, viewsets

from .models import ImpactProject
from .serializers import ImpactProjectSerializer


class ImpactProjectViewSet(viewsets.ModelViewSet):
    queryset = ImpactProject.objects.all()
    serializer_class = ImpactProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
