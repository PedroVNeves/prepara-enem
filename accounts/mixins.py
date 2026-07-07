"""Mixins de escopo por contexto. Toda view que toca dados de aluno/turma/
escola deve herdar daqui em vez de usar querysets sem filtro — o isolamento
multi-tenant é responsabilidade da aplicação (Django conecta direto no
Postgres do Supabase, RLS de PostgREST não se aplica a essa conexão)."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

from .context import get_active_context


class ActiveContextRequiredMixin(LoginRequiredMixin):
    """Garante que existe um contexto ativo na sessão; senão manda escolher."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            context = get_active_context(request)
            if context is None:
                return redirect("accounts:select_context")
            self.active_context = context
        return super().dispatch(request, *args, **kwargs)


class AlunoContextRequiredMixin(ActiveContextRequiredMixin):
    """Só permite acesso quando o contexto ativo é de aluno (individual ou de escola)."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and self.active_context.kind != "aluno":
            return redirect("accounts:select_context")
        return response


class ProfessorContextRequiredMixin(ActiveContextRequiredMixin):
    """Só permite acesso quando o contexto ativo é de professor/admin de escola."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and self.active_context.kind != "professor":
            return redirect("accounts:select_context")
        return response
