from unittest.mock import patch

from django.core.management import call_command
from django.db.models import F
from django.test import TestCase
from django.utils import timezone

from accounts.models import AlunoProfile, User
from exams.models import Alternative, Discipline, Exam, Question, Topic
from simulados.models import Resposta, Simulado, TipoSimulado

from .models import DifficultySource, ItemParameters, StudentAbility
from .services import recalibrate_tri


def _make_question(exam, index, discipline, correct="A", n_alt=5):
    q = Question.objects.create(
        exam=exam,
        external_index=index,
        discipline=discipline,
        context=f"Contexto {index}",
        alternatives_introduction="Assinale a correta.",
        correct_alternative=correct,
    )
    for letter in "ABCDE"[:n_alt]:
        Alternative.objects.create(question=q, letter=letter, text=f"Alt {letter}", is_correct=(letter == correct))
    return q


class ClassifyQuestionsLlmTests(TestCase):
    def setUp(self):
        self.exam = Exam.objects.create(title="ENEM 2023", year=2023)
        self.topic = Topic.objects.create(discipline=Discipline.MATEMATICA, name="Álgebra")
        self.question = _make_question(self.exam, 1, Discipline.MATEMATICA)

    @patch("irt.management.commands.classify_questions_llm.generate_json")
    def test_classify_creates_item_parameters(self, mock_generate):
        mock_generate.return_value = {
            "classificacoes": [{"id": self.question.id, "topic": "Álgebra", "difficulty_b": 0.75}]
        }
        call_command("classify_questions_llm")

        self.question.refresh_from_db()
        params = ItemParameters.objects.get(question=self.question)
        self.assertEqual(params.b, 0.75)
        self.assertEqual(params.a, 1.0)
        self.assertAlmostEqual(params.c, 0.2)
        self.assertEqual(params.difficulty_source, DifficultySource.LLM_ESTIMATE)
        self.assertEqual(self.question.topic, self.topic)

    @patch("irt.management.commands.classify_questions_llm.generate_json")
    def test_classify_ignores_topic_outside_curated_taxonomy(self, mock_generate):
        mock_generate.return_value = {
            "classificacoes": [
                {"id": self.question.id, "topic": "Assunto Inventado Pelo LLM", "difficulty_b": -1.0}
            ]
        }
        call_command("classify_questions_llm")

        self.question.refresh_from_db()
        self.assertIsNone(self.question.topic)
        params = ItemParameters.objects.get(question=self.question)
        self.assertEqual(params.b, -1.0)

    @patch("irt.management.commands.classify_questions_llm.generate_json")
    def test_classify_is_idempotent(self, mock_generate):
        mock_generate.return_value = {
            "classificacoes": [{"id": self.question.id, "topic": "Álgebra", "difficulty_b": 0.0}]
        }
        call_command("classify_questions_llm")
        call_command("classify_questions_llm")

        self.assertEqual(ItemParameters.objects.count(), 1)
        mock_generate.assert_called_once()


class RecalibrateTriTests(TestCase):
    """Spike de integração com girth: gera respostas sintéticas com uma
    estrutura de habilidade real (via numpy, seed fixa) e confere que a
    recalibração roda de ponta a ponta sem erro e produz saída plausível."""

    def setUp(self):
        import numpy as np

        rng = np.random.default_rng(42)
        self.exam = Exam.objects.create(title="ENEM 2023", year=2023)

        self.itens_com_respondentes = []
        for i in range(1, 6):
            q = _make_question(self.exam, i, Discipline.MATEMATICA)
            ip = ItemParameters.objects.create(
                question=q, a=1.0, b=float(rng.normal(0, 1)), c=0.2,
                difficulty_source=DifficultySource.LLM_ESTIMATE,
            )
            self.itens_com_respondentes.append((q, ip))

        # item extra com poucos respondentes — não deve ser recalibrado
        self.item_poucos_respondentes_q = _make_question(self.exam, 6, Discipline.MATEMATICA)
        self.item_poucos_respondentes_ip = ItemParameters.objects.create(
            question=self.item_poucos_respondentes_q, a=1.0, b=0.0, c=0.2,
            difficulty_source=DifficultySource.LLM_ESTIMATE,
        )

        thetas = rng.normal(0, 1, size=30)
        for aluno_idx, theta in enumerate(thetas):
            user = User.objects.create_user(
                email=f"calib_{aluno_idx}@example.com", password="s", nome=f"Aluno {aluno_idx}"
            )
            perfil = AlunoProfile.objects.create(user=user, escola=None)
            simulado = Simulado.objects.create(aluno_profile=perfil, tipo=TipoSimulado.CUSTOMIZADO)
            for q, ip in self.itens_com_respondentes:
                p_correta = ip.c + (1 - ip.c) / (1 + np.exp(-(theta - ip.b)))
                correta = bool(rng.random() < p_correta)
                Resposta.objects.create(
                    simulado=simulado, aluno_profile=perfil, question=q,
                    alternativa_escolhida="A" if correta else "B", correta=correta,
                    respondida_em=timezone.now(),
                )
                ItemParameters.objects.filter(pk=ip.pk).update(
                    respondent_count=F("respondent_count") + 1
                )

    def test_recalibrate_updates_items_with_enough_respondents(self):
        for _, ip in self.itens_com_respondentes:
            ip.respondent_count = 30
            ip.save(update_fields=["respondent_count"])
        self.item_poucos_respondentes_ip.respondent_count = 2
        self.item_poucos_respondentes_ip.save(update_fields=["respondent_count"])

        resumo = recalibrate_tri(min_respondents=10, discipline=Discipline.MATEMATICA)

        self.assertEqual(resumo["itens_calibrados"], 5)
        self.assertEqual(resumo["alunos_reestimados"], 30)

        for _, ip in self.itens_com_respondentes:
            ip.refresh_from_db()
            self.assertEqual(ip.difficulty_source, DifficultySource.CALIBRATED)
            self.assertIsNotNone(ip.last_calibrated_at)

        self.item_poucos_respondentes_ip.refresh_from_db()
        self.assertEqual(
            self.item_poucos_respondentes_ip.difficulty_source, DifficultySource.LLM_ESTIMATE
        )

        self.assertTrue(StudentAbility.objects.filter(method="em_calibrated").exists())

    def test_recalibrate_with_no_qualifying_items_is_a_noop(self):
        resumo = recalibrate_tri(min_respondents=99999)
        self.assertEqual(resumo["itens_calibrados"], 0)
        self.assertEqual(resumo["alunos_reestimados"], 0)
