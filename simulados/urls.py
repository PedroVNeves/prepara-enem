from django.urls import path

from . import views

app_name = "simulados"

urlpatterns = [
    # aluno
    path("aluno/simulados/novo/", views.SimuladoStartView.as_view(), name="start"),
    path(
        "aluno/simulados/novo-customizado/",
        views.SimuladoCustomStartView.as_view(),
        name="start_custom",
    ),
    path(
        "aluno/simulados/<int:simulado_id>/questao/<int:ordem>/",
        views.SimuladoQuestionView.as_view(),
        name="questao",
    ),
    path(
        "aluno/simulados/<int:simulado_id>/resultado/",
        views.SimuladoResultView.as_view(),
        name="resultado",
    ),
    # professor
    path(
        "professor/simulados/atribuir/",
        views.SimuladoAssignmentCreateView.as_view(),
        name="assignment_create",
    ),
    path(
        "professor/simulados/atribuicoes/<int:assignment_id>/",
        views.SimuladoAssignmentResultsView.as_view(),
        name="assignment_results",
    ),
]
