import time

from django.core.management.base import BaseCommand

from exams.models import Question, Topic
from llm.client import generate_json

from irt.models import DifficultySource, ItemParameters


class Command(BaseCommand):
    help = (
        "Classifica questões sem ItemParameters via Gemini (bootstrap de TRI, Fase 1). "
        "Idempotente: pula questões já classificadas."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--discipline", default=None)
        parser.add_argument(
            "--sleep", type=float, default=0.5, help="segundos entre chamadas (rate limit)"
        )

    def handle(self, *args, **options):
        qs = Question.objects.filter(itemparameters__isnull=True).prefetch_related("alternatives")
        if options["discipline"]:
            qs = qs.filter(discipline=options["discipline"])
        if options["limit"]:
            qs = qs[: options["limit"]]

        ok, falhas = 0, 0
        for question in qs:
            try:
                self._classify_one(question)
                ok += 1
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  questão {question.id} falhou: {exc}"))
                falhas += 1
            time.sleep(options["sleep"])

        self.stdout.write(self.style.SUCCESS(f"Classificadas: {ok}, falhas: {falhas}"))

    def _classify_one(self, question):
        topicos_por_nome = {
            t.name: t for t in Topic.objects.filter(discipline=question.discipline)
        }
        alternativas_texto = "\n".join(
            f"{alt.letter}) {alt.text}" for alt in question.alternatives.all()
        )
        prompt = (
            "Você é um especialista em classificar questões do ENEM.\n"
            f"Disciplina: {question.get_discipline_display()}\n"
            f"Escolha o assunto (topic) EXATAMENTE de uma destas opções: "
            f"{list(topicos_por_nome.keys())}\n"
            "Estime a dificuldade (difficulty_b) numa escala de -2 (muito fácil) a +2 "
            "(muito difícil), sendo 0 dificuldade média.\n\n"
            f"Enunciado: {question.context}\n"
            f"{question.alternatives_introduction}\n{alternativas_texto}\n\n"
            'Responda em JSON: {"topic": "<um dos valores da lista>", "difficulty_b": <float>}'
        )
        result = generate_json(prompt)

        topic = topicos_por_nome.get(result.get("topic"))
        if topic is None:
            self.stdout.write(
                self.style.WARNING(
                    f"  questão {question.id}: assunto '{result.get('topic')}' fora da "
                    "taxonomia curada, deixando topic em branco"
                )
            )

        num_alternativas = question.alternatives.count()
        ItemParameters.objects.create(
            question=question,
            a=1.0,
            b=float(result["difficulty_b"]),
            c=(1 / num_alternativas) if num_alternativas else 0.2,
            difficulty_source=DifficultySource.LLM_ESTIMATE,
        )
        if topic is not None:
            question.topic = topic
            question.save(update_fields=["topic"])
