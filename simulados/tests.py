from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import AlunoProfile, Escola, Professor, Turma, User
from exams.models import Alternative, Discipline, Exam, Question
from irt.models import DifficultySource, ItemParameters, StudentAbility

from .models import Resposta, SimuladoAssignment, StatusSimulado, TipoSimulado
from .services import (
    create_simulado_assignment,
    finalize_simulado,
    select_by_difficulty_band,
    select_fixed_exam_questions,
    start_custom_simulado,
    start_fixed_simulado,
)


def _make_question(exam, index, discipline, language=None, correct="A"):
    q = Question.objects.create(
        exam=exam,
        external_index=index,
        discipline=discipline,
        language=language,
        context=f"Contexto da questão {index}",
        alternatives_introduction="Assinale a alternativa correta.",
        correct_alternative=correct,
    )
    for letter in "ABCDE":
        Alternative.objects.create(
            question=q, letter=letter, text=f"Alternativa {letter}", is_correct=(letter == correct)
        )
    return q


def _make_classified_question(exam, index, discipline, b, correct="A"):
    q = _make_question(exam, index, discipline, correct=correct)
    ItemParameters.objects.create(
        question=q, a=1.0, b=b, c=0.2, difficulty_source=DifficultySource.LLM_ESTIMATE
    )
    return q


class SelectByDifficultyBandTests(TestCase):
    def setUp(self):
        self.exam = Exam.objects.create(title="ENEM 2023", year=2023)
        self.user = User.objects.create_user(
            email="banda@example.com", password="senha123", nome="Aluno Banda"
        )
        self.perfil = AlunoProfile.objects.create(user=self.user, escola=None)

    def test_creates_student_ability_with_default_theta(self):
        _make_classified_question(self.exam, 1, Discipline.MATEMATICA, b=0.0)
        self.assertFalse(
            StudentAbility.objects.filter(
                aluno_profile=self.perfil, discipline=Discipline.MATEMATICA
            ).exists()
        )
        select_by_difficulty_band(self.perfil, Discipline.MATEMATICA, quantidade=1)
        habilidade = StudentAbility.objects.get(
            aluno_profile=self.perfil, discipline=Discipline.MATEMATICA
        )
        self.assertEqual(habilidade.theta, 0.0)

    def test_only_selects_classified_questions_of_the_right_discipline(self):
        _make_classified_question(self.exam, 1, Discipline.MATEMATICA, b=0.0)
        _make_question(self.exam, 2, Discipline.MATEMATICA)  # sem ItemParameters
        _make_classified_question(self.exam, 3, Discipline.LINGUAGENS, b=0.0)

        selecionadas = select_by_difficulty_band(self.perfil, Discipline.MATEMATICA, quantidade=10)
        self.assertEqual(len(selecionadas), 1)
        self.assertEqual(selecionadas[0].external_index, 1)

    def test_excludes_already_answered_questions(self):
        q1 = _make_classified_question(self.exam, 1, Discipline.MATEMATICA, b=0.0)
        _make_classified_question(self.exam, 2, Discipline.MATEMATICA, b=0.0)
        simulado = start_fixed_simulado(self.perfil, self.exam)
        Resposta.objects.create(
            simulado=simulado, aluno_profile=self.perfil, question=q1, alternativa_escolhida="A"
        )

        selecionadas = select_by_difficulty_band(self.perfil, Discipline.MATEMATICA, quantidade=10)
        self.assertNotIn(q1, selecionadas)

    def test_start_custom_simulado_creates_simulado_with_questions(self):
        for i in range(1, 6):
            _make_classified_question(self.exam, i, Discipline.MATEMATICA, b=0.0)

        simulado = start_custom_simulado(self.perfil, Discipline.MATEMATICA, quantidade=3)
        self.assertEqual(simulado.tipo, TipoSimulado.CUSTOMIZADO)
        self.assertEqual(simulado.perguntas.count(), 3)


class SimuladoAssignmentTests(TestCase):
    def setUp(self):
        self.exam = Exam.objects.create(title="ENEM 2023", year=2023)
        for i in range(1, 6):
            _make_classified_question(self.exam, i, Discipline.MATEMATICA, b=0.0)

        self.escola = Escola.objects.create(nome="Cursinho A")
        self.turma = Turma.objects.create(escola=self.escola, nome="3A", ano_letivo=2026)
        self.prof_user = User.objects.create_user(
            email="prof@example.com", password="senha123", nome="Prof"
        )
        self.professor = Professor.objects.create(user=self.prof_user, escola=self.escola)

        self.aluno1_user = User.objects.create_user(
            email="aluno1@example.com", password="senha123", nome="Aluno 1"
        )
        self.aluno1 = AlunoProfile.objects.create(
            user=self.aluno1_user, escola=self.escola, turma=self.turma
        )
        self.aluno2_user = User.objects.create_user(
            email="aluno2@example.com", password="senha123", nome="Aluno 2"
        )
        self.aluno2 = AlunoProfile.objects.create(user=self.aluno2_user, escola=self.escola)

    def test_creates_simulado_for_every_aluno_in_turma(self):
        assignment = create_simulado_assignment(
            professor=self.professor,
            escola=self.escola,
            config={"discipline": Discipline.MATEMATICA, "quantidade": 3},
            turma=self.turma,
        )
        self.assertEqual(assignment.simulados.count(), 1)
        self.assertEqual(assignment.simulados.first().aluno_profile, self.aluno1)

    def test_creates_simulado_for_explicit_alunos_beyond_turma(self):
        assignment = create_simulado_assignment(
            professor=self.professor,
            escola=self.escola,
            config={"discipline": Discipline.MATEMATICA, "quantidade": 3},
            turma=self.turma,
            alunos=[self.aluno2],
        )
        alunos_com_simulado = {s.aluno_profile for s in assignment.simulados.all()}
        self.assertEqual(alunos_com_simulado, {self.aluno1, self.aluno2})

    def test_professor_of_another_escola_cannot_see_assignment_results(self):
        assignment = create_simulado_assignment(
            professor=self.professor,
            escola=self.escola,
            config={"discipline": Discipline.MATEMATICA, "quantidade": 3},
            turma=self.turma,
        )
        outra_escola = Escola.objects.create(nome="Cursinho B")
        outro_prof_user = User.objects.create_user(
            email="prof_b@example.com", password="senha123", nome="Prof B"
        )
        Professor.objects.create(user=outro_prof_user, escola=outra_escola)

        client = Client()
        client.login(email="prof_b@example.com", password="senha123")
        client.get(reverse("accounts:select_context"))
        response = client.get(reverse("simulados:assignment_results", args=[assignment.id]))
        self.assertEqual(response.status_code, 404)


class SelectFixedExamQuestionsTests(TestCase):
    def test_dedupes_language_variants_preferring_ingles(self):
        exam = Exam.objects.create(title="ENEM 2023", year=2023)
        _make_question(exam, 1, Discipline.LINGUAGENS, language="espanhol")
        _make_question(exam, 1, Discipline.LINGUAGENS, language="ingles")
        _make_question(exam, 2, Discipline.MATEMATICA)

        selected = select_fixed_exam_questions(exam)
        self.assertEqual(len(selected), 2)
        q1 = next(q for q in selected if q.external_index == 1)
        self.assertEqual(q1.language, "ingles")


class SimuladoFlowTests(TestCase):
    def setUp(self):
        self.exam = Exam.objects.create(title="ENEM 2023", year=2023)
        self.questions = [
            _make_question(self.exam, i, Discipline.MATEMATICA, correct="A") for i in range(1, 4)
        ]
        self.user = User.objects.create_user(
            email="aluno@example.com", password="senha123", nome="Aluno Teste"
        )
        self.perfil = AlunoProfile.objects.create(user=self.user, escola=None)

    def _login_and_select_context(self):
        client = Client()
        client.login(email="aluno@example.com", password="senha123")
        client.get(reverse("accounts:select_context"))  # auto-seleciona único contexto
        return client

    def test_full_flow_answer_all_questions_and_finalize(self):
        client = self._login_and_select_context()

        response = client.post(reverse("simulados:start"), {"exam_id": self.exam.id})
        self.assertEqual(response.status_code, 302)
        simulado_id = int(response.url.split("/")[3])

        for ordem in range(1, 4):
            response = client.post(
                reverse("simulados:questao", args=[simulado_id, ordem]),
                {"alternativa": "A", "tempo_gasto_ms": "1500"},
            )
            self.assertEqual(response.status_code, 302)

        self.assertEqual(Resposta.objects.filter(simulado_id=simulado_id).count(), 3)

        response = client.get(reverse("simulados:resultado", args=[simulado_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "3 / 3")

    def test_aluno_cannot_access_simulado_of_another_aluno(self):
        outro_user = User.objects.create_user(
            email="outro@example.com", password="senha123", nome="Outro"
        )
        outro_perfil = AlunoProfile.objects.create(user=outro_user, escola=None)
        simulado = start_fixed_simulado(outro_perfil, self.exam)

        client = self._login_and_select_context()
        response = client.get(reverse("simulados:questao", args=[simulado.id, 1]))
        self.assertEqual(response.status_code, 404)

    def test_finalize_computes_percentual(self):
        simulado = start_fixed_simulado(self.perfil, self.exam)
        for q in self.questions[:2]:
            Resposta.objects.create(
                simulado=simulado,
                aluno_profile=self.perfil,
                question=q,
                alternativa_escolhida="A",
                correta=True,
            )
        resumo = finalize_simulado(simulado)
        self.assertEqual(resumo["acertos"], 2)
        self.assertEqual(resumo["total_questoes"], 3)
        self.assertAlmostEqual(resumo["percentual"], 66.7, places=1)
        simulado.refresh_from_db()
        self.assertEqual(simulado.status, StatusSimulado.FINALIZADO)
