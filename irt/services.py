"""Calibração TRI real (Fase 2) via EM/MML.

Biblioteca: girth (não py-irt) — decisão tomada após spike: importar
py-irt/PyTorch consome ~700MB de RAM só no import, o que estoura o limite
de 512MB do plano Render Starter. girth (numpy/scipy puro) usa ~110MB.

Trade-off aceito: girth não expõe um prior bayesiano nativo por item como o
py-irt faria. Em vez disso, aplicamos um shrinkage empírico — a estimativa
calibrada via MML é misturada com a estimativa anterior (do Gemini ou de uma
calibração prévia) ponderada por PRIOR_STRENGTH, um "peso" em unidades de
respondentes equivalentes. Com poucos itens/respondentes isso estabiliza a
calibração puxando para a estimativa anterior; com muitos respondentes o
MML domina — mesmo espírito do prior bayesiano do brief, via um mecanismo
mais simples compatível com a biblioteca leve."""

from django.utils import timezone

from simulados.models import Resposta

from .models import DifficultySource, ItemParameters, StudentAbility

PRIOR_STRENGTH = 50


def recalibrate_tri(min_respondents=200, discipline=None):
    import girth  # lazy import: leve (~110MB), mas ainda assim fora do boot do app

    itens_qs = ItemParameters.objects.filter(respondent_count__gte=min_respondents)
    if discipline:
        itens_qs = itens_qs.filter(question__discipline=discipline)
    itens = list(itens_qs.select_related("question"))
    if not itens:
        return {"itens_calibrados": 0, "alunos_reestimados": 0, "disciplinas": []}

    disciplinas = sorted({ip.question.discipline for ip in itens})
    total_itens = 0
    total_alunos = 0
    for disc in disciplinas:
        itens_disc = [ip for ip in itens if ip.question.discipline == disc]
        n_itens, n_alunos = _recalibrate_discipline(girth, itens_disc, disc)
        total_itens += n_itens
        total_alunos += n_alunos

    return {
        "itens_calibrados": total_itens,
        "alunos_reestimados": total_alunos,
        "disciplinas": disciplinas,
    }


def _recalibrate_discipline(girth, itens, discipline):
    import numpy as np

    questions = [ip.question for ip in itens]
    respostas = Resposta.objects.filter(
        question__in=questions, respondida_em__isnull=False
    ).values("question_id", "aluno_profile_id", "correta")

    alunos_ids = sorted({r["aluno_profile_id"] for r in respostas})
    if not alunos_ids:
        return 0, 0
    aluno_index = {aluno_id: i for i, aluno_id in enumerate(alunos_ids)}
    question_index = {q.id: i for i, q in enumerate(questions)}

    matrix = np.full((len(questions), len(alunos_ids)), girth.INVALID_RESPONSE, dtype=float)
    for r in respostas:
        i = question_index[r["question_id"]]
        j = aluno_index[r["aluno_profile_id"]]
        matrix[i, j] = 1.0 if r["correta"] else 0.0

    resultado_mml = girth.threepl_mml(matrix)
    discriminacao = resultado_mml["Discrimination"]
    dificuldade = resultado_mml["Difficulty"]
    acaso = resultado_mml["Guessing"]

    for i, ip in enumerate(itens):
        b_mml = float(dificuldade[i])
        n = ip.respondent_count
        b_final = (n * b_mml + PRIOR_STRENGTH * ip.b) / (n + PRIOR_STRENGTH)
        ip.a = float(discriminacao[i])
        ip.b = b_final
        ip.c = float(acaso[i])
        ip.difficulty_source = DifficultySource.CALIBRATED
        ip.last_calibrated_at = timezone.now()
        ip.save()

    thetas = girth.ability_3pl_eap(matrix, dificuldade, discriminacao, acaso)
    for aluno_id, idx in aluno_index.items():
        StudentAbility.objects.update_or_create(
            aluno_profile_id=aluno_id,
            discipline=discipline,
            defaults={"theta": float(thetas[idx]), "method": StudentAbility.METHOD_EM_CALIBRATED},
        )

    return len(itens), len(alunos_ids)
