from django.contrib import admin

from .models import Club, ClubBudgetSpend, ClubConceptNote, ClubMembership, LeadershipHandover, LeadershipTerm, StaffAdvisor

admin.site.register(Club)
admin.site.register(ClubMembership)
admin.site.register(LeadershipTerm)
admin.site.register(LeadershipHandover)
admin.site.register(StaffAdvisor)
admin.site.register(ClubConceptNote)
admin.site.register(ClubBudgetSpend)
