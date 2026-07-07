from django.db import models

from core.models import TimeStampedModel


class Plan(TimeStampedModel):
    """Placeholder de schema — sem lógica de cobrança/gateway ainda. Reserva
    o caminho para quando o modelo de negócio (aluno individual paga e
    entra; escola escolhe plano por quantidade de alunos) for implementado."""

    nome = models.CharField(max_length=100)
    preco_mensal = models.DecimalField(max_digits=8, decimal_places=2)
    limite_alunos = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.nome
