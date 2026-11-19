"""
assets.py
Loader centralizado de imagens, sons e fontes.
Todos os outros módulos importam daqui — nunca carregam arquivos direto.
"""
import os
import unicodedata
import pygame
from src.emoji_renderer import emoji_surface

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


def _is_emoji_char(ch: str) -> bool:
    """
    Heurística para separar emoji de texto comum: caracteres da
    categoria Unicode 'So' (Symbol, other) são emoji/símbolos na
    prática (▶ ℹ ✕ 🧍 👥 🧩 🔍 💡 ⚙ etc.), enquanto letras, números e
    pontuação comum (incluindo — e ...) ficam em outras categorias e
    continuam sendo desenhados pela fonte normal.
    Seletores de variação (ex.: o ️ depois de ⚙) e ZWJ são tratados como
    parte do emoji anterior, nunca como um "token" próprio.
    """
    if ch in ("\ufe0f", "\ufe0e", "\u200d"):
        return True
    return unicodedata.category(ch) == "So"


def render_mixed(text: str, size: int, color, bold: bool = False,
                  shadow: bool = False, shadow_color=(0, 0, 0)) -> pygame.Surface:
    """
    Como render_text(), mas reconhece emojis dentro da string e os
    desenha coloridos via emoji_renderer (o mesmo usado para os objetos
    e o recipiente nas fases), em vez de deixar a fonte do sistema
    desenhar um quadradinho "tofu" no lugar.

    Texto comum (incluindo acentos, espaços e pontuação) continua
    sendo desenhado pela fonte normal — só os trechos reconhecidos como
    emoji passam pelo renderizador colorido. Pode ser usado como
    substituto direto de render_text() em qualquer lugar.
    """
    if not text:
        return pygame.Surface((0, 0), pygame.SRCALPHA)

    # Agrupa a string em blocos consecutivos do mesmo tipo (emoji vs texto)
    chunks: list[tuple[bool, str]] = []
    cur_is_emoji = _is_emoji_char(text[0])
    cur = text[0]
    for ch in text[1:]:
        is_emoji = _is_emoji_char(ch)
        if is_emoji == cur_is_emoji:
            cur += ch
        else:
            chunks.append((cur_is_emoji, cur))
            cur, cur_is_emoji = ch, is_emoji
    chunks.append((cur_is_emoji, cur))

    # Emoji fica visualmente um pouco maior que o texto ao redor (senão
    # parece pequeno demais comparado à altura da fonte normal).
    emoji_size = max(1, int(size * 1.2))

    pieces: list[pygame.Surface] = []
    for is_emoji, chunk in chunks:
        if is_emoji:
            pieces.append(emoji_surface(chunk, size=emoji_size))
        else:
            pieces.append(render_text(chunk, size, color, bold=bold,
                                      shadow=shadow, shadow_color=shadow_color))

    total_w = sum(p.get_width() for p in pieces)
    total_h = max(p.get_height() for p in pieces)
    combined = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
    x = 0
    for surf in pieces:
        y = (total_h - surf.get_height()) // 2   # centraliza verticalmente
        combined.blit(surf, (x, y))
        x += surf.get_width()
    return combined