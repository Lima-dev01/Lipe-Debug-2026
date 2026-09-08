"""
emoji_renderer.py
Renderiza emojis coloridos via Pillow + NotoColorEmoji
e retorna pygame.Surface com alpha.

Uso:
    from src.emoji_renderer import emoji_surface
    surf = emoji_surface("🚗", size=52)
"""
import io
import pygame
from PIL import Image, ImageDraw, ImageFont

# ── Caminhos possíveis da fonte NotoColorEmoji ────────────────────────────────
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto-color-emoji/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/noto-color-emoji/NotoColorEmoji.ttf",
]

_emoji_font_path: str | None = None
for _p in _FONT_CANDIDATES:
    import os
    if os.path.exists(_p):
        _emoji_font_path = _p
        break

if _emoji_font_path is None:
    print("[EMOJI] NotoColorEmoji não encontrada — emojis podem aparecer como quadradinhos.")
    print("[EMOJI] Instale com: sudo apt install fonts-noto-color-emoji")

# ── Cache de surfaces ─────────────────────────────────────────────────────────
_cache: dict[tuple, pygame.Surface] = {}


def emoji_surface(emoji: str, size: int = 52) -> pygame.Surface:
    """
    Retorna um pygame.Surface (RGBA) com o emoji renderizado.
    Resultados são cacheados — chamar várias vezes com o mesmo
    emoji+size não recalcula.
    """
    key = (emoji, size)
    if key in _cache:
        return _cache[key]

    surf = _render(emoji, size)
    _cache[key] = surf
    return surf


def _render(emoji: str, size: int) -> pygame.Surface:
    # NotoColorEmoji usa tamanho fixo internamente (109px base).
    # Pedimos 109 e redimensionamos para o size desejado.
    NOTO_SIZE = 109

    if _emoji_font_path:
        try:
            font  = ImageFont.truetype(_emoji_font_path, NOTO_SIZE)
            # Canvas com espaço suficiente
            canvas = Image.new("RGBA", (NOTO_SIZE + 20, NOTO_SIZE + 20), (0, 0, 0, 0))
            draw   = ImageDraw.Draw(canvas)
            draw.text((2, 2), emoji, font=font, embedded_color=True)

            # Crop automático removendo área transparente
            bbox = canvas.getbbox()
            if bbox:
                canvas = canvas.crop(bbox)

            # Redimensiona para o tamanho pedido
            canvas = canvas.resize((size, size), Image.LANCZOS)

            return _pil_to_pygame(canvas)
        except Exception as e:
            print(f"[EMOJI] Erro ao renderizar '{emoji}': {e}")

    # Fallback: quadrado colorido com texto simples
    return _fallback(emoji, size)


def _pil_to_pygame(pil_img: Image.Image) -> pygame.Surface:
    """Converte PIL RGBA → pygame.Surface com alpha."""
    raw  = pil_img.tobytes("raw", "RGBA")
    surf = pygame.image.fromstring(raw, pil_img.size, "RGBA").convert_alpha()
    return surf


def _fallback(emoji: str, size: int) -> pygame.Surface:
    """Surface de fallback quando a fonte não está disponível."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    surf.fill((80, 80, 200, 200))
    font = pygame.font.SysFont("Arial", size // 3, bold=True)
    txt  = font.render("?", True, (255, 255, 255))
    surf.blit(txt, txt.get_rect(center=(size // 2, size // 2)))
    return surf


def preload(emojis: list[str], size: int = 52):
    """Pré-carrega uma lista de emojis no cache (chama antes do loop do jogo)."""
    for e in emojis:
        emoji_surface(e, size)
    print(f"[EMOJI] {len(emojis)} emojis pré-carregados (size={size})")