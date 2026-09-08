"""
assets.py
Loader centralizado de imagens, sons e fontes.
Todos os outros módulos importam daqui — nunca carregam arquivos direto.
"""
import os
import pygame

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _path(*parts):
    return os.path.join(_BASE, *parts)

# ── Imagens ──────────────────────────────────────────────────────────────────
def load_image(path: str, size: tuple = None, alpha: bool = False) -> pygame.Surface:
    """Carrega imagem e redimensiona se size=(w,h) for fornecido."""
    full = _path(path)
    img = pygame.image.load(full).convert_alpha() if alpha else pygame.image.load(full).convert()
    if size:
        img = pygame.transform.smoothscale(img, size)
    return img

# ── Fontes ────────────────────────────────────────────────────────────────────
_font_cache: dict = {}

def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("Arial", size, bold=bold)
    return _font_cache[key]

def font_path(rel_path: str, size: int) -> pygame.font.Font:
    """Carrega fonte customizada de assets/fonts/."""
    key = (rel_path, size)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.Font(_path("assets", "fonts", rel_path), size)
    return _font_cache[key]

# ── Helpers de texto ──────────────────────────────────────────────────────────
def render_text(text: str, size: int, color, bold: bool = False,
                shadow: bool = False, shadow_color=(0,0,0)) -> pygame.Surface:
    f = font(size, bold)
    if shadow:
        sh = f.render(text, True, shadow_color)
        base = f.render(text, True, color)
        surf = pygame.Surface((base.get_width()+2, base.get_height()+2), pygame.SRCALPHA)
        surf.blit(sh, (2, 2))
        surf.blit(base, (0, 0))
        return surf
    return f.render(text, True, color)