from django.db.models import Avg, Count, Q

from irt.models import ItemParameters, StudentAbility
from simulados.models import Resposta

from .formulas import item_information


def erros_por_assunto(aluno_profile):
    """Questões erradas agrupadas por área/assunto."""
    return (
        Resposta.objects.filter(aluno_profile=aluno_profile, correta=False)
        .values("question__discipline", "question__topic__name")
        .annotate(total=Count("id"))
        .order_by("-total")
    )


def dominio_por_area(aluno_profile):
    """Ranking de domínio por área (theta), do menor para o maior."""
    return StudentAbility.objects.filter(aluno_profile=aluno_profile).order_by("theta")


def dominio_por_assunto(aluno_profile):
    """Taxa de acerto simples por assunto — não é IRT formal (poucos itens
    por assunto para calibrar theta), mas suficiente para apontar onde o
    aluno mais erra."""
    return (
        Resposta.objects.filter(aluno_profile=aluno_profile, question__topic__isnull=False)
        .values("question__topic__name", "question__discipline")
        .annotate(
            total=Count("id"),
            acertos=Count("id", filter=Q(correta=True)),
        )
        .order_by("acertos")
    )


def tempo_por_questao_vs_media(aluno_profile):
    """Tempo médio do aluno por disciplina comparado à média global (cross-
    aluno) — a única agregação do sistema que cruza perfis, segura porque
    retorna só uma média anônima, nunca dados individuais de outro aluno."""
    tempo_aluno = (
        Resposta.objects.filter(aluno_profile=aluno_profile, respondida_em__isnull=False)
        .values("question__discipline")
        .annotate(media_aluno=Avg("tempo_gasto_ms"))
    )
    resultado = []
    for row in tempo_aluno:
        discipline = row["question__discipline"]
        media_global = Resposta.objects.filter(
            question__discipline=discipline, respondida_em__isnull=False
        ).aggregate(media=Avg("tempo_gasto_ms"))["media"]
        resultado.append(
            {
                "discipline": discipline,
                "media_aluno_ms": row["media_aluno"],
                "media_global_ms": media_global,
            }
        )
    resultado.sort(key=lambda r: (r["media_aluno_ms"] or 0), reverse=True)
    return resultado


def impacto_erros_no_theta(aluno_profile, limit=10):
    """Rankeia os erros do aluno pela informação do item no theta atual dele
    — quanto maior a informação, maior o impacto daquele erro na estimativa
    de proficiência."""
    erros = Resposta.objects.filter(aluno_profile=aluno_profile, correta=False).select_related(
        "question", "question__itemparameters"
    )
    habilidades = {
        h.discipline: h.theta
        for h in StudentAbility.objects.filter(aluno_profile=aluno_profile)
    }
    ranqueados = []
    for resposta in erros:
        try:
            ip = resposta.question.itemparameters
        except ItemParameters.DoesNotExist:
            continue
        theta = habilidades.get(resposta.question.discipline, 0.0)
        informacao = item_information(ip.a, ip.b, ip.c, theta)
        ranqueados.append({"resposta": resposta, "informacao": informacao})
    ranqueados.sort(key=lambda r: r["informacao"], reverse=True)
    return ranqueados[:limit]


def turma_stats(turma):
    """Estatísticas agregadas por aluno de uma turma — média de acertos e
    tempo médio, para o painel do professor."""
    resultado = []
    for aluno in turma.alunos.all():
        respostas = Resposta.objects.filter(aluno_profile=aluno, respondida_em__isnull=False)
        total = respostas.count()
        acertos = respostas.filter(correta=True).count()
        tempo_medio = respostas.aggregate(media=Avg("tempo_gasto_ms"))["media"]
        resultado.append(
            {
                "aluno": aluno,
                "total_respostas": total,
                "acertos": acertos,
                "percentual": round(100 * acertos / total, 1) if total else None,
                "tempo_medio_ms": tempo_medio,
            }
        )
    return resultado
