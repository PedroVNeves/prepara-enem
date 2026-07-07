from django.shortcuts import get_object_or_404, render
from django.views import View

from accounts.context import current_aluno_profile, scoped_alunos, scoped_turmas
from accounts.mixins import AlunoContextRequiredMixin, ProfessorContextRequiredMixin

from . import services


class StudentReportView(AlunoContextRequiredMixin, View):
    template_name = "reports/student_report.html"

    def get(self, request):
        perfil = current_aluno_profile(request)
        context = {
            "erros_por_assunto": services.erros_por_assunto(perfil),
            "dominio_por_area": services.dominio_por_area(perfil),
            "dominio_por_assunto": services.dominio_por_assunto(perfil),
            "tempo_por_questao": services.tempo_por_questao_vs_media(perfil),
            "impacto_erros": services.impacto_erros_no_theta(perfil),
        }
        return render(request, self.template_name, context)


class TurmaStatsView(ProfessorContextRequiredMixin, View):
    template_name = "reports/turma_stats.html"

    def get(self, request, turma_id):
        turma = get_object_or_404(scoped_turmas(self.active_context), pk=turma_id)
        return render(
            request,
            self.template_name,
            {"turma": turma, "resultado": services.turma_stats(turma)},
        )


class AlunoStatsView(ProfessorContextRequiredMixin, View):
    template_name = "reports/student_report.html"

    def get(self, request, aluno_id):
        aluno = get_object_or_404(scoped_alunos(self.active_context), pk=aluno_id)
        context = {
            "aluno": aluno,
            "erros_por_assunto": services.erros_por_assunto(aluno),
            "dominio_por_area": services.dominio_por_area(aluno),
            "dominio_por_assunto": services.dominio_por_assunto(aluno),
            "tempo_por_questao": services.tempo_por_questao_vs_media(aluno),
            "impacto_erros": services.impacto_erros_no_theta(aluno),
        }
        return render(request, self.template_name, context)
