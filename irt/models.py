from django.db import models

from accounts.models import AlunoProfile
from exams.models import Discipline, Question


class DifficultySource(models.TextChoices):
    LLM_ESTIMATE = "llm_estimate", "Estimativa do LLM"
    CALIBRATED = "calibrated", "Calibrado via EM"


class ItemParameters(models.Model):
    """Parâmetros do modelo 3PL. Fase 1 (cold-start): b vem da estimativa do
    Gemini, a=1.0 fixo, c=1/nº alternativas. Fase 2: recalibrado via EM
    quando o item acumula respondentes suficientes (ver recalibrate_tri)."""

    question = models.OneToOneField(Question, on_delete=models.CASCADE, related_name="itemparameters")
    a = models.FloatField(default=1.0)
    b = models.FloatField()
    c = models.FloatField()
    difficulty_source = models.CharField(max_length=20, choices=DifficultySource.choices)
    respondent_count = models.PositiveIntegerField(default=0)
    last_calibrated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.question} — b={self.b:.2f} ({self.difficulty_source})"


class StudentAbility(models.Model):
    """Um registro por (aluno, disciplina) — o ENEM pontua por área, então
    proficiência é modelada por área desde o início, não um theta global."""

    METHOD_COLD_START = "cold_start"
    METHOD_EM_CALIBRATED = "em_calibrated"
    METHOD_CHOICES = [
        (METHOD_COLD_START, "Cold start"),
        (METHOD_EM_CALIBRATED, "Calibrado via EM"),
    ]

    aluno_profile = models.ForeignKey(
        AlunoProfile, on_delete=models.CASCADE, related_name="habilidades"
    )
    discipline = models.CharField(max_length=32, choices=Discipline.choices)
    theta = models.FloatField(default=0.0)
    theta_se = models.FloatField(null=True, blank=True)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_COLD_START)

    class Meta:
        unique_together = [("aluno_profile", "discipline")]

    def __str__(self):
        return f"{self.aluno_profile} — {self.discipline}: θ={self.theta:.2f}"
