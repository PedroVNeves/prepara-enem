from django.shortcuts import render
from django.views import View

from accounts.context import scoped_turmas
from accounts.mixins import AlunoContextRequiredMixin, ProfessorContextRequiredMixin


class AlunoHomeView(AlunoContextRequiredMixin, View):
    template_name = "core/aluno_home.html"

    def get(self, request):
        perfil_id = self.active_context.aluno_profile_id
        from simulados.models import Simulado

        simulados_recentes = Simulado.objects.filter(aluno_profile_id=perfil_id).order_by(
            "-criado_em"
        )[:5]
        return render(request, self.template_name, {"simulados_recentes": simulados_recentes})


class ProfessorHomeView(ProfessorContextRequiredMixin, View):
    template_name = "core/professor_home.html"

    def get(self, request):
        turmas = scoped_turmas(self.active_context)
        return render(request, self.template_name, {"turmas": turmas})
