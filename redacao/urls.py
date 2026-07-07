from django.urls import path

from . import views

app_name = "redacao"

urlpatterns = [
    # aluno
    path("aluno/redacao/nova/", views.EssaySubmitView.as_view(), name="submit"),
    path("aluno/redacao/<int:submission_id>/", views.EssayResultView.as_view(), name="resultado"),
    path(
        "aluno/redacao/atribuicao/<int:assignment_id>/",
        views.EssayAssignmentSubmitView.as_view(),
        name="assignment_submit",
    ),
    # professor
    path(
        "professor/redacao/atribuir/",
        views.EssayAssignmentCreateView.as_view(),
        name="assignment_create",
    ),
    path(
        "professor/redacao/atribuicoes/<int:assignment_id>/",
        views.EssayAssignmentResultsView.as_view(),
        name="assignment_results",
    ),
    path(
        "professor/redacao/corrigir/<int:submission_id>/",
        views.ProfessorEssayGradingView.as_view(),
        name="grade",
    ),
]
