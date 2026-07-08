import time

from django.core.management.base import BaseCommand

from exams.models import Question, Topic
from llm.client import generate_json

from irt.models import DifficultySource, ItemParameters

BATCH_SIZE = 25
# Free tier do Gemini Flash-Lite: 15 requisições/min. Uma chamada por lote
# (não por questão) é o que torna isso viável — 2757 questões em lotes de 25
# são ~110 chamadas, não 2757.
SLEEP_BETWEEN_BATCHES = 4.5


class Command(BaseCommand):
    help = (
        "Classifica questões sem ItemParameters via Gemini (bootstrap de TRI, Fase 1). "
        "Manda várias questões por chamada (agrupadas por disciplina, em lotes de "
        f"{BATCH_SIZE}) em vez de uma por questão — 15 req/min no free tier torna "
        "uma chamada por questão impraticável em escala (2757 questões estourariam "
        "a cota em ~1 minuto). Idempotente: pula questões já classificadas."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--discipline", default=None)
        parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
        parser.add_argument(
            "--sleep",
            type=float,
            default=SLEEP_BETWEEN_BATCHES,
            help="segundos entre lotes (rate limit)",
        )

    def handle(self, *args, **options):
        qs = Question.objects.filter(itemparameters__isnull=True).prefetch_related(
            "alternatives"
        ).order_by("discipline", "exam", "external_index")
        if options["discipline"]:
            qs = qs.filter(discipline=options["discipline"])
        if options["limit"]:
            qs = qs[: options["limit"]]

        questions = list(qs)
        batch_size = options["batch_size"]
        sleep_s = options["sleep"]

        ok, falhas = 0, 0
        for i in range(0, len(questions), batch_size):
            batch = questions[i : i + batch_size]
            # Todo o lote é da mesma disciplina, graças ao order_by acima —
            # exceto possivelmente na fronteira entre disciplinas, então
            # separamos por disciplina dentro do próprio lote.
            by_discipline = {}
            for q in batch:
                by_discipline.setdefault(q.discipline, []).append(q)

            for discipline, disc_questions in by_discipline.items():
                try:
                    n_ok, n_falhas = self._classify_batch(discipline, disc_questions)
                    ok += n_ok
                    falhas += n_falhas
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"  lote falhou: {exc}"))
                    falhas += len(disc_questions)
                time.sleep(sleep_s)

        self.stdout.write(self.style.SUCCESS(f"Classificadas: {ok}, falhas: {falhas}"))

    def _classify_batch(self, discipline, questions):
        topicos_por_nome = {t.name: t for t in Topic.objects.filter(discipline=discipline)}

        itens_prompt = []
        for q in questions:
            alternativas_texto = "\n".join(
                f"{alt.letter}) {alt.text}" for alt in q.alternatives.all()
            )
            itens_prompt.append(
                f"### Questão id={q.id}\n"
                f"{q.context}\n{q.alternatives_introduction}\n{alternativas_texto}"
            )

        prompt = (
            "Você é um especialista em classificar questões do ENEM.\n"
            f"Disciplina: {questions[0].get_discipline_display()}\n"
            f"Para CADA questão abaixo, escolha o assunto (topic) EXATAMENTE de uma "
            f"destas opções: {list(topicos_por_nome.keys())}\n"
            "Estime a dificuldade (difficulty_b) numa escala de -2 (muito fácil) a "
            "+2 (muito difícil), sendo 0 dificuldade média.\n\n"
            + "\n\n".join(itens_prompt)
            + "\n\nResponda em JSON, uma entrada por questão, na mesma ordem, "
            'incluindo o id: {"classificacoes": [{"id": <id>, "topic": '
            '"<um dos valores da lista>", "difficulty_b": <float>}, ...]}'
        )
        result = generate_json(prompt)
        classificacoes = {c["id"]: c for c in result.get("classificacoes", [])}

        questions_by_id = {q.id: q for q in questions}
        item_params = []
        topic_updates = []
        ok = 0
        for qid, question in questions_by_id.items():
            c = classificacoes.get(qid)
            if c is None:
                self.stdout.write(self.style.WARNING(f"  questão {qid}: sem classificação no lote"))
                continue

            topic = topicos_por_nome.get(c.get("topic"))
            if topic is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"  questão {qid}: assunto '{c.get('topic')}' fora da "
                        "taxonomia curada, deixando topic em branco"
                    )
                )
            else:
                question.topic = topic
                topic_updates.append(question)

            num_alternativas = question.alternatives.count()
            item_params.append(
                ItemParameters(
                    question=question,
                    a=1.0,
                    b=float(c["difficulty_b"]),
                    c=(1 / num_alternativas) if num_alternativas else 0.2,
                    difficulty_source=DifficultySource.LLM_ESTIMATE,
                )
            )
            ok += 1

        if item_params:
            ItemParameters.objects.bulk_create(item_params)
        if topic_updates:
            Question.objects.bulk_update(topic_updates, ["topic"])

        falhas = len(questions) - ok
        return ok, falhas
