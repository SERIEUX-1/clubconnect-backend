from django.contrib import admin

from .models import Appeal, EvaluationCriterion, EvaluationCycle, Score, ScoreAdjustment

admin.site.register(EvaluationCycle)
admin.site.register(EvaluationCriterion)
admin.site.register(Score)
admin.site.register(ScoreAdjustment)
admin.site.register(Appeal)
