"""
gesture.py
Converte os pacotes da CameraThread em eventos de alto nível para o jogo.
Na V0 apenas loga/retorna o estado. Nas versões seguintes dispara eventos Pygame.
"""

from src.config import CONFIG

_debug = CONFIG["debug"]


class GestureDetector:

    def __init__(self):
        self.raise_right = False
        self.raise_left  = False

        # Edge detection — True somente no primeiro frame que muda
        self._prev_right = False
        self._prev_left  = False

    def update(self, packet: dict):
        """Recebe pacote da CameraThread e atualiza o estado interno."""
        if packet is None:
            return

        self.raise_right = packet["raise_right"]
        self.raise_left  = packet["raise_left"]

        if _debug:
            if self.raise_right and not self._prev_right:
                print("[GESTO] Braço DIREITO levantado ↑")
            elif not self.raise_right and self._prev_right:
                print("[GESTO] Braço direito abaixado ↓")

            if self.raise_left and not self._prev_left:
                print("[GESTO] Braço ESQUERDO levantado ↑")
            elif not self.raise_left and self._prev_left:
                print("[GESTO] Braço esquerdo abaixado ↓")

        self._prev_right = self.raise_right
        self._prev_left  = self.raise_left

    # Helpers de borda (úteis nas cenas de jogo)
    def just_raised_right(self) -> bool:
        return self.raise_right and not self._prev_right

    def just_raised_left(self) -> bool:
        return self.raise_left and not self._prev_left