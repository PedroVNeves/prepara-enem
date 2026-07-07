from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.context import current_aluno_profile, current_professor, scoped_alunos, scoped_turmas
from accounts.mixins import AlunoContextRequiredMixin, ProfessorContextRequiredMixin
from exams.models import Discipline, Exam, Topic

from .models import Simulado, SimuladoAssignment, StatusSimulado
from .services import (
    create_simulado_assignment,
    finalize_simulado,
    record_answer,
    score_summary,
    start_custom_simulado,
    start_fixed_simulado,
)


class SimuladoStartView(AlunoContextRequiredMixin, View):
    template_name = "simulados/start.html"

    def get(self, request):
        exams = Exam.objects.all()
        return render(request, self.template_name, {"exams": exams})

    def post(self, request):
        perfil = current_aluno_profile(request)
        exam = get_object_or_404(Exam, pk=request.POST["exam_id"])
        simulado = start_fixed_simulado(perfil, exam)
        return redirect("simulados:questao", simulado_id=simulado.id, ordem=1)


class SimuladoCustomStartView(AlunoContextRequiredMixin, View):
    template_name = "simulados/start_custom.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {"disciplines": Discipline.choices, "topics": Topic.objects.all()},
        )

    def post(self, request):
        perfil = current_aluno_profile(request)
        discipline = request.POST["discipline"]
        topic_id = request.POST.get("topic_id") or None
        topic = Topic.objects.filter(pk=topic_id).first() if topic_id else None
        quantidade = int(request.POST.get("quantidade") or 10)
        simulado = start_custom_simulado(perfil, discipline, topic, quantidade)
        if simulado.perguntas.count() == 0:
            return redirect("simulados:start_custom")
        return redirect("simulados:questao", simulado_id=simulado.id, ordem=1)


class SimuladoQuestionView(AlunoContextRequiredMixin, View):
    template_name = "simulados/questao.html"

    def get(self, request, simulado_id, ordem):
        simulado = self._get_simulado(request, simulado_id)
        pergunta = get_object_or_404(simulado.perguntas.select_related("question"), ordem=ordem)
        alternativas = pergunta.question.alternatives.all()
        total = simulado.perguntas.count()
        return render(
            request,
            self.template_name,
            {
                "simulado": simulado,
                "pergunta": pergunta,
                "question": pergunta.question,
                "alternativas": alternativas,
                "ordem": ordem,
                "total": total,
                "is_last": ordem >= total,
            },
        )

    def post(self, request, simulado_id, ordem):
        simulado = self._get_simulado(request, simulado_id)
        pergunta = get_object_or_404(simulado.perguntas.select_related("question"), ordem=ordem)
        alternativa = request.POST.get("alternativa", "")
        tempo_gasto_ms = int(request.POST.get("tempo_gasto_ms") or 0)
        record_answer(simulado, pergunta.question, alternativa, tempo_gasto_ms)

        total = simulado.perguntas.count()
        if ordem >= total:
            return redirect("simulados:resultado", simulado_id=simulado.id)
        return redirect("simulados:questao", simulado_id=simulado.id, ordem=ordem + 1)

    @staticmethod
    def _get_simulado(request, simulado_id):
        perfil = current_aluno_profile(request)
        return get_object_or_404(Simulado, pk=simulado_id, aluno_profile=perfil)


class SimuladoResultView(AlunoContextRequiredMixin, View):
    template_name = "simulados/resultado.html"

    def get(self, request, simulado_id):
        perfil = current_aluno_profile(request)
        simulado = get_object_or_404(Simulado, pk=simulado_id, aluno_profile=perfil)
        if simulado.status != StatusSimulado.FINALIZADO:
            resumo = finalize_simulado(simulado)
        else:
            resumo = score_summary(simulado)
        return render(request, self.template_name, {"simulado": simulado, "resumo": resumo})


class SimuladoAssignmentCreateView(ProfessorContextRequiredMixin, View):
    template_name = "simulados/assignment_create.html"

    def get(self, request):
        professor = current_professor(request)
        return render(
            request,
            self.template_name,
            {
                "disciplines": Discipline.choices,
                "topics": Topic.objects.all(),
                "turmas": scoped_turmas(self.active_context),
                "alunos": scoped_alunos(self.active_context),
            },
        )

    def post(self, request):
        professor = current_professor(request)
        topic_id = request.POST.get("topic_id") or None
        turma_id = request.POST.get("turma_id") or None
        turma = scoped_turmas(self.active_context).filter(pk=turma_id).first() if turma_id else None
        aluno_ids = request.POST.getlist("alunos")
        alunos = scoped_alunos(self.active_context).filter(pk__in=aluno_ids) if aluno_ids else None

        config = {
            "discipline": request.POST["discipline"],
            "topic_id": int(topic_id) if topic_id else None,
            "quantidade": int(request.POST.get("quantidade") or 10),
        }
        assignment = create_simulado_assignment(
            professor=professor,
            escola=professor.escola,
            config=config,
            turma=turma,
            alunos=alunos,
        )
        return redirect("simulados:assignment_results", assignment_id=assignment.id)


class SimuladoAssignmentResultsView(ProfessorContextRequiredMixin, View):
    template_name = "simulados/assignment_results.html"

    def get(self, request, assignment_id):
        assignment = get_object_or_404(
            SimuladoAssignment, pk=assignment_id, escola_id=self.active_context.escola_id
        )
        simulados = assignment.simulados.select_related("aluno_profile")
        resultados = []
        for simulado in simulados:
            if simulado.status == StatusSimulado.FINALIZADO:
                resumo = score_summary(simulado)
            else:
                resumo = None
            resultados.append({"simulado": simulado, "resumo": resumo})
        return render(
            request, self.template_name, {"assignment": assignment, "resultados": resultados}
        )
