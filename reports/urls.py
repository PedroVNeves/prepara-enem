from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("aluno/relatorio/", views.StudentReportView.as_view(), name="student_report"),
    path("professor/turma/<int:turma_id>/", views.TurmaStatsView.as_view(), name="turma_stats"),
    path("professor/aluno/<int:aluno_id>/", views.AlunoStatsView.as_view(), name="aluno_stats"),
]
