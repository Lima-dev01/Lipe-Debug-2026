"""
scene_phase.py — V2
Mecânica central + pontuação e progressão da fase:

  - Contagem regressiva ("5, 4, 3, 2, 1... VAI!") antes de cada fase começar
  - Objetos (emoji) passam da direita para esquerda em trilhas
  - Baú (fase 1) ou Cesto (fase 2) centralizado na tela
  - Levantar o braço direito → objeto cai de onde estiver
  - Pontuação (via src.score.ScoreTracker) com 4 resultados possíveis:
        item certo  no alvo      -> +2
        item errado ignorado     -> +1
        item certo  ignorado     -> -1
        item errado no alvo      -> -2
  - Velocidade dos objetos sobe a cada 5 resolvidos, até 4 aumentos
  - Fase termina quando a velocidade atinge o teto e o último lote acaba

Todas as posições/tamanhos/velocidades em pixel foram pensadas para uma
resolução de referência de 800x600. Para suportar uma resolução interna
maior (ver settings.json -> window.width/height) sem redesenhar o
layout, cada valor espacial passa pelo helper S(), que aplica o fator
de escala UI_SCALE. Durações em segundos (timers, SPAWN_INTERVAL) NÃO
são escaladas — tempo não muda com resolução.
"""
import pygame
import random
from src.config          import CONFIG
from src.gesture         import GestureDetector
from src.emoji_renderer  import emoji_surface, preload
from src.score           import ScoreTracker, Outcome

WIN_W = CONFIG["window"]["width"]
WIN_H = CONFIG["window"]["height"]

# Resolução de referência do design original = 800x600.
UI_SCALE = WIN_W / 800


def S(value: float) -> int:
    """Escala um valor espacial pensado para 800x600 até a resolução atual."""
    return round(value * UI_SCALE)


# ── Paleta ────────────────────────────────────────────────────────────────────
C_BG       = (15, 8, 38)
C_YELLOW   = (255, 227, 69)
C_TEAL     = (124, 255, 203)
C_ORANGE   = (255, 170, 70)     # usado no feedback "-1" (oportunidade perdida)
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

# ── Trilhas verticais dos objetos (valores de referência 800x600) ────────────
TRACKS = [S(105), S(165), S(225), S(285)]   # y de cada trilha (abaixo do HUD)

GRAVITY        = S(900)  # px/s² de aceleração na queda
FALL_SPEED     = S(400)  # px/s — referência histórica (ver FallingObject)
HIT_RADIUS     = S(90)   # px — raio de acerto ao redor do centro do alvo
SPAWN_INTERVAL = 1.8     # segundos entre spawns — TEMPORAL, não escala
FONT_SIZE_OBJ  = S(52)   # tamanho do emoji do objeto
FONT_SIZE_TGT  = S(110)  # tamanho do emoji do recipiente

# ── Progressão de velocidade e duração da rodada ──────────────────────────────
# A velocidade sobe a cada OBJECTS_PER_LEVEL objetos resolvidos, até um teto
# de MAX_SPEED_INCREASES aumentos. A fase termina quando o teto é atingido E
# o lote de objetos daquele nível também termina.
OBJECTS_PER_LEVEL      = 5
MAX_SPEED_INCREASES    = 4
SPEED_LEVELS            = [S(v) for v in (180, 220, 260, 300, 340)]  # px/s
TOTAL_OBJECTS_PER_PHASE = OBJECTS_PER_LEVEL * (MAX_SPEED_INCREASES + 1)  # 25

# ── Contagem regressiva de início de fase (TEMPORAL — não escala) ────────────
COUNTDOWN_START           = 5      # "5, 4, 3, 2, 1"
COUNTDOWN_SECONDS_PER_NUM = 1.0    # segundos que cada número fica na tela
GO_FLASH_SECONDS          = 0.6    # duração do "VAI!" antes de liberar o jogo

# ── Texto/cor do feedback flutuante para cada resultado de pontuação ──────────
_FEEDBACK_BY_OUTCOME = {
    Outcome.HIT_CORRECT:    ("+2  ✓",  C_TEAL),
    Outcome.IGNORED_WRONG:  ("+1  👍", C_TEAL),
    Outcome.MISSED_CORRECT: ("-1  😕", C_ORANGE),
    Outcome.HIT_WRONG:      ("-2  ✗",  C_RED),
}


class FallingObject:
    """Um objeto que passa pela tela e pode ser derrubado."""

    def __init__(self, emoji: str, is_correct: bool, track_y: int, speed: float):
        self.emoji      = emoji
        self.is_correct = is_correct
        self.x          = float(WIN_W + S(60))
        self.y          = float(track_y)
        self.track_y    = track_y
        self.speed      = speed        # px/s horizontal — fixado no momento do spawn
        self.state      = "moving"     # moving | falling | done
        self.vy         = 0.0
        self.alpha      = 255
        self.will_hit   = False        # definido no momento do drop

        # Controle de pontuação — garante que cada objeto é resolvido
        # (pontuado) exatamente uma vez, não importa por qual caminho
        # ele termina (acerto, erro, ou simplesmente ignorado).
        self.was_dropped = False
        self.scored      = False

    def drop(self, target_cx: int, hit_margin: int = None):
        """
        Jogador levantou o braço.
        Define na hora se vai acertar (x dentro da margem do alvo).
        A queda é sempre reta — sem desvio horizontal.
        """
        if hit_margin is None:
            hit_margin = S(40)
        if self.state == "moving":
            self.state       = "falling"
            self.vy          = 0.0
            self.was_dropped = True
            self.will_hit    = abs(self.x - target_cx) <= hit_margin

    def update(self, dt: float) -> bool:
        """Retorna True quando o objeto deve ser removido."""
        if self.state == "moving":
            self.x -= self.speed * dt
            if self.x < -S(80):
                self.state = "done"    # saiu da tela sem ser derrubado

        elif self.state == "falling":
            self.vy += GRAVITY * dt   # gravidade — x não muda
            self.y  += self.vy * dt
            if self.y > WIN_H - S(60):
                self.alpha = max(0, self.alpha - 400 * dt)  # alpha: unidade 0-255, não espacial
                if self.alpha == 0:
                    self.state = "done"

        return self.state == "done"

    def get_rect(self) -> pygame.Rect:
        """Rect aproximado do emoji para colisão."""
        return pygame.Rect(int(self.x) - S(28), int(self.y) - S(28), S(56), S(56))


class Feedback:
    """Texto flutuante de acerto/erro/pontuação."""
    def __init__(self, text: str, color, cx: int, cy: int):
        self.text  = text
        self.color = color
        self.x     = cx
        self.y     = float(cy)
        self.life  = 1.2   # segundos — TEMPORAL, não escala
        self.alpha = 255

    def update(self, dt: float) -> bool:
        self.y    -= S(60) * dt
        self.life -= dt
        self.alpha = max(0, int(255 * (self.life / 1.2)))
        return self.life <= 0


class ScenePhase:
    def __init__(self, phase: int, lipe_surface: pygame.Surface = None):
        self.phase   = phase
        self._lipe   = lipe_surface
        self._cfg    = PHASE_CONFIG[phase]

        # Fontes (só para UI — emojis usam emoji_renderer)
        self._font_ui        = pygame.font.SysFont("Arial", S(18), bold=True)
        self._font_small     = pygame.font.SysFont("Arial", S(14))
        self._font_badge     = pygame.font.SysFont("Arial", S(17), bold=True)
        self._font_fb        = pygame.font.SysFont("Arial", S(38), bold=True)
        self._font_countdown = pygame.font.SysFont("Arial", S(96), bold=True)

        # Pré-carrega todos os emojis desta fase
        all_emojis = (self._cfg["correct"] + self._cfg["incorrect"]
                      + [self._cfg["target_emoji"]])
        preload(all_emojis, size=FONT_SIZE_OBJ)
        preload([self._cfg["target_emoji"]], size=FONT_SIZE_TGT)

        # Recipiente central
        self._target_rect = pygame.Rect(
            WIN_W // 2 - S(70), WIN_H // 2 + S(30), S(140), S(140)
        )
        self._target_surf = emoji_surface(
            self._cfg["target_emoji"], size=FONT_SIZE_TGT
        )

        # ── Estado de jogo ────────────────────────────────────────────────────
        self._objects: list[FallingObject] = []
        self._feedbacks: list[Feedback]    = []
        self._spawn_timer  = 0.0
        self._prev_raise   = False
        self._done         = False
        self._flash        = 0.0
        self._flash_color  = C_TEAL
        self._tick         = 0
        self._webcam_surf: pygame.Surface | None = None   # frame atual da câmera

        # ── Pontuação e progressão da rodada ──────────────────────────────────
        self._score        = ScoreTracker()
        self._resolved      = 0                    # objetos já resolvidos
        self._speed_level   = 0                     # índice em SPEED_LEVELS
        self._object_speed  = SPEED_LEVELS[0]

        # ── Contagem regressiva de início ─────────────────────────────────────
        # "countdown" (5→1) → "go" ("VAI!") → "playing" (jogo liberado)
        self._phase_state     = "countdown"
        self._countdown_value = COUNTDOWN_START
        self._countdown_timer = COUNTDOWN_SECONDS_PER_NUM
        self._go_timer        = 0.0

    # ── API pública ───────────────────────────────────────────────────────────
    @property
    def done(self) -> bool:
        return self._done

    @property
    def score(self) -> ScoreTracker:
        """Exposto para o loop principal usar em telas de resultado (V3)."""
        return self._score

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self._phase_state in ("countdown", "go"):
                # Atalho de dev: pula direto para o jogo
                self._phase_state = "playing"
            else:
                # Atalho de dev: pula direto para a próxima fase
                self._done = True

    def update(self, dt: float, gesture: GestureDetector,
               cam_packet: dict | None = None):
        self._tick += 1
        self._update_webcam(cam_packet)

        if self._phase_state == "countdown":
            self._update_countdown(dt)
            return
        if self._phase_state == "go":
            self._update_go_flash(dt)
            return

        # ── "playing": mecânica normal do jogo ─────────────────────────────────
        self._spawn_timer -= dt
        if self._spawn_timer <= 0:
            self._spawn_object()
            self._spawn_timer = SPAWN_INTERVAL

        # Gesto: borda de subida do braço
        raise_now   = gesture.raise_right or gesture.raise_left
        
        just_raised = raise_now and not self._prev_raise
        self._prev_raise = raise_now

        if just_raised:
            self._drop_nearest()

        # Atualiza objetos e resolve pontuação
        to_remove = []
        for obj in self._objects:
            finished = obj.update(dt)

            if obj.state == "falling":
                self._check_collision(obj)

            # Resolve (pontua) objetos que terminam SEM cair no alvo:
            # passaram direto pela tela, ou foram derrubados mas erraram.
            if not obj.scored:
                if obj.state == "done" and not obj.was_dropped:
                    self._resolve(obj, ended_in_target=False)
                elif (obj.state == "falling" and not obj.will_hit
                      and obj.y > WIN_H - S(60)):
                    self._resolve(obj, ended_in_target=False)

            if finished:
                to_remove.append(obj)

        for obj in to_remove:
            self._objects.remove(obj)

        # Feedbacks flutuantes
        self._feedbacks = [f for f in self._feedbacks if not f.update(dt)]

        # Flash de tela
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

        # Feedbacks flutuantes (acerto/erro/pontuação/nível de velocidade)
        for fb in self._feedbacks:
            fb_surf = self._font_fb.render(fb.text, True, fb.color)
            fb_surf.set_alpha(fb.alpha)
            surf.blit(fb_surf, fb_surf.get_rect(
                centerx=WIN_W // 2, centery=int(fb.y)))

        # HUD topo (fase, pontuação e progresso da rodada)
        self._draw_hud(surf)

        # Badge de instrução
        self._draw_badge(surf)

        # Webcam — canto inferior esquerdo
        self._draw_webcam(surf)

        # Indicador de braço (debug visual)
        self._draw_arm_indicator(surf)

        if self._phase_state in ("countdown", "go"):
            self._draw_countdown_overlay(surf)
        else:
            # Dica ENTER (atalho de desenvolvimento)
            hint = self._font_small.render(
                "ENTER → próxima fase (temporário)", True, (80, 80, 100))
            surf.blit(hint, (WIN_W - hint.get_width() - S(10), WIN_H - S(22)))

    # ── Internos: webcam ──────────────────────────────────────────────────────
    def _update_webcam(self, cam_packet: dict | None):
        """Atualiza a miniatura da webcam a partir do pacote da CameraThread."""
        if cam_packet is None:
            return
        import cv2
        frame = cam_packet["frame_rgb"]
        # Redimensiona para o tamanho do overlay
        frame_small = cv2.resize(frame, (S(160), S(120)))
        self._webcam_surf = pygame.surfarray.make_surface(
            frame_small.swapaxes(0, 1)
        )

    # ── Internos: contagem regressiva ─────────────────────────────────────────
    def _update_countdown(self, dt: float):
        self._countdown_timer -= dt
        if self._countdown_timer <= 0:
            self._countdown_value -= 1
            self._countdown_timer = COUNTDOWN_SECONDS_PER_NUM
            if self._countdown_value <= 0:
                self._phase_state = "go"
                self._go_timer    = GO_FLASH_SECONDS

    def _update_go_flash(self, dt: float):
        self._go_timer -= dt
        if self._go_timer <= 0:
            self._phase_state = "playing"

    # ── Internos: mecânica de jogo ────────────────────────────────────────────
    def _spawn_object(self):
        all_items = (
            [(e, True)  for e in self._cfg["correct"]] +
            [(e, False) for e in self._cfg["incorrect"]]
        )
        emoji, is_correct = random.choice(all_items)
        track = random.choice(TRACKS)
        self._objects.append(
            FallingObject(emoji, is_correct, track, speed=self._object_speed)
        )

    def _drop_nearest(self):
        """Derruba o objeto mais próximo do centro horizontal."""
        candidates = [o for o in self._objects if o.state == "moving"]
        if not candidates:
            return
        nearest = min(candidates, key=lambda o: abs(o.x - WIN_W // 2))
        nearest.drop(target_cx=self._target_rect.centerx)

    def _check_collision(self, obj: FallingObject):
        """
        Resultado (vai acertar ou não) já foi definido no drop() pelo x do
        objeto. Aqui só esperamos o objeto chegar na altura do alvo para
        resolver a pontuação — sem depender de colisão frame a frame.
        """
        if obj.state != "falling" or obj.scored:
            return
        if obj.y < self._target_rect.centery:
            return

        if obj.will_hit:
            self._resolve(obj, ended_in_target=True)
            obj.state = "done"   # some imediatamente dentro do recipiente
        # Se will_hit=False o objeto segue caindo e é resolvido mais tarde,
        # quando pousar no chão (ver update()).

    def _resolve(self, obj: FallingObject, ended_in_target: bool):
        """
        Ponto único de resolução de um objeto: registra a pontuação,
        dispara o feedback visual (texto + flash de tela) e avança o
        progresso da rodada (nível de velocidade / fim de fase).

        Garantido por `obj.scored` a nunca rodar duas vezes para o
        mesmo objeto, mesmo que seja chamado a partir de mais de um
        lugar (colisão com o alvo, pouso no chão, saída de tela).
        """
        if obj.scored:
            return
        obj.scored = True

        delta   = self._score.register(obj.is_correct, ended_in_target)
        outcome = self._score.last_outcome
        text, color = _FEEDBACK_BY_OUTCOME[outcome]

        self._feedbacks.append(
            Feedback(text, color, WIN_W // 2, WIN_H // 2 - S(80)))
        self._flash       = 0.25
        self._flash_color = color

        self._advance_round()

    def _advance_round(self):
        """
        Chamado a cada objeto resolvido. Controla a progressão de
        velocidade (a cada OBJECTS_PER_LEVEL objetos) e decide quando
        a fase termina (velocidade no teto + último lote concluído).
        """
        self._resolved += 1

        level_up = (self._resolved % OBJECTS_PER_LEVEL == 0
                    and self._speed_level < MAX_SPEED_INCREASES)
        if level_up:
            self._speed_level  += 1
            self._object_speed  = SPEED_LEVELS[self._speed_level]
            self._feedbacks.append(
                Feedback("⚡ Mais rápido!", C_YELLOW,
                         WIN_W // 2, WIN_H // 2 - S(130)))

        round_finished = (self._speed_level >= MAX_SPEED_INCREASES
                          and self._resolved >= TOTAL_OBJECTS_PER_PHASE)
        if round_finished:
            self._done = True

    # ── Desenho ───────────────────────────────────────────────────────────────
    def _draw_target(self, surf: pygame.Surface):
        import math
        # Anel pulsante
        pulse = 0.85 + 0.15 * math.sin(self._tick * 0.05)
        r = int(S(90) * pulse)
        ring_surf = pygame.Surface((r * 2 + S(4), r * 2 + S(4)), pygame.SRCALPHA)
        pygame.draw.circle(ring_surf, (*C_YELLOW, 60),
                           (r + S(2), r + S(2)), r, S(3))
        surf.blit(ring_surf, (
            self._target_rect.centerx - r - S(2),
            self._target_rect.centery - r - S(2),
        ))

        # Emoji do recipiente
        surf.blit(self._target_surf, self._target_surf.get_rect(
            center=self._target_rect.center))

        # Label
        lbl = self._font_ui.render(
            self._cfg["target_label"], True, C_YELLOW)
        surf.blit(lbl, lbl.get_rect(
            centerx=self._target_rect.centerx,
            top=self._target_rect.bottom + S(8)))

    def _draw_object(self, surf: pygame.Surface, obj: FallingObject):
        txt = emoji_surface(obj.emoji, size=FONT_SIZE_OBJ).copy()
        txt.set_alpha(obj.alpha)
        surf.blit(txt, txt.get_rect(
            centerx=int(obj.x), centery=int(obj.y)))

        # Sombra embaixo do objeto
        if obj.state == "moving":
            shadow = pygame.Surface((S(50), S(10)), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 60), shadow.get_rect())
            surf.blit(shadow, (int(obj.x) - S(25), obj.track_y + S(28)))

    def _draw_hud(self, surf: pygame.Surface):
        hud = pygame.Surface((WIN_W, S(56)), pygame.SRCALPHA)
        hud.fill((8, 4, 24, 210))
        surf.blit(hud, (0, 0))

        phase_txt = self._font_ui.render(
            f"FASE {self.phase}  —  {'Baú de Brinquedos 🧸' if self.phase == 1 else 'Cesto de Roupas 🧺'}",
            True, C_WHITE)
        surf.blit(phase_txt, (S(20), S(14)))

        # Pontuação + nível de velocidade, alinhados à direita
        score_txt = self._font_ui.render(
            f"Pontos: {self._score.total}   ⚡{self._speed_level}/{MAX_SPEED_INCREASES}",
            True, C_YELLOW)
        surf.blit(score_txt, (WIN_W - score_txt.get_width() - S(20), S(14)))

        # Barra de progresso da rodada
        progress = min(1.0, self._resolved / TOTAL_OBJECTS_PER_PHASE)
        bar_x, bar_y, bar_w, bar_h = S(20), S(42), WIN_W - S(40), S(6)
        pygame.draw.rect(surf, (40, 35, 70), (bar_x, bar_y, bar_w, bar_h), border_radius=S(3))
        pygame.draw.rect(surf, C_TEAL, (bar_x, bar_y, int(bar_w * progress), bar_h), border_radius=S(3))

    def _draw_badge(self, surf: pygame.Surface):
        badge_txt = self._font_badge.render(self._cfg["badge"], True, C_BG)
        bw = badge_txt.get_width() + S(30)
        bh = badge_txt.get_height() + S(10)
        bx = WIN_W // 2 - bw // 2
        by = S(66)
        badge_bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        badge_bg.fill((*self._cfg["badge_color"], 230))
        pygame.draw.rect(badge_bg, C_BG, (0, 0, bw, bh), S(2), border_radius=S(12))
        surf.blit(badge_bg, (bx, by))
        surf.blit(badge_txt, (bx + S(15), by + S(5)))

    def _draw_webcam(self, surf: pygame.Surface):
        """Overlay da webcam no canto inferior esquerdo."""
        W, H = S(160), S(120)
        x, y = S(8), WIN_H - H - S(8)

        # Borda
        pygame.draw.rect(surf, (60, 60, 80),
                         (x - S(2), y - S(2), W + S(4), H + S(4)), border_radius=S(8))

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
        surf.blit(lbl, (x, y - S(16)))

    def _draw_arm_indicator(self, surf: pygame.Surface):
        """Indicador visual de gesto no canto inferior direito."""
        color  = C_TEAL if self._prev_raise else (60, 60, 80)
        label  = "💪 BRAÇO LEVANTADO!" if self._prev_raise else "Levante o braço esquerdo"
        txt    = self._font_small.render(label, True, color)
        surf.blit(txt, (WIN_W - txt.get_width() - S(14), WIN_H - S(44)))
        pygame.draw.circle(surf, color, (WIN_W - txt.get_width() - S(26), WIN_H - S(36)), S(6))

    def _draw_countdown_overlay(self, surf: pygame.Surface):
        """Tela semitransparente com a contagem regressiva de início da fase."""
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((*C_BG, 165))
        surf.blit(overlay, (0, 0))

        if self._phase_state == "countdown":
            text, color = str(self._countdown_value), C_YELLOW
        else:  # "go"
            text, color = "VAI!", C_TEAL

        txt_surf = self._font_countdown.render(text, True, color)
        surf.blit(txt_surf, txt_surf.get_rect(center=(WIN_W // 2, WIN_H // 2)))

        sub = self._font_ui.render("Prepare-se!", True, C_WHITE)
        surf.blit(sub, sub.get_rect(centerx=WIN_W // 2, top=WIN_H // 2 + S(62)))