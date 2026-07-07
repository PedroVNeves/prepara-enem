from django.db import models

from accounts.models import AlunoProfile, Escola, Professor, Turma
from core.models import TimeStampedModel


class StatusSubmissao(models.TextChoices):
    PENDING = "pending", "Aguardando correção"
    PROCESSING = "processing", "Em correção"
    CORRECTED = "corrected", "Corrigida"
    FAILED = "failed", "Falhou"


class CorrectionMode(models.TextChoices):
    MANUAL = "manual", "Correção manual pelo professor"
    AI = "ai", "Correção por IA"


class SubmissionType(models.TextChoices):
    TEXT = "text", "Texto digitado"
    PHOTO = "photo", "Foto"


class EssayPrompt(TimeStampedModel):
    """Banco de temas para prática livre do aluno individual (fora de
    qualquer atribuição de escola — ver EssayAssignment abaixo)."""

    titulo = models.CharField(max_length=255)
    texto_motivador = models.TextField(blank=True)
    ano = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.titulo


class EssayAssignment(TimeStampedModel):
    """Redação atribuída por um professor a uma turma e/ou alunos
    específicos. Tema pode ser gerado por IA (llm.client.generate_json)."""

    professor = models.ForeignKey(
        Professor, on_delete=models.CASCADE, related_name="essay_assignments"
    )
    escola = models.ForeignKey(Escola, on_delete=models.CASCADE, related_name="essay_assignments")
    tema = models.CharField(max_length=255)
    texto_motivador = models.TextField(blank=True)
    tema_gerado_por_ia = models.BooleanField(default=False)
    correction_mode = models.CharField(max_length=10, choices=CorrectionMode.choices)
    turma = models.ForeignKey(
        Turma, on_delete=models.SET_NULL, related_name="essay_assignments", null=True, blank=True
    )
    alunos = models.ManyToManyField(AlunoProfile, related_name="essay_assignments", blank=True)
    prazo = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.tema} — {self.escola}"


class EssaySubmission(TimeStampedModel):
    aluno_profile = models.ForeignKey(
        AlunoProfile, on_delete=models.CASCADE, related_name="redacoes"
    )
    prompt = models.ForeignKey(
        EssayPrompt, on_delete=models.SET_NULL, related_name="submissoes", null=True, blank=True
    )
    assignment = models.ForeignKey(
        EssayAssignment,
        on_delete=models.SET_NULL,
        related_name="submissoes",
        null=True,
        blank=True,
    )
    submission_type = models.CharField(
        max_length=10, choices=SubmissionType.choices, default=SubmissionType.TEXT
    )
    texto = models.TextField(blank=True)
    foto = models.FileField(upload_to="redacoes/%Y/%m/", null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=StatusSubmissao.choices, default=StatusSubmissao.PENDING
    )
    correction_source = models.CharField(max_length=10, default="ai")
    corrected_by = models.ForeignKey(
        Professor,
        on_delete=models.SET_NULL,
        related_name="redacoes_corrigidas",
        null=True,
        blank=True,
    )
    notas_competencias = models.JSONField(null=True, blank=True)
    nota_final = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.JSONField(null=True, blank=True)
    llm_model_used = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Redação de {self.aluno_profile} — {self.status}"
