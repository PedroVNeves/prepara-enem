import random

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from accounts.models import AlunoProfile
from exams.models import Question, Topic
from irt.models import ItemParameters, StudentAbility

from .models import Resposta, Simulado, SimuladoAssignment, SimuladoQuestion, StatusSimulado, TipoSimulado

# Bandas de dificuldade relativas ao theta do aluno: quanto mais perto de
# theta, mais peso na amostragem ponderada (favorece questões no nível atual
# do aluno, sem excluir totalmente as mais fáceis/difíceis).
DIFFICULTY_BANDS = [(0.5, 3), (1.5, 2), (float("inf"), 1)]


def _weighted_sample_without_replacement(items_with_weights, k):
    """Amostragem ponderada sem reposição (algoritmo A-Res): cada item recebe
    uma chave aleatória proporcional ao seu peso; pega-se os k maiores."""
    keyed = []
    for item, weight in items_with_weights:
        u = random.random()
        key = u ** (1.0 / weight) if weight > 0 else 0.0
        keyed.append((key, item))
    keyed.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in keyed[:k]]


def _band_weight(question_b, theta):
    diff = abs(question_b - theta)
    for limite, peso in DIFFICULTY_BANDS:
        if diff <= limite:
            return peso
    return 1


def select_fixed_exam_questions(exam):
    """Uma prova histórica tem índices 1-5 duplicados entre espanhol/inglês
    (o aluno real escolhe um idioma no dia da prova) — aqui escolhemos
    deterministicamente 'ingles' quando houver variante, senão a questão
    sem idioma, para montar uma prova de tamanho real (sem duplicar índice)."""
    questions = list(
        Question.objects.filter(exam=exam).order_by("external_index", "language")
    )
    by_index = {}
    for q in questions:
        current = by_index.get(q.external_index)
        if current is None:
            by_index[q.external_index] = q
        elif current.language is not None and q.language == "ingles":
            by_index[q.external_index] = q
    return [by_index[idx] for idx in sorted(by_index)]


def select_by_difficulty_band(aluno_profile, discipline, topic=None, quantidade=10, excluir_respondidas=True):
    """Seleciona questões por banda de dificuldade relativa ao theta atual do
    aluno (default 0.0 se ainda não há StudentAbility calibrado). Só considera
    questões já classificadas (com ItemParameters) — cold-start via Gemini ou
    calibradas via EM, tanto faz para este propósito."""
    habilidade, _ = StudentAbility.objects.get_or_create(
        aluno_profile=aluno_profile, discipline=discipline
    )
    theta = habilidade.theta

    candidatas = (
        Question.objects.filter(discipline=discipline, itemparameters__isnull=False)
        .filter(Q(language__isnull=True) | Q(language="ingles"))
        .select_related("itemparameters")
    )
    if topic is not None:
        candidatas = candidatas.filter(topic=topic)
    if excluir_respondidas:
        respondidas_ids = Resposta.objects.filter(
            aluno_profile=aluno_profile, question__discipline=discipline
        ).values_list("question_id", flat=True)
        candidatas = candidatas.exclude(id__in=respondidas_ids)

    candidatas = list(candidatas)
    if len(candidatas) <= quantidade:
        return candidatas

    items_with_weights = [
        (q, _band_weight(q.itemparameters.b, theta)) for q in candidatas
    ]
    return _weighted_sample_without_replacement(items_with_weights, quantidade)


@transaction.atomic
def start_custom_simulado(aluno_profile, discipline, topic=None, quantidade=10):
    simulado = Simulado.objects.create(
        aluno_profile=aluno_profile,
        tipo=TipoSimulado.CUSTOMIZADO,
        config={
            "discipline": discipline,
            "topic_id": topic.id if topic else None,
            "quantidade": quantidade,
        },
    )
    questions = select_by_difficulty_band(aluno_profile, discipline, topic, quantidade)
    SimuladoQuestion.objects.bulk_create(
        [
            SimuladoQuestion(simulado=simulado, question=q, ordem=i)
            for i, q in enumerate(questions, start=1)
        ]
    )
    return simulado


def _target_alunos_for_assignment(assignment):
    alunos = set(assignment.alunos.all())
    if assignment.turma_id:
        alunos.update(AlunoProfile.objects.filter(turma=assignment.turma))
    return alunos


@transaction.atomic
def create_simulado_assignment(professor, escola, config, turma=None, alunos=None, prazo=None):
    """Cria a atribuição e, para cada aluno-alvo (roster da turma ∪ lista
    explícita), um Simulado individual usando a mesma seleção por banda de
    dificuldade do self-service — só que parametrizada pela config do
    professor em vez do theta livre do aluno."""
    assignment = SimuladoAssignment.objects.create(
        professor=professor, escola=escola, config=config, turma=turma, prazo=prazo
    )
    if alunos:
        assignment.alunos.set(alunos)

    discipline = config["discipline"]
    topic_id = config.get("topic_id")
    topic = Topic.objects.filter(pk=topic_id).first() if topic_id else None
    quantidade = config.get("quantidade", 10)

    for aluno in _target_alunos_for_assignment(assignment):
        simulado = Simulado.objects.create(
            aluno_profile=aluno,
            tipo=TipoSimulado.CUSTOMIZADO,
            assignment=assignment,
            config=config,
        )
        questions = select_by_difficulty_band(aluno, discipline, topic, quantidade)
        SimuladoQuestion.objects.bulk_create(
            [
                SimuladoQuestion(simulado=simulado, question=q, ordem=i)
                for i, q in enumerate(questions, start=1)
            ]
        )
    return assignment


@transaction.atomic
def start_fixed_simulado(aluno_profile, exam):
    simulado = Simulado.objects.create(
        aluno_profile=aluno_profile,
        tipo=TipoSimulado.FIXO,
        exam=exam,
        config={"exam_year": exam.year},
    )
    questions = select_fixed_exam_questions(exam)
    SimuladoQuestion.objects.bulk_create(
        [
            SimuladoQuestion(simulado=simulado, question=q, ordem=i)
            for i, q in enumerate(questions, start=1)
        ]
    )
    return simulado


def record_answer(simulado, question, alternativa_escolhida, tempo_gasto_ms):
    correta = alternativa_escolhida == question.correct_alternative
    resposta, created = Resposta.objects.update_or_create(
        simulado=simulado,
        question=question,
        defaults={
            "aluno_profile": simulado.aluno_profile,
            "alternativa_escolhida": alternativa_escolhida,
            "correta": correta,
            "tempo_gasto_ms": tempo_gasto_ms,
            "respondida_em": timezone.now(),
        },
    )
    if created:
        # conta quantos alunos já responderam este item — usado pelo limiar
        # de 200+ respondentes antes de recalibrar via EM (irt.services)
        ItemParameters.objects.filter(question=question).update(
            respondent_count=F("respondent_count") + 1
        )
    return resposta


def finalize_simulado(simulado):
    simulado.status = StatusSimulado.FINALIZADO
    simulado.finalizado_em = timezone.now()
    simulado.save(update_fields=["status", "finalizado_em"])
    return score_summary(simulado)


def score_summary(simulado):
    respostas = list(simulado.respostas.select_related("question"))
    total = simulado.perguntas.count()
    acertos = sum(1 for r in respostas if r.correta)
    return {
        "total_questoes": total,
        "respondidas": len(respostas),
        "acertos": acertos,
        "percentual": round(100 * acertos / total, 1) if total else 0,
    }
