from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("aluno/", views.AlunoHomeView.as_view(), name="aluno_home"),
    path("professor/", views.ProfessorHomeView.as_view(), name="professor_home"),
]
