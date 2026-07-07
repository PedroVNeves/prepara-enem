import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from redacao.services import build_prompt
from llm.client import generate_json

COMPETENCIAS = ["c1", "c2", "c3", "c4", "c5"]

CORPORA = {
    "essay-br": Path(__file__).resolve().parent.parent.parent / "fixtures" / "essay_br_sample.csv",
}


class Command(BaseCommand):
    help = (
        "Mede a proximidade entre a nota do modelo e a nota humana no corpus Essay-BR/UOL. "
        "Roda fora do fluxo de produção — pré-requisito antes de habilitar a correção por IA "
        "para alunos reais."
    )

    def add_arguments(self, parser):
        parser.add_argument("--corpus", default="essay-br", choices=list(CORPORA.keys()))
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        corpus_path = CORPORA[options["corpus"]]
        limit = options["limit"]

        with open(corpus_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))[:limit]

        erros_por_competencia = {c: [] for c in COMPETENCIAS}
        erros_nota_final = []
        falhas = 0

        for i, row in enumerate(rows, start=1):
            prompt = build_prompt(row["titulo"], row["texto_motivador"], row["texto"])
            try:
                result = generate_json(prompt)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  [{i}] falhou: {exc}"))
                falhas += 1
                continue

            nota_final_modelo = 0
            nota_final_humana = 0
            for c in COMPETENCIAS:
                previsto = int(result[c])
                humano = int(row[c])
                erros_por_competencia[c].append(abs(previsto - humano))
                nota_final_modelo += previsto
                nota_final_humana += humano
            erros_nota_final.append(abs(nota_final_modelo - nota_final_humana))

            self.stdout.write(
                f"  [{i}] modelo={nota_final_modelo} humano={nota_final_humana} "
                f"diff={abs(nota_final_modelo - nota_final_humana)}"
            )

        self.stdout.write(self.style.SUCCESS("\nResumo (MAE = erro médio absoluto):"))
        for c in COMPETENCIAS:
            valores = erros_por_competencia[c]
            if valores:
                mae = sum(valores) / len(valores)
                self.stdout.write(f"  {c}: MAE = {mae:.1f} pontos (n={len(valores)})")
        if erros_nota_final:
            mae_total = sum(erros_nota_final) / len(erros_nota_final)
            self.stdout.write(
                self.style.SUCCESS(f"  nota final: MAE = {mae_total:.1f} pontos (n={len(erros_nota_final)})")
            )
        if falhas:
            self.stdout.write(self.style.WARNING(f"  {falhas} redações falharam na chamada ao Gemini"))
