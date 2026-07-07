from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import AlunoProfile, Escola, Professor, Turma, User

from .models import (
    CorrectionMode,
    EssayAssignment,
    EssayPrompt,
    EssaySubmission,
    StatusSubmissao,
    SubmissionType,
)
from .services import correct_essay, grade_essay_manually, process_pending_essay_submissions

MOCKED_GEMINI_RESPONSE = {
    "c1": 160,
    "c2": 160,
    "c3": 120,
    "c4": 160,
    "c5": 120,
    "feedback": {
        "c1": "Boa norma culta.",
        "c2": "Compreendeu bem a proposta.",
        "c3": "Argumentos razoáveis.",
        "c4": "Boa coesão.",
        "c5": "Proposta de intervenção incompleta.",
    },
}


class CorrectEssayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="aluno@example.com", password="senha123", nome="Aluno"
        )
        self.perfil = AlunoProfile.objects.create(user=self.user, escola=None)
        self.prompt = EssayPrompt.objects.create(titulo="Tema teste", texto_motivador="Motivador")

    @patch("redacao.services.generate_json", return_value=MOCKED_GEMINI_RESPONSE)
    def test_correct_essay_updates_submission(self, mock_generate):
        submission = EssaySubmission.objects.create(
            aluno_profile=self.perfil, prompt=self.prompt, texto="Texto da redação de teste."
        )
        correct_essay(submission)

        submission.refresh_from_db()
        self.assertEqual(submission.status, StatusSubmissao.CORRECTED)
        self.assertEqual(submission.nota_final, 720)
        self.assertEqual(submission.notas_competencias["c1"], 160)
        mock_generate.assert_called_once()

    @patch("redacao.services.generate_json", side_effect=RuntimeError("API indisponível"))
    def test_correct_essay_failure_is_not_silently_swallowed(self, mock_generate):
        submission = EssaySubmission.objects.create(
            aluno_profile=self.perfil, texto="Texto de teste."
        )
        with self.assertRaises(RuntimeError):
            correct_essay(submission)


class ProcessPendingQueueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="aluno2@example.com", password="senha123", nome="Aluno 2"
        )
        self.perfil = AlunoProfile.objects.create(user=self.user, escola=None)

    @patch("redacao.services.generate_json", return_value=MOCKED_GEMINI_RESPONSE)
    def test_process_pending_corrects_and_counts(self, mock_generate):
        EssaySubmission.objects.create(aluno_profile=self.perfil, texto="Redação 1")
        EssaySubmission.objects.create(aluno_profile=self.perfil, texto="Redação 2")

        resumo = process_pending_essay_submissions()

        self.assertEqual(resumo["processadas"], 2)
        self.assertEqual(resumo["falhas"], 0)
        self.assertEqual(
            EssaySubmission.objects.filter(status=StatusSubmissao.CORRECTED).count(), 2
        )

    @patch("redacao.services.generate_json", side_effect=RuntimeError("falhou"))
    def test_process_pending_marks_failures_without_raising(self, mock_generate):
        EssaySubmission.objects.create(aluno_profile=self.perfil, texto="Redação com falha")

        resumo = process_pending_essay_submissions()

        self.assertEqual(resumo["falhas"], 1)
        self.assertEqual(
            EssaySubmission.objects.filter(status=StatusSubmissao.FAILED).count(), 1
        )


class EssaySubmitFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="aluno3@example.com", password="senha123", nome="Aluno 3"
        )
        AlunoProfile.objects.create(user=self.user, escola=None)

    def _login(self):
        client = Client()
        client.login(email="aluno3@example.com", password="senha123")
        client.get(reverse("accounts:select_context"))
        return client

    def test_submit_essay_creates_pending_submission(self):
        client = self._login()
        response = client.post(reverse("redacao:submit"), {"texto": "Minha redação de teste."})
        self.assertEqual(response.status_code, 302)
        submission = EssaySubmission.objects.get()
        self.assertEqual(submission.status, StatusSubmissao.PENDING)
        self.assertEqual(submission.texto, "Minha redação de teste.")

    def test_aluno_cannot_see_essay_of_another_aluno(self):
        outro_user = User.objects.create_user(
            email="outro3@example.com", password="senha123", nome="Outro"
        )
        outro_perfil = AlunoProfile.objects.create(user=outro_user, escola=None)
        submission = EssaySubmission.objects.create(aluno_profile=outro_perfil, texto="Privada")

        client = self._login()
        response = client.get(reverse("redacao:resultado", args=[submission.id]))
        self.assertEqual(response.status_code, 404)


class EssayAssignmentTests(TestCase):
    def setUp(self):
        self.escola = Escola.objects.create(nome="Cursinho A")
        self.turma = Turma.objects.create(escola=self.escola, nome="3A", ano_letivo=2026)
        self.prof_user = User.objects.create_user(
            email="prof_redacao@example.com", password="senha123", nome="Prof"
        )
        self.professor = Professor.objects.create(user=self.prof_user, escola=self.escola)
        self.aluno_user = User.objects.create_user(
            email="aluno_atrib@example.com", password="senha123", nome="Aluno"
        )
        self.aluno = AlunoProfile.objects.create(
            user=self.aluno_user, escola=self.escola, turma=self.turma
        )

    def _login_aluno(self):
        client = Client()
        client.login(email="aluno_atrib@example.com", password="senha123")
        client.get(reverse("accounts:select_context"))
        return client

    def _login_professor(self):
        client = Client()
        client.login(email="prof_redacao@example.com", password="senha123")
        client.get(reverse("accounts:select_context"))
        return client

    @patch(
        "redacao.services.generate_json",
        return_value={"tema": "Tema gerado pela IA", "texto_motivador": "Motivador gerado"},
    )
    def test_professor_creates_assignment_with_ai_generated_theme(self, mock_generate):
        client = self._login_professor()
        response = client.post(
            reverse("redacao:assignment_create"),
            {
                "gerar_tema_ia": "1",
                "correction_mode": CorrectionMode.MANUAL,
                "turma_id": self.turma.id,
                "alunos": [],
            },
        )
        self.assertEqual(response.status_code, 302)
        assignment = EssayAssignment.objects.get()
        self.assertEqual(assignment.tema, "Tema gerado pela IA")
        self.assertTrue(assignment.tema_gerado_por_ia)
        mock_generate.assert_called_once()

    def test_aluno_photo_submission_allowed_when_manual(self):
        assignment = EssayAssignment.objects.create(
            professor=self.professor,
            escola=self.escola,
            tema="Tema",
            correction_mode=CorrectionMode.MANUAL,
            turma=self.turma,
        )
        client = self._login_aluno()
        foto = SimpleUploadedFile("redacao.jpg", b"fake-image-bytes", content_type="image/jpeg")
        response = client.post(
            reverse("redacao:assignment_submit", args=[assignment.id]),
            {"submission_type": "photo", "foto": foto},
        )
        self.assertEqual(response.status_code, 302)
        submission = EssaySubmission.objects.get(assignment=assignment)
        self.assertEqual(submission.submission_type, SubmissionType.PHOTO)
        self.assertEqual(submission.correction_source, "manual")

    def test_ai_assignment_coerces_photo_submission_to_text(self):
        assignment = EssayAssignment.objects.create(
            professor=self.professor,
            escola=self.escola,
            tema="Tema",
            correction_mode=CorrectionMode.AI,
            turma=self.turma,
        )
        client = self._login_aluno()
        foto = SimpleUploadedFile("redacao.jpg", b"fake-image-bytes", content_type="image/jpeg")
        client.post(
            reverse("redacao:assignment_submit", args=[assignment.id]),
            {"submission_type": "photo", "texto": "Texto digitado", "foto": foto},
        )
        submission = EssaySubmission.objects.get(assignment=assignment)
        self.assertEqual(submission.submission_type, SubmissionType.TEXT)
        self.assertEqual(submission.correction_source, "ai")

    def test_professor_grades_essay_manually(self):
        submission = EssaySubmission.objects.create(
            aluno_profile=self.aluno,
            assignment=EssayAssignment.objects.create(
                professor=self.professor,
                escola=self.escola,
                tema="Tema",
                correction_mode=CorrectionMode.MANUAL,
            ),
            texto="Redação do aluno",
            correction_source="manual",
        )
        notas = {"c1": 120, "c2": 120, "c3": 120, "c4": 120, "c5": 120}
        feedback = {c: "" for c in notas}
        grade_essay_manually(submission, self.professor, notas, feedback)

        submission.refresh_from_db()
        self.assertEqual(submission.status, StatusSubmissao.CORRECTED)
        self.assertEqual(submission.nota_final, 600)
        self.assertEqual(submission.corrected_by, self.professor)

    def test_manual_submissions_are_not_picked_up_by_ai_queue(self):
        EssaySubmission.objects.create(
            aluno_profile=self.aluno, texto="Redação manual", correction_source="manual"
        )
        resumo = process_pending_essay_submissions()
        self.assertEqual(resumo["processadas"], 0)

    def test_professor_of_another_escola_cannot_grade(self):
        submission = EssaySubmission.objects.create(
            aluno_profile=self.aluno,
            assignment=EssayAssignment.objects.create(
                professor=self.professor,
                escola=self.escola,
                tema="Tema",
                correction_mode=CorrectionMode.MANUAL,
            ),
            texto="Redação",
            correction_source="manual",
        )
        outra_escola = Escola.objects.create(nome="Cursinho B")
        outro_prof_user = User.objects.create_user(
            email="prof_b_redacao@example.com", password="senha123", nome="Prof B"
        )
        Professor.objects.create(user=outro_prof_user, escola=outra_escola)

        client = Client()
        client.login(email="prof_b_redacao@example.com", password="senha123")
        client.get(reverse("accounts:select_context"))
        response = client.get(reverse("redacao:grade", args=[submission.id]))
        self.assertEqual(response.status_code, 404)
