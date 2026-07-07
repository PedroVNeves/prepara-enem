from django.contrib import admin

from .models import Resposta, Simulado, SimuladoAssignment, SimuladoQuestion


class SimuladoQuestionInline(admin.TabularInline):
    model = SimuladoQuestion
    extra = 0


@admin.register(Simulado)
class SimuladoAdmin(admin.ModelAdmin):
    list_display = ["id", "aluno_profile", "tipo", "exam", "assignment", "status", "criado_em"]
    list_filter = ["tipo", "status", "exam"]
    inlines = [SimuladoQuestionInline]


@admin.register(SimuladoAssignment)
class SimuladoAssignmentAdmin(admin.ModelAdmin):
    list_display = ["id", "professor", "escola", "turma", "criado_em"]
    list_filter = ["escola", "turma"]


@admin.register(Resposta)
class RespostaAdmin(admin.ModelAdmin):
    list_display = [
        "aluno_profile",
        "question",
        "alternativa_escolhida",
        "correta",
        "tempo_gasto_ms",
    ]
    list_filter = ["correta"]
