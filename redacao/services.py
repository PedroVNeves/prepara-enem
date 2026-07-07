from django.conf import settings

from llm.client import generate_json

from .models import EssaySubmission, StatusSubmissao

RUBRICA = """Você é um corretor de redações do ENEM. Avalie o texto do aluno segundo as 5 \
competências oficiais, cada uma de 0 a 200 pontos, em múltiplos de 40 (0, 40, 80, 120, 160, 200):

Competência 1: Domínio da norma culta da língua escrita (gramática, ortografia, acentuação).
Competência 2: Compreensão da proposta e aplicação de conceitos de várias áreas do conhecimento, \
respeitando a estrutura dissertativo-argumentativa.
Competência 3: Seleção, organização e interpretação de informações, fatos, opiniões e argumentos \
em defesa de um ponto de vista.
Competência 4: Conhecimento dos mecanismos linguísticos para construção da argumentação \
(coesão e coerência).
Competência 5: Proposta de intervenção para o problema abordado, respeitando os direitos humanos.

Responda em JSON no formato:
{"c1": <int>, "c2": <int>, "c3": <int>, "c4": <int>, "c5": <int>,
 "feedback": {"c1": "<explicação>", "c2": "...", "c3": "...", "c4": "...", "c5": "..."}}
"""


def build_prompt(tema, texto_motivador, texto_redacao):
    return (
        f"{RUBRICA}\n\n"
        f"Tema da redação: {tema}\n"
        f"Texto motivador: {texto_motivador}\n\n"
        f"Redação do aluno:\n{texto_redacao}"
    )


def correct_essay(submission):
    """Chama o Gemini para corrigir uma redação e atualiza a submissão.
    Levanta exceção em caso de falha — quem chama decide como tratar."""
    if submission.assignment:
        tema = submission.assignment.tema
        texto_motivador = submission.assignment.texto_motivador
    elif submission.prompt:
        tema = submission.prompt.titulo
        texto_motivador = submission.prompt.texto_motivador
    else:
        tema, texto_motivador = "Tema livre", ""
    prompt = build_prompt(tema, texto_motivador, submission.texto)

    result = generate_json(prompt, model=settings.GEMINI_MODEL_FLASH)

    notas = {k: int(result[k]) for k in ("c1", "c2", "c3", "c4", "c5")}
    nota_final = sum(notas.values())

    submission.notas_competencias = notas
    submission.nota_final = nota_final
    submission.feedback = result.get("feedback", {})
    submission.llm_model_used = settings.GEMINI_MODEL_FLASH
    submission.status = StatusSubmissao.CORRECTED
    submission.save()
    return submission


def generate_essay_theme():
    """Pede ao Gemini um tema + texto motivador estilo ENEM, para quando o
    professor não quer escolher um tema próprio."""
    prompt = (
        "Gere um tema de redação no estilo da prova do ENEM (dissertativo-argumentativo), "
        "com um texto motivador curto (2-3 parágrafos, sem citar fontes fictícias como se "
        "fossem reais). Responda em JSON: "
        '{"tema": "<título do tema>", "texto_motivador": "<texto motivador>"}'
    )
    return generate_json(prompt, model=settings.GEMINI_MODEL_FLASH)


def grade_essay_manually(submission, professor, notas, feedback):
    """Grava a correção manual de um professor — mesmos campos da correção
    por IA, mas com correction_source/corrected_by identificando a origem."""
    nota_final = sum(int(v) for v in notas.values())
    submission.notas_competencias = notas
    submission.nota_final = nota_final
    submission.feedback = feedback
    submission.correction_source = "manual"
    submission.corrected_by = professor
    submission.status = StatusSubmissao.CORRECTED
    submission.save()
    return submission


def process_pending_essay_submissions(limit=20):
    """Processa a fila de redações pendentes de correção por IA — usado tanto
    pelo management command quanto pelo job periódico disparado via ops."""
    pendentes = EssaySubmission.objects.filter(
        status=StatusSubmissao.PENDING, correction_source="ai"
    )[:limit]
    processadas = 0
    falhas = 0
    for submission in pendentes:
        submission.status = StatusSubmissao.PROCESSING
        submission.save(update_fields=["status"])
        try:
            correct_essay(submission)
            processadas += 1
        except Exception as exc:
            submission.status = StatusSubmissao.FAILED
            submission.error_message = str(exc)
            submission.save(update_fields=["status", "error_message"])
            falhas += 1
    return {"processadas": processadas, "falhas": falhas}
