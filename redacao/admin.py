from django.contrib import admin

from .models import EssayAssignment, EssayPrompt, EssaySubmission


@admin.register(EssayPrompt)
class EssayPromptAdmin(admin.ModelAdmin):
    list_display = ["titulo", "ano"]


@admin.register(EssayAssignment)
class EssayAssignmentAdmin(admin.ModelAdmin):
    list_display = ["tema", "escola", "professor", "correction_mode", "turma", "criado_em"]
    list_filter = ["escola", "correction_mode"]


@admin.register(EssaySubmission)
class EssaySubmissionAdmin(admin.ModelAdmin):
    list_display = [
        "aluno_profile",
        "prompt",
        "assignment",
        "status",
        "correction_source",
        "nota_final",
        "criado_em",
    ]
    list_filter = ["status", "correction_source", "submission_type"]
