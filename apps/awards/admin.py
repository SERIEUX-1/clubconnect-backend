from django.contrib import admin
from .models import Award
admin.site.register(Award)

from .models import HallOfExcellenceEntry
admin.site.register(HallOfExcellenceEntry)
