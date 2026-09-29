"""
score.py — Sistema de pontuação do Jogo do LIPE (V2)

Regra de pontuação (definida com base no feedback pedagógico do jogo):

    Item CERTO  cai no recipiente certo      -> +2  (ação correta)
    Item ERRADO é ignorado (não é derrubado) -> +1  (bom julgamento)
    Item CERTO  é ignorado / não entra       -> -1  (oportunidade perdida)
    Item ERRADO cai no recipiente            -> -2  (ação errada)

Este módulo é intencionalmente desacoplado do Pygame: não conhece
"objetos caindo", "trilhas" ou qualquer detalhe visual. Ele só recebe
fatos ("o item era do tipo certo?", "ele terminou dentro do alvo?")
e devolve pontuação. Isso facilita testes unitários e reuso — por
exemplo, quando o modo multiplayer (V4) precisar de um ScoreTracker
por grupo.
"""
from enum import Enum
from typing import Optional


class Outcome(Enum):
    """Um dos 4 resultados possíveis para um objeto resolvido."""
    HIT_CORRECT    = "hit_correct"     # item certo   -> caiu no alvo
    IGNORED_WRONG  = "ignored_wrong"   # item errado  -> não caiu no alvo
    MISSED_CORRECT = "missed_correct"  # item certo   -> não caiu no alvo
    HIT_WRONG      = "hit_wrong"       # item errado  -> caiu no alvo


# Pontos por resultado — única fonte de verdade para o balanceamento.
# Mudar o valor aqui é o suficiente para rebalancear o jogo inteiro.
POINTS: dict[Outcome, int] = {
    Outcome.HIT_CORRECT:    2,
    Outcome.IGNORED_WRONG:  1,
    Outcome.MISSED_CORRECT: -1,
    Outcome.HIT_WRONG:      -2,
}


def resolve_outcome(is_correct: bool, ended_in_target: bool) -> Outcome:
    """
    Traduz o estado final de um objeto (tipo + destino) em um Outcome.

    Args:
        is_correct:      True se o objeto era do tipo esperado pelo
                          recipiente da fase (ex.: brinquedo na fase 1).
        ended_in_target: True se o objeto foi derrubado E caiu dentro
                          da área do alvo (baú/cesto). False em qualquer
                          outro destino: passou direto pela tela, ou foi
                          derrubado mas caiu no chão fora do alvo.
    """
    if is_correct and ended_in_target:
        return Outcome.HIT_CORRECT
    if is_correct and not ended_in_target:
        return Outcome.MISSED_CORRECT
    if not is_correct and ended_in_target:
        return Outcome.HIT_WRONG
    return Outcome.IGNORED_WRONG


class ScoreTracker:
    """
    Mantém a pontuação de uma fase (ou, futuramente, de um grupo no
    modo multiplayer). Guarda também um contador por tipo de resultado,
    útil para a tela de resumo/resultado (V3).
    """

    def __init__(self) -> None:
        self.total: int = 0
        self._counts: dict[Outcome, int] = {outcome: 0 for outcome in Outcome}
        self.last_delta: int = 0
        self.last_outcome: Optional[Outcome] = None

    def register(self, is_correct: bool, ended_in_target: bool) -> int:
        """
        Registra o resultado de um objeto resolvido.

        Retorna o delta de pontos ganho/perdido nesta jogada, para que
        quem chamou possa usá-lo imediatamente (ex.: escolher a cor do
        feedback visual) sem precisar recalcular o outcome.
        """
        outcome = resolve_outcome(is_correct, ended_in_target)
        delta = POINTS[outcome]

        self.total += delta
        self._counts[outcome] += 1
        self.last_delta = delta
        self.last_outcome = outcome
        return delta

    def count(self, outcome: Outcome) -> int:
        """Quantas vezes um determinado outcome já ocorreu."""
        return self._counts[outcome]

    @property
    def resolved_count(self) -> int:
        """Total de objetos já resolvidos (soma de todos os contadores)."""
        return sum(self._counts.values())

    def summary(self) -> dict:
        """Resumo em dict simples, pronto para a tela de resultado (V3)."""
        return {
            "total":      self.total,
            "acertos":    self._counts[Outcome.HIT_CORRECT],
            "ignorados":  self._counts[Outcome.IGNORED_WRONG],
            "perdidos":   self._counts[Outcome.MISSED_CORRECT],
            "erros":      self._counts[Outcome.HIT_WRONG],
            "resolvidos": self.resolved_count,
        }