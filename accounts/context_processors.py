from .context import get_active_context


def active_context(request):
    """Expõe o contexto ativo (aluno/professor) em todo template, sem cada
    view precisar passar isso manualmente — o cabeçalho/nav em base.html
    depende disso pra saber quais links mostrar."""
    if not request.user.is_authenticated:
        return {}
    return {"active_context": get_active_context(request)}
