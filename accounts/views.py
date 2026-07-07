from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from .context import available_contexts, set_active_context


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"

    def get_success_url(self):
        return "/contexto/"


class SelectContextView(LoginRequiredMixin, View):
    template_name = "accounts/select_context.html"

    def get(self, request):
        contexts = available_contexts(request.user)
        if len(contexts) == 1:
            set_active_context(request, contexts[0])
            return redirect(self._destination(contexts[0]))
        return render(request, self.template_name, {"contexts": list(enumerate(contexts))})

    def post(self, request):
        contexts = available_contexts(request.user)
        index = int(request.POST["context_index"])
        context = contexts[index]
        set_active_context(request, context)
        return redirect(self._destination(context))

    @staticmethod
    def _destination(context):
        return "/professor/" if context.kind == "professor" else "/aluno/"
