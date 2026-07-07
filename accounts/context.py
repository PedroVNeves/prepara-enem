"""Context switcher: separa identidade (User) de contexto de uso (Professor
em uma Escola, ou AlunoProfile individual/de escola). O contexto ativo vive
na sessão, nunca é inferido do User sozinho."""

from dataclasses import dataclass
from typing import Literal, Optional, Union

from .models import AlunoProfile, Professor

SESSION_KEY = "active_context"


@dataclass(frozen=True)
class ProfessorContext:
    kind: Literal["professor"] = "professor"
    professor_id: int = 0
    escola_id: int = 0
    label: str = ""


@dataclass(frozen=True)
class AlunoContext:
    kind: Literal["aluno"] = "aluno"
    aluno_profile_id: int = 0
    escola_id: Optional[int] = None
    label: str = ""


Context = Union[ProfessorContext, AlunoContext]


def available_contexts(user) -> list[Context]:
    contexts: list[Context] = []
    for prof in Professor.objects.filter(user=user).select_related("escola"):
        contexts.append(
            ProfessorContext(
                professor_id=prof.id,
                escola_id=prof.escola_id,
                label=f"Administrador — {prof.escola.nome}",
            )
        )
    for perfil in AlunoProfile.objects.filter(user=user).select_related("escola"):
        label = "Aluno individual" if perfil.escola_id is None else f"Aluno — {perfil.escola.nome}"
        contexts.append(
            AlunoContext(
                aluno_profile_id=perfil.id,
                escola_id=perfil.escola_id,
                label=label,
            )
        )
    return contexts


def context_to_session(context: Context) -> dict:
    if isinstance(context, ProfessorContext):
        return {
            "kind": "professor",
            "professor_id": context.professor_id,
            "escola_id": context.escola_id,
            "label": context.label,
        }
    return {
        "kind": "aluno",
        "aluno_profile_id": context.aluno_profile_id,
        "escola_id": context.escola_id,
        "label": context.label,
    }


def set_active_context(request, context: Context) -> None:
    request.session[SESSION_KEY] = context_to_session(context)


def get_active_context(request) -> Optional[Context]:
    data = request.session.get(SESSION_KEY)
    if not data:
        return None
    if data["kind"] == "professor":
        return ProfessorContext(
            professor_id=data["professor_id"], escola_id=data["escola_id"], label=data["label"]
        )
    return AlunoContext(
        aluno_profile_id=data["aluno_profile_id"], escola_id=data.get("escola_id"), label=data["label"]
    )


def clear_active_context(request) -> None:
    request.session.pop(SESSION_KEY, None)


def current_aluno_profile(request) -> Optional[AlunoProfile]:
    """AlunoProfile do contexto ativo — nunca deduzido de request.user sozinho,
    pois o mesmo User pode ter mais de uma AlunoProfile (individual + escolas)."""
    context = get_active_context(request)
    if context is None or context.kind != "aluno":
        return None
    return AlunoProfile.objects.filter(pk=context.aluno_profile_id, user=request.user).first()


def current_professor(request) -> Optional[Professor]:
    """Professor do contexto ativo — mesmo raciocínio de current_aluno_profile:
    nunca deduzido de request.user sozinho, verifica que o Professor pertence
    de fato ao usuário autenticado."""
    context = get_active_context(request)
    if context is None or context.kind != "professor":
        return None
    return Professor.objects.filter(pk=context.professor_id, user=request.user).first()


def scoped_alunos(context: Context):
    """Alunos visíveis no contexto ativo. Só contexto de professor lista
    alunos de uma escola — é a fronteira de isolamento multi-tenant."""
    if context.kind != "professor":
        raise ValueError("Somente contexto de professor pode listar alunos de uma escola.")
    return AlunoProfile.objects.filter(escola_id=context.escola_id)


def scoped_turmas(context: Context):
    if context.kind != "professor":
        raise ValueError("Somente contexto de professor pode listar turmas de uma escola.")
    from .models import Turma

    return Turma.objects.filter(escola_id=context.escola_id)
