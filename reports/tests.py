from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import AlunoProfile, Escola, Professor, Turma, User
from exams.models import Alternative, Discipline, Exam, Question, Topic
from irt.models import DifficultySource, ItemParameters, StudentAbility
from simulados.models import Resposta, Simulado, TipoSimulado

from .formulas import item_information, probability_correct
from .services import (
    dominio_por_area,
    erros_por_assunto,
    impacto_erros_no_theta,
    tempo_por_questao_vs_media,
    turma_stats,
)


def _make_question(exam, index, discipline, topic=None, b=0.0, correct="A"):
    q = Question.objects.create(
        exam=exam,
        external_index=index,
        discipline=discipline,
        topic=topic,
        context=f"Contexto {index}",
        alternatives_introduction="Assinale a correta.",
        correct_alternative=correct,
    )
    for letter in "ABCDE":
        Alternative.objects.create(question=q, letter=letter, text=letter, is_correct=(letter == correct))
    ItemParameters.objects.create(question=q, a=1.0, b=b, c=0.2, difficulty_source=DifficultySource.LLM_ESTIMATE)
    return q


class FormulasTests(TestCase):
    def test_probability_correct_at_theta_equals_b_is_midpoint(self):
        p = probability_correct(a=1.0, b=0.0, c=0.2, theta=0.0)
        self.assertAlmostEqual(p, 0.6, places=2)  # c + (1-c)/2

    def test_item_information_is_nonnegative(self):
        info = item_information(a=1.0, b=0.0, c=0.2, theta=0.0)
        self.assertGreaterEqual(info, 0.0)

    def test_item_information_peaks_near_b(self):
        info_near = item_information(a=1.0, b=0.0, c=0.2, theta=0.0)
        info_far = item_information(a=1.0, b=0.0, c=0.2, theta=5.0)
        self.assertGreater(info_near, info_far)


class ReportServicesTests(TestCase):
    def setUp(self):
        self.exam = Exam.objects.create(title="ENEM 2023", year=2023)
        self.topic_facil = Topic.objects.create(discipline=Discipline.MATEMATICA, name="Álgebra")
        self.topic_dificil = Topic.objects.create(discipline=Discipline.MATEMATICA, name="Geometria plana")
        self.user = User.objects.create_user(email="rep@example.com", password="s", nome="Rep")
        self.perfil = AlunoProfile.objects.create(user=self.user, escola=None)

    def _answer(self, question, correta, tempo_ms):
        simulado = Simulado.objects.create(
            aluno_profile=self.perfil, tipo=TipoSimulado.CUSTOMIZADO
        )
        Resposta.objects.create(
            simulado=simulado,
            aluno_profile=self.perfil,
            question=question,
            alternativa_escolhida="A" if correta else "B",
            correta=correta,
            tempo_gasto_ms=tempo_ms,
            respondida_em=timezone.now(),
        )

    def test_erros_por_assunto_counts_only_wrong_answers(self):
        q1 = _make_question(self.exam, 1, Discipline.MATEMATICA, topic=self.topic_facil)
        q2 = _make_question(self.exam, 2, Discipline.MATEMATICA, topic=self.topic_facil)
        self._answer(q1, correta=False, tempo_ms=1000)
        self._answer(q2, correta=True, tempo_ms=1000)

        erros = list(erros_por_assunto(self.perfil))
        self.assertEqual(len(erros), 1)
        self.assertEqual(erros[0]["total"], 1)

    def test_dominio_por_area_orders_ascending_by_theta(self):
        StudentAbility.objects.create(
            aluno_profile=self.perfil, discipline=Discipline.MATEMATICA, theta=1.5
        )
        StudentAbility.objects.create(
            aluno_profile=self.perfil, discipline=Discipline.LINGUAGENS, theta=-0.5
        )
        ranking = list(dominio_por_area(self.perfil))
        self.assertEqual(ranking[0].discipline, Discipline.LINGUAGENS)
        self.assertEqual(ranking[1].discipline, Discipline.MATEMATICA)

    def test_tempo_por_questao_vs_media_compares_to_global_average(self):
        q1 = _make_question(self.exam, 1, Discipline.MATEMATICA)
        self._answer(q1, correta=True, tempo_ms=5000)

        outro_user = User.objects.create_user(email="outro_rep@example.com", password="s", nome="Outro")
        outro_perfil = AlunoProfile.objects.create(user=outro_user, escola=None)
        outro_simulado = Simulado.objects.create(aluno_profile=outro_perfil, tipo=TipoSimulado.CUSTOMIZADO)
        Resposta.objects.create(
            simulado=outro_simulado, aluno_profile=outro_perfil, question=q1,
            alternativa_escolhida="A", correta=True, tempo_gasto_ms=1000, respondida_em=timezone.now(),
        )

        resultado = tempo_por_questao_vs_media(self.perfil)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["media_aluno_ms"], 5000)
        self.assertEqual(resultado[0]["media_global_ms"], 3000)  # média entre 5000 e 1000

    def test_impacto_erros_ranks_by_item_information(self):
        q_dentro = _make_question(self.exam, 1, Discipline.MATEMATICA, b=0.0)  # perto do theta=0
        q_longe = _make_question(self.exam, 2, Discipline.MATEMATICA, b=5.0)  # longe do theta=0
        self._answer(q_dentro, correta=False, tempo_ms=1000)
        self._answer(q_longe, correta=False, tempo_ms=1000)

        ranking = impacto_erros_no_theta(self.perfil)
        self.assertEqual(ranking[0]["resposta"].question, q_dentro)

    def test_turma_stats_aggregates_per_aluno(self):
        escola = Escola.objects.create(nome="Cursinho X")
        turma = Turma.objects.create(escola=escola, nome="1A", ano_letivo=2026)
        aluno_user = User.objects.create_user(email="turma_aluno@example.com", password="s", nome="A")
        aluno = AlunoProfile.objects.create(user=aluno_user, escola=escola, turma=turma)
        q1 = _make_question(self.exam, 1, Discipline.MATEMATICA)
        simulado = Simulado.objects.create(aluno_profile=aluno, tipo=TipoSimulado.CUSTOMIZADO)
        Resposta.objects.create(
            simulado=simulado, aluno_profile=aluno, question=q1,
            alternativa_escolhida="A", correta=True, tempo_gasto_ms=2000, respondida_em=timezone.now(),
        )

        resultado = turma_stats(turma)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["acertos"], 1)
        self.assertEqual(resultado[0]["percentual"], 100.0)


class ReportViewsTests(TestCase):
    def setUp(self):
        self.escola = Escola.objects.create(nome="Cursinho Y")
        self.turma = Turma.objects.create(escola=self.escola, nome="2A", ano_letivo=2026)
        self.prof_user = User.objects.create_user(email="prof_rep@example.com", password="s", nome="Prof")
        self.professor = Professor.objects.create(user=self.prof_user, escola=self.escola)
        self.aluno_user = User.objects.create_user(email="aluno_rep@example.com", password="s", nome="Aluno")
        self.aluno = AlunoProfile.objects.create(user=self.aluno_user, escola=self.escola, turma=self.turma)

    def test_aluno_can_view_own_report(self):
        client = Client()
        client.login(email="aluno_rep@example.com", password="s")
        client.get(reverse("accounts:select_context"))
        response = client.get(reverse("reports:student_report"))
        self.assertEqual(response.status_code, 200)

    def test_professor_can_view_turma_stats(self):
        client = Client()
        client.login(email="prof_rep@example.com", password="s")
        client.get(reverse("accounts:select_context"))
        response = client.get(reverse("reports:turma_stats", args=[self.turma.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aluno")

    def test_professor_of_another_escola_cannot_view_turma(self):
        outra_escola = Escola.objects.create(nome="Cursinho Z")
        outro_prof_user = User.objects.create_user(email="prof_rep_b@example.com", password="s", nome="B")
        Professor.objects.create(user=outro_prof_user, escola=outra_escola)

        client = Client()
        client.login(email="prof_rep_b@example.com", password="s")
        client.get(reverse("accounts:select_context"))
        response = client.get(reverse("reports:turma_stats", args=[self.turma.id]))
        self.assertEqual(response.status_code, 404)
