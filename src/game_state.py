from enum import Enum, auto

class State(Enum):
    MENU        = auto()   # tela inicial (Jogar / Sobre / Sair)
    MODE_SELECT = auto()   # sozinho ou 2 grupos
    INTRO_1     = auto()   # sala: avisa a mãe
    INTRO_2     = auto()   # sala: nervoso com o quarto
    DECOMP      = auto()   # pilar Decomposição
    PHASE_1     = auto()   # fase 1 — baú de brinquedos
    ABSTRACAO   = auto()   # pilar Abstração (transição)
    PHASE_2     = auto()   # fase 2 — cesto de roupas
    ALGORITMO   = auto()   # pilar Algoritmo
    RESULT      = auto()   # tela de resultado final
    ABOUT       = auto()   # tela Sobre

class GameState:
    def __init__(self):
        self.current   = State.MENU
        self.n_players = 1          # 1 ou 2 grupos
        self.scores    = [0, 0]     # pontuação de cada grupo

    def go(self, state: State):
        self.current = state

    def is_(self, state: State) -> bool:
        return self.current == state