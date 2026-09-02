from rest_framework import permissions, viewsets

from .models import MonthlyReport
from .serializers import MonthlyReportSerializer


class MonthlyReportViewSet(viewsets.ModelViewSet):
    queryset = MonthlyReport.objects.all()
    serializer_class = MonthlyReportSerializer
    permission_classes = [permissions.IsAuthenticated]
