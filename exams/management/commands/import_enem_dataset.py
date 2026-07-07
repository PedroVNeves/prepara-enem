import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from exams.models import Alternative, Exam, Question

ENEM_DEV_PREFIX = "https://enem.dev/"
IMAGE_URL_RE = re.compile(re.escape(ENEM_DEV_PREFIX) + r'[^\s)"]+')

BATCH_SIZE = 500


class _DryRunRollback(Exception):
    pass


class Command(BaseCommand):
    help = (
        "Importa o dataset ENEM (exams.json + <ano>/details.json + "
        "questions/<index[-idioma]>/details.json) para Exam/Question/Alternative. "
        "Usa upsert em lote (bulk_create/bulk_update, casamento feito em Python) "
        "em vez de uma query por linha — contra um Postgres remoto, uma query por "
        "questão/alternativa (~12 por questão) chega a ~33 mil queries no dataset "
        "completo, o que leva horas só de latência de rede. Idempotente: reruns "
        "são seguros."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--years", nargs="*", type=int, default=None, help="Limita a anos específicos."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Roda tudo em transação com rollback ao final."
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limita o total de questões processadas (teste rápido de fumaça).",
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        years_filter = set(options["years"]) if options["years"] else None
        dry_run = options["dry_run"]
        limit = options["limit"]

        exams_index = json.loads((base_dir / "exams.json").read_text(encoding="utf-8"))
        stats = {"questions": 0, "alternatives": 0, "missing_images": []}

        try:
            with transaction.atomic():
                for entry in exams_index:
                    if limit is not None and stats["questions"] >= limit:
                        break
                    year = entry["year"]
                    if years_filter and year not in years_filter:
                        continue
                    self.stdout.write(f"Importando ENEM {year}...")
                    exam, _ = Exam.objects.update_or_create(
                        year=year, defaults={"title": entry["title"]}
                    )
                    self._import_year(base_dir, exam, stats, limit)

                if dry_run:
                    raise _DryRunRollback()
        except _DryRunRollback:
            self.stdout.write(self.style.WARNING("--dry-run: nada foi persistido (rollback)."))

        total = Question.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Questões processadas nesta execução: {stats['questions']}, "
                f"alternativas: {stats['alternatives']}, total no banco: {total}"
            )
        )
        if stats["missing_images"]:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(stats['missing_images'])} imagens referenciadas não "
                    "encontradas no disco (arquivo pode ter sido movido/renomeado)."
                )
            )

    def _import_year(self, base_dir, exam, stats, limit=None):
        year_dir = base_dir / str(exam.year)
        details_path = year_dir / "details.json"
        if not details_path.exists():
            self.stdout.write(self.style.WARNING(f"  {details_path} não encontrado, pulando."))
            return
        details = json.loads(details_path.read_text(encoding="utf-8"))

        parsed = []
        for q_ref in details["questions"]:
            if limit is not None and stats["questions"] + len(parsed) >= limit:
                break
            row = self._read_question(base_dir, year_dir, q_ref, stats)
            if row is not None:
                parsed.append(row)

        questions_by_key = self._upsert_questions(exam, parsed, stats)
        self._upsert_alternatives(parsed, questions_by_key, stats)

    def _read_question(self, base_dir, year_dir, q_ref, stats):
        index = q_ref["index"]
        language = q_ref.get("language")
        folder_name = f"{index}-{language}" if language else str(index)
        question_path = year_dir / "questions" / folder_name / "details.json"
        if not question_path.exists():
            self.stdout.write(self.style.WARNING(f"  questão ausente: {question_path}"))
            return None
        data = json.loads(question_path.read_text(encoding="utf-8"))
        context, missing = self._rewrite_images(data.get("context") or "", base_dir)
        stats["missing_images"].extend(missing)
        return {
            "index": index,
            "language": language,
            "data": data,
            "context": context,
            "base_dir": base_dir,
        }

    def _upsert_questions(self, exam, parsed, stats):
        """Casa em Python (não via ON CONFLICT do Postgres) porque `language`
        é nulo na maioria das questões, e o Postgres trata NULL como sempre
        distinto de outro NULL — ON CONFLICT nunca "acharia" essas linhas
        numa reimportação, criando duplicatas."""
        existing = {
            (q.external_index, q.language): q for q in Question.objects.filter(exam=exam)
        }

        to_create, to_update = [], []
        for row in parsed:
            data = row["data"]
            key = (row["index"], row["language"])
            fields = {
                "discipline": data["discipline"],
                "context": row["context"],
                "alternatives_introduction": data.get("alternativesIntroduction") or "",
                "correct_alternative": data["correctAlternative"],
            }
            existing_q = existing.get(key)
            if existing_q:
                for field, value in fields.items():
                    setattr(existing_q, field, value)
                to_update.append(existing_q)
            else:
                new_q = Question(exam=exam, external_index=row["index"], language=row["language"], **fields)
                to_create.append(new_q)
                existing[key] = new_q

        if to_create:
            Question.objects.bulk_create(to_create, batch_size=BATCH_SIZE)
        if to_update:
            Question.objects.bulk_update(
                to_update,
                ["discipline", "context", "alternatives_introduction", "correct_alternative"],
                batch_size=BATCH_SIZE,
            )
        stats["questions"] += len(parsed)

        return {(row["index"], row["language"]): existing[(row["index"], row["language"])] for row in parsed}

    def _upsert_alternatives(self, parsed, questions_by_key, stats):
        question_ids = [q.id for q in questions_by_key.values()]
        existing = {
            (a.question_id, a.letter): a
            for a in Alternative.objects.filter(question_id__in=question_ids)
        }

        to_create, to_update = [], []
        for row in parsed:
            question = questions_by_key[(row["index"], row["language"])]
            for alt in row["data"].get("alternatives", []):
                image_path = ""
                if alt.get("file"):
                    image_path, found = self._relative_path(alt["file"], row["base_dir"])
                    if not found:
                        stats["missing_images"].append(alt["file"])
                fields = {
                    "text": alt.get("text") or "",
                    "image_path": image_path,
                    "is_correct": bool(alt.get("isCorrect")),
                }
                key = (question.id, alt["letter"])
                existing_a = existing.get(key)
                if existing_a:
                    for field, value in fields.items():
                        setattr(existing_a, field, value)
                    to_update.append(existing_a)
                else:
                    new_a = Alternative(question=question, letter=alt["letter"], **fields)
                    to_create.append(new_a)
                    existing[key] = new_a
                stats["alternatives"] += 1

        if to_create:
            Alternative.objects.bulk_create(to_create, batch_size=BATCH_SIZE)
        if to_update:
            Alternative.objects.bulk_update(
                to_update, ["text", "image_path", "is_correct"], batch_size=BATCH_SIZE
            )

    @staticmethod
    def _relative_path(url, base_dir):
        """Extrai o caminho relativo (com prefixo de ano) de uma URL enem.dev
        e confirma que o arquivo correspondente existe fisicamente no disco."""
        rel_path = url.replace(ENEM_DEV_PREFIX, "")
        found = (base_dir / rel_path).exists()
        return rel_path, found

    def _rewrite_images(self, text, base_dir):
        """Reescreve URLs https://enem.dev/... embutidas no markdown do
        enunciado para o caminho servido via STATIC_URL (WhiteNoise)."""
        missing = []

        def _replace(match):
            url = match.group(0)
            rel_path, found = self._relative_path(url, base_dir)
            if not found:
                missing.append(url)
            return settings.STATIC_URL.rstrip("/") + "/" + rel_path

        rewritten = IMAGE_URL_RE.sub(_replace, text)
        return rewritten, missing
