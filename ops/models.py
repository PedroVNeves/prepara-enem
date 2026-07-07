from django.db import models

from core.models import TimeStampedModel


class StatusJobRun(models.TextChoices):
    RUNNING = "running", "Em execução"
    SUCCESS = "success", "Concluído"
    FAILED = "failed", "Falhou"


class JobRun(TimeStampedModel):
    job_name = models.CharField(max_length=100)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=StatusJobRun.choices, default=StatusJobRun.RUNNING)
    summary = models.TextField(blank=True)
    triggered_by = models.CharField(max_length=20, default="manual")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.job_name} — {self.status} ({self.started_at})"
