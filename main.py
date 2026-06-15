"""
main.py — Jogo do LIPE  V0
Loop principal com:
  - Janela Pygame 800×600
  - Overlay da webcam com landmarks MediaPipe
  - Detecção de gesto (braço direito/esquerdo levantado)
  - HUD de debug mostrando estado do gesto em tempo real
"""

import sys
import numpy as np
import pygame
import cv2

from src.config  import CONFIG
from src.camera  import CameraThread
from src.gesture import GestureDetector

# ── Configurações ─────────────────────────────────────────────────────────────
WIN_W   = CONFIG["window"]["width"]
WIN_H   = CONFIG["window"]["height"]
FPS     = CONFIG["window"]["fps"]
TITLE   = CONFIG["window"]["title"]
SHOW_OV = CONFIG["camera"]["show_overlay"]
OV_ALPHA= CONFIG["camera"]["overlay_alpha"]
DEBUG   = CONFIG["debug"]

# ── Cores ─────────────────────────────────────────────────────────────────────
C_BG         = (30,  30,  40)
C_WHITE      = (255, 255, 255)
C_GREEN      = (50,  220, 120)
C_RED        = (220,  60,  60)
C_YELLOW     = (255, 210,  50)
C_DARK       = (15,  15,  20)
C_OVERLAY_BG = (20,  20,  30, 200)


def frame_to_surface(frame_rgb: np.ndarray, target_size: tuple) -> pygame.Surface:
    """Converte ndarray RGB do OpenCV em pygame.Surface redimensionada."""
    h, w = frame_rgb.shape[:2]
    # Redimensiona mantendo proporção dentro de target_size
    tw, th = target_size
    scale  = min(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = cv2.resize(frame_rgb, (nw, nh))
    # numpy H×W×3 → pygame precisa de (W, H) e transposta dos eixos
    surface = pygame.surfarray.make_surface(resized.swapaxes(0, 1))
    return surface


def draw_hud(screen: pygame.Surface, font: pygame.font.Font,
             small_font: pygame.font.Font,
             raise_left: bool, raise_right: bool, fps: float):
    """Desenha HUD de debug com estado dos gestos e FPS."""

    # Painel inferior
    panel = pygame.Surface((WIN_W, 70), pygame.SRCALPHA)
    panel.fill((15, 15, 20, 210))
    screen.blit(panel, (0, WIN_H - 70))

    # Estado braço direito
    cor_r = C_GREEN if raise_right else C_RED
    label_r = "DIREITO ↑" if raise_right else "direito ↓"
    txt_r = font.render(f"Braço {label_r}", True, cor_r)
    screen.blit(txt_r, (20, WIN_H - 55))

    # Estado braço esquerdo
    cor_l = C_GREEN if raise_left else C_RED
    label_l = "ESQUERDO ↑" if raise_left else "esquerdo ↓"
    txt_l = font.render(f"Braço {label_l}", True, cor_l)
    screen.blit(txt_l, (WIN_W // 2, WIN_H - 55))

    # FPS
    fps_txt = small_font.render(f"FPS: {fps:.0f}", True, C_YELLOW)
    screen.blit(fps_txt, (WIN_W - 90, WIN_H - 55))

    # Versão
    ver_txt = small_font.render("LIPE V0 — Prova de Conceito", True, (120, 120, 140))
    screen.blit(ver_txt, (20, WIN_H - 25))


def draw_overlay_label(screen: pygame.Surface, small_font: pygame.font.Font):
    """Etiqueta no canto do overlay da câmera."""
    lbl = small_font.render("webcam + MediaPipe", True, (180, 180, 200))
    screen.blit(lbl, (WIN_W - lbl.get_width() - 10, 8))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()

    font       = pygame.font.SysFont("Arial", 18, bold=True)
    small_font = pygame.font.SysFont("Arial", 14)
    title_font = pygame.font.SysFont("Arial", 32, bold=True)

    # ── Inicia câmera em thread separada ─────────────────────────────────────
    cam     = CameraThread()
    gesture = GestureDetector()
    cam.start()

    last_surface = None   # último frame da câmera convertido

    print("[LIPE V0] Iniciando... pressione ESC para sair.")

    running = True
    while running:

        # ── Eventos ──────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # ── Atualiza câmera / gesto ───────────────────────────────────────────
        packet = cam.get_latest()
        gesture.update(packet)

        if packet is not None:
            ov_w = WIN_W // 3        # overlay ocupa 1/3 da largura
            ov_h = int(ov_w * 0.75)  # mantém proporção 4:3
            last_surface = frame_to_surface(packet["frame_rgb"], (ov_w, ov_h))

        # ── Desenha ───────────────────────────────────────────────────────────
        screen.fill(C_BG)

        # Título central (placeholder até ter assets)
        title_txt = title_font.render("Jogo do LIPE", True, C_WHITE)
        screen.blit(title_txt, (WIN_W // 2 - title_txt.get_width() // 2, 40))

        sub_txt = small_font.render(
            "V0 — câmera e detecção de gesto funcionando", True, (140, 140, 160)
        )
        screen.blit(sub_txt, (WIN_W // 2 - sub_txt.get_width() // 2, 85))

        # Instrução
        inst = font.render(
            "Levante o braço direito para testar o gesto", True, (200, 200, 220)
        )
        screen.blit(inst, (WIN_W // 2 - inst.get_width() // 2, WIN_H // 2 - 20))

        # Indicador visual grande de gesto
        if gesture.raise_right:
            circ_color = C_GREEN
            circ_txt   = font.render("GESTO DETECTADO!", True, C_GREEN)
        else:
            circ_color = (60, 60, 80)
            circ_txt   = font.render("aguardando gesto...", True, (100, 100, 120))

        pygame.draw.circle(screen, circ_color, (WIN_W // 2, WIN_H // 2 + 60), 30, 4)
        screen.blit(circ_txt, (WIN_W // 2 - circ_txt.get_width() // 2, WIN_H // 2 + 100))

        # Overlay câmera (canto superior direito)
        if SHOW_OV and last_surface is not None:
            ov_x = WIN_W - last_surface.get_width() - 10
            ov_y = 10
            # Borda
            pygame.draw.rect(screen, (80, 80, 100),
                             (ov_x - 2, ov_y - 2,
                              last_surface.get_width() + 4,
                              last_surface.get_height() + 4), 2)
            screen.blit(last_surface, (ov_x, ov_y))
            draw_overlay_label(screen, small_font)

        # HUD inferior
        draw_hud(screen, font, small_font,
                 gesture.raise_right, gesture.raise_left,
                 clock.get_fps())

        pygame.display.flip()
        clock.tick(FPS)

    # ── Encerra ───────────────────────────────────────────────────────────────
    cam.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()