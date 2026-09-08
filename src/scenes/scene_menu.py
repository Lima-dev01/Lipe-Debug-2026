"""
scene_menu.py
Gerencia 3 telas via sub-estado interno:
  SUB_MENU        → botões Jogar / Sobre / Sair
  SUB_MODE_SELECT → sozinho ou 2 grupos
  SUB_ABOUT       → tela Sobre
"""
import sys
import pygame
from src.game_state import GameState, State
from src.assets     import render_text, load_image
from src.config     import CONFIG

# ── Paleta ────────────────────────────────────────────────────────────────────
C_BG_TOP    = (13,  7,  32)
C_BG_BOT    = (20, 14, 52)
C_YELLOW    = (255, 227, 69)
C_YELLOW_DK = (160,  96,  0)
C_TEAL      = (124, 255, 203)
C_WHITE     = (255, 255, 255)
C_GRAY      = (160, 160, 180)
C_RED_SOFT  = (200,  80,  80)
C_PANEL     = ( 18,  10,  48, 220)   # RGBA

WIN_W = CONFIG["window"]["width"]
WIN_H = CONFIG["window"]["height"]

# Sub-estados internos
SUB_MENU        = "menu"
SUB_MODE_SELECT = "mode"
SUB_ABOUT       = "about"


def _draw_gradient(surf: pygame.Surface):
    """Fundo gradiente vertical escuro."""
    for y in range(WIN_H):
        t = y / WIN_H
        r = int(C_BG_TOP[0] + (C_BG_BOT[0] - C_BG_TOP[0]) * t)
        g = int(C_BG_TOP[1] + (C_BG_BOT[1] - C_BG_TOP[1]) * t)
        b = int(C_BG_TOP[2] + (C_BG_BOT[2] - C_BG_TOP[2]) * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (WIN_W, y))


def _draw_stars(surf: pygame.Surface, tick: int):
    """Estrelas simples piscando no fundo."""
    import math
    positions = [
        (80, 60), (200, 30), (350, 80), (500, 20), (650, 55),
        (750, 35), (100, 150), (300, 120), (600, 100), (720, 140),
        (160, 420), (420, 440), (560, 410), (680, 460), (820, 430),
    ]
    for i, (x, y) in enumerate(positions):
        alpha = int(128 + 127 * math.sin((tick * 0.03) + i * 0.7))
        r = max(0, min(255, alpha))
        pygame.draw.circle(surf, (r, r, r), (x, y), 2)


def _panel(surf: pygame.Surface, rect: pygame.Rect,
           border_color=C_YELLOW, radius=16):
    """Painel semitransparente com borda arredondada."""
    panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    panel.fill((18, 10, 48, 210))
    pygame.draw.rect(panel, (*border_color, 255),
                     (0, 0, rect.w, rect.h), 3, border_radius=radius)
    surf.blit(panel, rect.topleft)


class Button:
    def __init__(self, rect: pygame.Rect, label: str,
                 bg=C_YELLOW, fg=C_BG_TOP, hover_scale=1.05):
        self.rect        = rect
        self.label       = label
        self.bg          = bg
        self.fg          = fg
        self.hover_scale = hover_scale
        self._hovered    = False

    def draw(self, surf: pygame.Surface):
        r = self.rect
        if self._hovered:
            inflate = int(r.w * (self.hover_scale - 1))
            r = r.inflate(inflate, inflate // 2)

        pygame.draw.rect(surf, self.bg, r, border_radius=14)
        txt = render_text(self.label, 20, self.fg, bold=True)
        surf.blit(txt, txt.get_rect(center=r.center))

    def update(self, mouse_pos):
        self._hovered = self.rect.collidepoint(mouse_pos)

    def is_clicked(self, event) -> bool:
        return (event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.rect.collidepoint(event.pos))


class ModeCard:
    def __init__(self, rect: pygame.Rect, icon: str,
                 title: str, desc: str):
        self.rect     = rect
        self.icon     = icon
        self.title    = title
        self.desc     = desc
        self._hovered = False

    def draw(self, surf: pygame.Surface):
        border = C_YELLOW if self._hovered else (80, 80, 120)
        panel  = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        panel.fill((18, 10, 48, 220))
        pygame.draw.rect(panel, (*border, 255),
                         (0, 0, self.rect.w, self.rect.h), 3, border_radius=18)
        surf.blit(panel, self.rect.topleft)

        # Ícone
        icon_txt = render_text(self.icon, 52, C_WHITE)
        surf.blit(icon_txt, icon_txt.get_rect(
            centerx=self.rect.centerx, top=self.rect.top + 20))

        # Título
        title_txt = render_text(self.title, 22, C_YELLOW, bold=True,
                                shadow=True, shadow_color=(0, 0, 0))
        surf.blit(title_txt, title_txt.get_rect(
            centerx=self.rect.centerx, top=self.rect.top + 90))

        # Descrição (quebra linha manual)
        words = self.desc.split()
        lines, line = [], []
        for w in words:
            line.append(w)
            if len(" ".join(line)) > 28:
                lines.append(" ".join(line[:-1]))
                line = [w]
        lines.append(" ".join(line))

        for j, ln in enumerate(lines):
            t = render_text(ln, 14, C_GRAY)
            surf.blit(t, t.get_rect(
                centerx=self.rect.centerx,
                top=self.rect.top + 126 + j * 18))

    def update(self, mouse_pos):
        self._hovered = self.rect.collidepoint(mouse_pos)

    def is_clicked(self, event) -> bool:
        return (event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.rect.collidepoint(event.pos))


class SceneMenu:
    def __init__(self, lipe_surface: pygame.Surface = None):
        self.sub    = SUB_MENU
        self._tick  = 0
        self._lipe  = lipe_surface   # Surface do LIPE com alpha (pode ser None)

        # ── Botões do menu principal ──
        bw, bh, bx = 260, 52, 60
        self._btn_play  = Button(pygame.Rect(bx, 300, bw, bh), "▶  Jogar",
                                 bg=C_YELLOW, fg=C_BG_TOP)
        self._btn_about = Button(pygame.Rect(bx, 364, bw, bh), "ℹ  Sobre",
                                 bg=(50, 40, 90), fg=C_WHITE)
        self._btn_quit  = Button(pygame.Rect(bx, 428, bw, bh), "✕  Sair",
                                 bg=(80, 30, 30), fg=(255, 140, 140))
        self._menu_buttons = [self._btn_play, self._btn_about, self._btn_quit]

        # ── Cards de modo ──
        cw, ch = 340, 200
        cx1 = WIN_W // 2 - cw - 20
        cx2 = WIN_W // 2 + 20
        cy  = WIN_H // 2 - ch // 2 + 20
        self._card_solo  = ModeCard(
            pygame.Rect(cx1, cy, cw, ch),
            "🧍", "Jogar Sozinho",
            "Um jogador enfrenta os dois quartos e tenta a maior pontuação!"
        )
        self._card_group = ModeCard(
            pygame.Rect(cx2, cy, cw, ch),
            "👥", "Em 2 Grupos",
            "Dois grupos competem. Pode ser 1×1 ou vários×vários. Quem arruma mais?"
        )
        bw2 = 160
        self._btn_back = Button(
            pygame.Rect(WIN_W // 2 - bw2 // 2, cy + ch + 20, bw2, 44),
            "← Voltar", bg=(50, 40, 90), fg=C_WHITE
        )

        # ── Botão voltar (Sobre) ──
        self._btn_back_about = Button(
            pygame.Rect(WIN_W // 2 - 80, WIN_H - 70, 160, 44),
            "← Voltar", bg=C_YELLOW, fg=C_BG_TOP
        )

    # ── API pública ───────────────────────────────────────────────────────────
    def handle_event(self, event: pygame.event.Event,
                     gs: GameState) -> None:
        if self.sub == SUB_MENU:
            if self._btn_play.is_clicked(event):
                self.sub = SUB_MODE_SELECT
            elif self._btn_about.is_clicked(event):
                self.sub = SUB_ABOUT
            elif self._btn_quit.is_clicked(event):
                pygame.quit(); sys.exit()

        elif self.sub == SUB_MODE_SELECT:
            if self._card_solo.is_clicked(event):
                gs.n_players = 1
                gs.go(State.INTRO_1)
            elif self._card_group.is_clicked(event):
                gs.n_players = 2
                gs.go(State.INTRO_1)
            elif self._btn_back.is_clicked(event):
                self.sub = SUB_MENU

        elif self.sub == SUB_ABOUT:
            if self._btn_back_about.is_clicked(event):
                self.sub = SUB_MENU

        # ESC volta ao menu
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.sub = SUB_MENU

    def update(self, mouse_pos: tuple):
        self._tick += 1
        if self.sub == SUB_MENU:
            for b in self._menu_buttons:
                b.update(mouse_pos)
        elif self.sub == SUB_MODE_SELECT:
            self._card_solo.update(mouse_pos)
            self._card_group.update(mouse_pos)
            self._btn_back.update(mouse_pos)
        elif self.sub == SUB_ABOUT:
            self._btn_back_about.update(mouse_pos)

    def draw(self, surf: pygame.Surface):
        _draw_gradient(surf)
        _draw_stars(surf, self._tick)

        if self.sub == SUB_MENU:
            self._draw_menu(surf)
        elif self.sub == SUB_MODE_SELECT:
            self._draw_mode_select(surf)
        elif self.sub == SUB_ABOUT:
            self._draw_about(surf)

    # ── Sub-desenhos ──────────────────────────────────────────────────────────
    def _draw_menu(self, surf: pygame.Surface):
        # LIPE grande à direita
        if self._lipe:
            lh = int(WIN_H * 0.88)
            lw = int(self._lipe.get_width() * lh / self._lipe.get_height())
            scaled = pygame.transform.smoothscale(self._lipe, (lw, lh))
            surf.blit(scaled, (WIN_W - lw + 30, WIN_H - lh))

        # Título
        t1 = render_text("JOGO DO LIPE", 52, C_YELLOW, bold=True,
                         shadow=True, shadow_color=C_YELLOW_DK)
        surf.blit(t1, (60, 180))
        t2 = render_text("Pensamento Computacional na vida real", 16, C_GRAY)
        surf.blit(t2, (62, 240))

        # Botões
        for b in self._menu_buttons:
            b.draw(surf)

    def _draw_mode_select(self, surf: pygame.Surface):
        # Título
        title = render_text("Como vocês vão jogar?", 32, C_YELLOW, bold=True,
                            shadow=True, shadow_color=(0, 0, 0))
        surf.blit(title, title.get_rect(centerx=WIN_W // 2, top=60))

        self._card_solo.draw(surf)
        self._card_group.draw(surf)
        self._btn_back.draw(surf)

    def _draw_about(self, surf: pygame.Surface):
        # Painel
        pw, ph = 700, 340
        pr = pygame.Rect(WIN_W // 2 - pw // 2, WIN_H // 2 - ph // 2, pw, ph)
        _panel(surf, pr, border_color=C_TEAL)

        # LIPE pequeno
        if self._lipe:
            lh = 200
            lw = int(self._lipe.get_width() * lh / self._lipe.get_height())
            scaled = pygame.transform.smoothscale(self._lipe, (lw, lh))
            surf.blit(scaled, (pr.left + 20, pr.centery - lh // 2))
            tx = pr.left + lw + 40
        else:
            tx = pr.left + 20

        # Textos
        lines = [
            ("Sobre o Jogo do LIPE", 22, C_TEAL,   True),
            ("", 8, C_WHITE, False),
            ("Jogo educacional que ensina Pensamento", 14, C_WHITE, False),
            ("Computacional para crianças usando", 14, C_WHITE, False),
            ("gestos capturados pela câmera.", 14, C_WHITE, False),
            ("", 8, C_WHITE, False),
            ("IFRS – Campus Ibirubá", 14, C_TEAL, True),
            ("Projeto de pesquisa acadêmica, 2026.", 13, C_GRAY, False),
            ("", 8, C_WHITE, False),
            ("🧩 Decomposição   🔍 Padrões", 13, C_YELLOW, False),
            ("💡 Abstração       ⚙️ Algoritmo", 13, C_YELLOW, False),
        ]
        y = pr.top + 30
        for text, size, color, bold in lines:
            t = render_text(text, size, color, bold=bold)
            surf.blit(t, (tx, y))
            y += size + 6

        self._btn_back_about.draw(surf)