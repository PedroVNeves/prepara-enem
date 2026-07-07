from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser precisa de is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser precisa de is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Identidade de login. Não carrega tipo de perfil — ver Professor/AlunoProfile
    para os contextos de uso (uma pessoa pode ter mais de um contexto)."""

    email = models.EmailField(unique=True)
    nome = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    def __str__(self):
        return self.email


class Escola(TimeStampedModel):
    """Entidade organizacional. Não é login — professores (staff da escola)
    é que autenticam, cada um com seu próprio User."""

    nome = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=20, blank=True)
    # Reservado para o modelo de negócio futuro (escola escolhe plano por
    # quantidade de alunos) — sem integração de gateway de pagamento ainda.
    plano = models.ForeignKey(
        "billing.Plan", on_delete=models.SET_NULL, related_name="escolas", null=True, blank=True
    )

    def __str__(self):
        return self.nome


class Professor(TimeStampedModel):
    CARGO_ADMIN = "admin"
    CARGO_PROFESSOR = "professor"
    CARGO_CHOICES = [
        (CARGO_ADMIN, "Administrador"),
        (CARGO_PROFESSOR, "Professor"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="professor_set")
    escola = models.ForeignKey(Escola, on_delete=models.CASCADE, related_name="professores")
    cargo = models.CharField(max_length=20, choices=CARGO_CHOICES, default=CARGO_PROFESSOR)

    class Meta:
        unique_together = [("user", "escola")]

    def __str__(self):
        return f"{self.user.email} @ {self.escola.nome}"


class Turma(TimeStampedModel):
    escola = models.ForeignKey(Escola, on_delete=models.CASCADE, related_name="turmas")
    nome = models.CharField(max_length=255)
    ano_letivo = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.nome} ({self.ano_letivo}) — {self.escola.nome}"


class AlunoProfile(TimeStampedModel):
    """Um contexto de uso de aluno. Um User pode ter várias AlunoProfile:
    no máximo uma individual (escola=None) e uma por escola em que estuda."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="aluno_profiles")
    escola = models.ForeignKey(
        Escola, on_delete=models.CASCADE, related_name="alunos", null=True, blank=True
    )
    turma = models.ForeignKey(
        Turma, on_delete=models.SET_NULL, related_name="alunos", null=True, blank=True
    )
    data_nascimento = models.DateField(null=True, blank=True)
    # Reservado para o modelo de negócio futuro (aluno individual paga e
    # entra) — default True por ora, já que não há cobrança implementada.
    assinatura_ativa = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(escola__isnull=True),
                name="unique_individual_profile_per_user",
            ),
            models.UniqueConstraint(
                fields=["user", "escola"],
                name="unique_school_profile_per_user_per_escola",
            ),
        ]

    def __str__(self):
        contexto = self.escola.nome if self.escola_id else "individual"
        return f"{self.user.email} ({contexto})"
