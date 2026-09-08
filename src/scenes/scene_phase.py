"""
scene_phase.py — V1
Mecânica central:
  - Objetos (emoji) passam da direita para esquerda em trilhas
  - Baú (fase 1) ou Cesto (fase 2) centralizado na tela
  - Levantar o braço direito → objeto cai de onde estiver
  - Se estiver sobre o recipiente → ACERTO (some + feedback)
  - Se não estiver → ERRO (cai no chão + feedback)
  - Sem pontuação ainda (V1)
"""
import pygame
import random
from src.config          import CONFIG
from src.gesture         import GestureDetector
from src.emoji_renderer  import emoji_surface, preload

WIN_W = CONFIG["window"]["width"]
WIN_H = CONFIG["window"]["height"]

# ── Paleta ────────────────────────────────────────────────────────────────────
C_BG       = (15, 8, 38)
C_YELLOW   = (255, 227, 69)
C_TEAL     = (124, 255, 203)
C_RED      = (220,  70,  70)
C_WHITE    = (255, 255, 255)
C_GRAY     = (140, 140, 160)
C_PANEL    = ( 18,  10,  48)

# ── Objetos por fase ──────────────────────────────────────────────────────────
PHASE_CONFIG = {
    1: {
        "target_emoji": "🪣",
        "target_label": "BAÚ DE BRINQUEDOS",
        "correct":   ["🚗", "🎮", "🧸", "⚽", "🎯", "🪀", "🎲", "🏓"],
        "incorrect": ["👕", "🧦", "👗", "🧥", "🧤", "🧣"],
        "badge":     "🧸 Coloque os BRINQUEDOS no Baú!",
        "badge_color": C_YELLOW,
    },
    2: {
        "target_emoji": "🧺",
        "target_label": "CESTO DE ROUPAS",
        "correct":   ["👕", "🧦", "👗", "🧥", "🧤", "🧣"],
        "incorrect": ["🚗", "🎮", "🧸", "⚽", "🎯", "🪀"],
        "badge":     "🧺 Coloque as ROUPAS no Cesto!",
        "badge_color": C_TEAL,
    },
}

# ── Trilhas verticais dos objetos ─────────────────────────────────────────────
TRACKS = [105, 165, 225, 285]   # y de cada trilha (abaixo do HUD)

OBJECT_SPEED   = 180   # px/s na horizontal
FALL_SPEED     = 400   # px/s na queda
HIT_RADIUS     = 90    # px — raio de acerto ao redor do centro do alvo
SPAWN_INTERVAL = 1.8   # segundos entre spawns
FONT_SIZE_OBJ  = 52    # tamanho do emoji do objeto
FONT_SIZE_TGT  = 110   # tamanho do emoji do recipiente


class FallingObject:
    """Um objeto que passa pela tela e pode ser derrubado."""

    def __init__(self, emoji: str, is_correct: bool, track_y: int):
        self.emoji      = emoji
        self.is_correct = is_correct
        self.x          = float(WIN_W + 60)
        self.y          = float(track_y)
        self.track_y    = track_y
        self.state    = "moving"   # moving | falling | done
        self.vy       = 0.0
        self.alpha    = 255
        self.will_hit = False   # definido no momento do drop

    def drop(self, target_cx: int, hit_margin: int = 40):
        """
        Jogador levantou o braço.
        Define na hora se vai acertar (x dentro da margem do alvo).
        A queda é sempre reta — sem desvio horizontal.
        """
        if self.state == "moving":
            self.state    = "falling"
            self.vy       = 0.0
            self.will_hit = abs(self.x - target_cx) <= hit_margin

    def update(self, dt: float) -> bool:
        """Retorna True quando o objeto deve ser removido."""
        if self.state == "moving":
            self.x -= OBJECT_SPEED * dt
            if self.x < -80:
                self.state = "done"

        elif self.state == "falling":
            self.vy += 900 * dt   # gravidade — x não muda
            self.y  += self.vy * dt
            if self.y > WIN_H - 60:
                self.alpha = max(0, self.alpha - 400 * dt)
                if self.alpha == 0:
                    self.state = "done"

        return self.state == "done"

    def get_rect(self) -> pygame.Rect:
        """Rect aproximado do emoji para colisão."""
        return pygame.Rect(int(self.x) - 28, int(self.y) - 28, 56, 56)


class Feedback:
    """Texto flutuante de acerto/erro."""
    def __init__(self, text: str, color, cx: int, cy: int):
        self.text  = text
        self.color = color
        self.x     = cx
        self.y     = float(cy)
        self.life  = 1.2   # segundos
        self.alpha = 255

    def update(self, dt: float) -> bool:
        self.y    -= 60 * dt
        self.life -= dt
        self.alpha = max(0, int(255 * (self.life / 1.2)))
        return self.life <= 0


class ScenePhase:
    def __init__(self, phase: int, lipe_surface: pygame.Surface = None):
        self.phase   = phase
        self._lipe   = lipe_surface
        self._cfg    = PHASE_CONFIG[phase]

        # Fontes (só para UI — emojis usam emoji_renderer)
        self._font_ui    = pygame.font.SysFont("Arial", 18, bold=True)
        self._font_small = pygame.font.SysFont("Arial", 14)
        self._font_badge = pygame.font.SysFont("Arial", 17, bold=True)
        self._font_fb    = pygame.font.SysFont("Arial", 38, bold=True)

        # Pré-carrega todos os emojis desta fase
        all_emojis = (self._cfg["correct"] + self._cfg["incorrect"]
                      + [self._cfg["target_emoji"]])
        preload(all_emojis, size=FONT_SIZE_OBJ)
        preload([self._cfg["target_emoji"]], size=FONT_SIZE_TGT)

        # Recipiente central — 80px abaixo do centro
        self._target_rect = pygame.Rect(
            WIN_W // 2 - 70, WIN_H // 2 + 30, 140, 140
        )
        self._target_surf = emoji_surface(
            self._cfg["target_emoji"], size=FONT_SIZE_TGT
        )

        # Estado
        self._objects: list[FallingObject] = []
        self._feedbacks: list[Feedback]    = []
        self._spawn_timer  = 0.0
        self._prev_raise   = False
        self._done         = False
        self._flash        = 0.0
        self._flash_color  = C_TEAL
        self._tick         = 0
        self._webcam_surf: pygame.Surface | None = None   # frame atual da câmera

    # ── API pública ───────────────────────────────────────────────────────────
    @property
    def done(self) -> bool:
        return self._done

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._done = True

    def update(self, dt: float, gesture: GestureDetector,
               cam_packet: dict | None = None):
        self._tick += 1

        # Atualiza frame da webcam
        if cam_packet is not None:
            import numpy as np
            import cv2
            frame = cam_packet["frame_rgb"]
            h, w  = frame.shape[:2]
            # Redimensiona para o tamanho do overlay (160×120)
            frame_small = cv2.resize(frame, (160, 120))
            self._webcam_surf = pygame.surfarray.make_surface(
                frame_small.swapaxes(0, 1)
            )
        self._tick += 1

        # ── Spawn ────────────────────────────────────────────────────────────
        self._spawn_timer -= dt
        if self._spawn_timer <= 0:
            self._spawn_object()
            self._spawn_timer = SPAWN_INTERVAL

        # ── Gesto: borda de subida do braço direito ───────────────────────────
        raise_now  = gesture.raise_right
        just_raised = raise_now and not self._prev_raise
        self._prev_raise = raise_now

        if just_raised:
            self._drop_nearest()

        # ── Atualiza objetos ──────────────────────────────────────────────────
        to_remove = []
        for obj in self._objects:
            finished = obj.update(dt)

            # Verifica colisão com recipiente durante queda
            if obj.state == "falling":
                self._check_collision(obj)

            if finished:
                to_remove.append(obj)

        for obj in to_remove:
            self._objects.remove(obj)

        # ── Atualiza feedbacks ────────────────────────────────────────────────
        self._feedbacks = [f for f in self._feedbacks if not f.update(dt)]

        # ── Flash ─────────────────────────────────────────────────────────────
        if self._flash > 0:
            self._flash = max(0.0, self._flash - dt)

    def draw(self, surf: pygame.Surface):
        # Fundo escuro
        surf.fill(C_BG)

        # Flash de feedback
        if self._flash > 0:
            alpha = int(120 * (self._flash / 0.25))
            flash_surf = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            flash_surf.fill((*self._flash_color, alpha))
            surf.blit(flash_surf, (0, 0))

        # Trilhas (linhas sutis)
        for y in TRACKS:
            pygame.draw.line(surf, (40, 35, 70), (0, y), (WIN_W, y), 1)

        # Recipiente central (emoji grande + brilho)
        self._draw_target(surf)

        # Objetos
        for obj in self._objects:
            self._draw_object(surf, obj)

        # Feedbacks flutuantes
        for fb in self._feedbacks:
            fb_surf = self._font_fb.render(fb.text, True, fb.color)
            fb_surf.set_alpha(fb.alpha)
            surf.blit(fb_surf, fb_surf.get_rect(
                centerx=WIN_W // 2, centery=int(fb.y)))

        # HUD topo
        self._draw_hud(surf)

        # Badge de instrução
        self._draw_badge(surf)

        # Webcam — canto inferior esquerdo
        self._draw_webcam(surf)

        # Indicador de braço (debug visual)
        self._draw_arm_indicator(surf)

        # Dica ENTER
        hint = self._font_small.render(
            "ENTER → próxima fase (temporário)", True, (80, 80, 100))
        surf.blit(hint, (WIN_W - hint.get_width() - 10, WIN_H - 22))

    # ── Internos ──────────────────────────────────────────────────────────────
    def _spawn_object(self):
        all_items = (
            [(e, True)  for e in self._cfg["correct"]] +
            [(e, False) for e in self._cfg["incorrect"]]
        )
        emoji, is_correct = random.choice(all_items)
        track = random.choice(TRACKS)
        self._objects.append(FallingObject(emoji, is_correct, track))

    def _drop_nearest(self):
        """Derruba o objeto mais próximo do centro horizontal."""
        candidates = [o for o in self._objects if o.state == "moving"]
        if not candidates:
            return
        nearest = min(candidates, key=lambda o: abs(o.x - WIN_W // 2))
        nearest.drop(target_cx=self._target_rect.centerx, hit_margin=40)

    def _check_collision(self, obj: FallingObject):
        """
        Resultado definido no drop() pelo x do objeto.
        Aqui só espera o objeto chegar na altura do alvo para
        disparar o feedback — sem depender de colisão frame a frame.
        """
        if obj.state != "falling":
            return
        # Aguarda o objeto atingir o centro vertical do alvo
        if obj.y < self._target_rect.centery:
            return

        if obj.will_hit:
            if obj.is_correct:
                self._on_hit(obj)
            else:
                self._on_miss(obj)
        # Se will_hit=False o objeto continua caindo e some no chão

    def _on_hit(self, obj: FallingObject):
        obj.state = "done"
        self._feedbacks.append(
            Feedback("+2 ✓", C_TEAL, WIN_W // 2, WIN_H // 2 - 80))
        self._flash       = 0.25
        self._flash_color = C_TEAL

    def _on_miss(self, obj: FallingObject):
        obj.state = "done"
        self._feedbacks.append(
            Feedback("ERROU! ✗", C_RED, WIN_W // 2, WIN_H // 2 - 80))
        self._flash       = 0.25
        self._flash_color = C_RED

    def _draw_target(self, surf: pygame.Surface):
        import math
        # Anel pulsante
        pulse = 0.85 + 0.15 * math.sin(self._tick * 0.05)
        r = int(90 * pulse)
        ring_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(ring_surf, (*C_YELLOW, 60),
                           (r + 2, r + 2), r, 3)
        surf.blit(ring_surf, (
            self._target_rect.centerx - r - 2,
            self._target_rect.centery - r - 2,
        ))

        # Emoji do recipiente
        surf.blit(self._target_surf, self._target_surf.get_rect(
            center=self._target_rect.center))

        # Label
        lbl = self._font_ui.render(
            self._cfg["target_label"], True, C_YELLOW)
        surf.blit(lbl, lbl.get_rect(
            centerx=self._target_rect.centerx,
            top=self._target_rect.bottom + 8))

    def _draw_object(self, surf: pygame.Surface, obj: FallingObject):
        txt = emoji_surface(obj.emoji, size=FONT_SIZE_OBJ).copy()
        txt.set_alpha(obj.alpha)
        surf.blit(txt, txt.get_rect(
            centerx=int(obj.x), centery=int(obj.y)))

        # Sombra embaixo do objeto
        if obj.state == "moving":
            shadow = pygame.Surface((50, 10), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 60), shadow.get_rect())
            surf.blit(shadow, (int(obj.x) - 25, obj.track_y + 28))

    def _draw_hud(self, surf: pygame.Surface):
        hud = pygame.Surface((WIN_W, 50), pygame.SRCALPHA)
        hud.fill((8, 4, 24, 210))
        surf.blit(hud, (0, 0))

        phase_txt = self._font_ui.render(
            f"FASE {self.phase}  —  {'Baú de Brinquedos 🧸' if self.phase == 1 else 'Cesto de Roupas 🧺'}",
            True, C_WHITE)
        surf.blit(phase_txt, (20, 14))

    def _draw_badge(self, surf: pygame.Surface):
        badge_txt = self._font_badge.render(self._cfg["badge"], True, C_BG)
        bw = badge_txt.get_width() + 30
        bh = badge_txt.get_height() + 10
        bx = WIN_W // 2 - bw // 2
        by = 58
        badge_bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        badge_bg.fill((*self._cfg["badge_color"], 230))
        pygame.draw.rect(badge_bg, C_BG, (0, 0, bw, bh), 2, border_radius=12)
        surf.blit(badge_bg, (bx, by))
        surf.blit(badge_txt, (bx + 15, by + 5))

    def _draw_webcam(self, surf: pygame.Surface):
        """Overlay da webcam no canto inferior esquerdo."""
        W, H = 160, 120
        x, y = 8, WIN_H - H - 8

        # Borda
        pygame.draw.rect(surf, (60, 60, 80),
                         (x - 2, y - 2, W + 4, H + 4), border_radius=8)

        if self._webcam_surf:
            surf.blit(self._webcam_surf, (x, y))
        else:
            # Placeholder enquanto câmera não chegou
            placeholder = pygame.Surface((W, H))
            placeholder.fill((20, 20, 35))
            txt = self._font_small.render("📷 câmera", True, (80, 80, 100))
            placeholder.blit(txt, txt.get_rect(center=(W // 2, H // 2)))
            surf.blit(placeholder, (x, y))

        # Label
        lbl = self._font_small.render("webcam", True, (100, 100, 120))
        surf.blit(lbl, (x, y - 16))

    def _draw_arm_indicator(self, surf: pygame.Surface):
        """Indicador visual de gesto no canto inferior direito."""
        color  = C_TEAL if self._prev_raise else (60, 60, 80)
        label  = "💪 BRAÇO LEVANTADO!" if self._prev_raise else "Levante o braço esquerdo"
        txt    = self._font_small.render(label, True, color)
        surf.blit(txt, (WIN_W - txt.get_width() - 14, WIN_H - 44))
        pygame.draw.circle(surf, color, (WIN_W - txt.get_width() - 26, WIN_H - 36), 6)