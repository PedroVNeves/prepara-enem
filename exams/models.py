from django.db import models

from core.models import TimeStampedModel


class Discipline(models.TextChoices):
    CIENCIAS_HUMANAS = "ciencias-humanas", "Ciências Humanas e suas Tecnologias"
    CIENCIAS_NATUREZA = "ciencias-natureza", "Ciências da Natureza e suas Tecnologias"
    LINGUAGENS = "linguagens", "Linguagens, Códigos e suas Tecnologias"
    MATEMATICA = "matematica", "Matemática e suas Tecnologias"


class Language(models.TextChoices):
    ESPANHOL = "espanhol", "Espanhol"
    INGLES = "ingles", "Inglês"


class Exam(TimeStampedModel):
    title = models.CharField(max_length=255)
    year = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ["-year"]

    def __str__(self):
        return self.title


class Topic(models.Model):
    """Taxonomia curada por disciplina, carregada via fixture — não texto
    livre gerado pelo LLM, para não fragmentar a agregação por assunto do
    relatório com sinônimos (ex.: "Trigonometria" vs "Funções Trigonométricas")."""

    discipline = models.CharField(max_length=32, choices=Discipline.choices)
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = [("discipline", "name")]
        ordering = ["discipline", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_discipline_display()})"


class Question(TimeStampedModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    external_index = models.PositiveIntegerField(help_text="Índice 1-183 da prova original")
    discipline = models.CharField(max_length=32, choices=Discipline.choices)
    language = models.CharField(max_length=16, choices=Language.choices, null=True, blank=True)
    context = models.TextField(help_text="Enunciado em markdown, pode referenciar imagens locais")
    alternatives_introduction = models.TextField(blank=True)
    correct_alternative = models.CharField(max_length=1)
    topic = models.ForeignKey(
        Topic, on_delete=models.SET_NULL, related_name="questions", null=True, blank=True
    )

    class Meta:
        unique_together = [("exam", "external_index", "language")]
        ordering = ["exam", "external_index"]

    def __str__(self):
        return f"Questão {self.external_index} - ENEM {self.exam.year}"


class Alternative(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="alternatives")
    letter = models.CharField(max_length=1)
    text = models.TextField(blank=True)
    image_path = models.CharField(max_length=500, blank=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = [("question", "letter")]
        ordering = ["question", "letter"]

    def __str__(self):
        return f"{self.letter} — {self.question}"
