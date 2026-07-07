from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.context import current_aluno_profile, current_professor, scoped_alunos, scoped_turmas
from accounts.mixins import AlunoContextRequiredMixin, ProfessorContextRequiredMixin

from .models import CorrectionMode, EssayAssignment, EssayPrompt, EssaySubmission, SubmissionType
from .services import generate_essay_theme, grade_essay_manually


class EssaySubmitView(AlunoContextRequiredMixin, View):
    template_name = "redacao/submit.html"

    def get(self, request):
        prompts = EssayPrompt.objects.all()
        return render(request, self.template_name, {"prompts": prompts})

    def post(self, request):
        perfil = current_aluno_profile(request)
        prompt_id = request.POST.get("prompt_id") or None
        prompt = EssayPrompt.objects.filter(pk=prompt_id).first() if prompt_id else None
        submission = EssaySubmission.objects.create(
            aluno_profile=perfil,
            prompt=prompt,
            texto=request.POST["texto"],
        )
        return redirect("redacao:resultado", submission_id=submission.id)


class EssayResultView(AlunoContextRequiredMixin, View):
    template_name = "redacao/resultado.html"

    def get(self, request, submission_id):
        perfil = current_aluno_profile(request)
        submission = get_object_or_404(EssaySubmission, pk=submission_id, aluno_profile=perfil)
        detalhes = []
        if submission.notas_competencias:
            feedback = submission.feedback or {}
            detalhes = [
                {"competencia": k, "nota": v, "feedback": feedback.get(k, "")}
                for k, v in submission.notas_competencias.items()
            ]
        return render(request, self.template_name, {"submission": submission, "detalhes": detalhes})


class EssayAssignmentSubmitView(AlunoContextRequiredMixin, View):
    template_name = "redacao/assignment_submit.html"

    def get(self, request, assignment_id):
        perfil = current_aluno_profile(request)
        assignment = get_object_or_404(EssayAssignment, pk=assignment_id, escola_id=perfil.escola_id)
        return render(request, self.template_name, {"assignment": assignment})

    def post(self, request, assignment_id):
        perfil = current_aluno_profile(request)
        assignment = get_object_or_404(EssayAssignment, pk=assignment_id, escola_id=perfil.escola_id)

        submission_type = request.POST.get("submission_type", SubmissionType.TEXT)
        if submission_type == SubmissionType.PHOTO and assignment.correction_mode != CorrectionMode.MANUAL:
            # correção por IA só aceita texto digitado por ora (sem OCR/visão computacional)
            submission_type = SubmissionType.TEXT

        submission = EssaySubmission.objects.create(
            aluno_profile=perfil,
            assignment=assignment,
            submission_type=submission_type,
            texto=request.POST.get("texto", ""),
            foto=request.FILES.get("foto"),
            correction_source=assignment.correction_mode,
        )
        return redirect("redacao:resultado", submission_id=submission.id)


class EssayAssignmentCreateView(ProfessorContextRequiredMixin, View):
    template_name = "redacao/assignment_create.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {"turmas": scoped_turmas(self.active_context), "alunos": scoped_alunos(self.active_context)},
        )

    def post(self, request):
        professor = current_professor(request)
        turma_id = request.POST.get("turma_id") or None
        turma = scoped_turmas(self.active_context).filter(pk=turma_id).first() if turma_id else None
        aluno_ids = request.POST.getlist("alunos")
        alunos = scoped_alunos(self.active_context).filter(pk__in=aluno_ids) if aluno_ids else None

        tema_gerado_por_ia = bool(request.POST.get("gerar_tema_ia"))
        if tema_gerado_por_ia:
            gerado = generate_essay_theme()
            tema, texto_motivador = gerado["tema"], gerado["texto_motivador"]
        else:
            tema = request.POST["tema"]
            texto_motivador = request.POST.get("texto_motivador", "")

        assignment = EssayAssignment.objects.create(
            professor=professor,
            escola=professor.escola,
            tema=tema,
            texto_motivador=texto_motivador,
            tema_gerado_por_ia=tema_gerado_por_ia,
            correction_mode=request.POST["correction_mode"],
            turma=turma,
        )
        if alunos:
            assignment.alunos.set(alunos)
        return redirect("redacao:assignment_results", assignment_id=assignment.id)


class EssayAssignmentResultsView(ProfessorContextRequiredMixin, View):
    template_name = "redacao/assignment_results.html"

    def get(self, request, assignment_id):
        assignment = get_object_or_404(
            EssayAssignment, pk=assignment_id, escola_id=self.active_context.escola_id
        )
        submissoes = assignment.submissoes.select_related("aluno_profile")
        return render(
            request, self.template_name, {"assignment": assignment, "submissoes": submissoes}
        )


class ProfessorEssayGradingView(ProfessorContextRequiredMixin, View):
    template_name = "redacao/grade.html"

    def get(self, request, submission_id):
        submission = self._get_submission(request, submission_id)
        return render(request, self.template_name, {"submission": submission})

    def post(self, request, submission_id):
        professor = current_professor(request)
        submission = self._get_submission(request, submission_id)
        notas = {c: int(request.POST[c]) for c in ["c1", "c2", "c3", "c4", "c5"]}
        feedback = {c: request.POST.get(f"feedback_{c}", "") for c in ["c1", "c2", "c3", "c4", "c5"]}
        grade_essay_manually(submission, professor, notas, feedback)
        return redirect("redacao:assignment_results", assignment_id=submission.assignment_id)

    def _get_submission(self, request, submission_id):
        return get_object_or_404(
            EssaySubmission,
            pk=submission_id,
            assignment__escola_id=self.active_context.escola_id,
        )
