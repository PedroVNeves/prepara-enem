from django.core.management.base import BaseCommand

from irt.services import recalibrate_tri


class Command(BaseCommand):
    help = (
        "Recalibra parâmetros TRI via EM (girth) para itens com respondentes "
        "suficientes, usando a estimativa anterior (Gemini ou calibração prévia) "
        "como base de shrinkage. Cadência recomendada: semanal."
    )

    def add_arguments(self, parser):
        parser.add_argument("--min-respondents", type=int, default=200)
        parser.add_argument("--discipline", default=None)

    def handle(self, *args, **options):
        resumo = recalibrate_tri(
            min_respondents=options["min_respondents"], discipline=options["discipline"]
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Itens calibrados: {resumo['itens_calibrados']}, "
                f"alunos reestimados: {resumo['alunos_reestimados']}, "
                f"disciplinas: {resumo['disciplinas']}"
            )
        )
