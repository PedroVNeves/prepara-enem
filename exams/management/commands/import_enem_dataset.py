import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from exams.models import Alternative, Exam, Question

ENEM_DEV_PREFIX = "https://enem.dev/"
IMAGE_URL_RE = re.compile(re.escape(ENEM_DEV_PREFIX) + r'[^\s)"]+')


class _DryRunRollback(Exception):
    pass


class Command(BaseCommand):
    help = (
        "Importa o dataset ENEM (exams.json + <ano>/details.json + "
        "questions/<index[-idioma]>/details.json) para Exam/Question/Alternative. "
        "Idempotente: reruns são seguros (update_or_create)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--years", nargs="*", type=int, default=None, help="Limita a anos específicos."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Roda tudo em transação com rollback ao final."
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        years_filter = set(options["years"]) if options["years"] else None
        dry_run = options["dry_run"]

        exams_index_path = base_dir / "exams.json"
        exams_index = json.loads(exams_index_path.read_text(encoding="utf-8"))

        stats = {"questions": 0, "alternatives": 0, "missing_images": []}

        try:
            with transaction.atomic():
                for entry in exams_index:
                    year = entry["year"]
                    if years_filter and year not in years_filter:
                        continue
                    self.stdout.write(f"Importando ENEM {year}...")
                    exam, _ = Exam.objects.update_or_create(
                        year=year, defaults={"title": entry["title"]}
                    )
                    self._import_year(base_dir, exam, stats)

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

    def _import_year(self, base_dir, exam, stats):
        year_dir = base_dir / str(exam.year)
        details_path = year_dir / "details.json"
        if not details_path.exists():
            self.stdout.write(self.style.WARNING(f"  {details_path} não encontrado, pulando."))
            return
        details = json.loads(details_path.read_text(encoding="utf-8"))
        for q_ref in details["questions"]:
            self._import_question(base_dir, year_dir, exam, q_ref, stats)

    def _import_question(self, base_dir, year_dir, exam, q_ref, stats):
        index = q_ref["index"]
        language = q_ref.get("language")
        folder_name = f"{index}-{language}" if language else str(index)
        question_path = year_dir / "questions" / folder_name / "details.json"
        if not question_path.exists():
            self.stdout.write(self.style.WARNING(f"  questão ausente: {question_path}"))
            return
        data = json.loads(question_path.read_text(encoding="utf-8"))

        context, missing = self._rewrite_images(data.get("context") or "", base_dir)
        stats["missing_images"].extend(missing)

        question, _ = Question.objects.update_or_create(
            exam=exam,
            external_index=index,
            language=language,
            defaults={
                "discipline": data["discipline"],
                "context": context,
                "alternatives_introduction": data.get("alternativesIntroduction") or "",
                "correct_alternative": data["correctAlternative"],
            },
        )
        stats["questions"] += 1

        for alt in data.get("alternatives", []):
            image_path = ""
            if alt.get("file"):
                image_path, found = self._relative_path(alt["file"], base_dir)
                if not found:
                    stats["missing_images"].append(alt["file"])
            Alternative.objects.update_or_create(
                question=question,
                letter=alt["letter"],
                defaults={
                    "text": alt.get("text") or "",
                    "image_path": image_path,
                    "is_correct": bool(alt.get("isCorrect")),
                },
            )
            stats["alternatives"] += 1

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
