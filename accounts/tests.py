from django.test import Client, TestCase
from django.urls import reverse

from .context import (
    AlunoContext,
    ProfessorContext,
    available_contexts,
    current_aluno_profile,
    get_active_context,
    scoped_alunos,
    set_active_context,
)
from .models import AlunoProfile, Escola, Professor, Turma, User


class TenantIsolationTests(TestCase):
    """Prova que o isolamento multi-tenant é garantido pela aplicação (Django
    conecta direto no Postgres, sem RLS de PostgREST cobrindo essa conexão)."""

    def setUp(self):
        self.escola_a = Escola.objects.create(nome="Cursinho A")
        self.escola_b = Escola.objects.create(nome="Cursinho B")

        self.prof_a_user = User.objects.create_user(
            email="prof_a@example.com", password="senha123", nome="Prof A"
        )
        self.prof_a = Professor.objects.create(user=self.prof_a_user, escola=self.escola_a)

        self.prof_b_user = User.objects.create_user(
            email="prof_b@example.com", password="senha123", nome="Prof B"
        )
        self.prof_b = Professor.objects.create(user=self.prof_b_user, escola=self.escola_b)

        self.aluno_a_user = User.objects.create_user(
            email="aluno_a@example.com", password="senha123", nome="Aluno A"
        )
        self.aluno_a = AlunoProfile.objects.create(user=self.aluno_a_user, escola=self.escola_a)

        self.aluno_b_user = User.objects.create_user(
            email="aluno_b@example.com", password="senha123", nome="Aluno B"
        )
        self.aluno_b = AlunoProfile.objects.create(user=self.aluno_b_user, escola=self.escola_b)

    def test_professor_does_not_see_alunos_of_another_escola(self):
        context_a = ProfessorContext(
            professor_id=self.prof_a.id, escola_id=self.escola_a.id, label="A"
        )
        alunos_visiveis = scoped_alunos(context_a)
        self.assertIn(self.aluno_a, alunos_visiveis)
        self.assertNotIn(self.aluno_b, alunos_visiveis)

    def test_professor_cannot_scope_aluno_context(self):
        context = AlunoContext(aluno_profile_id=self.aluno_a.id, label="x")
        with self.assertRaises(ValueError):
            scoped_alunos(context)

    def test_individual_and_school_context_of_same_person_are_isolated(self):
        """Mesma pessoa (mesmo e-mail) tem uma conta individual e uma vinculada
        a uma escola — os dois espaços de dados não podem se misturar."""
        user = User.objects.create_user(
            email="duplo@example.com", password="senha123", nome="Duplo Contexto"
        )
        individual = AlunoProfile.objects.create(user=user, escola=None)
        na_escola = AlunoProfile.objects.create(user=user, escola=self.escola_a)

        contexts = available_contexts(user)
        self.assertEqual(len(contexts), 2)

        request = self._FakeRequest(user=user)
        set_active_context(request, self._as_aluno_context(individual))
        self.assertEqual(current_aluno_profile(request), individual)
        self.assertNotEqual(current_aluno_profile(request), na_escola)

        request2 = self._FakeRequest(user=user)
        set_active_context(request2, self._as_aluno_context(na_escola))
        self.assertEqual(current_aluno_profile(request2), na_escola)
        self.assertNotEqual(current_aluno_profile(request2), individual)

    def test_cannot_create_two_individual_profiles_for_same_user(self):
        from django.db import IntegrityError, transaction

        user = User.objects.create_user(
            email="unico@example.com", password="senha123", nome="Único"
        )
        AlunoProfile.objects.create(user=user, escola=None)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AlunoProfile.objects.create(user=user, escola=None)

    @staticmethod
    def _as_aluno_context(perfil):
        return AlunoContext(
            aluno_profile_id=perfil.id,
            escola_id=perfil.escola_id,
            label="test",
        )

    class _FakeRequest:
        """dict já cobre a API de sessão usada por context.py (getitem/get/pop)."""

        def __init__(self, user):
            self.session = {}
            self.user = user


class LoginContextSelectionTests(TestCase):
    def setUp(self):
        self.escola = Escola.objects.create(nome="Cursinho A")
        self.turma = Turma.objects.create(escola=self.escola, nome="3A", ano_letivo=2026)

    def test_login_with_single_context_auto_selects(self):
        user = User.objects.create_user(
            email="unico@example.com", password="senha123", nome="Único"
        )
        AlunoProfile.objects.create(user=user, escola=None)

        client = Client()
        client.login(email="unico@example.com", password="senha123")
        response = client.get(reverse("accounts:select_context"))
        self.assertEqual(response.status_code, 302)

    def test_login_with_multiple_contexts_shows_selection_screen(self):
        user = User.objects.create_user(
            email="duplo@example.com", password="senha123", nome="Duplo"
        )
        AlunoProfile.objects.create(user=user, escola=None)
        AlunoProfile.objects.create(user=user, escola=self.escola, turma=self.turma)

        client = Client()
        client.login(email="duplo@example.com", password="senha123")
        response = client.get(reverse("accounts:select_context"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aluno individual")
        self.assertContains(response, "Cursinho A")

    def test_selecting_context_sets_session(self):
        user = User.objects.create_user(
            email="duplo2@example.com", password="senha123", nome="Duplo"
        )
        AlunoProfile.objects.create(user=user, escola=None)
        AlunoProfile.objects.create(user=user, escola=self.escola, turma=self.turma)

        client = Client()
        client.login(email="duplo2@example.com", password="senha123")
        response = client.post(reverse("accounts:select_context"), {"context_index": "1"})
        self.assertEqual(response.status_code, 302)
        session = client.session
        self.assertEqual(session["active_context"]["kind"], "aluno")
        self.assertEqual(session["active_context"]["escola_id"], self.escola.id)


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reset@example.com", password="senhaAntiga123", nome="Reset Teste"
        )

    def test_full_reset_flow_changes_password(self):
        from django.core import mail

        client = Client()
        response = client.post(reverse("accounts:password_reset"), {"email": "reset@example.com"})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        # extrai uid/token do link no corpo do e-mail
        from urllib.parse import urlparse

        body = mail.outbox[0].body
        link = next(line for line in body.splitlines() if "/senha/resetar/confirmar/" in line)
        path = urlparse(link).path

        response = client.get(path, follow=True)
        self.assertEqual(response.status_code, 200)
        confirm_url = response.redirect_chain[-1][0]

        response = client.post(
            confirm_url,
            {"new_password1": "senhaNova456", "new_password2": "senhaNova456"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("senhaNova456"))

    def test_reset_with_unknown_email_does_not_error(self):
        client = Client()
        response = client.post(
            reverse("accounts:password_reset"), {"email": "naoexiste@example.com"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
