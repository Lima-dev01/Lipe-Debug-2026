"""
scene_story.py
Cena de história (visual novel) lida de data/story.json.

Cada quadro tem: fundo, personagens (imagem, x, altura, base opcional),
quem fala, texto e retrato opcional. A cena:
  - desenha o fundo em modo "cover" e os personagens ancorados pelos pés
    com um leve movimento idle;
  - mostra o texto numa caixa embaixo com efeito de digitação;
  - avança por braço levantado (1º gesto completa o texto, 2º avança),
    com cooldown e exigindo baixar o braço entre gestos; ENTER, ESPAÇO,
    → ou clique fazem o mesmo (para testar sem câmera);
  - faz fade entre quadros, e de/para preto na entrada e na saída.

Quando o último quadro termina, `done` vira True e o main.py troca de estado.
Esta cena NÃO altera a detecção de gesto: só lê raise_left/raise_right.
"""
import json
import math
import os
import pygame

from src.config  import CONFIG
from src.gesture import GestureDetector
from src import assets
from src.assets  import C_UI_DARK, C_UI_LIGHT

WIN_W = CONFIG["window"]["width"]
WIN_H = CONFIG["window"]["height"]
UI_SCALE = WIN_W / 800


def S(value: float) -> int:
    """Escala um valor pensado para 800x600 até a resolução interna atual."""
    return round(value * UI_SCALE)


# ── Ajustes (tempos em segundos — não escalam) ────────────────────────────────
CHARS_PER_SECOND = 38      # velocidade da digitação
ADVANCE_COOLDOWN = 0.7     # tempo mínimo entre dois acionamentos
FADE_SECONDS     = 0.35    # fade entre quadros / entrada / saída
DEFAULT_BASE     = 0.80    # linha dos pés (fração da altura) se o quadro não disser
IDLE_AMPLITUDE   = 0.006   # balanço idle (fração da altura da tela)
SPEAKER_BOOST    = 1.8     # quem fala balança um pouco mais

# ── Caixa de diálogo (valores de referência 800x600) ──────────────────────────
BOX_MARGIN_X   = 24
BOX_MARGIN_BOT = 18
BOX_HEIGHT     = 120
BOX_PADDING    = 18
TEXT_SIZE      = 26
NAME_SIZE      = 20
LINE_GAP       = 6

_STORY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "story.json")
_story_cache: dict | None = None


def load_story() -> dict:
    """Lê data/story.json uma vez (cache). Erro de leitura não derruba o jogo."""
    global _story_cache
    if _story_cache is None:
        try:
            with open(_STORY_PATH, "r", encoding="utf-8") as f:
                _story_cache = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"[AVISO] Não foi possível ler data/story.json: {e}")
            _story_cache = {"nomes": {}, "cenas": {}}
    return _story_cache


def _wrap(text: str, fnt: pygame.font.Font, max_w: int) -> list[str]:
    """Quebra o texto em linhas que cabem em max_w (por palavra)."""
    lines, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if fnt.size(test)[0] <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class SceneStory:
    def __init__(self, key: str):
        self.key     = key                      # ex.: "INTRO_1" (= State.name)
        story        = load_story()
        self._names  = story.get("nomes", {})
        self._frames = story.get("cenas", {}).get(key, [])
        if not self._frames:
            print(f"[AVISO] Cena '{key}' sem quadros no story.json — pulando.")

        self._font_text = assets.font(S(TEXT_SIZE), bold=True)
        self._font_name = assets.font(S(NAME_SIZE), bold=True)
        self._font_hint = assets.font(S(14))

        self._box = pygame.Rect(S(BOX_MARGIN_X), WIN_H - S(BOX_MARGIN_BOT) - S(BOX_HEIGHT),
                                WIN_W - 2 * S(BOX_MARGIN_X), S(BOX_HEIGHT))

        self._index      = 0
        self._typed      = 0.0              # caracteres já revelados
        self._time       = 0.0              # relógio do idle
        self._cooldown   = 0.0
        self._prev_raise = True             # exige baixar o braço antes do 1º gesto
        self._done       = False

        # Fade: "in" (entrando), "show", "out" (saindo da cena)
        self._fade_state = "in"
        self._fade_t     = FADE_SECONDS
        self._snapshot: pygame.Surface | None = None   # imagem anterior p/ crossfade
        self._black      = pygame.Surface((WIN_W, WIN_H)).convert()
        self._black.fill((0, 0, 0))
        self._snapshot   = self._black

        self._preload()
        self._layout_text()

    # ── API pública ───────────────────────────────────────────────────────────
    @property
    def done(self) -> bool:
        return self._done or not self._frames

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_RETURN, pygame.K_SPACE, pygame.K_RIGHT):
            self._advance()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._advance()

    def update(self, dt: float, gesture: GestureDetector):
        if self.done:
            return
        self._time     += dt
        self._cooldown  = max(0.0, self._cooldown - dt)

        # Gesto: borda de subida de qualquer braço
        raise_now = gesture.raise_right or gesture.raise_left
        if raise_now and not self._prev_raise:
            self._advance()
        self._prev_raise = raise_now

        if self._fade_state in ("in", "out"):
            self._fade_t -= dt
            if self._fade_t <= 0:
                if self._fade_state == "out":
                    self._done = True
                    return
                self._fade_state = "show"
                self._snapshot   = None
            return                              # texto só digita depois do fade

        self._typed = min(self._text_len, self._typed + CHARS_PER_SECOND * dt)

    def draw(self, surf: pygame.Surface):
        if not self._frames:
            surf.fill((0, 0, 0))
            return
        self._draw_frame(surf)
        if self._snapshot is not None and self._fade_t > 0:
            a = self._fade_t / FADE_SECONDS
            if self._fade_state == "out":       # saindo: escurece até o preto
                a = 1.0 - a
            self._snapshot.set_alpha(round(255 * a))
            surf.blit(self._snapshot, (0, 0))

    # ── Avanço ────────────────────────────────────────────────────────────────
    @property
    def _frame(self) -> dict:
        return self._frames[self._index]

    def _text_complete(self) -> bool:
        return self._typed >= self._text_len

    def _advance(self):
        if self.done or self._fade_state != "show" or self._cooldown > 0:
            return
        self._cooldown = ADVANCE_COOLDOWN
        if not self._text_complete():
            self._typed = self._text_len
            return
        if self._index + 1 >= len(self._frames):
            self._fade_state, self._fade_t = "out", FADE_SECONDS
            self._snapshot = self._black
            return
        # Crossfade: guarda o quadro atual e troca para o próximo
        snap = pygame.Surface((WIN_W, WIN_H)).convert()
        self._draw_frame(snap)
        self._snapshot   = snap
        self._index     += 1
        self._typed      = 0.0
        self._fade_state, self._fade_t = "in", FADE_SECONDS
        self._layout_text()

    # ── Preparação ────────────────────────────────────────────────────────────
    def _preload(self):
        """Escala tudo da cena na entrada, para não travar no meio dela."""
        for fr in self._frames:
            assets.background_cover(fr.get("fundo", ""), (WIN_W, WIN_H))
            for p in fr.get("personagens", []):
                assets.character_sprite(p["imagem"], round(p.get("altura", 0.6) * WIN_H))
            if fr.get("retrato"):
                assets.portrait(fr["retrato"], self._portrait_h())

    def _portrait_h(self) -> int:
        return self._box.h - 2 * S(BOX_PADDING) + S(10)

    def _text_left(self) -> int:
        left = self._box.x + S(BOX_PADDING)
        if self._frames and self._frame.get("retrato"):
            left += assets.portrait(self._frame["retrato"], self._portrait_h()).get_width() + S(12)
        return left

    def _layout_text(self):
        self._lines, self._text_len = [], 0
        if not self._frames:
            return
        max_w = self._box.right - S(BOX_PADDING) - self._text_left()
        self._lines = _wrap(self._frame.get("texto", ""), self._font_text, max_w)
        self._text_len = len(" ".join(self._lines))

    # ── Desenho ───────────────────────────────────────────────────────────────
    def _draw_frame(self, surf: pygame.Surface):
        fr = self._frame
        surf.blit(assets.background_cover(fr.get("fundo", ""), (WIN_W, WIN_H)), (0, 0))

        speaker = fr.get("fala", "")
        for i, p in enumerate(fr.get("personagens", [])):
            sprite, (ax, ay) = assets.character_sprite(
                p["imagem"], round(p.get("altura", 0.6) * WIN_H))
            amp = IDLE_AMPLITUDE * WIN_H
            if speaker and p["imagem"].split("/")[0] == speaker:
                amp *= SPEAKER_BOOST
            bob = math.sin(self._time * 2.2 + i * 1.3) * amp
            x = round(p.get("x", 0.5) * WIN_W) - ax
            y = round(p.get("base", DEFAULT_BASE) * WIN_H + bob) - ay
            surf.blit(sprite, (x, y))

        self._draw_box(surf, fr)

    def _draw_box(self, surf: pygame.Surface, fr: dict):
        box, r = self._box, S(16)

        panel = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (*C_UI_DARK, 235), panel.get_rect(), border_radius=r)
        pygame.draw.rect(panel, C_UI_LIGHT, panel.get_rect(), S(3), border_radius=r)
        surf.blit(panel, box.topleft)

        # Retrato (opcional), apoiado no canto inferior esquerdo da caixa
        if fr.get("retrato"):
            pt = assets.portrait(fr["retrato"], self._portrait_h())
            surf.blit(pt, (box.x + S(BOX_PADDING), box.bottom - S(3) - pt.get_height()))

        # Etiqueta com o nome de quem fala, por cima da borda
        name = self._names.get(fr.get("fala", ""), fr.get("fala", ""))
        if name:
            nt  = self._font_name.render(name, True, C_UI_DARK)
            tag = pygame.Rect(0, 0, nt.get_width() + S(28), nt.get_height() + S(8))
            tag.bottomleft = (self._text_left() - S(6), box.top + S(10))
            pygame.draw.rect(surf, C_UI_LIGHT, tag, border_radius=S(10))
            pygame.draw.rect(surf, C_UI_DARK, tag, S(2), border_radius=S(10))
            surf.blit(nt, nt.get_rect(center=tag.center))

        # Texto com digitação (quebra calculada no texto inteiro → nada "pula")
        remaining = int(self._typed)
        y = box.top + S(BOX_PADDING) + S(8)
        for line in self._lines:
            if remaining <= 0:
                break
            shown = line[:remaining]
            remaining -= len(line) + 1          # +1 = espaço que virou quebra
            surf.blit(self._font_text.render(shown, True, C_UI_LIGHT),
                      (self._text_left(), y))
            y += self._font_text.get_linesize() + S(LINE_GAP)

        # Indicador "pode avançar" piscando
        if self._fade_state == "show" and self._text_complete():
            if int(self._time * 2.5) % 2 == 0:
                cx, cy = box.right - S(26), box.bottom - S(20)
                pygame.draw.polygon(surf, C_UI_LIGHT,
                                    [(cx - S(9), cy - S(6)), (cx + S(9), cy - S(6)), (cx, cy + S(6))])
            hint = self._font_hint.render("levante o braço para continuar", True, C_UI_LIGHT)
            hint.set_alpha(170)
            surf.blit(hint, (box.right - S(42) - hint.get_width(), box.bottom - S(28)))