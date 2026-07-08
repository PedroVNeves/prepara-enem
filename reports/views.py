from django.shortcuts import get_object_or_404, render
from django.views import View

from accounts.context import current_aluno_profile, scoped_alunos, scoped_turmas
from accounts.mixins import AlunoContextRequiredMixin, ProfessorContextRequiredMixin
from exams.models import Discipline

from . import services


def _discipline_label(value):
    return dict(Discipline.choices).get(value, value)


def _dashboard_json(perfil):
    """Serializa os dados do relatório em JSON simples pro D3 no template —
    QuerySets/model instances não são serializáveis, e o front não precisa
    (nem deve) enxergar os objetos ORM inteiros."""
    dominio_area = [
        {
            "discipline": h.discipline,
            "discipline_label": _discipline_label(h.discipline),
            "theta": round(h.theta, 3),
        }
        for h in services.dominio_por_area(perfil)
    ]

    dominio_assunto = [
        {
            "topic": item["question__topic__name"],
            "discipline_label": _discipline_label(item["question__discipline"]),
            "total": item["total"],
            "acertos": item["acertos"],
            "percentual": round(100 * item["acertos"] / item["total"], 1) if item["total"] else 0,
        }
        for item in services.dominio_por_assunto(perfil)
    ]

    erros_assunto = [
        {
            "discipline_label": _discipline_label(item["question__discipline"]),
            "topic": item["question__topic__name"] or "Assunto não classificado",
            "total": item["total"],
        }
        for item in services.erros_por_assunto(perfil)
    ]

    tempo_questao = [
        {
            "discipline_label": _discipline_label(item["discipline"]),
            "media_aluno_s": round((item["media_aluno_ms"] or 0) / 1000, 1),
            "media_global_s": round((item["media_global_ms"] or 0) / 1000, 1),
        }
        for item in services.tempo_por_questao_vs_media(perfil)
    ]

    impacto_erros = [
        {
            "label": f"Q{item['resposta'].question.external_index} — ENEM {item['resposta'].question.exam.year}",
            "discipline_label": _discipline_label(item["resposta"].question.discipline),
            "informacao": round(item["informacao"], 3),
        }
        for item in services.impacto_erros_no_theta(perfil)
    ]

    return {
        "dominio_area": dominio_area,
        "dominio_assunto": dominio_assunto,
        "erros_assunto": erros_assunto,
        "tempo_questao": tempo_questao,
        "impacto_erros": impacto_erros,
    }


class StudentReportView(AlunoContextRequiredMixin, View):
    template_name = "reports/student_report.html"

    def get(self, request):
        perfil = current_aluno_profile(request)
        context = {"dashboard_data": _dashboard_json(perfil)}
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
        context = {"aluno": aluno, "dashboard_data": _dashboard_json(aluno)}
        return render(request, self.template_name, context)
