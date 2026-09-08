"""
main.py — Jogo do LIPE  V1
- Menu completo (SceneMenu)
- Mecânica central: objetos caindo, gesto, colisão (ScenePhase)
- Câmera + MediaPipe rodando em thread separada
"""
import sys
import pygame

from src.config     import CONFIG
from src.game_state import GameState, State
from src.camera     import CameraThread
from src.gesture    import GestureDetector
from src.scenes.scene_menu  import SceneMenu
from src.scenes.scene_phase import ScenePhase

WIN_W = CONFIG["window"]["width"]
WIN_H = CONFIG["window"]["height"]
FPS   = CONFIG["window"]["fps"]
TITLE = CONFIG["window"]["title"]


def load_lipe() -> pygame.Surface | None:
    import os
    path = os.path.join(os.path.dirname(__file__), "assets", "images", "lipe.png")
    if os.path.exists(path):
        return pygame.image.load(path).convert_alpha()
    print("[AVISO] assets/images/lipe.png não encontrado.")
    return None


def draw_placeholder(screen, gs, font):
    screen.fill((20, 12, 45))
    msg  = font.render(f"Cena: {gs.current.name}  (em desenvolvimento)", True, (180, 180, 200))
    hint = font.render("ESC = voltar ao menu", True, (100, 100, 120))
    screen.blit(msg,  msg.get_rect(center=(WIN_W // 2, WIN_H // 2 - 20)))
    screen.blit(hint, hint.get_rect(center=(WIN_W // 2, WIN_H // 2 + 20)))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()
    font  = pygame.font.SysFont("Arial", 18, bold=True)

    lipe_surface = load_lipe()

    # ── Estado e cenas ────────────────────────────────────────────────────────
    gs         = GameState()
    scene_menu = SceneMenu(lipe_surface=lipe_surface)
    scene_phase: ScenePhase | None = None

    # ── Câmera ────────────────────────────────────────────────────────────────
    cam     = CameraThread()
    gesture = GestureDetector()
    cam.start()
    print("[LIPE V1] Rodando... ESC volta ao menu.")

    running = True
    while running:
        dt        = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()

        # ── Eventos ───────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if gs.current != State.MENU:
                    gs.go(State.MENU)
                    scene_menu.sub = "menu"
                    scene_phase    = None

            if gs.current == State.MENU:
                scene_menu.handle_event(event, gs)

            elif gs.current in (State.PHASE_1, State.PHASE_2):
                if scene_phase:
                    scene_phase.handle_event(event)

        # ── Câmera / gesto ────────────────────────────────────────────────────
        packet = cam.get_latest()
        gesture.update(packet)
        # ── Transição INTRO_1 → PHASE_1 (placeholder direto por ora) ─────────
        if gs.current == State.INTRO_1:
            gs.go(State.PHASE_1)

        # ── Inicializa ScenePhase ao entrar na fase ───────────────────────────
        if gs.current == State.PHASE_1 and (
                scene_phase is None or scene_phase.phase != 1):
            scene_phase = ScenePhase(1, lipe_surface)

        if gs.current == State.PHASE_2 and (
                scene_phase is None or scene_phase.phase != 2):
            scene_phase = ScenePhase(2, lipe_surface)

        # ── Transição PHASE_1 → PHASE_2 quando done ──────────────────────────
        if gs.current == State.PHASE_1 and scene_phase and scene_phase.done:
            gs.go(State.PHASE_2)
            scene_phase = None

        if gs.current == State.PHASE_2 and scene_phase and scene_phase.done:
            gs.go(State.RESULT)
            scene_phase = None

        # ── Update ────────────────────────────────────────────────────────────
        if gs.current == State.MENU:
            scene_menu.update(mouse_pos)

        elif gs.current in (State.PHASE_1, State.PHASE_2) and scene_phase:
            scene_phase.update(dt, gesture, cam_packet=packet)

        # ── Draw ──────────────────────────────────────────────────────────────
        if gs.current == State.MENU:
            scene_menu.draw(screen)

        elif gs.current in (State.PHASE_1, State.PHASE_2) and scene_phase:
            scene_phase.draw(screen)

        else:
            draw_placeholder(screen, gs, font)

        pygame.display.flip()

    cam.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()