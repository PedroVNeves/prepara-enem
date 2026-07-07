from django.contrib import admin

from .models import ItemParameters, StudentAbility


@admin.register(ItemParameters)
class ItemParametersAdmin(admin.ModelAdmin):
    list_display = ["question", "a", "b", "c", "difficulty_source", "respondent_count"]
    list_filter = ["difficulty_source"]


@admin.register(StudentAbility)
class StudentAbilityAdmin(admin.ModelAdmin):
    list_display = ["aluno_profile", "discipline", "theta", "method"]
    list_filter = ["discipline", "method"]
