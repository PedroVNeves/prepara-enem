"""Fórmulas do modelo 3PL — compartilhadas entre o relatório, a seleção de
simulados por banda de dificuldade e a futura calibração TRI."""

import math


def probability_correct(a, b, c, theta):
    """P(theta) — probabilidade de acerto do modelo 3PL."""
    return c + (1 - c) / (1 + math.exp(-a * (theta - b)))


def item_information(a, b, c, theta):
    """Função de informação do item 3PL — quanto o item reduz a incerteza
    sobre theta no nível de habilidade atual do aluno. Usada para rankear o
    impacto de cada erro na proficiência estimada."""
    p = probability_correct(a, b, c, theta)
    q = 1 - p
    if p <= 0 or c >= 1:
        return 0.0
    return (a**2) * (q / p) * (((p - c) / (1 - c)) ** 2)
