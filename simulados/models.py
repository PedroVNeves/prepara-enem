from django.db import models

from accounts.models import AlunoProfile, Escola, Professor, Turma
from core.models import TimeStampedModel
from exams.models import Exam, Question


class TipoSimulado(models.TextChoices):
    FIXO = "fixo", "Prova histórica completa"
    CUSTOMIZADO = "customizado", "Simulado customizado"


class StatusSimulado(models.TextChoices):
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    FINALIZADO = "finalizado", "Finalizado"


class SimuladoAssignment(TimeStampedModel):
    """Simulado customizado atribuído por um professor a uma turma e/ou a
    alunos específicos — ao ser criado, dispara um Simulado individual por
    aluno-alvo (ver simulados/services.py: create_simulado_assignment)."""

    professor = models.ForeignKey(
        Professor, on_delete=models.CASCADE, related_name="simulado_assignments"
    )
    escola = models.ForeignKey(Escola, on_delete=models.CASCADE, related_name="simulado_assignments")
    config = models.JSONField(default=dict, blank=True)
    turma = models.ForeignKey(
        Turma, on_delete=models.SET_NULL, related_name="simulado_assignments", null=True, blank=True
    )
    alunos = models.ManyToManyField(AlunoProfile, related_name="simulado_assignments", blank=True)
    prazo = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Atribuição #{self.pk} — {self.escola}"


class Simulado(TimeStampedModel):
    aluno_profile = models.ForeignKey(
        AlunoProfile, on_delete=models.CASCADE, related_name="simulados"
    )
    tipo = models.CharField(max_length=20, choices=TipoSimulado.choices)
    exam = models.ForeignKey(
        Exam, on_delete=models.SET_NULL, related_name="simulados", null=True, blank=True
    )
    assignment = models.ForeignKey(
        SimuladoAssignment,
        on_delete=models.SET_NULL,
        related_name="simulados",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20, choices=StatusSimulado.choices, default=StatusSimulado.EM_ANDAMENTO
    )
    config = models.JSONField(default=dict, blank=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Simulado #{self.pk} ({self.tipo}) — {self.aluno_profile}"


class SimuladoQuestion(models.Model):
    simulado = models.ForeignKey(Simulado, on_delete=models.CASCADE, related_name="perguntas")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="+")
    ordem = models.PositiveIntegerField()

    class Meta:
        unique_together = [("simulado", "question")]
        ordering = ["simulado", "ordem"]

    def __str__(self):
        return f"{self.simulado} — questão {self.ordem}"


class Resposta(models.Model):
    simulado = models.ForeignKey(Simulado, on_delete=models.CASCADE, related_name="respostas")
    aluno_profile = models.ForeignKey(
        AlunoProfile, on_delete=models.CASCADE, related_name="respostas"
    )
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="respostas")
    alternativa_escolhida = models.CharField(max_length=1, blank=True)
    correta = models.BooleanField(null=True)
    tempo_gasto_ms = models.PositiveIntegerField(default=0)
    respondida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("simulado", "question")]
        indexes = [
            models.Index(fields=["aluno_profile"]),
            models.Index(fields=["simulado"]),
            models.Index(fields=["question"]),
            models.Index(fields=["respondida_em"]),
        ]

    def __str__(self):
        return f"{self.aluno_profile} — {self.question} — {self.alternativa_escolhida or '?'}"
