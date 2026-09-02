from django.contrib import admin

from .models import Club, ClubMembership, LeadershipTerm, StaffAdvisor

admin.site.register(Club)
admin.site.register(ClubMembership)
admin.site.register(LeadershipTerm)
admin.site.register(StaffAdvisor)
