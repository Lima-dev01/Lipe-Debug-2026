"""
main.py — Jogo do LIPE  V1
- Menu completo (SceneMenu)
- Mecânica central: objetos caindo, gesto, colisão (ScenePhase)
- Câmera + MediaPipe rodando em thread separada
- Fullscreen com resolução interna fixa (canvas 800x600 escalado)
"""
import sys
import pygame


from src.config     import CONFIG
from src.game_state import GameState, State
from src.camera     import CameraThread
from src.gesture    import GestureDetector
from src.scenes.scene_menu  import SceneMenu
from src.scenes.scene_phase import ScenePhase
from src.scenes.scene_story import SceneStory

WIN_W = CONFIG["window"]["width"]
WIN_H = CONFIG["window"]["height"]
FPS   = CONFIG["window"]["fps"]
TITLE = CONFIG["window"]["title"]

# Fullscreen ligado/desligado por padrão (settings.json) e alternável
# em tempo real com F11. Todo o jogo continua desenhando num canvas
# interno fixo de WIN_W x WIN_H — só a apresentação final na tela real
# muda entre janela e tela cheia.
DEFAULT_FULLSCREEN = CONFIG["window"].get("fullscreen", False)
# Cenas de história (data/story.json) e para onde cada uma leva ao terminar.
STORY_NEXT = {
    State.INTRO_1:   State.INTRO_2,
    State.INTRO_2:   State.DECOMP,
    State.DECOMP:    State.PHASE_1,
    State.ABSTRACAO: State.PHASE_2,
    State.ALGORITMO: State.RESULT,
}


def load_lipe() -> pygame.Surface | None:
    import os
    path = os.path.join(os.path.dirname(__file__), "assets", "images", "lipe.png")
    if os.path.exists(path):
        return pygame.image.load(path).convert_alpha()
    print("[AVISO] assets/images/lipe.png não encontrado.")
    return None


def _create_display(fullscreen: bool) -> pygame.Surface:
    """
    Cria a superfície da janela real (a que o SO mostra).

    Em fullscreen usamos (0, 0) + FULLSCREEN, o que pede ao SDL pra usar
    a resolução atual do desktop — mais compatível entre monitores do
    que tentar forçar o modo de vídeo para 800x600 (que muitos monitores
    não suportam nativamente e pode gerar mudança de resolução ou
    barras pretas fora do nosso controle).
    """
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    return pygame.display.set_mode((WIN_W, WIN_H))


def _compute_render_rect(screen_w: int, screen_h: int) -> tuple[pygame.Rect, float]:
    """
    Calcula onde o canvas interno (WIN_W x WIN_H) deve ser desenhado
    dentro da tela real, preservando a proporção original — com barras
    pretas (letterbox/pillarbox) nas bordas quando a proporção da tela
    real não bate exatamente com a do jogo.
    """
    scale = min(screen_w / WIN_W, screen_h / WIN_H)
    render_w = int(WIN_W * scale)
    render_h = int(WIN_H * scale)
    x = (screen_w - render_w) // 2
    y = (screen_h - render_h) // 2
    return pygame.Rect(x, y, render_w, render_h), scale


def _screen_to_canvas(pos: tuple[int, int], render_rect: pygame.Rect,
                       scale: float) -> tuple[int, int]:
    """Converte uma posição em coordenadas da tela real para coordenadas
    do canvas interno de 800x600 (onde os botões/cenas são desenhados)."""
    sx, sy = pos
    return (int((sx - render_rect.x) / scale),
            int((sy - render_rect.y) / scale))


def _translate_event_pos(event: pygame.event.Event, render_rect: pygame.Rect,
                          scale: float) -> pygame.event.Event:
    """
    Devolve uma cópia do evento com 'pos' traduzido para coordenadas do
    canvas interno, para eventos de mouse (MOUSEBUTTONDOWN/UP/MOTION).
    Outros tipos de evento (teclado, etc.) voltam inalterados.
    Necessário porque scene_menu.py testa cliques com `event.pos`
    diretamente, além de usar mouse_pos separadamente para hover.
    """
    if not hasattr(event, "pos"):
        return event
    new_dict = dict(event.dict)
    new_dict["pos"] = _screen_to_canvas(event.pos, render_rect, scale)
    return pygame.event.Event(event.type, new_dict)


def draw_placeholder(screen, gs, font):
    screen.fill((20, 12, 45))
    msg  = font.render(f"Cena: {gs.current.name}  (em desenvolvimento)", True, (180, 180, 200))
    hint = font.render("ESC = voltar ao menu", True, (100, 100, 120))
    screen.blit(msg,  msg.get_rect(center=(WIN_W // 2, WIN_H // 2 - 20)))
    screen.blit(hint, hint.get_rect(center=(WIN_W // 2, WIN_H // 2 + 20)))


def main():
    pygame.init()

    fullscreen = DEFAULT_FULLSCREEN
    screen     = _create_display(fullscreen)
    pygame.display.set_caption(TITLE)

    # Canvas interno fixo — todas as cenas desenham aqui, sempre em
    # 800x600, não importa o tamanho real da tela. É esse canvas que
    # depois escalamos pra tela real a cada frame.
    canvas = pygame.Surface((WIN_W, WIN_H))

    clock = pygame.time.Clock()
    font  = pygame.font.SysFont("Arial", 18, bold=True)

    lipe_surface = load_lipe()

    # ── Estado e cenas ────────────────────────────────────────────────────────
    gs         = GameState()
    scene_menu = SceneMenu(lipe_surface=lipe_surface)
    scene_phase: ScenePhase | None = None
    scene_story: SceneStory | None = None

    # ── Câmera ────────────────────────────────────────────────────────────────
    cam     = CameraThread()
    gesture = GestureDetector()
    cam.start()
    print("[LIPE V1] Rodando... ESC volta ao menu.")

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # Onde o canvas 800x600 cai dentro da tela real neste frame, e
        # o mouse já convertido para as coordenadas do canvas.
        render_rect, scale = _compute_render_rect(*screen.get_size())
        mouse_pos = _screen_to_canvas(pygame.mouse.get_pos(), render_rect, scale)

        # ── Eventos ───────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if gs.current != State.MENU:
                    gs.go(State.MENU)
                    scene_menu.sub = "menu"
                    scene_phase    = None
                    scene_story    = None

            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                fullscreen = not fullscreen
                screen     = _create_display(fullscreen)
                continue  # tecla de sistema, não repassa pras cenas

            # Eventos de mouse chegam em coordenadas da tela real — traduz
            # pra coordenadas do canvas antes de repassar pras cenas.
            event = _translate_event_pos(event, render_rect, scale)

            if gs.current == State.MENU:
                scene_menu.handle_event(event, gs)

            elif gs.current in (State.PHASE_1, State.PHASE_2):
                if scene_phase:
                    scene_phase.handle_event(event)
                elif gs.current in STORY_NEXT and scene_story:
                   scene_story.handle_event(event)

        # ── Câmera / gesto ────────────────────────────────────────────────────
        packet = cam.get_latest()
        gesture.update(packet)
        # ── Cenas de história: cria ao entrar, avança ao terminar ────────────
        if gs.current in STORY_NEXT:
            if scene_story is None or scene_story.key != gs.current.name:
                scene_story = SceneStory(gs.current.name)
            if scene_story.done:
                gs.go(STORY_NEXT[gs.current])
                scene_story = None
        # ── Inicializa ScenePhase ao entrar na fase ───────────────────────────
        if gs.current == State.PHASE_1 and (
                scene_phase is None or scene_phase.phase != 1):
            scene_phase = ScenePhase(1, lipe_surface)

        if gs.current == State.PHASE_2 and (
                scene_phase is None or scene_phase.phase != 2):
            scene_phase = ScenePhase(2, lipe_surface)

        # ── Transição PHASE_1 → PHASE_2 quando done ──────────────────────────
        if gs.current == State.PHASE_1 and scene_phase and scene_phase.done:
            gs.go(State.ABSTRACAO)
            scene_phase = None

        if gs.current == State.PHASE_2 and scene_phase and scene_phase.done:
            gs.go(State.ALGORITMO)
            scene_phase = None

        # ── Update ────────────────────────────────────────────────────────────
        if gs.current == State.MENU:
            scene_menu.update(mouse_pos)

        elif gs.current in (State.PHASE_1, State.PHASE_2) and scene_phase:
            scene_phase.update(dt, gesture, cam_packet=packet)
        elif gs.current in STORY_NEXT and scene_story:
            scene_story.update(dt, gesture)
 

        # ── Draw (sempre no canvas interno 800x600) ─────────────────────────────
        if gs.current == State.MENU:
            scene_menu.draw(canvas)

        elif gs.current in (State.PHASE_1, State.PHASE_2) and scene_phase:
            scene_phase.draw(canvas)
        elif gs.current in STORY_NEXT and scene_story:
            scene_story.draw(canvas)

        else:
            draw_placeholder(canvas, gs, font)

        # ── Apresentação: escala o canvas pra tela real e centraliza ────────────
        screen.fill((0, 0, 0))  # barras pretas (letterbox) quando sobra espaço
        if scale == 1.0:
            screen.blit(canvas, render_rect.topleft)
        else:
            scaled = pygame.transform.smoothscale(canvas, render_rect.size)
            screen.blit(scaled, render_rect.topleft)

        pygame.display.flip()

    cam.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()